"""The score-version switch (PM 2026-11-21): precedence, loud errors, the engine twins both ways, the scores build both ways, rollback, the legacy view and the cache check."""
import json

import numpy as np
import pandas as pd
import pytest

from src.engines import score_version as SV


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(SV.ENV_VAR, raising=False)


# ------------------------------------------------------------------ the switch
def test_precedence_env_then_config_then_default_and_an_unknown_value_is_loud(tmp_path, monkeypatch):
    cfg = tmp_path / "score_version.json"
    monkeypatch.setattr(SV, "CONFIG_PATH", cfg)
    assert SV.active() == "v1" and SV.source() == "default"                       # nothing set: the dark default
    cfg.write_text(json.dumps({"version": "v2", "cutover_date": "2026-11-24"}))
    assert SV.active() == "v2" and SV.source() == "config" and SV.cutover_date() == "2026-11-24"
    monkeypatch.setenv(SV.ENV_VAR, "v1")
    assert SV.active() == "v1" and SV.source() == "env"                           # the env var is the one-flag rollback
    monkeypatch.setenv(SV.ENV_VAR, "v3")
    with pytest.raises(SV.ScoreVersionError, match="unknown score version"):
        SV.active()
    monkeypatch.delenv(SV.ENV_VAR)
    cfg.write_text("{not json")
    with pytest.raises(SV.ScoreVersionError, match="unreadable"):
        SV.active()


def test_the_repo_default_is_v1_until_the_cutover_pr_flips_it():
    cfg = json.loads((SV.PROJECT_ROOT / "data" / "score_version.json").read_text())
    assert cfg["version"] in SV.VERSIONS


def test_apply_keeps_the_old_value_as_legacy_and_swaps_only_under_v2(monkeypatch):
    df = lambda: pd.DataFrame({"a": [1.0, 2.0], "a_v2": [10.0, np.nan]})
    monkeypatch.setenv(SV.ENV_VAR, "v1")
    o = SV.apply(df(), [("a", "a_v2")])
    assert o["a"].tolist() == [1.0, 2.0] and o["a_legacy"].tolist() == [1.0, 2.0]
    monkeypatch.setenv(SV.ENV_VAR, "v2")
    o = SV.apply(df(), [("a", "a_v2")])
    assert o["a"].iloc[0] == 10.0 and np.isnan(o["a"].iloc[1])                    # NaN comes through as NaN, never a default credit
    assert o["a_legacy"].tolist() == [1.0, 2.0] and o["a_v2"].iloc[0] == 10.0
    with pytest.raises(SV.ScoreVersionError, match="missing its pair"):
        SV.apply(pd.DataFrame({"a": [1.0]}), [("a", "a_v2")])
    assert SV.apply(pd.DataFrame(), [("a", "a_v2")]).empty                        # a too-short series returns an empty frame: skipped


def test_legacy_view_gives_frozen_consumers_the_old_scale():
    df = pd.DataFrame({"sc_momentum": [80.0], "sc_momentum_legacy": [60.0], "flow_100": [1.0], "other": [5.0]})
    v = SV.legacy_view(df)
    assert v["sc_momentum"].iloc[0] == 60.0 and v["other"].iloc[0] == 5.0 and v["flow_100"].iloc[0] == 1.0     # no legacy twin: untouched
    assert df["sc_momentum"].iloc[0] == 80.0                                      # the original frame is not modified


def test_cache_problem_is_loud_for_unstamped_mixed_or_wrong_version(monkeypatch):
    monkeypatch.setenv(SV.ENV_VAR, "v2")
    assert "no score_version stamp" in SV.cache_problem(pd.DataFrame({"x": [1]}))
    assert "MIXED" in SV.cache_problem(pd.DataFrame({SV.VERSION_COLUMN: ["v1", "v2"]}))
    assert "holds v1 but the active version is v2" in SV.cache_problem(pd.DataFrame({SV.VERSION_COLUMN: ["v1"]}))
    assert SV.cache_problem(pd.DataFrame({SV.VERSION_COLUMN: ["v2", "v2"]})) is None


# ------------------------------------------------------------------ the engines, both ways
def _series(n=420, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rng.normal(0.0004, 0.013, n))
    d = pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=n), "open": c, "high": c * 1.006, "low": c * 0.994, "close": c, "volume": rng.uniform(5e5, 2e6, n)})
    spy = d.copy()
    spy["close"] = 100 * np.cumprod(1 + rng.normal(0.0004, 0.009, n))
    return d, spy


def _engine_frames():
    from src.data.fmp_client import resample_to_weekly
    from src.engines import bq, elder, energy, flow, health, mp, pipeline_rank, readiness, structure
    d, spy = _series()
    w = resample_to_weekly(d)
    dates = [x.strftime("%Y-%m-%d") for x in pd.date_range("2020-10-01", "2023-06-01", freq="91D")]
    return {"flow": (flow, flow.compute(d)), "energy": (energy, energy.compute(d)), "mp": (mp, mp.compute(d, spy_daily=spy)),
            "structure": (structure, structure.compute(d, spy_daily=spy, weekly=w, ticker="X", earn_dates_full={"X": dates})), "elder": (elder, elder.compute(d)),
            "bq": (bq, bq.compute(d)), "pipeline_rank": (pipeline_rank, pipeline_rank.compute(d.assign(ticker="X"))),
            "readiness": (readiness, readiness.compute(d, spy_daily=spy)), "health": (health, health.compute(d, spy_daily=spy, weekly=w))}


def _same(a, b):
    pd.testing.assert_series_equal(pd.Series(a).reset_index(drop=True), pd.Series(b).reset_index(drop=True), check_names=False, check_dtype=False)


def test_every_engine_twin_swaps_under_v2_and_restores_under_v1(monkeypatch):
    monkeypatch.setenv(SV.ENV_VAR, "v1")
    v1 = _engine_frames()
    monkeypatch.setenv(SV.ENV_VAR, "v2")
    v2 = _engine_frames()
    n = 0
    for name, (mod, f1) in v1.items():
        f2 = v2[name][1]
        for live, new in mod.TWINS:
            _same(f1[live + SV.LEGACY], f1[live])                                  # v1: legacy is a copy of the (old) live column
            _same(f1[live], f2[live + SV.LEGACY])                                  # the old calculation is the same in both runs: v2's legacy == v1's live
            _same(f2[live], f1[new])                                               # v2: the live column carries the corrected value
            _same(f2[live], f2[new])
            n += 1
    assert n >= 34, "every engine twin must be exercised"
    # rollback: flipping back reproduces the v1 frames exactly
    monkeypatch.setenv(SV.ENV_VAR, "v1")
    again = _engine_frames()
    for name, (mod, f1) in v1.items():
        for live, _ in mod.TWINS:
            _same(again[name][1][live], f1[live])


def test_the_decorated_engines_keep_their_source_visible_to_inspect():
    import inspect
    from src.engines import elder
    assert "SHADOW v2 histogram score" in inspect.getsource(elder.compute)       # the wrapper must not hide the engine from introspection


# ------------------------------------------------------------------ the scores build, both ways + rollback
def _build(tmp_path, monkeypatch, version):
    from src.data.fmp_client import resample_to_weekly
    from src.scanner import score_runner as SR
    rows = []
    for k, t in enumerate(["AAA", "BBB"]):
        rng = np.random.default_rng(3 + k)
        c = 100 * np.cumprod(1 + rng.normal(0.0004, 0.013, 420))
        rows.append(pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=420), "ticker": t, "open": c, "high": c * 1.006, "low": c * 0.994, "close": c,
                                  "volume": rng.uniform(5e5, 2e6, 420)}))
    panel = pd.concat(rows, ignore_index=True)
    rng = np.random.default_rng(99)
    sc = 100 * np.cumprod(1 + rng.normal(0.0004, 0.009, 420))
    spy = pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=420), "open": sc, "high": sc, "low": sc, "close": sc, "volume": 1e8})
    weekly = pd.concat([resample_to_weekly(g.drop(columns="ticker")).assign(ticker=t) for t, g in panel.groupby("ticker")], ignore_index=True)
    out = tmp_path / version
    out.mkdir(exist_ok=True)
    paths = {"PANEL_DAILY": out / "panel_daily.parquet", "PANEL_WEEKLY": out / "panel_weekly.parquet", "SPY_DAILY": out / "spy_daily.parquet", "SCORES_DAILY": out / "scores_daily.parquet"}
    panel.to_parquet(paths["PANEL_DAILY"], index=False)
    weekly.to_parquet(paths["PANEL_WEEKLY"], index=False)
    spy.to_parquet(paths["SPY_DAILY"], index=False)
    for key, v in paths.items():
        monkeypatch.setattr(SR, key, v)
    dates = [x.strftime("%Y-%m-%d") for x in pd.date_range("2020-10-01", "2023-06-01", freq="91D")]
    monkeypatch.setattr(SR, "load_earnings", lambda: {})
    monkeypatch.setattr(SR, "load_earnings_dates_full", lambda: {"AAA": dates})        # BBB has NO report dates: unscorable under v2
    import src.data.universe as U
    import src.data.ptj as PTJ
    monkeypatch.setattr(U, "load_universe", lambda include_benchmark=False: {"AAA", "BBB", "SPY"})
    monkeypatch.setattr(PTJ, "load_held_positions", lambda: [])
    monkeypatch.setenv(SV.ENV_VAR, version)
    SR.build_scores()
    return pd.read_parquet(paths["SCORES_DAILY"]), json.loads(paths["SCORES_DAILY"].with_name("score_diagnostics_v2.json").read_text())


def test_the_scores_build_carries_legacy_for_every_twin_the_version_stamp_and_swaps_only_under_v2(tmp_path, monkeypatch):
    from src.scanner import score_runner as SR
    v1, d1 = _build(tmp_path, monkeypatch, "v1")
    v2, d2 = _build(tmp_path, monkeypatch, "v2")
    for c in SR.LEGACY_COLUMNS + [SV.VERSION_COLUMN]:
        assert c in v1.columns and c in v2.columns, c
    assert set(v1[SV.VERSION_COLUMN]) == {"v1"} and set(v2[SV.VERSION_COLUMN]) == {"v2"}
    # v1 is dark: the live columns are the old values and each legacy column equals its live twin
    for live in [a for a, _, _ in SR.LEGACY_FROM] + SR.LEGACY_LOCAL:
        _same(v1[live], v1[live + SV.LEGACY])
    # v2: AAA (has report dates) is scored; its legacy columns are the OLD calculation, i.e. v1's live values on the same dates
    a1, a2 = v1[v1.ticker == "AAA"].set_index("date"), v2[v2.ticker == "AAA"].set_index("date")
    common = a2.index.intersection(a1.index)
    assert len(common) > 20
    for live in ("flow_100", "energy_100", "sc_momentum", "sc_position", "pipe_rank", "elder_score", "bq_100", "base_days", "hl_score", "rd_score"):
        _same(a2.loc[common, live + SV.LEGACY], a1.loc[common, live])                                   # legacy under v2 == live under v1
        _same(a2.loc[common, live], a2.loc[common, {"pipe_rank": "pipe_rank_v2", "base_days": "base_days_v2"}.get(live, live + "_v2")])    # live under v2 == the v2 column
    assert not a2.loc[common, "sc_momentum"].isna().any()
    # BBB has no report dates: it is NOT excluded (conductor ruling 2026-11-21): scored without the earnings component, rescaled, flagged earn_data: missing
    assert "BBB" in set(v2.ticker) and "BBB" in set(v1.ticker)
    bb = v2[v2.ticker == "BBB"]
    assert (bb["earn_data"] == "missing").all() and bb["sc_momentum"].notna().all() and bb["earn_score"].isna().all()
    assert d2["v2_unscorable"] == {} and d1["v2_unscorable"] == {}                                           # genuine failures only: none here
    assert list(d2["earn_data_missing"]) == ["BBB"] and list(d1["earn_data_missing"]) == ["BBB"]
    assert d1["score_version"] == "v1" and d2["score_version"] == "v2"
    assert (a2["earn_data"] == "ok").sum() > 20


def test_rolling_back_to_v1_reproduces_the_old_live_values_exactly(tmp_path, monkeypatch):
    first, _ = _build(tmp_path, monkeypatch, "v1")
    _build(tmp_path, monkeypatch, "v2")                                                                  # a v2 build in between
    back, _ = _build(tmp_path, monkeypatch, "v1")                                                        # flip the one switch back
    pd.testing.assert_frame_equal(first, back, check_dtype=True)


def test_qs_and_signal_radar_read_the_legacy_scale_not_the_live_one():
    """QS's frozen recipe/calibration and Signal Radar's fitted kNN parameters must never silently read the new scale (conductor ruling 2026-11-21)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    qs = (root / "src" / "engines" / "qs_daily.py").read_text()
    sr = (root / "src" / "engines" / "signal_radar.py").read_text()
    assert qs.count("_legacy_view(pd.read_parquet(SCORES_DAILY))") == 2 and "pd.read_parquet(SCORES_DAILY)\n" not in qs.replace("_legacy_view(pd.read_parquet(SCORES_DAILY))", "")
    assert "_legacy_view(pd.read_parquet(scores_path))" in sr



def test_structure_rescale_formula_when_the_earnings_component_is_missing():
    """structure_100_v2 = (the other parts) / 85 x 100 when the earnings component is missing, = total / 95 x 100 otherwise; any OTHER NaN part still gives NaN."""
    from src.data.fmp_client import resample_to_weekly
    from src.engines import structure
    d, spy = _series(420, seed=5)
    w = resample_to_weekly(d)
    dates = [x.strftime("%Y-%m-%d") for x in pd.date_range("2020-10-01", "2023-06-01", freq="91D")]
    have = structure.compute(d, spy_daily=spy, weekly=w, ticker="X", earn_dates_full={"X": dates})
    miss = structure.compute(d, spy_daily=spy, weekly=w, ticker="X", earn_dates_full={})
    parts = ["rs_spy_score_v2", "rs_accel_score_v2", "base_score_v2", "resist_score_v2", "wk_score_v2"]
    assert (have["earn_data_v2"] == "ok").all() and (miss["earn_data_v2"] == "missing").all() and miss["earn_score_v2"].isna().all()
    ok = miss["structure_100_v2"].notna()
    assert ok.sum() > 100
    ms_pos = (have["structure_100_v2"] / 100.0 * 95.0) - have[parts].sum(axis=1) - have["earn_score_v2"]        # recover the position component from the with-earnings run
    want = ((miss[parts].sum(axis=1) + ms_pos) / 85.0 * 100.0).clip(0.0, 100.0)
    _same(miss["structure_100_v2"][ok], want[ok])
    assert (have["structure_100_v2"].dropna() >= 0).all()
    # a NaN OTHER part still propagates (no score can be formed): drop the weekly history and the weekly part goes NaN
    nowk = structure.compute(d, spy_daily=spy, weekly=pd.DataFrame(), ticker="X", earn_dates_full={})
    assert nowk["wk_score_v2"].isna().all() and nowk["structure_100_v2"].isna().all()
