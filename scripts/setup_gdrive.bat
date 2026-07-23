@echo off
REM ===================================================================
REM  setup_gdrive.bat -- Google Drive OAuth setup / token RE-MINT
REM
REM  Double-click this whenever Drive export fails with
REM    "invalid_grant: Token has been expired or revoked".
REM  It opens your browser, you click Allow, and it writes a fresh
REM  refresh token straight into your local .env (fixes the local run)
REM  and prints the values to paste into the HF Space + GitHub secrets.
REM
REM  Prereq: client_secret.json downloaded from GCP and saved at the
REM  project root. See scripts/setup_gdrive_oauth.py for the GCP steps,
REM  including setting the OAuth consent screen to "In production" so the
REM  token does not expire after 7 days.
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
