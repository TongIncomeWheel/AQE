@echo off
REM ===================================================================
REM  push_both.bat -- push current branch to GitHub + HuggingFace Space
REM
REM  Use this after each round of changes. Order is:
REM    1. origin (GitHub) -- cheap, fast
REM    2. hf (HuggingFace) -- triggers Docker rebuild on the Space
REM
REM  Pass --dry-run to preview, --no-hf to skip HF, --no-origin for GitHub-only.
REM ===================================================================
cd /d "%~dp0"

python -m scripts.push_both %*

if errorlevel 1 (
    echo.
    echo Push had failures. Inspect output above.
    pause
)
