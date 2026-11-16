"""Standard Scan (PM 2026-11-16): the committee without the AQE gate, plus the AQE Quant Scan (report C) independent of A.
Covers: the AQE-listed read, augment-export, the packet CLEAN TEST, the ledger columns, the manifest method, the report_compare split, quant-screen."""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
sys.path.insert(0, str(TOOLS))
import aqe_listing as AL  # noqa: E402
import report_compare as RC  # noqa: E402

PIPE, REG = TOOLS / "pma_pipeline.py", TOOLS / "registrar.py"
FIX = ROOT / "tests" / "fixtures" / "cards_v3"
MENUS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "contracts" / "voice_menus.json"


def run(args, env_extra=None, cwd=None):
    env = dict(os.environ); env.pop("AEGIS_REPORT", None); env.update(env_extra or {})
    return subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, env=env, cwd=cwd)


# ------------------------------------------------------------------ the AQE-listed read
def test_listing_says_listed_none_or_not_available_and_never_blank():
    ex = {"AAA": {"ticker": "AAA", "on_longlist": True, "on_elder": True, "sc_momentum": 85.7, "flow": 90, "elder": 10, "qs": {"odds": {"p": 0.52}}},
          "BBB": {"ticker": "BBB", "on_longlist": False, "on_elder": False, "sc_momentum": 61.0}}
    uni = {"CCC": {"ticker": "CCC", "sc_momentum": 70.0, "flow": 55}}
    a = AL.listing("AAA", ex, uni)
    assert a["aqe_listed"] is True and a["aqe_lists"] == "Longlist|Elder" and a["scores"]["SC_MOMENTUM"] == 85.7 and a["qs_odds"] == 0.52
    assert "Quiet Strength odds 52%" in a["plain_line"] and "SC_MOMENTUM" not in a["plain_line"]          # the Cards plain-words gate rejects raw names
    b = AL.listing("BBB", ex, uni)
    assert b["aqe_listed"] is False and b["aqe_lists"] == "none" and "on the AQE daily list but on no Longlist" in b["line"] and "QS: not scored" in b["line"]
    c = AL.listing("CCC", ex, uni)                                         # outside the export: read from the universe rows
    assert c["aqe_listed"] is False and c["source"] == "universe_rows" and "below the AQE shortlist gate" in c["line"]
    z = AL.listing("ZZZ", ex, uni)                                         # in neither: loud, never blank
    assert z["source"] == "unavailable" and z["aqe_listed"] is None and "AQE score not available" in z["line"] and "AQE score not available" in z["plain_line"]
    md = AL.table_md(["AAA", "ZZZ"], ex, uni)
    assert md.startswith("| Ticker | AQE-listed | AQE scores |") and "**AAA** | Longlist, Elder" in md and "**ZZZ** | AQE score not available" in md


def test_ptrs_is_never_claimed():
    assert "ptrs" in AL.NOT_IN_EXPORT and "PTRS" not in AL.listing("A", {"A": {"ticker": "A", "sc_momentum": 1}})["line"]


# ------------------------------------------------------------------ augment-export
def _universe_files(tmp_path):
    rows = [{"ticker": f"U{i}", "rank": i + 1, "sc_momentum": 60 + i, "flow": 50, "energy": 50, "structure": 50, "mp": 50, "elder": 5, "entry": 10.0} for i in range(6)]
    (tmp_path / "u.json").write_text(json.dumps({"date": "2026-11-16", "rows": rows}))
    ex = {"daily_list": [dict(rows[0], on_longlist=True, on_elder=False, on_qs=False)], "held_positions": [], "srm": []}
    (tmp_path / "ex.json").write_text(json.dumps(ex))
    (tmp_path / "ss.json").write_text(json.dumps({"seats": {"oneil": [{"ticker": "U0"}, {"ticker": "U3"}], "seow": ["U4"]}}))
    return tmp_path


def test_augment_export_adds_only_the_missing_screened_names_as_universe_only_and_never_edits_the_original(tmp_path):
    d = _universe_files(tmp_path)
    before = (d / "ex.json").read_text()
    r = run([PIPE, "augment-export", "--export", d / "ex.json", "--universe-rows", d / "u.json", "--seat-sets", d / "ss.json", "--out", d / "wu.json"])
    assert r.returncode == 0, r.stdout + r.stderr
    wu = json.loads((d / "wu.json").read_text())
    added = [x for x in wu["daily_list"] if x.get("universe_only")]
    assert sorted(x["ticker"] for x in added) == ["U3", "U4"] and all(x["on_longlist"] is False and x["source"] == "universe" for x in added)
    assert (d / "ex.json").read_text() == before                                  # the original export is untouched
    assert wu["standard_scan"]["universe_only_added"] == ["U3", "U4"]


def test_augment_export_refuses_a_name_in_neither_file(tmp_path):
    d = _universe_files(tmp_path)
    r = run([PIPE, "augment-export", "--export", d / "ex.json", "--universe-rows", d / "u.json", "--tickers", "NOPE", "--out", d / "wu.json"])
    assert r.returncode != 0 and "NOPE" in r.stdout + r.stderr


# ------------------------------------------------------------------ the CLEAN TEST on the packets
def _packets(tmp_path, clean):
    ex = FIX / "aqe_daily_export.json"
    if not ex.exists():
        pytest.skip("no export fixture")
    cs, out = tmp_path / "cs.json", tmp_path / ("pk_clean" if clean else "pk")
    assert run([PIPE, "trim", "--export", ex, "--date", "2026-11-04", "--out", cs]).returncode == 0
    args = [PIPE, "packets", "--candidates", cs, "--export", ex, "--menus", MENUS, "--date", "2026-11-04", "--outdir", out]
    r = run(args + (["--clean"] if clean else []))
    assert r.returncode == 0, r.stderr[-500:]
    return out


def test_clean_packets_carry_no_aqe_membership_or_score_and_say_so(tmp_path):
    out = _packets(tmp_path, True)
    ct = json.loads((out / "clean_test.json").read_text())
    strip = set(ct["stripped_fields"])
    assert {"on_longlist", "on_elder", "on_qs", "sc_momentum", "rank", "flow", "energy", "structure", "mp_state", "lens"} <= strip
    for f in sorted(out.glob("*.tsv")):
        txt = f.read_text()
        assert txt.startswith("# CLEAN TEST"), f.name
        cols = [l for l in txt.split("\n") if l and not l.startswith("#")][0].split("\t")
        assert not ({c.split(".")[0] for c in cols} & strip), (f.name, sorted({c.split(".")[0] for c in cols} & strip))
        assert "rs_rank_pct" in cols and "ma_50" in cols                     # raw columns remain
    # control: without --clean the same packets DO carry them
    ctrl = _packets(tmp_path, False)
    cols = [l for l in (ctrl / "oneil.tsv").read_text().split("\n") if l and not l.startswith("#")][0].split("\t")
    assert "sc_momentum" in cols and not (ctrl / "clean_test.json").exists()


# ------------------------------------------------------------------ the manifest method and the ledger
def test_registrar_stamps_the_method_and_rejects_an_unknown_one(tmp_path):
    ok = run([REG, "--manifest", tmp_path / "m.json", "init", "--date", "2026-11-16", "--method", "whole_universe"])
    assert ok.returncode == 0 and json.loads((tmp_path / "m.json").read_text())["method"] == "whole_universe"
    bad = run([REG, "--manifest", tmp_path / "m2.json", "init", "--date", "2026-11-16", "--method", "vibes"])
    assert bad.returncode == 2
    plain = run([REG, "--manifest", tmp_path / "m3.json", "init", "--date", "2026-11-16"])
    assert "method" not in json.loads((tmp_path / "m3.json").read_text())                     # no flag = the old chain, no new key
    c = run([REG, "--manifest", tmp_path / "m4.json", "init", "--date", "2026-11-16", "--report", "C"], {"AEGIS_REPORT": "C"})
    assert c.returncode == 0 and json.loads((tmp_path / "m4.json").read_text())["method"] == "quant_scan"


def test_record_verdicts_writes_method_and_the_aqe_listing_with_a_frozen_score_snapshot(tmp_path):
    d = _universe_files(tmp_path)
    run([PIPE, "augment-export", "--export", d / "ex.json", "--universe-rows", d / "u.json", "--tickers", "U3", "--out", d / "wu.json"])
    (d / "consensus.json").write_text(json.dumps([
        {"ticker": "U0", "verdict": "ADVANCE", "conviction": 4, "split": {"support": ["a", "b"], "oppose": [], "abstain": []}},
        {"ticker": "U3", "verdict": "PASS", "conviction": 2, "split": {"support": [], "oppose": ["a"], "abstain": []}},
        {"ticker": "GONE", "verdict": "PASS", "conviction": 1, "split": {"support": [], "oppose": [], "abstain": []}}]))
    (d / "cs.json").write_text(json.dumps({"universe": [{"ticker": "U0", "entry": 10.0}, {"ticker": "U3", "entry": 10.0}, {"ticker": "GONE", "entry": 10.0}]}))
    (d / "run_manifest.json").write_text(json.dumps({"method": "whole_universe"}))
    r = run([PIPE, "record-verdicts", "--consensus", "consensus.json", "--candidates", "cs.json", "--phase4", "none.json", "--ledger", "led.json", "--date", "2026-11-16",
             "--export", "wu.json", "--universe-rows", "u.json"], cwd=d, env_extra={})
    assert r.returncode == 0, r.stdout + r.stderr
    # the manifest is read from the working directory
    rows = {x["ticker"]: x for x in json.loads((d / "led.json").read_text())["rows"]}
    assert rows["U0"]["aqe_listed"] is True and rows["U0"]["aqe_lists"] == "Longlist" and rows["U0"]["aqe_scores"]["scores"]["SC_MOMENTUM"] == 60.0
    assert rows["U3"]["aqe_listed"] is False and rows["U3"]["aqe_lists"] == "none" and rows["U3"]["aqe_scores"]["in_daily_list"] is False
    assert rows["GONE"]["aqe_listed"] is None and rows["GONE"]["aqe_scores"]["note"] == "AQE score not available"
    assert all(x["method"] == "whole_universe" for x in rows.values())


# ------------------------------------------------------------------ scorecard series
def test_report_compare_splits_a_into_the_old_method_and_the_standard_scan_with_listed_and_not_listed():
    led = [{"date": "2026-11-12", "ticker": "AAA", "verdict": "ADVANCE"},                                                    # old method, no tag
           {"date": "2026-11-16", "ticker": "BBB", "verdict": "ADVANCE", "method": "whole_universe", "aqe_listed": True},
           {"date": "2026-11-16", "ticker": "CCC", "verdict": "ADVANCE", "method": "whole_universe", "aqe_listed": False},
           {"date": "2026-11-16", "ticker": "DDD", "verdict": "PASS", "method": "whole_universe", "aqe_listed": False}]
    out = RC.split_series({"A": led, "C": []})
    assert set(out) == {"A1", "A2", "A2L", "A2N", "C"}
    assert [r["ticker"] for r in out["A1"]] == ["AAA"] and [r["ticker"] for r in out["A2L"]] == ["BBB"] and [r["ticker"] for r in out["A2N"]] == ["CCC", "DDD"]
    assert set(RC.split_series({"A": led[:1]})) == {"A"}                                                                    # before any Standard Scan row, A is one series
    assert RC.DISPLAY["A2L"].startswith("Committee Standard Scan") and RC.DISPLAY["C"] == "Committee AQE Quant Scan"
