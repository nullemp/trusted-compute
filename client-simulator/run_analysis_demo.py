#!/usr/bin/env python3
"""
模拟客户端调用 POST /api/run-analysis：可选 DDL + 数据文件 + SQL 分析。
需先启动服务（docker-compose 或本机后端），再运行本脚本。
"""
import json
import os
import sys

# Windows: 强制 stdout/stderr 使用 UTF-8，避免控制台无输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("请安装: pip install requests", file=sys.stderr, flush=True)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# 与 data/ 中 orders.csv、users.csv 对应
CONFIG = {
    "tables": [
        {
            "table_name": "orders",
            "ddl": "id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)",
            "has_header": True,
            "delimiter": ",",
        },
        {
            "table_name": "users",
            "ddl": "id INT, name VARCHAR(100)",
            "has_header": True,
            "delimiter": ",",
        },
    ],
    "analysis_type": "sql",
    "sql": "SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name",
}


def main():
    orders_csv = os.path.join(DATA_DIR, "orders.csv")
    users_csv = os.path.join(DATA_DIR, "users.csv")
    schema_sql = os.path.join(DATA_DIR, "schema.sql")

    if not os.path.isfile(orders_csv) or not os.path.isfile(users_csv):
        print(f"请确保 {DATA_DIR} 下存在 orders.csv、users.csv", file=sys.stderr, flush=True)
        sys.exit(1)

    url = f"{BASE.rstrip('/')}/api/run-analysis"
    print("模拟客户端: POST /api/run-analysis", flush=True)
    print(f"  API: {url}", flush=True)
    print("  表: orders, users -> SQL 按用户汇总订单金额\n", flush=True)

    data = {"config": json.dumps(CONFIG, ensure_ascii=False)}

    with open(orders_csv, "rb") as f1, open(users_csv, "rb") as f2:
        files = [
            ("files", ("orders.csv", f1, "text/csv")),
            ("files", ("users.csv", f2, "text/csv")),
        ]
        if os.path.isfile(schema_sql):
            with open(schema_sql, "rb") as ddl_f:
                files_with_ddl = files + [("ddl_file", ("schema.sql", ddl_f, "text/plain"))]
                print("  使用 data/schema.sql 作为 DDL 文件", flush=True)
                r = requests.post(url, data=data, files=files_with_ddl, timeout=120)
        else:
            print("  未使用 DDL 文件，按 config.tables 建表", flush=True)
            r = requests.post(url, data=data, files=files, timeout=120)
    r.raise_for_status()
    out = r.json()

    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    if out.get("status") == "error":
        print("\n失败:", out.get("error"), file=sys.stderr, flush=True)
        sys.exit(1)
    # 表格形式展示 result，便于直接看到数据处理结果
    result = out.get("result")
    if isinstance(result, dict) and "columns" in result and "data" in result:
        cols = result["columns"]
        rows = result["data"]
        print("\n--- 数据处理结果（表格） ---", flush=True)
        if cols:
            print("  " + " | ".join(str(c) for c in cols), flush=True)
            print("  " + "-" * (sum(len(str(c)) for c in cols) + 3 * (len(cols) - 1)), flush=True)
        for row in rows:
            print("  " + " | ".join(str(v) for v in row), flush=True)
        print(f"  共 {len(rows)} 行。", flush=True)
    print("\n完成。result 为按用户汇总的订单总额。", flush=True)


if __name__ == "__main__":
    main()
