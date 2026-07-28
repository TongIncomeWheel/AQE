@echo off
echo ============================================
echo   WALK-FORWARD ANALYSIS (Rolling Mode)
echo ============================================
echo.
cd /d "%~dp0"
python -m src.research.calibration.run_walkforward
echo.
pause
