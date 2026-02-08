#!/usr/bin/env python3
"""
亿行级：上传 CSV 文件 + SQL，由 MariaDB LOAD DATA LOCAL INFILE 入库后执行。
不将文件读入应用内存。用法：python run_analysis_file.py <csv路径> [--sql "SELECT ..."]
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


def execute_sql_file(
    base: str,
    file_path: str,
    sql: str,
    table_name: str = "input_data",
    has_header: bool = True,
    delimiter: str = ",",
    columns: str = None,
    ddl: str = None,
) -> dict:
    """POST /api/execute-sql/file：上传 CSV + SQL。可选 ddl 指定表结构。"""
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "text/csv")}
        data = {
            "sql": sql,
            "table_name": table_name,
            "has_header": "true" if has_header else "false",
            "delimiter": delimiter,
        }
        if columns:
            data["columns"] = columns
        if ddl:
            data["ddl"] = ddl
        r = requests.post(
            f"{base}/api/execute-sql/file",
            files=files,
            data=data,
            timeout=3600,
        )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(
        description="上传 CSV + SQL，支持亿行级（LOAD DATA 入库）",
        epilog="示例: python run_analysis_file.py data.csv --sql 'SELECT * FROM input_data LIMIT 10'",
    )
    parser.add_argument("csv", help="CSV 文件路径")
    parser.add_argument("--base", default=BASE_URL, help="API 根地址")
    parser.add_argument("--sql", default="SELECT * FROM input_data LIMIT 10", help="导入后执行的 SQL")
    parser.add_argument("--table", default="input_data", help="临时表名")
    parser.add_argument("--no-header", action="store_true", help="CSV 无表头")
    parser.add_argument("--delimiter", default=",", help="列分隔符（单字符，或 tab）")
    parser.add_argument("--columns", default=None, help="列名逗号分隔（无表头时可用）")
    parser.add_argument("--ddl", default=None, help="表结构，如: id INT, value DECIMAL(10,2), name VARCHAR(100)；CSV 列顺序须与 DDL 一致")
    args = parser.parse_args()

    if not os.path.isfile(args.csv):
        print(f"文件不存在: {args.csv}", file=sys.stderr)
        sys.exit(1)

    base = args.base.rstrip("/")
    out = execute_sql_file(
        base=base,
        file_path=args.csv,
        sql=args.sql,
        table_name=args.table,
        has_header=not args.no_header,
        delimiter="\t" if args.delimiter.strip().lower() in ("tab", "\\t") else args.delimiter[:1],
        columns=args.columns,
        ddl=args.ddl,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
