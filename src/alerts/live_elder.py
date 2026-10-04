"""Live (provisional) Elder Impulse for the 15-min condition cards -- PM ask
2026-10-04: "a live elder score (trend impulse factor) ... calculated as a
normalised score as this is intraday."

Elder is a pure function of the daily CLOSE series (engines/elder.py:
EMA-13 slope + MACD 12/26/9 histogram -- no volume, no range), so the
live read is the nightly formula run again with today's live price
standing in as today's close: "what Elder would print if the day closed
now." That is exactly how the indicator behaves on a live daily chart.
The 0-10 score is already the normalised form; nothing intraday needs
scaling because nothing in the formula depends on a partial day's volume
or range.

Provisional means provisional: the number moves with price until the
close, so the card shows it beside last night's exported `elder` and
labels it. Nothing here evaluates a PMA COB word -- `elder_ge`/`elder_le`
stay the committee's close-of-business judgment (handoff §5).
"""

from __future__ import annotations

import pandas as pd

from src.engines import elder as _elder

_COLS = ["date", "open", "high", "low", "close", "volume"]
MIN_BARS = 40            # MACD(26) + signal(9) + the 3-bar slope lag, with margin
HISTORY_BARS = 250       # one trading year: matches the nightly EMA seed closely


def provisional_frame(history: pd.DataFrame, live_price: float, today) -> pd.DataFrame:
    """`history` = daily bars through the LAST completed session (ascending).
    Appends today's bar with close = live price; if the history already
    ends on `today` (a panel refreshed intraday), that row's close is
    replaced instead of duplicated."""
    h = history[_COLS].copy() if set(_COLS).issubset(history.columns) else history.copy()
    h["date"] = pd.to_datetime(h["date"])
    today_ts = pd.Timestamp(today).normalize()
    if len(h) and h["date"].iloc[-1].normalize() == today_ts:
        h = h.iloc[:-1]
    last_close = float(h["close"].iloc[-1]) if len(h) else live_price
    row = {"date": today_ts, "open": last_close, "high": max(last_close, live_price),
           "low": min(last_close, live_price), "close": float(live_price), "volume": 0.0}
    return pd.concat([h, pd.DataFrame([row])], ignore_index=True)


def elder_live(history: pd.DataFrame | None, live_price: float | None, today) -> dict:
    """{elder_live, impulse_live, elder_prev, impulse_prev} -- None-filled
    (never raises) when history is too short or the price is missing.
    `elder_prev` is the score on the last COMPLETED session, recomputed
    from the same series so the two numbers are always comparable."""
    null = {"elder_live": None, "impulse_live": None, "elder_prev": None, "impulse_prev": None}
    try:
        if history is None or live_price is None or len(history) < MIN_BARS:
            return null
        frame = provisional_frame(history, float(live_price), today)
        out = _elder.compute(frame.tail(HISTORY_BARS + 1).reset_index(drop=True))
        s, st = out["elder_score"], out["impulse_state"]
        live_v, prev_v = s.iloc[-1], s.iloc[-2]
        if pd.isna(live_v):
            return null
        return {
            "elder_live": int(round(float(live_v))),
            "impulse_live": str(st.iloc[-1]),
            "elder_prev": (int(round(float(prev_v))) if not pd.isna(prev_v) else None),
            "impulse_prev": str(st.iloc[-2]) if len(st) > 1 else None,
        }
    except Exception:  # noqa: BLE001 -- a card line, never the cycle
        return null
