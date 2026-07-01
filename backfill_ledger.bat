@echo off
echo ============================================================
echo   AQE Signal Ledger — Historical Backfill
echo   This will rebuild scores and populate ~365 days of signals
echo   Runtime: ~5-10 minutes
echo ============================================================
echo.
python -m scripts.backfill_ledger
echo.
pause
