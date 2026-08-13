"""Rolling daily-bar VWAP — a longer-horizon companion to elder_context's
5-day HOURLY vwap_5d.

vwap_5d (elder_context.py) is an intraday-anchored VWAP built from hourly
bars, used for Elder-impulse exhaustion checks over a short window. This is
a different instrument: a rolling VWAP over `length` daily bars (default
14), the standard volume-weighted price anchor traders mean by "14D VWAP" —
built from the same EOD panel every other AQE engine reads, no intraday
feed required. Two VWAPs, two horizons, two purposes — not a duplicate.
"""

from __future__ import annotations

import pandas as pd

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}


def compute_vwap(daily: pd.DataFrame, *, length: int = 14) -> dict:
    """Rolling `length`-bar VWAP as of the LAST closed bar of `daily`.

    typical_price = (high + low + close) / 3, Pine's `hlc3`.
    vwap = sum(typical_price * volume, length) / sum(volume, length).

    Returns (always present, never raises):
        vwap_{length}d: the VWAP level, or None if too few bars / no volume.
        vwap_{length}d_position: "ABOVE" | "BELOW" — last close vs that VWAP.
    """
    key_val, key_pos = f"vwap_{length}d", f"vwap_{length}d_position"
    null = {key_val: None, key_pos: None}
    try:
        if daily is None or len(daily) < length:
            return null
        if not _REQUIRED_COLS.issubset(daily.columns):
            return null

        d = daily.tail(length)
        high = d["high"].astype(float)
        low = d["low"].astype(float)
        close = d["close"].astype(float)
        volume = d["volume"].astype(float)

        typical = (high + low + close) / 3.0
        total_volume = float(volume.sum())
        if total_volume <= 0:
            return null

        vwap_level = float((typical * volume).sum() / total_volume)
        last_close = float(close.iloc[-1])
        return {
            key_val: round(vwap_level, 2),
            key_pos: "ABOVE" if last_close >= vwap_level else "BELOW",
        }
    except Exception:  # noqa: BLE001 — pure arithmetic read, never blocks the caller
        return null
