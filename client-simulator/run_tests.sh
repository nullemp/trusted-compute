#!/usr/bin/env bash
# Run from client-simulator: wait for API, then run_sql_examples
set -e
cd "$(dirname "$0")"
echo "=== Waiting for API ==="
python wait_for_api.py
echo ""
echo "=== SQL examples (POST /api/execute-sql) ==="
python ../examples/run_sql_examples.py
echo ""
echo "=== All done ==="
