@echo off
REM One-time setup. Installs Python dependencies into the user's Python.
REM Run this once (double-click) before run_app.bat.

cd /d "%~dp0"

where python >nul 2>nul
if not %errorlevel%==0 (
    echo Python was not found on PATH. Install Python 3.11+ from python.org and re-run setup.bat.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Setup complete. You can now double-click run_app.bat.
pause
