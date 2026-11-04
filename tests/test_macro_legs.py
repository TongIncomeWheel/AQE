"""Reason-coded macro legs, the feed-timing record, and the committee-gate rule (PM 2026-11-04: 'stale because we are slow' vs
'stale because the publisher is')."""
import importlib.util
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from src.macro import legs as L
from src.data import feed_timing as FT

ROOT = Path(__file__).resolve().parents[1]
EXP = "2026-11-03"
TODAY = date(2026, 11, 4)


def _legs(**kw):
    base = dict(breadth={"freshness": {"as_of": EXP, "stale": False, "current": 4314, "total": 4314}},
                vol_series={"vix": EXP, "vixeq": "2026-11-02", "dspx": "2026-11-02", "vix3m": EXP, "vix9d": EXP, "cor1m": EXP},
                cot_as_of="2026-10-27", heartbeat_asof=EXP, cboe_ok=True)
    base.update(kw)
    return {r["leg"]: r for r in L.build_legs(EXP, TODAY, **base)}


def test_the_3_nov_morning_reads_publisher_lag_for_vixeq_and_dspx_and_cadence_for_cot():
    t = _legs()
    assert t["dispersion_vixeq"]["reason"] == L.LAG and t["dspx"]["reason"] == L.LAG
    assert t["vix_level"]["reason"] == L.CURRENT and t["vix3m"]["reason"] == L.CURRENT
    assert t["positioning_cot"]["reason"] == L.CADENCE and "next release 2026-11-06" in t["positioning_cot"]["detail"]
    assert t["breadth_whole_market"]["reason"] == L.CURRENT
    assert L.blocking(list(t.values())) == []                          # a publisher lag never blocks


def test_a_panel_we_did_not_refresh_is_our_budget_and_blocks_and_a_missing_source_is_source_down():
    t = _legs(breadth={"freshness": {"as_of": EXP, "stale": True, "reason": "1600/4314 carry it", "current": 1600, "total": 4314}})
    assert t["breadth_whole_market"]["reason"] == L.BUDGET
    assert [r["leg"] for r in L.blocking(list(t.values()))] == ["breadth_whole_market"]
    t = _legs(breadth={}, vol_series={}, cot_as_of=None, cboe_ok=False)
    assert t["breadth_whole_market"]["reason"] == L.DOWN and t["vix_level"]["reason"] == L.DOWN and t["positioning_cot"]["reason"] == L.DOWN
    t = _legs(cot_as_of="2026-10-06")
    assert t["positioning_cot"]["reason"] == L.DOWN and "missing" in t["positioning_cot"]["detail"]      # a missed weekly release is not 'cadence'


def test_feed_timing_appends_one_entry_per_run_keeps_history_and_never_raises(tmp_path):
    class R:
        def __init__(self, text, lm): self.text, self.status_code, self.headers = text, 200, {"Last-Modified": lm}
    def get(u):
        return R("10/30/2026,1\n11/03/2026,2\n", "Wed, 04 Nov 2026 02:11:03 GMT") if "cboe" in u else R('"WHEAT",261027,2026-10-27,001602', "Fri, 30 Oct 2026 19:27:45 GMT")
    d1 = FT.record("2026-11-03", legs=[{"leg": "dspx", "as_of": "2026-11-02", "reason": "PUBLISHER_LAG"}], out_dir=tmp_path, previous_path=tmp_path / "none.json", get=get)
    e = d1["history"][-1]
    assert e["cboe"]["VIXEQ"]["last_modified"].startswith("Wed, 04 Nov 2026 02:11") and e["cboe"]["VIX"]["newest_row_date"] == "11/03/2026"
    assert e["cftc"]["report_date"] == "2026-10-27" and e["legs"][0]["reason"] == "PUBLISHER_LAG"
    d2 = FT.record("2026-11-04", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=get)
    assert [h["run_date"] for h in d2["history"]] == ["2026-11-03", "2026-11-04"]
    d3 = FT.record("2026-11-04", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=get)       # a rerun replaces, never duplicates
    assert [h["run_date"] for h in d3["history"]] == ["2026-11-03", "2026-11-04"]
    boom = lambda u: (_ for _ in ()).throw(RuntimeError("down"))
    assert "error" in FT.record("2026-11-05", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=boom)["history"][-1]["cboe"]["VIX"]


def _check_module():
    p = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py"
    spec = importlib.util.spec_from_file_location("check_legs", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_the_gate_fails_our_budget_and_two_nights_running_and_only_warns_a_publisher_lag():
    C = _check_module()
    row = lambda leg, rc: {"leg": leg, "as_of": "2026-11-02", "expected": EXP, "reason": rc, "detail": "d"}
    f, n = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "PUBLISHER_LAG"), row("positioning_cot", "PUBLISHER_CADENCE")]}}, None)
    assert f == [] and any("WARN" in x and "PUBLISHER_LAG" in x for x in n) and any("PUBLISHER_CADENCE" in x for x in n)
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("breadth_whole_market", "OUR_BUDGET")]}}, None)
    assert len(f) == 1 and "OUR_BUDGET" in f[0]
    f, _ = C.check_macro_legs({"data_freshness": {}}, None)
    assert len(f) == 1 and "cannot be audited" in f[0]
    hist = {"history": [{"run_date": "2026-11-02", "legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}]},
                        {"run_date": "2026-11-03", "legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}, {"leg": "vix_level", "reason": "CURRENT"}]}]}
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "PUBLISHER_LAG")]}}, hist)
    assert len(f) == 1 and "two nights running" in f[0] and "dspx" in f[0]
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "CURRENT")]}}, {"history": [{"legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}]}, {"legs": [{"leg": "dspx", "reason": "CURRENT"}]}]})
    assert f == []
