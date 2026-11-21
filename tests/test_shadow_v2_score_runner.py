"""End-to-end: build_scores on a small synthetic panel carries every shadow v2 column, the live columns are unchanged, composites v2 are built only from v2 parts,
and the diagnostics side file is written. Nothing reads the _v2 columns."""
import json

import numpy as np
import pandas as pd
import pytest

from src.scanner import score_runner as SR
from src.data.fmp_client import resample_to_weekly


def _panel(tickers, n=420, seed=3):
    rows = []
    for k, t in enumerate(tickers):
        rng = np.random.default_rng(seed + k)
        close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.013, n))
        d = pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=n), "ticker": t, "open": close, "high": close * 1.006, "low": close * 0.994,
                          "close": close, "volume": rng.uniform(5e5, 2e6, n)})
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


@pytest.fixture()
def scored(tmp_path, monkeypatch):
    panel = _panel(["AAA", "BBB"])
    spy = _panel(["SPY"], seed=99).drop(columns="ticker")
    weekly = pd.concat([resample_to_weekly(g.drop(columns="ticker")).assign(ticker=t) for t, g in panel.groupby("ticker")], ignore_index=True)
    paths = {"PANEL_DAILY": tmp_path / "panel_daily.parquet", "PANEL_WEEKLY": tmp_path / "panel_weekly.parquet", "SPY_DAILY": tmp_path / "spy_daily.parquet",
             "SCORES_DAILY": tmp_path / "scores_daily.parquet"}
    panel.to_parquet(paths["PANEL_DAILY"], index=False)
    weekly.to_parquet(paths["PANEL_WEEKLY"], index=False)
    spy.to_parquet(paths["SPY_DAILY"], index=False)
    for k, v in paths.items():
        monkeypatch.setattr(SR, k, v)
    monkeypatch.setattr(SR, "load_earnings", lambda: {})
    monkeypatch.setattr(SR, "load_earnings_dates_full",
                        lambda: {"AAA": [x.strftime("%Y-%m-%d") for x in pd.date_range("2020-10-01", "2023-06-01", freq="91D")]})
    import src.data.universe as U
    import src.data.ptj as PTJ
    monkeypatch.setattr(U, "load_universe", lambda include_benchmark=False: {"AAA", "BBB", "SPY"})
    monkeypatch.setattr(PTJ, "load_held_positions", lambda: [])
    SR.build_scores()
    return pd.read_parquet(paths["SCORES_DAILY"]), paths["SCORES_DAILY"]


def test_every_score_column_is_written_including_the_shadow_block(scored):
    df, _ = scored
    assert list(df.columns) == SR.SCORE_COLUMNS
    for c in ("pipe_rank_v2", "bq_100_v2", "structure_100_v2", "elder_score_v2", "flow_100_v2", "energy_100_v2", "mp_score_v2", "sc_momentum_v2", "sc_position_v2",
              "rd_score_v2", "hl_score_v2", "k39_gate_v2"):
        assert c in df.columns and df[c].notna().any(), c


def test_composites_v2_are_built_only_from_v2_parts_and_nan_when_a_part_is_nan(scored):
    df, _ = scored
    from src.engines import scoring
    a = df[df["ticker"] == "AAA"].reset_index(drop=True)
    ok = a["sc_momentum_v2"].notna()
    assert ok.sum() > 20                                       # AAA has earnings dates, so structure_100_v2 exists
    want = scoring.compute(a["flow_100_v2"], a["energy_100_v2"], a["structure_100_v2"], a["mp_score_v2"], a["elder_score_v2"])
    assert np.allclose(a["sc_momentum_v2"][ok].to_numpy(), want[ok].to_numpy())
    b = df[df["ticker"] == "BBB"]
    assert b["earn_score_v2"].isna().all() and b["structure_100_v2"].isna().all() and b["sc_momentum_v2"].isna().all()    # no dates -> NaN, never points
    assert b["sc_momentum"].notna().any()                                                                              # the live composite is untouched


def test_the_diagnostics_file_counts_the_defaults_and_the_missing_dates(scored):
    _, p = scored
    diag = json.loads(p.with_name("score_diagnostics_v2.json").read_text())
    assert diag["tickers_scored"] == 2 and diag["scope"] == "full" and diag["tickers_without_earn_dates"] == 1
    assert diag["nan_v2_bars"]["earn_score_v2"] > 0 and "spy_misaligned_bars" in diag
