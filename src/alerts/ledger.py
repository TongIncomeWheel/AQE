"""Alert ledger — every fired alert, appended to a running file on Drive.

An email cannot be handed to the AIC, so every alert is also written here.
Over time this becomes the record the alert layer is judged on: what fired,
on what, in what state, and (once outcomes are filled) whether it was worth
firing.

Two design points, both deliberate:

ROTATION, NOT MANUAL CLEANUP. The hot file keeps the last RETENTION_DAYS; once
an entry ages out it moves to `aqe_alert_ledger_YYYY-MM.json`. Nothing is ever
deleted and nothing has to be remembered — a running file that needs a weekly
prune is a running file that will one day be 40MB or silently truncated.

EACH ENTRY MUST BE SCORABLE LATER. An alert that recorded only "BOS fired on
NVDA at 14:32" cannot be evaluated afterwards: you would not know what the
level was, where price sat, or what AQE thought of the name at that moment.
So every entry carries the trigger, the level, the price, the intraday
measures and the list/QS state AT FIRE TIME. That is what makes the file a
ledger rather than a log.

Follows the same Drive-plus-local-mirror pattern as `alerts/state.py`, so
there is one storage idiom in this package rather than two.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR

LEDGER_FILENAME = "aqe_alert_ledger.json"
LOCAL_LEDGER = OUTPUT_DIR / LEDGER_FILENAME
_ET = ZoneInfo("America/New_York")
_SGT = ZoneInfo("Asia/Singapore")

# Days kept in the hot file before an entry rotates to its month archive.
RETENTION_DAYS = 30
# Hard cap so a runaway poll cannot produce an unbounded file even within the
# retention window. Oldest entries rotate out first.
MAX_HOT_ENTRIES = 5000


def _archive_name(day: str) -> str:
    return f"aqe_alert_ledger_{day[:7]}.json"          # YYYY-MM


def _now_iso() -> str:
    return datetime.now(_ET).isoformat(timespec="seconds")


def build_entry(trigger: dict, record: dict, quote: dict,
                intraday: dict | None = None) -> dict:
    """One ledger row, carrying enough context to be scored later.

    `trigger` is the alert dict from the engine; `record` the export row;
    `quote` the live quote; `intraday` the normalised measures.
    """
    qs = record.get("qs") or {}
    bracket = record.get("bracket") or {}
    return {
        "ts": _now_iso(),
        "date": datetime.now(_ET).strftime("%Y-%m-%d"),
        "ticker": trigger.get("ticker"),
        "event": trigger.get("level"),
        "label": trigger.get("label"),
        "note": trigger.get("note"),
        "level_price": trigger.get("level_price"),
        "live_px": trigger.get("live_px"),
        "is_held": bool(trigger.get("is_held")),
        # --- state AT FIRE TIME: without this the row cannot be scored ---
        "lists": {
            "on_longlist": bool(record.get("on_longlist")),
            "on_elder": bool(record.get("on_elder")),
            "on_qs": bool(record.get("on_qs")),
            "held": bool(record.get("held")),
        },
        "qs": {
            "conviction": qs.get("conviction"),
            "state": (qs.get("state") or {}).get("code"),
            "p": (qs.get("odds") or {}).get("p"),
            "n_analogues": (qs.get("odds") or {}).get("n_analogues"),
            "recipe_hits": (qs.get("engine") or {}).get("recipe_hits"),
        } if qs else None,
        "scores": {k: record.get(k) for k in
                   ("sc_momentum", "ptrs", "elder", "flow", "energy", "mp",
                    "mp_state", "lens_positive")},
        "levels": {
            "bracket_stop": bracket.get("stop"),
            "bracket_valid": bracket.get("valid"),
            "tp1": next((t.get("price") for t in (bracket.get("targets") or [])
                         if t.get("tp") == "TP1"), None),
            "last_pivot_high": (record.get("last_pivot_high") or {}).get("price"),
            "atr_14d": record.get("atr_14d"),
        },
        "structure_shift": record.get("structure_shift"),
        "intraday": intraday or {},
        # Filled by a later pass, exactly like signal_outcomes.
        "outcome": None,
    }


def load() -> dict:
    """The hot ledger — Drive first, then the local mirror, then empty."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(LEDGER_FILENAME)
            if txt:
                d = json.loads(txt)
                if isinstance(d, dict) and isinstance(d.get("entries"), list):
                    return d
    except Exception:  # noqa: BLE001
        pass
    try:
        if LOCAL_LEDGER.exists():
            d = json.loads(LOCAL_LEDGER.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("entries"), list):
                return d
    except Exception:  # noqa: BLE001
        pass
    return {"updated": None, "entries": []}


def _split_for_rotation(entries: list[dict]) -> tuple[list, list]:
    """(keep_hot, rotate_out) by age, then by the hard entry cap."""
    cutoff = (datetime.now(_ET) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    hot = [e for e in entries if (e.get("date") or "") >= cutoff]
    old = [e for e in entries if (e.get("date") or "") < cutoff]
    if len(hot) > MAX_HOT_ENTRIES:
        hot.sort(key=lambda e: e.get("ts") or "")
        old.extend(hot[:len(hot) - MAX_HOT_ENTRIES])
        hot = hot[len(hot) - MAX_HOT_ENTRIES:]
    return hot, old


def append(new_entries: list[dict]) -> dict:
    """Append, rotate anything aged out, persist locally and to Drive.

    Best-effort throughout: a ledger write must never break the alert run that
    produced it. Returns {ok, appended, hot, rotated, archives}.
    """
    if not new_entries:
        return {"ok": True, "appended": 0, "hot": 0, "rotated": 0, "archives": []}
    try:
        led = load()
        entries = list(led.get("entries") or []) + list(new_entries)
        hot, old = _split_for_rotation(entries)

        archives: list[str] = []
        if old:
            by_month: dict[str, list] = {}
            for e in old:
                by_month.setdefault(_archive_name(e.get("date") or "0000-00"), []).append(e)
            for fname, rows in by_month.items():
                _append_archive(fname, rows)
                archives.append(fname)

        payload = {
            "updated": datetime.now(_SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "retention_days": RETENTION_DAYS,
            "entries": hot,
        }
        blob = json.dumps(payload, indent=1, default=str)
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            LOCAL_LEDGER.write_text(blob, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        try:
            from src.data import gdrive_uploader
            if gdrive_uploader.is_configured():
                gdrive_uploader.upload_or_replace(
                    LEDGER_FILENAME, blob, mime="application/json")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "appended": len(new_entries), "hot": len(hot),
                "rotated": len(old), "archives": archives}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def _append_archive(fname: str, rows: list[dict]) -> None:
    """Merge rows into a month archive on Drive (read-modify-write)."""
    existing: list[dict] = []
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(fname)
            if txt:
                d = json.loads(txt)
                existing = d.get("entries") or []
    except Exception:  # noqa: BLE001
        pass
    merged = existing + rows
    blob = json.dumps({"archived": datetime.now(_SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
                       "entries": merged}, indent=1, default=str)
    try:
        (OUTPUT_DIR / fname).write_text(blob, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(fname, blob, mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def status() -> dict:
    """Counts for the pipeline log / UI."""
    led = load()
    entries = led.get("entries") or []
    dates = sorted({e.get("date") for e in entries if e.get("date")})
    from collections import Counter
    return {
        "entries": len(entries),
        "days": len(dates),
        "from": dates[0] if dates else None,
        "to": dates[-1] if dates else None,
        "by_event": dict(Counter(e.get("event") for e in entries)),
        "updated": led.get("updated"),
    }
