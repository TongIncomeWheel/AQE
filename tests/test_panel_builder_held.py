"""Regression test for the 2026-07-15 incident: held positions that have
dropped out of (or never were in) the curated universe must still get their
bars pulled into the panel, so the daily engine read (Health, DSL bracket,
subcomponents, conviction labels, ...) can be computed for them — "as long
as we have the ticker, we can source this" (PM ruling)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data import panel_builder


class _StubFMPClient:
    """Returns a tiny valid daily-bar frame for any ticker, no network."""

    def get_daily_bars(self, ticker, from_date=None, to_date=None):
        dates = pd.bdate_range("2025-01-02", periods=5)
        return pd.DataFrame({
            "date": dates,
            "open": [10.0] * 5, "high": [11.0] * 5,
            "low": [9.0] * 5, "close": [10.5] * 5,
            "volume": [1_000_000.0] * 5,
        })


@pytest.fixture
def _wired(tmp_path, monkeypatch):
    monkeypatch.setattr(panel_builder, "DATA_DIR", tmp_path)
    monkeypatch.setattr(panel_builder, "PANEL_DAILY", tmp_path / "panel_daily.parquet")
    monkeypatch.setattr(panel_builder, "PANEL_WEEKLY", tmp_path / "panel_weekly.parquet")
    monkeypatch.setattr(panel_builder, "SPY_DAILY", tmp_path / "spy_daily.parquet")
    monkeypatch.setattr(panel_builder, "load_universe", lambda include_benchmark=True: ["AAPL", "SPY"])
    monkeypatch.setattr(panel_builder, "FMPClient", _StubFMPClient)
    monkeypatch.setattr("src.engines.srm.GICS_ETFS", [])
    monkeypatch.setattr("src.engines.srm.BASKET_CONSTITUENTS", set())
    return tmp_path


def test_build_panel_always_pulls_held_tickers_outside_universe(_wired, monkeypatch):
    monkeypatch.setattr(
        "src.data.ptj.load_held_positions",
        lambda: [
            {"ticker": "ZZZZ", "type": "STK"},   # held, NOT in universe
            {"ticker": "AAPL", "type": "STK"},   # held, already in universe (dedup)
            {"ticker": "IBM_260C", "type": "OPT"},  # option leg — not a real equity ticker
        ],
    )

    panel_builder.build_panel(history_years=1)

    daily = pd.read_parquet(panel_builder.PANEL_DAILY)
    tickers = set(daily["ticker"].unique())
    assert "ZZZZ" in tickers, "held ticker outside the universe must still be pulled into the panel"
    assert "AAPL" in tickers
    assert "IBM_260C" not in tickers, "option/spread legs are not equity tickers FMP can bar-series price"


def test_build_panel_survives_ptj_failure(_wired, monkeypatch):
    def _boom():
        raise RuntimeError("Drive unreachable")
    monkeypatch.setattr("src.data.ptj.load_held_positions", _boom)

    panel_builder.build_panel(history_years=1)  # must not raise

    daily = pd.read_parquet(panel_builder.PANEL_DAILY)
    assert "AAPL" in set(daily["ticker"].unique())
