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


def test_every_alert_carries_the_move_vs_cob_anchor():
    """PM ruling: whatever fired, the first question is how far it moved today."""
    rec = _rec(last_pivot_high={"price": 104.0})
    for t in E.evaluate("T", "daily_list", False, rec,
                        {"price": 103.0, "prev_close": 100.0}):
        assert "vs COB" in t["note"]
        assert t["chg_pct"] == pytest.approx(3.0, abs=0.1)
        assert t["prev_close"] == 100.0


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


def test_near_breakout_fires_below_the_pivot_only():
    """Named for what it is: climbing INTO the level, not sitting anywhere near it."""
    rec = _rec(last_pivot_high={"price": 104.0})
    assert "NEAR_BREAKOUT" in _fired(rec, {"price": 103.0, "prev_close": 100.0})
    assert "NEAR_BREAKOUT" not in _fired(rec, {"price": 98.0, "prev_close": 100.0})
    assert "NEAR_BREAKOUT" not in _fired(rec, {"price": 106.0, "prev_close": 100.0})


def test_near_breakout_is_suppressed_once_bos_has_fired():
    """"Approaching" a level the daily read says you broke is a contradiction."""
    rec = _rec(last_pivot_high={"price": 104.0}, structure_shift="BULLISH_BOS")
    fired = _fired(rec, {"price": 103.0, "prev_close": 100.0})
    assert "BOS" in fired and "NEAR_BREAKOUT" not in fired


def test_bos_says_so_when_price_slipped_back_under_intraday():
    """structure_shift is COB; live price can be under the level again."""
    rec = _rec(last_pivot_high={"price": 104.0}, structure_shift="BULLISH_BOS")
    t = [x for x in E.evaluate("T", "daily_list", False, rec,
                               {"price": 103.0, "prev_close": 100.0})
         if x["level"] == "BOS"]
    assert "back UNDER it intraday" in t[0]["note"]


def test_near_target_fires_below_tp1():
    rec = _rec()
    assert "NEAR_TARGET" in _fired(rec, {"price": 110.5, "prev_close": 100.0})
    assert "NEAR_TARGET" not in _fired(rec, {"price": 105.0, "prev_close": 100.0})


# ------------------------------------------------------------- near stop

def test_near_stop_is_a_plain_percentage_band(monkeypatch):
    """PM ruling: keep it simple. Within 5% above the stop, nothing cleverer."""
    rec = _rec()                                   # stop 92.00
    assert "NEAR_STOP" in _fired(rec, {"price": 94.0, "prev_close": 100.0})
    assert "NEAR_STOP" not in _fired(rec, {"price": 98.0, "prev_close": 100.0})
    assert "NEAR_STOP" not in _fired(rec, {"price": 91.0, "prev_close": 100.0})


def test_held_names_use_their_own_live_sl_not_the_structural_stop():
    """Held rows carry an INVALID bracket in the live export — the SL is theirs."""
    rec = {"ticker": "SPGI", "entry": 450.36, "held_sl": 420.73,
           "bracket": {"valid": False}}
    t = [x for x in E.evaluate("SPGI", "held", True, rec,
                               {"price": 435.0, "prev_close": 450.36})
         if x["level"] == "NEAR_STOP"]
    assert t and "420.73" in t[0]["note"]
    assert "SL" in t[0]["label"]


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


def test_a_signature_never_manufactures_an_alert_of_its_own():
    """A textbook COIL on a name doing nothing structural emails NOTHING.

    This is the property the retired EMAIL_INTRADAY_SIGNATURES flag was meant
    to guarantee and never did — nothing read it, so it guaranteed a comment.
    The guarantee lives in evaluate(): the signature is attached to triggers,
    it is never a trigger, so an unfitted threshold cannot page the PM.
    """
    import math
    el = I.session_elapsed_fraction(_at(13, 0))
    rng = 3.6 * math.sqrt(el) * 0.45                  # tight for the hour
    quote = {"price": 100 + rng * 0.40, "day_high": 100 + rng * 0.45,
             "day_low": 100 - rng * 0.55, "open": 100.0, "prev_close": 100.0,
             "volume": 0.9e6 * el, "avg_volume": 1e6}
    assert I.measures(quote, 3.6, _at(13, 0))["signature"] == "COIL"
    # ...and yet: no 2% move, no BOS, nowhere near stop or target.
    assert E.evaluate("T", "daily_list", False, _rec(), quote) == []


def test_the_signature_rides_along_on_an_alert_that_did_earn_its_place():
    rec = _rec(structure_shift="BULLISH_BOS", last_pivot_high={"price": 99.0})
    t = E.evaluate("T", "daily_list", False, rec,
                   {"price": 103.0, "prev_close": 100.0})
    assert t and all("intraday" in x for x in t)


def test_the_dead_email_switch_is_gone_not_merely_defaulted_off():
    """It claimed COIL/THRUST were ledger-only while they shipped in every
    email. A config that describes behaviour the code does not have is worse
    than no config."""
    assert not hasattr(C, "EMAIL_INTRADAY_SIGNATURES")
