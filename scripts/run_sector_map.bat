@echo off
echo ============================================
echo   BUILD SECTOR MAP (one-time, uses FMP)
echo ============================================
echo.
cd /d "%~dp0"
python -m src.data.sector_mapper
echo.
pause
