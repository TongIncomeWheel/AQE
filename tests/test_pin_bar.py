"""Tests for the Pin Bar / Inside Bar pattern detector (src/engines/pin_bar.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.engines.pin_bar import compute_pin_bar, _NULL


def _bars(rows: list[dict]) -> pd.DataFrame:
    """Build a 4-bar OHLC frame from [{o,h,l,c}, ...] (oldest first)."""
    dates = pd.bdate_range("2026-06-01", periods=len(rows))
    return pd.DataFrame({
        "date": dates,
        "open": [r["o"] for r in rows],
        "high": [r["h"] for r in rows],
        "low": [r["l"] for r in rows],
        "close": [r["c"] for r in rows],
    })


# A neutral, non-pin, non-filter-triggering "filler" bar (small range, no
# extreme wicks) used for indices we don't care about in a given test.
_FILLER = {"o": 94.0, "h": 95.0, "l": 93.0, "c": 94.5}


def test_bullish_pin_bar_on_last_bar():
    # bar[-2] small range (2) so the filter (>= 2.0x) passes for bar[-1]'s range 10.
    prev = {"o": 93.5, "h": 95.0, "l": 93.0, "c": 94.5}          # range 2, not a pin
    pin = {"o": 98.0, "h": 100.0, "l": 90.0, "c": 99.0}          # range 10
    # lower_wick = 98-90=8 (>=6.6) | body = 1 (<=4) | upper_wick = 100-99=1 (<=4)
    df = _bars([_FILLER, _FILLER, prev, pin])
    out = compute_pin_bar(df)
    assert out["pin_bar_state"] == "BULLISH_PIN"
    assert out["pin_bar_level"] == 90.0
    assert out["pin_bar_date"] == str(df["date"].iloc[-1].date())
    assert out["pin_bar_date"] is not None


def test_bearish_pin_bar_on_last_bar():
    prev = {"o": 93.5, "h": 95.0, "l": 93.0, "c": 94.5}          # range 2
    pin = {"o": 91.0, "h": 100.0, "l": 90.0, "c": 92.0}          # range 10
    # upper_wick = 100-92=8 (>=6.6) | body=1 (<=4) | lower_wick=91-90=1 (<=4)
    df = _bars([_FILLER, _FILLER, prev, pin])
    out = compute_pin_bar(df)
    assert out["pin_bar_state"] == "BEARISH_PIN"
    assert out["pin_bar_level"] == 100.0


def test_inside_bar_detection():
    mother = {"o": 92.0, "h": 100.0, "l": 90.0, "c": 96.0}       # range 10
    inside = {"o": 94.0, "h": 98.0, "l": 92.0, "c": 95.0}        # fully within mother
    df = _bars([_FILLER, _FILLER, mother, inside])
    out = compute_pin_bar(df)
    assert out["inside_bar"] is True


def test_not_inside_bar_when_range_exceeds_mother():
    mother = {"o": 92.0, "h": 100.0, "l": 90.0, "c": 96.0}
    not_inside = {"o": 94.0, "h": 101.0, "l": 92.0, "c": 95.0}   # high breaks mother's high
    df = _bars([_FILLER, _FILLER, mother, not_inside])
    out = compute_pin_bar(df)
    assert out["inside_bar"] is False


def test_pib_pattern_pin_bar_then_inside_bar():
    # index1 small range so the filter passes for index2 (the pin bar).
    small_prev = {"o": 94.5, "h": 95.0, "l": 94.0, "c": 94.7}    # range 1
    pin = {"o": 98.0, "h": 100.0, "l": 90.0, "c": 99.0}          # range 10, bullish pin
    inside = {"o": 95.0, "h": 98.0, "l": 92.0, "c": 96.0}        # range 6, inside pin's range
    df = _bars([_FILLER, small_prev, pin, inside])
    out = compute_pin_bar(df)
    assert out["inside_bar"] is True
    assert out["pib_pattern"] is True
    # the inside bar itself is filtered out as a fresh pin (range 6 < 2x prior range 10)
    assert out["pin_bar_state"] == "NONE"


def test_pib_pattern_false_when_prior_bar_not_a_pin():
    normal = {"o": 92.0, "h": 96.0, "l": 90.0, "c": 94.0}        # ordinary candle, not a pin
    inside = {"o": 92.5, "h": 95.0, "l": 91.0, "c": 93.0}        # inside `normal`'s range
    df = _bars([_FILLER, _FILLER, normal, inside])
    out = compute_pin_bar(df)
    assert out["inside_bar"] is True
    assert out["pib_pattern"] is False


def test_small_candle_filter_rejects_undersized_range():
    # Same shape as the bullish pin bar test, but the prior bar's range (6) is
    # too close to the pin candidate's range (10) to clear the 2.0x filter.
    prev = {"o": 91.0, "h": 99.0, "l": 93.0, "c": 96.0}          # range 6
    pin_shape = {"o": 98.0, "h": 100.0, "l": 90.0, "c": 99.0}    # range 10 (< 2*6=12)
    df = _bars([_FILLER, _FILLER, prev, pin_shape])
    out = compute_pin_bar(df)
    assert out["pin_bar_state"] == "NONE"


def test_small_candle_filter_disabled_allows_it():
    prev = {"o": 91.0, "h": 99.0, "l": 93.0, "c": 96.0}          # range 6
    pin_shape = {"o": 98.0, "h": 100.0, "l": 90.0, "c": 99.0}    # range 10
    df = _bars([_FILLER, _FILLER, prev, pin_shape])
    out = compute_pin_bar(df, small_candle_filter=False)
    assert out["pin_bar_state"] == "BULLISH_PIN"


def test_no_pattern_on_ordinary_candles():
    ordinary = {"o": 92.0, "h": 96.0, "l": 90.0, "c": 94.5}      # balanced candle
    df = _bars([_FILLER, _FILLER, _FILLER, ordinary])
    out = compute_pin_bar(df)
    assert out["pin_bar_state"] == "NONE"
    assert out["pin_bar_level"] is None
    assert out["pin_bar_date"] is None
    assert out["pib_pattern"] is False


def test_short_data_degrades_to_null():
    df = _bars([_FILLER, _FILLER, _FILLER])  # only 3 bars, need >= 4
    assert compute_pin_bar(df) == _NULL


def test_none_input_degrades_to_null():
    assert compute_pin_bar(None) == _NULL


def test_empty_frame_degrades_to_null():
    assert compute_pin_bar(pd.DataFrame()) == _NULL


def test_missing_required_column_degrades_to_null():
    df = _bars([_FILLER, _FILLER, _FILLER, _FILLER]).drop(columns=["high"])
    assert compute_pin_bar(df) == _NULL


def test_never_raises_on_malformed_values():
    bad = _bars([_FILLER, _FILLER, _FILLER, _FILLER])
    bad.loc[3, "high"] = float("nan")
    out = compute_pin_bar(bad)
    assert out["pin_bar_state"] == "NONE"   # NaN range -> no crash, no false signal
