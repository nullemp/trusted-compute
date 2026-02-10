"""
Client call: accept DDL + data files, create DB/tables, import data, then run SQL or Python analysis.
No frontend; for client process.
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
    """Split DDL by semicolon; drop empty and comment lines."""
    # Simple split by ; (quoted semicolons not handled; client DDL should be well-formed)
    parts = re.split(r";\s*", ddl.strip())
    out = []
    for p in parts:
        p = p.strip()
        if not p or p.startswith("--"):
            continue
        out.append(p + ";")
    return out


def _rewrite_ddl_for_job_db(statement: str, job_db: str) -> Optional[str]:
    """Skip CREATE DATABASE; rewrite USE xxx to USE job_db; rest unchanged."""
    s = statement.strip().upper()
    if s.startswith("CREATE DATABASE"):
        return None
    if s.startswith("USE "):
        return f"USE `{job_db}`;"
    return statement


def _run_ddl_in_job_db(cursor, ddl_text: str, job_db: str) -> None:
    """Execute client DDL on connection already USE job_db (CREATE DATABASE/USE filtered)."""
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
    In current DB (job DB): create table from config if not exists, then LOAD DATA.
    table_name must exist (from DDL) or be created by this function from ddl/first line.
    """
    file_path = os.path.abspath(file_path)
    upload_dir_abs = os.path.abspath(upload_dir)
    if not os.path.isfile(file_path) or not file_path.startswith(upload_dir_abs):
        raise ValueError(f"File not found or path not allowed: {file_path}")

    table_name = _sanitize_identifier(table_name) or "input_data"
    path_escaped = file_path.replace("\\", "\\\\").replace("'", "\\'")
    if delimiter == "\t":
        delim_sql = "'\\t'"
    elif delimiter == "|":
        delim_sql = "'|'"
    else:
        delim_sql = repr(delimiter)
    ignore_lines = "IGNORE 1 LINES" if has_header else ""

    # Check if table exists (cursor already USE job_db)
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    if not cursor.fetchone():
        # Table does not exist, create
        if ddl:
            col_list = _parse_ddl(ddl)
            if not col_list:
                raise ValueError("Invalid DDL format")
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
    Flow: create job DB -> run DDL (tables etc.) -> import data files per config -> run SQL or Python analysis -> drop DB.
    - ddl_text: optional DDL SQL (may include CREATE DATABASE/USE/CREATE TABLE)
    - table_configs: 1:1 with file_paths; each table_name, has_header?, delimiter?, ddl?, columns?
    - analysis_type: "sql" | "python"
    - analysis_sql: SQL to run when analysis_type=sql
    - analysis_python: Python code when analysis_type=python (must define result)
    - data_sql: when analysis_type=python, SQL to fetch data into input_params["data"]; else analysis_sql or SELECT * FROM first table
    """
    if len(file_paths) != len(table_configs):
        return {"status": "error", "error": f"Data file count ({len(file_paths)}) does not match table config count ({len(table_configs)})"}
    if analysis_type not in ("sql", "python"):
        return {"status": "error", "error": "analysis_type must be sql or python"}
    if analysis_type == "sql" and not (analysis_sql and analysis_sql.strip()):
        return {"status": "error", "error": "analysis_sql required when analysis_type=sql"}
    if analysis_type == "python" and not (analysis_python and analysis_python.strip()):
        return {"status": "error", "error": "analysis_python required when analysis_type=python"}

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

        # Python: fetch data with data_sql or analysis_sql or "SELECT * FROM first_table", pass to sandbox
        run_sql = (data_sql or analysis_sql or "").strip() or (f"SELECT * FROM `{first_table}`" if first_table else "")
        if not run_sql:
            return {"status": "error", "error": "Provide data_sql or analysis_sql for analysis_type=python, or have at least one table to SELECT"}
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
