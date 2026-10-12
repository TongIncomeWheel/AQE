"""PM 2026-10-12: "I only want to see things in the latest AQE/PMA, please provide
date of PMA and AQE when you send the mail." Carried-forward committee rows and
stale exports never become cards; the digest says which PMA and AQE it is built on."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import condition_cycle as CC
from src.alerts import condition_defaults as DEF
from src.alerts import emailer as E
from src.alerts import pma_levels as PMA

_ET = ZoneInfo("America/New_York")
MON = datetime(2026, 10, 12, 10, 5, tzinfo=_ET)          # Monday 2026-10-12


def _cond():
    return {"shared": {"buy": [{"w": "h1_close_above", "level": 100.0}], "confirm": []},
            "exits": [], "analysts": []}


def _doc():
    return {"run_date": "2026-10-12", "session": "2026-10-12", "rows": [
        {"ticker": "NEW", "class": "ADVANCE", "origin_run": "2026-10-12", "age_sessions": 0,
         "conditions": _cond()},
        {"ticker": "OLD", "class": "HOLD_FOR_CONDITIONS", "origin_run": "2026-10-09",
         "age_sessions": 1, "carried": True, "conditions": _cond()},
        {"ticker": "OLDER", "class": "ADVANCE", "origin_run": "2026-10-08", "age_sessions": 2,
         "carried": True, "conditions": _cond()},
        {"ticker": "HLD", "class": "HELD", "origin_run": "2026-10-12", "age_sessions": 0,
         "conditions": _cond()},
        {"ticker": "NOFIELDS", "class": "ADVANCE", "conditions": _cond()},     # legacy row
    ]}


def test_the_latest_run_rule():
    d = _doc()
    got = {r["ticker"]: PMA.is_latest_run_row(d, r) for r in d["rows"]}
    assert got == {"NEW": True, "OLD": False, "OLDER": False, "HLD": True, "NOFIELDS": True}


def test_carried_forward_rows_are_not_watched():
    assert [r["ticker"] for r in CC.rows_with_conditions(_doc())] == ["NEW", "HLD", "NOFIELDS"]


def _export(date="2026-10-10"):
    rec = {"ticker": "OLD", "entry": 99.0, "atr_14d": 2.0, "on_longlist": True,
           "last_pivot_high": {"price": 100.0}, "prior_bar_high": 99.5,
           "bracket": {"valid": True, "stop": 95.0, "targets": []}}
    return {"date": date, "daily_list": [rec], "held_positions": []}


def test_a_carried_name_that_is_on_the_latest_longlist_is_an_aqe_default_not_a_committee_row():
    rows = DEF.synthesize_rows(_export(), _doc())
    old = [r for r in rows if r["ticker"] == "OLD"]
    assert old and old[0]["aqe_default"] is True and old[0]["class"] == "AQE_LONGLIST"


def test_meta_for_a_current_export_and_a_fresh_pma():
    m = CC.data_meta(_doc(), None, _export("2026-10-10"), MON)
    assert m["pma_run"] == "2026-10-12" and m["pma_session"] == "2026-10-12"
    assert m["aqe_date"] == "2026-10-10" and m["aqe_covers"] == "2026-10-09"
    assert m["aqe_current"] is True


def test_an_export_older_than_the_last_close_is_flagged_not_current():
    m = CC.data_meta(_doc(), None, _export("2026-10-08"), MON)      # covers Wed 10-07
    assert m["aqe_covers"] == "2026-10-07" and m["aqe_current"] is False


def test_a_missing_pma_for_todays_session_names_the_stale_file():
    m = CC.data_meta(None, {"session": "2026-10-09"}, _export(), MON)
    assert m["pma_run"] is None and m["pma_missing"] == "2026-10-09"


def test_a_stale_export_seeds_no_aqe_default_cards(tmp_path, monkeypatch):
    import src.alerts.condition_data as CD
    import src.alerts.condition_ledger as CL
    import src.alerts.condition_state as CS
    import src.data.fmp_client as FC
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path / "vp")
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    monkeypatch.setattr(CD, "_panel_history", lambda t, d: {})
    monkeypatch.setattr(CL, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")

    class _C:
        def get_intraday_bars(self, *a, **k):
            return []

        def get_daily_bars(self, *a, **k):
            return None
    monkeypatch.setattr(FC, "FMPClient", _C)
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: None)
    q = {"OLD": {"price": 99.0, "prev_close": 98.0, "day_low": 98.0, "day_high": 99.5, "open": 98.5},
         "SPY": {"price": 500.0, "prev_close": 499.0}}
    stale = CC.data_meta(None, None, _export("2026-10-08"), MON)
    s = CC.run_condition_cycle(None, q, MON, run_date="2026-10-12",
                               export=_export("2026-10-08"), meta=stale)
    assert s["defaults"] == 0
    fresh = CC.data_meta(None, None, _export("2026-10-10"), MON)
    s2 = CC.run_condition_cycle(None, q, MON, run_date="2026-10-12",
                                export=_export("2026-10-10"), meta=fresh)
    assert s2["defaults"] == 1


# ------------------------------------------------------------ the mail header

def _row():
    return {"ticker": "X", "class": "ADVANCE", "conditions": _cond(), "levels": {}}


def _ev():
    return {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False, "exit_warn": None,
            "exit_hit": None, "n_counting": 0, "n_lit": 0, "no_shared_buy": False,
            "analyst_detail": {}, "shared_buy_detail": [], "shared_confirm_detail": []}


def _live():
    return {"price": 99.0, "unr": {"status": "NOT_MET", "armed": [], "levels": [],
                                    "reason": "no shallow dip", "stop": None, "volume": {}},
            "vwap_trigger": {"state": "NOT_READY"}}


def test_the_mail_says_which_pma_and_aqe_it_is_built_on():
    meta = CC.data_meta(_doc(), None, _export("2026-10-10"), MON)
    subj, plain, html = E.build_condition_digest([("X", _row(), _ev(), ["CONDITION_MET"], _live())],
                                                 MON, meta=meta)
    assert ("Data: PMA run 2026-10-12 for session 2026-10-12 · "
            "AQE export 2026-10-10 (the 2026-10-09 close)") in plain
    assert "PMA 10-12 · AQE 10-10" in subj
    assert "Data: PMA run 2026-10-12" in html


def test_a_stale_aqe_and_a_missing_pma_are_loud_in_the_header():
    meta = CC.data_meta(None, {"session": "2026-10-09"}, _export("2026-10-08"), MON)
    line = E._data_line(meta)
    assert "⚠ PMA: no file for today's session (latest is session 2026-10-09)" in line
    assert "⚠ older than the last close — AQE-default names skipped" in line


def test_no_meta_no_data_line():
    assert E._data_line(None) is None
    _s, plain, _h = E.build_condition_digest([("X", _row(), _ev(), ["CONDITION_MET"], _live())], MON)
    assert "Data:" not in plain
