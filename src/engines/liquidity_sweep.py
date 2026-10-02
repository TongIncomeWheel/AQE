"""Liquidity sweep ("stop run") detection — a DETECT-layer addition, data
only, never a gate and never sizing (CLAUDE.md's rule for this whole layer).

A sweep is a wick that pokes through a prior CONFIRMED pivot — where stops
cluster — and then closes back on the other side the same bar, the classic
signature of liquidity being taken before the real move. Reuses AQE's single
pivot definition (`src/scanner/levels.py`'s 11-bar fractal, PIVOT_K=5) via
`last_confirmed_pivot_high`/`last_confirmed_pivot_low` rather than inventing
a second one — the same discipline `structure_shift` and the fib ladder
already follow.

  BULLISH_SWEEP: today's LOW wicks below the most recent confirmed pivot
                 low, but today's CLOSE recovers back above it.
  BEARISH_SWEEP: today's HIGH wicks above the most recent confirmed pivot
                 high, but today's CLOSE falls back below it.
  NONE:          neither.

Volume confirmation (today's volume vs its own trailing 20-bar average) is
reported alongside, never gating the state itself — the same pattern
`squeeze_breakout_volume_confirmed` uses: an unconfirmed sweep stays visible,
just flagged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.scanner.levels import (PIVOT_K, last_confirmed_pivot_high,
                                last_confirmed_pivot_low)

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}
LS_RVOL_WINDOW = 20

_NULL = {"ls_state": None, "ls_level": None, "ls_date": None,
        "ls_volume_confirmed": None}


def compute_liquidity_sweep(daily: pd.DataFrame) -> dict:
    """BULLISH_SWEEP / BEARISH_SWEEP / NONE on the LAST closed bar.

    Returns (always present, never raises):
        ls_state: "BULLISH_SWEEP" | "BEARISH_SWEEP" | "NONE" | None.
        ls_level: the swept pivot's price, or None when ls_state=NONE.
        ls_date: date of the sweep bar, or None when ls_state=NONE.
        ls_volume_confirmed: True if the sweep bar's volume cleared its own
            20-bar average, None when ls_state=NONE or volume is unusable.
    """
    try:
        min_bars = max(2 * PIVOT_K + 1, LS_RVOL_WINDOW + 1)
        if daily is None or len(daily) < min_bars:
            return dict(_NULL)
        if not _REQUIRED_COLS.issubset(daily.columns):
            return dict(_NULL)

        high = daily["high"].astype(float).to_numpy()
        low = daily["low"].astype(float).to_numpy()
        close = daily["close"].astype(float).to_numpy()
        volume = daily["volume"].astype(float).to_numpy()
        dates = daily["date"].to_numpy()

        h, l, c = high[-1], low[-1], close[-1]
        if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(c)):
            return dict(_NULL)

        def _volume_confirmed() -> bool | None:
            avg_vol = float(np.mean(volume[-(LS_RVOL_WINDOW + 1):-1]))
            if not (np.isfinite(avg_vol) and avg_vol > 0 and np.isfinite(volume[-1])):
                return None
            return bool(volume[-1] > avg_vol)

        # BULLISH: today's low swept below a prior confirmed pivot low, but
        # the close recovered back above it. Scanned on the bars BEFORE
        # today so a sweep can never "discover" itself as its own pivot.
        pl = last_confirmed_pivot_low(low[:-1], dates[:-1])
        if pl is not None and l < pl["price"] < c:
            return {"ls_state": "BULLISH_SWEEP", "ls_level": pl["price"],
                    "ls_date": str(pd.Timestamp(dates[-1]).date()),
                    "ls_volume_confirmed": _volume_confirmed()}

        # BEARISH: today's high swept above a prior confirmed pivot high,
        # but the close fell back below it.
        ph = last_confirmed_pivot_high(high[:-1], dates[:-1])
        if ph is not None and h > ph["price"] > c:
            return {"ls_state": "BEARISH_SWEEP", "ls_level": ph["price"],
                    "ls_date": str(pd.Timestamp(dates[-1]).date()),
                    "ls_volume_confirmed": _volume_confirmed()}

        return {"ls_state": "NONE", "ls_level": None, "ls_date": None,
                "ls_volume_confirmed": None}
    except Exception:  # noqa: BLE001 — pure arithmetic read, never blocks the caller
        return dict(_NULL)
