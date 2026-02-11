# Build backend + sandbox images and export to runtime/images for offline deployment.
# Run from project root (online). Uses Podman or Docker; offline side uses Podman only. Network required for first build.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ImagesDir = Join-Path $ProjectRoot "runtime\images"
$BackendTar = Join-Path $ImagesDir "trusted-compute-backend.tar"
$SandboxTar = Join-Path $ImagesDir "trusted-compute-sandbox.tar"

# Prefer bundled runtime then PATH
$RuntimeRoot = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
$BundledPodman = Join-Path $RuntimeRoot "podman\podman.exe"
$BundledDocker = Join-Path $RuntimeRoot "docker\docker.exe"
$runtime = $null
if (Test-Path $BundledPodman) {
    $env:PATH = "$(Split-Path $BundledPodman -Parent);$env:PATH"
    $runtime = "podman"
    $env:CONTAINER_RUNTIME = "podman"
} elseif (Test-Path $BundledDocker) {
    $env:PATH = "$(Split-Path $BundledDocker -Parent);$env:PATH"
    $runtime = "docker"
} elseif (Get-Command podman -ErrorAction SilentlyContinue) {
    $runtime = "podman"
    $env:CONTAINER_RUNTIME = "podman"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $runtime = "docker"
}
if (-not $runtime) {
    Write-Error "No podman or docker found. Install one or place under runtime\podman or runtime\docker."
    exit 1
}

if (-not $env:PYTHON_IMAGE) { $env:PYTHON_IMAGE = "docker.m.daocloud.io/library/python:3.11-slim" }
$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

Write-Host "Building images with $runtime (this requires network)..." -ForegroundColor Cyan
if ($runtime -eq "podman") {
    cmd /c "podman compose version 2>nul"
    if ($LASTEXITCODE -eq 0) { cmd /c "podman compose build" }
    else { cmd /c "podman-compose build" }
} else {
    cmd /c "docker compose version 2>nul"
    if ($LASTEXITCODE -eq 0) { cmd /c "docker compose build" }
    else { cmd /c "docker-compose build" }
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

New-Item -ItemType Directory -Force -Path $ImagesDir | Out-Null
Write-Host "Saving images to $ImagesDir ..." -ForegroundColor Cyan
& $runtime save -o $BackendTar trusted-compute-backend
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to save trusted-compute-backend"; exit 1 }
& $runtime save -o $SandboxTar trusted-compute-sandbox
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to save trusted-compute-sandbox"; exit 1 }
Write-Host "Done. Copy the project (including runtime\images\*.tar) to the offline environment and run the usual start script." -ForegroundColor Green
