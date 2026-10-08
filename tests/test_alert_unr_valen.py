"""Valen's U&R across the two timeframes (PM 2026-10-09): the DAILY chart picks
the stock and the day (candidate), the INTRADAY chart picks the entry (a 15-min
candle closing above VWAP), stop = low of day. The two are not chained: the
trigger does not wait for the daily level to be reclaimed."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.alerts import condition_state as CS
from src.alerts import emailer as E
from src.alerts import live_measures as LM
from src.alerts import live_unr as LU

_ET = ZoneInfo("America/New_York")


def _history(n=160, a=40.0, b=100.0, end=date(2026, 10, 6), vols=None):
    c = np.geomspace(a, b, n)
    return [{"date": str(end - timedelta(days=n - 1 - i)), "open": c[i] * 0.998,
             "high": c[i] * 1.006, "low": c[i] * 0.994, "close": float(c[i]),
             "volume": float((vols or {}).get(i, 1e6))} for i in range(n)]


def _ema21(h):
    return float(pd.Series([r["close"] for r in h]).ewm(span=21, adjust=False).mean().iloc[-1])


def _under(h, closes_under, lows_under):
    """Set the last len(closes_under) sessions' closes to fractions of the
    EMA21 and their lows to fractions of it. The EMA moves as the closes are
    lowered, so iterate to a fixed point: the last close really ends UNDER the
    final EMA21 level."""
    k = len(closes_under)
    e = _ema21(h)
    for _ in range(8):
        for i, cl in enumerate(closes_under):
            h[-k + i]["close"] = e * cl
        e = _ema21(h)
    for i, lo in enumerate(lows_under):
        h[-k + i]["low"] = e * lo
    return e


# ------------------------------------------------------------- the candidate

def test_undercut_today_and_reclaimed_is_a_candidate_with_the_reclaim_ticked():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985)
    assert r["status"] == LU.ARMED
    a = next(x for x in r["armed"] if x["name"] == "EMA21")
    assert a["when"] == "today" and a["reclaimed"] is True and a["spot_pct"] > 0


def test_undercut_today_and_still_under_is_still_a_candidate_not_reclaimed():
    """PM 2026-10-09: the daily reclaim is a tick, not a gate."""
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 0.995, day_low=e * 0.985)
    a = next(x for x in r["armed"] if x["name"] == "EMA21")
    assert r["status"] == LU.ARMED and a["reclaimed"] is False and a["spot_pct"] < 0


def test_an_undercut_two_sessions_ago_still_under_at_the_last_close_is_a_candidate():
    h = _history()
    e = _under(h, closes_under=(0.975, 0.99, 0.992), lows_under=(0.96, 0.985, 0.99))
    r = LU.evaluate(h, spot=e * 1.004, day_low=e * 0.998)        # today never dipped
    a = next(x for x in r["armed"] if x["name"] == "EMA21")
    assert r["status"] == LU.ARMED and a["when"] == "yesterday"      # the most recent undercut


def test_an_undercut_that_already_closed_back_above_is_not_a_candidate():
    h = _history()
    e = _ema21(h)
    h[-2].update({"low": e * 0.97, "close": e * 0.98})
    h[-1].update({"close": e * 1.02, "low": e * 1.005})           # reclaim day was yesterday
    r = LU.evaluate(h, spot=e * 1.03, day_low=e * 1.012)
    assert not [x for x in r["armed"] if x["name"] == "EMA21"]


def test_nothing_undercut_is_not_met_with_the_lookback_in_the_reason():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.09, day_low=e * 1.065)
    assert r["status"] == LU.NOT_MET and "last 3 sessions" in r["reason"]


def test_a_falling_ema21_is_not_an_uptrend_pullback():
    h = _history(a=100.0, b=60.0)
    r = LU.evaluate(h, spot=61.0, day_low=58.0)
    assert r["status"] == LU.NOT_MET and "EMA21" in r["reason"]


def test_a_breakdown_is_not_a_flush():
    """AMD, 2026-10-09: 'undercut Trendline 688.66 (low 632.46), spot 7.2% under'
    went out as U&R ENTRY. A dip deeper than 2 daily ranges, or a level price is
    still more than 1.5 daily ranges under, is a breakdown."""
    h = _history()
    e = _ema21(h)
    deep = LU.evaluate(h, spot=e * 1.002, day_low=e * 0.93)          # 7% flush, back at the line
    assert not [x for x in deep["armed"] if x["name"] == "EMA21"]
    far = LU.evaluate(h, spot=e * 0.93, day_low=e * 0.92)            # still 7% under it
    assert not [x for x in far["armed"] if x["name"] == "EMA21"]
    ok = LU.evaluate(h, spot=e * 1.002, day_low=e * 0.985)
    assert [x for x in ok["armed"] if x["name"] == "EMA21"]


def test_unknown_never_a_silent_not_met_when_data_is_missing():
    assert LU.evaluate(None, 100.0, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history()[:30], 100.0, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history(), None, 99.0)["status"] == LU.UNKNOWN
    assert LU.evaluate(_history(), 100.0, None)["status"] == LU.UNKNOWN


def test_levels_are_valens_four_types_only():
    r = LU.evaluate(_history(), spot=101.0, day_low=100.5)
    names = {x["name"] for x in r["levels"]}
    assert {"EMA9", "EMA21"} <= names
    assert names <= {"Swing low", "Trendline", "EMA9", "EMA21", "Gap"}
    json.dumps(r)                                                    # JSON-safe


def test_stop_is_todays_low_of_day_and_volume_marks_never_decide_the_status():
    n = 160
    h = _history(vols={i: 4e5 for i in range(n - 3, n)})
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, vol_x=0.2)
    assert r["stop"] == round(e * 0.985, 2) and r["status"] == LU.ARMED
    assert r["volume"] == {"pullback_dry": True, "reclaim_x": 0.2, "reclaim_ok": False}
    ok = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, vol_x=1.4)
    assert ok["volume"]["reclaim_ok"] is True


def test_a_panel_row_for_today_is_ignored():
    h = _history(end=date(2026, 10, 7))
    e = _ema21(h[:-1])
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, today=date(2026, 10, 7))
    assert r["status"] == LU.ARMED


# -------------------------------------------------------------- VWAP trigger

def _bar(hh, mm, o, h, l, c, v=1000):
    return {"date": f"2026-10-07 {hh:02d}:{mm:02d}:00", "open": o, "high": h, "low": l,
            "close": c, "volume": v}


def test_wait_while_the_candles_close_under_vwap():
    bars = [_bar(9, 30, 100, 100.5, 99.5, 99.8, 5000), _bar(9, 45, 99.8, 100.0, 99.0, 99.2, 3000)]
    t = LM.vwap_trigger(bars)
    assert t["state"] == "WAIT" and t["vwap"] > t["last_close"]


def test_triggered_when_a_candle_closes_above_vwap_after_being_below():
    bars = [_bar(9, 30, 100, 100.2, 98.8, 99.0, 5000), _bar(9, 45, 99.0, 99.2, 98.5, 98.7, 4000),
            _bar(10, 0, 98.7, 100.4, 98.6, 100.2, 4000)]
    t = LM.vwap_trigger(bars)
    assert t["state"] == "TRIGGERED" and t["was_below"] is True
    assert t["at"] == "10:15" and t["entry"] == 100.2


def test_above_vwap_since_the_open_is_not_a_trigger_there_was_no_dip_to_reclaim():
    bars = [_bar(9, 30, 100, 101, 99.9, 100.9, 5000), _bar(9, 45, 100.9, 101.5, 100.8, 101.4, 4000)]
    assert LM.vwap_trigger(bars)["state"] == "ABOVE"
    # one bar in: VWAP is just that bar's own average -- never a trigger on its own
    assert LM.vwap_trigger([_bar(9, 30, 100, 100.4, 99.9, 100.3, 5000)])["state"] == "ABOVE"


def test_not_ready_without_bars():
    assert LM.vwap_trigger([])["state"] == "NOT_READY"
    assert LM.vwap_trigger([{"date": "2026-10-07 08:00:00", "high": 1, "low": 1,
                             "close": 1, "volume": 1}])["state"] == "NOT_READY"


# ------------------------------------------------------------ state machine

def _ev(armed=False, trig=False, spot=None, stop=None, **k):
    return {"buy_met": False, "unr_armed": armed or trig, "unr_trigger": trig,
            "unr_spot": spot, "unr_stop": stop, **k}


def test_candidate_card_first_then_the_trigger_card_each_once():
    st = {}
    assert CS.advance(st, "2026-10-07", "X", _ev(armed=True)) == ["UNR_ARMED"]
    assert CS.advance(st, "2026-10-07", "X", _ev(armed=True)) == []
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=101, stop=98)) == ["UNR_TRIGGER"]
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=101, stop=98)) == []


def test_a_name_armed_and_triggered_on_the_same_cycle_gets_the_trigger_card_only():
    st = {}
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=101, stop=98)) == ["UNR_TRIGGER"]
    assert CS.advance(st, "2026-10-07", "X", _ev(armed=True)) == []     # no late candidate card


def test_the_trigger_does_not_need_the_daily_level_reclaimed():
    """The whole point of the fix: nothing in the state machine reads the
    reclaim. A trigger on an armed name fires on its own."""
    st = {}
    CS.advance(st, "2026-10-07", "X", _ev(armed=True))
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=99.0, stop=98.5)) == ["UNR_TRIGGER"]


def test_failed_only_after_a_trigger_and_only_under_the_stop_set_at_trigger_time():
    st = {}
    CS.advance(st, "2026-10-07", "X", _ev(armed=True))
    assert CS.advance(st, "2026-10-07", "X", _ev(armed=True, spot=90.0, stop=95.0)) == []   # no trigger yet
    CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=101.0, stop=98.0))
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=98.5, stop=97.0)) == []    # above 98
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=97.9, stop=97.0)) == ["UNR_FAILED"]
    assert CS.advance(st, "2026-10-07", "X", _ev(trig=True, spot=90.0, stop=90.0)) == []     # once


def test_nothing_fires_for_a_name_that_is_not_armed():
    assert CS.advance({}, "2026-10-07", "X", _ev()) == []


# --------------------------------------------------------------------- card

def _row():
    return {"ticker": "CAT", "class": "AQE_LONGLIST", "aqe_default": True,
            "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 858.87}],
                                      "confirm": [{"w": "vol_x_ge", "x": 1.0}]},
                           "exits": [], "analysts": []},
            "levels": {"stop": 822.64, "tp": [887.91, 909.6, 931.35]}}


def _evr(words=("TRUE", "NOT_YET")):
    sh = _row()["conditions"]["shared"]
    return {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False, "exit_warn": None,
            "exit_hit": None, "n_counting": 0, "n_lit": 0, "no_shared_buy": False,
            "analyst_detail": {},
            "shared_buy_detail": [(sh["buy"][0], words[0])],
            "shared_confirm_detail": [(sh["confirm"][0], words[1])]}


def _live(trigger=None, status="ARMED", reclaimed=False, spot=849.0):
    armed = []
    if status == "ARMED":
        pct = round((spot / 851.4 - 1) * 100, 2)
        armed = [{"name": "EMA21", "level": 851.4, "low": 846.2, "when": "yesterday",
                  "reclaimed": reclaimed, "spot_pct": pct}]
    unr = {"status": status, "reason": "no shallow dip under a support level in the last 3 sessions",
           "armed": armed, "stop": 846.2,
           "levels": [{"name": "EMA21", "level": 851.4}, {"name": "Gap", "level": 359.5}],
           "volume": {"pullback_dry": True, "reclaim_x": 1.3, "reclaim_ok": True}}
    return {"price": spot, "day_low": 846.2, "unr": unr,
            "vwap_trigger": trigger or {"state": "WAIT", "vwap": 865.28, "last_close": 862.0}}


def test_setup_forming_card_says_what_to_wait_for_in_plain_english():
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_ARMED"], _live())
    assert c["headline"] == "CAT $849.00 · 🟡 U&R SETUP FORMING"
    assert c["lines"][0] == "Entry signal comes when a 15-min candle closes above VWAP (865.28)"
    assert c["lines"][1] == "Stop would be 846.20 (today's low), 0.3% below price"
    assert c["lines"][2] == ("Dipped below the 21-day average (851.40) yesterday; "
                             "price is still 0.3% under it")
    assert c["lines"][3] == "Volume confirms ✓"
    assert len(c["lines"]) <= 5


def test_entry_signal_card_leads_with_what_triggered_the_stop_and_the_risk():
    trig = {"state": "TRIGGERED", "vwap": 848.5, "last_close": 849.5, "was_below": True,
            "at": "10:15", "entry": 849.5}
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_TRIGGER"], _live(trig))
    assert c["headline"] == "CAT $849.00 · 🟢 U&R ENTRY SIGNAL"
    assert c["lines"][0] == "A 15-min candle closed above VWAP at 10:15 (price 849.50)"
    assert c["lines"][1] == "Stop: 846.20 (today's low), 0.3% below price"
    assert "price is still 0.3% under it" in c["lines"][2]        # the reclaim is info, not a gate


def test_the_reclaim_is_a_tick_in_the_setup_sentence():
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_ARMED"],
                               _live(reclaimed=True, spot=864.99))
    assert any(l.endswith("and is back above it ✓") for l in c["lines"])


def test_only_the_watch_outs_are_shown_for_volume():
    live = _live()
    live["unr"]["volume"] = {"pullback_dry": False, "reclaim_x": 0.6, "reclaim_ok": False}
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_ARMED"], live)
    assert "Watch: buying volume only 0.6× normal; the pullback ran on heavy volume" in c["lines"]


def test_nearby_levels_hide_the_levels_nobody_needs_and_use_plain_names():
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_ARMED"], _live())
    line = next(l for l in c["lines"] if l.startswith("Nearby levels"))
    assert line == "Nearby levels: 21-day average 851.40"           # the 359.50 gap is 58% away


def test_failed_card_is_one_plain_sentence():
    ev = _evr()
    ev["unr_stop"] = 846.2
    c = E.build_condition_card("CAT", _row(), ev, ["UNR_FAILED"], _live())
    assert c["headline"] == "CAT $849.00 · 🟠 U&R FAILED"
    assert c["lines"] == ["Price 849.00 fell under the stop (846.20) that was set at the entry signal"]


def test_a_buy_card_leads_with_the_state_and_one_u_and_r_line():
    c = E.build_condition_card("CAT", _row(), _evr(("TRUE", "FALSE")), ["CONDITION_MET"],
                               _live(status="NOT_MET"))
    assert c["headline"] == "CAT $849.00 · 🟢 BUY CONDITIONS MET · AQE default criteria"
    assert c["lines"][-1] == "U&R: no setup"
    assert len(c["lines"]) <= 4


def test_the_card_has_none_of_the_jargon_the_pm_rejected():
    trig = {"state": "TRIGGERED", "vwap": 848.5, "last_close": 849.5, "was_below": True,
            "at": "10:15", "entry": 849.5}
    for states in (["UNR_ARMED"], ["UNR_TRIGGER"]):
        c = E.build_condition_card("CAT", _row(), _evr(), states, _live(trig))
        text = "\n".join([c["headline"]] + c["lines"])
        for gone in ("EMA", "Trendline", "◌", "ref ", "Ref:", "open-range", "MET ·", "CANDIDATE",
                     "reclaim 0.", "Undercut"):
            assert gone not in text, gone


def test_buy_line_says_watching_while_words_are_pending_not_not_met():
    pending = E._buy_line(_row(), _evr(("NOT_YET", "NOT_YET")), ["UNR_ARMED"], _live())
    assert pending.startswith("Buy conditions (AQE default) ◌ WATCHING")
    failed = E._buy_line(_row(), _evr(("TRUE", "FALSE")), ["UNR_ARMED"], _live())
    assert failed.startswith("Buy conditions (AQE default) ✗ NOT MET")


def test_duplicate_word_categories_are_merged_into_one_mark():
    """Screenshot 2026-10-09: 'price ◌ · price ◌ · VWAP ◌'."""
    row = _row()
    sh = row["conditions"]["shared"]
    sh["buy"] = [{"w": "h1_close_above", "level": 100.5}, {"w": "h1_close_above", "level": 99.0}]
    ev = _evr()
    ev["shared_buy_detail"] = [(sh["buy"][0], "NOT_YET"), (sh["buy"][1], "NOT_YET")]
    ev["shared_confirm_detail"] = [({"w": "above_vwap_s"}, "NOT_YET")]
    line = E._buy_line(row, ev, ["UNR_ARMED"], _live())
    assert line.count("price") == 1 and "price ◌ · VWAP ◌" in line
    ev["shared_buy_detail"] = [(sh["buy"][0], "TRUE"), (sh["buy"][1], "FALSE")]
    assert "price ✗" in E._buy_line(row, ev, ["UNR_ARMED"], _live())


# ------------------------------------------------------------------- digest

def test_setups_forming_collapse_to_plain_one_line_rows_and_entry_signals_lead():
    cands = [(f"T{i}", _row(), _evr(), ["UNR_ARMED"], _live()) for i in range(16)]
    trig = {"state": "TRIGGERED", "vwap": 848.5, "last_close": 849.5, "was_below": True,
            "at": "10:15", "entry": 849.5}
    cards = cands + [("DOG", _row(), _evr(), ["UNR_TRIGGER"], _live(trig))]
    subj, plain, html = E.build_condition_digest(cards, datetime(2026, 10, 8, 9, 47, tzinfo=_ET))
    assert "17 cards" in subj and "U&R SETUP 16" in subj and "U&R ENTRY 1" in subj
    assert plain.index("DOG $849.00 · 🟢 U&R ENTRY SIGNAL") < plain.index("U&R setups forming (16)")
    assert plain.count("🟡 T") == 16
    assert ("🟡 T0 $849.00 — dipped below the 21-day average (851.40), still under it; "
            "stop would be 846.20") in plain
    assert "U&R setups forming (16)" in html


def test_a_setup_that_also_has_a_buy_state_stays_a_full_card():
    subj, plain, _ = E.build_condition_digest(
        [("CAT", _row(), _evr(), ["UNR_ARMED", "CONDITION_MET"], _live())],
        datetime(2026, 10, 8, 9, 47, tzinfo=_ET))
    assert "setups forming" not in plain and plain.count("CAT $") == 1


def test_digest_subject_counts_the_new_states():
    subj, _, _ = E.build_condition_digest(
        [("CAT", _row(), _evr(), ["UNR_ARMED"], _live()),
         ("DOG", _row(), _evr(), ["UNR_TRIGGER"], _live({"state": "TRIGGERED", "vwap": 1,
                                                          "last_close": 2, "was_below": True,
                                                          "at": "10:15", "entry": 2.0})),
         ("EEL", _row(), _evr(), ["UNR_FAILED"], _live())],
        datetime(2026, 10, 7, 11, 0, tzinfo=_ET))
    assert "U&R SETUP 1" in subj and "U&R ENTRY 1" in subj and "U&R FAILED 1" in subj


# ----------------------------------------------- Drive-synced condition state

def test_merge_keeps_what_either_poller_already_emailed():
    a = {"2026-10-07:X": {"stage": "CONDITION_MET", "emailed_today": ["CONDITION_MET"],
                          "chased": False, "analyst_out": False, "exit_line": False,
                          "unr": True, "unr_trigger": True, "unr_failed": False, "unr_stop": 98.0}}
    b = {"2026-10-07:X": {"stage": "WATCHING", "emailed_today": ["UNR_ARMED"],
                          "chased": True, "analyst_out": False, "exit_line": False,
                          "unr": False, "unr_trigger": False, "unr_failed": False,
                          "unr_stop": None},
         "2026-10-07:Y": {"stage": "WATCHING", "emailed_today": [], "chased": False,
                          "analyst_out": False, "exit_line": False}}
    m = CS.merge_states(a, b)
    x = m["2026-10-07:X"]
    assert x["emailed_today"] == ["CONDITION_MET", "UNR_ARMED"]
    assert x["stage"] == "CONDITION_MET" and x["unr"] and x["unr_trigger"] and x["chased"]
    assert x["unr_stop"] == 98.0 and "2026-10-07:Y" in m


def test_prune_is_relative_to_the_newest_run_date():
    st = {"2026-09-01:A": {}, "2026-10-06:B": {}, "2026-10-07:C": {}}
    assert set(CS._prune(st)) == {"2026-10-06:B", "2026-10-07:C"}


def test_save_and_load_go_through_drive_and_merge_across_pollers(tmp_path, monkeypatch):
    import src.data.gdrive_uploader as G
    drive = {}
    monkeypatch.setattr(G, "is_configured", lambda: True)
    monkeypatch.setattr(G, "download_text", lambda name: drive.get(name))
    monkeypatch.setattr(G, "upload_or_replace",
                        lambda name, payload, mime=None: drive.__setitem__(name, payload))
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "a" / "state.json")
    a = {}
    assert CS.advance(a, "2026-10-07", "CAT", _ev(armed=True)) == ["UNR_ARMED"]
    CS.save_condition_state(a)
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "b" / "state.json")
    b = CS.load_condition_state()                               # a fresh checkout
    assert CS.advance(b, "2026-10-07", "CAT", _ev(armed=True)) == []
    assert json.loads(drive[CS.STATE_FILENAME])["2026-10-07:CAT"]["unr"] is True


def test_drive_failures_fall_back_to_the_local_mirror(tmp_path, monkeypatch):
    import src.data.gdrive_uploader as G

    def boom(*a, **k):
        raise RuntimeError("drive down")
    monkeypatch.setattr(G, "is_configured", lambda: True)
    monkeypatch.setattr(G, "download_text", boom)
    monkeypatch.setattr(G, "upload_or_replace", boom)
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")
    st = {}
    CS.advance(st, "2026-10-07", "CAT", _ev(armed=True))
    CS.save_condition_state(st)
    assert CS.load_condition_state()["2026-10-07:CAT"]["unr"] is True


# ---------------------------------------------------------- end to end cycles

def _cycle_env(tmp_path, monkeypatch, h):
    from src.alerts import condition_cycle as CC
    from src.alerts import condition_data as CD
    from src.alerts import condition_ledger as CL
    import src.data.fmp_client as FC
    (tmp_path / "dh").mkdir()
    (tmp_path / "dh" / "2026-10-07.json").write_text(json.dumps({"HPE": h}))
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path / "vp")
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    monkeypatch.setattr(CD, "_panel_history", lambda tickers, today: {})
    monkeypatch.setattr(CL, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")
    bars = {"now": []}

    class _Client:
        def get_intraday_bars(self, tk, interval="15min", from_date=None, to_date=None):
            return bars["now"] if from_date == to_date else []

        def get_daily_bars(self, *a, **k):
            return None
    monkeypatch.setattr(FC, "FMPClient", _Client)
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    doc = {"run_date": "2026-10-07", "rows": [{
        "ticker": "HPE", "class": "ADVANCE", "atr_14d": 2.0,
        "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 999.0}],
                                  "confirm": [], "no_shared_buy": False},
                       "exits": [], "analysts": []}}]}

    def run(hh, mm, spot, low):
        q = {"HPE": {"price": spot, "prev_close": h[-1]["close"], "day_high": spot * 1.02,
                     "day_low": low, "open": spot},
             "SPY": {"price": 500.0, "prev_close": 499.0}}
        return CC.run_condition_cycle(doc, q, datetime(2026, 10, 7, hh, mm, tzinfo=_ET),
                                      run_date="2026-10-07")
    return run, bars, sent


def test_candidate_then_trigger_while_still_under_the_level_then_failed(tmp_path, monkeypatch):
    """The scenario that exposed the bug: the VWAP candle closes while spot is
    still just under the daily level. It must send the trigger card."""
    h = _history(end=date(2026, 10, 6))
    e = _ema21(h)
    run, bars, sent = _cycle_env(tmp_path, monkeypatch, h)
    bars["now"] = [_bar(9, 30, e * 0.995, e * 0.998, e * 0.985, e * 0.988, 9000),
                   _bar(9, 45, e * 0.988, e * 0.99, e * 0.985, e * 0.986, 8000)]
    s1 = run(10, 5, e * 0.987, e * 0.985)              # undercut today, candles under VWAP
    assert s1["fired"]["HPE"] == ["UNR_ARMED"]
    live1 = sent[-1][0][0][4]
    assert live1["vwap_trigger"]["state"] == "WAIT" and live1["unr"]["armed"][0]["reclaimed"] is False
    bars["now"] = bars["now"] + [_bar(10, 0, e * 0.986, e * 0.997, e * 0.985, e * 0.995, 9000)]
    s2 = run(10, 20, e * 0.995, e * 0.985)             # candle above VWAP; spot STILL under level
    assert s2["fired"]["HPE"] == ["UNR_TRIGGER"]
    live2 = sent[-1][0][0][4]
    assert live2["unr"]["armed"][0]["reclaimed"] is False        # trigger did not wait for it
    assert run(10, 35, e * 0.996, e * 0.985)["fired"] == {}
    s4 = run(10, 50, e * 0.98, e * 0.98)               # trades under the stop set at the trigger
    assert s4["fired"]["HPE"] == ["UNR_FAILED"]


def test_a_name_armed_from_yesterday_sends_one_candidate_card_at_the_open(tmp_path, monkeypatch):
    """Including a name that opens strong: above VWAP with no dip to reclaim is
    still a CANDIDATE, never an instant entry."""
    h = _history(end=date(2026, 10, 6))
    e = _under(h, closes_under=(0.975, 0.99, 0.992), lows_under=(0.96, 0.985, 0.99))
    run, bars, sent = _cycle_env(tmp_path, monkeypatch, h)
    bars["now"] = [_bar(9, 30, e * 0.992, e * 0.996, e * 0.99, e * 0.994, 9000)]
    s = run(9, 50, e * 0.995, e * 0.99)
    assert s["fired"]["HPE"] == ["UNR_ARMED"]
    assert run(10, 5, e * 0.996, e * 0.99)["fired"] == {}
