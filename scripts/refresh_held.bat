@echo off
echo ============================================
echo   AQE HELD-BOOK-ONLY REFRESH
echo ============================================
echo.
echo Fast, targeted path: refreshes the PTJ journal, prices ONLY the held
echo tickers, recomputes scores, rebuilds the export, publishes to GitHub.
echo Does NOT touch the ~800-name scan universe or FMP quota for names
echo nobody holds. Use this instead of the full daily pipeline when only
echo the held book needs fixing (e.g. after an incident).
echo.
cd /d "%~dp0.."
python -m src.pipeline.refresh_held
echo.
pause
