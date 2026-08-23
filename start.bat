@echo off
title CongressQuant CI://TERMINAL
cd /d "%~dp0"

echo.
echo  ========================================
echo   CongressQuant CI://TERMINAL
echo  ========================================
echo.

where uv >nul 2>&1
if errorlevel 1 (
    start "CI://TERMINAL Server" cmd /k "cd /d "%~dp0" && set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1 && set MARKET_DATA_ENABLED=1 && python server\api_server.py"
) else (
    start "CI://TERMINAL Server" cmd /k "cd /d "%~dp0" && set PYTHONIOENCODING=utf-8 && set MARKET_DATA_ENABLED=1 && uv run python server\api_server.py"
)
timeout /t 3 /nobreak >nul
start http://localhost:8000/terminal/

echo  Terminal: http://localhost:8000/terminal/
echo  API Docs: http://localhost:8000/docs
echo.
echo  Server running in background window. Close it to stop.
echo.
pause
