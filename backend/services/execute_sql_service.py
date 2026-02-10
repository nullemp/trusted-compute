"""
Direct SQL execution: insert data into MariaDB temp table, run user SQL, return result.
- execute_sql_mariadb: JSON data then execute (small/medium data)
- execute_sql_from_file: file upload + LOAD DATA LOCAL INFILE (large scale)
"""
import os
from typing import List, Any, Dict, Optional, Union, Tuple

from database import engine

# Temp table column type: TEXT for large cells; large data on MariaDB disk
_COL_TYPE = "TEXT"
_BATCH_SIZE = 5000


def _sanitize_identifier(name: str) -> str:
    """Keep only letters, digits, underscore; for table/column names."""
    return "".join(c for c in name if c.isalnum() or c == "_") or "col"


def _normalize_data(
    data: List[Union[List[Any], Dict[str, Any]]],
    columns: Optional[List[str]] = None,
) -> Tuple[List[str], List[List[Any]]]:
    """Return column names and row data (each row as list)."""
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
    # Normalize to list of list, values str or number
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
    Create temp table in MariaDB, insert data, run sql, return result.
    Temp table dropped when connection closes; supports large data.
    """
    table_name = _sanitize_identifier(table_name) or "input_data"
    cols, rows = _normalize_data(data, columns)
    if not cols:
        return {"status": "error", "error": "Data or columns empty"}

    # Quote column names to avoid reserved words
    col_list = ", ".join(f"`{c}` {_COL_TYPE}" for c in cols)
    create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO `{table_name}` ({','.join('`' + c + '`' for c in cols)}) VALUES ({placeholders})"

    conn = engine.raw_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(create_sql)

        # Batch insert
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = [tuple(str(v) if v is not None else "" for v in row) for row in rows[i : i + _BATCH_SIZE]]
            cursor.executemany(insert_sql, batch)

        # Execute user SQL (single statement)
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


# Uploaded files saved here; LOAD DATA only allows reading under this dir
UPLOAD_DIR = os.environ.get("TRUSTED_COMPUTE_UPLOAD_DIR", "/tmp/trusted_compute_upload")

# DDL allowed types: safe chars only [A-Za-z0-9(),.]
_TYPE_SAFE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789(),. ")


def parse_ddl_file(content: str) -> Dict[str, str]:
    """
    Parse each CREATE TABLE from DB-exported SQL (e.g. schema.sql);
    return { table_name: "column_def_str" }, column def = part inside parens, e.g. "id INT, name VARCHAR(100)".
    """
    out: Dict[str, str] = {}
    lower_content = content.lower()
    pos = 0
    while True:
        idx = lower_content.find("create table", pos)
        if idx < 0:
            break
        # Skip CREATE TABLE [IF NOT EXISTS], get table name (`name` or name)
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
        # Find matching right paren (type may contain VARCHAR(20) etc.)
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
    """Split DDL by comma, ignoring commas inside parens (e.g. DECIMAL(10,2), VARCHAR(20))."""
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
    Parse DDL table body (inside parens), return safe CREATE column def string.
    E.g. "id INT, value DECIMAL(10,2), name VARCHAR(100)" -> "`id` INT, `value` DECIMAL(10,2), `name` VARCHAR(100)".
    """
    if not ddl or not ddl.strip():
        return None
    parts = []
    for part in _split_ddl_by_comma(ddl):
        if not part:
            continue
        # Before first space = column name, rest = type
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
    Import CSV into temp table via MariaDB LOAD DATA LOCAL INFILE, then run SQL.
    File not loaded into app memory; supports very large data.
    file_path: absolute path readable by backend (under UPLOAD_DIR).
    ddl: optional. Table DDL body, e.g. "id INT, value DECIMAL(10,2), name VARCHAR(100)"; CSV column order must match. Else infer from first line as TEXT.
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return {"status": "error", "error": f"File not found: {file_path}"}
    upload_dir = os.path.abspath(UPLOAD_DIR)
    if not file_path.startswith(upload_dir):
        return {"status": "error", "error": "File path not allowed"}

    table_name = _sanitize_identifier(table_name) or "input_data"

    if ddl:
        col_list = _parse_ddl(ddl)
        if not col_list:
            return {"status": "error", "error": "Invalid DDL format, e.g.: id INT, value DECIMAL(10,2), name VARCHAR(100)"}
        create_sql = f"CREATE TEMPORARY TABLE `{table_name}` ({col_list})"
    else:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                first = f.readline()
        except Exception as e:
            return {"status": "error", "error": f"Failed to read file: {e}"}
        first = first.rstrip("\r\n")
        if columns_override:
            cols = [_sanitize_identifier(c) for c in columns_override]
        elif has_header:
            cols = [_sanitize_identifier(h.strip().strip('"') or f"col_{i}") for i, h in enumerate(first.split(delimiter))]
        else:
            n = len(first.split(delimiter))
            cols = [f"col_{i}" for i in range(n)]
        if not cols:
            return {"status": "error", "error": "Cannot infer columns"}
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
    Build CREATE and LOAD SQL for single file. Return (table_name_safe, create_sql, load_sql). No DB connection; path check and SQL only.
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")
    upload_dir_abs = os.path.abspath(upload_dir)
    if not file_path.startswith(upload_dir_abs):
        raise ValueError("File path not allowed")

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
            raise ValueError("Invalid DDL format")
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
            raise ValueError("Cannot infer columns")
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
    Multi-table: import each CSV into a temp table (same connection), then run one SQL (can join).
    file_paths and table_configs 1:1. Each config: table_name, ddl?, has_header?, delimiter?, columns?
    """
    if len(file_paths) != len(table_configs):
        return {"status": "error", "error": f"File count ({len(file_paths)}) does not match table config count ({len(table_configs)})"}

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
            return {"status": "error", "error": f"Table {i} ({cfg.get('table_name', '')}): {e}"}

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

