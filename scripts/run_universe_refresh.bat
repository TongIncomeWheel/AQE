@echo off
echo ============================================
echo   AQE UNIVERSE REFRESH
echo ============================================
echo.
echo Pulling FMP screener: $1B+ mcap, $5+ price, 500K+ volume
echo NYSE + NASDAQ only (excludes warrants, units)
echo.
cd /d "%~dp0"
python -c "from src.data.universe import refresh_universe; r = refresh_universe(); print(f'Added: {len(r[\"added\"])} | Removed: {len(r[\"removed\"])} | Total: {r[\"total\"]}')"
echo.
pause
