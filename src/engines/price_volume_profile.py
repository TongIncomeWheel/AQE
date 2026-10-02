"""Classic volume profile — volume-by-PRICE (not by time-of-day), with a
Point of Control and Value Area. Distinct from two other things in this
codebase that could be mistaken for it:

  * `vol_profile.py` ("Volatility Profile") — a per-ticker historical-
    simulation target/stop corridor. Nothing to do with price buckets.
  * `src/alerts/live_measures.py::volume_profile()` — a TIME-OF-DAY profile
    (is 10:30am volume normal for 10:30am), built from 15-min bars for the
    ~50-name D123 condition-watch set only.

This module answers a different question: over the last `lookback` daily
bars, which PRICE levels did the heaviest volume trade at? Built from the
daily EOD panel alone (no intraday pull), so it runs for the full 600+ scan
universe nightly.

Method — the standard daily-bar approximation (true tick-level volume-by-
price needs intraday data this engine deliberately does not require): each
day's volume is split across a price grid spanning the lookback's [low, high],
weighted by a TRIANGULAR kernel peaking at that day's own typical price
(high+low+close)/3 and falling to zero at that day's own high/low — more
volume is assumed to trade near the day's typical price than at its extremes,
which a flat (uniform) split across the day's range would not capture.

Point of Control (POC) = the bin carrying the most volume. Value Area (VA) =
the narrowest band of bins, grown outward from the POC one side at a time
(always extending into whichever neighbour carries more volume), that holds
`value_area_pct` (70% by convention) of the lookback's total volume.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}

DEFAULT_LOOKBACK = 60          # sessions — roughly one quarter
DEFAULT_N_BINS = 24            # price buckets across the lookback's range
DEFAULT_VALUE_AREA_PCT = 0.70  # the conventional value-area share

_NULL = {
    "pvp_poc": None, "pvp_vah": None, "pvp_val": None,
    "pvp_position": None, "pvp_bars_used": None,
}


def _day_weights(low: float, high: float, close: float,
                 bin_edges: np.ndarray) -> np.ndarray:
    """Triangular weight of each bin (by its midpoint) for one day's range,
    peaking at that day's typical price. Zero outside [low, high]."""
    mids = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    tp = (high + low + close) / 3.0
    tp = min(max(tp, low), high)          # guard float dust at the edges

    w = np.zeros_like(mids)
    in_range = (mids >= low) & (mids <= high)
    if not in_range.any():
        return w

    left = tp - low
    right = high - tp
    for i in np.flatnonzero(in_range):
        m = mids[i]
        if m <= tp:
            w[i] = 1.0 if left <= 0 else (m - low) / left
        else:
            w[i] = 1.0 if right <= 0 else (high - m) / right
    total = w.sum()
    if total <= 0:
        # Degenerate day (e.g. high==low==close) — spread flat across the
        # bins the range touches rather than drop the day's volume entirely.
        w[in_range] = 1.0
        total = w.sum()
    return w / total


def _value_area(volumes: np.ndarray, poc_idx: int, target_pct: float) -> tuple[int, int]:
    """Grow outward from the POC bin, always taking the heavier neighbour,
    until the covered volume reaches `target_pct` of the total. Returns
    (lo_idx, hi_idx) inclusive."""
    total = float(volumes.sum())
    target = total * target_pct
    lo, hi = poc_idx, poc_idx
    covered = float(volumes[poc_idx])
    n = len(volumes)
    while covered < target and (lo > 0 or hi < n - 1):
        left_vol = volumes[lo - 1] if lo > 0 else -1.0
        right_vol = volumes[hi + 1] if hi < n - 1 else -1.0
        if left_vol >= right_vol:
            lo -= 1
            covered += left_vol
        else:
            hi += 1
            covered += right_vol
    return lo, hi


def compute_price_volume_profile(
    daily: pd.DataFrame, *,
    lookback: int = DEFAULT_LOOKBACK,
    n_bins: int = DEFAULT_N_BINS,
    value_area_pct: float = DEFAULT_VALUE_AREA_PCT,
) -> dict:
    """POC / value-area-high / value-area-low over the trailing `lookback`
    daily bars, plus the last close's position relative to the value area.

    Returns (always present, never raises):
        pvp_poc: the point-of-control price level, or None.
        pvp_vah / pvp_val: value-area high/low, or None.
        pvp_position: "ABOVE_VALUE" | "INSIDE_VALUE" | "BELOW_VALUE" | None.
        pvp_bars_used: how many of the trailing bars actually had volume.
    """
    try:
        if daily is None or len(daily) < 5:
            return dict(_NULL)
        if not _REQUIRED_COLS.issubset(daily.columns):
            return dict(_NULL)

        d = daily.tail(lookback)
        high = d["high"].astype(float).to_numpy()
        low = d["low"].astype(float).to_numpy()
        close = d["close"].astype(float).to_numpy()
        volume = d["volume"].astype(float).to_numpy()

        valid = (volume > 0) & np.isfinite(high) & np.isfinite(low) & (high >= low)
        if not valid.any():
            return dict(_NULL)
        high, low, close, volume = high[valid], low[valid], close[valid], volume[valid]

        grid_lo, grid_hi = float(low.min()), float(high.max())
        if grid_hi <= grid_lo:
            return dict(_NULL)
        bin_edges = np.linspace(grid_lo, grid_hi, n_bins + 1)
        bin_mids = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        bins_vol = np.zeros(n_bins)
        for h, l, c, v in zip(high, low, close, volume):
            bins_vol += _day_weights(l, h, c, bin_edges) * v

        total_vol = float(bins_vol.sum())
        if total_vol <= 0:
            return dict(_NULL)

        poc_idx = int(np.argmax(bins_vol))
        lo_idx, hi_idx = _value_area(bins_vol, poc_idx, value_area_pct)

        last_close = float(close[-1])
        val, vah = float(bin_edges[lo_idx]), float(bin_edges[hi_idx + 1])
        position = ("ABOVE_VALUE" if last_close > vah else
                    "BELOW_VALUE" if last_close < val else "INSIDE_VALUE")

        return {
            "pvp_poc": round(float(bin_mids[poc_idx]), 2),
            "pvp_vah": round(vah, 2),
            "pvp_val": round(val, 2),
            "pvp_position": position,
            "pvp_bars_used": int(valid.sum()),
        }
    except Exception:  # noqa: BLE001 — pure arithmetic read, never blocks the caller
        return dict(_NULL)
