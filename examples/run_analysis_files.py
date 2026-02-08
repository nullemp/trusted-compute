#!/usr/bin/env python3
"""
多表上传 + 连表 SQL：多个 CSV 对应多张临时表，执行一条可 JOIN 的 SQL。
用法：python run_analysis_files.py --config config.json file1.csv file2.csv ...
config.json 格式：{"tables": [{"table_name":"t1","ddl":"id INT,...", "has_header": true}, ...], "sql": "SELECT ... JOIN ..."}
"""
import json
import os
import sys
import argparse

try:
    import requests
except ImportError:
    print("请安装: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")


def main():
    parser = argparse.ArgumentParser(
        description="多表 CSV 上传 + 连表 SQL",
        epilog="示例: python run_analysis_files.py --config config.json orders.csv users.csv",
    )
    parser.add_argument("--config", "-c", required=True, help="JSON 文件路径，含 tables 与 sql")
    parser.add_argument("--base", default=BASE_URL, help="API 根地址")
    parser.add_argument("csv_files", nargs="+", help="CSV 文件，顺序与 config.tables 一致")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)
    tables = config.get("tables")
    sql = config.get("sql")
    if not tables or not sql:
        print("config 需包含 tables 数组和 sql 字符串", file=sys.stderr)
        sys.exit(1)
    if len(args.csv_files) != len(tables):
        print(f"CSV 文件数({len(args.csv_files)})与 tables 数({len(tables)})不一致", file=sys.stderr)
        sys.exit(1)
    for p in args.csv_files:
        if not os.path.isfile(p):
            print(f"文件不存在: {p}", file=sys.stderr)
            sys.exit(1)

    base = args.base.rstrip("/")
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/csv")) for p in args.csv_files]
    try:
        r = requests.post(
            f"{base}/api/execute-sql/files",
            data={"config": json.dumps(config, ensure_ascii=False)},
            files=files,
            timeout=3600,
        )
        r.raise_for_status()
        out = r.json()
    finally:
        for _, (_, fh, _) in files:
            fh.close()

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
