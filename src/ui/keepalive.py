"""Keep-alive pinger — stops the Hugging Face Space sleeping during the day.

HF Spaces sleep after a period with no traffic, which wipes the ephemeral
filesystem (universe/scores/output). A daemon thread periodically requests the
Space's own public URL; that counts as traffic and resets the idle timer.

Scope + limits:
- Active ONLY on HF (when `SPACE_HOST` is present). No-op locally.
- Keeps a *running* container awake. It cannot resurrect one that has already
  slept — for guaranteed wake-ups (e.g. the 9am run) use an EXTERNAL uptime
  monitor (cron-job.org / UptimeRobot) hitting the Space URL.
- Interval via `KEEPALIVE_MINUTES` env (default 90). Floor of 1 minute.
"""

from __future__ import annotations

import os
import threading
import time

_started = False
_lock = threading.Lock()


def _public_url() -> str | None:
    """The Space's public URL, or None when not on HF."""
    host = os.environ.get("SPACE_HOST")
    if not host:
        return None
    return host if host.startswith("http") else f"https://{host}"


def _loop(url: str, interval_s: int) -> None:
    while True:
        time.sleep(interval_s)
        try:
            import requests
            requests.get(url, timeout=15)
        except Exception:  # noqa: BLE001 — best-effort, never crash the app
            pass


def start_keepalive() -> bool:
    """Start the keep-alive thread once per process. Returns True if it started.

    Safe to call on every Streamlit rerun — only the first call starts a thread.
    """
    global _started
    url = _public_url()
    if not url:
        return False  # not on HF — nothing to keep alive
    with _lock:
        if _started:
            return False
        try:
            minutes = float(os.environ.get("KEEPALIVE_MINUTES", "90"))
        except ValueError:
            minutes = 90.0
        interval_s = max(60, int(minutes * 60))
        threading.Thread(
            target=_loop, args=(url, interval_s),
            daemon=True, name="aqe-keepalive",
        ).start()
        _started = True
        return True
