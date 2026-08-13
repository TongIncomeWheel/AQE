"""Tests for the rolling daily-bar VWAP (src/engines/vwap.py)."""

from __future__ import annotations

import pandas as pd

from src.engines.vwap import compute_vwap


def _bars(rows: list[dict]) -> pd.DataFrame:
    dates = pd.bdate_range("2026-06-01", periods=len(rows))
    return pd.DataFrame({
        "date": dates,
        "high": [r["h"] for r in rows],
        "low": [r["l"] for r in rows],
        "close": [r["c"] for r in rows],
        "volume": [r["v"] for r in rows],
    })


def test_vwap_matches_hand_computed_value():
    # Two bars, equal volume: VWAP is the plain average of the two typical prices.
    rows = [{"h": 102.0, "l": 98.0, "c": 100.0, "v": 1000},
            {"h": 106.0, "l": 102.0, "c": 104.0, "v": 1000}]
    df = _bars(rows * 7)  # 14 bars total, alternating — still 50/50 volume split
    out = compute_vwap(df, length=14)
    typ1 = (102.0 + 98.0 + 100.0) / 3.0
    typ2 = (106.0 + 102.0 + 104.0) / 3.0
    expected = (typ1 + typ2) / 2.0
    assert out["vwap_14d"] == round(expected, 2)


def test_vwap_position_above_when_close_at_or_above_vwap():
    rows = [{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000_000}] * 13
    rows.append({"h": 121.0, "l": 119.0, "c": 120.0, "v": 1_000_000})  # last bar spikes up
    df = _bars(rows)
    out = compute_vwap(df, length=14)
    assert out["vwap_14d_position"] == "ABOVE"


def test_vwap_position_below_when_close_under_vwap():
    rows = [{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000_000}] * 13
    rows.append({"h": 81.0, "l": 79.0, "c": 80.0, "v": 1_000_000})  # last bar drops
    df = _bars(rows)
    out = compute_vwap(df, length=14)
    assert out["vwap_14d_position"] == "BELOW"


def test_heavier_volume_bar_pulls_vwap_toward_it():
    light = {"h": 101.0, "l": 99.0, "c": 100.0, "v": 100}
    heavy = {"h": 111.0, "l": 109.0, "c": 110.0, "v": 100_000}
    df = _bars([light] * 13 + [heavy])
    out = compute_vwap(df, length=14)
    # VWAP should sit much closer to the heavy bar's typical price (110) than
    # a naive unweighted average of the two prices (105) would.
    assert out["vwap_14d"] > 108.0


def test_custom_length_produces_matching_key_names():
    rows = [{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1000}] * 5
    df = _bars(rows)
    out = compute_vwap(df, length=5)
    assert "vwap_5d" in out
    assert "vwap_5d_position" in out


def test_too_few_bars_degrades_to_null():
    df = _bars([{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1000}] * 5)
    out = compute_vwap(df, length=14)
    assert out["vwap_14d"] is None
    assert out["vwap_14d_position"] is None


def test_none_input_degrades_to_null():
    out = compute_vwap(None, length=14)
    assert out["vwap_14d"] is None


def test_zero_volume_degrades_to_null():
    df = _bars([{"h": 101.0, "l": 99.0, "c": 100.0, "v": 0}] * 14)
    out = compute_vwap(df, length=14)
    assert out["vwap_14d"] is None


def test_missing_required_column_degrades_to_null():
    df = _bars([{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1000}] * 14).drop(columns=["volume"])
    out = compute_vwap(df, length=14)
    assert out["vwap_14d"] is None


def test_never_raises_on_malformed_values():
    df = _bars([{"h": 101.0, "l": 99.0, "c": 100.0, "v": 1000}] * 14)
    df.loc[13, "close"] = float("nan")
    out = compute_vwap(df, length=14)  # must not raise
    assert "vwap_14d" in out and "vwap_14d_position" in out
