"""Tests for the value-level data-quality guard (2026-07-15 ruling): a ticker
that made it into daily_list/held_positions via full scoring should never
carry a null in a core engine field. _REQUIRED_FIELDS only checked that the
KEY exists; this guard checks the VALUE isn't null, without ever blocking
the export (a single thin-history ticker must not take down the whole feed)."""

from __future__ import annotations

from src.data.drive_sync import _compute_data_quality, _HARD_REQUIRED_NONNULL


def _good_record(ticker="AAPL"):
    return {
        "ticker": ticker, "sc_momentum": 80.0, "flow": 75.0, "energy": 70.0,
        "structure": 65.0, "mp": 60.0, "elder": 8.0, "entry": 150.0,
        "atr_14d": 3.5, "bracket": {"valid": True, "stop": 145.0},
        "div_state": None,  # legitimately nullable — must NOT be flagged
    }


def test_clean_records_produce_no_flags():
    dq = _compute_data_quality([_good_record()], [_good_record("MSFT")])
    assert dq == {"flagged_count": 0, "flagged": []}


def test_null_core_field_is_flagged_not_blocked():
    bad = _good_record("XYZ")
    bad["flow"] = None
    bad["structure"] = None
    dq = _compute_data_quality([bad], [])
    assert dq["flagged_count"] == 1
    assert dq["flagged"][0]["ticker"] == "XYZ"
    assert dq["flagged"][0]["tier"] == "daily_list"
    assert set(dq["flagged"][0]["null_fields"]) == {"flow", "structure"}


def test_held_positions_are_covered_unlike_the_old_key_only_guard():
    bad_held = _good_record("HELD1")
    bad_held["bracket"] = None
    dq = _compute_data_quality([], [bad_held])
    assert dq["flagged_count"] == 1
    assert dq["flagged"][0]["tier"] == "held_positions"
    assert dq["flagged"][0]["null_fields"] == ["bracket"]


def test_bracket_invalid_but_present_is_not_a_null():
    # bracket.valid=False (no structural stop passes gates) is a legitimate
    # state, not a data gap — only bracket being None counts as a gap.
    rec = _good_record()
    rec["bracket"] = {"valid": False, "invalid_reason": "no resistance above price"}
    dq = _compute_data_quality([rec], [])
    assert dq["flagged_count"] == 0


def test_soft_nullable_fields_never_trigger_a_flag():
    rec = _good_record()
    for f in ("div_state", "structure_shift", "knn_prob", "choch_state", "pin_bar_state"):
        rec[f] = None
    dq = _compute_data_quality([rec], [])
    assert dq["flagged_count"] == 0


def test_hard_required_list_matches_what_the_pm_confirmed():
    assert set(_HARD_REQUIRED_NONNULL) == {
        "sc_momentum", "flow", "energy", "structure", "mp", "elder",
        "entry", "atr_14d", "bracket",
    }
