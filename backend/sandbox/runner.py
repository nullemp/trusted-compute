"""
沙箱入口：从 stdin 读取 JSON（model_type, model_code, input_params），
执行后向 stdout 输出 JSON 结果。每次任务对应一次容器运行，结束后容器销毁。
当 input_params 含 data 时：在内存 SQLite 建表、插入数据后执行 SQL 并返回结果。
"""
import sys
import json
import sqlite3


def run_sql(sql_code: str, input_params: dict) -> dict:
    # 模板替换（用于无 data 的简单参数化）
    for key, value in input_params.items():
        if key in ("data", "columns", "table_name"):
            continue
        sql_code = sql_code.replace(f"{{{{{key}}}}}", str(value))

    data = input_params.get("data")
    table_name = input_params.get("table_name", "input_data")

    if not data:
        # 无数据时返回演示用模拟结果（兼容旧用法）
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

    # 有数据：内存 SQLite 建表 -> 插入 -> 执行 SQL
    rows = data
    columns = input_params.get("columns")
    if columns is None and rows and isinstance(rows[0], dict):
        columns = list(rows[0].keys())
        rows = [[r[c] for c in columns] for r in rows]
    if not columns and rows:
        columns = [f"col_{i}" for i in range(len(rows[0]))]

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 安全表名：仅字母数字下划线
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
