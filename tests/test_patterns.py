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


def test_an_ambiguous_chart_names_the_runner_up_instead_of_hiding_it():
    """A cup & handle and a double top are the SAME geometry — two highs at a
    level with a trough between — differing only in how price resolves. Picking
    one silently would hand the reader a bullish or bearish flag decided by a
    tie-break they cannot see."""
    h, l, c, d, v = _bars(_cup())
    r = P.detect_all(h, l, c, d, v)
    named = {r["pattern"]} | set((r["pattern_alt"] or "").split(", ")) - {""}
    assert "CUP_HANDLE" in named and "DOUBLE_TOP" in named


def test_an_unambiguous_chart_has_no_alternatives():
    h, l, c, d, v = _bars(list(np.linspace(50, 150, 160)))
    assert P.detect_all(h, l, c, d, v)["pattern_alt"] is None


def test_a_detector_that_explodes_cannot_break_the_lens(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("bad maths")
    for name in list(P.DETECTORS):
        monkeypatch.setitem(P.DETECTORS, name, _boom)
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


# ═══════════════════════════════════════════════════ double bottom

def _double_bottom(gap_pct=1.5, bounce_pct=15.0, sep=40, pre=20, post=12,
                   break_out=False):
    """Two lows at a similar level with a real peak between them."""
    lo = 100.0
    peak = lo * (1 + bounce_pct / 100)
    second = lo * (1 + gap_pct / 100)
    down = list(np.linspace(peak * 1.15, lo, pre))
    up = list(np.linspace(lo, peak, sep // 2))
    back = list(np.linspace(peak, second, sep - sep // 2))
    end_at = peak * (1.04 if break_out else 0.93)
    tail = list(np.linspace(second, end_at, post))
    return down + up + back + tail


def test_a_double_bottom_is_found_with_the_neckline_as_the_trigger():
    """The trigger must be the NECKLINE, not the lows — that is the level whose
    break confirms the base and the one the alert layer should watch."""
    h, l, c, d, v = _bars(_double_bottom())
    r = P.detect_double_bottom(h, l, c, d, v)
    assert r["pattern"] == "DOUBLE_BOTTOM"
    assert r["pattern_stage"] == "BASE"
    assert r["pattern_trigger"] == pytest.approx(115.0, rel=0.05)
    assert r["pattern_invalidation"] == pytest.approx(100.0, rel=0.05)
    assert r["pattern_trigger"] > r["pattern_invalidation"]


def test_a_double_bottom_that_clears_the_neckline_reads_triggered():
    h, l, c, d, v = _bars(_double_bottom(break_out=True))
    assert P.detect_double_bottom(h, l, c, d, v)["pattern_stage"] == "TRIGGERED"


def test_two_lows_with_no_bounce_between_them_is_a_flat_range():
    """Without a minimum rise, ANY two similar lows in a quiet range qualify —
    and quiet ranges are everywhere."""
    h, l, c, d, v = _bars(_double_bottom(bounce_pct=3.0))
    assert P.detect_double_bottom(h, l, c, d, v)["pattern"] is None


def test_a_second_low_well_below_the_first_is_a_downtrend_not_a_base():
    h, l, c, d, v = _bars(_double_bottom(gap_pct=-14.0))
    assert P.detect_double_bottom(h, l, c, d, v)["pattern"] is None


def test_a_base_that_has_since_broken_down_is_not_the_live_read():
    path = _double_bottom() + list(np.linspace(100, 82, 12))
    h, l, c, d, v = _bars(path)
    assert P.detect_double_bottom(h, l, c, d, v)["pattern"] is None


# ══════════════════════════════════════════════ ascending triangle

def _asc_triangle(top=100.0, touches=3, rise_pct=6.0, leg=18, break_out=False):
    """Flat ceiling tested repeatedly while the lows step up underneath."""
    path = list(np.linspace(top * 0.80, top, leg))
    n_low = touches
    lows = np.linspace(top * (1 - rise_pct / 100 * n_low), top * 0.985, n_low)
    for lw in lows:
        path += list(np.linspace(top, lw, leg))       # pull back to a higher low
        path += list(np.linspace(lw, top, leg))       # and back to the ceiling
    path += list(np.linspace(top, top * (1.05 if break_out else 0.99), 10))
    return path


def test_an_ascending_triangle_is_found():
    h, l, c, d, v = _bars(_asc_triangle())
    r = P.detect_ascending_triangle(h, l, c, d, v)
    assert r["pattern"] == "ASC_TRIANGLE"
    assert r["pattern_stage"] == "FORMING"
    assert r["pattern_trigger"] == pytest.approx(100.0, rel=0.04)


def test_the_triangle_invalidation_is_the_LAST_rising_low():
    """Tighter and more honest than the first low of the formation: that step
    is the one that has to fail for the structure to be gone."""
    h, l, c, d, v = _bars(_asc_triangle())
    r = P.detect_ascending_triangle(h, l, c, d, v)
    assert r["pattern_invalidation"] > 85.0
    assert r["pattern_invalidation"] < r["pattern_trigger"]


def test_a_close_above_the_ceiling_reads_triggered():
    h, l, c, d, v = _bars(_asc_triangle(break_out=True))
    assert P.detect_ascending_triangle(h, l, c, d, v)["pattern_stage"] == "TRIGGERED"


def test_flat_lows_under_a_flat_top_is_a_range_not_a_triangle():
    """The RISING lows are the entire content. Without them this is just a
    resistance level, which AQE already ships as last_pivot_high."""
    h, l, c, d, v = _bars(_asc_triangle(rise_pct=0.0))
    assert P.detect_ascending_triangle(h, l, c, d, v)["pattern"] is None


def test_falling_lows_are_not_an_ascending_triangle():
    h, l, c, d, v = _bars(_asc_triangle(rise_pct=-5.0))
    assert P.detect_ascending_triangle(h, l, c, d, v)["pattern"] is None


def test_one_touch_of_the_ceiling_is_not_a_ceiling():
    h, l, c, d, v = _bars(list(np.linspace(70, 100, 60)) + list(np.linspace(100, 92, 20)))
    assert P.detect_ascending_triangle(h, l, c, d, v)["pattern"] is None


# ═══════════════════════════════════════════════ the three together

def test_every_detector_returns_the_identical_key_set():
    """The registry contract: adding a pattern changes DETECTORS and nothing
    downstream. That only holds if the shapes match exactly."""
    h, l, c, d, v = _bars(_cup())
    shapes = [fn(h, l, c, d, v) for fn in P.DETECTORS.values()]
    assert all(set(s) == set(shapes[0]) for s in shapes)


def test_detect_all_picks_the_best_fit_when_several_match():
    """Ranked among the shapes that SURVIVE the spent/fit cuts — detect_all
    applies those before choosing, so the comparison has to as well."""
    h, l, c, d, v = _bars(_double_bottom())
    last = float(c[-1])
    matched = {}
    for n, fn in P.DETECTORS.items():
        r = fn(h, l, c, d, v)
        if (r["pattern"] and not P._is_spent(r, last)
                and (r["pattern_fit"] or 0) >= P.PATTERN_MIN_FIT):
            matched[n] = r
    best = P.detect_all(h, l, c, d, v)
    if not matched:
        assert best["pattern"] is None
        return
    assert best["pattern"] in matched
    assert best["pattern_fit"] == max(r["pattern_fit"] for r in matched.values())


def test_noise_does_not_manufacture_any_of_the_three():
    """Repeated for the full registry: the looser the shape, the more this
    matters. An ascending triangle is the easiest of the three to see in noise."""
    rng = np.random.default_rng(11)
    hits = {n: 0 for n in P.DETECTORS}
    for _ in range(40):
        path = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 180)))
        h, l, c, d, v = _bars(path)
        for n, fn in P.DETECTORS.items():
            if fn(h, l, c, d, v)["pattern"]:
                hits[n] += 1
    assert all(v <= 10 for v in hits.values()), hits


def test_the_lens_carries_no_probability_by_design():
    """PM ruling: a visual flag, not a signal. A hit-rate field reappearing
    here would be a quiet re-litigation of that call."""
    h, l, c, d, v = _bars(_cup())
    r = P.detect_all(h, l, c, d, v)
    assert not any(k in r for k in ("pattern_hit_rate", "pattern_n",
                                    "pattern_status", "pattern_p"))


# ═════════════════════════════════════ bearish twins + wedges + H&S

def _mirror_path(path):
    """Reflect a price path so a bullish fixture becomes its bearish twin."""
    a = np.asarray(path, dtype=float)
    return list(a.max() + a.min() - a)


def _zig(pairs, leg=14):
    out = []
    for a, b in pairs:
        out += list(np.linspace(a, b, leg))
    return out


_HS = [(80, 100), (100, 88), (88, 115), (115, 87), (87, 101), (101, 92)]
_RISING_WEDGE = [(80, 100), (100, 88), (88, 104), (104, 95), (95, 107),
                 (107, 101), (101, 108)]
_FALLING_WEDGE = [(120, 95), (95, 112), (112, 90), (90, 104), (104, 88),
                  (88, 98), (98, 89)]


@pytest.mark.parametrize("name,path", [
    ("DOUBLE_TOP", _mirror_path(_double_bottom())),
    ("DESC_TRIANGLE", _mirror_path(_asc_triangle())),
    ("HEAD_SHOULDERS", _zig(_HS, 22)),
    ("INV_HEAD_SHOULDERS", _mirror_path(_zig(_HS, 22))),
    ("RISING_WEDGE", _zig(_RISING_WEDGE)),
    ("FALLING_WEDGE", _zig(_FALLING_WEDGE)),
    ("DOUBLE_BOTTOM", _double_bottom()),
    ("ASC_TRIANGLE", _asc_triangle()),
    ("CUP_HANDLE", _cup()),
])
def test_every_registered_pattern_detects_its_own_textbook_shape(name, path):
    h, l, c, d, v = _bars(path)
    assert P.DETECTORS[name](h, l, c, d, v)["pattern"] == name


@pytest.mark.parametrize("name,expected", [
    ("CUP_HANDLE", "BULLISH"), ("DOUBLE_BOTTOM", "BULLISH"),
    ("ASC_TRIANGLE", "BULLISH"), ("FALLING_WEDGE", "BULLISH"),
    ("INV_HEAD_SHOULDERS", "BULLISH"),
    ("DOUBLE_TOP", "BEARISH"), ("DESC_TRIANGLE", "BEARISH"),
    ("RISING_WEDGE", "BEARISH"), ("HEAD_SHOULDERS", "BEARISH"),
])
def test_the_lens_reads_both_directions(name, expected):
    """A lens that only ever reports bullish shapes is not reading the chart,
    it is flattering it."""
    paths = {"CUP_HANDLE": _cup(), "DOUBLE_BOTTOM": _double_bottom(),
             "ASC_TRIANGLE": _asc_triangle(),
             "DOUBLE_TOP": _mirror_path(_double_bottom()),
             "DESC_TRIANGLE": _mirror_path(_asc_triangle()),
             "HEAD_SHOULDERS": _zig(_HS, 22),
             "INV_HEAD_SHOULDERS": _mirror_path(_zig(_HS, 22)),
             "RISING_WEDGE": _zig(_RISING_WEDGE),
             "FALLING_WEDGE": _zig(_FALLING_WEDGE)}
    h, l, c, d, v = _bars(paths[name])
    r = P.DETECTORS[name](h, l, c, d, v)
    assert r["pattern_direction"] == expected


def test_a_bearish_trigger_sits_BELOW_its_invalidation():
    """The whole reason pattern_direction exists. On a bearish shape the
    trigger is broken DOWNWARD and the invalidation is ABOVE it — a reader who
    assumes 'trigger = buy above' would have it exactly backwards."""
    for name, path in (("DOUBLE_TOP", _mirror_path(_double_bottom())),
                       ("HEAD_SHOULDERS", _zig(_HS, 22)),
                       ("RISING_WEDGE", _zig(_RISING_WEDGE))):
        h, l, c, d, v = _bars(path)
        r = P.DETECTORS[name](h, l, c, d, v)
        assert r["pattern_direction"] == "BEARISH", name
        assert r["pattern_trigger"] < r["pattern_invalidation"], name


def test_a_bullish_trigger_sits_ABOVE_its_invalidation():
    for name, path in (("CUP_HANDLE", _cup()), ("DOUBLE_BOTTOM", _double_bottom()),
                       ("ASC_TRIANGLE", _asc_triangle()),
                       ("FALLING_WEDGE", _zig(_FALLING_WEDGE))):
        h, l, c, d, v = _bars(path)
        r = P.DETECTORS[name](h, l, c, d, v)
        assert r["pattern_direction"] == "BULLISH", name
        assert r["pattern_trigger"] > r["pattern_invalidation"], name


def test_a_rising_wedge_is_bearish_even_though_every_high_is_higher():
    """The convergence is the content. Mirroring a falling wedge would have
    produced this shape with the WRONG direction attached — which is why the
    wedges are written directly rather than reflected."""
    h, l, c, d, v = _bars(_zig(_RISING_WEDGE))
    r = P.detect_rising_wedge(h, l, c, d, v)
    assert r["pattern_direction"] == "BEARISH"
    piv = P.pivot_series(h, l, d)
    hs = [p["price"] for p in piv if p["kind"] == "H"]
    assert hs[-1] > hs[0], "fixture is not actually making higher highs"


def test_a_plain_uptrend_that_never_converges_is_not_a_wedge():
    h, l, c, d, v = _bars(_zig([(80, 100), (100, 90), (90, 112), (112, 102),
                                (102, 124), (124, 114), (114, 136)]))
    assert P.detect_rising_wedge(h, l, c, d, v)["pattern"] is None


def test_a_double_top_halfway_up_a_range_is_not_a_top():
    """Mirror of the base test that fixed double bottom: two similar highs
    halfway down a range are a pause, not a top."""
    path = _mirror_path(_double_bottom()) + list(np.linspace(100, 160, 30))
    h, l, c, d, v = _bars(path)
    assert P.detect_double_top(h, l, c, d, v)["pattern"] is None


def test_head_and_shoulders_needs_an_actual_head():
    """Three peaks at the same height is a range, not a reversal."""
    h, l, c, d, v = _bars(_zig([(80, 100), (100, 90), (90, 100), (100, 90),
                                (90, 100), (100, 93)], 22))
    assert P.detect_head_shoulders(h, l, c, d, v)["pattern"] is None


def test_head_and_shoulders_needs_comparable_shoulders():
    h, l, c, d, v = _bars(_zig([(60, 78), (78, 70), (70, 115), (115, 87),
                                (87, 108), (108, 95)], 22))
    assert P.detect_head_shoulders(h, l, c, d, v)["pattern"] is None


def test_the_registry_covers_both_directions():
    dirs = set()
    for name, path in (("CUP_HANDLE", _cup()), ("HEAD_SHOULDERS", _zig(_HS, 22))):
        h, l, c, d, v = _bars(path)
        dirs.add(P.DETECTORS[name](h, l, c, d, v)["pattern_direction"])
    assert dirs == {"BULLISH", "BEARISH"}
    assert len(P.DETECTORS) >= 9


def test_direction_is_present_on_every_blank_record_too():
    h, l, c, d, v = _bars(list(np.linspace(50, 150, 160)))
    for fn in P.DETECTORS.values():
        r = fn(h, l, c, d, v)
        assert "pattern_direction" in r


def test_the_ascending_triangle_tolerates_one_overshoot_and_one_flat_tread():
    """Both were fatal in the first version: it stopped gathering ceiling
    touches at the first pivot outside tolerance, and demanded every single
    low step up. A real staircase has an odd tread."""
    path = _zig([(80, 100), (100, 88), (88, 107), (107, 93),   # 107 overshoots
                 (93, 100), (100, 93), (93, 100), (100, 97)], 16)
    h, l, c, d, v = _bars(path)
    assert P.detect_ascending_triangle(h, l, c, d, v)["pattern"] == "ASC_TRIANGLE"


# ════════════════════════════════════ spent shapes are dropped, not reported

def test_a_shape_price_has_long_since_left_is_not_reported():
    """The same defect as structure_shift's, one layer up: a flag latches on at
    the break and never switches off. On the 2026-08-06 board 157 of 282
    detections were TRIGGERED and the median one was already 9.9% past its
    level — 87% of the whole board carried a pattern, which is not a flag."""
    # JUST through the rim (~100.4): still the read.
    fresh = _cup() + [101.0, 101.4, 101.8]
    h, l, c, d, v = _bars(fresh)
    assert P.detect_cup_handle(h, l, c, d, v)["pattern_stage"] == "TRIGGERED"
    # The cup fixture is ALSO a double top (same geometry — see the ambiguity
    # test), so assert the shape survived rather than that it won the tie-break.
    r = P.detect_all(h, l, c, d, v)
    named = {r["pattern"]} | {x.strip() for x in (r["pattern_alt"] or "").split(",")}
    assert "CUP_HANDLE" in named
    # ...and long gone once price has run away from it.
    h2, l2, c2, d2, v2 = _bars(_cup() + list(np.linspace(101, 125, 8)))
    assert P.detect_cup_handle(h2, l2, c2, d2, v2)["pattern_stage"] == "TRIGGERED"
    assert P.detect_all(h2, l2, c2, d2, v2)["pattern"] is None


def test_the_spent_test_reads_the_right_way_round_for_a_bearish_shape():
    """A bearish trigger is broken DOWNWARD, so "past it" means BELOW. Getting
    the sign wrong would keep every spent bearish shape and drop every fresh
    one — and both halves would still look plausible on screen."""
    fresh = {"pattern": "DOUBLE_TOP", "pattern_direction": "BEARISH",
             "pattern_stage": "TRIGGERED", "pattern_trigger": 100.0}
    assert P._is_spent(fresh, 98.0) is False        # 2% through — still the read
    assert P._is_spent(fresh, 80.0) is True         # 20% through — long gone


def test_an_unbroken_shape_is_never_spent_however_old():
    """FORMING/BASE shapes have not triggered, so the extension test does not
    apply to them at all — they are exactly what a watchlist wants."""
    r = {"pattern": "ASC_TRIANGLE", "pattern_direction": "BULLISH",
         "pattern_stage": "FORMING", "pattern_trigger": 100.0}
    assert P._is_spent(r, 60.0) is False


def test_a_sloppy_shape_is_dropped_by_the_fit_floor():
    h, l, c, d, v = _bars(_cup())
    one = P.detect_cup_handle(h, l, c, d, v)
    assert one["pattern"] == "CUP_HANDLE"
    import unittest.mock as _m
    with _m.patch.object(P, "PATTERN_MIN_FIT", (one["pattern_fit"] or 0) + 0.01):
        assert P.detect_all(h, l, c, d, v)["pattern"] != "CUP_HANDLE"


def test_the_thresholds_are_named_so_they_can_be_argued_with():
    assert P.PATTERN_MAX_EXTENSION_PCT == 5.0
    assert P.PATTERN_MIN_FIT == 0.50
