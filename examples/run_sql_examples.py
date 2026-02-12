#!/usr/bin/env python3
"""
SQL 示例：多数据文件 + 多条 SQL，统一走 POST /api/execute-sql（JSON，沙箱 SQLite）。
先启动服务（Windows: scripts\\start-for-client.ps1；Linux/Mac: make up），再运行：
  python examples/run_sql_examples.py
  TRUSTED_COMPUTE_API=http://localhost:8000 python examples/run_sql_examples.py
"""
import csv
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("请先安装依赖: pip install -r examples/requirements.txt", file=sys.stderr)
    print("若使用项目内离线包: pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000").rstrip("/")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
if not os.path.isdir(DATA_DIR):
    DATA_DIR = SCRIPT_DIR


def read_csv_as_dicts(path: str) -> list:
    """读取 CSV，第一行为表头，返回 list of dict。"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    print("API 地址:", BASE)
    try:
        health = requests.get(f"{BASE}/", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print("服务未就绪，请先启动（Windows: scripts\\start-for-client.ps1）:", e, file=sys.stderr)
        sys.exit(1)

    orders_csv = os.path.join(DATA_DIR, "orders.csv")
    users_csv = os.path.join(DATA_DIR, "users.csv")
    if not os.path.isfile(orders_csv) or not os.path.isfile(users_csv):
        print(f"请确保 {DATA_DIR} 下有 orders.csv 和 users.csv", file=sys.stderr)
        sys.exit(1)

    orders_data = read_csv_as_dicts(orders_csv)
    users_data = read_csv_as_dicts(users_csv)

    url = f"{BASE}/api/execute-sql"
    tables_payload = [
        {"table_name": "orders", "data": orders_data},
        {"table_name": "users", "data": users_data},
    ]
    sql_list = [
        "SELECT u.name, SUM(o.amount) AS total "
        "FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name",
        "SELECT COUNT(*) AS order_count, SUM(amount) AS total_amount FROM orders",
    ]

    print("\n========== 多表 + 多条 SQL（POST /api/execute-sql，沙箱 SQLite） ==========\n")
    for idx, sql in enumerate(sql_list, start=1):
        print(f"--- SQL {idx} ---")
        r = requests.post(
            url,
            json={"sql": sql, "tables": tables_payload},
            timeout=60,
        )
        r.raise_for_status()
        out = r.json()
        if out.get("status") == "error":
            print("错误:", out.get("error"))
            continue
        result = out.get("result", {})
        print("SQL:", sql)
        print("结果列:", result.get("columns"))
        for row in result.get("data", []):
            print(" ", row)
        print("行数:", result.get("row_count"))
        if out.get("execution_time_ms") is not None:
            print("耗时(ms):", out["execution_time_ms"])
        print()
    print("========== 结束 ==========\n")


if __name__ == "__main__":
    main()
