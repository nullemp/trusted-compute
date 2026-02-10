#!/usr/bin/env python3
"""
Simulate client POST /api/run-analysis: optional DDL + data files + SQL analysis.
Start service (docker-compose or local backend) first, then run this script.
"""
import json
import os
import sys

# Windows: force UTF-8 for stdout/stderr
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("Install: pip install requests", file=sys.stderr, flush=True)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Matches orders.csv, users.csv in data/
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
        print(f"Ensure {DATA_DIR} contains orders.csv and users.csv", file=sys.stderr, flush=True)
        sys.exit(1)

    url = f"{BASE.rstrip('/')}/api/run-analysis"
    print("Client sim: POST /api/run-analysis", flush=True)
    print(f"  API: {url}", flush=True)
    print("  Tables: orders, users -> SQL aggregate order amount by user\n", flush=True)

    data = {"config": json.dumps(CONFIG, ensure_ascii=False)}

    with open(orders_csv, "rb") as f1, open(users_csv, "rb") as f2:
        files = [
            ("files", ("orders.csv", f1, "text/csv")),
            ("files", ("users.csv", f2, "text/csv")),
        ]
        if os.path.isfile(schema_sql):
            with open(schema_sql, "rb") as ddl_f:
                files_with_ddl = files + [("ddl_file", ("schema.sql", ddl_f, "text/plain"))]
                print("  Using data/schema.sql as DDL file", flush=True)
                r = requests.post(url, data=data, files=files_with_ddl, timeout=120)
        else:
            print("  No DDL file; creating tables from config.tables", flush=True)
            r = requests.post(url, data=data, files=files, timeout=120)
    r.raise_for_status()
    out = r.json()

    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    if out.get("status") == "error":
        print("\nFailed:", out.get("error"), file=sys.stderr, flush=True)
        sys.exit(1)
    result = out.get("result")
    if isinstance(result, dict) and "columns" in result and "data" in result:
        cols = result["columns"]
        rows = result["data"]
        print("\n--- Result (table) ---", flush=True)
        if cols:
            print("  " + " | ".join(str(c) for c in cols), flush=True)
            print("  " + "-" * (sum(len(str(c)) for c in cols) + 3 * (len(cols) - 1)), flush=True)
        for row in rows:
            print("  " + " | ".join(str(v) for v in row), flush=True)
        print(f"  Total {len(rows)} rows.", flush=True)
    print("\nDone. Result is order total per user.", flush=True)


if __name__ == "__main__":
    main()
