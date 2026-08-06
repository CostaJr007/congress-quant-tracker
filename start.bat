@echo off
title CongressInvests
cd /d "%~dp0"

echo.
echo  ========================================
echo   CongressInvests Tracker
echo  ========================================
echo.

start "CongressInvests API" cmd /k "cd /d "%~dp0" && uv run python server\api_server.py"
timeout /t 2 /nobreak >nul
start "CongressInvests Web" cmd /k "cd /d "%~dp0web_fused" && npm run dev"

echo  API:  http://localhost:8000
echo  App:  http://localhost:3000
echo.
echo  Opened two terminals. Close them to stop.
echo.
pause
