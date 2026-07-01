@echo off
echo ============================================================
echo   AQE Signal Ledger — Historical Backfill
echo   Uses existing panel_daily.parquet (no FMP calls)
echo   Runtime: ~15-30 minutes
echo ============================================================
echo.
python -m scripts.backfill_ledger
