@echo off
REM Stop backend + MariaDB (compose down). Run from project root.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-for-client.ps1"
pause
