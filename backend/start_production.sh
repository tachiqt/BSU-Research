#!/bin/bash
# BSU Research Dashboard - Production Startup Script for Linux
# Uses Gunicorn WSGI server for production deployment

echo "Starting BSU Research Dashboard (Production Mode)..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Check if Gunicorn is installed
if ! python -c "import gunicorn" &> /dev/null; then
    echo "Installing Gunicorn..."
    pip install gunicorn
fi

# Start Gunicorn server
echo ""
echo "========================================"
echo "Starting Production Server..."
echo "Server will be available at:"
echo "  - Local: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

gunicorn --workers 3 --bind 0.0.0.0:5000 --timeout 120 --access-logfile - --error-logfile - app:app
