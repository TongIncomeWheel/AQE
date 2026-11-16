"""PM 2026-11-16: the funnel strip for both scans, built by code from the run files, each name with its AQE tag, and safe for the Cards plain-words gate."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
sys.path.insert(0, str(TOOLS))
import scan_funnel as SF  # noqa: E402

RUNS = [d for d in sorted((ROOT / "aegis" / "output" / "pma" / "run").glob("2026-11-1[0-9]")) if (d / "funnel.json").exists() and (d / "phase4.json").exists()
        and (d / "consensus.json").exists() and (d / "slate.json").exists() and (d / "committee_record.json").exists()]


def _gate():
    spec = importlib.util.spec_from_file_location("chk_funnel", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def _synthetic(tmp_path):
    (tmp_path / "seat_sets.json").write_text(json.dumps({"universe_rows": 1000, "seats": {"oneil": [{"ticker": "A"}, {"ticker": "B"}], "seow": [{"ticker": "B"}, {"ticker": "C"}]}}))
    (tmp_path / "tally.json").write_text(json.dumps([{"ticker": "A", "seats": ["oneil"]}, {"ticker": "B", "seats": ["seow"]}]))
    (tmp_path / "phase4.json").write_text(json.dumps({"deliberation_set": ["A", "B", "H"], "held_seated": ["H"], "nominations_cut_by_machinery": [], "nominations_off_universe": []}))
    ev = "lens coil warn: no tight base; rs_down_day_20d 0.21 (C16, R2); structure_shift CORRECTION_REENTRY"
    (tmp_path / "funnel.json").write_text(json.dumps({"rule": {"survives": "support CONFIRM >= 1", "out": "no SUPPORT vote at the blind vote", "dropped": "refuting evidence"},
        "survivors": ["A"], "dropped": ["B"], "out": ["H"],
        "names": {"B": {"claims": [{"rulings": [{"reviewer": "oneil", "ruling": "REFUTE", "evidence": ev}]}]}}}))
    (tmp_path / "slate.json").write_text(json.dumps({"tickets": [{"ticker": "A"}]}))
    (tmp_path / "consensus.json").write_text(json.dumps([{"ticker": "A", "verdict": "ADVANCE", "status": "AGREED", "objections": []}]))
    (tmp_path / "committee_record.json").write_text(json.dumps({"qa": {"holds": []}}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "whole_universe"}))
    eb = {"A": {"ticker": "A", "on_longlist": True, "on_elder": False, "sc_momentum": 80.0}}
    return eb


def test_standard_scan_funnel_counts_every_stage_and_tags_every_name_with_its_aqe_status(tmp_path):
    eb = _synthetic(tmp_path)
    f = SF.build(str(tmp_path), "A", eb, {})
    st = {s["stage"]: s for s in f["stages"]}
    assert st["Universe rows scored (market cap $2B+, 10-day volume 1.5M+, NYSE or NASDAQ)"]["n_out"] == 1000
    sc = st["Seat screens, union"]
    assert sc["n_out"] == 3 and sc["dropped_count"] == 997
    assert st["Nominated (any seat, any conviction)"]["n_out"] == 2
    room = st["In the room (nominated plus the held book)"]
    assert room["n_out"] == 3
    cx = st["Cross-examination (survivors move on)"]
    assert cx["n_out"] == 1 and {d["ticker"] for d in cx["dropped"]} == {"B", "H"}
    why = {d["ticker"]: d["reason"] for d in cx["dropped"]}
    assert why["B"].startswith("oneil: lens coil warn") and why["H"] == "no SUPPORT vote at the blind vote"        # the tool file's own words, never hand-written
    by = {n["ticker"]: n for n in f["names"]}
    assert by["A"]["aqe_listed"] is True and "AQE-listed: Longlist" in by["A"]["aqe_line"]
    assert "AQE score not available" in by["B"]["aqe_line"] and "AQE score not available" in by["H"]["aqe_plain"]       # a name in neither file: loud, never blank
    assert f["disclosure"]                                                                                          # the Standard Scan disclosure line rides on the funnel
    md = SF.render_md(f)
    assert "| Stage | In | Out | What fell out |" in md and "**B**" in md and "997 names (count only" in md


def test_quant_scan_funnel_has_the_quant_stages_and_no_disclosure(tmp_path):
    eb = _synthetic(tmp_path)
    (tmp_path / "quant_screen.json").write_text(json.dumps({"universe_rows": 1000, "rule": "top 30 by AQE rank plus the top 6 on five sub-scores", "names": 3, "why": {"A": ["AQE rank 1"], "B": ["Flow 99"], "C": ["Energy 98"]}}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "quant_scan", "report": "C"}))
    (tmp_path / "consensus.json").write_text(json.dumps([{"ticker": "A", "verdict": "ADVANCE"}, {"ticker": "B", "verdict": "PASS", "objections": [{"voice": "oneil", "objection": "no base"}]}]))
    f = SF.build(str(tmp_path), "C", eb, {})
    names = [s["stage"] for s in f["stages"]]
    assert names[1] == "AQE quant screen" and "Nominated by aqe-quant" in names and names[-1].startswith("Vote by all eight seats")
    assert f["stages"][1]["n_out"] == 3 and f["disclosure"] is None


def test_plain_reason_removes_charter_codes_and_raw_tokens_for_the_cards_gate():
    t = SF.plain_reason("lens coil warn (C16, R2); rs_down_day_20d 0.21; structure CORRECTION_REENTRY; BULLISH_B")
    assert "C16" not in t and "R2" not in t and "_" not in t and "CORRECTION" not in t.upper().replace("CORRECTION REENTRY", "")


@pytest.mark.skipif(not RUNS, reason="no real run dirs with a funnel in this checkout")
def test_every_real_run_funnel_passes_the_cards_plain_words_gate(tmp_path):
    ck = _gate()
    bad = []
    for run in RUNS:
        f = SF.build(str(run), "A", {}, {})
        assert f["stages"] and f["names"] and len(f["names"]) == len({n["ticker"] for n in f["names"]})
        body = "".join(f"<td>{SF.plain_reason(n['reason'])}</td><td>{SF.plain_reason(n['aqe_plain'])}</td>" for n in f["names"])
        page = tmp_path / f"{run.name}.html"
        page.write_text(f"<!doctype html><html><body><div class='card'><table><tr>{body}</tr></table></div></body></html>")
        fails, _ = ck.check_cards_html(str(page))
        bad += [(run.name, x) for x in fails]
    assert not bad, bad[:3]


def test_the_quant_scan_page_carries_the_funnel_tables_and_passes_the_html_gate(tmp_path):
    import pma_cards_report as CR
    eb = _synthetic(tmp_path)
    (tmp_path / "quant_screen.json").write_text(json.dumps({"universe_rows": 1000, "rule": "top 30 by AQE rank", "names": 2, "why": {"A": ["AQE rank 1"], "B": ["Flow 99"]}}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "quant_scan", "report": "C"}))
    f = SF.build(str(tmp_path), "C", eb, {})
    cons = [{"ticker": "A", "verdict": "ADVANCE", "conviction": 4, "split": {"support": ["a"], "oppose": [], "abstain": []}}]
    page = CR.render("C", "2026-11-16", cons, None, f)
    assert "The funnel" in page and "AQE quant screen" in page and "AQE-listed" in page and 'Scorecard' in page
    out = tmp_path / "c.html"; out.write_text(page)
    fails, _ = _gate().check_cards_html(str(out))
    assert not fails, fails
    assert "The funnel" not in CR.render("C", "2026-11-16", cons, None, None)          # no funnel file: the page is exactly as before
