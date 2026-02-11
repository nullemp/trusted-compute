#!/usr/bin/env bash
# Call POST /api/run-analysis with analysis_type=python to trigger the sandbox container.
# Then check backend logs for: "Sandbox: starting container" and "Sandbox: container finished".

set -e
BASE="${TRUSTED_COMPUTE_API:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSV="$SCRIPT_DIR/demo_orders.csv"

CONFIG=$(cat <<'EOF'
{
  "tables": [
    { "table_name": "orders", "ddl": "id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)", "has_header": true, "delimiter": "," }
  ],
  "analysis_type": "python",
  "sql": "SELECT * FROM orders LIMIT 5",
  "python": "result = {\"status\": \"ok\", \"row_count\": len(input_params.get(\"data\", [])), \"message\": \"Sandbox ran.\"}"
}
EOF
)

echo "Calling POST /api/run-analysis (analysis_type=python) to trigger sandbox..."
echo "API: $BASE"
echo "Watch backend logs for: Sandbox: starting container / Sandbox: container finished"
echo ""

curl -s -X POST "$BASE/api/run-analysis" \
  -F "config=$CONFIG" \
  -F "files=@$CSV" | python3 -m json.tool

echo ""
echo "Done. If you saw status success above, the sandbox container was started for this request."
