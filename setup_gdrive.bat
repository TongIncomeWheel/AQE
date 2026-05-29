@echo off
REM ===================================================================
REM  setup_gdrive.bat -- ONE-TIME Google Drive OAuth setup
REM
REM  Run this once on your Windows PC to capture a refresh token that
REM  lets the HF Space upload export JSON to your Drive automatically.
REM
REM  Prereq: client_secret.json downloaded from GCP and saved at the
REM  project root. See scripts/setup_gdrive_oauth.py for the GCP steps.
REM ===================================================================
cd /d "%~dp0"

echo.
echo  Google Drive OAuth setup for AQE
echo  =================================
echo.

REM Install dependencies if missing (idempotent)
python -m pip install --quiet google-api-python-client google-auth-oauthlib

python -m scripts.setup_gdrive_oauth

if errorlevel 1 (
    echo.
    echo  Setup failed. Read the output above for guidance.
    pause
    exit /b 1
)

echo.
pause
