"""Tests for build_scores(only_tickers=...) — the targeted-refresh scoping
added 2026-08-21 for src/pipeline/refresh_held.py. Every per-ticker engine
call operates on that ticker's own price history plus spy_daily; nothing
compares tickers to each other. So scoring a subset and merging (upsert by
ticker) into the existing cache must be equivalent to a full rebuild for the
tickers actually requested, while leaving every other cached ticker's rows
byte-for-byte untouched — a bug here would silently corrupt the scores of
tickers the caller never asked to touch."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scanner import score_runner


def _bars(seed: int, n: int = 300, start: float = 100.0) -> pd.DataFrame:
    """A tame trending random walk — enough history (>252d) for every engine,
    including Pipeline Rank, to compute without degenerating on flat data."""
    rng = np.random.RandomState(seed)
    rets = rng.normal(0.0004, 0.014, n)
    close = start * np.cumprod(1 + rets)
    high = close * (1 + np.abs(rng.normal(0.004, 0.003, n)))
    low = close * (1 - np.abs(rng.normal(0.004, 0.003, n)))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    volume = rng.uniform(1e6, 3e6, n)
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": open_, "high": high,
                         "low": low, "close": close, "volume": volume})


@pytest.fixture
def _wired(tmp_path, monkeypatch):
    monkeypatch.setattr(score_runner, "PANEL_DAILY", tmp_path / "panel_daily.parquet")
    monkeypatch.setattr(score_runner, "PANEL_WEEKLY", tmp_path / "panel_weekly.parquet")
    monkeypatch.setattr(score_runner, "SPY_DAILY", tmp_path / "spy_daily.parquet")
    monkeypatch.setattr(score_runner, "SCORES_DAILY", tmp_path / "scores_daily.parquet")
    monkeypatch.setattr("src.data.universe.load_universe",
                        lambda include_benchmark=True: ["AAPL", "MSFT", "GOOG", "SPY"])
    monkeypatch.setattr("src.engines.srm.BASKET_CONSTITUENTS", set())
    monkeypatch.setattr("src.data.ptj.load_held_positions", lambda: [])
    monkeypatch.setattr("src.data.earnings.load_earnings", lambda: {})

    panel = pd.concat([
        _bars(1, start=100.0).assign(ticker="AAPL"),
        _bars(2, start=300.0).assign(ticker="MSFT"),
        _bars(3, start=150.0).assign(ticker="GOOG"),
        _bars(4, start=450.0).assign(ticker="SPY"),
    ], ignore_index=True)
    panel.to_parquet(score_runner.PANEL_DAILY, index=False)
    return tmp_path


def test_only_tickers_scores_just_the_requested_subset(_wired):
    score_runner.build_scores(only_tickers=["AAPL"])

    out = pd.read_parquet(score_runner.SCORES_DAILY)
    assert set(out["ticker"].unique()) == {"AAPL"}


def test_only_tickers_upserts_without_disturbing_other_cached_tickers(_wired):
    # A full run first, as if the last full pipeline had already scored everyone.
    score_runner.build_scores()
    full = pd.read_parquet(score_runner.SCORES_DAILY)
    assert set(full["ticker"].unique()) == {"AAPL", "MSFT", "GOOG", "SPY"}
    msft_before = full[full["ticker"] == "MSFT"].sort_values("date").reset_index(drop=True)
    goog_before = full[full["ticker"] == "GOOG"].sort_values("date").reset_index(drop=True)

    # Now a targeted re-score of AAPL only.
    score_runner.build_scores(only_tickers=["AAPL"])

    merged = pd.read_parquet(score_runner.SCORES_DAILY)
    assert set(merged["ticker"].unique()) == {"AAPL", "MSFT", "GOOG", "SPY"}

    msft_after = merged[merged["ticker"] == "MSFT"].sort_values("date").reset_index(drop=True)
    goog_after = merged[merged["ticker"] == "GOOG"].sort_values("date").reset_index(drop=True)
    pd.testing.assert_frame_equal(msft_before, msft_after)
    pd.testing.assert_frame_equal(goog_before, goog_after)


def test_a_ticker_not_previously_cached_can_be_added_by_a_targeted_run(_wired):
    score_runner.build_scores(only_tickers=["AAPL"])
    assert set(pd.read_parquet(score_runner.SCORES_DAILY)["ticker"].unique()) == {"AAPL"}

    score_runner.build_scores(only_tickers=["MSFT"])
    out = pd.read_parquet(score_runner.SCORES_DAILY)
    assert set(out["ticker"].unique()) == {"AAPL", "MSFT"}
