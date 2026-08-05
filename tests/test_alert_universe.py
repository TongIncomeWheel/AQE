"""Alert universe, event rules and ledger tests.

The theme is that every threshold here was WRONG before, in a way that was
invisible from the output: a flat 5% stop band meant 0.4R on one name and 2.5R
on another; a +2% "breakout" fired below real resistance on 37 of 50 names;
"near a structural level" caught 72% of the universe. So the tests assert the
property that makes each rule meaningful, not just that it fires.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import config as C
from src.alerts import engine as E
from src.alerts import intraday as I

_ET = ZoneInfo("America/New_York")


def _at(h, m):
    return datetime(2026, 8, 5, h, m, tzinfo=_ET)


# --------------------------------------------------------------- universe

@pytest.mark.parametrize("rec,expected", [
    ({"on_longlist": True, "on_elder": True}, True),
    ({"on_longlist": True, "on_qs": True}, True),
    ({"on_elder": True, "on_qs": True}, True),
    ({"on_qs": True}, True),                       # QS-only earns its place
    ({"on_longlist": True}, False),                # single lens is not enough
    ({"on_elder": True}, False),
    ({}, False),
])
def test_strength_gate(rec, expected):
    assert E.in_alert_universe(rec) is expected


def test_held_names_bypass_the_strength_gate():
    """You own it — conviction is irrelevant to risk."""
    ex = {"held_positions": [{"ticker": "AAA"}],
          "daily_list": [{"ticker": "BBB", "on_longlist": True}]}
    mon = E.monitored(ex)
    assert [m["ticker"] for m in mon] == ["AAA"]      # BBB is single-lens
    assert mon[0]["is_held"] is True


def test_retired_radar_pool_is_no_longer_a_source():
    ex = {"held_positions": [],
          "daily_list": [],
          "_radar_pool": [{"ticker": "RADAR", "on_longlist": True,
                           "on_elder": True}]}
    assert E.monitored(ex) == []


# ------------------------------------------------------------ event rules

def _rec(**over):
    r = {"ticker": "T", "entry": 100.0,
         "bracket": {"valid": True, "stop": 92.0, "risk": 8.0,
                     "targets": [{"tp": "TP1", "price": 112.0}]}}
    r.update(over)
    return r


def _fired(rec, quote, is_held=False):
    return {t["level"] for t in
            E.evaluate("T", "daily_list", is_held, rec, quote)}


def test_move_fires_on_two_percent_either_way():
    assert "MOVE" in _fired(_rec(), {"price": 102.5, "prev_close": 100.0})
    assert "MOVE" in _fired(_rec(), {"price": 97.5, "prev_close": 100.0})
    assert "MOVE" not in _fired(_rec(), {"price": 101.0, "prev_close": 100.0})


def test_bos_needs_the_daily_structure_read_not_a_percentage():
    """The replacement for the old +2%-over-prior-close 'breakout'."""
    quiet = {"price": 100.5, "prev_close": 100.0}
    assert "BOS" not in _fired(_rec(), quiet)
    rec = _rec(structure_shift="BULLISH_BOS",
               last_pivot_high={"price": 99.0})
    assert "BOS" in _fired(rec, quiet)


def test_bos_does_not_fire_for_held_names():
    rec = _rec(structure_shift="BULLISH_BOS", last_pivot_high={"price": 99.0})
    assert "BOS" not in _fired(rec, {"price": 100.5, "prev_close": 100.0},
                               is_held=True)


def test_at_level_uses_decision_levels_only():
    """Not all ~15 structural levels — that caught 72% of the universe.

    A fib sitting 1% away must NOT fire; the stop, TP1 and pivot high must.
    """
    rec = _rec(fib_618=99.5, ma_50=99.6, ma_200=100.4)
    assert "AT_LEVEL" not in _fired(rec, {"price": 100.0, "prev_close": 100.0})
    assert "AT_LEVEL" in _fired(rec, {"price": 92.5, "prev_close": 92.5})   # stop
    assert "AT_LEVEL" in _fired(rec, {"price": 111.0, "prev_close": 111.0})  # TP1


def test_at_level_fires_once_per_poll():
    rec = _rec(last_pivot_high={"price": 92.3})     # pivot AND stop both near
    trig = E.evaluate("T", "daily_list", False, rec,
                      {"price": 92.4, "prev_close": 92.4})
    assert sum(1 for t in trig if t["level"] == "AT_LEVEL") == 1


# ------------------------------------------------- near-stop is R-relative

def test_near_stop_means_the_same_on_a_cheap_and_an_expensive_name():
    """The old flat 5% spanned 0.4R to 2.5R across the universe."""
    cheap = _rec(entry=20.0, bracket={"valid": True, "stop": 18.0, "risk": 2.0,
                                      "targets": []})
    dear = _rec(entry=500.0, bracket={"valid": True, "stop": 450.0,
                                      "risk": 50.0, "targets": []})
    # both exactly 0.25R above their stop
    assert "NEAR_STOP" in _fired(cheap, {"price": 18.5, "prev_close": 18.5})
    assert "NEAR_STOP" in _fired(dear, {"price": 462.5, "prev_close": 462.5})
    # both exactly 0.5R above — neither should fire
    assert "NEAR_STOP" not in _fired(cheap, {"price": 19.0, "prev_close": 19.0})
    assert "NEAR_STOP" not in _fired(dear, {"price": 475.0, "prev_close": 475.0})


def test_held_risk_unit_comes_from_the_trade_actually_taken():
    """Held rows carry an INVALID bracket (risk None) in the live export.

    Without falling back to entry - held_sl every held position would silently
    revert to the flat-% rule, which is the behaviour this replaces.
    """
    rec = {"ticker": "SPGI", "entry": 450.36, "held_sl": 420.73,
           "bracket": {"valid": False}}
    t = [x for x in E.evaluate("SPGI", "held", True, rec,
                               {"price": 428.0, "prev_close": 428.0})
         if x["level"] == "NEAR_STOP"]
    assert t and "R above stop" in t[0]["note"]
    assert "fallback" not in t[0]["note"]


def test_veto_on_a_held_name_fires_without_any_price_level():
    rec = {"ticker": "T", "entry": 100.0, "bracket": {},
           "qs": {"vetoes": ["fading laggard"]}}
    assert "VETO_HELD" in _fired(rec, {"price": 100.0, "prev_close": 100.0},
                                 is_held=True)
    assert "VETO_HELD" not in _fired(rec, {"price": 100.0, "prev_close": 100.0})


# --------------------------------------------------------------- intraday

def test_a_normal_day_never_reads_as_a_coil_at_any_hour():
    """The clock bug: raw range vs full-day ATR calls every morning a coil."""
    import math
    for h, m in ((9, 50), (10, 30), (11, 30), (13, 0), (15, 0)):
        el = I.session_elapsed_fraction(_at(h, m))
        rng = 3.6 * math.sqrt(el)              # exactly normal for the hour
        q = {"price": 100.0, "day_high": 100 + rng / 2, "day_low": 100 - rng / 2,
             "open": 100.0, "prev_close": 100.0,
             "volume": 1e6 * el, "avg_volume": 1e6}
        r = I.measures(q, atr14=3.6, now=_at(h, m))
        assert r["range_ratio"] == pytest.approx(1.0, abs=0.02)
        assert r["signature"] is None


def test_the_same_tightness_reads_coil_at_every_hour():
    import math
    for h, m in ((10, 30), (13, 0), (15, 0)):
        el = I.session_elapsed_fraction(_at(h, m))
        rng = 3.6 * math.sqrt(el) * 0.45
        q = {"price": 100 + rng * 0.40, "day_high": 100 + rng * 0.45,
             "day_low": 100 - rng * 0.55, "open": 100.0, "prev_close": 100.0,
             "volume": 0.9e6 * el, "avg_volume": 1e6}
        assert I.measures(q, 3.6, _at(h, m))["signature"] == "COIL"


def test_too_early_in_the_session_classifies_nothing():
    q = {"price": 100, "day_high": 100.2, "day_low": 99.9, "open": 100,
         "prev_close": 100, "volume": 1e5, "avg_volume": 1e6}
    r = I.measures(q, 3.6, _at(9, 35))
    assert r["range_ratio"] is None and r["signature"] is None


def test_missing_range_is_not_treated_as_tight():
    r = I.measures({"price": 100, "open": 100}, 3.6, _at(13, 0))
    assert r["position_in_range"] is None and r["signature"] is None


def test_intraday_signatures_are_ledger_only_by_default():
    assert C.EMAIL_INTRADAY_SIGNATURES is False
