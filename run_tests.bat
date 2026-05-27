@echo off
REM Run the pytest suite. Useful after first-time setup to confirm the port logic works.

cd /d "%~dp0"
python -m pytest tests -v
pause
