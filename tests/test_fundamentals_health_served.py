"""PM rulings 2 and 3 (2026-11-19): fundamentals from FMP with the source per field; every calculated sub-score asked (health parts) served. Offline."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
MENUS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "contracts" / "voice_menus.json"
CANON = ROOT / "aegis" / "plugin" / "aegis-voices" / "canon"

os.environ.setdefault("AEGIS_REPORT", "A")
spec = importlib.util.spec_from_file_location("pma_pipeline_fh", TOOLS / "pma_pipeline.py")
PP = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(TOOLS))
spec.loader.exec_module(PP)

ENTRY = {"pulled_on": "2026-11-18", "status": "served",
         "growth_3y": [{"date": "2025-10-31", "growthEPS": 0.0338, "growthRevenue": 0.0673}],
         "ratios_ttm": {"netProfitMarginTTM": 0.1953, "priceToEarningsRatioTTM": 33.83},
         "extras": {"status": "served", "pulled_on": "2026-11-18", "roe_ttm_pct": 41.8, "roe_source": "FMP key-metrics-ttm returnOnEquityTTM",
                    "quarterly": {"eps_growth_yoy_pct": 80.3, "sales_growth_yoy_pct": 13.9, "eps_note": None,
                                  "source": "FMP income-statement (quarter): Q3 FY2026 vs Q3 FY2025, diluted EPS and revenue"}}}


def test_a_row_gets_every_fund_field_with_its_source_and_periods_in_fund_basis():
    f = PP._fund_row_fields("CAKE", ENTRY)
    assert f["fund_eps_growth_q_yoy"] == 80.3 and f["fund_sales_growth_q_yoy"] == 13.9 and f["fund_roe_ttm"] == 41.8
    assert f["fund_eps_growth_annual"] == 3.4 and f["fund_sales_growth_annual"] == 6.7 and f["fund_net_margin_ttm"] == 19.5 and f["fund_pe_ttm"] == 33.8
    assert f["fund_sponsorship"] == "NOT_AVAILABLE"
    b = f["fund_basis"]
    for part in ("Q3 FY2026 vs Q3 FY2025", "FMP income-statement-growth FY 2025-10-31", "FMP key-metrics-ttm", "NOT_AVAILABLE", "pulled 2026-11-18"):
        assert part in b, part


def test_a_missing_figure_stays_null_and_the_basis_says_why_a_missing_row_is_declared():
    e = json.loads(json.dumps(ENTRY))
    e["extras"] = {"status": "partial", "missing": {"quarterly": "no Q3 FY2025 quarter in the 4 quarters served", "roe": "unrouted"}}
    f = PP._fund_row_fields("NEW", e)
    assert f["fund_eps_growth_q_yoy"] is None and f["fund_roe_ttm"] is None
    assert "quarterly EPS/sales growth NOT SERVED (no Q3 FY2025 quarter" in f["fund_basis"] and "ROE NOT SERVED (unrouted)" in f["fund_basis"]
    g = PP._fund_row_fields("ZZZ", None)
    assert all(g[k] is None for k in PP.FUND_FIELDS if k != "fund_basis") and g["fund_basis"].startswith("NOT SERVED: no fundamentals row for ZZZ")


def test_the_merge_command_stamps_candidate_and_export_rows_in_place_and_is_idempotent(tmp_path):
    (tmp_path / "pack.json").write_text(json.dumps({"tickers": {"AAA": ENTRY}, "extras_coverage": {"served": 1}}))
    (tmp_path / "cs.json").write_text(json.dumps({"universe": [{"ticker": "AAA"}, {"ticker": "BBB"}]}))
    (tmp_path / "ex.json").write_text(json.dumps({"daily_list": [{"ticker": "AAA"}], "held_positions": [{"ticker": "BBB"}]}))
    cmd = [sys.executable, str(TOOLS / "pma_pipeline.py"), "fundamentals-merge", "--fundamentals", str(tmp_path / "pack.json"), "--candidates", str(tmp_path / "cs.json"),
           "--export", str(tmp_path / "ex.json")]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, AEGIS_REPORT="A"))
    assert r.returncode == 0, r.stderr
    assert "no pack entry for ['BBB']" in r.stdout
    cs = {x["ticker"]: x for x in json.loads((tmp_path / "cs.json").read_text())["universe"]}
    assert cs["AAA"]["fund_eps_growth_q_yoy"] == 80.3 and cs["BBB"]["fund_basis"].startswith("NOT SERVED")
    ex = json.loads((tmp_path / "ex.json").read_text())
    assert ex["daily_list"][0]["fund_roe_ttm"] == 41.8 and ex["held_positions"][0]["fund_eps_growth_q_yoy"] is None
    before = (tmp_path / "cs.json").read_text()
    subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, AEGIS_REPORT="A"))
    assert (tmp_path / "cs.json").read_text() == before
    bad = subprocess.run(cmd[:3] + [str(tmp_path / "nope.json")] + cmd[4:], capture_output=True, text=True, env=dict(os.environ, AEGIS_REPORT="A"))
    assert bad.returncode != 0, "a missing pack is a loud exit, never an empty merge"


def test_the_fundamentals_reach_only_the_seats_whose_canon_asks():
    m = json.loads(MENUS.read_text())
    for f in ("fund_eps_growth_q_yoy", "fund_eps_growth_annual", "fund_sales_growth_q_yoy", "fund_sales_growth_annual", "fund_roe_ttm", "fund_sponsorship", "fund_basis"):
        assert f in m["oneil"], f
    for f in ("fund_eps_growth_q_yoy", "fund_eps_growth_annual", "fund_sales_growth_q_yoy", "fund_roe_ttm", "fund_basis"):
        assert f in m["minervini"], f
    for v in ("livermore", "elder-lens", "seow", "raschke", "wyckoff"):
        assert not [f for f in m[v] if f.startswith("fund_")], v


def test_the_oneil_and_minervini_canon_read_the_fund_fields_and_keep_sponsorship_declared_unavailable():
    o = yaml.safe_load((CANON / "oneil" / "canon.lock.yaml").read_text())
    r10 = next(r for r in o["recognisers"] if r["id"] == "R10")
    assert "fund_roe_ttm" in r10["fields"] and "fund_sponsorship" in r10["fields"] and "NOT_AVAILABLE" in r10["then"] and "fund_basis" in r10["then"]
    mv = yaml.safe_load((CANON / "minervini" / "canon.lock.yaml").read_text())
    r4 = next(r for r in mv["recognisers"] if r["id"] == "R4")
    assert "fund_eps_growth_q_yoy" in r4["fields"] and "company_category is still NOT_SERVED" in r4["then"]


def test_the_health_parts_are_in_the_subcomponents_block_and_on_the_four_seats_menus():
    from src.data.drive_sync import _SUBCOMPONENT_SPEC, _subcomponents
    assert _SUBCOMPONENT_SPEC["health"] == ["hl_trend", "hl_flow", "hl_rs", "hl_risk", "hl_higher_lows", "hl_trend_bars", "hl_vol_updn", "hl_atr_spike"]
    row = {"hl_trend": 28.4, "hl_flow": 17.0, "hl_rs": 12.5, "hl_risk": -4.0}
    h = _subcomponents(row)["health"]
    assert h["hl_trend"] == 28.4 and h["hl_flow"] == 17.0 and h["hl_rs"] == 12.5 and h["hl_risk"] == -4.0 and h["hl_atr_spike"] is None
    m = json.loads(MENUS.read_text())
    want = {"minervini": ("hl_trend", "hl_risk"), "oneil": ("hl_rs", "hl_risk"), "livermore": ("hl_trend", "hl_flow"), "wyckoff": ("hl_flow", "hl_risk")}
    for seat, fields in want.items():
        for f in fields:
            assert f"subcomponents.health.{f}" in m[seat], (seat, f)


def test_no_decider_canon_still_declares_a_served_health_part_not_served():
    for v in ("minervini", "oneil", "livermore", "wyckoff"):
        t = (CANON / v / "canon.lock.yaml").read_text()
        for part in ("hl_trend", "hl_flow", "hl_rs"):
            assert f"{part} NOT_SERVED" not in t, (v, part)
            assert f"declare {part} NOT_SERVED" not in t and f"I declare {part}" not in t, (v, part)
