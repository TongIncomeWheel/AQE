"""Tests for the order-flow / tape-reading PROXY (src/engines/order_flow.py)
-- a last-bar, volume-confirmed money-flow read. Explicitly a proxy: FMP's
daily panel carries no trade-by-trade or bid/ask data."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.order_flow import compute_order_flow


def _bars(last_high=101.0, last_low=99.0, last_close=100.0, last_vol=25_000.0,
         avg_vol=10_000.0) -> pd.DataFrame:
    n = 25
    dates = pd.bdate_range("2026-01-01", periods=n)
    highs = np.full(n, 101.0)
    lows = np.full(n, 99.0)
    closes = np.full(n, 100.0)
    vols = np.full(n, avg_vol)
    highs[-1], lows[-1], closes[-1], vols[-1] = last_high, last_low, last_close, last_vol
    return pd.DataFrame({"date": dates, "high": highs, "low": lows,
                         "close": closes, "volume": vols})


def test_aggressive_buy_needs_both_a_lopsided_close_and_confirming_volume():
    out = compute_order_flow(_bars(last_high=110.0, last_low=100.0,
                                   last_close=109.5, last_vol=25_000.0))
    assert out["of_state"] == "AGGRESSIVE_BUY"
    assert out["of_pressure"] == 0.9
    assert out["of_rvol"] == 2.5
    assert out["of_date"] is not None


def test_aggressive_sell_mirrors_the_buy_side():
    out = compute_order_flow(_bars(last_high=110.0, last_low=100.0,
                                   last_close=100.5, last_vol=25_000.0))
    assert out["of_state"] == "AGGRESSIVE_SELL"
    assert out["of_pressure"] == -0.9


def test_lopsided_close_on_weak_volume_is_none():
    out = compute_order_flow(_bars(last_high=110.0, last_low=100.0,
                                   last_close=109.5, last_vol=10_500.0))
    assert out["of_state"] == "NONE"
    assert out["of_date"] is None
    assert out["of_pressure"] == 0.9   # pressure still reported even when NONE


def test_centred_close_on_heavy_volume_is_none():
    out = compute_order_flow(_bars(last_high=110.0, last_low=100.0,
                                   last_close=105.0, last_vol=25_000.0))
    assert out["of_state"] == "NONE"


def test_too_few_bars_degrades_to_null():
    out = compute_order_flow(_bars().iloc[:5])
    assert out["of_state"] is None
    assert out["of_rvol"] is None


def test_none_input_degrades_to_null():
    out = compute_order_flow(None)
    assert out["of_state"] is None


def test_missing_required_column_degrades_to_null():
    out = compute_order_flow(_bars().drop(columns=["volume"]))
    assert out["of_state"] is None


def test_zero_range_bar_degrades_to_null_not_a_fabricated_reading():
    df = _bars()
    df.loc[df.index[-1], "high"] = df.loc[df.index[-1], "low"]
    out = compute_order_flow(df)
    assert out["of_state"] is None


def test_never_raises_on_malformed_values():
    df = _bars()
    df.loc[df.index[-1], "close"] = float("nan")
    out = compute_order_flow(df)  # must not raise
    assert "of_state" in out and "of_pressure" in out
