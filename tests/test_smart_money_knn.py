"""Tests for the Smart-Money CHoCH + kNN engine (src/engines/smart_money_knn.py).

All synthetic OHLCV — no network, no files. Small swing_len/lookahead/
window_len kwargs are used so short synthetic series exercise real CHoCH
event pools; the engine's core logic is never adjusted to make a test pass
— only the synthetic price shapes are tuned.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.smart_money_knn import compute_smart_money

_NULL = {
    "choch_state": "NONE",
    "choch_date": None,
    "knn_prob": None,
    "knn_significant": False,
    "knn_neighbors_used": 0,
    "tp1": None,
    "tp2": None,
    "tp3": None,
}

# Expanding zigzag waypoints: each breakout leg exceeds the prior swing
# high/low so the CHoCH state machine keeps re-firing (trend flips bullish
# <-> bearish every leg). BULL ends on a fresh bullish breakout (the query);
# BEAR mirrors it, ending on a fresh bearish breakdown.
_WP_BULL = [100, 102, 98, 101, 97, 115, 90, 125, 80, 140, 65, 160]
_WP_BEAR = [150, 148, 152, 149, 153, 135, 165, 120, 180, 100, 200, 75]


def _waypoint_series(waypoints, bars_per_leg=10, noise=0.0, seed=0):
    """Piecewise-linear interpolation between waypoints, optional jitter."""
    rng = np.random.default_rng(seed)
    closes: list[float] = []
    for a, b in zip(waypoints[:-1], waypoints[1:]):
        seg = np.linspace(a, b, bars_per_leg, endpoint=False)
        seg = seg + rng.uniform(-noise, noise, size=bars_per_leg)
        closes.extend(seg.tolist())
    closes.append(waypoints[-1])
    return closes


def _ohlcv_from_close(closes, volume=None, vol_base=1_000_000.0, band=0.002):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    opens = np.empty(n)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]
    high = np.maximum(opens, closes) * (1.0 + band)
    low = np.minimum(opens, closes) * (1.0 - band)
    if volume is None:
        volume = np.full(n, vol_base)
    else:
        volume = np.asarray(volume, dtype=float)
    dates = pd.bdate_range("2024-01-01", periods=n).strftime("%Y-%m-%d").tolist()
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": high,
            "low": low,
            "close": closes,
            "volume": volume,
        }
    )


# ---------------------------------------------------------------------------


def test_no_choch_flat_series():
    closes = np.full(80, 100.0)
    df = _ohlcv_from_close(closes)
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    assert out["choch_state"] == "NONE"
    assert out["knn_prob"] is None
    assert out == _NULL


def test_bullish_choch_with_knn_prob():
    closes = _waypoint_series(_WP_BULL, bars_per_leg=10, noise=0.05, seed=1)
    df = _ohlcv_from_close(closes)
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    last_close = float(df["close"].iloc[-1])

    assert out["choch_state"] == "BULLISH"
    assert out["knn_prob"] is not None
    assert 0.0 <= out["knn_prob"] <= 1.0
    assert out["knn_neighbors_used"] >= 1
    assert out["tp1"] is not None
    assert out["tp1"] > last_close


def test_bearish_choch_with_knn_prob():
    closes = _waypoint_series(_WP_BEAR, bars_per_leg=10, noise=0.05, seed=2)
    df = _ohlcv_from_close(closes)
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    last_close = float(df["close"].iloc[-1])

    assert out["choch_state"] == "BEARISH"
    assert out["knn_prob"] is not None
    assert 0.0 <= out["knn_prob"] <= 1.0
    assert out["knn_neighbors_used"] >= 1
    assert out["tp1"] is not None
    assert out["tp1"] < last_close


def test_short_history_degrades_to_null():
    closes = _waypoint_series(_WP_BULL[:4], bars_per_leg=6, noise=0.0, seed=3)
    df = _ohlcv_from_close(closes)
    assert len(df) < 60
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    assert out == _NULL


def test_missing_volume_column_degrades_to_null():
    closes = _waypoint_series(_WP_BULL, bars_per_leg=10, noise=0.05, seed=4)
    df = _ohlcv_from_close(closes).drop(columns=["volume"])
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    assert out == _NULL


def test_none_and_empty_input_never_raises():
    assert compute_smart_money(None) == _NULL
    assert compute_smart_money(pd.DataFrame()) == _NULL


def test_determinism_two_calls_identical():
    closes = _waypoint_series(_WP_BULL, bars_per_leg=10, noise=0.07, seed=5)
    df = _ohlcv_from_close(closes)
    out1 = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    out2 = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    assert out1 == out2


def test_knn_significant_unanimous_neighbors():
    # Zero noise -> every repeated bullish breakout leg is geometrically
    # clean, so the k nearest neighbors' outcomes are unanimous and
    # knn_prob lands exactly at 0.0 or 1.0.
    closes = _waypoint_series(_WP_BULL, bars_per_leg=10, noise=0.0, seed=6)
    df = _ohlcv_from_close(closes)
    out = compute_smart_money(df, swing_len=3, lookahead=5, window_len=100, k=3)
    assert out["knn_prob"] is not None
    assert out["knn_prob"] in (0.0, 1.0)
    assert out["knn_significant"] is True
