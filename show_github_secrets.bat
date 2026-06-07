@echo off
REM Double-click to print the exact values to paste into GitHub Actions secrets.
REM Reads your local .env / client_secret.json / token caches. Prints only; sends nothing.
cd /d "%~dp0"
python -m scripts.show_github_secrets
echo.
pause
