@echo off
echo ============================================
echo   AQE VOICE PACKETS ONLY
echo ============================================
echo.
echo Re-slices the CURRENT daily export into the 11 per-voice packet files
echo and publishes them to aegis/output/packets/.
echo.
echo No FMP pull. No re-scoring. Nothing is recalculated - the packets are
echo a pure re-slice of the export that has already been published. Use this
echo when the daily run succeeded but the packet split did not.
echo.
cd /d "%~dp0.."
python -m src.pipeline.voice_packets
echo.
pause
