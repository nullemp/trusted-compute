# Run from client-simulator: wait for API then run run_analysis_demo, execute_sql_files_demo
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 确保 Python 输出 UTF-8，避免 PowerShell 下中文/JSON 不显示
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Waiting for API ==="
python -u wait_for_api.py
Write-Host ""
Write-Host "=== 1/2 POST /api/run-analysis ==="
python -u run_analysis_demo.py
Write-Host ""
Write-Host "=== 2/2 POST /api/execute-sql/files ==="
python -u execute_sql_files_demo.py
Write-Host ""
Write-Host "=== All done ==="
