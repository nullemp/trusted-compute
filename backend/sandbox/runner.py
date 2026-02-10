"""
Sandbox entry: read JSON from stdin (model_type, model_code, input_params), run, output JSON to stdout.
One container run per task, then container removed. When input_params has data: in-memory SQLite table, insert, run SQL, return result.
"""
import sys
import json
import sqlite3


def run_sql(sql_code: str, input_params: dict) -> dict:
    # Template substitution (for simple param when no data)
    for key, value in input_params.items():
        if key in ("data", "columns", "table_name"):
            continue
        sql_code = sql_code.replace(f"{{{{{key}}}}}", str(value))

    data = input_params.get("data")
    table_name = input_params.get("table_name", "input_data")

    if not data:
        # No data: return demo mock result (backward compat)
        return {
            "type": "sql",
            "sql": sql_code,
            "result": {
                "columns": ["id", "value", "category"],
                "data": [[1, 100, "A"], [2, 200, "B"], [3, 150, "A"], [4, 300, "C"]],
                "row_count": 4,
            },
            "status": "success",
        }

    # With data: in-memory SQLite create table -> insert -> run SQL
    rows = data
    columns = input_params.get("columns")
    if columns is None and rows and isinstance(rows[0], dict):
        columns = list(rows[0].keys())
        rows = [[r[c] for c in columns] for r in rows]
    if not columns and rows:
        columns = [f"col_{i}" for i in range(len(rows[0]))]

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Safe table name: alphanumeric and underscore only
    safe_table = "".join(c for c in table_name if c.isalnum() or c == "_") or "input_data"
    placeholders = ", ".join("?" * len(columns))
    col_def = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f'CREATE TABLE "{safe_table}" ({col_def})')
    conn.executemany(
        f'INSERT INTO "{safe_table}" VALUES ({placeholders})',
        [[str(v) for v in row] for row in rows],
    )
    conn.commit()

    try:
        cur = conn.execute(sql_code)
        result_rows = cur.fetchall()
        if result_rows:
            cols = [d[0] for d in cur.description]
            return {
                "type": "sql",
                "sql": sql_code,
                "result": {
                    "columns": cols,
                    "data": [list(r) for r in result_rows],
                    "row_count": len(result_rows),
                },
                "status": "success",
            }
        return {
            "type": "sql",
            "sql": sql_code,
            "result": {"columns": [], "data": [], "row_count": 0},
            "status": "success",
        }
    except Exception as e:
        return {"type": "sql", "status": "error", "error": str(e), "sql": sql_code}
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
        if model_type == "sql":
            out = run_sql(model_code, input_params)
        elif model_type == "python":
            out = run_python(model_code, input_params)
        else:
            out = {"status": "error", "error": f"不支持的 model_type: {model_type}"}
    except Exception as e:
        out = {"status": "error", "error": str(e)}

    print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
