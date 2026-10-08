"""The U&R-first compact card layout (PM 2026-10-07). The U&R logic itself
(candidate / trigger / failed, reclaim as a tick) is tested in
test_alert_unr_valen.py; this file covers the card's shape."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import emailer as E

_ET = ZoneInfo("America/New_York")


def _row(default=True):
    return {"ticker": "CAT", "class": "AQE_LONGLIST", "aqe_default": default,
            "conditions": {"shared": {
                "buy": [{"w": "h1_close_above", "level": 858.87, "plain": "x"}],
                "confirm": [{"w": "vol_x_ge", "x": 1.0, "plain": "y"}],
                "chase": {"w": "close_above", "level": 884.64, "plain": "z"}},
                "exits": [], "analysts": []},
            "levels": {"stop": 822.64, "tp": [887.91, 909.60, 931.35]}}


def _ev(vol="FALSE"):
    sh = _row()["conditions"]["shared"]
    return {"buy_met": vol == "TRUE", "lit": [], "wrong_lit": [], "chased": False,
            "exit_warn": None, "exit_hit": None, "n_counting": 0, "n_lit": 0,
            "no_shared_buy": False, "analyst_detail": {},
            "shared_buy_detail": [(sh["buy"][0], "TRUE")],
            "shared_confirm_detail": [(sh["confirm"][0], vol)]}


def _live(status="ARMED", spot=864.99, trigger=None):
    unr = {"status": status, "reason": "no support level undercut in the last 3 sessions",
           "armed": [], "stop": 846.2,
           "levels": [{"name": "EMA9", "level": 858.9}, {"name": "EMA21", "level": 851.4},
                      {"name": "Trendline", "level": 849.0}],
           "volume": {"pullback_dry": True, "reclaim_x": 1.3, "reclaim_ok": True}}
    if status == "ARMED":
        unr["armed"] = [{"name": "EMA21", "level": 851.4, "low": 846.2, "when": "today",
                         "reclaimed": spot > 851.4, "spot_pct": round((spot / 851.4 - 1) * 100, 2)}]
    return {"price": spot, "day_low": 846.2, "day_high": 876.95,
            "opening_range": {"high": 866.8, "low": 851.47},
            "vwap": {"vwap": 865.28, "provisional": False}, "hourly_closes": [860.0, 866.0],
            "vol_x": {"so_far": 1.0},
            "ema": {"m15": {"ema8": 865.63, "ema20": 864.66, "spot_vs_8_pct": -0.1,
                            "spot_vs_20_pct": 0.0, "stack": "above", "slope8": "rising",
                            "slope20": "rising"},
                    "daily": {"ema8": 836.78, "ema20": 824.13, "spot_vs_8_pct": 3.4,
                              "spot_vs_20_pct": 5.0, "stack": "above", "slope8": "rising",
                              "slope20": "rising"}},
            "elder": {"elder_live": 10, "impulse_live": "GREEN", "elder_prev": 10},
            "unr": unr,
            "vwap_trigger": trigger or {"state": "WAIT", "vwap": 865.28, "last_close": 862.0}}


def _card(states, status="ARMED", spot=864.99, vol="FALSE", trigger=None):
    return E.build_condition_card("CAT", _row(), _ev(vol), states, _live(status, spot, trigger))


def test_headline_names_the_u_and_r_state_or_the_buy_state():
    assert _card(["UNR_ARMED"])["headline"] == "CAT @ 864.99 · 🟡 U&R CANDIDATE"
    trig = {"state": "TRIGGERED", "vwap": 865.28, "last_close": 866.0, "was_below": True,
            "at": "10:15", "entry": 866.0}
    assert _card(["UNR_TRIGGER"], trigger=trig)["headline"] == "CAT @ 864.99 · 🟢 U&R MET · ENTRY TRIGGER"
    assert _card(["CONDITION_MET"], status="NOT_MET")["headline"] == (
        "CAT @ 864.99 · 🟢 BUY CONDITIONS MET · AQE default criteria")


def test_a_buy_card_says_u_and_r_in_one_line_whatever_its_state():
    assert _card(["CONDITION_MET"], status="NOT_MET")["lines"][-1] == "U&R ✗ not met"
    assert _card(["CONDITION_MET"], status="UNKNOWN")["lines"][-1] == "U&R ◌ not checked"
    assert _card(["CONDITION_MET"])["lines"][-1].startswith("U&R candidate — Undercut EMA21")


def test_the_cat_card_no_longer_says_back_under_when_spot_is_above_the_line():
    """PM 2026-10-07: spot 864.99 vs a line at 858.87 was headed 'BACK UNDER THE
    LEVEL'. The volume confirm lapsed; price never fell back."""
    c = _card(["FAILED_PUSH"])
    text = "\n".join([c["headline"]] + c["lines"])
    assert "BACK UNDER" not in text
    assert "CONFIRMATION LOST — price still above the line" in c["headline"]
    assert "volume ✗" in text and "price ✓" in text
    low = E.build_condition_card("CAT", _row(), _ev(), ["FAILED_PUSH"], _live("NOT_MET", 850.0))
    assert "CONFIRMATION LOST" not in low["headline"]


def test_the_full_layout_also_stops_mislabelling_it():
    from src.alerts import config as C
    C.CONDITION_CARD_STYLE, old = "full", C.CONDITION_CARD_STYLE
    try:
        c = E.build_condition_card("CAT", _row(), _ev(), ["FAILED_PUSH"], _live())
    finally:
        C.CONDITION_CARD_STYLE = old
    assert "CONFIRMATION LOST" in c["headline"] and "BACK UNDER" not in c["headline"]
    assert "Price is still above 858.87" in c["summary"]


def test_buy_card_lines_are_the_marks_the_stop_and_the_one_target_that_matters():
    lines = _card(["CONDITION_MET"], vol="TRUE", status="NOT_MET")["lines"]
    assert lines[0] == "price ✓ · volume ✓ · entry 858.87 (spot +0.7%)"
    assert lines[1] == "Stop 822.64 · target TP2 909.60 (1.4R)"       # no TP1/TP3 ladder, no R:R essay


def test_u_and_r_card_reference_is_two_short_lines_of_numbers():
    lines = _card(["UNR_ARMED"])["lines"]
    ref = [l for l in lines if l.startswith("Ref:") or l.startswith("VWAP ")]
    assert ref[0] == "Ref: EMA9 858.90 · ▼EMA21 851.40 · Trendline 849.00"
    assert ref[1] == "VWAP 865.28 · open-range 866.80/851.47 · EMA8/20 15m 865.63/864.66"


def test_the_u_and_r_card_is_short_and_has_none_of_the_old_clutter():
    c = _card(["UNR_ARMED", "FAILED_PUSH"])
    assert len(c["lines"]) <= 6
    text = "\n".join(c["lines"])
    for gone in ("Structure:", "Entry readiness", "Analysts:", "Live:", "Bracket:", "R:R",
                 "UnR reference", "Elder", "chase"):
        assert gone not in text


def test_held_cards_are_untouched_by_the_compact_layout():
    card = E.build_held_card({"ticker": "ANET", "is_held": True, "kind": "near_stops",
                              "live_px": 199.1, "broker_stop": 197.05})
    assert "NEAR YOUR STOP — HELD POSITION" in card["headline"]
