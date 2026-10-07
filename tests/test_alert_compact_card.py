"""The U&R-first compact card (PM 2026-10-07): "what we need to know is if U&R
took place (met or not met) ... everything else is numbers for reference
under UnR reference", plus the same-day U&R read behind it (live_unr.py)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.alerts import condition_state as CS
from src.alerts import emailer as E
from src.alerts import live_unr as LU

_ET = ZoneInfo("America/New_York")


def _history(n=160, a=40.0, b=100.0, end=date(2026, 10, 1)):
    c = np.geomspace(a, b, n)
    return [{"date": str(end - timedelta(days=n - 1 - i)), "open": c[i] * 0.998,
             "high": c[i] * 1.006, "low": c[i] * 0.994, "close": float(c[i]), "volume": 1e6}
            for i in range(n)]


def _ema21(h):
    return float(pd.Series([r["close"] for r in h]).ewm(span=21, adjust=False).mean().iloc[-1])


# ------------------------------------------------------------------- live_unr

def test_met_when_a_level_was_undercut_today_and_spot_is_back_above():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985)
    assert r["status"] == LU.MET
    assert any(x["name"] == "EMA21" and x["spot_pct"] > 0 for x in r["hits"])
    assert all(isinstance(x["level"], float) for x in r["hits"])      # JSON-safe
    json.dumps(r)


def test_not_met_when_nothing_was_undercut_today():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.09, day_low=e * 1.065)     # never dipped under EMA8
    assert r["status"] == LU.NOT_MET and "no reference level undercut" in r["reason"]


def test_not_met_when_undercut_but_spot_is_still_under():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 0.99, day_low=e * 0.97)
    assert r["status"] == LU.NOT_MET and r["below"] and not r["hits"]


def test_unknown_never_a_silent_not_met_when_data_is_missing():
    assert LU.evaluate(None, 100.0, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history()[:30], 100.0, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history(), None, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history(), 100.0, None)["status"] == LU.UNKNOWN


def test_a_falling_50_day_is_not_an_uptrend_pullback():
    h = _history(a=100.0, b=60.0)
    r = LU.evaluate(h, spot=61.0, day_low=58.0)
    assert r["status"] == LU.NOT_MET and "50-day" in r["reason"]


def test_levels_are_listed_for_the_reference_block():
    r = LU.evaluate(_history(), spot=101.0, day_low=100.5)
    names = [x["name"] for x in r["levels"]]
    assert {"EMA8", "EMA10", "EMA21", "SMA50"} <= set(names)
    assert any(n.startswith("Wk EMA") for n in names)


# -------------------------------------------------------------- state machine

def test_unr_met_fires_once_per_name_per_day_independent_of_the_buy_lifecycle():
    st = {}
    ev = {"buy_met": False, "unr_met": True}
    assert CS.advance(st, "2026-10-07", "CAT", ev) == ["UNR_MET"]
    assert CS.advance(st, "2026-10-07", "CAT", ev) == []                 # not again today
    assert CS.advance(st, "2026-10-08", "CAT", ev) == ["UNR_MET"]        # a new day
    both = CS.advance({}, "2026-10-07", "X", {"buy_met": True, "unr_met": True})
    assert both == ["CONDITION_MET", "UNR_MET"]


# ----------------------------------------------------------------- the card

def _row(default=True):
    return {"ticker": "CAT", "class": "AQE_LONGLIST", "aqe_default": default,
            "conditions": {"shared": {
                "buy": [{"w": "h1_close_above", "level": 858.87, "plain": "x"}],
                "confirm": [{"w": "vol_x_ge", "x": 1.0, "plain": "y"}],
                "chase": {"w": "close_above", "level": 884.64, "plain": "z"}},
                "exits": [], "analysts": []},
            "levels": {"stop": 822.64, "tp": [887.91, 909.60, 931.35]}}


def _ev(vol="FALSE"):
    row = _row()
    sh = row["conditions"]["shared"]
    return {"buy_met": vol == "TRUE", "lit": [], "wrong_lit": [], "chased": False,
            "exit_warn": None, "exit_hit": None, "n_counting": 0, "n_lit": 0,
            "no_shared_buy": False, "analyst_detail": {},
            "shared_buy_detail": [(sh["buy"][0], "TRUE")],
            "shared_confirm_detail": [(sh["confirm"][0], vol)]}


def _live(status="MET", spot=864.99):
    unr = {"status": status, "hits": [], "below": [], "reason": None,
           "levels": [{"name": "EMA8", "level": 858.9}, {"name": "EMA21", "level": 851.4},
                      {"name": "Round 850", "level": 850.0}]}
    if status == "MET":
        unr["hits"] = [{"name": "EMA21", "level": 851.4, "low": 846.2, "spot_pct": 1.6}]
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
            "unr": unr}


def _card(states, status="MET", spot=864.99, vol="FALSE"):
    return E.build_condition_card("CAT", _row(), _ev(vol), states, _live(status, spot))


def test_headline_is_the_unr_verdict():
    assert _card(["UNR_MET"])["headline"] == "CAT @ 864.99 · 🟢 U&R MET"
    assert _card(["CONDITION_MET"], status="NOT_MET")["headline"] == "CAT @ 864.99 · ⚪ U&R NOT MET"
    assert "NOT CHECKED" in _card(["CONDITION_MET"], status="UNKNOWN")["headline"]


def test_first_line_says_what_was_undercut_and_that_spot_is_back_above():
    line = _card(["UNR_MET"])["lines"][0]
    assert line.startswith("U&R today ✓ MET — undercut EMA21 851.40")
    assert "spot 864.99 is back above" in line


def test_not_met_says_why_in_plain_words():
    c = _card(["CONDITION_MET"], status="NOT_MET")
    assert c["lines"][0] == "U&R today ✗ NOT MET — no daily level undercut today"
    live = _live("NOT_MET", 849.0)
    live["unr"]["below"] = [{"name": "EMA21", "level": 851.4, "low": 846.2}]
    c2 = E.build_condition_card("CAT", _row(), _ev(), ["CONDITION_MET"], live)
    assert "undercut EMA21 851.40 (low 846.20) but spot 849.00 is still under it" in c2["lines"][0]


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
    line = _card(["CONDITION_MET"], vol="TRUE")["lines"][1]
    assert line == "Buy conditions (AQE default) ✓ MET — price ✓ · volume ✓ · entry 858.87 (spot +0.7%)"


def test_bracket_is_a_single_line_with_the_rr_verdict():
    c = _card(["CONDITION_MET"])
    br = [l for l in c["lines"] if l.startswith("Bracket:")]
    assert len(br) == 1
    assert "TP2 909.60 (1.4R)" in br[0] and "R:R to TP2 1.4 — below the 2.0 gate" in br[0]


def test_reference_block_holds_the_numbers_and_marks_undercut_levels():
    lines = _card(["UNR_MET"])["lines"]
    i = next(k for k, l in enumerate(lines) if "UnR reference" in l)
    ref = "\n".join(lines[i + 1:])
    assert "▼EMA21 851.40" in ref and "Round 850" in ref and "850.00" not in ref.split("Round 850")[1][:6]
    assert "open-range 866.80/851.47" in ref and "low 846.20" in ref and "high 876.95" in ref
    assert "VWAP 865.28 (spot below, hourly close reclaimed it)" in ref
    assert "EMA 8/20: 15m 865.63/864.66 · daily 836.78/824.13" in ref
    assert "volume 1.0× · Elder 10/10 GREEN · chase line 884.64" in ref


def test_the_card_is_tight_and_has_no_word_by_word_lines():
    c = _card(["UNR_MET", "FAILED_PUSH"])
    assert len(c["lines"]) <= 12
    text = "\n".join(c["lines"])
    for gone in ("Structure:", "Volume:", "Entry readiness", "Analysts:", "Live:"):
        assert gone not in text


def test_digest_counts_unr_met_in_the_subject():
    subj, plain, _ = E.build_condition_digest(
        [("CAT", _row(), _ev(), ["UNR_MET"], _live())],
        datetime(2026, 10, 7, 11, 0, tzinfo=_ET))
    assert "U&R MET 1" in subj and "CAT @ 864.99 · 🟢 U&R MET" in plain


def test_held_cards_are_untouched_by_the_compact_layout():
    card = E.build_held_card({"ticker": "ANET", "is_held": True, "kind": "near_stops",
                              "live_px": 199.1, "broker_stop": 197.05})
    assert "NEAR YOUR STOP — HELD POSITION" in card["headline"]


# ----------------------------------------------------- end to end, one cycle

def test_a_cycle_fires_unr_met_from_the_cached_daily_history(tmp_path, monkeypatch):
    from src.alerts import condition_cycle as CC
    from src.alerts import condition_data as CD
    from src.alerts import condition_ledger as CL
    import src.data.fmp_client as FC

    class _Client:
        def get_intraday_bars(self, *a, **k):
            return []

        def get_daily_bars(self, *a, **k):
            return None

    h = _history(end=date(2026, 10, 6))
    e = _ema21(h)
    (tmp_path / "dh").mkdir()
    (tmp_path / "dh" / "2026-10-07.json").write_text(json.dumps({"HPE": h}))
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path / "vp")
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    monkeypatch.setattr(CD, "_panel_history", lambda tickers, today: {})
    monkeypatch.setattr(CL, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(FC, "FMPClient", _Client)
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    doc = {"run_date": "2026-10-07", "rows": [{
        "ticker": "HPE", "class": "ADVANCE", "atr_14d": 2.0,
        "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 999.0}],
                                  "confirm": [], "no_shared_buy": False},
                       "exits": [], "analysts": []}}]}
    quotes = {"HPE": {"price": e * 1.012, "prev_close": h[-1]["close"], "day_high": e * 1.02,
                      "day_low": e * 0.985, "open": e},
              "SPY": {"price": 500.0, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(doc, quotes, datetime(2026, 10, 7, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-07")
    assert summary["fired"]["HPE"] == ["UNR_MET"]
    ticker, row, ev, states, live = sent[0][0][0]
    assert states == ["UNR_MET"] and live["unr"]["status"] == "MET"
    card = E.build_condition_card(ticker, row, ev, states, live)
    assert card["headline"].endswith("🟢 U&R MET")
