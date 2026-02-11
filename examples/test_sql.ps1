# SQL 接口测试（PowerShell）：GET / 与 POST /api/execute-sql
# 用法：在项目根目录执行 .\examples\test_sql.ps1
# 或先设置： $env:TRUSTED_COMPUTE_API = "http://localhost:8000"

$Base = if ($env:TRUSTED_COMPUTE_API) { $env:TRUSTED_COMPUTE_API.TrimEnd("/") } else { "http://localhost:8000" }
$ErrorActionPreference = "Stop"

Write-Host "API: $Base"
Write-Host ""

# GET /
try {
    $root = Invoke-RestMethod -Uri $Base -Method Get -TimeoutSec 5
    Write-Host "GET / -> $($root | ConvertTo-Json -Compress)"
} catch {
    Write-Host "Service not ready. Error: $_" -ForegroundColor Red
    exit 2
}

Write-Host ""
Write-Host "--- SQL API test ---"
Write-Host ""

# POST /api/execute-sql
$body = @{
    data = @(
        @{ id = 1; name = "A"; v = 10 }
        @{ id = 2; name = "B"; v = 20 }
    )
    sql = "SELECT name, v FROM input_data WHERE v >= 15"
    table_name = "input_data"
} | ConvertTo-Json -Depth 10

try {
    $resp = Invoke-RestMethod -Uri "$Base/api/execute-sql" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
    if ($resp.status -eq "success") {
        $cols = $resp.result.columns -join ", "
        Write-Host "  [OK] POST /api/execute-sql"
        Write-Host "  result.columns: $cols"
        Write-Host "  result.data: $($resp.result.data | ConvertTo-Json -Compress)"
        Write-Host ""
        Write-Host "Result: OK"
        exit 0
    } else {
        Write-Host "  [FAIL] POST /api/execute-sql: $($resp.error)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  [FAIL] POST /api/execute-sql: $_" -ForegroundColor Red
    exit 1
}
