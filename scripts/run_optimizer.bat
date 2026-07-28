@echo off
echo ══════════════════════════════════════════════════════════
echo   AQE Recipe Optimizer — Grid Search
echo   Testing thousands of filter combinations...
echo ══════════════════════════════════════════════════════════
echo.
python -m src.research.calibration.run_optimizer
echo.
pause
