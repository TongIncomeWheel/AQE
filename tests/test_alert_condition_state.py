"""Tests for src/alerts/condition_state.py (AQE handoff D123/R21,
2026-10-02 §6).
"""

from __future__ import annotations

from src.alerts import condition_state as CS


def _result(**overrides) -> dict:
    base = {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False,
           "exit_warn": None, "exit_hit": None}
    base.update(overrides)
    return base


def test_starts_watching():
    state = {}
    e = CS._entry(state, "2026-10-02", "X")
    assert e["stage"] == CS.STAGE_WATCHING


def test_buy_met_transitions_to_condition_met_and_fires_once():
    state = {}
    fired = CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    assert fired == [CS.STAGE_CONDITION_MET]
    assert state["2026-10-02:X"]["stage"] == CS.STAGE_CONDITION_MET


def test_condition_met_does_not_refire_on_a_later_cycle_same_day():
    state = {}
    CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    fired_again = CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    assert fired_again == []


def test_buy_met_turning_false_after_condition_met_fires_failed_push():
    state = {}
    CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    fired = CS.advance(state, "2026-10-02", "X", _result(buy_met=False))
    assert fired == [CS.STAGE_FAILED_PUSH]
    assert state["2026-10-02:X"]["stage"] == CS.STAGE_FAILED_PUSH


def test_re_qualifying_after_failed_push_fires_condition_met_again():
    """CONDITION_MET already used its once-per-day allowance on entry #1,
    so a SECOND entry the same day must not re-fire -- "once per state
    per day" (§6)."""
    state = {}
    CS.advance(state, "2026-10-02", "X", _result(buy_met=True))          # CONDITION_MET (fires)
    CS.advance(state, "2026-10-02", "X", _result(buy_met=False))         # FAILED_PUSH (fires)
    fired = CS.advance(state, "2026-10-02", "X", _result(buy_met=True))  # CONDITION_MET again
    assert fired == []  # already emailed once today
    assert state["2026-10-02:X"]["stage"] == CS.STAGE_CONDITION_MET


def test_watching_never_emails():
    state = {}
    fired = CS.advance(state, "2026-10-02", "X", _result())
    assert fired == []
    assert state["2026-10-02:X"]["stage"] == CS.STAGE_WATCHING


def test_chased_fires_once():
    state = {}
    fired1 = CS.advance(state, "2026-10-02", "X", _result(chased=True))
    fired2 = CS.advance(state, "2026-10-02", "X", _result(chased=True))
    assert fired1 == ["CHASED"]
    assert fired2 == []


def test_analyst_out_fires_once_on_new_wrong_lit():
    state = {}
    fired1 = CS.advance(state, "2026-10-02", "X", _result(wrong_lit=["minervini"]))
    fired2 = CS.advance(state, "2026-10-02", "X", _result(wrong_lit=["minervini"]))
    assert fired1 == ["ANALYST_OUT"]
    assert fired2 == []


def test_exit_line_labelled_held_vs_warn_by_is_held():
    state = {}
    fired_held = CS.advance(state, "2026-10-02", "HELD1",
                            _result(exit_hit={"value": 60.0}), is_held=True)
    fired_shortlist = CS.advance(state, "2026-10-02", "SL1",
                                 _result(exit_hit={"value": 60.0}), is_held=False)
    assert fired_held == ["EXIT_LINE_HELD"]
    assert fired_shortlist == ["EXIT_LINE_WARN"]


def test_exit_warn_alone_also_fires_exit_line():
    state = {}
    fired = CS.advance(state, "2026-10-02", "X", _result(exit_warn={"value": 60.0}))
    assert fired == ["EXIT_LINE_WARN"]


def test_multiple_independent_states_can_fire_the_same_cycle():
    state = {}
    fired = CS.advance(state, "2026-10-02", "X",
                       _result(buy_met=True, chased=True, wrong_lit=["livermore"]))
    assert set(fired) == {CS.STAGE_CONDITION_MET, "CHASED", "ANALYST_OUT"}


def test_different_tickers_tracked_independently():
    state = {}
    CS.advance(state, "2026-10-02", "A", _result(buy_met=True))
    fired_b = CS.advance(state, "2026-10-02", "B", _result(buy_met=True))
    assert fired_b == [CS.STAGE_CONDITION_MET]
    assert state["2026-10-02:A"]["stage"] == CS.STAGE_CONDITION_MET
    assert state["2026-10-02:B"]["stage"] == CS.STAGE_CONDITION_MET


def test_same_ticker_different_run_dates_tracked_independently():
    """A carried row keeps separate history per run date it was carried
    under, matching pma_levels.py's own 3-session carry model."""
    state = {}
    CS.advance(state, "2026-10-01", "X", _result(buy_met=True))
    fired = CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    assert fired == [CS.STAGE_CONDITION_MET]  # a fresh day, fresh allowance


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")
    state = {}
    CS.advance(state, "2026-10-02", "X", _result(buy_met=True))
    CS.save_condition_state(state)
    loaded = CS.load_condition_state()
    assert loaded == state


def test_load_returns_empty_dict_when_file_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "does_not_exist.json")
    assert CS.load_condition_state() == {}
