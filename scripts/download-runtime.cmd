@echo off
REM Download and install Podman, then copy to runtime\podman (no execution policy needed)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download-runtime.ps1"
pause
