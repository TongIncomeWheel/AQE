#!/bin/sh
# Launches the standalone scheduler (keepalive + daily_job + alert_job) as an
# independent background process, then runs Streamlit in the foreground.
#
# 2026-09-06 fix: these used to start only when a real browser session hit
# require_login() inside the Streamlit app -- which a plain HTTP keepalive
# ping never does (Streamlit only runs the script for a real WebSocket
# session, confirmed empirically). On a Space rebuilt many times a day, that
# left the 08:30 SGT daily run unarmed unless a human happened to open the
# app first. Starting the scheduler here means it runs from the moment the
# container boots, with no dependency on anyone visiting the page.
set -e

python3 -m scripts.scheduler_daemon &

exec streamlit run src/ui/1_Scanner.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
