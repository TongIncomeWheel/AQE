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


def test_headline_is_the_unr_verdict():
    assert _card(["UNR_ARMED"])["headline"] == "CAT @ 864.99 · 🟡 U&R CANDIDATE"
    assert _card(["CONDITION_MET"], status="NOT_MET")["headline"] == "CAT @ 864.99 · ⚪ U&R NOT MET"
    assert "NOT CHECKED" in _card(["CONDITION_MET"], status="UNKNOWN")["headline"]
    trig = {"state": "TRIGGERED", "vwap": 865.28, "last_close": 866.0, "was_below": True,
            "at": "10:15", "entry": 866.0}
    assert _card(["UNR_TRIGGER"], trigger=trig)["headline"] == "CAT @ 864.99 · 🟢 U&R MET · ENTRY TRIGGER"


def test_not_met_says_why_in_plain_words():
    c = _card(["CONDITION_MET"], status="NOT_MET")
    assert c["lines"][0] == "U&R ✗ NOT MET — no support level undercut in the last 3 sessions"


def test_the_cat_card_no_longer_says_back_under_when_spot_is_above_the_line():
    """PM 2026-10-07: spot 864.99 vs a line at 858.87 was headed 'BACK UNDER THE
    LEVEL'. The volume confirm lapsed; price never fell back."""
    c = _card(["FAILED_PUSH"])
    text = "\n".join([c["headline"]] + c["lines"])
    assert "BACK UNDER" not in text
    assert "CONFIRMATION LOST — price still above the line" in text
    assert "volume ✗" in text and "price ✓" in text
    low = E.build_condition_card("CAT", _row(), _ev(), ["FAILED_PUSH"], _live("NOT_MET", 850.0))
    assert "CONFIRMATION LOST" not in "\n".join(low["lines"])


def test_the_full_layout_also_stops_mislabelling_it():
    from src.alerts import config as C
    C.CONDITION_CARD_STYLE, old = "full", C.CONDITION_CARD_STYLE
    try:
        c = E.build_condition_card("CAT", _row(), _ev(), ["FAILED_PUSH"], _live())
    finally:
        C.CONDITION_CARD_STYLE = old
    assert "CONFIRMATION LOST" in c["headline"] and "BACK UNDER" not in c["headline"]
    assert "Price is still above 858.87" in c["summary"]


def test_buy_conditions_are_one_line_of_marks_with_the_entry_distance():
    lines = _card(["CONDITION_MET"], vol="TRUE", status="NOT_MET")["lines"]
    assert lines[1] == "Buy conditions (AQE default) ✓ MET — price ✓ · volume ✓ · entry 858.87 (spot +0.7%)"


def test_bracket_is_a_single_line_with_the_rr_verdict():
    c = _card(["CONDITION_MET"])
    br = [l for l in c["lines"] if l.startswith("Bracket:")]
    assert len(br) == 1
    assert "TP2 909.60 (1.4R)" in br[0] and "R:R to TP2 1.4 — below the 2.0 gate" in br[0]


def test_reference_block_holds_the_numbers_and_marks_undercut_levels():
    lines = _card(["UNR_ARMED"])["lines"]
    i = next(k for k, l in enumerate(lines) if "UnR reference" in l)
    ref = "\n".join(lines[i + 1:])
    assert "▼EMA21 851.40" in ref and "Trendline 849.00" in ref
    assert "open-range 866.80/851.47" in ref and "low 846.20" in ref and "high 876.95" in ref
    assert "VWAP 865.28 (spot below, hourly close reclaimed it)" in ref
    assert "EMA 8/20: 15m 865.63/864.66 · daily 836.78/824.13" in ref
    assert "volume 1.0× · Elder 10/10 GREEN · chase line 884.64" in ref


def test_the_card_is_tight_and_has_no_word_by_word_lines():
    c = _card(["UNR_ARMED", "FAILED_PUSH"])
    assert len(c["lines"]) <= 13
    text = "\n".join(c["lines"])
    for gone in ("Structure:", "Volume:", "Entry readiness", "Analysts:", "Live:"):
        assert gone not in text


def test_held_cards_are_untouched_by_the_compact_layout():
    card = E.build_held_card({"ticker": "ANET", "is_held": True, "kind": "near_stops",
                              "live_px": 199.1, "broker_stop": 197.05})
    assert "NEAR YOUR STOP — HELD POSITION" in card["headline"]
