#!/usr/bin/env python3
"""
SQL 示例：支持两种数据源
1) 企业示例（推荐）：enterprise_data.json（5 张表，每表 100+ 行）+ enterprise_ddl.sql + enterprise_queries.sql
2) 简易示例：dbprofile.sql + orders.csv / users.csv + query.sql

先启动服务（Windows: scripts\\start-for-client.ps1），再运行：
  python examples/run_sql_examples.py
  TRUSTED_COMPUTE_API=http://localhost:8000 python examples/run_sql_examples.py
"""
import csv
import json
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
    """读取 .sql 文件，按分号拆成多条 SQL（去掉空语句）。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return [s.strip() for s in text.split(";") if s.strip()]


def load_enterprise_or_legacy():
    """优先使用企业单文件 dump；否则 JSON+DDL；否则 dbprofile+CSV。返回 (ddl, tables_payload, sql_list, title, use_dump_path)。"""
    enterprise_dump = os.path.join(DATA_DIR, "enterprise_dump.sql")
    enterprise_queries = os.path.join(DATA_DIR, "enterprise_queries.sql")
    if os.path.isfile(enterprise_dump) and os.path.isfile(enterprise_queries):
        with open(enterprise_dump, "r", encoding="utf-8") as f:
            dump_content = f.read()
        sql_list = read_query_statements(enterprise_queries)
        return None, None, sql_list, "企业示例（enterprise_dump.sql + enterprise_queries.sql）", dump_content

    enterprise_json = os.path.join(DATA_DIR, "enterprise_data.json")
    enterprise_ddl = os.path.join(DATA_DIR, "enterprise_ddl.sql")
    if os.path.isfile(enterprise_json) and os.path.isfile(enterprise_ddl) and os.path.isfile(enterprise_queries):
        with open(enterprise_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
        tables_payload = payload.get("tables", [])
        with open(enterprise_ddl, "r", encoding="utf-8") as f:
            ddl = f.read()
        sql_list = read_query_statements(enterprise_queries)
        return ddl, tables_payload, sql_list, "企业示例（enterprise_data.json + enterprise_ddl + enterprise_queries）", None

    dbprofile_path = os.path.join(DATA_DIR, "dbprofile.sql")
    query_path = os.path.join(DATA_DIR, "query.sql")
    orders_csv = os.path.join(DATA_DIR, "orders.csv")
    users_csv = os.path.join(DATA_DIR, "users.csv")
    if not os.path.isfile(dbprofile_path) or not os.path.isfile(query_path):
        print(f"请确保 {DATA_DIR} 下有 enterprise_data.json + enterprise_ddl.sql + enterprise_queries.sql，或 dbprofile.sql + query.sql", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(orders_csv) or not os.path.isfile(users_csv):
        print(f"简易示例需要 {DATA_DIR} 下有 orders.csv 和 users.csv", file=sys.stderr)
        sys.exit(1)
    with open(dbprofile_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    tables_payload = [
        {"table_name": "users", "data": read_csv_as_dicts(users_csv)},
        {"table_name": "orders", "data": read_csv_as_dicts(orders_csv)},
    ]
    sql_list = read_query_statements(query_path)
    return ddl, tables_payload, sql_list, "dbprofile + CSV + query.sql", None


def main():
    print("API 地址:", BASE)
    try:
        health = requests.get(f"{BASE}/", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print("服务未就绪，请先启动（Windows: scripts\\start-for-client.ps1）:", e, file=sys.stderr)
        sys.exit(1)

    ddl, tables_payload, sql_list, title, dump_content = load_enterprise_or_legacy()
    if not sql_list:
        print("未找到有效 SQL 语句", file=sys.stderr)
        sys.exit(1)

    print("创建沙箱（独立 MariaDB 容器+数据卷）...")
    r = requests.post(f"{BASE}/api/sandboxes", timeout=30)
    r.raise_for_status()
    sandbox_id = r.json()["sandbox_id"]
    print("沙箱 ID:", sandbox_id)

    url = f"{BASE}/api/execute-sql"
    print(f"\n========== {title}（POST /api/execute-sql） ==========\n")
    try:
        for idx, sql in enumerate(sql_list, start=1):
            print(f"--- SQL {idx} ---")
            if dump_content is not None:
                body = {"sandbox_id": sandbox_id, "sql": dump_content.rstrip() + "\n" + sql}
            else:
                body = {"sandbox_id": sandbox_id, "sql": sql, "ddl": ddl, "tables": tables_payload}
            r = requests.post(url, json=body, timeout=180)
            r.raise_for_status()
            out = r.json()
            if out.get("status") == "error":
                print("错误:", out.get("error"))
                continue
            result = out.get("result", {})
            print("结果列:", result.get("columns"))
            for row in result.get("data", []):
                print(" ", row)
            print("行数:", result.get("row_count"))
            if out.get("execution_time_ms") is not None:
                print("耗时(ms):", out["execution_time_ms"])
            print()
    finally:
        print("销毁沙箱（删除 DB 容器与数据卷）...")
        requests.delete(f"{BASE}/api/sandboxes/{sandbox_id}", timeout=60)
    print("========== 结束 ==========\n")


if __name__ == "__main__":
    main()
