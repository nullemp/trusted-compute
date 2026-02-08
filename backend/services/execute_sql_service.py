"""
直接执行 SQL 服务：将数据插入 MariaDB 临时表后执行用户 SQL，返回结果。
- execute_sql_mariadb: JSON 数据入库后执行（适合中小数据量）
- execute_sql_from_file: 文件上传 + LOAD DATA LOCAL INFILE（适合亿行级）
"""
import os
from typing import List, Any, Dict, Optional, Union, Tuple

from database import engine

# 临时表列类型：TEXT 支持较大单格，大数据量用 MariaDB 落盘
_COL_TYPE = "TEXT"
_BATCH_SIZE = 5000


def _sanitize_identifier(name: str) -> str:
    """只保留字母、数字、下划线，用于表名和列名."""
    return "".join(c for c in name if c.isalnum() or c == "_") or "col"


def _normalize_data(
    data: List[Union[List[Any], Dict[str, Any]]],
    columns: Optional[List[str]] = None,
) -> Tuple[List[str], List[List[Any]]]:
    """得到列名列表和行数据（每行为 list）。"""
    if not data:
        return [], []
    rows = data
    if columns is None and isinstance(rows[0], dict):
        columns = list(rows[0].keys())
        rows = [[r[c] for c in columns] for r in rows]
    elif columns is None and isinstance(rows[0], (list, tuple)):
        columns = [f"col_{i}" for i in range(len(rows[0]))]
    else:
        columns = columns or [f"col_{i}" for i in range(len(rows[0]))]
    # 统一为 list of list，值为 str 或 number
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append([r.get(c) for c in columns])
        else:
            out.append(list(r))
    return [_sanitize_identifier(c) for c in columns], out


def execute_sql_mariadb(
    data: List[Union[List[Any], Dict[str, Any]]],
    sql: str,
    table_name: str = "input_data",
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    在 MariaDB 中创建临时表、插入 data、执行 sql，返回结果。
    临时表随连接关闭自动销毁，支持大数据量。
    """
    table_name = _sanitize_identifier(table_name) or "input_data"
    cols, rows = _normalize_data(data, columns)
    if not cols:
        return {"status": "error", "error": "数据或列名为空"}

    # 列名用反引号包裹，避免保留字
    col_list = ", ".join(f"`{c}` {_COL_TYPE}" for c in cols)
    create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO `{table_name}` ({','.join('`' + c + '`' for c in cols)}) VALUES ({placeholders})"

    conn = engine.raw_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(create_sql)

        # 批量插入
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = [tuple(str(v) if v is not None else "" for v in row) for row in rows[i : i + _BATCH_SIZE]]
            cursor.executemany(insert_sql, batch)

        # 执行用户 SQL（单条语句）
        cursor.execute(sql)
        if cursor.description:
            result_columns = [d[0] for d in cursor.description]
            result_rows = cursor.fetchall()
            result_rows = [list(r) for r in result_rows]
            return {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows,
                    "row_count": len(result_rows),
                },
            }
        else:
            return {
                "status": "success",
                "type": "sql",
                "result": {"row_count": cursor.rowcount},
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if cursor:
            try:
                cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{table_name}`")
            except Exception:
                pass
            cursor.close()
        conn.close()


# 文件上传后保存到此目录，LOAD DATA 时仅允许读此目录下文件
UPLOAD_DIR = os.environ.get("TRUSTED_COMPUTE_UPLOAD_DIR", "/tmp/trusted_compute_upload")

# DDL 中允许的类型：仅包含安全字符 [A-Za-z0-9(),.]
_TYPE_SAFE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789(),. ")


def parse_ddl_file(content: str) -> Dict[str, str]:
    """
    从数据库导出的 SQL 文件（如 schema.sql）中解析每个 CREATE TABLE，
    返回 { 表名: "列定义串" }，列定义即括号内部分，如 "id INT, name VARCHAR(100)"。
    用于用同一份 DDL 文件作为建表依据。
    """
    out: Dict[str, str] = {}
    lower_content = content.lower()
    pos = 0
    while True:
        idx = lower_content.find("create table", pos)
        if idx < 0:
            break
        # 跳过 CREATE TABLE [IF NOT EXISTS]，取表名（`name` 或 name）
        start = idx + len("create table")
        rest = content[start:].lstrip()
        if rest.lower().startswith("if not exists"):
            rest = rest[12:].lstrip()
        if rest.startswith("`"):
            end = rest.index("`", 1) + 1
            table_name = rest[1 : end - 1]
        else:
            end = 0
            while end < len(rest) and (rest[end].isalnum() or rest[end] == "_"):
                end += 1
            table_name = rest[:end]
        rest = rest[end:].lstrip()
        if not rest.startswith("("):
            pos = start
            continue
        # 找匹配的右括号（列类型里可能有 VARCHAR(20) 等）
        depth = 0
        i = 0
        for i, c in enumerate(rest):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
        body = rest[1:i].strip()
        body = " ".join(body.split()).strip()
        table_name = _sanitize_identifier(table_name)
        if table_name and body:
            out[table_name] = body
        pos = start + end + 1 + i + 1
    return out


def _split_ddl_by_comma(ddl: str) -> List[str]:
    """按逗号分割 DDL，但忽略括号内的逗号（如 DECIMAL(10,2)、VARCHAR(20)）。"""
    out: List[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(ddl):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            out.append(ddl[start:i].strip())
            start = i + 1
    if start < len(ddl):
        out.append(ddl[start:].strip())
    return out


def _parse_ddl(ddl: str) -> Optional[str]:
    """
    解析 DDL 表体（括号内部分），返回安全的 CREATE 列定义串。
    例如 "id INT, value DECIMAL(10,2), name VARCHAR(100)" -> "`id` INT, `value` DECIMAL(10,2), `name` VARCHAR(100)"
    按逗号分割时忽略括号内逗号，避免 DECIMAL(10,2) 被拆开。
    """
    if not ddl or not ddl.strip():
        return None
    parts = []
    for part in _split_ddl_by_comma(ddl):
        if not part:
            continue
        # 第一个空格前为列名，其余为类型
        idx = part.find(" ")
        if idx <= 0:
            continue
        name = _sanitize_identifier(part[:idx].strip())
        type_str = part[idx + 1 :].strip()
        if not name or not type_str:
            continue
        if not all(c in _TYPE_SAFE_CHARS for c in type_str):
            continue
        parts.append(f"`{name}` {type_str}")
    return ", ".join(parts) if parts else None


def execute_sql_from_file(
    file_path: str,
    sql: str,
    table_name: str = "input_data",
    has_header: bool = True,
    delimiter: str = ",",
    columns_override: Optional[List[str]] = None,
    ddl: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用 MariaDB LOAD DATA LOCAL INFILE 将 CSV 文件导入临时表后执行 SQL。
    不将文件全部读入应用内存，支持亿行级数据。
    file_path: 后端可读的绝对路径（应位于 UPLOAD_DIR 下）。
    ddl: 可选。表结构，即 CREATE TABLE 括号内部分，如 "id INT, value DECIMAL(10,2), name VARCHAR(100)"。
         CSV 列顺序须与 DDL 列顺序一致。不传则从首行推断列名，类型均为 TEXT。
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return {"status": "error", "error": f"文件不存在: {file_path}"}
    upload_dir = os.path.abspath(UPLOAD_DIR)
    if not file_path.startswith(upload_dir):
        return {"status": "error", "error": "文件路径不允许"}

    table_name = _sanitize_identifier(table_name) or "input_data"

    if ddl:
        col_list = _parse_ddl(ddl)
        if not col_list:
            return {"status": "error", "error": "DDL 格式无效，示例: id INT, value DECIMAL(10,2), name VARCHAR(100)"}
        create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"
    else:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                first = f.readline()
        except Exception as e:
            return {"status": "error", "error": f"读取文件失败: {e}"}
        first = first.rstrip("\r\n")
        if columns_override:
            cols = [_sanitize_identifier(c) for c in columns_override]
        elif has_header:
            cols = [_sanitize_identifier(h.strip().strip('"') or f"col_{i}") for i, h in enumerate(first.split(delimiter))]
        else:
            n = len(first.split(delimiter))
            cols = [f"col_{i}" for i in range(n)]
        if not cols:
            return {"status": "error", "error": "无法推断列"}
        col_list = ", ".join(f"`{c}` {_COL_TYPE}" for c in cols)
        create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"

    path_escaped = file_path.replace("\\", "\\\\").replace("'", "\\'")
    if delimiter == "\t":
        delim_sql = "'\\t'"
    elif delimiter == "|":
        delim_sql = "'|'"
    else:
        delim_sql = repr(delimiter)
    ignore_lines = "IGNORE 1 LINES" if has_header else ""
    load_sql = (
        f"LOAD DATA LOCAL INFILE '{path_escaped}' "
        f"INTO TABLE `{table_name}` "
        f"CHARACTER SET utf8mb4 "
        f"FIELDS TERMINATED BY {delim_sql} ENCLOSED BY '\"' "
        f"LINES TERMINATED BY '\\n' {ignore_lines}"
    )

    conn = engine.raw_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(create_sql)
        cursor.execute(load_sql)

        cursor.execute(sql)
        if cursor.description:
            result_columns = [d[0] for d in cursor.description]
            result_rows = cursor.fetchall()
            result_rows = [list(r) for r in result_rows]
            return {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows,
                    "row_count": len(result_rows),
                },
            }
        else:
            return {
                "status": "success",
                "type": "sql",
                "result": {"row_count": cursor.rowcount},
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if cursor:
            try:
                cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{table_name}`")
            except Exception:
                pass
            cursor.close()
        conn.close()


def _build_create_and_load_for_file(
    file_path: str,
    upload_dir: str,
    table_name: str,
    has_header: bool = True,
    delimiter: str = ",",
    columns_override: Optional[List[str]] = None,
    ddl: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    为单文件构建 CREATE 与 LOAD SQL。返回 (table_name_safe, create_sql, load_sql)。
    不做连接，仅做路径校验与 SQL 拼接。
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        raise ValueError(f"文件不存在: {file_path}")
    upload_dir_abs = os.path.abspath(upload_dir)
    if not file_path.startswith(upload_dir_abs):
        raise ValueError("文件路径不允许")

    table_name = _sanitize_identifier(table_name) or "input_data"
    path_escaped = file_path.replace("\\", "\\\\").replace("'", "\\'")
    if delimiter == "\t":
        delim_sql = "'\\t'"
    elif delimiter == "|":
        delim_sql = "'|'"
    else:
        delim_sql = repr(delimiter)
    ignore_lines = "IGNORE 1 LINES" if has_header else ""

    if ddl:
        col_list = _parse_ddl(ddl)
        if not col_list:
            raise ValueError("DDL 格式无效")
        create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            first = f.readline()
        first = first.rstrip("\r\n")
        if columns_override:
            cols = [_sanitize_identifier(c) for c in columns_override]
        elif has_header:
            cols = [_sanitize_identifier(h.strip().strip('"') or f"col_{i}") for i, h in enumerate(first.split(delimiter))]
        else:
            n = len(first.split(delimiter))
            cols = [f"col_{i}" for i in range(n)]
        if not cols:
            raise ValueError("无法推断列")
        col_list = ", ".join(f"`{c}` {_COL_TYPE}" for c in cols)
        create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"

    load_sql = (
        f"LOAD DATA LOCAL INFILE '{path_escaped}' "
        f"INTO TABLE `{table_name}` "
        f"CHARACTER SET utf8mb4 "
        f"FIELDS TERMINATED BY {delim_sql} ENCLOSED BY '\"' "
        f"LINES TERMINATED BY '\\n' {ignore_lines}"
    )
    return table_name, create_sql, load_sql


def execute_sql_from_files(
    file_paths: List[str],
    table_configs: List[Dict[str, Any]],
    sql: str,
) -> Dict[str, Any]:
    """
    多表：多个 CSV 分别导入多个临时表（同一连接），再执行一条 SQL（可连表）。
    file_paths 与 table_configs 一一对应。每个 config: table_name, ddl?, has_header?, delimiter?, columns?
    """
    if len(file_paths) != len(table_configs):
        return {"status": "error", "error": f"文件数量({len(file_paths)})与表配置数量({len(table_configs)})不一致"}

    upload_dir = os.path.abspath(UPLOAD_DIR)
    steps = []
    for i, (path, cfg) in enumerate(zip(file_paths, table_configs)):
        try:
            tname, create_sql, load_sql = _build_create_and_load_for_file(
                file_path=path,
                upload_dir=upload_dir,
                table_name=cfg.get("table_name") or f"t{i}",
                has_header=cfg.get("has_header", True),
                delimiter=cfg.get("delimiter", ","),
                columns_override=cfg.get("columns"),
                ddl=cfg.get("ddl"),
            )
            steps.append((tname, create_sql, load_sql))
        except Exception as e:
            return {"status": "error", "error": f"表{i}({cfg.get('table_name', '')}): {e}"}

    conn = engine.raw_connection()
    cursor = None
    table_names = [s[0] for s in steps]
    try:
        cursor = conn.cursor()
        for _, create_sql, load_sql in steps:
            cursor.execute(create_sql)
            cursor.execute(load_sql)
        cursor.execute(sql)
        if cursor.description:
            result_columns = [d[0] for d in cursor.description]
            result_rows = cursor.fetchall()
            result_rows = [list(r) for r in result_rows]
            out = {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows,
                    "row_count": len(result_rows),
                },
            }
        else:
            out = {
                "status": "success",
                "type": "sql",
                "result": {"row_count": cursor.rowcount},
            }
        return out
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if cursor:
            for t in table_names:
                try:
                    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
                except Exception:
                    pass
            cursor.close()
        conn.close()

