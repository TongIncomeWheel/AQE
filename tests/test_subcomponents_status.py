"""Report C input guard: value-level check on the export's `subcomponents` block (PM 2026-11-05)."""
from src.data.drive_sync import _subcomponents_status

GOOD = {"flow": {"flow_score": 17.0, "mfi": None}, "mp": {"adx_val": 31.0}}
NULLS = {"flow": {"flow_score": None}, "mp": {"adx_val": None}}


def test_live_when_every_row_has_values():
    r = _subcomponents_status([{"ticker": "A", "subcomponents": GOOD}, {"ticker": "B", "subcomponents": GOOD}])
    assert r["status"] == "live" and r["rows"] == 2


def test_degraded_names_the_rows_that_are_empty_or_missing():
    r = _subcomponents_status([{"ticker": "A", "subcomponents": GOOD}, {"ticker": "B", "subcomponents": NULLS},
                               {"ticker": "C", "subcomponents": None}])
    assert r["status"] == "degraded" and r["missing"] == 1 and r["all_null"] == 1
    assert r["tickers"] == ["B", "C"] and "2 of 3" in r["reason"]


def test_error_when_nothing_is_usable_and_never_raises():
    assert _subcomponents_status([{"ticker": "A", "subcomponents": NULLS}])["status"] == "error"
    assert _subcomponents_status([])["status"] == "error"
    assert _subcomponents_status([None])["status"] == "error"


def test_a_key_check_alone_would_have_passed_the_all_null_block():
    assert _subcomponents_status([{"ticker": "A", "subcomponents": NULLS}])["status"] != "live"
