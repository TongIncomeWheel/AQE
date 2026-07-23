@echo off
echo ============================================================
echo  Precision Edge Validation
echo  Walk-Forward + Independent Statistical Tests
echo  Testing sub-component recipe across time windows
echo ============================================================
echo.
python -u -m src.calibration.run_pe_validation
echo.
pause
