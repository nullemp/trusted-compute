@echo off
REM Start backend via Podman or Docker
REM Uses PowerShell with Bypass to avoid execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-for-client.ps1"
pause
