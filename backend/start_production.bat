@echo off
REM BSU Research Dashboard - Production Startup Script for Windows
REM Uses Waitress WSGI server for production deployment

echo Starting BSU Research Dashboard (Production Mode)...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install waitress

REM Check if Waitress is installed
python -c "import waitress" >nul 2>&1
if errorlevel 1 (
    echo Installing Waitress...
    pip install waitress
)

REM Start Waitress server
echo.
echo ========================================
echo Starting Production Server...
echo Server will be available at:
echo   - Local: http://localhost:5000
echo   - Network: http://%COMPUTERNAME%:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

waitress-serve --host=0.0.0.0 --port=5000 --threads=4 app:app

pause
