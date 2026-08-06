"""Candlestick lens.

Two things are being guarded here, and only one of them is "does it detect".

The first is the DEFINITIONS: each pattern has near-misses that a sloppy rule
waves through — an engulfing bar that does not actually engulf, a star whose
middle candle is too big to be a star, a harami that is really an inside bar
with a full body. Those are what separate a candlestick lens from a random
label generator, so they get more tests than the happy paths.

The second is that HAMMER must be the same geometry as `pin_bar_state`. AQE
already ships that field; a second wick rule living in this module is how one
field quietly comes to mean something different from its twin.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.engines import candles as C


def _bar(o, h, l, c):
    return [o, h, l, c]


def _series(bars):
    """bars = list of [o,h,l,c] -> the four arrays detect_candle wants."""
    a = np.asarray(bars, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def _flat(n=3, px=100.0):
    return [_bar(px, px + 0.5, px - 0.5, px) for _ in range(n)]


def _detect(bars):
    return C.detect_candle(*_series(bars))


# ------------------------------------------------------------- single bar

def test_a_hammer_is_the_same_geometry_as_pin_bar_state():
    """The field already exists. If this module re-derived the wick rule the
    two could disagree about the same bar — so it calls the shared test."""
    from src.engines.pin_bar import _pin_bar_at
    bars = _flat(2) + [_bar(100, 100.6, 94, 99.6)]
    r = _detect(bars)
    assert r["candle"] == "HAMMER" and r["candle_direction"] == "BULLISH"
    o, h, l, c = 100, 100.6, 94, 99.6
    assert _pin_bar_at(o, h, l, c, float("nan"),
                       wick_ratio=C.PIN_WICK_RATIO, body_ratio=C.PIN_BODY_RATIO,
                       opp_wick_ratio=C.PIN_OPP_WICK_RATIO,
                       small_candle_filter=False,
                       small_candle_mult=0.0) == "BULLISH_PIN"


def test_a_shooting_star_is_the_bearish_pin():
    bars = _flat(2) + [_bar(100, 106, 99.5, 100.3)]
    r = _detect(bars)
    assert r["candle"] == "SHOOTING_STAR" and r["candle_direction"] == "BEARISH"


def test_a_doji_is_neutral_not_bullish():
    """Open and close level says indecision. Calling it directional would be
    inventing a read the bar does not contain."""
    bars = _flat(2) + [_bar(100, 103, 97, 100.1)]
    r = _detect(bars)
    assert r["candle"] == "DOJI" and r["candle_direction"] == "NEUTRAL"


def test_a_marubozu_needs_almost_no_wick():
    assert _detect(_flat(2) + [_bar(100, 105.1, 99.95, 105)])["candle"] == "MARUBOZU_BULL"
    # same body, but a third of the range is wick -> not a marubozu
    assert _detect(_flat(2) + [_bar(100, 108, 98, 105)])["candle"] != "MARUBOZU_BULL"


# --------------------------------------------------------------- two bar

def test_a_bullish_engulfing_must_actually_engulf():
    down = _bar(105, 105.5, 99, 100)
    assert _detect(_flat(1) + [down, _bar(99.5, 106, 99.4, 105.5)])["candle"] \
        == "BULLISH_ENGULFING"
    # closes higher but opens ABOVE the prior close — no engulf
    assert _detect(_flat(1) + [down, _bar(101, 106, 100.9, 105.5)])["candle"] \
        != "BULLISH_ENGULFING"


def test_a_bearish_engulfing_is_the_mirror():
    up = _bar(100, 105.5, 99.5, 105)
    r = _detect(_flat(1) + [up, _bar(105.5, 105.6, 99, 99.5)])
    assert r["candle"] == "BEARISH_ENGULFING" and r["candle_direction"] == "BEARISH"


def test_piercing_must_close_past_the_MIDPOINT_of_the_prior_body():
    down = _bar(110, 110.5, 99.5, 100)
    # opens below the prior low, closes above the midpoint (105) -> piercing
    assert _detect(_flat(1) + [down, _bar(99, 107, 98.9, 106)])["candle"] == "PIERCING"
    # same gap-down open, but closes short of the midpoint -> nothing
    assert _detect(_flat(1) + [down, _bar(99, 104, 98.9, 103)])["candle"] != "PIERCING"


def test_dark_cloud_is_the_bearish_mirror_of_piercing():
    up = _bar(100, 110.5, 99.5, 110)
    r = _detect(_flat(1) + [up, _bar(111, 111.5, 103, 104)])
    assert r["candle"] == "DARK_CLOUD" and r["candle_direction"] == "BEARISH"


def test_a_harami_needs_a_SMALL_inner_body_not_just_an_inside_bar():
    """An inside bar with a full-sized body is a different thing — AQE already
    ships `inside_bar` for that. The harami is the PAUSE."""
    big_down = _bar(110, 110.5, 99.5, 100)
    assert _detect(_flat(1) + [big_down, _bar(102, 104, 101.5, 103)])["candle"] \
        == "BULLISH_HARAMI"
    # inside the prior RANGE but its body is nearly as big -> not a harami
    assert _detect(_flat(1) + [big_down, _bar(109, 109.5, 101, 101.5)])["candle"] \
        != "BULLISH_HARAMI"


# ------------------------------------------------------------- three bar

def test_a_morning_star_needs_a_SMALL_middle_candle():
    down = _bar(110, 110.5, 99.5, 100)
    star = _bar(98, 98.8, 97, 98.2)
    up = _bar(98.5, 106.5, 98.4, 106)
    r = _detect([down, star, up])
    assert r["candle"] == "MORNING_STAR" and r["candle_direction"] == "BULLISH"
    # a big middle candle is just a two-day reversal, not a star
    big_middle = _bar(99, 99.2, 90, 90.5)
    assert _detect([down, big_middle, up])["candle"] != "MORNING_STAR"


def test_an_evening_star_is_the_bearish_mirror():
    up = _bar(100, 110.5, 99.5, 110)
    star = _bar(112, 113, 111.5, 112.3)
    down = _bar(111.5, 111.6, 103, 103.5)
    r = _detect([up, star, down])
    assert r["candle"] == "EVENING_STAR" and r["candle_direction"] == "BEARISH"


def test_three_white_soldiers_need_three_decisive_bodies():
    good = [_bar(100, 105.2, 99.9, 105), _bar(104, 109.2, 103.9, 109),
            _bar(108, 113.2, 107.9, 113)]
    assert _detect(good)["candle"] == "THREE_WHITE_SOLDIERS"
    # three up days, but all wick and no body
    weak = [_bar(100, 108, 96, 101), _bar(101, 109, 97, 102), _bar(102, 110, 98, 103)]
    assert _detect(weak)["candle"] != "THREE_WHITE_SOLDIERS"


def test_three_black_crows_is_the_bearish_mirror():
    bars = [_bar(113, 113.1, 107.8, 108), _bar(109, 109.1, 103.8, 104),
            _bar(105, 105.1, 99.8, 100)]
    r = _detect(bars)
    assert r["candle"] == "THREE_BLACK_CROWS" and r["candle_direction"] == BEARISH \
        if (BEARISH := "BEARISH") else False


# ---------------------------------------------------------- precedence

def test_the_widest_context_wins_when_several_fire():
    """A three-bar reversal says more than the shape of its last candle alone.
    The ordering is a convention, and it is applied consistently."""
    down = _bar(110, 110.5, 99.5, 100)
    star = _bar(98.3, 98.8, 97, 98.0)      # small RED body, so it can be engulfed
    up = _bar(97.9, 106.5, 97.8, 106)      # ALSO a bullish engulfing of `star`
    assert C._two_bar(*_series([down, star, up])) is not None, "fixture is not ambiguous"
    assert _detect([down, star, up])["candle"] == "MORNING_STAR"


# ------------------------------------------------------------- contract

def test_an_ordinary_bar_reads_blank_with_every_key_present():
    r = _detect(_flat(3) + [_bar(100, 102, 98, 101)])
    assert r["candle"] is None
    for k in ("candle", "candle_direction", "candle_date"):
        assert k in r


def test_degenerate_input_never_raises():
    for bad in ([], [_bar(np.nan, np.nan, np.nan, np.nan)],
                [_bar(100, 100, 100, 100)]):
        assert C.detect_candle(*_series(bad)) if bad else C.detect_candle([], [], [], [])


def test_a_single_bar_of_history_still_gets_a_read():
    """Weekly data on a young listing has few bars. One bar cannot make a star,
    but it can make a doji, and refusing to read it would be a silent gap."""
    r = _detect([_bar(100, 103, 97, 100.1)])
    assert r["candle"] == "DOJI"


def test_the_date_of_the_bar_is_carried():
    o, h, l, c = _series(_flat(2) + [_bar(100, 106, 99.5, 100.3)])
    r = C.detect_candle(o, h, l, c, dates=["2026-08-04", "2026-08-05", "2026-08-06"])
    assert r["candle_date"] == "2026-08-06"


def test_no_probability_rides_along():
    """Same ruling as the chart patterns: a visual flag, not a signal."""
    r = _detect(_flat(2) + [_bar(100, 100.6, 94, 99.6)])
    assert not any("rate" in k or "_p" == k[-2:] or "prob" in k for k in r)
