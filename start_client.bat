@echo off
echo Starting ProjectX Desktop Client...
cd /d "%~dp0client"
if exist "%~dp0venv_312\Scripts\activate.bat" (
    call "%~dp0venv_312\Scripts\activate.bat"
) else if exist "%~dp0.venv314\Scripts\activate.bat" (
    call "%~dp0.venv314\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
python main.py
