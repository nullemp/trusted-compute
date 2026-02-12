@echo off
REM Download examples Python wheels for offline install (uses Bypass to avoid execution policy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download-examples-wheels.ps1"
pause
