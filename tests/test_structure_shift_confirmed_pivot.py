"""Regression tests for the FIX_CONFIRMED_PIVOT fix (AIC ruling 9-0, 2026-07-16):
structure_shift's BULLISH_BOS test used to compare close against find_swing()'s
window-max high, which always includes today's own bar — making close > that
value mathematically impossible (0 hits in 227,717 historical rows). It now
compares against the nearest CONFIRMED pivot high (overhead_resistance()[0]),
which excludes the live/unconfirmed peak — so BULLISH_BOS can actually fire."""

from __future__ import annotations

from src.data.drive_sync import _v21_record_fields


def _levels(entry, swing_low, swing_high, resistance=None, atr14=2.0):
    return {
        "entry": entry, "atr14": atr14,
        "fib": {"swing_low": swing_low, "swing_high": swing_high, "retracements": {}},
        "resistance": resistance or [],
        "swing_lows": [],
    }


def test_bullish_bos_now_reachable_above_confirmed_pivot():
    # Close (110) is above the nearest CONFIRMED pivot high (105) but still
    # below the raw window-max swing_high (120, e.g. an unconfirmed live peak
    # from an earlier bar in the window) — the old code could never fire here.
    d = _levels(entry=110.0, swing_low=90.0, swing_high=120.0,
                resistance=[{"price": 105.0, "date": "2026-07-01"}])
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BULLISH_BOS"
    assert fields["structure_shift_ref"] == 105.0


def test_bearish_choch_unaffected_by_the_fix():
    d = _levels(entry=85.0, swing_low=90.0, swing_high=120.0,
                resistance=[{"price": 105.0, "date": "2026-07-01"}])
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BEARISH_CHOCH"
    assert fields["structure_shift_ref"] == 90.0


def test_range_when_between_anchors():
    d = _levels(entry=100.0, swing_low=90.0, swing_high=120.0,
                resistance=[{"price": 105.0, "date": "2026-07-01"}])
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "RANGE"
    assert fields["structure_shift_ref"] is None


def test_no_confirmed_resistance_falls_back_to_range_not_bos():
    # Price already above swing_low, no confirmed pivot high in the window at
    # all — BOS can't be evaluated (nothing to break above), so this reads
    # RANGE rather than fabricating a break.
    d = _levels(entry=110.0, swing_low=90.0, swing_high=120.0, resistance=[])
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "RANGE"


def test_null_when_no_swing_detected():
    d = {"entry": 100.0, "atr14": 2.0, "fib": {}, "resistance": []}
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] is None
    assert fields["structure_shift_ref"] is None


def test_nearest_confirmed_pivot_wins_over_farther_ones():
    d = _levels(entry=108.0, swing_low=90.0, swing_high=130.0, resistance=[
        {"price": 105.0, "date": "2026-07-10"},  # nearest, overhead_resistance is nearest-first
        {"price": 118.0, "date": "2026-05-01"},
    ])
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BULLISH_BOS"
    assert fields["structure_shift_ref"] == 105.0
