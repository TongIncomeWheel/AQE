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


# pull_tickers() — the low-blast-radius held-book-only price refresh
# (src/pipeline/refresh_held.py), built after the 2026-08-21 incident where a
# full ~800-ticker pull died mid-way on a transient FMP connection drop and
# took the held-book refresh down with it. Merges into the existing panel by
# (date, ticker) rather than replacing it.

def test_pull_tickers_pulls_only_the_given_tickers_and_leaves_others_untouched(_wired):
    # Seed an existing panel with a ticker NOT in the requested pull.
    existing = pd.DataFrame({
        "date": pd.bdate_range("2025-01-02", periods=5),
        "ticker": "MSFT", "open": 1.0, "high": 1.0, "low": 1.0,
        "close": 1.0, "volume": 1.0,
    })
    existing.to_parquet(panel_builder.PANEL_DAILY, index=False)

    result = panel_builder.pull_tickers(["IBM"], history_years=1)

    daily = pd.read_parquet(panel_builder.PANEL_DAILY)
    tickers = set(daily["ticker"].unique())
    assert tickers == {"MSFT", "IBM"}
    assert result["pulled"] == 1
    assert result["failed"] == []


def test_pull_tickers_incremental_pull_skips_an_already_current_ticker(_wired, monkeypatch):
    from datetime import date as _date
    monkeypatch.setattr(panel_builder, "_us_market_date", lambda: _date(2025, 1, 8))
    existing = pd.DataFrame({
        "date": pd.bdate_range("2025-01-02", periods=5),  # through 2025-01-08
        "ticker": "IBM", "open": 1.0, "high": 1.0, "low": 1.0,
        "close": 1.0, "volume": 1.0,
    })
    existing.to_parquet(panel_builder.PANEL_DAILY, index=False)

    result = panel_builder.pull_tickers(["IBM"], history_years=1)
    assert result["pulled"] == 0
    assert result["skipped_current"] == 1


def test_pull_tickers_a_failed_ticker_is_reported_not_raised(_wired, monkeypatch):
    class _FlakyClient:
        def get_daily_bars(self, ticker, from_date=None, to_date=None):
            from src.data.fmp_client import FMPError
            raise FMPError("boom")
    monkeypatch.setattr(panel_builder, "FMPClient", _FlakyClient)

    result = panel_builder.pull_tickers(["ZZZZ"], history_years=1)  # must not raise
    assert result["pulled"] == 0
    assert result["failed"] == ["ZZZZ"]


def test_pull_tickers_dedups_overlapping_dates_keeping_the_new_pull(_wired):
    """A re-pull of an already-cached range must replace, not duplicate, the
    overlapping rows — same discipline as build_panel()."""
    existing = pd.DataFrame({
        "date": pd.bdate_range("2025-01-02", periods=5),
        "ticker": "IBM", "open": 999.0, "high": 999.0, "low": 999.0,
        "close": 999.0, "volume": 999.0,
    })
    existing.to_parquet(panel_builder.PANEL_DAILY, index=False)

    panel_builder.pull_tickers(["IBM"], history_years=1)

    daily = pd.read_parquet(panel_builder.PANEL_DAILY)
    ibm = daily[daily["ticker"] == "IBM"]
    assert len(ibm) == len(ibm.drop_duplicates(subset=["date"]))
    assert (ibm["close"] != 999.0).all(), "the fresh pull must win over stale cached rows"
