# Download and install Podman, then copy to project runtime/podman for bundled use.
# Run from project root or scripts/. Requires network; installer may prompt UAC.
$ErrorActionPreference = "Stop"
$ProjectRoot = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path } else { (Get-Location).Path }
$RuntimePodman = Join-Path $ProjectRoot "runtime\podman"
$PodmanVersion = "5.7.1"
$MsiName = "podman-installer-windows-amd64.msi"
$MsiUrl = "https://github.com/containers/podman/releases/download/v$PodmanVersion/$MsiName"
$TempDir = Join-Path $env:TEMP "podman-install-$PodmanVersion"

if (-not (Test-Path $ProjectRoot)) { New-Item -ItemType Directory -Path $ProjectRoot -Force | Out-Null }
if (-not (Test-Path $RuntimePodman)) { New-Item -ItemType Directory -Path $RuntimePodman -Force | Out-Null }

# Already have podman.exe in runtime?
if (Test-Path (Join-Path $RuntimePodman "podman.exe")) {
    Write-Host "runtime\podman\podman.exe already exists. Skip download. Remove it to reinstall."
    exit 0
}

Write-Host "Downloading Podman $PodmanVersion..."
if (-not (Test-Path $TempDir)) { New-Item -ItemType Directory -Path $TempDir -Force | Out-Null }
$MsiPath = Join-Path $TempDir $MsiName
try {
    Invoke-WebRequest -Uri $MsiUrl -OutFile $MsiPath -UseBasicParsing
} catch {
    Write-Warning "Download failed. You can manually download $MsiUrl and run the installer, then copy podman.exe to runtime\podman\"
    exit 1
}

Write-Host "Running Podman installer (UAC may prompt)..."
$proc = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i", "`"$MsiPath`"", "/passive" -Wait -PassThru
if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    Write-Warning "Installer exited with code $($proc.ExitCode). You may install manually and then copy podman.exe to runtime\podman\"
    exit 1
}

Write-Host "Locating podman.exe..."
$podmanExe = $null
foreach ($dir in @(
    "${env:ProgramFiles}\Red Hat\Podman",
    "${env:ProgramFiles}\Podman",
    "${env:LOCALAPPDATA}\Programs\Podman",
    "${env:ProgramFiles(x86)}\Red Hat\Podman",
    "${env:ProgramFiles(x86)}\Podman"
)) {
    if (Test-Path (Join-Path $dir "podman.exe")) {
        $podmanExe = Join-Path $dir "podman.exe"
        break
    }
}
if (-not $podmanExe) {
    $cmd = Get-Command podman -ErrorAction SilentlyContinue
    if ($cmd) { $podmanExe = $cmd.Source }
}
if (-not $podmanExe -or -not (Test-Path $podmanExe)) {
    Write-Warning "Podman installed but podman.exe not found in common paths. Add Podman to PATH or copy podman.exe to $RuntimePodman manually."
    exit 1
}

$srcDir = Split-Path $podmanExe -Parent
Write-Host "Copying from $srcDir to $RuntimePodman ..."
Get-ChildItem -Path $srcDir -File | ForEach-Object { Copy-Item $_.FullName -Destination $RuntimePodman -Force }
Write-Host "Done. Runtime is in runtime\podman\. Run .\scripts\start-for-client.cmd to start services."
# Cleanup
Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
