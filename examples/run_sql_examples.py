#!/usr/bin/env python3
"""
SQL 示例：用 dbprofile.sql 建表、CSV 提供数据、query.sql 提供要执行的 SQL，走 POST /api/execute-sql。
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


def read_query_statements(path: str) -> list:
    """读取 query.sql，按分号拆成多条 SQL（去掉空语句）。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return [s.strip() for s in text.split(";") if s.strip()]


def main():
    print("API 地址:", BASE)
    try:
        health = requests.get(f"{BASE}/", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print("服务未就绪，请先启动（Windows: scripts\\start-for-client.ps1）:", e, file=sys.stderr)
        sys.exit(1)

    dbprofile_path = os.path.join(DATA_DIR, "dbprofile.sql")
    query_path = os.path.join(DATA_DIR, "query.sql")
    orders_csv = os.path.join(DATA_DIR, "orders.csv")
    users_csv = os.path.join(DATA_DIR, "users.csv")
    if not os.path.isfile(dbprofile_path):
        print(f"请确保 {DATA_DIR} 下有 dbprofile.sql", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(query_path):
        print(f"请确保 {DATA_DIR} 下有 query.sql", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(orders_csv) or not os.path.isfile(users_csv):
        print(f"请确保 {DATA_DIR} 下有 orders.csv 和 users.csv", file=sys.stderr)
        sys.exit(1)

    with open(dbprofile_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    orders_data = read_csv_as_dicts(orders_csv)
    users_data = read_csv_as_dicts(users_csv)
    sql_list = read_query_statements(query_path)
    if not sql_list:
        print("query.sql 中无有效 SQL 语句", file=sys.stderr)
        sys.exit(1)

    tables_payload = [
        {"table_name": "users", "data": users_data},
        {"table_name": "orders", "data": orders_data},
    ]
    url = f"{BASE}/api/execute-sql"

    print("\n========== dbprofile.sql 建表 + CSV 数据 + query.sql（POST /api/execute-sql） ==========\n")
    for idx, sql in enumerate(sql_list, start=1):
        print(f"--- SQL {idx} ---")
        r = requests.post(
            url,
            json={"sql": sql, "ddl": ddl, "tables": tables_payload},
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
