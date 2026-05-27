@echo off
echo ══════════════════════════════════════════════════════════
echo   AQE Recipe Optimizer — Grid Search
echo   Testing thousands of filter combinations...
echo ══════════════════════════════════════════════════════════
echo.
python -m src.calibration.run_optimizer
echo.
pause
