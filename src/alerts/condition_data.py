"""AQE handoff D123/R21 (2026-10-02) §3/§4.1 — the new FMP intraday pulls
this build needs, and the per-day volume-profile cache that keeps the
20-session history pull to once per morning rather than once per cycle.

Only for names in today's `pma_levels.json` carrying a `conditions` block
(~50 names per the handoff) — this never touches the broader monitored
universe the existing trigger path already polls.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.data.paths import PROJECT_ROOT

VOLUME_PROFILE_DIR = PROJECT_ROOT / "aegis" / "output" / "alerts" / "volume_profile"
PROFILE_HISTORY_CALENDAR_DAYS = 30  # covers the last 20 trading sessions


def _cache_path(date_str: str) -> Path:
    return VOLUME_PROFILE_DIR / f"{date_str}.json"


def load_cached_profiles(date_str: str) -> dict[str, dict[int, float]]:
    """{ticker: {slot_index: avg_volume}} — local file only (this is a
    same-day scratch cache, rebuilt fresh every morning; no Drive sync
    needed since nothing reads it across container restarts)."""
    path = _cache_path(date_str)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {tk: {int(k): v for k, v in (prof or {}).items()}
               for tk, prof in data.items()}
    except Exception:  # noqa: BLE001
        return {}


def save_cached_profiles(date_str: str, profiles: dict[str, dict[int, float]]) -> None:
    try:
        VOLUME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(date_str).write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def ensure_volume_profiles(client, tickers: list[str], today: date) -> dict[str, dict[int, float]]:
    """§4.1: "cache it per ticker per day... so it is built once." Pulls
    20-session 15-min bars ONLY for tickers missing from today's cache —
    the common case on every cycle after the first is a no-op network-wise.
    A ticker whose pull fails caches an empty profile for today rather
    than retrying every cycle (a thin/new-to-the-book name degrades to
    "no vol_x reading today", not a repeated failing call)."""
    from . import live_measures as LM

    date_str = today.isoformat()
    cached = load_cached_profiles(date_str)
    missing = [t for t in tickers if t not in cached]
    if not missing:
        return cached

    from_date = today - timedelta(days=PROFILE_HISTORY_CALENDAR_DAYS)
    changed = False
    for tk in missing:
        try:
            bars = client.get_intraday_bars(tk, interval="15min",
                                            from_date=from_date, to_date=today)
        except Exception:  # noqa: BLE001
            bars = []
        cached[tk] = LM.volume_profile(bars or [])
        changed = True
    if changed:
        save_cached_profiles(date_str, cached)
    return cached


def fetch_today_bars(client, ticker: str, today: date) -> list[dict]:
    """§3: today's 15-min bars, every cycle. Empty list (never raises) on
    any fetch failure — the caller's NOT_YET discipline already handles a
    missing read correctly."""
    try:
        return client.get_intraday_bars(ticker, interval="15min",
                                        from_date=today, to_date=today) or []
    except Exception:  # noqa: BLE001
        return []
