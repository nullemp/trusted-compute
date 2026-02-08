#!/usr/bin/env python3
"""
多表 demo：用 demo_orders.csv + demo_users.csv 调用 /api/execute-sql/files，
连表按用户汇总订单金额。需先启动服务：docker-compose up -d
"""
import json
import os
import sys

try:
    import requests
except ImportError:
    print("请安装: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(SCRIPT_DIR, "demo_multi_table_config.json")
ORDERS_CSV = os.path.join(SCRIPT_DIR, "demo_orders.csv")
USERS_CSV = os.path.join(SCRIPT_DIR, "demo_users.csv")


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    print("多表 demo：orders + users 连表，按用户汇总订单金额")
    print(f"API: {BASE}\n")

    with open(ORDERS_CSV, "rb") as f1, open(USERS_CSV, "rb") as f2:
        r = requests.post(
            f"{BASE.rstrip('/')}/api/execute-sql/files",
            data={"config": json.dumps(config, ensure_ascii=False)},
            files=[
                ("files", ("demo_orders.csv", f1, "text/csv")),
                ("files", ("demo_users.csv", f2, "text/csv")),
            ],
            timeout=60,
        )
    r.raise_for_status()
    out = r.json()

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("status") == "error":
        sys.exit(1)
    print("\n完成。result.data 为每人订单总额。")


if __name__ == "__main__":
    main()
