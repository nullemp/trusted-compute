# Stop backend + sandbox (compose down). Run from project root. Uses same runtime as start-for-client.ps1.
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
    Write-Error "No podman or docker found. Use the same runtime as start-for-client (runtime\podman or runtime\docker, or on PATH)."
    exit 1
}

if ($addToPath) {
    $env:PATH = "$addToPath;$env:PATH"
}

function Ensure-DockerComposeForPodman {
    $rt = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
    $exe = Join-Path (Join-Path $rt "docker") "docker-compose.exe"
    if (Test-Path $exe) {
        $len = (Get-Item $exe).Length
        if ($len -gt 1MB) { return $exe }
    }
    return $null
}

$downOk = $false
if ($runtime -eq "podman") {
    if ($env:OS -eq "Windows_NT") { $env:DOCKER_HOST = "npipe:////./pipe/docker_engine" }
    cmd /c "podman compose version 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "podman compose down"
        $downOk = ($LASTEXITCODE -eq 0)
    }
    if (-not $downOk -and (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
        cmd /c "podman-compose down"
        $downOk = ($LASTEXITCODE -eq 0)
    }
    if (-not $downOk) {
        $composeExe = Ensure-DockerComposeForPodman
        if ($composeExe) {
            cmd /c "set `"DOCKER_HOST=npipe:////./pipe/docker_engine`" && cd /d `"$ProjectRoot`" && `"$composeExe`" down"
            $downOk = ($LASTEXITCODE -eq 0)
        }
    }
} else {
    cmd /c "docker compose version 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "docker compose down"
    } else {
        cmd /c "docker-compose down"
    }
    $downOk = $true
}

if ($downOk) {
    Write-Host "Services stopped ($runtime)." -ForegroundColor Green
} else {
    Write-Host "Compose down failed or no compose found. You can stop containers manually, e.g. docker ps then docker stop <id>." -ForegroundColor Yellow
    exit 1
}
