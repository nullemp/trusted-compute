@echo off
REM run test_sql.ps1 with ExecutionPolicy Bypass
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_sql.ps1"
exit /b %ERRORLEVEL%
