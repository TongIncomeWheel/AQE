"""Tests for AQE-default conditions (src/alerts/condition_defaults.py) --
PM ruling 2026-10-04: the condition-card universe is the committee book
plus AQE Longlist/Elder, with AQE's own criteria said so on the card."""

from __future__ import annotations

import pytest

from src.alerts import condition_defaults as D


def _rec(tk, entry, lph=None, pbh=None, longlist=False, elder=False, held=False,
         stop=None, valid=True, fallback=None, targets=()):
    return {"ticker": tk, "entry": entry, "atr_14d": 2.0,
            "last_pivot_high": {"price": lph} if lph is not None else None,
            "prior_bar_high": pbh, "on_longlist": longlist, "on_elder": elder, "held": held,
            "bracket": {"valid": valid, "stop": stop, "atr_fallback_stop": fallback,
                        "targets": [{"price": p} for p in targets]}}


def _export(*recs, held=()):
    return {"daily_list": list(recs), "held_positions": [{"ticker": t} for t in held]}


@pytest.fixture(autouse=True)
def _defaults_on(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_ENABLED", True)
    monkeypatch.setattr(C, "CONDITION_DEFAULT_SOURCES", "longlist,elder")
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_INCLUDE_WATCH", False)
    monkeypatch.setattr(C, "CONDITION_DEFAULT_MAX_LEVEL_PCT", 6.0)
    monkeypatch.setattr(C, "CONDITION_MAX_WATCHED", 120)


# ---------------------------------------------------------------- the line

def test_breakout_line_is_the_pivot_when_it_still_sits_above_the_close():
    assert D.breakout_line(_rec("A", entry=100.0, lph=103.0, pbh=101.0)) == 103.0


def test_breakout_line_falls_back_to_prior_bar_high_once_the_pivot_is_cleared():
    """A name already through its pivot needs a NEW intraday break -- not a
    card at 09:45 for a move that already happened."""
    assert D.breakout_line(_rec("A", entry=105.0, lph=103.0, pbh=106.0)) == 106.0


def test_no_line_when_nothing_sits_above_the_close():
    assert D.breakout_line(_rec("A", entry=105.0, lph=103.0, pbh=104.0)) is None


def test_a_line_too_far_above_the_close_is_not_armed():
    assert D.build_default_conditions(_rec("A", entry=100.0, lph=113.0)) is None
    assert D.build_default_conditions(_rec("A", entry=100.0, lph=105.0)) is not None


# ------------------------------------------------------------- the block

def test_default_block_matches_pmas_schema_and_says_aqe_default():
    cond = D.build_default_conditions(_rec("A", entry=100.0, lph=104.0))
    buy = cond["shared"]["buy"][0]
    assert buy["w"] == "h1_close_above" and buy["level"] == 104.0
    assert "(AQE default)" in buy["plain"]
    assert cond["shared"]["confirm"][0]["w"] == "vol_x_ge"
    assert cond["shared"]["chase"]["level"] == round(104.0 * 1.03, 2)
    assert cond["exits"] == [] and cond["analysts"] == []


# --------------------------------------------------------- synthesize_rows

def test_longlist_and_elder_names_outside_the_book_are_added():
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True),
                 _rec("EL1", 50.0, lph=51.0, elder=True),
                 _rec("NONE", 10.0, lph=10.5))                      # on neither list
    rows = D.synthesize_rows(ex, {"rows": []})
    assert {r["ticker"]: r["class"] for r in rows} == {"LL1": "AQE_LONGLIST", "EL1": "AQE_ELDER"}
    assert all(r["aqe_default"] for r in rows)


def test_names_already_in_the_committee_book_are_left_to_the_committee():
    ex = _export(_rec("HPE", 100.0, lph=103.0, longlist=True))
    pma = {"rows": [{"ticker": "HPE", "class": "ADVANCE",
                     "conditions": {"shared": {"buy": []}}}]}
    assert D.synthesize_rows(ex, pma) == []


def test_committee_rows_without_conditions_are_filled_but_watch_is_not():
    ex = _export(_rec("HOLD1", 100.0, lph=103.0), _rec("W1", 100.0, lph=103.0))
    pma = {"rows": [{"ticker": "HOLD1", "class": "HOLD_FOR_CONDITIONS"},
                    {"ticker": "W1", "class": "WATCH"}]}
    rows = D.synthesize_rows(ex, pma)
    assert [r["ticker"] for r in rows] == ["HOLD1"]
    assert rows[0]["class"] == "HOLD_FOR_CONDITIONS" and rows[0]["aqe_default"] is True
    assert pma["rows"][0].get("conditions") is None          # never mutated


def test_watch_rows_fill_only_behind_the_flag(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_INCLUDE_WATCH", True)
    ex = _export(_rec("W1", 100.0, lph=103.0))
    rows = D.synthesize_rows(ex, {"rows": [{"ticker": "W1", "class": "WATCH"}]})
    assert [r["ticker"] for r in rows] == ["W1"]


def test_held_names_are_never_default_watched():
    ex = _export(_rec("H1", 100.0, lph=103.0, longlist=True, held=True),
                 _rec("H2", 100.0, lph=103.0, longlist=True), held=("H2",))
    assert D.synthesize_rows(ex, {"rows": []}) == []


def test_source_knob_can_narrow_to_longlist_only(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_DEFAULT_SOURCES", "longlist")
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True),
                 _rec("EL1", 50.0, lph=51.0, elder=True))
    assert [r["ticker"] for r in D.synthesize_rows(ex, {"rows": []})] == ["LL1"]


def test_bracket_line_reads_the_exports_own_stop_and_targets():
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True, stop=97.0,
                      targets=(101.0, 110.0, 120.0)))
    row = D.synthesize_rows(ex, {"rows": []})[0]
    assert row["levels"] == {"stop": 97.0, "tp": [110.0, 120.0]}   # only targets above the line


def test_invalid_bracket_falls_back_to_the_atr_stop():
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True, stop=None, valid=False,
                      fallback=96.5))
    assert D.synthesize_rows(ex, {"rows": []})[0]["levels"]["stop"] == 96.5


def test_disabled_flag_or_no_export_yields_nothing(monkeypatch):
    from src.alerts import config as C
    assert D.synthesize_rows(None, {"rows": []}) == []
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_ENABLED", False)
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True))
    assert D.synthesize_rows(ex, {"rows": []}) == []


def test_default_tickers_feeds_the_quote_fetch():
    ex = _export(_rec("LL1", 100.0, lph=103.0, longlist=True))
    assert D.default_tickers(ex, None) == {"LL1"}
