@echo off
title CongressInvests — API + UI
cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
set MARKET_DATA_ENABLED=1

where uv >nul 2>&1
if errorlevel 1 (
    start "CI API :8000" cmd /k "cd /d "%~dp0" && set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1 && set MARKET_DATA_ENABLED=1 && python server\api_server.py"
) else (
    start "CI API :8000" cmd /k "cd /d "%~dp0" && uv run python server\api_server.py"
)
timeout /t 3 /nobreak >nul
start "CI UI :3000" cmd /k "cd /d "%~dp0web_fused" && npm run dev"
timeout /t 2 /nobreak >nul
start http://localhost:3000
start http://localhost:8000/terminal/

echo  UI:       http://localhost:3000
echo  Terminal: http://localhost:8000/terminal/
echo  API docs: http://localhost:8000/docs
pause
