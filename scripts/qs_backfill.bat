@echo off
echo ============================================================
echo   QS Backfill - minimum memory so day one is honest
echo   Replays ~15 recent sessions of recipe_hits + the regime
echo   series. Uses existing parquets, no FMP calls.
echo   Runtime: ~1-3 minutes
echo ============================================================
echo.
python -m scripts.qs_backfill
echo.
pause
