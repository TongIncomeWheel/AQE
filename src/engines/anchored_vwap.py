"""Anchored VWAP — volume-weighted average price run forward from a chosen
EVENT bar, not a rolling window (`vwap.py`'s 14D) and not the session open
(`src/alerts/live_measures.py`'s intraday `session_vwap`, built for the
~50-name D123 condition-watch set only).

Two anchors, both reusing AQE's existing single pivot/swing definition
(`src/scanner/levels.py`) rather than inventing a second one:

  * "structure" — the most recent CONFIRMED pivot high
    (`last_confirmed_pivot_high`), the same level `structure_shift` already
    measures a break against.
  * "swing"     — the up-swing's anchor low (`find_swing`), the same level
    the fib ladder and `structure_shift`'s BEARISH_CHOCH side already
    measure against.

Built from the daily EOD panel only — typical_price * volume, cumulative
from the anchor bar forward — so it runs for the full 600+ scan universe
every night with no new intraday pull and no new FMP call budget.
"""

from __future__ import annotations

import pandas as pd

from src.scanner.levels import PIVOT_K, find_swing, last_confirmed_pivot_high

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}

_NULL = {
    "avwap_structure": None, "avwap_structure_date": None,
    "avwap_structure_position": None, "avwap_structure_bars": None,
    "avwap_swing": None, "avwap_swing_date": None,
    "avwap_swing_position": None, "avwap_swing_bars": None,
}


def _anchored(daily: pd.DataFrame, anchor_idx: int) -> dict | None:
    """VWAP from `anchor_idx` (inclusive) through the last row. `None` when
    the segment carries no volume — a VWAP of zero volume is undefined, not
    zero."""
    seg = daily.iloc[anchor_idx:]
    volume = seg["volume"].astype(float)
    total_volume = float(volume.sum())
    if total_volume <= 0:
        return None
    typical = (seg["high"].astype(float) + seg["low"].astype(float)
              + seg["close"].astype(float)) / 3.0
    vwap_level = float((typical * volume).sum() / total_volume)
    last_close = float(seg["close"].astype(float).iloc[-1])
    return {"vwap": round(vwap_level, 2),
           "position": "ABOVE" if last_close >= vwap_level else "BELOW",
           "bars": int(len(seg))}


def compute_anchored_vwap(daily: pd.DataFrame) -> dict:
    """Both anchors as of the LAST closed bar of `daily` (ascending date
    order, full history). Never raises; a missing anchor (no confirmed pivot
    or swing yet — short history, no structure) degrades that anchor's four
    keys to None rather than dropping them, same discipline as
    `vwap.compute_vwap`'s null dict.
    """
    out = dict(_NULL)
    try:
        if daily is None or len(daily) < 2 * PIVOT_K + 1:
            return out
        if not _REQUIRED_COLS.issubset(daily.columns):
            return out

        highs = daily["high"].astype(float).to_numpy()
        lows = daily["low"].astype(float).to_numpy()
        dates = daily["date"].to_numpy()

        lph = last_confirmed_pivot_high(highs, dates)
        if lph is not None:
            idx = len(daily) - 1 - lph["bars_ago"]
            r = _anchored(daily, idx)
            if r is not None:
                out["avwap_structure"] = r["vwap"]
                out["avwap_structure_date"] = lph["date"]
                out["avwap_structure_position"] = r["position"]
                out["avwap_structure_bars"] = r["bars"]

        swing = find_swing(highs, lows)
        if swing is not None:
            r = _anchored(daily, int(swing["low_idx"]))
            if r is not None:
                out["avwap_swing"] = r["vwap"]
                out["avwap_swing_date"] = str(pd.Timestamp(dates[swing["low_idx"]]).date())
                out["avwap_swing_position"] = r["position"]
                out["avwap_swing_bars"] = r["bars"]
        return out
    except Exception:  # noqa: BLE001 — pure arithmetic read, never blocks the caller
        return dict(_NULL)
