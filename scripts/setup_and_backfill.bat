@echo off
setlocal enabledelayedexpansion
title AQE Signal Ledger — Setup + Backfill
color 0A

echo ============================================================
echo   AQE Signal Ledger — One-Time Setup + Historical Backfill
echo   This will install dependencies and run the 365-day backfill
echo   Runtime after setup: ~30-60 minutes
echo ============================================================
echo.

:: ── Check Python ───────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo   Download Python 3.11+ from https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% found
echo.

:: ── Install dependencies ───────────────────────────────────────
echo [1/3] Installing Python dependencies...
echo   (pandas, numpy, scipy, scikit-learn, streamlit, etc.)
echo.
pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo   Try running: pip install -r requirements.txt
    echo   to see the full error.
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

:: ── FMP API key ────────────────────────────────────────────────
if exist .env (
    findstr /c:"FMP_API_KEY" .env >nul 2>&1
    if not errorlevel 1 (
        echo [OK] .env already has FMP_API_KEY
        echo.
        goto :run
    )
)

echo [2/3] FMP API key needed for market data pull
echo.
set /p "FMP_KEY=  Paste your FMP API key here: "
if "!FMP_KEY!"=="" (
    echo [ERROR] No key entered. Cannot proceed without FMP API key.
    pause
    exit /b 1
)
echo FMP_API_KEY=!FMP_KEY!> .env
echo [OK] .env created with your FMP key
echo   (this file is gitignored — never committed)
echo.

:: ── Run backfill ───────────────────────────────────────────────
:run
echo [3/3] Starting historical backfill...
echo   This pulls 365 days of OHLCV for ~490 tickers from FMP,
echo   runs all 9 AQE engines, and populates the signal ledger.
echo.
echo   *** You can walk away now — come back in 30-60 minutes ***
echo.
echo ============================================================
echo.

python -m scripts.backfill_ledger --pull
