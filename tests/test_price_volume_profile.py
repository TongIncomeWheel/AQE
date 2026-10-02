"""Tests for the classic price-level volume profile
(src/engines/price_volume_profile.py) — POC + value area, approximated from
daily OHLCV (no intraday pull)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.price_volume_profile import compute_price_volume_profile


def _bars(highs, lows, closes, vols) -> pd.DataFrame:
    n = len(highs)
    dates = pd.bdate_range("2026-01-01", periods=n)
    return pd.DataFrame({"date": dates, "high": highs, "low": lows,
                         "close": closes, "volume": vols})


def _tight_range_with_outliers() -> pd.DataFrame:
    n = 60
    highs = np.full(n, 102.0)
    lows = np.full(n, 100.0)
    closes = np.full(n, 101.0)
    vols = np.full(n, 100_000.0)
    for i in (5, 15, 25):   # a few low-volume days trading far away
        highs[i], lows[i], closes[i], vols[i] = 122.0, 118.0, 120.0, 5_000.0
    return _bars(highs, lows, closes, vols)


def test_poc_lands_in_the_heavily_traded_range_not_the_low_volume_outliers():
    out = compute_price_volume_profile(_tight_range_with_outliers())
    assert 99.5 <= out["pvp_poc"] <= 102.5


def test_value_area_sits_inside_the_heavily_traded_range():
    out = compute_price_volume_profile(_tight_range_with_outliers())
    assert 99.5 <= out["pvp_val"] <= out["pvp_vah"] <= 102.5


def test_position_inside_when_last_close_sits_in_the_value_area():
    out = compute_price_volume_profile(_tight_range_with_outliers())
    assert out["pvp_position"] == "INSIDE_VALUE"


def test_position_above_value_on_a_fresh_breakout_close():
    df = _tight_range_with_outliers()
    df.loc[df.index[-1], "close"] = 130.0
    out = compute_price_volume_profile(df)
    assert out["pvp_position"] == "ABOVE_VALUE"


def test_position_below_value_on_a_fresh_breakdown_close():
    df = _tight_range_with_outliers()
    df.loc[df.index[-1], "close"] = 50.0
    out = compute_price_volume_profile(df)
    assert out["pvp_position"] == "BELOW_VALUE"


def test_bars_used_counts_only_valid_volume_bars():
    out = compute_price_volume_profile(_tight_range_with_outliers())
    assert out["pvp_bars_used"] == 60


def test_too_few_bars_degrades_to_null():
    out = compute_price_volume_profile(_tight_range_with_outliers().iloc[:3])
    assert out["pvp_poc"] is None
    assert out["pvp_bars_used"] is None


def test_none_input_degrades_to_null():
    out = compute_price_volume_profile(None)
    assert out["pvp_poc"] is None


def test_missing_required_column_degrades_to_null():
    out = compute_price_volume_profile(_tight_range_with_outliers().drop(columns=["volume"]))
    assert out["pvp_poc"] is None


def test_zero_volume_degrades_to_null_not_a_fabricated_level():
    df = _tight_range_with_outliers()
    df["volume"] = 0.0
    out = compute_price_volume_profile(df)
    assert out["pvp_poc"] is None


def test_lookback_window_is_configurable():
    df = _tight_range_with_outliers()
    out = compute_price_volume_profile(df, lookback=10)
    assert out["pvp_bars_used"] == 10


def test_heavier_volume_concentration_pulls_the_poc_toward_it():
    n = 40
    highs = np.full(n, 110.0)
    lows = np.full(n, 90.0)
    closes = np.full(n, 100.0)
    vols = np.full(n, 1000.0)
    # Make the back half of the window trade in a tight, heavy pocket near 108.
    highs[20:], lows[20:], closes[20:], vols[20:] = 109.0, 107.0, 108.0, 50_000.0
    out = compute_price_volume_profile(_bars(highs, lows, closes, vols))
    assert out["pvp_poc"] > 104.0


def test_never_raises_on_malformed_values():
    df = _tight_range_with_outliers()
    df.loc[df.index[-1], "close"] = float("nan")
    out = compute_price_volume_profile(df)  # must not raise
    assert "pvp_poc" in out and "pvp_position" in out
