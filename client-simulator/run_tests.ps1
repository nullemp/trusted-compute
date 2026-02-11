# Run from client-simulator: wait for API, then run_sql_examples
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Waiting for API ==="
python -u wait_for_api.py
Write-Host ""
Write-Host "=== SQL examples (POST /api/execute-sql) ==="
python -u ..\examples\run_sql_examples.py
Write-Host ""
Write-Host "=== All done ==="
