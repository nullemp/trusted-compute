# Client integration: run from project root. Start backend + MariaDB with Podman or Docker (no frontend).
# Prefer bundled runtime under project runtime/ then PATH (Podman before Docker).
# On Windows with Podman, ensure WSL and Podman Machine are ready so users do not need to configure them manually.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-WslReady {
    # 1) If "wsl -e echo 0" works, WSL can run commands (distro is usable) -> ready
    $null = cmd /c "wsl -e echo 0 2>nul"
    if ($LASTEXITCODE -eq 0) { return $true }
    # 2) Else check "wsl -l -v": if exit 0 and output has a distro line (not "no installed distribution"), WSL is ready
    $out = cmd /c "wsl -l -v 2>nul"
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($out -match "no installed distribution|没有已安装的分发|No installed") { return $false }
    return $true
}

function Install-WslIfNeeded {
    if (Test-WslReady) {
        Remove-Item (Join-Path $env:TEMP "trusted-compute-wsl-install-started.txt") -Force -ErrorAction SilentlyContinue
        return $true
    }
    Write-Host "WSL is required for Podman on Windows, but this offline package does not install WSL automatically." -ForegroundColor Yellow
    Write-Host "Please enable WSL (with at least one distro, e.g. Ubuntu) when preparing your offline image, then run scripts/start-for-client.cmd again." -ForegroundColor Yellow
    Write-Host "For detailed WSL installation steps, see WSL_SETUP_WINDOWS.md in the project root." -ForegroundColor Yellow
    return $false
}

function Ensure-DockerComposeForPodman {
    $RuntimeRoot = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
    $ComposeDir = Join-Path $RuntimeRoot "docker"
    $ComposeExe = Join-Path $ComposeDir "docker-compose.exe"
    if (Test-Path $ComposeExe) {
        $len = (Get-Item $ComposeExe).Length
        if ($len -gt 1MB) { return $ComposeExe }
    }
    Write-Host ""
    Write-Host "docker-compose.exe was not found in $ComposeDir; this offline package does not download it automatically." -ForegroundColor Yellow
    Write-Host "Download docker-compose-windows-x86_64.exe when online, rename it to docker-compose.exe, and place it in $ComposeDir." -ForegroundColor Yellow
    Write-Host ""
    return $null
}

function Load-LocalImages {
    param(
        [string]$RuntimeTool
    )
    # Completely offline mode: if there are image archives under runtime\images, load them before starting.
    $ImagesDir = Join-Path $ProjectRoot "runtime\images"
    if (-not (Test-Path $ImagesDir)) { return }
    $archives = Get-ChildItem -Path $ImagesDir -Filter *.tar -File -ErrorAction SilentlyContinue
    if (-not $archives -or $archives.Count -eq 0) { return }
    Write-Host "Found local image archives under runtime\images. Loading them into $RuntimeTool..." -ForegroundColor Cyan
    foreach ($img in $archives) {
        Write-Host "Loading $($img.Name) ..." -ForegroundColor Cyan
        & $RuntimeTool load -i $img.FullName
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to load $($img.Name) with $RuntimeTool. You may need to run '$RuntimeTool load -i ""$($img.FullName)""' manually." -ForegroundColor Yellow
        }
    }
}

$RuntimeRoot = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
$BundledPodman = Join-Path $RuntimeRoot "podman\podman.exe"
$BundledDocker = Join-Path $RuntimeRoot "docker\docker.exe"

$runtime = $null
$addToPath = $null

if (Test-Path $BundledPodman) {
    $addToPath = Split-Path $BundledPodman -Parent
    $runtime = "podman"
    $env:CONTAINER_RUNTIME = "podman"
} elseif (Test-Path $BundledDocker) {
    $addToPath = Split-Path $BundledDocker -Parent
    $runtime = "docker"
} elseif (Get-Command podman -ErrorAction SilentlyContinue) {
    $runtime = "podman"
    $env:CONTAINER_RUNTIME = "podman"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $runtime = "docker"
}

if (-not $runtime) {
    Write-Error "No podman or docker found. Either place runtime in project: runtime\podman\podman.exe or runtime\docker\docker.exe, or install one on PATH. See DOCKER_IN_CLIENT.md."
    exit 1
}

if ($addToPath) {
    $env:PATH = "$addToPath;$env:PATH"
}

if ($runtime -eq "podman") {
    # On Windows, Podman runs in a Linux VM (Podman Machine) and requires WSL. Auto-install WSL if missing.
    if ($env:OS -eq "Windows_NT") {
        # Check WSL first so we never run podman before WSL is ready (avoids noisy podman errors)
        if (-not (Test-WslReady)) { $null = Install-WslIfNeeded }
        $list = cmd /c "podman machine list 2>nul"
        if ($list -notmatch "running") {
            Write-Host "Starting Podman Machine (Linux VM for Windows)..."
            cmd /c "podman machine init 2>nul"
            cmd /c "podman machine start 2>nul"
            $maxWait = 60
            $ready = $false
            for ($i = 0; $i -lt $maxWait; $i++) {
                Start-Sleep -Seconds 1
                cmd /c "podman info 2>nul"
                if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            }
            if (-not $ready) {
                Write-Host ""
                Write-Host "Podman Machine did not become ready. Try: podman machine start . Or use Docker Desktop and put docker.exe in runtime\docker\ ." -ForegroundColor Yellow
                exit 1
            }
            Write-Host "Podman Machine is running."
            Start-Sleep -Seconds 5
        }
    }
    $env:DOCKER_HOST = "npipe:////./pipe/docker_engine"
    $env:MARIADB_IMAGE = "docker.m.daocloud.io/library/mariadb:11".Trim()
    $env:PYTHON_IMAGE = "docker.m.daocloud.io/library/python:3.11-slim".Trim()
    $env:DOCKER_BUILDKIT = "0"
    $env:COMPOSE_DOCKER_CLI_BUILD = "0"
    # If fully offline, first try to load any bundled image archives from runtime\images using podman load.
    Load-LocalImages -RuntimeTool "podman"
    Write-Host "If required images are not present locally, they will be fetched from the network. Please wait." -ForegroundColor Cyan
    # Prefer built-in "podman compose", then podman-compose, then docker-compose (works with Podman's Docker API)
    $composeOk = $false
    cmd /c "podman compose version 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "podman compose up -d --build"
        $composeOk = ($LASTEXITCODE -eq 0)
    }
    if (-not $composeOk -and (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
        cmd /c "podman-compose up -d --build"
        $composeOk = ($LASTEXITCODE -eq 0)
    }
    if (-not $composeOk) {
        $composeExePath = Ensure-DockerComposeForPodman
        if ($composeExePath -and (Test-Path $composeExePath) -and ($composeExePath.Length -lt 260)) {
            Write-Host "Using docker-compose (Podman exposes Docker API)."
            for ($retry = 0; $retry -lt 2; $retry++) {
                if ($retry -gt 0) {
                    Write-Host "Retrying compose in 10s (daemon may still be starting)..."
                    Start-Sleep -Seconds 10
                }
                cmd /c "set `"DOCKER_HOST=npipe:////./pipe/docker_engine`" && set `"DOCKER_BUILDKIT=0`" && set `"COMPOSE_DOCKER_CLI_BUILD=0`" && set `"MARIADB_IMAGE=docker.m.daocloud.io/library/mariadb:11`" && set `"PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim`" && cd /d `"$ProjectRoot`" && `"$composeExePath`" up -d --build"
                if ($LASTEXITCODE -eq 0) { $composeOk = $true; break }
            }
        }
    }
    if (-not $composeOk) {
        Write-Host "Compose failed. If you see 'connection refused', start Podman Machine first: podman machine start" -ForegroundColor Yellow
        exit 1
    }
} else {
    # Prefer domestic mirror when pulling (same as Podman path)
    if (-not $env:MARIADB_IMAGE) { $env:MARIADB_IMAGE = "docker.m.daocloud.io/library/mariadb:11" }
    if (-not $env:PYTHON_IMAGE) { $env:PYTHON_IMAGE = "docker.m.daocloud.io/library/python:3.11-slim" }
    # If fully offline, first try to load any bundled image archives from runtime\images using docker load.
    Load-LocalImages -RuntimeTool "docker"
    Write-Host "If required images are not present locally, they will be fetched from the network. Please wait." -ForegroundColor Cyan
    cmd /c "docker compose version 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "docker compose up -d --build"
    } else {
        cmd /c "docker-compose up -d --build"
    }
}

Write-Host "Started with $runtime. Backend API: http://localhost:8000  Docs: http://localhost:8000/docs"
