"""Tests for the value-level data-quality guard (2026-07-15 ruling): a ticker
that made it into daily_list/held_positions via full scoring should never
carry a null in a core engine field. _REQUIRED_FIELDS only checked that the
KEY exists; this guard checks the VALUE isn't null, without ever blocking
the export (a single thin-history ticker must not take down the whole feed)."""

from __future__ import annotations

import pytest

from src.data.drive_sync import (
    _compute_data_quality, _HARD_REQUIRED_NONNULL,
    _assert_scored_universe_not_collapsed, MIN_SCORED_UNIVERSE,
)


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


def test_option_and_spread_legs_never_flagged_as_a_data_gap():
    """A covered-call/hedge leg from the PTJ (e.g. IBM_260C, IWM_HEDGE) can
    never carry an equity score/bracket — that's a category mismatch, not a
    data gap. Only STK-type held_positions rows go through the guard."""
    for kind in ("OPT", "OPT_SPREAD"):
        leg = {"ticker": "IBM_260C", "position_type": kind}  # everything else genuinely null
        dq = _compute_data_quality([], [leg])
        assert dq["flagged_count"] == 0, kind


def test_stk_rows_without_position_type_default_to_checked():
    # Back-compat: a held row with no position_type at all is treated as STK
    # (the default before this field existed), so it still gets checked.
    bad = _good_record("LEGACY")
    bad["bracket"] = None
    dq = _compute_data_quality([], [bad])
    assert dq["flagged_count"] == 1


# ── the scored-universe collapse guard (2026-08-27) ─────────────────────────
# daily_list/longlist/elder_list are all DERIVED from the scored universe, so
# _compute_data_quality above (which only inspects rows that already made it
# in) can never notice that most of the universe never became a row at all.
# This guard catches that: a collapsed price/score pull left scores_daily
# holding ~6-11 tickers (almost entirely the held book), and a 6-name
# daily_list published straight over the prior day's real ~200-name one with
# no error anywhere. Unlike _compute_data_quality, this one BLOCKS.

def test_a_healthy_universe_size_passes_clean():
    _assert_scored_universe_not_collapsed(700)   # must not raise


def test_the_actual_2026_08_27_collapse_size_is_blocked():
    with pytest.raises(ValueError, match="SCORED UNIVERSE COLLAPSED"):
        _assert_scored_universe_not_collapsed(6)


def test_the_threshold_is_exclusive_at_the_boundary():
    _assert_scored_universe_not_collapsed(MIN_SCORED_UNIVERSE)  # exactly at floor: OK
    with pytest.raises(ValueError):
        _assert_scored_universe_not_collapsed(MIN_SCORED_UNIVERSE - 1)


def test_the_error_names_the_actual_and_expected_counts_for_a_fast_diagnosis():
    with pytest.raises(ValueError) as exc:
        _assert_scored_universe_not_collapsed(11)
    msg = str(exc.value)
    assert "11" in msg
    assert str(MIN_SCORED_UNIVERSE) in msg
