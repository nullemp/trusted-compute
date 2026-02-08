@echo off
REM Run client-simulator tests: wait for API, run_analysis_demo, execute_sql_files_demo
REM Run Python directly from cmd so output is visible (avoid PowerShell swallowing stdout)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo === Waiting for API ===
python -u wait_for_api.py
if errorlevel 1 exit /b 1
echo.
echo === 1/2 POST /api/run-analysis ===
python -u run_analysis_demo.py
if errorlevel 1 exit /b 1
echo.
echo === 2/2 POST /api/execute-sql/files ===
python -u execute_sql_files_demo.py
if errorlevel 1 exit /b 1
echo.
echo === All done ===
