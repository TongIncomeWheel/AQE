@echo off
REM ===================================================================
REM  AEGIS Investment Committee -- web UI (briefs)
REM  Launches NiceGUI on http://localhost:8765
REM ===================================================================
cd /d "%~dp0"

echo.
echo  AEGIS Investment Committee -- briefs server
echo  ==========================================
echo.
echo  Pre-Market   http://localhost:8765/brief/premarket
echo  Market Open  http://localhost:8765/brief/open
echo  Market Close http://localhost:8765/brief/close
echo.
echo  Close this window to stop the server.
echo.

python -m src.aic.web.app

echo.
echo  Server stopped.
pause
