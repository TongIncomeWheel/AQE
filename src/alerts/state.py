"""Shared alert dedup state — one trigger fires at most once per trading day.

Both pollers (the in-app 15-min thread and the GitHub Actions backstop) read and
write the SAME state object so they don't double-email. Source of truth is a tiny
JSON on Drive (`aqe_alert_state.json` in the AQE folder); a local mirror in
`output/` is kept for offline/dev. last-writer-wins — at a 15-min cadence with the
two pollers offset, a collision can at worst send one duplicate, never miss one.

State shape: {"date": "YYYY-MM-DD" (US/Eastern), "fired": ["TICKER|LEVEL", ...]}.
On a new trading day the fired set resets automatically.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR

STATE_FILENAME = "aqe_alert_state.json"
LOCAL_STATE = OUTPUT_DIR / STATE_FILENAME
_ET = ZoneInfo("America/New_York")


def today_key() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def fired_key(ticker: str, level: str) -> str:
    return f"{ticker}|{level}"


def load_alert_state() -> dict:
    """Load the shared state — Drive first, then local mirror, then empty."""
    # Drive (shared source of truth)
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(STATE_FILENAME)
            if txt:
                return _ensure_today(json.loads(txt))
    except Exception:  # noqa: BLE001
        pass
    # Local mirror
    try:
        if LOCAL_STATE.exists():
            return _ensure_today(json.loads(LOCAL_STATE.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        pass
    return {"date": today_key(), "fired": []}


def save_alert_state(state: dict) -> None:
    """Persist to local mirror + Drive (both best-effort)."""
    payload = json.dumps(state, indent=2)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_STATE.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(STATE_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def _ensure_today(state: dict) -> dict:
    """Reset the fired set when the trading day rolls over."""
    if not isinstance(state, dict):
        return {"date": today_key(), "fired": []}
    if state.get("date") != today_key():
        return {"date": today_key(), "fired": []}
    state.setdefault("fired", [])
    return state


def is_fired(state: dict, ticker: str, level: str) -> bool:
    return fired_key(ticker, level) in set(state.get("fired") or [])


def mark_fired(state: dict, ticker: str, level: str) -> None:
    k = fired_key(ticker, level)
    if k not in (state.get("fired") or []):
        state.setdefault("fired", []).append(k)
