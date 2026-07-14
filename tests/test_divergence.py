"""Tests for src/engines/divergence.py — regular divergence detector.

All frames are synthetic, in-memory OHLCV constructions (no files, no
network). Bars are built as degenerate candles (open == high == low ==
close) so the engineered price path directly controls both the pivot-low
series (`low`) and the pivot-high series (`high`) without extra noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import divergence as DIV


def _df(prices, volumes=None, start: str = "2024-01-01") -> pd.DataFrame:
    """Build a single-ticker OHLCV frame from a bar-by-bar price path."""
    prices = np.asarray(prices, dtype=float)
    n = len(prices)
    dates = pd.bdate_range(start, periods=n)
    if volumes is None:
        volumes = np.full(n, 1_000_000.0)
    else:
        volumes = np.asarray(volumes, dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        }
    )


def _bullish_leg_prices() -> np.ndarray:
    """Engineered REGULAR BULLISH divergence path.

    Wave shape (all indices below refer to positions in the concatenated
    array):
      - idx 0-9   warmup uptrend 100 -> 110 (RSI warmup room).
      - idx 10-19 STEEP decline 110 -> 70: trough A at idx 19 (confirmed
        pivot low; the fast, large-step decline drives RSI deeply oversold).
      - idx 20-33 sharp rally 70 -> 140 (confirms pivot A + resets momentum).
      - idx 34-54 GRADUAL decline 140 -> 68: trough B at idx 53, a LOWER
        low than A (68 < 70), but spread over twice as many bars so the
        gain/loss mix feeding RSI(14) at B is materially less oversold
        than at A -> RSI[B] > RSI[A] while price[B] < price[A].
      - idx 55-63 rally 68 -> 90, confirming pivot B (5 bars right side).

    Pivot lows land at 19 and 53 (span 34, inside [min_span, max_span]);
    p2=53 sits within `fresh_bars(10) + pivot_right(5) = 15` bars of the
    last bar (idx 63), so the divergence is fresh.
    """
    seg1 = np.linspace(100, 110, 10)
    seg2 = np.linspace(110, 70, 10)
    seg3 = np.linspace(70, 140, 14)[1:]
    seg4 = np.linspace(140, 68, 22)[1:]
    seg5 = np.linspace(68, 90, 11)[1:]
    return np.concatenate([seg1, seg2, seg3, seg4, seg5])


def _bearish_leg_prices() -> np.ndarray:
    """Mirror of `_bullish_leg_prices()` (reflected about 105) -> REGULAR
    BEARISH divergence: price makes a HIGHER high while momentum makes a
    LOWER high (mirrors the bullish "lower low / higher-momentum-low" case).
    """
    return 210.0 - _bullish_leg_prices()


def test_bullish_divergence_detected():
    df = _df(_bullish_leg_prices())
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "BULLISH"
    assert res["div_bull_count"] >= 1
    assert res["div_bear_count"] == 0
    assert "rsi" in res["div_oscs"]
    assert res["div_date"] is not None


def test_bearish_divergence_detected():
    df = _df(_bearish_leg_prices())
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "BEARISH"
    assert res["div_bear_count"] >= 1
    assert res["div_bull_count"] == 0
    assert "-rsi" in res["div_oscs"]
    assert res["div_date"] is not None


def test_clean_uptrend_no_divergence():
    # Steady uptrend with small sub-threshold wiggle, never makes a lower
    # low -> the bullish leg can never fire; nothing else can either.
    idx = np.arange(80)
    prices = 100 + idx * 1.0 + 0.3 * np.sin(idx * 0.9)
    df = _df(prices)
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "NONE"
    assert res["div_bull_count"] == 0
    assert res["div_bear_count"] == 0
    assert res["div_oscs"] is None
    assert res["div_date"] is None


def test_short_data_returns_none_never_raises():
    df = _df(np.linspace(100, 110, 30))  # < 40 bars
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "NONE"
    assert res["div_bull_count"] == 0
    assert res["div_bear_count"] == 0
    assert res["div_oscs"] is None
    assert res["div_date"] is None


def test_stale_divergence_ages_out():
    # Same bullish construction, but padded with ~45 perfectly flat bars
    # after pivot B so p2 falls outside fresh_bars + pivot_right of the
    # last bar. A flat pad can't itself form a new strict pivot, so the
    # only candidate divergence is the now-stale one -> NONE.
    prices = np.concatenate([_bullish_leg_prices(), np.full(45, 90.0)])
    df = _df(prices)
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "NONE"
    assert res["div_bull_count"] == 0
    assert res["div_bear_count"] == 0
    assert res["div_oscs"] is None
    assert res["div_date"] is None


def test_malformed_input_missing_volume_column():
    df = _df(_bullish_leg_prices()).drop(columns=["volume"])
    res = DIV.compute_divergence(df)
    assert res["div_state"] == "NONE"
    assert res["div_bull_count"] == 0
    assert res["div_bear_count"] == 0
    assert res["div_oscs"] is None
    assert res["div_date"] is None


def test_none_input_never_raises():
    res = DIV.compute_divergence(None)
    assert res["div_state"] == "NONE"


def test_empty_dataframe_never_raises():
    res = DIV.compute_divergence(pd.DataFrame())
    assert res["div_state"] == "NONE"


@pytest.mark.parametrize("field", ["div_state", "div_bull_count", "div_bear_count", "div_oscs", "div_date"])
def test_return_shape_has_exact_keys(field):
    df = _df(_bullish_leg_prices())
    res = DIV.compute_divergence(df)
    assert set(res.keys()) == {"div_state", "div_bull_count", "div_bear_count", "div_oscs", "div_date"}
    assert field in res
