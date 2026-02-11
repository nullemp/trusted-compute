@echo off
REM Stop backend (compose down). Run from project root.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-for-client.ps1"
pause
