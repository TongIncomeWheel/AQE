"""Report B universe rows: every scored name, a full record, loud on any failure, size-guarded (PM 2026-11-05)."""
import json
from src.data import drive_sync as ds


def _rec(wr, wr_rank, source):
    tk = wr["ticker"]
    if tk == "BAD":
        raise ValueError("no bars")
    return {"ticker": tk, "rank": wr_rank, "source": source, "bracket": {}}


def test_every_scored_name_becomes_a_row_in_score_order_with_the_universe_source():
    sc = {"AAA": {"ticker": "AAA", "_sc": 50}, "BBB": {"ticker": "BBB", "_sc": 90}, "CCC": {"ticker": "CCC", "_sc": 10}}
    rows, st = ds._build_universe_rows(sc, _rec, [])
    assert [r["ticker"] for r in rows] == ["BBB", "AAA", "CCC"]
    assert all(r["source"] == "universe" for r in rows) and st["status"] == "live" and st["rows"] == 3


def test_a_name_that_cannot_be_built_is_named_and_the_set_is_degraded_not_thinner_in_silence():
    sc = {"AAA": {"ticker": "AAA", "_sc": 5}, "BAD": {"ticker": "BAD", "_sc": 9}}
    rows, st = ds._build_universe_rows(sc, _rec, [])
    assert [r["ticker"] for r in rows] == ["AAA"]
    assert st["status"] == "degraded" and any(x.startswith("BAD") for x in st["skipped"])


def test_a_failing_pass_is_recorded_and_the_others_still_run():
    ran = []
    def good(rows):
        ran.append(len(rows)); return {"status": "live"}
    def boom(rows):
        raise RuntimeError("panel gone")
    rows, st = ds._build_universe_rows({"AAA": {"ticker": "AAA", "_sc": 1}}, _rec, [("boom", boom), ("good", good)])
    assert ran == [1] and st["status"] == "degraded"
    assert st["passes"]["boom"]["status"] == "error" and st["passes"]["good"]["status"] == "live"


def test_nothing_built_is_an_error_not_an_empty_success():
    rows, st = ds._build_universe_rows({}, _rec, [])
    assert rows == [] and st["status"] == "error"


def test_the_builder_never_raises_on_garbage():
    rows, st = ds._build_universe_rows({"AAA": object()}, _rec, [])
    assert st["status"] in ("error", "degraded")


def test_the_file_is_listed_for_publish_and_persist():
    from src.data import github_sync, persist
    assert "aqe_universe_rows.json" in github_sync.DAILY_ARTIFACTS
    assert any(str(m[1]).endswith("aqe_universe_rows.json") for m in persist._members())
