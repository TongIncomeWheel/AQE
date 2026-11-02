"""In-app live-alert poller — the Trade Entry Menu's 15-min heartbeat.

A daemon thread (started once per process) runs `alerts.engine.run_alert_cycle`
every AQE_ALERT_MINUTES (default 30 since 2026-11-01, PM ruling; FMP Starter prices are 15-min delayed)
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


def _watchdog() -> None:
    """Dead-man alarm for a HUNG cycle: the loop thread can block inside a cycle
    (the 2026-08-06 failure) without dying. This thread checks the Drive
    heartbeat every 5 min and emails once a day if the primary has not completed
    a cycle for AQE_DEADMAN_MINUTES inside the window. A dead PROCESS is covered
    by scripts/alert_deadman.py and the backstop's pre-check, which run elsewhere."""
    global _last_deadman
    while True:
        time.sleep(300)
        try:
            from src.alerts import heartbeat
            _last_deadman = heartbeat.check_and_alarm()
        except Exception as exc:  # noqa: BLE001
            _last_deadman = {"stale": None, "reason": f"watchdog error: {exc}"}


_last_deadman: dict | None = None


def last_deadman() -> dict | None:
    return _last_deadman


def start_alert_job() -> bool:
    """Start the alert poller once per process. Returns True if it started.

    This is now the PRIMARY emailer: with the Resend HTTP backend (HTTPS, which
    HF allows) the in-app thread can both poll reliably every 15 min AND send the
    digest — unlike GitHub's */15 cron which GitHub throttles. The GH Actions
    backstop still runs and shares the Drive dedup state, so the two never
    double-email. Active on HF, or anywhere with AQE_ENABLE_ALERTS=1.
    Needs RESEND_API_KEY set (else it polls + logs but can't email from HF).
    """
    global _started
    on_hf = bool(os.environ.get("SPACE_HOST") or os.environ.get("SPACE_ID"))
    forced = os.environ.get("AQE_ENABLE_ALERTS") == "1"
    if not (on_hf or forced):
        return False
    with _lock:
        if _started:
            return False
        threading.Thread(target=_loop, daemon=True, name="aqe-alert-job").start()
        threading.Thread(target=_watchdog, daemon=True, name="aqe-alert-watchdog").start()
        _started = True
        return True
