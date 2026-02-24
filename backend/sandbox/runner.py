"""
Sandbox entry: read JSON from stdin (model_type, model_code, input_params), run, output JSON to stdout.
- model_type=python: run Python script (pandas/numpy).
- model_type=sql: run SQL in sandbox using MariaDB (one DB per run; data in input_params).
"""
import os
import sys
import json
import uuid

# SQL 模式使用 PyMySQL 连接 MariaDB
try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None
    DictCursor = None


def _sanitize_identifier(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c == "_") or "col"


def _rows_and_cols(data, columns_in=None):
    """从 data 得到列名和行列表。"""
    if not data:
        raise ValueError("data 为空")
    rows = data
    if isinstance(rows[0], dict):
        cols = columns_in or list(rows[0].keys())
        rows = [[r.get(c) for c in cols] for r in rows]
    else:
        rows = [list(r) for r in rows]
        cols = columns_in or [f"col_{i}" for i in range(len(rows[0]))]
    cols = [_sanitize_identifier(c) for c in cols]
    if not cols:
        raise ValueError("列名为空")
    return cols, rows


def _normalize_ddl_for_mariadb(ddl: str) -> str:
    """将 DDL 转为 MariaDB 兼容（INTEGER->INT, REAL->DOUBLE, AUTOINCREMENT->AUTO_INCREMENT）。"""
    s = ddl.strip()
    s = s.replace("INTEGER", "INT")
    s = s.replace("REAL", "DOUBLE")
    s = s.replace("AUTOINCREMENT", "AUTO_INCREMENT")
    return s


def _get_mariadb_connection(db_name: str = None, conn_params: dict = None):
    """连接 MariaDB，可选指定 database。conn_params 优先于环境变量（避免容器 -e 未传入）。"""
    if conn_params:
        host = conn_params.get("host") or os.getenv("MARIADB_HOST", "mariadb")
        port = int(conn_params.get("port") or os.getenv("MARIADB_PORT", "3306"))
        user = conn_params.get("user") or os.getenv("MARIADB_USER", "root")
        password = conn_params.get("password") or os.getenv("MARIADB_PASSWORD", "")
    else:
        host = os.getenv("MARIADB_HOST", "mariadb")
        port = int(os.getenv("MARIADB_PORT", "3306"))
        user = os.getenv("MARIADB_USER", "root")
        password = os.getenv("MARIADB_PASSWORD", "")
    # #region agent log
    try:
        with open("/app/.cursor_debug.log", "a") as _f:
            _f.write(json.dumps({"hypothesisId": "H5", "location": "runner._get_mariadb_connection", "message": "resolved host", "data": {"conn_params_present": conn_params is not None, "host": host}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def _insert_data_into_table(cur, table_name: str, data, columns_in=None):
    """向已存在的表插入数据（不建表）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ",".join(f"`{c}`" for c in cols)
    sql = f'INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})'
    for row in rows:
        # Use None for NULL so INT columns accept it; empty string '' causes (1366) in strict mode
        cur.execute(sql, [str(v) if v is not None else None for v in row])


def _create_table_from_data(cur, table_name: str, data, columns_in=None):
    """用 data 创建一张表并插入数据（列类型 VARCHAR(2000)）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    col_defs = ", ".join(f"`{c}` VARCHAR(2000)" for c in cols)
    cur.execute(f"CREATE TABLE `{table_name}` ({col_defs})")
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ",".join(f"`{c}`" for c in cols)
    sql = f'INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})'
    for row in rows:
        cur.execute(sql, [str(v) if v is not None else None for v in row])


def run_sql(sql: str, input_params: dict) -> dict:
    """
    在沙箱内用 MariaDB 执行 SQL：每请求创建独立 database，执行后删除。
    - 若提供 ddl：先执行 DDL 建表，再按 tables 仅插入数据；否则按 data/tables 自动建表+插入。
    - 单表：input_params 包含 data, table_name, columns
    - 多表：input_params 包含 tables=[{table_name, data, columns?}, ...]
    """
    if not pymysql:
        return {"status": "error", "error": "未安装 pymysql，无法连接 MariaDB"}

    tables = input_params.get("tables")
    data = input_params.get("data")
    ddl = input_params.get("ddl")
    conn_params = input_params.get("_mariadb")
    sql_only = not ddl and not tables and not data
    if sql_only and not (sql and sql.strip()):
        return {"status": "error", "error": "请提供 ddl、data、tables 或完整 sql（如 mysqldump 导出的 DDL+INSERT）"}

    db_name = "sandbox_" + uuid.uuid4().hex[:16]
    conn = None
    try:
        conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE `{db_name}`")
        cur.close()
        conn.close()

        conn = _get_mariadb_connection(db_name=db_name, conn_params=conn_params)
        cur = conn.cursor()

        if sql_only:
            # 仅 sql：执行整段（如 mysqldump 文件内容 + 一条 SELECT），返回第一条有结果集的结果
            pass
        elif ddl:
            mariadb_ddl = _normalize_ddl_for_mariadb(ddl)
            for stmt in mariadb_ddl.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            if tables:
                for t in tables:
                    _insert_data_into_table(
                        cur,
                        table_name=t.get("table_name") or "input_data",
                        data=t.get("data") or [],
                        columns_in=t.get("columns"),
                    )
        elif tables:
            for t in tables:
                _create_table_from_data(
                    cur,
                    table_name=t.get("table_name") or "input_data",
                    data=t.get("data") or [],
                    columns_in=t.get("columns"),
                )
        else:
            _create_table_from_data(
                cur,
                table_name=input_params.get("table_name") or "input_data",
                data=data or [],
                columns_in=input_params.get("columns"),
            )

        # 执行 sql 中的语句；若多条则取第一条有结果集的
        statements = [s.strip() for s in sql.strip().split(";") if s.strip()]
        result_columns = None
        result_rows = None
        row_count = 0
        for stmt in statements:
            cur.execute(stmt)
            if cur.description:
                result_columns = [d[0] for d in cur.description]
                rows_raw = cur.fetchall()
                result_rows = [[row[c] for c in result_columns] for row in rows_raw]
                row_count = len(result_rows)
                break
            row_count = cur.rowcount

        cur.close()
        conn.close()
        conn = None

        # 删除本请求的 database
        conn_drop = _get_mariadb_connection(db_name=None, conn_params=conn_params)
        cur_drop = conn_drop.cursor()
        cur_drop.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        cur_drop.close()
        conn_drop.close()

        if result_columns is not None:
            return {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows or [],
                    "row_count": row_count,
                },
            }
        return {
            "status": "success",
            "type": "sql",
            "result": {"row_count": row_count},
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
            _cur = _conn.cursor()
            _cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            _cur.close()
            _conn.close()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}
    finally:
        try:
            _conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
            _cur = _conn.cursor()
            _cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            _cur.close()
            _conn.close()
        except Exception:
            pass


def run_python(model_code: str, input_params: dict) -> dict:
    import pandas as pd
    import numpy as np

    local_names = {"input_params": input_params, "pd": pd, "np": np}
    exec(model_code, local_names)
    result = local_names.get("result")
    if result is None:
        return {"type": "python", "status": "error", "error": "未定义 result 变量"}

    if isinstance(result, pd.DataFrame):
        output = {
            "type": "dataframe",
            "columns": result.columns.tolist(),
            "data": result.values.tolist(),
            "shape": list(result.shape),
        }
    elif isinstance(result, dict):
        output = result
    elif isinstance(result, (list, tuple)):
        output = {"type": "list", "data": list(result)}
    else:
        output = {"type": "scalar", "value": str(result)}

    return {"type": "python", "status": "success", "result": output}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"无效输入 JSON: {e}"}), flush=True)
        sys.exit(1)

    model_type = payload.get("model_type")
    model_code = payload.get("model_code", "")
    input_params = payload.get("input_params") or {}

    try:
        if model_type == "python":
            out = run_python(model_code, input_params)
        elif model_type == "sql":
            out = run_sql(model_code, input_params)
        else:
            out = {"status": "error", "error": f"不支持的 model_type: {model_type}"}
    except Exception as e:
        out = {"status": "error", "error": str(e)}

    print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
