@echo off
echo ============================================================
echo  Precision Edge Sub-Component Search
echo  Searching ALL engine sub-components for best entry recipe
echo  Min 2000 trades (~7/week), ranked by win rate
echo ============================================================
echo.
python -u -m src.calibration.subcomp_freq_search
echo.
pause
