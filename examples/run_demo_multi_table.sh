#!/bin/bash
# Multi-table demo: start service with docker-compose up -d, then run this script
# Uses demo_orders.csv + demo_users.csv, join and aggregate order total per user

set -e
BASE="${TRUSTED_COMPUTE_API:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Multi-table demo: orders + users join, order total per user"
echo "API: $BASE"
echo ""

curl -s -X POST "$BASE/api/execute-sql/files" \
  -F "config=$(cat "$SCRIPT_DIR/demo_multi_table_config.json")" \
  -F "files=@$SCRIPT_DIR/demo_orders.csv" \
  -F "files=@$SCRIPT_DIR/demo_users.csv" | python3 -m json.tool

echo ""
echo "完成。若看到 status: success 和 result.data 即表示多表导入与连表 SQL 执行成功。"
