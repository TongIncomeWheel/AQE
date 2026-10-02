"""Tests for liquidity-sweep ("stop run") detection
(src/engines/liquidity_sweep.py) -- a wick through a confirmed prior pivot
that closes back on the other side. DETECT-layer, data only, never a gate."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.liquidity_sweep import compute_liquidity_sweep

_N = 30


def _base_frame():
    dates = pd.bdate_range("2026-01-01", periods=_N)
    base = 108.0 + 0.001 * np.arange(_N)   # tiny strictly-increasing drift,
                                            # avoids flat-series pivot ties
    highs = base + 2.0
    lows = base.copy()
    closes = base + 1.0
    vols = np.full(_N, 10_000.0)
    return dates, highs, lows, closes, vols


def _bullish_setup(last_low=95.0, last_close=101.0, last_vol=25_000.0) -> pd.DataFrame:
    dates, highs, lows, closes, vols = _base_frame()
    lows[10], highs[10], closes[10] = 100.0, 102.0, 101.0   # the confirmed pivot low
    lows[-1], highs[-1], closes[-1], vols[-1] = last_low, 102.0, last_close, last_vol
    return pd.DataFrame({"date": dates, "high": highs, "low": lows,
                         "close": closes, "volume": vols})


def _bearish_setup(last_high=125.0, last_close=119.0, last_vol=25_000.0) -> pd.DataFrame:
    dates, highs, lows, closes, vols = _base_frame()
    highs[10], lows[10], closes[10] = 120.0, 118.0, 119.0   # the confirmed pivot high
    highs[-1], lows[-1], closes[-1], vols[-1] = last_high, 118.5, last_close, last_vol
    return pd.DataFrame({"date": dates, "high": highs, "low": lows,
                         "close": closes, "volume": vols})


def test_bullish_sweep_wicks_below_the_pivot_low_and_closes_back_above():
    out = compute_liquidity_sweep(_bullish_setup())
    assert out["ls_state"] == "BULLISH_SWEEP"
    assert out["ls_level"] == 100.0
    assert out["ls_date"] is not None
    assert out["ls_volume_confirmed"] is True


def test_bearish_sweep_wicks_above_the_pivot_high_and_closes_back_below():
    out = compute_liquidity_sweep(_bearish_setup())
    assert out["ls_state"] == "BEARISH_SWEEP"
    assert out["ls_level"] == 120.0
    assert out["ls_volume_confirmed"] is True


def test_volume_confirmed_is_false_on_a_weak_volume_sweep():
    out = compute_liquidity_sweep(_bullish_setup(last_vol=9_000.0))
    assert out["ls_state"] == "BULLISH_SWEEP"
    assert out["ls_volume_confirmed"] is False


def test_a_wick_through_with_no_close_recovery_is_not_a_sweep():
    """Low wicks below the pivot but the close stays below it too -- a real
    breakdown continuation, not a rejected stop run."""
    out = compute_liquidity_sweep(_bullish_setup(last_close=98.0))
    assert out["ls_state"] == "NONE"


def test_no_wick_through_the_pivot_at_all_is_not_a_sweep():
    df = _bullish_setup(last_low=108.0, last_close=109.0)
    out = compute_liquidity_sweep(df)
    assert out["ls_state"] == "NONE"
    assert out["ls_level"] is None


def test_sweep_cannot_use_todays_own_bar_as_the_pivot():
    """The pivot scan excludes the last bar -- a sweep must break a PRIOR
    level, never one the same bar just created."""
    dates, highs, lows, closes, vols = _base_frame()
    # No prior pivot low exists anywhere; only today's bar dips.
    lows[-1], highs[-1], closes[-1], vols[-1] = 90.0, 102.0, 101.0, 25_000.0
    df = pd.DataFrame({"date": dates, "high": highs, "low": lows,
                       "close": closes, "volume": vols})
    out = compute_liquidity_sweep(df)
    assert out["ls_state"] == "NONE"


def test_too_few_bars_degrades_to_null():
    out = compute_liquidity_sweep(_bullish_setup().iloc[:10])
    assert out["ls_state"] is None


def test_none_input_degrades_to_null():
    out = compute_liquidity_sweep(None)
    assert out["ls_state"] is None


def test_missing_required_column_degrades_to_null():
    out = compute_liquidity_sweep(_bullish_setup().drop(columns=["volume"]))
    assert out["ls_state"] is None


def test_never_raises_on_malformed_values():
    df = _bullish_setup()
    df.loc[df.index[-1], "close"] = float("nan")
    out = compute_liquidity_sweep(df)  # must not raise
    assert "ls_state" in out and "ls_level" in out
