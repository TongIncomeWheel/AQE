"""Valen's U&R, incorporated (PM 2026-10-08): reclaim day (the undercut may be
yesterday), his two volume marks, the 15-min VWAP entry trigger, stop = low of
day, the three one-shot states, and the Drive-synced condition state."""

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


def _history(n=160, a=40.0, b=100.0, end=date(2026, 10, 6), last=None, vols=None):
    c = np.geomspace(a, b, n)
    rows = [{"date": str(end - timedelta(days=n - 1 - i)), "open": c[i] * 0.998,
             "high": c[i] * 1.006, "low": c[i] * 0.994, "close": float(c[i]),
             "volume": float((vols or {}).get(i, 1e6))} for i in range(n)]
    if last:
        rows[-1].update(last)
    return rows


def _ema21(h):
    return float(pd.Series([r["close"] for r in h]).ewm(span=21, adjust=False).mean().iloc[-1])


# --------------------------------------------------------------- reclaim day

def test_an_undercut_yesterday_that_closed_under_is_reclaimed_today():
    h = _history()
    e = _ema21(h)
    h[-1].update({"low": e * 0.97, "close": e * 0.985})          # undercut AND closed under
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 1.004)         # today never dipped
    assert r["status"] == LU.MET
    hit = next(x for x in r["hits"] if x["name"] == "EMA21")
    assert hit["when"] == "yesterday"


def test_an_undercut_yesterday_that_already_closed_back_above_is_not_todays_reclaim():
    h = _history()
    e = _ema21(h)
    h[-1].update({"low": e * 0.97, "close": e * 1.01})           # reclaim day was yesterday
    r = LU.evaluate(h, spot=e * 1.02, day_low=e * 1.008)
    assert not [x for x in r["hits"] if x["name"] == "EMA21"]


def test_an_undercut_today_still_counts_and_says_today():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985)
    assert next(x for x in r["hits"] if x["name"] == "EMA21")["when"] == "today"


def test_stop_is_todays_low_of_day():
    h = _history()
    e = _ema21(h)
    assert LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985)["stop"] == round(e * 0.985, 2)


def test_volume_marks_pullback_dry_and_reclaim_above_average():
    n = 160
    h = _history(vols={i: 4e5 for i in range(n - 3, n)})          # last 3 sessions light
    e = _ema21(h)
    dry = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, vol_x=1.4)
    assert dry["volume"] == {"pullback_dry": True, "reclaim_x": 1.4, "reclaim_ok": True}
    heavy = _history(vols={i: 3e6 for i in range(n - 3, n)})
    r2 = LU.evaluate(heavy, spot=_ema21(heavy) * 1.012, day_low=_ema21(heavy) * 0.985, vol_x=0.6)
    assert r2["volume"]["pullback_dry"] is False and r2["volume"]["reclaim_ok"] is False


def test_volume_marks_never_decide_met():
    h = _history()
    e = _ema21(h)
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, vol_x=0.2)
    assert r["status"] == LU.MET and r["volume"]["reclaim_ok"] is False


def test_a_panel_row_for_today_is_ignored():
    h = _history(end=date(2026, 10, 7))                            # last row IS today
    e = _ema21(h[:-1])
    r = LU.evaluate(h, spot=e * 1.012, day_low=e * 0.985, today=date(2026, 10, 7))
    assert r["status"] == LU.MET


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
    assert t["at"] == "10:15" and t["entry"] == 100.2           # the bar's close time / close


def test_triggered_without_a_wait_when_above_since_the_open():
    bars = [_bar(9, 30, 100, 101, 99.9, 100.9, 5000), _bar(9, 45, 100.9, 101.5, 100.8, 101.4, 4000)]
    t = LM.vwap_trigger(bars)
    assert t["state"] == "TRIGGERED" and t["was_below"] is False


def test_not_ready_without_bars():
    assert LM.vwap_trigger([])["state"] == "NOT_READY"
    assert LM.vwap_trigger([{"date": "2026-10-07 08:00:00", "high": 1, "low": 1,
                             "close": 1, "volume": 1}])["state"] == "NOT_READY"


# ------------------------------------------------------------ state machine

def _ev(met=False, trig=False, known=True, **k):
    return {"buy_met": False, "unr_met": met, "unr_trigger": trig, "unr_known": known, **k}


def test_trigger_after_the_met_card_is_its_own_one_shot_card():
    st = {}
    assert CS.advance(st, "2026-10-07", "X", _ev(met=True)) == ["UNR_MET"]
    assert CS.advance(st, "2026-10-07", "X", _ev(met=True, trig=True)) == ["UNR_TRIGGER"]
    assert CS.advance(st, "2026-10-07", "X", _ev(met=True, trig=True)) == []


def test_trigger_in_the_same_cycle_rides_the_met_card_and_never_repeats():
    st = {}
    assert CS.advance(st, "2026-10-07", "X", _ev(met=True, trig=True)) == ["UNR_MET"]
    assert CS.advance(st, "2026-10-07", "X", _ev(met=True, trig=True)) == []


def test_failed_fires_once_after_met_and_only_when_judgeable():
    st = {}
    CS.advance(st, "2026-10-07", "X", _ev(met=True))
    assert CS.advance(st, "2026-10-07", "X", _ev(met=False, known=False)) == []      # no data
    assert CS.advance(st, "2026-10-07", "X", _ev(met=False)) == ["UNR_FAILED"]
    assert CS.advance(st, "2026-10-07", "X", _ev(met=False)) == []


def test_no_failed_without_a_prior_met():
    assert CS.advance({}, "2026-10-07", "X", _ev(met=False)) == []


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


def _live(trigger=None, status="MET"):
    unr = {"status": status, "reason": None, "below": [], "stop": 846.2,
           "hits": ([{"name": "EMA21", "level": 851.4, "low": 846.2, "when": "yesterday",
                      "spot_pct": 1.6}] if status == "MET" else []),
           "levels": [{"name": "EMA21", "level": 851.4}],
           "volume": {"pullback_dry": True, "reclaim_x": 1.3, "reclaim_ok": True}}
    return {"price": 864.99, "day_low": 846.2, "unr": unr,
            "vwap_trigger": trigger or {"state": "WAIT", "vwap": 865.28, "last_close": 862.0}}


def test_met_card_shows_the_trigger_the_stop_and_the_volume_marks():
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_MET"], _live())
    assert c["headline"] == "CAT @ 864.99 · 🟢 U&R MET"
    assert "undercut EMA21 851.40 yesterday" in c["lines"][0]
    assert c["lines"][1] == "Trigger ◌ wait — below VWAP 865.28"
    assert c["lines"][2] == ("Stop = low of day 846.20 (2.2% under spot) · "
                             "volume: pullback dry ✓, reclaim 1.3× ✓")


def test_trigger_card_headline_and_line():
    trig = {"state": "TRIGGERED", "vwap": 865.28, "last_close": 866.0, "was_below": True,
            "at": "10:15", "entry": 866.0}
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_TRIGGER"], _live(trig))
    assert c["headline"] == "CAT @ 864.99 · 🟢 U&R MET · ENTRY TRIGGER"
    assert c["lines"][1] == ("Trigger ✓ — a 15-min candle closed above VWAP 865.28 "
                             "at 10:15 (entry ref 866.00)")


def test_failed_card_says_so_and_shows_no_trigger_or_stop_lines():
    live = _live(status="NOT_MET")
    live["unr"]["below"] = [{"name": "EMA21", "level": 851.4, "low": 846.2}]
    c = E.build_condition_card("CAT", _row(), _evr(), ["UNR_FAILED"], live)
    assert c["headline"].endswith("🟠 U&R FAILED")
    text = "\n".join(c["lines"])
    assert "Trigger" not in text and "Stop = low of day" not in text


def test_not_met_card_stays_tight_no_trigger_or_stop():
    c = E.build_condition_card("CAT", _row(), _evr(("TRUE", "FALSE")), ["CONDITION_MET"],
                               _live(status="NOT_MET"))
    text = "\n".join(c["lines"])
    assert "Trigger" not in text and "low of day" not in text.split("UnR reference")[0]


def test_buy_line_says_watching_while_words_are_pending_not_not_met():
    """PM 2026-10-08: '✗ NOT MET — price ◌ · volume ◌' read as a failure."""
    pending = E._buy_line(_row(), _evr(("NOT_YET", "NOT_YET")), ["UNR_MET"], _live())
    assert pending.startswith("Buy conditions (AQE default) ◌ WATCHING")
    failed = E._buy_line(_row(), _evr(("TRUE", "FALSE")), ["UNR_MET"], _live())
    assert failed.startswith("Buy conditions (AQE default) ✗ NOT MET")
    mixed = E._buy_line(_row(), _evr(("FALSE", "NOT_YET")), ["UNR_MET"], _live())
    assert mixed.startswith("Buy conditions (AQE default) ✗ NOT MET")


def test_digest_subject_counts_the_new_states():
    subj, _, _ = E.build_condition_digest(
        [("CAT", _row(), _evr(), ["UNR_TRIGGER"], _live()),
         ("DOG", _row(), _evr(), ["UNR_FAILED"], _live(status="NOT_MET"))],
        datetime(2026, 10, 7, 11, 0, tzinfo=_ET))
    assert "U&R ENTRY 1" in subj and "U&R FAILED 1" in subj


# ----------------------------------------------- Drive-synced condition state

def test_merge_keeps_what_either_poller_already_emailed():
    a = {"2026-10-07:X": {"stage": "CONDITION_MET", "emailed_today": ["CONDITION_MET"],
                          "chased": False, "analyst_out": False, "exit_line": False,
                          "unr": True, "unr_trigger": False, "unr_failed": False}}
    b = {"2026-10-07:X": {"stage": "WATCHING", "emailed_today": ["UNR_MET"],
                          "chased": True, "analyst_out": False, "exit_line": False,
                          "unr": False, "unr_trigger": False, "unr_failed": False},
         "2026-10-07:Y": {"stage": "WATCHING", "emailed_today": [], "chased": False,
                          "analyst_out": False, "exit_line": False}}
    m = CS.merge_states(a, b)
    x = m["2026-10-07:X"]
    assert x["emailed_today"] == ["CONDITION_MET", "UNR_MET"]
    assert x["stage"] == "CONDITION_MET" and x["unr"] is True and x["chased"] is True
    assert "2026-10-07:Y" in m


def test_prune_is_relative_to_the_newest_run_date():
    st = {"2026-09-01:A": {}, "2026-10-06:B": {}, "2026-10-07:C": {}}
    assert set(CS._prune(st)) == {"2026-10-06:B", "2026-10-07:C"}


def test_save_and_load_go_through_drive_and_merge_across_pollers(tmp_path, monkeypatch):
    """The GitHub backstop starts from a fresh checkout: it must pick up what
    the in-app poller already emailed, from Drive, not re-send it."""
    import src.data.gdrive_uploader as G
    drive = {}
    monkeypatch.setattr(G, "is_configured", lambda: True)
    monkeypatch.setattr(G, "download_text", lambda name: drive.get(name))
    monkeypatch.setattr(G, "upload_or_replace",
                        lambda name, payload, mime=None: drive.__setitem__(name, payload))
    # poller A (in-app) emails a card and saves
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "a" / "state.json")
    a = {}
    assert CS.advance(a, "2026-10-07", "CAT", _ev(met=True)) == ["UNR_MET"]
    CS.save_condition_state(a)
    # poller B (fresh checkout, no local file) loads and must NOT fire it again
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "b" / "state.json")
    b = CS.load_condition_state()
    assert CS.advance(b, "2026-10-07", "CAT", _ev(met=True)) == []
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
    CS.advance(st, "2026-10-07", "CAT", _ev(met=True))
    CS.save_condition_state(st)                       # must not raise
    assert CS.load_condition_state()["2026-10-07:CAT"]["unr"] is True


# ------------------------------------------------------- end to end, 2 cycles

def test_two_cycles_met_then_trigger_each_fire_exactly_once(tmp_path, monkeypatch):
    from src.alerts import condition_cycle as CC
    from src.alerts import condition_data as CD
    from src.alerts import condition_ledger as CL
    import src.data.fmp_client as FC
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
    bars = {"now": [_bar(9, 30, e * 1.0, e * 1.004, e * 0.985, e * 0.99, 9000),
                    _bar(9, 45, e * 0.99, e * 0.992, e * 0.984, e * 0.986, 8000)]}

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

    def run(hh, mm, spot):
        q = {"HPE": {"price": spot, "prev_close": h[-1]["close"], "day_high": e * 1.02,
                     "day_low": e * 0.985, "open": e},
             "SPY": {"price": 500.0, "prev_close": 499.0}}
        return CC.run_condition_cycle(doc, q, datetime(2026, 10, 7, hh, mm, tzinfo=_ET),
                                      run_date="2026-10-07")

    s1 = run(10, 5, e * 1.012)                    # reclaimed, candles still under VWAP
    assert s1["fired"]["HPE"] == ["UNR_MET"]
    _t, _r, _ev2, _st, live1 = sent[-1][0][0]
    assert live1["vwap_trigger"]["state"] == "WAIT"
    bars["now"] = bars["now"] + [_bar(10, 0, e * 0.994, e * 1.02, e * 0.993, e * 1.015, 9000)]
    s2 = run(10, 20, e * 1.016)                   # a candle now closes above VWAP
    assert s2["fired"]["HPE"] == ["UNR_TRIGGER"]
    assert run(10, 35, e * 1.017)["fired"] == {}
    s4 = run(10, 50, e * 0.99)                    # slips back under every reclaimed level
    assert s4["fired"]["HPE"] == ["UNR_FAILED"]
