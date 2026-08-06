@echo off
echo ============================================================
echo Congress Trade Tracker - Full Setup & Run
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

echo [1/4] Installing dependencies...
pip install sqlalchemy pdfplumber anthropic yfinance requests pandas numpy plotly python-dotenv apscheduler pydantic httpx beautifulsoup4 lxml tenacity tqdm streamlit

echo.
echo [2/4] Seeding database with sample data...
python scripts\seed_database.py

echo.
echo [3/4] Starting dashboard...
echo Dashboard will open at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard
echo.

streamlit run dashboard\app.py

pause
