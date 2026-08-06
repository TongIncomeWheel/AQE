@echo off
echo ============================================================
echo   Pattern calibration - what actually happened after each
echo   historical cup and handle. Writes data/patterns/
echo   calibration.json, which the daily export reads.
echo   Uses the existing panel, no FMP calls.
echo   Runtime: a few minutes. Re-run quarterly.
echo ============================================================
echo.
python -m scripts.pattern_calibrate
echo.
pause
