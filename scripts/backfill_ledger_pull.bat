@echo off
echo ============================================================
echo   AQE Signal Ledger — Historical Backfill (with FMP pull)
echo   Refreshes bars from FMP first, then scores + ledger
echo   Runtime: ~30-60 minutes
echo ============================================================
echo.
python -m scripts.backfill_ledger --pull
