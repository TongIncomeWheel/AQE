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


DAILY_HISTORY_DIR = PROJECT_ROOT / "aegis" / "output" / "alerts" / "daily_history"
DAILY_HISTORY_CALENDAR_DAYS = 400   # ~270 sessions: comfortably seeds EMA-26/13


def _prior_session(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _panel_history(tickers: list[str], today: date) -> dict[str, list[dict]]:
    """The nightly panel as a fast path -- ONLY when its last bar is the
    prior session or later. A panel that merely EXISTS proves nothing: the
    dev checkout's copy was a month stale when this was written, and
    CLAUDE.md's heartbeat incident is the same lesson (recency, not
    length). Anything older falls through to FMP."""
    try:
        import pandas as pd
        from src.data.paths import PANEL_DAILY
        if not PANEL_DAILY.exists():
            return {}
        pan = pd.read_parquet(PANEL_DAILY, columns=["ticker", "date", "open", "high",
                                                    "low", "close", "volume"])
        last = pd.to_datetime(pan["date"]).max()
        if last is None or last.date() < _prior_session(today):
            return {}
        want = set(tickers)
        out: dict[str, list[dict]] = {}
        for tk, g in pan[pan["ticker"].isin(want)].groupby("ticker"):
            g = g.sort_values("date")
            out[tk] = [{"date": str(pd.Timestamp(r.date).date()), "open": float(r.open),
                        "high": float(r.high), "low": float(r.low), "close": float(r.close),
                        "volume": float(r.volume)} for r in g.itertuples()]
        return out
    except Exception:  # noqa: BLE001
        return {}


def ensure_daily_history(client, tickers: list[str], today: date) -> dict[str, list[dict]]:
    """Daily OHLCV through the last completed session, per watched name,
    for the live Elder read (live_elder.py). Cached once per day like the
    volume profile: panel fast path when FRESH, else one FMP daily-bars
    pull per name on the first cycle, nothing network-wise after that.
    A failed pull caches an empty list (that name shows no live Elder
    today) rather than retrying every cycle."""
    date_str = today.isoformat()
    path = DAILY_HISTORY_DIR / f"{date_str}.json"
    cached: dict[str, list[dict]] = {}
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cached = data
    except Exception:  # noqa: BLE001
        cached = {}
    missing = [t for t in tickers if t not in cached]
    if not missing:
        return cached

    from_panel = _panel_history(missing, today)
    cached.update(from_panel)
    still = [t for t in missing if t not in cached]
    from_date = today - timedelta(days=DAILY_HISTORY_CALENDAR_DAYS)
    for tk in still:
        try:
            df = client.get_daily_bars(tk, from_date=from_date, to_date=_prior_session(today))
            cached[tk] = [{"date": str(r.date.date()), "open": float(r.open), "high": float(r.high),
                           "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
                          for r in df.itertuples()] if df is not None and len(df) else []
        except Exception:  # noqa: BLE001
            cached[tk] = []
    try:
        DAILY_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
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
