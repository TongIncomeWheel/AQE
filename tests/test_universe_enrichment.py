"""PM 2026-11-19: screened universe-only names get hourly-bar elder_context and the M&A flag, budgeted, loud. Offline (stub FMP client)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"

from src.pipeline import universe_enrichment as UE  # noqa: E402


class Client:
    """Hourly bars for AAA and BBB; none for CCC; raises for DDD."""
    def __init__(self):
        self.calls = []

    def get_intraday_bars(self, t, interval="1hour"):
        self.calls.append(t)
        if t == "DDD":
            raise RuntimeError("boom")
        if t == "CCC":
            return []
        return [{"date": f"2026-11-1{d} {h:02d}:00:00", "open": 10 + d, "high": 11 + d, "low": 9 + d, "close": 10.5 + d, "volume": 1000 * (h + 1)}
                for d in range(2, 7) for h in range(10, 16)]


DAILY = {t: [{"date": f"2026-10-{d:02d}", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1e6} for d in range(1, 21)] for t in ("AAA", "BBB", "CCC", "DDD")}
ROWS = [{"ticker": t, "elder_5d": [3, 4, 5, 6, 7]} for t in ("AAA", "BBB", "CCC", "DDD")]


def _ma(tk, cl, today):
    return {"scan_status": "ok", "n_scanned": len(tk), "n_failed": 0, "n_flagged": 1, "tickers": {
        t: ({"ma_status": "PENDING_TARGET", "ma_note": "definitive agreement", "ma_evidence": {"headline": "x"}} if t == "AAA"
            else {"ma_status": "NONE", "ma_note": "no pending deal found", "ma_evidence": None}) for t in tk}}


def test_build_serves_hourly_context_and_ma_and_counts_every_gap():
    d = UE.build(["AAA", "BBB", "CCC", "DDD"], ROWS, "2026-11-19", Client(), daily=DAILY, ma_refresh=_ma)
    a = d["tickers"]["AAA"]
    assert a["elder_context"]["vwap_5d"]["value"] is not None and a["hourly_bars"] > 0
    assert a["ma_status"] == "PENDING_TARGET" and d["tickers"]["BBB"]["ma_status"] == "NONE"
    assert d["elder"]["served"] == 2 and d["elder"]["no_hourly_bars"] == 2
    assert d["status"] == "ok" or d["status"] == "partial"
    assert any("DDD" in e and "hourly bars failed" in e for e in d["errors"]), "a failed fetch is named, not hidden"
    assert d["ma"]["n_flagged"] == 1 and d["ma"]["unscanned"] == []


def test_a_name_the_ma_scan_does_not_reach_is_unknown_never_blank_and_the_status_says_partial():
    def partial(tk, cl, today):
        return {"scan_status": "partial", "n_scanned": 1, "n_failed": 1, "n_flagged": 0, "tickers": {"AAA": {"ma_status": "NONE", "ma_note": "n", "ma_evidence": None}}}
    d = UE.build(["AAA", "BBB"], ROWS, "2026-11-19", Client(), daily=DAILY, ma_refresh=partial)
    assert d["tickers"]["BBB"]["ma_status"] == "UNKNOWN" and "never as no deal" in d["tickers"]["BBB"]["ma_note"]
    assert d["ma"]["unscanned"] == ["BBB"] and d["status"] == "partial"


def test_the_hourly_budget_is_enforced_and_declared():
    import itertools
    ticks = itertools.count(0, 400)
    d = UE.build(["AAA", "BBB", "CCC"], ROWS, "2026-11-19", Client(), daily=DAILY, ma_refresh=_ma, budget_s=500, clock=lambda: next(ticks))
    assert d["elder"]["skipped_over_budget"] >= 1 and d["status"] == "partial"


def test_a_failed_ma_scan_reads_unknown_for_every_name():
    def boom(tk, cl, today):
        raise RuntimeError("quota")
    d = UE.build(["AAA"], ROWS, "2026-11-19", Client(), daily=DAILY, ma_refresh=boom)
    assert d["tickers"]["AAA"]["ma_status"] == "UNKNOWN" and d["ma"]["scan_status"] == "failed"
    assert any("M&A scan failed" in e for e in d["errors"])


def _augment(tmp_path, enrichment):
    exp = {"daily_list": [{"ticker": "KEEP", "ma_status": "NONE"}], "held_positions": []}
    uni = {"date": "2026-11-19", "rows": [{"ticker": "AAA", "elder_context": {"volume": {"avg_vol_20d": 1000}}}, {"ticker": "BBB"}, {"ticker": "KEEP"}]}
    ss = {"seats": {"oneil": [{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "KEEP"}]}}
    for n, o in (("export.json", exp), ("uni.json", uni), ("ss.json", ss)):
        (tmp_path / n).write_text(json.dumps(o))
    cmd = [sys.executable, str(TOOLS / "pma_pipeline.py"), "augment-export", "--export", str(tmp_path / "export.json"), "--universe-rows", str(tmp_path / "uni.json"),
           "--seat-sets", str(tmp_path / "ss.json"), "--out", str(tmp_path / "wu.json")]
    if enrichment:
        cmd += ["--enrichment", str(enrichment)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, AEGIS_REPORT="A"))
    assert r.returncode == 0, r.stderr
    return json.loads((tmp_path / "wu.json").read_text()), r.stdout


def test_augment_export_fills_universe_only_rows_from_the_enrichment_and_marks_the_rest_unknown(tmp_path):
    doc = UE.build(["AAA"], ROWS, "2026-11-19", Client(), daily=DAILY, ma_refresh=_ma)
    (tmp_path / "ue.json").write_text(json.dumps(doc))
    wu, out = _augment(tmp_path, tmp_path / "ue.json")
    rows = {r["ticker"]: r for r in wu["daily_list"]}
    assert rows["AAA"]["ma_status"] == "PENDING_TARGET" and rows["AAA"]["elder_context"]["vwap_5d"]["value"] is not None
    assert rows["AAA"]["elder_context"]["volume"]["avg_vol_20d"] == 1000, "a value the row already carries is never overwritten"
    assert rows["BBB"]["ma_status"] == "UNKNOWN" and "never as no deal" in rows["BBB"]["ma_note"]
    assert rows["KEEP"]["ma_status"] == "NONE", "an AQE-listed name keeps its own row untouched"
    assert "M&A scanned 1, M&A UNKNOWN 1" in out


def test_augment_export_without_an_enrichment_file_is_loud_and_never_blank(tmp_path):
    wu, out = _augment(tmp_path, None)
    rows = {r["ticker"]: r for r in wu["daily_list"]}
    assert rows["AAA"]["ma_status"] == "UNKNOWN" and rows["BBB"]["ma_status"] == "UNKNOWN"
    assert "WARNING enrichment" in out and "no enrichment file" in out


def test_the_nightly_and_the_topup_both_call_the_enrichment_and_run_yaml_passes_the_file():
    assert "universe_enrichment" in (ROOT / "src" / "pipeline" / "daily_orchestrator.py").read_text()
    assert "_enrich(" in (ROOT / "src" / "pipeline" / "committee_topup.py").read_text()
    assert "--enrichment aegis/output/committee_data/universe_enrichment.json" in (ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "RUN.yaml").read_text()
