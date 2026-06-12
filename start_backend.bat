@echo off
echo Starting ProjectX Backend...
cd /d "%~dp0backend"
if exist "%~dp0venv_312\Scripts\activate.bat" (
    call "%~dp0venv_312\Scripts\activate.bat"
) else if exist "%~dp0.venv314\Scripts\activate.bat" (
    call "%~dp0.venv314\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
