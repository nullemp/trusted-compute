# Pre-pull container images from domestic mirror (recommended before offline use).
# Also saves them as .tar archives under runtime\images for fully offline environments.
# Run from project root. Uses same runtime detection as start-for-client.ps1.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$RuntimeRoot = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
$BundledPodman = Join-Path $RuntimeRoot "podman\podman.exe"
$BundledDocker = Join-Path $RuntimeRoot "docker\docker.exe"

$runtime = $null
$addToPath = $null
if (Test-Path $BundledPodman) {
    $addToPath = Split-Path $BundledPodman -Parent
    $runtime = "podman"
} elseif (Test-Path $BundledDocker) {
    $addToPath = Split-Path $BundledDocker -Parent
    $runtime = "docker"
} elseif (Get-Command podman -ErrorAction SilentlyContinue) {
    $runtime = "podman"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $runtime = "docker"
}

if (-not $runtime) {
    Write-Error "No podman or docker found. Place runtime in project or install on PATH. See start-for-client.ps1."
    exit 1
}

if ($addToPath) {
    $env:PATH = "$addToPath;$env:PATH"
}

# Default: domestic mirror (faster in China). Set env USE_OFFICIAL_HUB=1 to use Docker Hub (e.g. when using VPN).
if ($env:USE_OFFICIAL_HUB -eq "1") {
    $MARIADB_IMAGE = "mariadb:11"
    $PYTHON_IMAGE = "python:3.11-slim"
    Write-Host "Using Docker Hub (USE_OFFICIAL_HUB=1)." -ForegroundColor Cyan
} else {
    $MARIADB_IMAGE = "docker.m.daocloud.io/library/mariadb:11"
    $PYTHON_IMAGE = "docker.m.daocloud.io/library/python:3.11-slim"
    Write-Host "Using domestic mirror (DaoCloud). Set USE_OFFICIAL_HUB=1 to use Docker Hub." -ForegroundColor Cyan
}

if ($runtime -eq "podman") {
    if ($env:OS -eq "Windows_NT") {
        $env:DOCKER_HOST = "npipe:////./pipe/docker_engine"
    }
    $env:DOCKER_BUILDKIT = "0"
    Write-Host "Pulling both images in parallel (faster)..." -ForegroundColor Cyan
    $j1 = Start-Job -ScriptBlock { param($img) & podman pull $img 2>&1 } -ArgumentList $MARIADB_IMAGE
    $j2 = Start-Job -ScriptBlock { param($img) & podman pull $img 2>&1 } -ArgumentList $PYTHON_IMAGE
    Wait-Job $j1, $j2 | Out-Null
    Receive-Job $j1 | ForEach-Object { Write-Host $_ }
    Receive-Job $j2 | ForEach-Object { Write-Host $_ }
    Remove-Job $j1, $j2 -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "Pulling both images in parallel (faster)..." -ForegroundColor Cyan
    $j1 = Start-Job -ScriptBlock { param($img) & docker pull $img 2>&1 } -ArgumentList $MARIADB_IMAGE
    $j2 = Start-Job -ScriptBlock { param($img) & docker pull $img 2>&1 } -ArgumentList $PYTHON_IMAGE
    Wait-Job $j1, $j2 | Out-Null
    Receive-Job $j1 | ForEach-Object { Write-Host $_ }
    Receive-Job $j2 | ForEach-Object { Write-Host $_ }
    Remove-Job $j1, $j2 -Force -ErrorAction SilentlyContinue
}

# After pulling, save images as .tar archives under runtime\images so they can be loaded later in a fully offline environment.
$ImagesDir = Join-Path $RuntimeRoot "images"
if (-not (Test-Path $ImagesDir)) {
    New-Item -ItemType Directory -Path $ImagesDir | Out-Null
}

Write-Host "Saving images as local archives under runtime\images ..." -ForegroundColor Cyan

$MariadbTar = Join-Path $ImagesDir "mariadb-11.tar"
$PythonTar  = Join-Path $ImagesDir "python-3.11-slim.tar"

if ($runtime -eq "podman") {
    & podman save -o $MariadbTar $MARIADB_IMAGE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to save $MARIADB_IMAGE as $MariadbTar. You may need to run 'podman save -o ""$MariadbTar"" ""$MARIADB_IMAGE""' manually." -ForegroundColor Yellow
    }
    & podman save -o $PythonTar $PYTHON_IMAGE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to save $PYTHON_IMAGE as $PythonTar. You may need to run 'podman save -o ""$PythonTar"" ""$PYTHON_IMAGE""' manually." -ForegroundColor Yellow
    }
} else {
    & docker save -o $MariadbTar $MARIADB_IMAGE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to save $MARIADB_IMAGE as $MariadbTar. You may need to run 'docker save -o ""$MariadbTar"" ""$MARIADB_IMAGE""' manually." -ForegroundColor Yellow
    }
    & docker save -o $PythonTar $PYTHON_IMAGE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to save $PYTHON_IMAGE as $PythonTar. You may need to run 'docker save -o ""$PythonTar"" ""$PYTHON_IMAGE""' manually." -ForegroundColor Yellow
    }
}

Write-Host "Pre-pull and image export done. Archives are under runtime\images. Run scripts\start-for-client.cmd (or .ps1) to start the project." -ForegroundColor Green
