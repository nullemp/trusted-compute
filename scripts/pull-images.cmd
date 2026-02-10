@echo off
REM Pre-pull images from domestic mirror (DaoCloud). Run from project root.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pull-images.ps1"
pause
