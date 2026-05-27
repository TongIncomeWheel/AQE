@echo off
REM Run all 5 engines + composite over the cached panel and write scores_daily.parquet.
REM Run this after build_panel.bat.

cd /d "%~dp0"
python -m src.scanner.score_runner
pause
