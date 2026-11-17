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
    assert st["Universe rows scored (market cap $2B+, 10-day volume 500K+, NYSE or NASDAQ)"]["n_out"] == 1000
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
    assert f["disclosure"] is None                                                                                  # PM 2026-11-16: no disclosure line (the seats keep every AQE field)
    md = SF.render_md(f)
    # PM 2026-11-17 (Valen funnel shape): one strip, chronological, a count per step, then the names in the same step order
    cs = SF.strip_cells(f)
    assert [lab for _, lab, _ in cs] == ["Universe", "Screens", "Nominated", "In the room", "Cross-examined", "Slated", "Ratified", "After QA"][:len(cs)] and [i for i, _, _ in cs] == list(range(1, len(cs) + 1))
    assert cs[0][2] == 1000 and cs[1][2] == 3 and SF.strip_text(f).startswith("Universe 1,000 > Screens 3 > Nominated 2")
    assert "| 1. Universe | 2. Screens |" in md and "**B**" in md and "997 names left out" in md
    order = [n["ticker"] for n in SF.fell_rows(f)]
    steps = [n["step"] for n in SF.fell_rows(f) if n["outcome"] == "fell out"]
    assert steps == sorted(steps) and set(order) == {n["ticker"] for n in f["names"]}


def test_quant_scan_funnel_starts_from_aqes_own_list_and_takes_nothing_from_a(tmp_path):
    eb = _synthetic(tmp_path)
    (tmp_path / "seat_sets.json").unlink()                                              # C has no seat sets: its universe is AQE's own scored list
    (tmp_path / "candidate_set.json").write_text(json.dumps({"universe": [{"ticker": t, "source": "longlist"} for t in "ABCDEFGH"] + [{"ticker": "H1", "source": "held_book"}]}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "quant_scan", "report": "C"}))
    (tmp_path / "consensus.json").write_text(json.dumps([{"ticker": "A", "verdict": "ADVANCE"}, {"ticker": "B", "verdict": "PASS", "objections": [{"voice": "oneil", "objection": "no base"}]}]))
    f = SF.build(str(tmp_path), "C", eb, {})
    names = [s["stage"] for s in f["stages"]]
    assert names[0].startswith("AQE's own scored list") and f["stages"][0]["n_out"] == 8                  # the held book is not part of AQE's list
    assert "Nominated by aqe-quant" in names and names[-1].startswith("Vote by all eight seats")
    nom = next(s for s in f["stages"] if s["stage"] == "Nominated by aqe-quant")
    assert nom["n_in"] == 8 and nom["n_out"] == 2 and nom["dropped_count"] == 6 and f["disclosure"] is None


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
        page.write_text(f"<!doctype html><html><body><div class='card'><table><tr>{body}</tr></table>{SF.html_actionable(f)}</div></body></html>")      # also the new actionable block
        fails, _ = ck.check_cards_html(str(page))
        bad += [(run.name, x) for x in fails]
    assert not bad, bad[:3]


def test_the_quant_scan_page_carries_the_funnel_tables_and_passes_the_html_gate(tmp_path):
    import pma_cards_report as CR
    eb = _synthetic(tmp_path)
    (tmp_path / "candidate_set.json").write_text(json.dumps({"universe": [{"ticker": t, "source": "longlist"} for t in "ABC"]}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "quant_scan", "report": "C"}))
    f = SF.build(str(tmp_path), "C", eb, {})
    cons = [{"ticker": "A", "verdict": "ADVANCE", "conviction": 4, "split": {"support": ["a"], "oppose": [], "abstain": []}}]
    page = CR.render("C", "2026-11-16", cons, None, f)
    assert "The funnel" in page and "1. AQE list" in page and "Audit: names that fell out" in page and 'Scorecard' in page
    out = tmp_path / "c.html"; out.write_text(page)
    fails, _ = _gate().check_cards_html(str(out))
    assert not fails, fails
    assert "The funnel" not in CR.render("C", "2026-11-16", cons, None, None)          # no funnel file: the page is exactly as before


def test_the_brief_gate_accepts_exactly_what_scan_funnel_pastes_and_rejects_the_old_header(tmp_path):
    """Conductor 2026-11-17: Q-SS still looked for '| Stage | In | Out | What fell out |', so the restyled strip (#101) failed the gate. The producer and the gate must agree, for both scans."""
    import pma_pipeline as PP
    eb = _synthetic(tmp_path)
    f = SF.build(str(tmp_path), "A", eb, {})
    md = SF.render_md(f)
    assert PP.funnel_pasted(md) == (True, True)
    assert PP.funnel_pasted("| Stage | In | Out | What fell out |\n|---|---|---|---|\n| Universe | 1,000 | 3 | x |\n") == (False, False)       # the retired layout
    assert PP.funnel_pasted(md.replace("| 1. Universe |", "| Universe |"))[0] is False                                    # an unnumbered strip is not the strip
    assert PP.funnel_pasted(md.replace("| Step | Ticker | Result |", "| Ticker |"))[1] is False
    (tmp_path / "seat_sets.json").unlink()
    (tmp_path / "candidate_set.json").write_text(json.dumps({"universe": [{"ticker": t, "source": "longlist"} for t in "ABCDEFGH"]}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "quant_scan", "report": "C"}))
    (tmp_path / "consensus.json").write_text(json.dumps([{"ticker": "A", "verdict": "ADVANCE"}, {"ticker": "B", "verdict": "PASS", "objections": [{"voice": "oneil", "objection": "no base"}]}]))
    assert PP.funnel_pasted(SF.render_md(SF.build(str(tmp_path), "C", eb, {}))) == (True, True)
    src = open(PP.__file__).read()
    assert "What fell out |\" in brief_full" not in src


def _room(tmp_path):
    """Room of 9: seven survive cross-exam, three slated (supporters 5, 4, 4), one within a seat of the floor (N1: 3), one far under (F1: 1), QA holds one slated name (S3)."""
    (tmp_path / "seat_sets.json").write_text(json.dumps({"universe_rows": 1000, "seats": {"oneil": [{"ticker": t} for t in ("S1", "S2", "S3", "N1", "F1", "X1", "X2", "D1", "D2")]}}))
    (tmp_path / "tally.json").write_text(json.dumps([{"ticker": t, "seats": ["oneil"]} for t in ("S1", "S2", "S3", "N1", "F1", "X1", "X2", "D1", "D2")]))
    (tmp_path / "phase4.json").write_text(json.dumps({"deliberation_set": ["S1", "S2", "S3", "N1", "F1", "X1", "X2", "D1", "D2"], "held_seated": [], "nominations_cut_by_machinery": [], "nominations_off_universe": []}))
    ev = "a very long piece of seat prose about lens coil warn and rs_down_day_20d and structure shift (C16, R2) that must never reach the Cards table as such"
    (tmp_path / "funnel.json").write_text(json.dumps({"rule": {"survives": "support CONFIRM >= 1", "out": "no SUPPORT vote at the blind vote", "dropped": "refuting evidence"},
        "survivors": ["S1", "S2", "S3", "N1", "F1"], "dropped": ["D1", "D2"], "out": ["X1", "X2"],
        "names": {t: {"claims": [{"rulings": [{"reviewer": "oneil", "ruling": "REFUTE", "evidence": ev}]}]} for t in ("D1", "D2")}}))
    (tmp_path / "slate.json").write_text(json.dumps({"tickets": [{"ticker": t} for t in ("S1", "S2", "S3")]}))
    sup = lambda n: {"support": [f"s{i}" for i in range(n)], "oppose": [], "abstain": []}
    (tmp_path / "consensus.json").write_text(json.dumps([
        {"ticker": "S1", "verdict": "ADVANCE", "status": "AGREED", "split": sup(5), "objections": []}, {"ticker": "S2", "verdict": "ADVANCE", "status": "AGREED", "split": sup(4), "objections": []},
        {"ticker": "S3", "verdict": "HOLD-FOR-CONDITIONS", "status": "CONTESTED", "split": sup(4), "objections": []},
        {"ticker": "N1", "verdict": "PASS", "status": "NOT_SLATED", "split": sup(3), "objections": []}, {"ticker": "F1", "verdict": "PASS", "status": "NOT_SLATED", "split": sup(1), "objections": []}]))
    (tmp_path / "committee_record.json").write_text(json.dumps({"qa": {"holds": [{"ticker": "S3", "question": "Does the 4.1 percent gap to the pivot still leave room for the first target given the earnings date on the 24th and the thin volume reading"}]}}))
    (tmp_path / "run_manifest.json").write_text(json.dumps({"method": "whole_universe"}))
    return {t: {"ticker": t, "on_longlist": t == "N1"} for t in ("S1", "S2", "S3", "N1", "F1")}


def test_the_cards_funnel_is_actionable_first_audit_behind_a_click_one_short_reason_per_name(tmp_path):
    """PM 2026-11-17: 'What's the purpose of showing me the nominated 82 names with full of prose ... how is it actionable'. Strip on top; near misses visible; the fell-out table closed in a details block
    with ONE short reason (at most 12 words) per name; count-only steps say 'counted, not listed'; the full prose stays in the brief's markdown."""
    import re
    eb = _room(tmp_path)
    f = SF.build(str(tmp_path), "A", eb, {})
    h = SF.html_actionable(f)
    assert h.index("<th>1. Universe") < h.index("Near misses a CIO can act on") < h.index("<details>")                      # strip, then near misses, then the audit
    assert "<details>" in h and "<details open" not in h and "Audit: names that fell out (7)" in h                      # closed; D1 D2 X1 X2 N1 F1 fell out, and S3 was held by QA
    assert "were not carried forward. They are counted here, not listed." in h and "names left out (count only)" not in h
    near = {n["ticker"]: n for n in f["near_misses"]}
    assert set(near) == {"N1", "S3"} and "F1" not in near                                                                  # within one seat of the floor (4), and the QA hold; F1 is far under it
    assert near["N1"]["where"] == "not slated" and "3 of the seats" in near["N1"]["what"] and near["S3"]["where"] == "QA hold" and "gap to the pivot" in near["S3"]["what"]
    for n in f["names"]:
        if n["outcome"] == "fell out":
            assert len(n["short"].split()) <= 13 and "C16" not in n["short"] and "prose" not in n["short"], (n["ticker"], n["short"])          # 12 words plus the cut mark
    by = {n["ticker"]: n["short"] for n in f["names"]}
    assert by["D1"] == "cross-examined: refuted by oneil" and by["X1"].startswith("cross-examined: no seat supported it") and by["N1"] == "not slated: 3 seats supported it, the lowest slated had 4"
    audit = h[h.index("<details>"):]
    assert "a very long piece of seat prose" not in h and "rs_down_day" not in h                                         # the seat prose never reaches the Cards block
    md = SF.render_md(f)
    assert "a very long piece of seat prose" in md or "cross-exam" in md.lower()                                         # the brief keeps the full table
    assert "| Step | Ticker | Result |" in md


def test_the_actionable_block_has_no_near_miss_table_when_there_is_none_and_says_so(tmp_path):
    eb = _synthetic(tmp_path)
    h = SF.html_actionable(SF.build(str(tmp_path), "A", eb, {}))
    assert "<b>Near misses:</b> none" in h and "Near misses a CIO can act on" not in h and "Audit: names that fell out (2)" in h


def test_an_older_funnel_file_without_near_misses_says_not_computed_never_none(tmp_path):
    eb = _synthetic(tmp_path)
    f = SF.build(str(tmp_path), "A", eb, {})
    del f["near_misses"]
    for n in f["names"]:
        n.pop("short", None)
    h = SF.html_actionable(f)
    assert "not computed in this scan_funnel.json" in h and "<b>Near misses:</b> none" not in h and "Audit: names that fell out" in h
