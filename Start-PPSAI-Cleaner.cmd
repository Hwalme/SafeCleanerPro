@echo off
setlocal
cd /d "%~dp0client_app"
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw main.py
    exit /b 0
)
python main.py
if errorlevel 1 pause
