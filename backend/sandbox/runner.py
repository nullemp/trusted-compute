"""
Sandbox entry: read JSON from stdin (model_type, model_code, input_params), run, output JSON to stdout.
- model_type=python: run Python script (pandas/numpy).
- model_type=sql: run SQL in sandbox using SQLite in-memory (data in input_params).
"""
import sys
import json
import sqlite3


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


def _insert_data_into_table(cur: sqlite3.Cursor, table_name: str, data, columns_in=None):
    """向已存在的表插入数据（不建表）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ",".join(f'"{c}"' for c in cols)
    cur.executemany(
        f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})',
        [[str(v) if v is not None else "" for v in row] for row in rows],
    )


def _create_table_from_data(cur: sqlite3.Cursor, table_name: str, data, columns_in=None):
    """在当前 SQLite 连接中，用 data 创建一张表并插入数据（全列 TEXT）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ",".join(f'"{c}"' for c in cols)
    cur.executemany(
        f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})',
        [[str(v) if v is not None else "" for v in row] for row in rows],
    )


def run_sql(sql: str, input_params: dict) -> dict:
    """
    在沙箱内用 SQLite 内存库执行 SQL。
    - 若提供 ddl：先执行 DDL 建表，再按 tables 仅插入数据；否则按 data/tables 自动建表+插入。
    - 单表：input_params 包含 data, table_name, columns
    - 多表：input_params 包含 tables=[{table_name, data, columns?}, ...]
    """
    tables = input_params.get("tables")
    data = input_params.get("data")
    ddl = input_params.get("ddl")
    if not ddl and not tables and not data:
        return {"status": "error", "error": "请提供 ddl、data 或 tables"}

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if ddl:
            conn.executescript(ddl.strip())
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
        cur.execute(sql)
        if cur.description:
            result_columns = [d[0] for d in cur.description]
            result_rows = [list(r) for r in cur.fetchall()]
            return {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows,
                    "row_count": len(result_rows),
                },
            }
        return {
            "status": "success",
            "type": "sql",
            "result": {"row_count": cur.rowcount},
        }
    except (sqlite3.Error, ValueError) as e:
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


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
