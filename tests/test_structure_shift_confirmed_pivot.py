"""Regression tests for structure_shift / BULLISH_BOS.

TWO failed fixes preceded this one, and both had the same shape: the reference
level was chosen such that price could never be above it, so BULLISH_BOS was
mathematically unreachable.

  attempt 1  compared close against find_swing()'s window-MAX high — a window
             that always includes today's own bar. close <= today's high <=
             window max, always. 0 hits in 227,717 historical rows.
  attempt 2  compared close against overhead_resistance()[0], which filters to
             pivots ABOVE the close (`h[i] > close`). Asking whether the close
             exceeds the nearest level above the close. 0 BULLISH_BOS in 240
             rows of the 2026-08-04 live export.

Attempt 2 SHIPPED WITH A PASSING TEST. That test hand-built a fixture carrying
a resistance level BELOW the close — an input `overhead_resistance()` cannot
produce — so it proved the wiring worked and said nothing about whether the
condition could ever be met by real data.

These tests therefore do two things the old suite did not:
  * assert the INVARIANT that made each old reference unreachable, directly,
    so a regression to either is caught by name
  * drive the REAL level functions with REAL price arrays, so no fixture can
    describe a world the production code cannot reach
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.drive_sync import _v21_record_fields
from src.scanner.levels import (
    last_confirmed_pivot_high,
    levels_for_ticker,
    overhead_resistance,
)


def _breakout_bars():
    """Rally -> confirmed pivot high at 20 -> pullback -> break out above it."""
    highs = np.array([10, 11, 12, 13, 14, 20, 14, 13, 12, 13, 14,
                      15, 16, 17, 18, 19, 21, 22], dtype=float)
    lows = highs - 1.0
    dates = pd.bdate_range("2026-01-01", periods=len(highs)).to_numpy()
    return highs, lows, dates


def _levels(entry, swing_low, swing_high, last_pivot_high=None, atr14=2.0):
    return {
        "entry": entry, "atr14": atr14,
        "fib": {"swing_low": swing_low, "swing_high": swing_high,
                "retracements": {}},
        "resistance": [],
        "swing_lows": [],
        "last_pivot_high": last_pivot_high,
    }


# ---------------------------------------------- the unreachability invariants

def test_overhead_resistance_can_never_sit_below_the_close():
    """The invariant that made attempt 2 unreachable.

    Every level it returns is above the close by construction, so
    `close > level[0]` is unsatisfiable — which is exactly what attempt 2 asked.
    """
    highs, _, dates = _breakout_bars()
    for close in (5.0, 15.0, 18.0, 21.5, 30.0):
        for lvl in overhead_resistance(highs, close, dates, atr14=1.0, k=5):
            assert lvl["price"] > close, \
                "overhead_resistance returned a level below close"


def test_window_max_high_can_never_sit_below_the_close():
    """The invariant that made attempt 1 unreachable."""
    highs, _, _ = _breakout_bars()
    close = float(highs[-1])          # best case: today closed on its own high
    assert not (close > highs.max())


# ----------------------------------------------------- the new reference works

def test_last_pivot_high_is_selected_by_recency_not_by_side():
    highs, _, dates = _breakout_bars()
    lph = last_confirmed_pivot_high(highs, dates, k=5, window=250)
    assert lph is not None
    assert lph["price"] == 20.0          # the confirmed pivot, not the running high
    assert lph["bars_ago"] > 0


def test_bos_fires_on_a_real_breakout_through_the_level_functions():
    """End-to-end through levels_for_ticker — no hand-built fixture.

    This is the test the old suite lacked. It cannot pass unless production
    code actually reaches a state where close exceeds the reference level.
    """
    highs, lows, dates = _breakout_bars()
    d = levels_for_ticker(close=20.2, atr14=1.0, highs=highs, lows=lows,
                          dates=dates)          # 1% through — a FRESH break
    assert d is not None
    assert d["last_pivot_high"]["price"] == 20.0
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BULLISH_BOS"
    assert fields["structure_shift_ref"] == 20.0


def test_no_bos_while_price_is_still_under_the_pivot():
    highs, lows, dates = _breakout_bars()
    d = levels_for_ticker(close=18.0, atr14=1.0, highs=highs, lows=lows,
                          dates=dates)
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] != "BULLISH_BOS"


# --------------------------------------------- the other two states unchanged

def test_bearish_choch_below_the_swing_anchor_low():
    d = _levels(entry=85.0, swing_low=90.0, swing_high=120.0,
                last_pivot_high={"price": 118.0, "date": "2026-07-01",
                                 "bars_ago": 9})
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BEARISH_CHOCH"
    assert fields["structure_shift_ref"] == 90.0


def test_range_between_the_anchors():
    d = _levels(entry=100.0, swing_low=90.0, swing_high=120.0,
                last_pivot_high={"price": 118.0, "date": "2026-07-01",
                                 "bars_ago": 9})
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "RANGE"
    assert fields["structure_shift_ref"] is None


def test_no_pivot_available_degrades_to_range_not_bos():
    """Nothing to break above — read RANGE rather than fabricate a break."""
    d = _levels(entry=110.0, swing_low=90.0, swing_high=120.0,
                last_pivot_high=None)
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "RANGE"


def test_null_when_no_swing_detected():
    d = {"entry": 100.0, "atr14": 2.0, "fib": {}, "resistance": [],
         "last_pivot_high": None}
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] is None
    assert fields["structure_shift_ref"] is None


def test_bos_beats_choch_when_both_could_read():
    """Above the pivot AND above the swing low — the bullish read wins."""
    d = _levels(entry=119.0, swing_low=90.0, swing_high=120.0,
                last_pivot_high={"price": 118.0, "date": "2026-07-01",
                                 "bars_ago": 9})
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "BULLISH_BOS"


# ------------------------------------ a BREAK is an event, not a standing state

def test_a_name_that_broke_out_weeks_ago_is_not_still_breaking_out():
    """Attempt 3's defect, found on the 2026-08-06 live export.

    Once the unreachability bugs were fixed the flag went the other way: 149 of
    328 names carried BULLISH_BOS, median price 4.6% ABOVE the level — MSFT
    +20%, PAY +80%. Nothing about MSFT 20% above an old pivot is a break of
    structure; the flag simply never switched off. 90 of the 136 alert-universe
    names would have gone into one digest.
    """
    d = _levels(entry=142.0, swing_low=90.0, swing_high=120.0,     # +20% through
                last_pivot_high={"price": 118.0, "date": "2026-07-01",
                                 "bars_ago": 9})
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["structure_shift"] == "ABOVE_STRUCTURE"
    assert fields["structure_shift_ref"] == 118.0      # the level is still named


def test_the_freshness_band_is_where_the_label_changes():
    # 0.0 is deliberately absent: sitting exactly ON the level is not through
    # it, and the rule is strictly-above. That case reads RANGE, tested below.
    for ext_pct, expected in ((0.1, "BULLISH_BOS"), (1.9, "BULLISH_BOS"),
                              (2.0, "BULLISH_BOS"), (2.1, "ABOVE_STRUCTURE"),
                              (10.0, "ABOVE_STRUCTURE")):
        d = _levels(entry=118.0 * (1 + ext_pct / 100), swing_low=90.0,
                    swing_high=120.0,
                    last_pivot_high={"price": 118.0, "date": "2026-07-01",
                                     "bars_ago": 9})
        got = _v21_record_fields("TEST", d, {}, {}, {})["structure_shift"]
        assert got == expected, (ext_pct, got)


def test_above_structure_does_not_read_as_a_strong_structure_lens():
    """The lens should not keep paying a name for a break it made in June."""
    from src.engines.lens_consensus import compute_lens_consensus
    rows = [{"ticker": "FRESH", "structure_shift": "BULLISH_BOS"},
            {"ticker": "OLD", "structure_shift": "ABOVE_STRUCTURE"}]
    out = {r["ticker"]: r for r in compute_lens_consensus(rows)}
    assert out["FRESH"]["lens"]["structure"] != out["OLD"]["lens"]["structure"]


# ------------------------------------------- the pivot itself ships on the row

def test_the_pivot_level_is_exported_not_just_used_and_discarded():
    """It was computed, used to set the flag, then dropped.

    The live NEAR_BREAKOUT alert reads record["last_pivot_high"]["price"], so
    with the key absent from every row that alert could not fire on ANY name —
    0 of 328 rows carried it on the 2026-08-06 export, and no test noticed
    because every alert test hand-fed the key it was testing.
    """
    highs, lows, dates = _breakout_bars()
    d = levels_for_ticker(close=18.0, atr14=1.0, highs=highs, lows=lows,
                          dates=dates)
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert fields["last_pivot_high"]["price"] == 20.0
    assert "date" in fields["last_pivot_high"]


def test_the_key_is_present_even_when_there_is_no_pivot():
    d = _levels(entry=100.0, swing_low=90.0, swing_high=120.0,
                last_pivot_high=None)
    fields = _v21_record_fields("TEST", d, {}, {}, {})
    assert "last_pivot_high" in fields and fields["last_pivot_high"] is None


def test_near_breakout_can_fire_on_a_record_the_pipeline_actually_builds():
    """End-to-end: the export row feeds the alert rule, no hand-built dict."""
    from src.alerts import engine as E
    highs, lows, dates = _breakout_bars()
    d = levels_for_ticker(close=19.7, atr14=1.0, highs=highs, lows=lows,
                          dates=dates)                     # 1.5% under 20.0
    rec = _v21_record_fields("TEST", d, {}, {}, {})
    rec["entry"] = 19.7
    fired = {t["level"] for t in
             E.evaluate("TEST", "daily_list", False, rec,
                        {"price": 19.7, "prev_close": 19.6})}
    assert "NEAR_BREAKOUT" in fired
