@echo off
chcp 65001 >nul
REM Run client-simulator tests (wait for API, run_analysis_demo, execute_sql_files_demo). Run after start-for-client.cmd.
cd /d "%~dp0..\client-simulator"
pip install -r requirements.txt -q 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & '%~dp0..\client-simulator\run_tests.ps1'"
pause
