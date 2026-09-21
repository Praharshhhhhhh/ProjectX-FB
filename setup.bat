@echo off
echo ========================================
echo  ProjectX - Setup
echo ========================================
echo.

echo [1/2] Setting up Python dependencies...
cd /d "%~dp0"
if not exist "venv_312" (
    echo Creating virtual environment...
    python -m venv venv_312
)
call venv_312\Scripts\activate
pip install -r requirements.txt
pip install pydantic-settings
echo Dependencies installed.
echo.

echo [2/2] Creating PostgreSQL database...
psql -U postgres -c "CREATE DATABASE projectx;" 2>nul
echo Done (ignore error if DB already exists).
echo.

echo ========================================
echo  Setup Complete!
echo  Run start_backend.bat to start the server
echo  Run start_client.bat to start the desktop app
echo ========================================
pause
