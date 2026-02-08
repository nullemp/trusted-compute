# Client integration: run from project root. Start backend + MariaDB with Podman or Docker (no frontend).
# Prefer bundled runtime under project runtime/ then PATH (Podman before Docker).
# On Windows with Podman, ensures WSL is installed (and Podman Machine) so customer does not need to configure manually.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-WslReady {
    # 1) If "wsl -e echo 0" works, WSL can run commands (distro is usable) -> ready
    $null = cmd /c "wsl -e echo 0 2>nul"
    if ($LASTEXITCODE -eq 0) { return $true }
    # 2) Else check wsl -l -v: exit 0 and has a distro line (not "no installed distribution")
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
    $marker = Join-Path $env:TEMP "trusted-compute-wsl-install-started.txt"
    $forceRetry = ($env:TRUSTED_COMPUTE_WSL_RETRY -eq "1")
    if ($forceRetry) { Remove-Item $marker -Force -ErrorAction SilentlyContinue }
    # If we already ran the installer (marker exists), do not block: continue and let Podman try; if it fails we show one message below.
    if ((Test-Path $marker) -and -not $forceRetry) {
        return $true
    }
    Write-Host "WSL is required for Podman. Installing (UAC may appear; click Yes)..."
    try {
        Start-Process -FilePath "wsl.exe" -ArgumentList "--install", "--no-launch" -Verb RunAs -Wait
    } catch {
        Start-Process -FilePath "wsl.exe" -ArgumentList "--install" -Verb RunAs -Wait
    }
    New-Item -Path $marker -ItemType File -Force | Out-Null
    Write-Host "If the system asked to RESTART, restart the PC then run this script again. Otherwise run again in a moment." -ForegroundColor Cyan
    exit 0
}

function Ensure-DockerComposeForPodman {
    $RuntimeRoot = if ($env:BUNDLED_RUNTIME_ROOT) { $env:BUNDLED_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
    $ComposeDir = Join-Path $RuntimeRoot "docker"
    $ComposeExe = Join-Path $ComposeDir "docker-compose.exe"
    if (Test-Path $ComposeExe) {
        $len = (Get-Item $ComposeExe).Length
        if ($len -gt 1MB) { return $ComposeExe }
    }
    Write-Host "Downloading docker-compose to $ComposeDir ..."
    New-Item -ItemType Directory -Path $ComposeDir -Force | Out-Null
    $version = "v2.24.0"
    $fileName = "docker-compose-windows-x86_64.exe"
    $urls = @(
        "https://github.com/docker/compose/releases/download/$version/$fileName",
        "https://ghproxy.com/https://github.com/docker/compose/releases/download/$version/$fileName",
        "https://mirror.ghproxy.com/https://github.com/docker/compose/releases/download/$version/$fileName",
        "https://github.com/docker/compose/releases/download/v2.23.0/$fileName"
    )
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    foreach ($url in $urls) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $ComposeExe -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 90
            if ((Test-Path $ComposeExe) -and (Get-Item $ComposeExe).Length -gt 1MB) { return $ComposeExe }
        } catch {
            Remove-Item $ComposeExe -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host ""
    Write-Host "Download failed (network/timeout). Save docker-compose manually:" -ForegroundColor Yellow
    Write-Host "  1. Open: https://github.com/docker/compose/releases" -ForegroundColor Gray
    Write-Host "  2. Download: docker-compose-windows-x86_64.exe" -ForegroundColor Gray
    Write-Host "  3. Rename to docker-compose.exe and put in: $ComposeDir" -ForegroundColor Gray
    Write-Host ""
    return $null
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
    cmd /c "docker compose version 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "docker compose up -d --build"
    } else {
        cmd /c "docker-compose up -d --build"
    }
}

Write-Host "Started with $runtime. Backend API: http://localhost:8000  Docs: http://localhost:8000/docs"
