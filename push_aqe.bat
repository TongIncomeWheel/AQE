@echo off
REM ===================================================================
REM  push_aqe.bat -- commit + push the latest AQE export to GitHub
REM  so the Streamlit Cloud deployment refreshes.
REM
REM  Run this AFTER `run_daily.bat` finishes. It stages only the small,
REM  cloud-facing JSONs; the heavy parquet caches stay local.
REM ===================================================================
cd /d "%~dp0"

python -m scripts.push_to_cloud %*

if errorlevel 1 (
    echo.
    echo Push failed. Run `python -m scripts.push_to_cloud --dry-run` to debug.
    pause
)
