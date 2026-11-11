"""Poller heartbeat + dead-man alarm (PM/conductor 2026-11-02).

Why: a hung cycle or a dead thread used to be silent. The HTTP keepalive proves
the web server answers, not that the alert loop is cycling (2026-08-06: cycles
hung with no trail). Every in-window cycle writes `aqe_alert_heartbeat.json`
(Drive + local mirror). `deadman_status` is pure; `check_and_alarm` sends ONE
alarm per day when the PRIMARY poller has not completed a cycle for
`C.DEADMAN_MINUTES` while the alert window is open -- as an ALARM record in
the cockpit notice feed (src/alerts/notice.py), never an email (PM 2026-11-02).

The GitHub backstop's own beats are recorded separately (`source == "gha"`) and
never count as the primary being alive -- a backstop that fires once a day must
not mask a dead in-app poller. A failed Drive read/write is loud in the return
value, never a silent "alive".

Alerts only: nothing here places, changes or sizes an order.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.alerts import config as C
from src.data.paths import PROJECT_ROOT

HEARTBEAT_FILENAME = "aqe_alert_heartbeat.json"
LOCAL_PATH = PROJECT_ROOT / "aegis" / "output" / "alerts" / HEARTBEAT_FILENAME
_ET = ZoneInfo("America/New_York")
BACKSTOP_SOURCE = "gha"


def source_label() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return BACKSTOP_SOURCE
    if os.environ.get("SPACE_HOST") or os.environ.get("SPACE_ID"):
        return "hf"
    return os.environ.get("AQE_POLLER_SOURCE", "local")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def load() -> tuple[dict | None, str | None]:
    """(heartbeat, problem). Drive first, local mirror second. `problem` is set
    when Drive is configured but unreadable -- the caller must say so."""
    problem = None
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(HEARTBEAT_FILENAME)
            if txt:
                return json.loads(txt), None
    except Exception as exc:  # noqa: BLE001
        problem = f"heartbeat unreadable from Drive: {type(exc).__name__}: {exc}"
    try:
        if LOCAL_PATH.exists():
            return json.loads(LOCAL_PATH.read_text(encoding="utf-8")), problem
    except Exception as exc:  # noqa: BLE001
        problem = problem or f"local heartbeat unreadable: {exc}"
    return None, problem


def _save(hb: dict) -> str | None:
    """Write local + Drive. Returns an error string if Drive failed (loud)."""
    payload = json.dumps(hb, indent=2)
    try:
        LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_PATH.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(HEARTBEAT_FILENAME, payload, mime="application/json")
    except Exception as exc:  # noqa: BLE001
        return f"heartbeat write to Drive failed: {type(exc).__name__}: {exc}"
    return None


def beat(summary: dict, now_utc: datetime | None = None, source: str | None = None) -> dict:
    """Record one completed in-window cycle. Never raises."""
    now_utc = now_utc or datetime.now(timezone.utc)
    source = source or source_label()
    prev, _ = load()
    hb = dict(prev or {})
    stamp = _iso(now_utc)
    if summary.get("crashed"):
        # A cycle that crashes every time must not read as "alive": record the
        # failure but leave last_primary_utc alone so the dead-man still trips.
        hb.update({"last_crash_utc": stamp, "last_crash_reason": summary.get("reason")})
        err = _save(hb)
        if err:
            hb["write_error"] = err
        return hb
    hb.update({
        "last_cycle_utc": stamp, "last_source": source, "seq": int(hb.get("seq") or 0) + 1,
        "ok": bool(summary.get("ok")), "reason": summary.get("reason"),
        "checked": summary.get("checked"), "new_triggers": summary.get("new_triggers"),
        "pma_fresh": (summary.get("pma") or {}).get("fresh"),
    })
    # The email outcome of THIS cycle, kept where the status check can read it. A
    # card digest that failed to send used to leave no trace outside a swallowed
    # summary (state is advanced before the send, so it is never retried).
    em = ((summary.get("_notice") or {}).get("email"))
    if em is not None:
        hb["last_email_attempt_utc"] = stamp
        hb["last_email_ok"] = em.get("ok")
        hb["last_email_reason"] = em.get("reason")
        hb["last_email_subject"] = em.get("subject")
        if em.get("ok"):
            hb["last_email_sent_utc"] = stamp
    if source != BACKSTOP_SOURCE:
        hb["last_primary_utc"], hb["primary_source"] = stamp, source
    else:
        hb["last_backstop_utc"] = stamp
    err = _save(hb)
    if err:
        hb["write_error"] = err
    return hb


def note_notice_problem(problem: str, now_utc: datetime | None = None) -> None:
    """Record that this cycle's cockpit notice did not publish (loud, never
    raises). Written only on a problem, so a healthy cycle costs no extra write."""
    try:
        hb, _ = load()
        hb = dict(hb or {})
        hb["last_notice_problem"] = problem
        hb["last_notice_problem_utc"] = _iso(now_utc or datetime.now(timezone.utc))
        _save(hb)
    except Exception:  # noqa: BLE001
        pass


def deadman_status(hb: dict | None, now_utc: datetime, now_et: datetime | None = None,
                   load_problem: str | None = None) -> dict:
    """Pure. stale=True only inside the alert window, once the window has been
    open long enough that a cycle must have completed."""
    from src.alerts.engine import in_alert_window
    now_et = now_et or now_utc.astimezone(_ET)
    out = {"stale": False, "age_min": None, "reason": "outside the alert window",
           "last_primary_utc": (hb or {}).get("last_primary_utc"), "problem": load_problem}
    if not in_alert_window(now_et):
        return out
    open_min = C.MARKET_OPEN[0] * 60 + C.MARKET_OPEN[1]
    since_open = now_et.hour * 60 + now_et.minute - open_min
    if since_open < C.DEADMAN_MINUTES:
        out["reason"] = f"window opened {since_open} min ago -- first cycle not yet due"
        return out
    last = (hb or {}).get("last_primary_utc")
    if not last:
        out.update(stale=True, reason="no primary-poller heartbeat on record"
                   + (f" ({load_problem})" if load_problem else ""))
        return out
    try:
        age = (now_utc - datetime.fromisoformat(last)).total_seconds() / 60
    except ValueError:
        out.update(stale=True, reason=f"heartbeat timestamp unreadable: {last!r}")
        return out
    out["age_min"] = round(age, 1)
    if age > C.DEADMAN_MINUTES:
        out.update(stale=True, reason=f"no completed cycle for {age:.0f} min "
                   f"(limit {C.DEADMAN_MINUTES}) -- last at {last}")
    else:
        out["reason"] = f"alive: last cycle {age:.0f} min ago"
    return out


def check_and_alarm(send: bool = True, now_utc: datetime | None = None) -> dict:
    """Read the heartbeat, decide, and (once per ET day) publish the ALARM
    record into the notice feed (PM 2026-11-02: never an email). The cockpit
    reader prints it as the engine-silent headline."""
    now_utc = now_utc or datetime.now(timezone.utc)
    hb, problem = load()
    st = deadman_status(hb, now_utc, load_problem=problem)
    st["alarm_sent"] = False
    today = now_utc.astimezone(_ET).date().isoformat()
    if st["stale"] and (hb or {}).get("alarm_day") != today:
        if send:
            try:
                from src.alerts import notice
                res = notice.publish_alarm(st["reason"], last_primary_utc=st.get("last_primary_utc"))
                pub = res.get("publish") or {}
                ok = any(v == "ok" for k, v in pub.items() if k in ("drive", "github_latest"))
                st["alarm_sent"] = ok
                st["alarm_detail"] = None if ok else f"alarm notice not published: {pub}"
            except Exception as exc:  # noqa: BLE001
                st["alarm_detail"] = f"alarm publish failed: {exc}"
        if st["alarm_sent"]:
            hb = dict(hb or {})
            hb["alarm_day"] = today
            _save(hb)
    return st
