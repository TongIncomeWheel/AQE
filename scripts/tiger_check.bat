@echo off
echo ============================================================
echo   Tiger credential check - run this BEFORE touching the Space
echo   Tests the key on THIS PC and pulls a live SPY gamma map.
echo   Passes here = the credential is good, and anything still
echo   broken on HuggingFace is a secrets problem, not a key one.
echo   Never prints your private key.
echo   Runtime: ~10-20 seconds
echo ============================================================
echo.
cd /d "%~dp0.."
python -m scripts.tiger_check
echo.
pause
