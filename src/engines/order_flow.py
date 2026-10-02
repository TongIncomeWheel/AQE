"""Order-flow / tape-reading PROXY — the closest reading AQE's OHLCV daily
panel can honestly give to "was there aggressive directional buying or
selling today." This is explicitly a proxy, never real tape data: FMP's feed
carries no trade-by-trade prints and no bid/ask, so there is no real order
flow to read. Genuine tape reading needs that data and is NOT what this
module claims to produce.

Distinct from `flow.py`'s existing CMF/MFI (a SMOOTHED 10-bar money-flow
average feeding the scored Flow composite): this is a LAST-BAR categorical
read requiring BOTH directional conviction AND volume confirmation, in the
same family as `squeeze_breakout_state`/`pin_bar_state` — an event on today's
bar, not a trend over several.

Money-flow multiplier (Chaikin's own formula, the root CMF is built on):

    mfm = ((close - low) - (high - close)) / (high - low)   in [-1, 1]

+1 = closed at the bar's high (maximal buy-side pressure in the bar's own
range), -1 = closed at the low. AGGRESSIVE_BUY/SELL additionally requires
today's volume to clear its own 20-bar average by `OF_RVOL_MIN` — a lopsided
close on thin volume is drift, not conviction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}

OF_PRESSURE_THRESHOLD = 0.6   # |mfm| at/above this = a lopsided close
OF_RVOL_WINDOW = 20
OF_RVOL_MIN = 1.5             # volume must clear 1.5x its own 20-bar average

_NULL = {"of_state": None, "of_pressure": None, "of_date": None, "of_rvol": None}


def compute_order_flow(daily: pd.DataFrame) -> dict:
    """AGGRESSIVE_BUY / AGGRESSIVE_SELL / NONE on the LAST closed bar, plus
    the raw pressure (-1..1) and volume-vs-average ratio behind it.

    Returns (always present, never raises):
        of_state: "AGGRESSIVE_BUY" | "AGGRESSIVE_SELL" | "NONE" | None.
        of_pressure: the last bar's money-flow multiplier, -1..1, or None.
        of_date: date of the last bar when of_state != NONE, else None.
        of_rvol: last bar's volume / its own trailing 20-bar average, or None.
    """
    try:
        if daily is None or len(daily) < OF_RVOL_WINDOW + 1:
            return dict(_NULL)
        if not _REQUIRED_COLS.issubset(daily.columns):
            return dict(_NULL)

        high = daily["high"].astype(float).to_numpy()
        low = daily["low"].astype(float).to_numpy()
        close = daily["close"].astype(float).to_numpy()
        volume = daily["volume"].astype(float).to_numpy()

        h, l, c, v = high[-1], low[-1], close[-1], volume[-1]
        if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(c) and h > l):
            return dict(_NULL)

        pressure = float(((c - l) - (h - c)) / (h - l))

        avg_vol = float(np.mean(volume[-(OF_RVOL_WINDOW + 1):-1]))
        if not (np.isfinite(avg_vol) and avg_vol > 0):
            return dict(_NULL)
        rvol = float(v) / avg_vol

        if pressure >= OF_PRESSURE_THRESHOLD and rvol >= OF_RVOL_MIN:
            state = "AGGRESSIVE_BUY"
        elif pressure <= -OF_PRESSURE_THRESHOLD and rvol >= OF_RVOL_MIN:
            state = "AGGRESSIVE_SELL"
        else:
            state = "NONE"

        return {
            "of_state": state,
            "of_pressure": round(pressure, 4),
            "of_date": (str(pd.Timestamp(daily["date"].to_numpy()[-1]).date())
                       if state != "NONE" else None),
            "of_rvol": round(rvol, 2),
        }
    except Exception:  # noqa: BLE001 — pure arithmetic read, never blocks the caller
        return dict(_NULL)
