@echo off
chcp 65001 >nul
echo Starting History AI Chat Viewer...
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -e . -q
)

echo.
echo Opening http://localhost:6300 in browser...
start http://localhost:6300

echo.
echo Press Ctrl+C to stop the server
echo ====================================
set PYTHONPATH=%~dp0src
python -m uvicorn viewer.main:app --host 127.0.0.1 --port 6300