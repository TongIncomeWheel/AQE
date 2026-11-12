"""ONE reversible switch that pauses every alert path (PM order 2026-11-12: "pause all alerts until I resume").

The flag is a small JSON file on the pinned Drive folder, `aqe_alerts_paused.json`, so the in-app HF poller, the GitHub `alerts.yml`
backstop and a laptop all read the same switch. `{"paused": true, ...}` pauses; rewriting it `{"paused": false, ...}` resumes (the file is
never deleted: the record of who paused and when stays). The env var ALERTS_PAUSED=true pauses one process regardless of Drive.

What a pause stops: the whole alert cycle in `engine.run_alert_cycle`: no FMP quote pull, no condition cards, no card email, no stale-PMA or
after-close email, no cockpit notice, no heartbeat beat. The dead-man check reports `paused` instead of raising an engine-silent alarm.
What it never touches: the daily AQE run, the committee, the export, the levels files.

A Drive read that FAILS does not pause (alerts guard real stops; a broken switch must not silently turn them off) and is returned as `problem`
so the status says so. Alerts only: nothing here places, changes or sizes an order.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

FLAG_FILENAME = "aqe_alerts_paused.json"
_TRUE = {"1", "true", "yes", "on"}


def _env_paused() -> bool:
    return os.environ.get("ALERTS_PAUSED", "").strip().lower() in _TRUE


def read_flag() -> tuple[dict | None, str | None]:
    """(flag document or None, problem). A missing file is (None, None): never paused. An unreadable one is (None, why)."""
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return None, None
        txt = gdrive_uploader.download_text(FLAG_FILENAME)
        if not txt:
            return None, None
        doc = json.loads(txt)
        return (doc if isinstance(doc, dict) else None), (None if isinstance(doc, dict) else "flag file is not a JSON object")
    except Exception as exc:  # noqa: BLE001
        return None, f"pause flag unreadable from Drive: {type(exc).__name__}: {exc}"


def status() -> dict:
    """{paused, why, since, by, problem}. Env var wins; otherwise the Drive flag."""
    if _env_paused():
        return {"paused": True, "why": "ALERTS_PAUSED env var is set", "since": None, "by": "env", "problem": None}
    doc, problem = read_flag()
    paused = bool((doc or {}).get("paused"))
    return {"paused": paused, "why": (doc or {}).get("reason"), "since": (doc or {}).get("since"),
            "by": (doc or {}).get("by"), "problem": problem}


def is_paused() -> bool:
    return bool(status()["paused"])


def set_paused(paused: bool, reason: str = "", by: str = "pm-order") -> dict:
    """Write the flag to Drive and read it back. Raises if Drive is not configured or the read-back disagrees: a pause that did not land
    must never be reported as one."""
    from src.data import gdrive_uploader
    if not gdrive_uploader.is_configured():
        raise RuntimeError("Drive is not configured here: the pause flag cannot be written")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = {"paused": bool(paused), "reason": reason, "by": by, "since": now if paused else None,
           "resumed_at": None if paused else now}
    gdrive_uploader.upload_or_replace(FLAG_FILENAME, json.dumps(doc, indent=2), mime="application/json")
    back, problem = read_flag()
    if problem or bool((back or {}).get("paused")) != bool(paused):
        raise RuntimeError(f"read-back disagrees with what was written (wrote paused={paused}; read {back}; problem {problem})")
    return status()
