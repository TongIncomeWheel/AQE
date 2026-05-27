@echo off
REM Refresh the price panel from FMP. Run this after setup.bat,
REM and any time you want to pull fresh daily bars.

cd /d "%~dp0"
python -m src.data.panel_builder
pause
