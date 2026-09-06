"""Standalone scheduler process for the HF Space container (2026-09-06 fix).

Root cause this replaces: keepalive/daily_job/alert_job used to be started
from `require_login()` (`src/ui/shared.py`), which only runs when Streamlit
executes an actual page script for a real browser session -- confirmed
empirically: a plain HTTP GET (exactly what a keepalive/uptime monitor sends)
gets a 200 from Streamlit's Tornado server without ever running a single line
of the app's Python code. Streamlit only executes the script when a browser's
JS opens the live WebSocket session, which no HTTP-only health check does.

That was invisible for a long time because once ANY real visit started the
threads, they kept running (a daemon thread survives across reruns/sessions
in the same process) for as long as that container process lived. But this
Space is being redeployed many times a day (each push to `main` rebuilds it),
and every rebuild wipes that state -- the scheduler only re-arms itself if a
human happens to open the app again before the next run is due. On several
recent days nobody did, and the 08:30 SGT run silently never fired at all
until the separate GitHub Actions backstop caught it hours later.

This script runs as its OWN OS process, launched directly by the container's
entrypoint (see Dockerfile) -- independent of Streamlit, independent of any
browser ever connecting. It owns keepalive/daily_job/alert_job exclusively now;
`require_login()` no longer starts them, so there is exactly one scheduler per
container, not a race between this process and a page-visit-triggered one.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.keepalive import start_keepalive
from src.ui.daily_job import start_daily_job
from src.ui.alert_job import start_alert_job


def main() -> None:
    # Each start_*() is itself a no-op off HF (SPACE_HOST unset) or already
    # started (per-process _started guard) -- safe to call unconditionally.
    start_keepalive()
    start_daily_job()
    start_alert_job()
    print("[scheduler_daemon] keepalive + daily_job + alert_job started, "
          "running as an independent process", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
