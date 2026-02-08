"""
客户端调用：接收 DDL 文件 + 数据文件，建库/建表、导入数据，再执行 SQL 或 Python 分析。
不依赖前端，供客户端进程调用。
"""
import json
import os
import re
import uuid
from typing import List, Any, Dict, Optional

from database import engine
from services.execute_sql_service import (
    UPLOAD_DIR,
    _build_create_and_load_for_file,
    _parse_ddl,
    _sanitize_identifier,
)
from services import sandbox_service

_COL_TYPE = "TEXT"


def _job_db_name() -> str:
    return "tc_job_" + uuid.uuid4().hex[:16]


def _split_ddl_statements(ddl: str) -> List[str]:
    """按分号拆分 DDL，去掉空语句和注释行。"""
    # 简单按 ; 拆分，保留引号内分号不拆（此处不处理复杂情况，客户 DDL 应规范）
    parts = re.split(r";\s*", ddl.strip())
    out = []
    for p in parts:
        p = p.strip()
        if not p or p.startswith("--"):
            continue
        out.append(p + ";")
    return out


def _rewrite_ddl_for_job_db(statement: str, job_db: str) -> Optional[str]:
    """跳过 CREATE DATABASE；将 USE xxx 改为 USE job_db；其余原样。"""
    s = statement.strip().upper()
    if s.startswith("CREATE DATABASE"):
        return None
    if s.startswith("USE "):
        return f"USE `{job_db}`;"
    return statement


def _run_ddl_in_job_db(cursor, ddl_text: str, job_db: str) -> None:
    """在已 USE job_db 的连接上执行客户 DDL（已过滤 CREATE DATABASE / USE）。"""
    for stmt in _split_ddl_statements(ddl_text):
        rewritten = _rewrite_ddl_for_job_db(stmt, job_db)
        if rewritten is None:
            continue
        cursor.execute(rewritten)


def _load_data_into_table(
    cursor,
    file_path: str,
    table_name: str,
    upload_dir: str,
    has_header: bool = True,
    delimiter: str = ",",
    columns_override: Optional[List[str]] = None,
    ddl: Optional[str] = None,
) -> None:
    """
    在当前 DB（job DB）中：若表不存在则用 config 建表，再 LOAD DATA。
    table_name 必须已存在（由 DDL 创建）或由本函数根据 ddl/文件首行创建。
    """
    file_path = os.path.abspath(file_path)
    upload_dir_abs = os.path.abspath(upload_dir)
    if not os.path.isfile(file_path) or not file_path.startswith(upload_dir_abs):
        raise ValueError(f"文件不存在或路径不允许: {file_path}")

    table_name = _sanitize_identifier(table_name) or "input_data"
    path_escaped = file_path.replace("\\", "\\\\").replace("'", "\\'")
    if delimiter == "\t":
        delim_sql = "'\\t'"
    elif delimiter == "|":
        delim_sql = "'|'"
    else:
        delim_sql = repr(delimiter)
    ignore_lines = "IGNORE 1 LINES" if has_header else ""

    # 检查表是否存在（cursor 已 USE job_db）
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    if not cursor.fetchone():
        # 表不存在，创建
        if ddl:
            col_list = _parse_ddl(ddl)
            if not col_list:
                raise ValueError("DDL 格式无效")
            create_sql = f"CREATE TABLE `{table_name}` ({col_list})"
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                first = f.readline().rstrip("\r\n")
            if columns_override:
                cols = [_sanitize_identifier(c) for c in columns_override]
            else:
                cols = [_sanitize_identifier(h.strip().strip('"') or f"col_{i}") for i, h in enumerate(first.split(delimiter))]
            col_list = ", ".join(f"`{c}` {_COL_TYPE}" for c in cols)
            create_sql = f"CREATE TABLE `{table_name}` ({col_list})"
        cursor.execute(create_sql)

    load_sql = (
        f"LOAD DATA LOCAL INFILE '{path_escaped}' "
        f"INTO TABLE `{table_name}` "
        f"CHARACTER SET utf8mb4 "
        f"FIELDS TERMINATED BY {delim_sql} ENCLOSED BY '\"' "
        f"LINES TERMINATED BY '\\n' {ignore_lines}"
    )
    cursor.execute(load_sql)


def run_analysis(
    ddl_text: Optional[str],
    table_configs: List[Dict[str, Any]],
    file_paths: List[str],
    analysis_type: str,
    analysis_sql: Optional[str] = None,
    analysis_python: Optional[str] = None,
    data_sql: Optional[str] = None,
) -> Dict[str, Any]:
    """
    流程：创建 job 库 → 执行 DDL（建表等）→ 按 config 将数据文件导入对应表 → 执行 SQL 或 Python 分析 → 删库。
    - ddl_text: 可选，DDL SQL（可含 CREATE DATABASE / USE / CREATE TABLE）
    - table_configs: 与 file_paths 一一对应，每项 table_name, has_header?, delimiter?, ddl?, columns?
    - analysis_type: "sql" | "python"
    - analysis_sql: analysis_type=sql 时执行的 SQL
    - analysis_python: analysis_type=python 时的 Python 代码（需定义 result）
    - data_sql: analysis_type=python 时，用该 SQL 取数据传入 input_params["data"]；不传则用 analysis_sql 或 "SELECT * FROM 第一张表"
    """
    if len(file_paths) != len(table_configs):
        return {"status": "error", "error": f"数据文件数量({len(file_paths)})与表配置数量({len(table_configs)})不一致"}
    if analysis_type not in ("sql", "python"):
        return {"status": "error", "error": "analysis_type 须为 sql 或 python"}
    if analysis_type == "sql" and not (analysis_sql and analysis_sql.strip()):
        return {"status": "error", "error": "analysis_type=sql 时须提供 analysis_sql"}
    if analysis_type == "python" and not (analysis_python and analysis_python.strip()):
        return {"status": "error", "error": "analysis_type=python 时须提供 analysis_python"}

    job_db = _job_db_name()
    upload_dir = os.path.abspath(UPLOAD_DIR)
    conn = engine.raw_connection()
    cursor = None
    first_table = None

    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE `{job_db}`")
        cursor.execute(f"USE `{job_db}`")

        if ddl_text and ddl_text.strip():
            _run_ddl_in_job_db(cursor, ddl_text, job_db)

        for i, (path, cfg) in enumerate(zip(file_paths, table_configs)):
            tname = _sanitize_identifier(cfg.get("table_name") or f"t{i}") or f"t{i}"
            if first_table is None:
                first_table = tname
            delim = cfg.get("delimiter", ",")
            if isinstance(delim, str) and len(delim) != 1:
                delim = "\t" if delim.strip().lower() in ("\\t", "tab") else ","
            _load_data_into_table(
                cursor=cursor,
                file_path=path,
                table_name=tname,
                upload_dir=upload_dir,
                has_header=cfg.get("has_header", True),
                delimiter=delim,
                columns_override=cfg.get("columns"),
                ddl=cfg.get("ddl"),
            )

        if analysis_type == "sql":
            cursor.execute(analysis_sql)
            if cursor.description:
                result_columns = [d[0] for d in cursor.description]
                result_rows = cursor.fetchall()
                result_rows = [list(r) for r in result_rows]
                return {
                    "status": "success",
                    "analysis_type": "sql",
                    "result": {
                        "columns": result_columns,
                        "data": result_rows,
                        "row_count": len(result_rows),
                    },
                }
            return {
                "status": "success",
                "analysis_type": "sql",
                "result": {"row_count": cursor.rowcount},
            }

        # Python：用 data_sql 或 analysis_sql 或 "SELECT * FROM first_table" 取数据，传入沙箱
        run_sql = (data_sql or analysis_sql or "").strip() or (f"SELECT * FROM `{first_table}`" if first_table else "")
        if not run_sql:
            return {"status": "error", "error": "analysis_type=python 时需提供 data_sql 或 analysis_sql，或至少有表可 SELECT"}
        cursor.execute(run_sql)
        if cursor.description:
            result_columns = [d[0] for d in cursor.description]
            result_rows = cursor.fetchall()
            data_for_python = [list(r) for r in result_rows]
        else:
            result_columns = []
            data_for_python = []

        payload = {
            "model_type": "python",
            "model_code": analysis_python,
            "input_params": {"data": data_for_python, "columns": result_columns, "table_name": "data"},
        }
        sandbox = sandbox_service.SandboxService()
        import io
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if sandbox.sandbox_mode == "local":
            proc = sandbox._run_local(stdin_bytes)
        else:
            proc = sandbox._run_docker(stdin_bytes)

        if proc.returncode != 0:
            return {
                "status": "error",
                "analysis_type": "python",
                "error": (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace"),
            }
        try:
            out = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            return {"status": "error", "analysis_type": "python", "error": f"解析 Python 输出失败: {e}"}
        if out.get("status") == "error":
            return {"status": "error", "analysis_type": "python", "error": out.get("error", "未知错误")}
        return {
            "status": "success",
            "analysis_type": "python",
            "result": out.get("result"),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if cursor:
            try:
                cursor.execute(f"DROP DATABASE IF EXISTS `{job_db}`")
            except Exception:
                pass
            cursor.close()
        conn.close()
