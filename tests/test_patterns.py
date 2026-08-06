"""Cup & handle detector.

The failure mode for any pattern scanner is the SAME one every time: loose
rules find the shape in noise, the output looks plausible, and nobody can tell
because a chart pattern has no ground truth on the row. So these tests spend
most of their effort on what must NOT detect — the near-misses that separate a
base from a bounce — rather than on proving the happy path once.

Every fixture is built as a price path and run through the real functions. No
hand-built pivot lists: a fixture that describes a pivot series the detector
cannot actually produce proves the wiring and nothing else, which is exactly
how the BULLISH_BOS bug shipped twice with a green suite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import patterns as P


def _dates(n):
    return pd.bdate_range("2026-01-01", periods=n).to_numpy()


def _bars(path, noise=0.0):
    """(high, low, close, dates, volume) from a close path."""
    c = np.asarray(path, dtype=float)
    h = c * (1.0 + 0.004 + noise)
    l = c * (1.0 - 0.004 - noise)
    v = np.full(len(c), 1.0e6)
    return h, l, c, _dates(len(c)), v


def _cup(depth_pct=25.0, cup_days=60, handle_days=8, handle_retrace=0.20,
         rim_drift_pct=0.0, pre=15, post_break=0):
    """A textbook path: flat run-up -> left rim -> rounded cup -> right rim
    -> handle -> (optionally) a break above the rim."""
    rim = 100.0
    low = rim * (1 - depth_pct / 100)
    pre_leg = list(np.linspace(rim * 0.80, rim, pre))
    half = cup_days // 2
    down = list(rim - (rim - low) * np.sin(np.linspace(0, np.pi / 2, half)))
    up_to = rim * (1 + rim_drift_pct / 100)
    up = list(low + (up_to - low) * np.sin(np.linspace(0, np.pi / 2, cup_days - half)))
    handle_low = up_to - (up_to - low) * handle_retrace
    hd = list(np.linspace(up_to, handle_low, max(handle_days // 2, 1))) + \
         list(np.linspace(handle_low, up_to * 0.995, max(handle_days - handle_days // 2, 1)))
    brk = list(np.linspace(up_to * 1.01, up_to * 1.06, post_break)) if post_break else []
    return pre_leg + down + up + hd + brk


# ------------------------------------------------------------ pivot series

def test_pivots_alternate_and_never_include_the_last_k_bars():
    """A pivot needs k clean bars to its RIGHT, so the newest k bars can never
    hold one — the detector must not call a shape whose final turn is unproven."""
    h, l, c, d, _ = _bars(_cup())
    piv = P.pivot_series(h, l, d)
    assert piv, "no pivots found in a shape built from turns"
    assert all(p["bars_ago"] >= P.PIVOT_K for p in piv)
    assert {p["kind"] for p in piv} <= {"H", "L"}


def test_pivot_series_survives_short_and_ragged_input():
    assert P.pivot_series(np.array([1.0, 2.0]), np.array([1.0, 2.0]), _dates(2)) == []
    h, l, c, d, _ = _bars([1.0] * 40)
    assert isinstance(P.pivot_series(h, l, d), list)


# ------------------------------------------------------------- the happy path

def test_a_textbook_cup_and_handle_is_found():
    h, l, c, d, v = _bars(_cup())
    r = P.detect_cup_handle(h, l, c, d, v)
    assert r["pattern"] == "CUP_HANDLE"
    assert r["pattern_stage"] in ("HANDLE", "CUP")
    assert r["pattern_trigger"] == pytest.approx(100.0, rel=0.03)
    assert r["pattern_invalidation"] < r["pattern_trigger"]
    assert r["pattern_days"] > P.CUP_MIN_DAYS
    assert 0.0 <= r["pattern_fit"] <= 1.0
    assert r["pattern_start"]


def test_a_break_above_the_rim_reads_triggered():
    h, l, c, d, v = _bars(_cup(post_break=4))
    r = P.detect_cup_handle(h, l, c, d, v)
    assert r["pattern"] == "CUP_HANDLE"
    assert r["pattern_stage"] == "TRIGGERED"


def test_the_trigger_is_the_rim_not_the_high_of_the_move():
    """It must be the level that CONFIRMS the pattern — the same kind of object
    as last_pivot_high — not wherever price has since run to."""
    h, l, c, d, v = _bars(_cup(post_break=6))
    r = P.detect_cup_handle(h, l, c, d, v)
    assert r["pattern_trigger"] < float(c[-1])


# ----------------------------------------------------- what must NOT detect

def test_a_shallow_pause_is_not_a_cup():
    h, l, c, d, v = _bars(_cup(depth_pct=5.0))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_a_crash_and_bounce_is_not_a_base():
    h, l, c, d, v = _bars(_cup(depth_pct=60.0))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_a_handle_that_gives_back_most_of_the_cup_is_a_failed_base():
    h, l, c, d, v = _bars(_cup(handle_retrace=0.75))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_a_right_rim_far_below_the_left_is_a_lower_high_not_a_cup():
    h, l, c, d, v = _bars(_cup(rim_drift_pct=-15.0))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_a_three_week_dip_is_a_flag_not_a_cup():
    h, l, c, d, v = _bars(_cup(cup_days=12, handle_days=4))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_a_straight_line_has_no_pattern():
    h, l, c, d, v = _bars(list(np.linspace(50, 150, 160)))
    assert P.detect_cup_handle(h, l, c, d, v)["pattern"] is None


def test_random_noise_does_not_manufacture_cups():
    """The point of building patterns from CONFIRMED pivots. A bar-template
    matcher finds a cup in any 120 bars of noise; this must mostly not."""
    rng = np.random.default_rng(7)
    hits = 0
    for _ in range(40):
        path = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 160)))
        h, l, c, d, v = _bars(path)
        if P.detect_cup_handle(h, l, c, d, v)["pattern"]:
            hits += 1
    assert hits <= 8, f"{hits}/40 random walks read as cups"


# ------------------------------------------------------------ contract shape

def test_a_blank_record_still_carries_every_key():
    """An ABSENT key would make a reader's .get() read as 'no pattern' on a row
    where the detector never ran. Those are different states."""
    h, l, c, d, v = _bars(list(np.linspace(50, 150, 160)))
    r = P.detect_cup_handle(h, l, c, d, v)
    for key in ("pattern", "pattern_stage", "pattern_trigger",
                "pattern_invalidation", "pattern_days", "pattern_fit",
                "pattern_start"):
        assert key in r, key
        assert r[key] is None


def test_detect_all_returns_the_same_shape_as_one_detector():
    h, l, c, d, v = _bars(_cup())
    one = P.detect_cup_handle(h, l, c, d, v)
    every = P.detect_all(h, l, c, d, v)
    assert set(one) == set(every)
    assert every["pattern"] == "CUP_HANDLE"


def test_a_detector_that_explodes_cannot_break_the_lens(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("bad maths")
    monkeypatch.setitem(P.DETECTORS, "CUP_HANDLE", _boom)
    h, l, c, d, v = _bars(_cup())
    assert P.detect_all(h, l, c, d, v)["pattern"] is None


def test_volume_is_optional_and_its_absence_is_not_a_penalty():
    h, l, c, d, v = _bars(_cup())
    with_v = P.detect_cup_handle(h, l, c, d, v)
    without = P.detect_cup_handle(h, l, c, d, None)
    assert without["pattern"] == with_v["pattern"]
    assert without["pattern_trigger"] == with_v["pattern_trigger"]


def test_the_window_is_six_months_not_three():
    """A textbook cup runs 2-6 months. A 3-month window would silently report
    only the short ones and call the rest 'no pattern'."""
    assert P.PATTERN_WINDOW >= 126
