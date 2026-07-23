@echo off
echo ============================================
echo   AQE DAILY PIPELINE
echo ============================================
echo.
cd /d "%~dp0"
python -m src.pipeline.daily_orchestrator --no-pull
echo.
pause
