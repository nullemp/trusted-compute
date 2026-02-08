#!/bin/bash
# 多表 demo：先启动服务 docker-compose up -d，再执行本脚本
# 使用 demo 数据：demo_orders.csv + demo_users.csv，连表聚合每人订单总额

set -e
BASE="${TRUSTED_COMPUTE_API:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "多表 demo：orders + users 连表，按用户汇总订单金额"
echo "API: $BASE"
echo ""

curl -s -X POST "$BASE/api/execute-sql/files" \
  -F "config=$(cat "$SCRIPT_DIR/demo_multi_table_config.json")" \
  -F "files=@$SCRIPT_DIR/demo_orders.csv" \
  -F "files=@$SCRIPT_DIR/demo_users.csv" | python3 -m json.tool

echo ""
echo "完成。若看到 status: success 和 result.data 即表示多表导入与连表 SQL 执行成功。"
