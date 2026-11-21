"""Research extract (one-off): column selection, forward-return maths, the read-only guarantees. No network."""
import importlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def rx(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SCRATCH", str(tmp_path / "scratch"))
    monkeypatch.setenv("RESEARCH_OUT", str(tmp_path / "out"))
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("scripts.research_extract", None)
    saved = {k: os.environ.get(k) for k in ("AQE_DATA_DIR", "AQE_OUTPUT_DIR")}
    m = importlib.import_module("scripts.research_extract")
    yield m
    for k, v in saved.items():                       # the module points src at scratch; never leak that to other tests
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_component_columns_exclude_last_bar_only_detect_fields_and_list_flags(rx):
    from src.scanner.score_runner import SCORE_COLUMNS
    c = rx._component_columns(SCORE_COLUMNS)
    allc = set(c["aggregate"]) | set(c["sub"]) | set(c["reference_composites"])
    for bad in ("div_state", "knn_prob", "pin_bar_state", "vwap_14d", "of_state", "ls_state", "squeeze_breakout_state", "on_longlist", "on_elder", "on_qs"):
        assert bad not in allc, bad
    for good in ("flow_100", "flow_score", "accum_score", "bq_range_tight", "hl_score", "mp_accel", "k39_value", "elder_score"):
        assert good in allc, good
    assert set(c["reference_composites"]) <= {"sc_momentum", "sc_momentum_raw", "sc_position", "sc_position_raw", "sc_m_gates", "sc_p_gates", "pipe_rank"}


def test_the_scratch_dirs_are_set_before_src_resolves_its_paths(tmp_path):
    """Fresh process (as in the workflow): src.data.paths must resolve inside the scratch dir, never the repo's data/."""
    import subprocess
    code = ("import scripts.research_extract as r; from src.data import paths; "
            "print(paths.DATA_DIR); print(paths.OUTPUT_DIR)")
    env = dict(os.environ, RESEARCH_SCRATCH=str(tmp_path / "s"), RESEARCH_OUT=str(tmp_path / "o"))
    env.pop("AQE_DATA_DIR", None); env.pop("AQE_OUTPUT_DIR", None)
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert all(l.startswith(str(tmp_path / "s")) for l in r.stdout.split()), r.stdout


def _fake_state(rx, tmp_path, n_days=60, tickers=("AAA", "BBB", "CCC")):
    from src.scanner.score_runner import SCORE_COLUMNS
    d = pd.bdate_range("2025-01-01", periods=n_days)
    rng = np.random.default_rng(1)
    rows, scores = [], []
    for i, t in enumerate(list(tickers) + ["SPY"]):
        close = 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n_days))
        rows.append(pd.DataFrame({"date": d, "ticker": t, "open": close, "high": close, "low": close, "close": close, "volume": 1e6}))
        if t != "SPY":
            s = pd.DataFrame({c: np.nan for c in SCORE_COLUMNS}, index=range(n_days))
            s["date"], s["ticker"], s["close"] = d, t, close
            s["flow_100"], s["flow_score"] = 50.0 + i, 5.0
            scores.append(s)
    data = Path(os.environ["AQE_DATA_DIR"])
    data.mkdir(parents=True, exist_ok=True)
    panel = pd.concat(rows)
    panel.to_parquet(data / "panel_daily.parquet", index=False)
    panel[panel.ticker == "SPY"].to_parquet(data / "spy_daily.parquet", index=False)
    pd.concat(scores).to_parquet(data / "scores_daily.parquet", index=False)
    (data / "sector_map.json").write_text(json.dumps({"AAA": "XLK", "BBB": "XLF"}))
    return d, panel


def test_extract_forward_returns_vs_spy_and_equal_weight_and_no_production_writes(rx, tmp_path, monkeypatch):
    monkeypatch.setattr(rx, "_restore", lambda: {"store": "test"})
    sent = []
    monkeypatch.setattr(rx, "_drive_put", lambda name, blob, mime: sent.append(name) or {"name": name, "ok": True, "file_id": "fid-" + name, "bytes": len(blob)})
    d, panel = _fake_state(rx, tmp_path)
    meta = rx.extract(years=6, recompute=False)
    out = pd.read_parquet(next((tmp_path / "out").glob("aqe_research_extract_*.parquet")))
    a = out[out.ticker == "AAA"].set_index("date")
    px = panel[panel.ticker == "AAA"].set_index("date")["close"]
    spy = panel[panel.ticker == "SPY"].set_index("date")["close"]
    t = d[10]
    assert a.loc[t, "fwd5"] == pytest.approx(px.shift(-5)[t] / px[t] - 1, rel=1e-4)
    assert a.loc[t, "fwd5_vs_spy"] == pytest.approx(px.shift(-5)[t] / px[t] - spy.shift(-5)[t] / spy[t], abs=1e-5)
    day = out[out.date == t]
    assert day["ew_fwd5"].iloc[0] == pytest.approx(day["fwd5"].mean(), abs=1e-5)
    assert a["fwd20"].iloc[-20:].isna().all(), "the last h sessions have no forward return"
    assert a.loc[t, "sector_etf_current"] == "XLK"
    assert "mcap_current_not_pit" in out.columns and out["mcap_current_not_pit"].isna().all()
    assert not any(c in out.columns for c in ("on_longlist", "on_elder", "div_state", "vwap_14d"))
    assert meta["not_point_in_time"]["universe"].startswith("survivorship")
    assert "aqe_research_extract_meta.json" in sent and not any("snapshot" in n for n in sent)


def test_a_missing_expected_column_is_loud_not_silent(rx, tmp_path, monkeypatch):
    monkeypatch.setattr(rx, "_restore", lambda: {"store": "test"})
    monkeypatch.setattr(rx, "_drive_put", lambda *a, **k: {"name": a[0], "ok": True})
    _fake_state(rx, tmp_path)
    p = Path(os.environ["AQE_DATA_DIR"]) / "scores_daily.parquet"
    pd.read_parquet(p).drop(columns=["accum_score"]).to_parquet(p, index=False)
    with pytest.raises(SystemExit) as e:
        rx.extract(years=6, recompute=False)
    assert "accum_score" in str(e.value)


def test_the_workflow_is_dispatch_only_isolated_and_read_only():
    y = (ROOT / ".github" / "workflows" / "research-extract.yml").read_text()
    assert "workflow_dispatch:" in y and "schedule:" not in y and "pull_request" not in y and "push:" not in y
    assert "group: aqe-research" in y and "aqe-daily" not in y.split("concurrency:")[1].split("permissions:")[0].replace("aqe-daily)", "")
    assert "contents: read" in y and "contents: write" not in y
    code = (ROOT / "scripts" / "research_extract.py").read_text()
    assert "save_snapshot" not in code.replace("never calls save_snapshot*", "")


def test_inventory_handles_a_tickerless_spy_file_and_reports_a_broken_file_loudly(rx, tmp_path, monkeypatch):
    monkeypatch.setattr(rx, "_restore", lambda: {"store": "test"})
    monkeypatch.setattr(rx, "_drive_put", lambda name, blob, mime: {"name": name, "ok": True, "file_id": "x"})
    d, panel = _fake_state(rx, tmp_path)
    data = Path(os.environ["AQE_DATA_DIR"])
    pd.read_parquet(data / "spy_daily.parquet").drop(columns=["ticker"]).to_parquet(data / "spy_daily.parquet", index=False)
    (data / "panel_weekly.parquet").write_bytes(b"not a parquet")
    inv = rx.inventory()
    assert inv["spy_daily"]["rows"] > 0 and inv["spy_daily"]["tickers"] == 1
    assert "error" in inv["panel_weekly"], "a broken file is reported, not hidden"
    assert inv["scores_daily"]["date_min"] and inv["scores_daily"]["names_per_date"]["max"] == 3
    assert "flow_100" in inv["scores_daily"]["non_null_share_by_year"]
    assert (tmp_path / "out" / "inventory.json").exists()


def test_shadow_v2_group_is_separate_and_leaves_live_groups_unchanged(rx):
    from src.scanner.score_runner import SCORE_COLUMNS
    c = rx._component_columns(SCORE_COLUMNS)
    assert c["shadow_v2"] and all(x.endswith("_v2") for x in c["shadow_v2"])
    live = set(c["aggregate"]) | set(c["sub"]) | set(c["reference_composites"])
    assert not (live & set(c["shadow_v2"])), "a shadow column leaked into a live group"
    for good in ("pipe_rank_v2", "flow_100_v2", "structure_100_v2", "atr_score_v2"):
        assert good in c["shadow_v2"], good


def test_shadow_report_shapes_the_promised_numbers(rx):
    df = pd.DataFrame({"atr_score": [0, 10, 10, 20], "atr_score_v2": [0, 5, 10, 20], "base_days": [3, 5, 8, 9], "base_days_v2": [2, 4, 6, 7],
                       "flow_100": [10., 20., 30., 40.], "flow_100_v2": [11., 19., 33., None]})
    rep = rx._shadow_report(df)
    assert rep["rows"] == 4 and rep["null_share"]["flow_100_v2"] == 0.25
    assert rep["atr_score_value_shares"]["live"]["10"] == 0.5 and rep["atr_score_value_shares"]["v2"]["5"] == 0.25
    assert rep["live_vs_v2"]["flow_100 -> flow_100_v2"]["n"] == 3


def test_workflow_passes_rescore_through():
    y = (ROOT / ".github" / "workflows" / "research-extract.yml").read_text()
    assert "rescore:" in y and "RESCORE: ${{ inputs.rescore }}" in y and "--rescore" in y


def test_merge_diag_sums_ints_and_dicts(rx):
    t = {}
    rx._merge_diag(t, {"tickers_scored": 3, "nan_v2_bars": {"a": 2}, "scope": "targeted"})
    rx._merge_diag(t, {"tickers_scored": 4, "nan_v2_bars": {"a": 1, "b": 5}, "scope": "targeted"})
    assert t == {"tickers_scored": 7, "nan_v2_bars": {"a": 3, "b": 5}, "scope": "targeted"}


def test_rescore_runs_in_shards_reduces_each_and_restores_the_output_path(rx, tmp_path, monkeypatch):
    from src.data import earnings as E
    from src.scanner import score_runner
    _fake_state(rx, tmp_path)
    monkeypatch.setattr(E, "pull_earnings_dates_full", lambda c, t: {"tickers": len(t), "failed": [], "aborted": False})
    import src.data.fmp_client as fc
    monkeypatch.setattr(fc, "FMPClient", lambda *a, **k: object())
    calls, orig_path = [], score_runner.SCORES_DAILY

    def fake_build(only_tickers=None):
        calls.append(list(only_tickers))
        rows = pd.DataFrame({"date": pd.to_datetime(["2026-01-02"] * len(only_tickers)), "ticker": only_tickers, "x_v2": 1.0})
        rows.to_parquet(score_runner.SCORES_DAILY, index=False)
        score_runner.SCORES_DAILY.with_name("score_diagnostics_v2.json").write_text(json.dumps({"tickers_scored": len(only_tickers)}))
    monkeypatch.setattr(score_runner, "build_scores", fake_build)
    info = rx._rescore(["date", "ticker", "x_v2"], n_shards=2)
    assert len(calls) == 2 and sorted(sum(calls, [])) == sorted(set(sum(calls, [])))
    assert info["score_diagnostics"]["tickers_scored"] == len(sum(calls, []))
    got = pd.concat([pd.read_parquet(x) for x in info["parts"]])
    assert got["x_v2"].dtype == "float32" and set(got["ticker"]) == set(sum(calls, []))
    assert score_runner.SCORES_DAILY == orig_path, "the scores path must be restored after sharding"
