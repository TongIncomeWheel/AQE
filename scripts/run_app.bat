@echo off
REM Aegis Quant Engine launcher.
REM Double-click to open. No terminal window.

cd /d "%~dp0"

REM Pick the Python launcher. Prefer pythonw (no console window).
where pythonw >nul 2>nul
if %errorlevel%==0 (
    set "PYEXE=pythonw"
) else (
    set "PYEXE=python"
)

start /b "" %PYEXE% -m streamlit run src\ui\1_Scanner.py --server.headless true --browser.gatherUsageStats false
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"
exit
