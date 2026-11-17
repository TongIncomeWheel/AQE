"""PM 2026-11-17 ("Stage 1-4 builds"): the Weinstein stage layer wired into the committee at three levels: market, group (sector ETF) and ticker."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
sys.path.insert(0, str(TOOLS))
import stage_brief as SB  # noqa: E402

MENUS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "contracts" / "voice_menus.json"
FIX = ROOT / "tests" / "fixtures" / "cards_v3"
TOOL = TOOLS / "pma_cards_v3.py"


def _export():
    mk = {"SPY": {"status": "OK", "stage": 2, "stage_name": "Advancing", "weeks_in_stage": 29, "candidate": 3, "candidate_forming": 2,
                  "distribution_days": {"count": 8, "canon_threshold": 4, "window_sessions": 25}},
          "QQQ": {"status": "OK", "stage": 3, "stage_name": "Topping", "weeks_in_stage": 2, "candidate": 3, "distribution_days": {"count": 3, "canon_threshold": 4, "window_sessions": 25}}}
    sec = {"XLK": {"status": "OK", "stage": 3, "weeks_in_stage": 5}, "XLV": {"status": "OK", "stage": 2, "weeks_in_stage": 12}, "XLU": {"status": "NA", "reason": "short history"}}
    return {"stage_market": {"status": "OK", "headline": "SPY is Advancing (Stage 2), QQQ is Topping (Stage 3).", "market": mk, "sectors": sec,
                             "breadth": {"status": "OK", "now": {"n": 800, "stage_2_pct": 40.3, "stage_4_pct": 23.1}, "four_weeks_ago": {"stage_2_pct": 37.2, "stage_4_pct": 34.0}}},
            "daily_list": [{"ticker": "AAA", "stage": 2, "stage_weeks": 9, "trend_template": "PASS", "trend_template_met": 8, "stage2_confirmed": True,
                            "stage_detail": {"sector_stage": 2, "market_stage": 2}},
                           {"ticker": "BBB", "stage": 3, "stage_weeks": 2, "stage_transition": "TOPPING", "trend_template": "FAIL", "trend_template_met": 5, "stage2_confirmed": False,
                            "stage_detail": {"sector_stage": 3, "market_stage": 2}}], "held_positions": []}


def test_the_distribution_day_line_is_the_canons_own_four():
    import importlib
    sys.path.insert(0, str(ROOT))
    spec = importlib.import_module("src.stages.spec")
    assert spec.CANON_DD_COUNT == 4 and spec.CANON_DD_WINDOW_SESSIONS == 25


def test_stage_brief_prints_market_group_breadth_and_a_row_for_every_pick():
    ex = _export()
    cons = [{"ticker": "AAA", "verdict": "ADVANCE"}, {"ticker": "BBB", "verdict": "HOLD-FOR-CONDITIONS"}, {"ticker": "ZZZ", "verdict": "ADVANCE"}, {"ticker": "PPP", "verdict": "PASS"}]
    md = SB.render_md(ex, cons)
    assert md.startswith("### Stage weather") and SB.HEADER in md
    assert "| SPY | Stage 2 advancing (change in progress) | 29 | 8 | at or above the line of 4 |" in md
    assert "| QQQ | Stage 3 topping | 2 | 3 | under the line of 4 |" in md
    assert "| XLV | Stage 2 advancing | 12 |" in md and "| XLU | not read: short history | n/a |" in md
    assert "Stage 2 40.3% now vs 37.2% four weeks ago" in md
    assert "| **AAA** | Stage 2 advancing | 9 | Stage 2 advancing | Stage 2 advancing | PASS (8 of 8) | yes |" in md
    assert "(topping this week)" in md and "| **ZZZ** | not read:" in md and "**PPP**" not in md                    # a name with no stage read is loud; a PASS is not a pick


def test_a_missing_layer_is_one_loud_line_never_an_empty_table():
    md = SB.render_md({"daily_list": []}, [])
    assert "Stage weather unavailable: the export carries no stage read" in md and SB.HEADER not in md
    bad = SB.render_md({"stage_market": {"status": "UNAVAILABLE", "reason": "no weekly panel"}}, [])
    assert "Stage weather unavailable: no weekly panel" in bad


def test_the_four_stage_seats_are_served_the_stage_columns_and_no_other_seat_is():
    m = json.loads(MENUS.read_text(encoding="utf-8"))
    for seat in ("minervini", "oneil"):
        assert {"stage", "stage_weeks", "stage2_confirmed", "trend_template", "trend_template_met", "stage_detail.sector_stage", "stage_detail.market_stage"} <= set(m[seat]), seat
    for seat in ("wyckoff", "livermore"):
        assert {"stage", "stage_weeks", "stage_transition", "stage_detail.sector_stage", "stage_detail.market_stage"} <= set(m[seat]), seat
    for seat in ("raschke", "seow", "elder-lens"):
        assert not [c for c in m[seat] if c.startswith("stage")], seat


def test_the_candidate_set_and_packets_carry_the_stage_columns(tmp_path):
    fx = FIX / "aqe_daily_export.json"
    if not fx.exists():
        pytest.skip("no export fixture")
    ex = json.loads(fx.read_text())
    for r in ex["daily_list"]:
        r.update({"stage": 2, "stage_name": "Advancing", "stage_weeks": 7, "stage_candidate": 2, "stage2_confirmed": True, "trend_template": "PASS", "trend_template_met": 8,
                  "stage_detail": {"sector_stage": 2, "market_stage": 3}})
    p = tmp_path / "ex.json"; p.write_text(json.dumps(ex))
    env = {"PATH": "/usr/bin:/usr/local/bin"}
    cs, out = tmp_path / "cs.json", tmp_path / "pk"
    r = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "trim", "--export", str(p), "--date", "2026-11-04", "--out", str(cs)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    r = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "packets", "--candidates", str(cs), "--export", str(p), "--menus", str(MENUS), "--date", "2026-11-04", "--outdir", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    hdr = lambda seat: [l for l in (out / f"{seat}.tsv").read_text().split("\n") if l and not l.startswith("#")][0].split("\t")
    assert "stage" in hdr("minervini") and "stage_detail.market_stage" in hdr("oneil") and "stage_detail.sector_stage" in hdr("wyckoff")
    assert "stage" not in hdr("raschke")
    rows = [l.split("\t") for l in (out / "minervini.tsv").read_text().split("\n") if l and not l.startswith("#")][1:]
    i = hdr("minervini").index("stage_detail.market_stage")
    vals = [r[i] for r in rows]
    assert vals.count("3") == len(ex["daily_list"]) and set(vals) <= {"3", "null"}                  # the values arrive, not a blank column (a held row the stamp did not touch stays null)


def _render(run):
    out = run / "out.html"
    r = subprocess.run([sys.executable, str(TOOL), "--run-dir", str(run), "--out", str(out), "--refresh-dir", str(run / "ref")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    return out.read_text(encoding="utf-8")


def test_cards_print_the_stage_card_and_a_stage_line_per_name(tmp_path):
    if not (FIX / "aqe_daily_export.json").exists():
        pytest.skip("no fixture")
    run = tmp_path / "run"; shutil.copytree(FIX, run)
    ex = json.loads((run / "aqe_daily_export.json").read_text())
    base = _export()
    ex["stage_market"] = base["stage_market"]
    for r in ex["daily_list"]:
        r.update({"stage": 2, "stage_name": "Advancing", "stage_weeks": 7, "trend_template": "PASS", "trend_template_met": 8, "stage2_confirmed": True,
                  "stage_detail": {"sector_stage": 2, "market_stage": 3}})
    (run / "aqe_daily_export.json").write_text(json.dumps(ex))
    h = _render(run)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
    assert "The market is in stage 2 advancing and 1 of 3 sector ETFs are advancing" in t and "O'Neil line" in t and "at or above the line of 4" in t
    assert "Stage, group and market" in t and "Stage: Stage 2 advancing, week 7; group Stage 2 advancing; market Stage 3 topping; Trend Template pass (8 of 8)" in t
    # without the layer the page still renders and says so
    ex2 = json.loads((FIX / "aqe_daily_export.json").read_text())
    (run / "aqe_daily_export.json").write_text(json.dumps(ex2))
    assert "Stage weather is not in this export" in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _render(run)))
