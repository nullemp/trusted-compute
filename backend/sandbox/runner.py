"""
沙箱入口：从 stdin 读取 JSON（model_type, model_code, input_params），
执行后向 stdout 输出 JSON 结果。每次任务对应一次容器运行，结束后容器销毁。
SQL 任务不加载 pandas/numpy，加快启动。
"""
import sys
import json


def run_sql(sql_code: str, input_params: dict) -> dict:
    for key, value in input_params.items():
        sql_code = sql_code.replace(f"{{{{{key}}}}}", str(value))
    # 演示用模拟结果，实际可接各参与方数据库
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
