@echo off
echo ============================================================
echo Congress Trade Tracker - Windows Setup
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
where uv >nul 2>&1
if errorlevel 1 (
    pip install -e .
) else (
    uv sync
)

echo.
echo ============================================================
echo Setup complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env and fill API keys if needed
echo 2. uv run python scripts\enrich_all.py
echo 3. uv run python server\api_server.py
echo 4. Optional UI: cd web_fused ^&^& npm install ^&^& npm run dev
echo    Terminal: http://localhost:8000/terminal/
echo.
pause
