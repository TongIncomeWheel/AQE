"""scripts/filter_to_universe.py: the emergency filter for the run-150 leak (2026-11-18). Keeps the screened universe and the held book, never edits its inputs, says what it did not recompute."""
import json


def test_the_emergency_filter_keeps_the_universe_and_the_held_book_and_never_edits_its_inputs(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("ftu", Path(__file__).resolve().parents[1] / "scripts" / "filter_to_universe.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    (tmp_path / "u.txt").write_text("# AQE Universe\nAAA\nBBB\n")
    ex = {"daily_list": [{"ticker": t} for t in ("AAA", "ZZZ", "ARKK")], "lens_ranking": [{"ticker": "BBB"}, {"ticker": "ZZZ"}], "held_positions": [{"ticker": "HELD"}]}
    ur = {"count": 4, "rows": [{"ticker": t} for t in ("AAA", "BBB", "ARKK", "HELD")]}
    (tmp_path / "e.json").write_text(json.dumps(ex)); (tmp_path / "r.json").write_text(json.dumps(ur))
    before = (tmp_path / "e.json").read_bytes()
    assert m.main(["--export", str(tmp_path / "e.json"), "--universe-rows", str(tmp_path / "r.json"), "--universe", str(tmp_path / "u.txt"), "--out-dir", str(tmp_path / "out")]) == 0
    fe = json.loads((tmp_path / "out" / "aqe_daily_export.filtered.json").read_text()); fr = json.loads((tmp_path / "out" / "aqe_universe_rows.filtered.json").read_text())
    assert [r["ticker"] for r in fe["daily_list"]] == ["AAA"] and [r["ticker"] for r in fe["lens_ranking"]] == ["BBB"] and [r["ticker"] for r in fr["rows"]] == ["AAA", "BBB", "HELD"] and fr["count"] == 3
    assert (tmp_path / "e.json").read_bytes() == before and "NOT recomputed" in fe["filtered_by"]
