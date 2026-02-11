#!/usr/bin/env bash
# Run from client-simulator: wait for API then run run_analysis_demo, execute_sql_files_demo
set -e
cd "$(dirname "$0")"
echo "=== Waiting for API ==="
python wait_for_api.py
echo ""
echo "=== 1/2 POST /api/run-analysis ==="
python run_analysis_demo.py
echo ""
echo "=== 2/2 POST /api/execute-sql/files ==="
python execute_sql_files_demo.py
echo ""
echo "=== All done ==="
