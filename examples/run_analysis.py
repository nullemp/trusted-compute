#!/usr/bin/env python3
"""
脚本方式调用：只传「数据 + SQL」，插入表后执行 SQL 并返回结果。
无需创建项目、任务。默认请求 http://localhost:8000。
"""
import os
import sys
import json
import argparse

try:
    import requests
except ImportError:
    print("请安装: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")


def execute_sql(base: str, data: list, sql: str, table_name: str = "input_data", columns: list = None) -> dict:
    """POST /api/execute-sql：数据插入内存表后执行 SQL。"""
    body = {"data": data, "sql": sql, "table_name": table_name}
    if columns is not None:
        body["columns"] = columns
    r = requests.post(f"{base}/api/execute-sql", json=body, timeout=90)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="提交数据 + SQL，执行并返回结果")
    parser.add_argument("--base", default=BASE_URL, help="API 根地址")
    parser.add_argument("--sql", default=None, help="SQL 语句（不指定则用示例）")
    parser.add_argument("--data-json", default=None, help="JSON 文件路径，内容为 data 数组（每行 list 或 dict）")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    # 示例数据：可改为从文件或数据库读取
    if args.data_json:
        with open(args.data_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = [
            {"id": 1, "value": 100, "category": "A"},
            {"id": 2, "value": 200, "category": "B"},
            {"id": 3, "value": 150, "category": "A"},
            {"id": 4, "value": 300, "category": "C"},
        ]

    sql = args.sql or "SELECT * FROM input_data WHERE value > 100 ORDER BY value"
    out = execute_sql(base, data, sql)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
