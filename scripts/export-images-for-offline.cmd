@echo off
REM Build and export images + examples wheels for offline deploy (uses Bypass to avoid execution policy)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0export-images-for-offline.ps1"
pause
