"""In-app live-alert poller — the Trade Entry Menu's 15-min heartbeat.

A daemon thread (started once per process) runs `alerts.engine.run_alert_cycle`
every AQE_ALERT_MINUTES (default 15, matching FMP Starter's 15-min price delay)
during the US cash session. Each cycle pulls live quotes for every monitored
ticker (longlist / watchlist / PE / held), checks key levels, and emails the PM a
digest of any NEW level hits (dedup'd once-per-level-per-day via shared state).

This poll doubles as keep-warm: the recurring outbound work keeps the Space busy
within FMP throttle limits.

Gating:
- Active only on HF (SPACE_HOST set) unless AQE_ENABLE_ALERTS=1 forces it on.
- Emails only fire inside the market window (handled in run_alert_cycle).
- No-op without AQE_SMTP_PASSWORD (engine still evaluates; email just won't send).
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import config as C

SGT = ZoneInfo("Asia/Singapore")
_started = False
_lock = threading.Lock()
_last: dict | None = None  # last cycle summary, for the UI status line


def last_cycle() -> dict | None:
    return _last


def _loop() -> None:
    global _last
    interval = max(60, C.ALERT_MINUTES * 60)
    while True:
        try:
            from src.alerts.engine import run_alert_cycle
            summary = run_alert_cycle(send_email=True)
            summary["ran_at"] = datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT")
            _last = summary
        except Exception as exc:  # noqa: BLE001
            _last = {"ok": False, "reason": f"{type(exc).__name__}: {exc}",
                     "ran_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT")}
        time.sleep(interval)


def start_alert_job() -> bool:
    """Start the alert poller once per process. Returns True if it started.

    IMPORTANT: HF Spaces block outbound SMTP, so the *email* path cannot run on
    HF — and if this poller marked the shared Drive dedup state, it would suppress
    the GitHub Actions backstop (the real emailer) from sending. So on HF this is
    intentionally a no-op: the GH Actions cron owns the poll→dedup→email→history
    pipeline. This thread only runs when explicitly forced (AQE_ENABLE_ALERTS=1),
    e.g. local dev where SMTP works.
    """
    global _started
    forced = os.environ.get("AQE_ENABLE_ALERTS") == "1"
    if not forced:
        return False
    with _lock:
        if _started:
            return False
        threading.Thread(target=_loop, daemon=True, name="aqe-alert-job").start()
        _started = True
        return True
