@echo off
REM Start backend via Podman or Docker
REM Uses PowerShell with Bypass to avoid execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-for-client.ps1"
REM 按任意键仅关闭本窗口；要跑示例请另开终端执行: python examples/run_sql_examples.py
pause