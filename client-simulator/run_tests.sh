#!/usr/bin/env bash
# 在 client-simulator 目录下执行：等待 API 后依次跑 run_analysis_demo、execute_sql_files_demo
set -e
cd "$(dirname "$0")"
echo "=== 等待 API 就绪 ==="
python wait_for_api.py
echo ""
echo "=== 1/2 POST /api/run-analysis ==="
python run_analysis_demo.py
echo ""
echo "=== 2/2 POST /api/execute-sql/files ==="
python execute_sql_files_demo.py
echo ""
echo "=== 全部完成 ==="
