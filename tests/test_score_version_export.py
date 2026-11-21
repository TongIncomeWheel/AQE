"""The export's score-version blocks: `score_version`, `score_exclusions` and `<field>_legacy` on rows, built from a real scores build in both versions."""
import json

import pandas as pd
import pytest

from src.data import score_version_export as SVE
from src.engines import score_version as SV
import test_score_version as TSV          # reuse the end-to-end scores builder


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(SV.ENV_VAR, raising=False)


def _ctx(tmp_path, monkeypatch, version):
    TSV._build(tmp_path, monkeypatch, version)
    return SVE.load_context(tmp_path / version / "scores_daily.parquet")


def test_v1_block_is_dark_lists_the_would_be_exclusions_and_legacy_equals_live(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "v1")
    sv, ex = SVE.blocks(ctx)
    assert sv["version"] == "v1" and sv["status"] == "live" and sv["scores_cache"] == {"versions": ["v1"], "problem": None}
    assert "sc_momentum" in sv["legacy_fields"] and "flow_100" in sv["legacy_fields"] and len(sv["legacy_fields"]) == 41
    assert ex["applies_now"] is False and ex["total"] == 1 and ex["by_reason"]["earnings history unavailable"]["tickers"] == ["BBB"]
    assert "WOULD exclude" in ex["basis"]
    rows = [{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "NOPE"}]
    assert SVE.attach_legacy(rows, ctx) == 2
    for r in rows[:2]:
        assert r["sc_momentum_legacy"] is not None and r["score_version"] == "v1"
    assert "sc_momentum_legacy" not in rows[2]                                      # a ticker with no scores row gets nothing invented
    json.dumps(rows)                                                                 # JSON-safe (no NaN / numpy scalars)


def test_v2_block_excludes_the_named_names_and_keeps_the_old_value_beside_the_live_one(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "v2")
    sv, ex = SVE.blocks(ctx)
    assert sv["version"] == "v2" and sv["scores_cache"]["versions"] == ["v2"] and sv["scores_cache"]["problem"] is None
    assert ex["applies_now"] is True and "EXCLUDED" in ex["basis"] and ex["by_reason"] == {"earnings history unavailable": {"count": 1, "tickers": ["BBB"]}}
    assert "BBB" not in ctx["rows"] and "AAA" in ctx["rows"]
    a = ctx["rows"]["AAA"]
    assert a["sc_momentum_legacy"] is not None and a["flow_100_legacy"] is not None


def test_a_mixed_unstamped_or_wrong_version_cache_is_reported_in_the_block(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "v1")
    monkeypatch.setenv(SV.ENV_VAR, "v2")                                            # the switch moved but the cache is still v1
    sv, _ = SVE.blocks(SVE.load_context(tmp_path / "v1" / "scores_daily.parquet"))
    assert "holds v1 but the active version is v2" in sv["scores_cache"]["problem"]
    df = pd.read_parquet(tmp_path / "v1" / "scores_daily.parquet")
    df.loc[df.index[:5], SV.VERSION_COLUMN] = "v2"
    df.to_parquet(tmp_path / "v1" / "mixed.parquet", index=False)
    sv, _ = SVE.blocks(SVE.load_context(tmp_path / "v1" / "mixed.parquet"))
    assert "MIXED" in sv["scores_cache"]["problem"]
    df.drop(columns=[SV.VERSION_COLUMN]).to_parquet(tmp_path / "v1" / "unstamped.parquet", index=False)
    sv, _ = SVE.blocks(SVE.load_context(tmp_path / "v1" / "unstamped.parquet"))
    assert "no score_version stamp" in sv["scores_cache"]["problem"]


def test_missing_scores_or_diagnostics_are_loud_never_an_empty_list(tmp_path):
    ctx = SVE.load_context(tmp_path / "nope.parquet")
    sv, ex = SVE.blocks(ctx)
    assert sv["status"] == "error" and "missing" in sv["reason"]
    assert ex["status"] == "unknown" and "NOT KNOWN" in ex["reason"]                 # no diagnostics: unknown, not 'none'


def test_the_export_glue_assigns_only_new_keys_and_feeds_data_quality():
    from pathlib import Path
    import re
    src = (Path(__file__).resolve().parent.parent / "src" / "data" / "drive_sync.py").read_text()
    block = src[src.index("# ---- Score version (PM 2026-11-21 cutover)"):src.index("# ---- Stage at ticker / sector / market level")]
    assigned = set(re.findall(r'export\["([a-z_]+)"\]\s*(?:,\s*export\["[a-z_]+"\]\s*)?=', block))
    assert assigned <= {"score_version", "score_exclusions"}, assigned
    assert 'export["data_quality"]["score_version"]' in src
    from src.data import drive_sync as DS
    for k in ("score_version", "score_exclusions", "sc_momentum_legacy", "flow_100_legacy", "base_days_legacy"):
        assert k in DS._FIELD_GLOSSARY, k


def test_the_scanner_shows_the_version_a_mixed_cache_error_and_the_named_exclusions(tmp_path, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from src.ui import shared
    root = Path(__file__).resolve().parent.parent
    sv = {"status": "live", "version": "v1", "cutover_date": None, "scores_cache": {"versions": ["v1", "v2"], "problem": "scores cache is MIXED (['v1', 'v2']); expected v1 only"}}
    sx = {"status": "live", "applies_now": False, "total": 2, "by_reason": {"earnings history unavailable": {"count": 2, "tickers": ["AAA", "BBB"]}}}
    p = tmp_path / "aqe_daily_export.json"
    p.write_text(json.dumps({"date": "2026-11-23", "daily_list": [], "score_version": sv, "score_exclusions": sx,
                             "data_quality": {"score_version": {"ok": False, "problem": sv["scores_cache"]["problem"]}}}))
    monkeypatch.setattr(shared, "EXPORT_JSON", p)
    at = AppTest.from_file(str(root / "src" / "ui" / "1_Scanner.py")).run(timeout=180)
    assert not at.exception, [e.value for e in at.exception][:2]
    assert any("Score version problem" in e.value and "MIXED" in e.value for e in at.error)
    assert any("Score version: **v1**" in c.value for c in at.caption)
    assert any("would be excluded under v2" in x.label for x in at.expander)
