"""Tests for `last_confirmed_pivot_low` (src/scanner/levels.py) -- the LOW
mirror of `last_confirmed_pivot_high`, built for liquidity-sweep detection
(engines/liquidity_sweep.py), which needs the most recent confirmed pivot low
on EITHER side of price, not `recent_pivot_lows()`'s below-close filter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.scanner.levels import last_confirmed_pivot_low


def _breakdown_bars():
    """Decline -> confirmed pivot low at 10 -> bounce -> break down below it."""
    lows = np.array([20, 19, 18, 17, 16, 10, 16, 17, 18, 17, 16,
                     15, 14, 13, 12, 11, 9, 8], dtype=float)
    dates = pd.bdate_range("2026-01-01", periods=len(lows)).to_numpy()
    return lows, dates


def test_last_pivot_low_is_selected_by_recency_not_by_side():
    lows, dates = _breakdown_bars()
    plp = last_confirmed_pivot_low(lows, dates, k=5, window=250)
    assert plp is not None
    assert plp["price"] == 10.0          # the confirmed pivot, not the running low
    assert plp["bars_ago"] > 0


def test_none_when_too_few_bars():
    lows, dates = _breakdown_bars()
    assert last_confirmed_pivot_low(lows[:5], dates[:5]) is None


def test_none_when_no_fractal_pivot_exists():
    """Strictly declining lows: the true local min of any window is always
    its RIGHT edge, never the centre, so no fractal pivot confirms."""
    n = 20
    lows = np.array([200.0 - i for i in range(n)])
    dates = pd.bdate_range("2026-01-01", periods=n).to_numpy()
    assert last_confirmed_pivot_low(lows, dates) is None


def test_date_and_bars_ago_are_reported():
    lows, dates = _breakdown_bars()
    plp = last_confirmed_pivot_low(lows, dates, k=5, window=250)
    assert plp["date"] == str(pd.Timestamp(dates[5]).date())
    assert plp["bars_ago"] == len(lows) - 1 - 5
