"""EMA8 / EMA20 figures for the 15-min condition cards -- PM ask 2026-10-06
("I want to see figures around EMA8 and EMA20; I think these give a very
good reference intraday").

FIGURES ONLY. No condition, gate or state is built on them here: the
technique the PM referred to (UMR) has rules AQE was never given, so this
module reports where price sits against the two averages and which way they
point, and nothing more. They never evaluate a committee word, never reach
`buy_met`, never size anything.

Two timeframes, each a plain standard EMA (span n, recursive, seeded from
the first value -- how a charting package draws it):

  * 15-min  -- the intraday reference. Closes of the last ~200 regular-session
               15-min bars of PRIOR sessions (a once-a-morning cache, built
               from the same pull the volume profile already makes) plus
               today's bars every cycle. The averages run continuously across
               the overnight gap, as on a continuous intraday chart.
  * daily   -- closes through the last completed session, with the live price
               standing in as today's close (the same provisional convention
               live_elder.py uses).

A read needs enough bars for the EMA to have settled; short history returns
None for that timeframe rather than a number built on a cold start.
"""

from __future__ import annotations

import pandas as pd

from . import live_measures as LM
from . import condition_spec as S

FAST, SLOW = 8, 20
MIN_BARS_15M = 60          # three times the slow span: the EMA has settled
MIN_BARS_DAILY = 60
SLOPE_LOOKBACK = 3         # bars back used to call an average rising/falling


def session_closes(bars: list[dict], before_date: str | None = None) -> list[float]:
    """Closes of regular-session bars, oldest first. `before_date` (YYYY-MM-DD)
    keeps only bars strictly before that day -- the warm-up seed excludes
    today, whose bars arrive fresh every cycle."""
    rows = []
    for b in bars or []:
        dt = LM._parse_bar_dt(b)
        if dt is None:
            continue
        mins = dt.hour * 60 + dt.minute
        if mins < S.SESSION_OPEN_MIN or mins >= S.SESSION_CLOSE_MIN:
            continue
        if before_date and dt.date().isoformat() >= before_date:
            continue
        c = LM._f(b.get("close"))
        if c is not None:
            rows.append((dt, c))
    rows.sort(key=lambda r: r[0])
    return [c for _, c in rows]


def _slope(series: pd.Series) -> str:
    if len(series) <= SLOPE_LOOKBACK:
        return "flat"
    d = float(series.iloc[-1]) - float(series.iloc[-1 - SLOPE_LOOKBACK])
    return "rising" if d > 0 else ("falling" if d < 0 else "flat")


def read(closes: list[float], price: float | None, min_bars: int) -> dict | None:
    """{ema8, ema20, spot_vs_8_pct, spot_vs_20_pct, stack, slope8, slope20,
    n_bars} -- or None when there is too little history or no price."""
    if price is None or price <= 0 or len(closes) < min_bars:
        return None
    s = pd.Series([float(c) for c in closes])
    e8 = s.ewm(span=FAST, adjust=False).mean()
    e20 = s.ewm(span=SLOW, adjust=False).mean()
    a, b = float(e8.iloc[-1]), float(e20.iloc[-1])
    if a <= 0 or b <= 0:
        return None
    return {
        "ema8": round(a, 2), "ema20": round(b, 2),
        "spot_vs_8_pct": round((price / a - 1.0) * 100.0, 2),
        "spot_vs_20_pct": round((price / b - 1.0) * 100.0, 2),
        "stack": "above" if a > b else ("below" if a < b else "equal"),
        "slope8": _slope(e8), "slope20": _slope(e20),
        "n_bars": len(s),
    }


def build(seed_closes: list[float] | None, today_bars: list[dict] | None,
          daily_history: list[dict] | None, price: float | None) -> dict:
    """{"m15": read|None, "daily": read|None}. Never raises."""
    out = {"m15": None, "daily": None}
    try:
        intra = list(seed_closes or []) + session_closes(today_bars or [])
        out["m15"] = read(intra, price, MIN_BARS_15M)
    except Exception:  # noqa: BLE001 -- a card line, never the cycle
        pass
    try:
        dc = [float(r["close"]) for r in (daily_history or []) if r.get("close") is not None]
        if price is not None:
            dc = dc + [float(price)]
        out["daily"] = read(dc, price, MIN_BARS_DAILY)
    except Exception:  # noqa: BLE001
        pass
    return out
