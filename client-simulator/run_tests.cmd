@echo off
REM Run from client-simulator: wait for API, then run_sql_examples
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo === Waiting for API ===
python -u wait_for_api.py
if errorlevel 1 exit /b 1
echo.
echo === SQL examples (POST /api/execute-sql) ===
python -u ..\examples\run_sql_examples.py
if errorlevel 1 exit /b 1
echo.
echo === All done ===
