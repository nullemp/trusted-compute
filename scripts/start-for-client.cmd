@echo off
REM Start backend + MariaDB via Podman or Docker (no frontend)
REM Uses PowerShell with Bypass to avoid execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-for-client.ps1"
pause
