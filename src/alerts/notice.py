"""The cockpit notice -- ONE machine-readable record per alert cycle (PM 2026-11-02).

Why: the [AQE] email is the only output of the 30-min alert cycle, and the
cockpit (the PM's live Claude session) has been reading it by parsing Gmail.
This module writes the SAME cards the email renders as a JSON notice
(`aegis/plugin/aegis-core/contracts/aqe_alert_notice.schema.json`) so the
Aegis side reads a contract, not an inbox, and email vs cockpit cannot
disagree. Email is unchanged; `email.sent/subject` in the notice is the parity
evidence for the eventual cut-over.

Published every in-window cycle (a quiet cycle is a real answer):
  Drive   aqe_alert_notice.json                         latest
  GitHub  aegis/output/alerts/live/latest.json          latest
  GitHub  aegis/output/alerts/live/<session_date>.json  the day's cycles, newest first
(aegis/output/** never triggers an HF redeploy -- deploy-hf.yml paths-ignore.)

AQE makes no decisions and no sizing: `action` is the plan's own plain verb,
levels are the committee's (or AQE-default) and the reader does any share
arithmetic on the Aegis 1R. A failed publish is loud in the cycle summary,
never silent.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data.paths import PROJECT_ROOT

SCHEMA = "aqe_alert_notice.v1"
DRIVE_LATEST = "aqe_alert_notice.json"
REPO_DIR = "aegis/output/alerts/live"
LOCAL_DIR = PROJECT_ROOT / "aegis" / "output" / "alerts" / "live"
_ET = ZoneInfo("America/New_York")
_SGT = ZoneInfo("Asia/Singapore")

# Plain verbs from the plan (live-review REVIEW_SPEC house style). Facts about a
# state, never a recommendation.
_ACTION = {
    "CONDITION_MET": ("ACT", "Buy trigger hit: queue the Tiger preview on your word"),
    "UNR_TRIGGER": ("ACT", "U&R entry signal: queue the Tiger preview on your word"),
    "FAILED_PUSH": ("INFO", "Back under its buy price: wait"),
    "CHASED": ("INFO", "Past the chase price: do not chase"),
    "UNR_FAILED": ("INFO", "U&R failed: stand down"),
    "EXIT_LINE_HELD": ("RISK", "Held name through its exit price: review your stop now"),
}
_HELD_ACTION = {
    "near_stop": ("RISK", "Near your broker stop: check it"),
    "near_target": ("INFO", "Near first target: trim or run, your call"),
    "exit_cross": ("RISK", "Held name through the committee exit price: review your stop now"),
    "veto": ("RISK", "QS veto on a held name: review"),
    "order": ("RISK", "Stop order check: confirm the stop is working"),
    "other": ("INFO", "Held position event"),
}
_SEV_RANK = {"ACT": 0, "RISK": 1, "INFO": 2}


def _n(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _row_class(row: dict) -> str:
    if row.get("aqe_default"):
        return "AQE_DEFAULT"
    c = row.get("class")
    return c if c in ("ADVANCE", "HOLD_FOR_CONDITIONS", "HELD", "WATCH") else "UNKNOWN"


def _item_from_card(card: tuple, market_broken: bool) -> dict:
    """One condition card -> one notice item. Headline/lines come from the
    emailer so the two channels print the same words."""
    from src.alerts import emailer as EM
    ticker, row, ev, states, live = card
    built = EM.build_condition_card(ticker, row, ev, states, live)
    primary = next((s for s in ("UNR_FAILED", "UNR_TRIGGER", "CONDITION_MET", "EXIT_LINE_HELD",
                                "FAILED_PUSH", "CHASED") if s in states), states[0])
    sev, action = _ACTION.get(primary, ("INFO", primary.replace("_", " ").title()))
    if primary == "CHASED" and row.get("deal_pinned"):
        sev, action = "INFO", "Deal-pinned (pending takeover): no buy trigger"
    elif primary == "CHASED" and row.get("watch_only"):
        sev, action = "INFO", "AQE list name through its entry line: no buy trigger"
    held = row.get("class") == "HELD"
    if held and sev == "ACT":
        sev, action = "INFO", "Held name met its add condition: your call"
    spot = _n(live.get("price"))
    levels = row.get("levels") or {}
    unr = live.get("unr") or {}
    entry = stop = target = None
    stop_type = None
    if primary in ("UNR_TRIGGER", "UNR_FAILED"):
        entry, stop, stop_type = spot, _n(unr.get("stop")), "unr_low_of_day"
    else:
        entry = EM._effective_entry(row)
        stop = _n(levels.get("stop"))
        stop_type = levels.get("stop_type") or ("committee" if stop is not None else None)
        tps = [_n(t) for t in (levels.get("tp") or []) if _n(t) is not None]
        target = next((t for t in tps if entry is None or t > entry), tps[0] if tps else None)
        if held and stop is None:
            stop = _n((row.get("broker_stop") or {}).get("stop"))
            stop_type = "broker" if stop is not None else None
    words = (ev.get("shared_buy_detail") or []) + (ev.get("shared_confirm_detail") or [])
    conds = ({"met": sum(1 for _e, r in words if r == "TRUE"), "of": len(words), "who": EM._who(row)}
             if words else None)
    armed = (unr.get("armed") or [None])[0] or {}
    risk = (entry - stop) if (entry is not None and stop is not None and entry > stop) else None
    prev = _n(live.get("prev_close")) if isinstance(live, dict) else None
    day_pct = ((spot / prev - 1) * 100) if (spot and prev) else None
    return {
        "ticker": ticker, "class": _row_class(row), "held": held, "states": list(states),
        "severity": sev, "headline": built.get("headline") or ticker, "action": action,
        "price": spot, "day_pct": round(day_pct, 2) if day_pct is not None else None,
        "entry": entry, "stop": stop, "stop_type": stop_type, "target": target,
        "risk_per_share": round(risk, 4) if risk is not None else None,
        "conditions": conds,
        "unr": {"status": unr.get("status"), "stop": _n(unr.get("stop")),
                "level": _n(armed.get("level"))} if unr else None,
        "lines": [str(x) for x in (built.get("lines") or []) if x],
        "suppressed_by_market_kill": bool(market_broken and sev == "ACT" and not held),
    }


def _item_from_held_event(ev: dict) -> dict:
    from src.alerts import emailer as EM
    built = EM.build_held_card(ev)
    kind = EM._held_kind(ev)
    sev, action = _HELD_ACTION.get(kind, _HELD_ACTION["other"])
    px = _n(ev.get("live_px"))
    b_stop, c_exit = _n(ev.get("broker_stop")), _n(ev.get("committee_exit"))
    stop, stop_type = (b_stop, "broker") if b_stop is not None else (
        (c_exit, "committee_exit") if c_exit is not None else (_n(ev.get("level_price")), "level"))
    return {
        "ticker": ev.get("ticker"), "class": "HELD", "held": True,
        "states": [ev.get("kind") or ev.get("level") or kind],
        "severity": sev, "headline": built.get("headline") or str(ev.get("ticker")), "action": action,
        "price": px, "day_pct": _n(ev.get("chg_pct")),
        "entry": None, "stop": stop, "stop_type": stop_type, "target": _n(ev.get("target_price")),
        "risk_per_share": None, "conditions": None, "unr": None,
        "lines": [str(x) for x in (built.get("lines") or []) if x],
        "suppressed_by_market_kill": False,
    }


def build(*, cards: list[tuple] | None, setup_rows: list[tuple] | None,
          held_events: list[dict] | None, meta: dict | None, email: dict | None,
          engine: dict | None, now_et: datetime, seq: int, source: str) -> dict:
    """Pure assembly (no I/O). `cards` are the digest cards (full ones), `setup_rows`
    the one-line U&R rows, exactly as build_condition_digest splits them."""
    from src.alerts import emailer as EM
    meta = meta or {}
    mk = meta.get("market_kill") or {}
    broken = bool(mk.get("broken"))
    items: list[dict] = []
    for c in cards or []:
        try:
            items.append(_item_from_card(c, broken))
        except Exception as exc:  # noqa: BLE001 -- one bad card never drops the notice
            st = list(c[3]) if c and len(c) > 3 and c[3] else []
            sev = next((_ACTION[x][0] for x in st if x in _ACTION), "INFO")
            items.append({"ticker": c[0] if c else "?", "class": "UNKNOWN", "held": False,
                          "states": st, "severity": sev,
                          "headline": f"{c[0] if c else '?'} (card unreadable: {exc})",
                          "action": "Read the email card", "price": None, "day_pct": None,
                          "entry": None, "stop": None, "stop_type": None, "target": None,
                          "risk_per_share": None, "conditions": None, "unr": None, "lines": [],
                          "suppressed_by_market_kill": False})
    for ev in held_events or []:
        try:
            items.append(_item_from_held_event(ev))
        except Exception as exc:  # noqa: BLE001
            items.append({"ticker": ev.get("ticker"), "class": "HELD", "held": True,
                          "states": [ev.get("kind") or "?"], "severity": "RISK",
                          "headline": f"{ev.get('ticker')} held event (unreadable: {exc})",
                          "action": "Check the held name", "price": _n(ev.get("live_px")),
                          "lines": [], "suppressed_by_market_kill": False})
    items.sort(key=lambda i: (_SEV_RANK.get(i.get("severity"), 9), i.get("ticker") or ""))
    setups = []
    for c in setup_rows or []:
        try:
            setups.append({"ticker": c[0], "price": _n((c[4] or {}).get("price")),
                           "text": EM._candidate_row(c)})
        except Exception:  # noqa: BLE001
            setups.append({"ticker": c[0] if c else "?", "price": None, "text": "setup forming"})
    if mk.get("just_broke"):
        try:
            card = EM.build_market_card(mk)
            sym = ((mk.get("kill") or {}).get("symbol")) or "MARKET"
            items.insert(0, {"ticker": sym, "class": "MARKET", "held": False, "states": ["MARKET_KILL"],
                             "severity": "RISK", "headline": card["headline"],
                             "action": "Market condition broken: no new buys this session",
                             "price": None, "day_pct": None, "entry": None, "stop": None, "stop_type": None,
                             "target": None, "risk_per_share": None, "conditions": None, "unr": None,
                             "lines": card["lines"], "suppressed_by_market_kill": False})
        except Exception:  # noqa: BLE001
            pass
    actionable = bool(items) or bool(mk.get("just_broke"))
    sgt = now_et.astimezone(_SGT)
    return {
        "schema": SCHEMA, "seq": seq, "session_date": now_et.date().isoformat(),
        "cycle_at_utc": now_et.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "cycle_at_sgt": sgt.strftime("%Y-%m-%d %H:%M SGT"), "cycle_at_et": now_et.strftime("%H:%M ET"),
        "source": source,
        "data": {k: meta.get(k) for k in ("pma_run", "pma_session", "pma_missing",
                                         "aqe_date", "aqe_covers", "aqe_current")},
        "market": {"status": mk.get("status"), "state": mk.get("state"), "broken": broken,
                   "just_broke": bool(mk.get("just_broke"))},
        "actionable": actionable,
        "items": items, "setups_forming": setups,
        "suppressed": int((engine or {}).get("suppressed") or 0),
        "quiet_line": None if actionable else f"{sgt.strftime('%H:%M')} SGT · AQE: no trigger, no action.",
        "email": {"sent": (email or {}).get("ok") if email is not None else None,
                  "subject": (email or {}).get("subject")},
        "engine": {k: (engine or {}).get(k) for k in ("checked", "new_triggers", "pma_fresh", "reason")},
    }


def build_alarm(reason: str, now_et: datetime, seq: int, source: str, last_primary_utc=None) -> dict:
    """A distinct ALARM record in the notice feed (PM 2026-11-02: the dead-man
    alarm is NOT an email). Same schema, `alarm` block set, actionable, no items.
    The reader prints it as the engine-silent headline (exit 4)."""
    sgt = now_et.astimezone(_SGT)
    return {
        "schema": SCHEMA, "seq": seq, "session_date": now_et.date().isoformat(),
        "cycle_at_utc": now_et.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "cycle_at_sgt": sgt.strftime("%Y-%m-%d %H:%M SGT"), "cycle_at_et": now_et.strftime("%H:%M ET"),
        "source": source, "data": {}, "market": {"status": None, "state": None, "broken": False, "just_broke": False},
        "actionable": True, "items": [], "setups_forming": [], "suppressed": 0, "quiet_line": None,
        "email": {"sent": None, "subject": None}, "engine": {"reason": reason},
        "alarm": {"kind": "engine_silent", "reason": reason, "last_primary_utc": last_primary_utc,
                  "text": f"AQE ALERT ENGINE SILENT: {reason}. Levels are NOT being watched. "
                          "Check the HF Space (Logs / restart) or run the 'AQE live alerts' workflow by hand (force)."},
    }


def publish_alarm(reason: str, last_primary_utc=None, now_et: datetime | None = None,
                  source: str | None = None) -> dict:
    """Dead-man alarm into the notice feed. Never raises; returns publish status."""
    now_et = now_et or datetime.now(_ET)
    if source is None:
        from src.alerts.heartbeat import source_label
        source = source_label()
    doc = build_alarm(reason, now_et, _next_seq(now_et.date().isoformat()), source, last_primary_utc)
    return {"notice": doc, "publish": publish(doc)}


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def _drive():
    from src.data import gdrive_uploader
    return gdrive_uploader if gdrive_uploader.is_configured() else None


def _next_seq(session_date: str) -> int:
    """seq continues the day's count from the latest published notice (Drive,
    then local), restarting at 1 on a new session date."""
    prev = None
    try:
        g = _drive()
        txt = g.download_text(DRIVE_LATEST) if g else None
        if txt:
            prev = json.loads(txt)
    except Exception:  # noqa: BLE001
        prev = None
    if prev is None:
        try:
            p = LOCAL_DIR / "latest.json"
            if p.exists():
                prev = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = None
    if prev and prev.get("session_date") == session_date:
        return int(prev.get("seq") or 0) + 1
    return 1


def publish(notice: dict) -> dict:
    """Local + Drive + GitHub (latest + the day's list). Returns per-target
    status; any failure is named, never swallowed."""
    out = {"local": None, "drive": None, "github_latest": None, "github_day": None}
    payload = json.dumps(notice, indent=1, default=str)
    day = notice.get("session_date") or "unknown"
    try:
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        (LOCAL_DIR / "latest.json").write_text(payload, encoding="utf-8")
        out["local"] = "ok"
    except Exception as exc:  # noqa: BLE001
        out["local"] = f"failed: {exc}"
    try:
        g = _drive()
        if g:
            g.upload_or_replace(DRIVE_LATEST, payload, mime="application/json")
            out["drive"] = "ok"
        else:
            out["drive"] = "not configured"
    except Exception as exc:  # noqa: BLE001
        out["drive"] = f"failed: {type(exc).__name__}: {exc}"
    try:
        from src.data import github_sync as GS
        if not GS.is_configured():
            out["github_latest"] = out["github_day"] = "not configured"
            return out
        r = GS.put_file(f"{REPO_DIR}/latest.json", payload,
                        f"alerts: notice {day} #{notice.get('seq')} ({notice.get('cycle_at_et')})")
        out["github_latest"] = "ok" if r.get("ok") else f"failed: {r.get('reason')}"
        day_path = f"{REPO_DIR}/{day}.json"
        prior: list = []
        got = GS.get_file(day_path)
        if got.get("ok"):
            try:
                prior = json.loads(got["text"])
                prior = prior if isinstance(prior, list) else []
            except Exception:  # noqa: BLE001
                prior = []
        prior = [p for p in prior if p.get("seq") != notice.get("seq")]
        day_doc = [notice] + sorted(prior, key=lambda p: -(p.get("seq") or 0))
        r2 = GS.put_file(day_path, json.dumps(day_doc, indent=1, default=str),
                         f"alerts: notices {day} ({len(day_doc)} cycles)")
        out["github_day"] = "ok" if r2.get("ok") else f"failed: {r2.get('reason')}"
    except Exception as exc:  # noqa: BLE001
        out["github_latest"] = out["github_latest"] or f"failed: {type(exc).__name__}: {exc}"
        out["github_day"] = out["github_day"] or f"failed: {type(exc).__name__}: {exc}"
    return out


def publish_from_summary(summary: dict, now_et: datetime | None = None,
                         source: str | None = None) -> dict | None:
    """Engine hook: build + publish from the cycle summary's `_notice` inputs
    (stashed by condition_cycle) -- or a quiet/degraded notice when the cycle
    never reached the condition layer. Never raises."""
    now_et = now_et or datetime.now(_ET)
    if source is None:
        from src.alerts.heartbeat import source_label
        source = source_label()
    inputs = summary.pop("_notice", None) or {}
    meta = inputs.get("meta")
    if meta is None:
        mk = summary.get("market_kill") or {}
        meta = {"market_kill": {"status": mk.get("status"), "state": mk.get("state"),
                                "broken": mk.get("broken"), "just_broke": mk.get("just_broke")}}
    engine = {"checked": summary.get("checked"), "new_triggers": summary.get("new_triggers"),
              "pma_fresh": (summary.get("pma") or {}).get("fresh"), "reason": summary.get("reason"),
              "suppressed": ((summary.get("pma_conditions") or {}).get("suppressed") or 0)
              + ((summary.get("market_kill") or {}).get("suppressed") or 0)}
    seq = _next_seq(now_et.date().isoformat())
    notice = build(cards=inputs.get("cards"), setup_rows=inputs.get("setup_rows"),
                   held_events=inputs.get("held_events"), meta=meta, email=inputs.get("email"),
                   engine=engine, now_et=now_et, seq=seq, source=source)
    res = publish(notice)
    summary["notice"] = {"seq": seq, "actionable": notice["actionable"], "items": len(notice["items"]),
                         "publish": res}
    return notice
