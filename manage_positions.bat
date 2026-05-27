@echo off
echo ============================================
echo   AQE Position Tracker
echo ============================================
echo.
echo Commands:
echo   1) Update all positions (daily levels)
echo   2) Add position from today's shortlist
echo   3) Close a position
echo   4) List open positions
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    python -m src.pipeline.position_tracker update
) else if "%choice%"=="2" (
    set /p ticker="Ticker to add: "
    python -m src.pipeline.position_tracker add %ticker%
) else if "%choice%"=="3" (
    set /p ticker="Ticker to close: "
    set /p price="Exit price (or press Enter for last close): "
    if "%price%"=="" (
        python -m src.pipeline.position_tracker close %ticker%
    ) else (
        python -m src.pipeline.position_tracker close %ticker% %price%
    )
) else if "%choice%"=="4" (
    python -m src.pipeline.position_tracker list
) else (
    echo Invalid choice.
)
echo.
pause
