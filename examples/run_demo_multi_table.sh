#!/bin/bash
# Multi-table demo with DDL: start service (e.g. ./scripts/start-for-client.sh), then run this script.
# Uploads config + ddl_file (demo_schema.sql) + CSV files; backend builds tables from DDL and runs join SQL.

set -e
BASE="${TRUSTED_COMPUTE_API:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/demo_multi_table_config.json"
DDL_FILE="$SCRIPT_DIR/demo_schema.sql"
ORDERS_CSV="$SCRIPT_DIR/demo_orders.csv"
USERS_CSV="$SCRIPT_DIR/demo_users.csv"

if [[ ! -f "$CONFIG" ]] || [[ ! -f "$ORDERS_CSV" ]] || [[ ! -f "$USERS_CSV" ]]; then
  echo "Missing config or CSV files in $SCRIPT_DIR" >&2
  exit 1
fi
if [[ ! -f "$DDL_FILE" ]]; then
  echo "Missing DDL file: $DDL_FILE" >&2
  exit 1
fi

echo "Multi-table demo (with DDL): orders + users, join and aggregate order total per user"
echo "API: $BASE"
echo "  config: $CONFIG"
echo "  ddl_file: $DDL_FILE"
echo "  files: demo_orders.csv, demo_users.csv"
echo ""

curl -s -X POST "$BASE/api/execute-sql/files" \
  -F "config=$(cat "$CONFIG")" \
  -F "ddl_file=@$DDL_FILE" \
  -F "files=@$ORDERS_CSV" \
  -F "files=@$USERS_CSV" | python3 -m json.tool

echo ""
echo "Done. status: success and result.data mean tables were created from DDL and SQL ran OK."
