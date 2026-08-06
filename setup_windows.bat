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
pip install sqlalchemy pdfplumber anthropic yfinance requests pandas numpy plotly python-dotenv apscheduler pydantic httpx beautifulsoup4 lxml tenacity tqdm streamlit

echo.
echo ============================================================
echo Setup complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Edit .env file with your API keys
echo 2. Run: python scripts\daily_update.py --once
echo 3. Run: streamlit run dashboard\app.py
echo.
pause
