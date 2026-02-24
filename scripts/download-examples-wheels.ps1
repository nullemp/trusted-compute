# Download examples Python wheels for offline install.
# Run from project root (with network). Requires Python with pip.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Req = Join-Path $ProjectRoot "examples\requirements.txt"
$OutDir = Join-Path $ProjectRoot "examples\offline_wheels"

if (-not (Test-Path $Req)) {
    Write-Error "Not found: $Req"
}

# Prefer: python in PATH, then py launcher, then common install paths
$pythonExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
} else {
    $locations = @(
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "$env:ProgramFiles\Python*\python.exe"
    )
    foreach ($pattern in $locations) {
        $found = Get-Item $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $pythonExe = $found.FullName
            break
        }
    }
}

if (-not $pythonExe) {
    Write-Error "Python not found. Install Python from https://www.python.org/downloads/ and ensure 'Add Python to PATH' is checked, or run: <path-to-python.exe> -m pip download -r examples/requirements.txt -d examples/offline_wheels"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
# 若系统设置了不可用的代理，pip 会报 ProxyError；此处临时取消代理，直连 PyPI
$saveProxy = @{}
foreach ($k in @("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")) {
    if (Test-Path "Env:$k") { $saveProxy[$k] = (Get-Item "Env:$k").Value; Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
}
try {
    & $pythonExe -m pip download -r $Req -d $OutDir
} finally {
    foreach ($k in $saveProxy.Keys) { Set-Item "Env:$k" $saveProxy[$k] -ErrorAction SilentlyContinue }
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Wheels saved to: $OutDir"
