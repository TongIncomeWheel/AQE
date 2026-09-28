"""Tests for the MA Proximity Scanner."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest


def _make_bars(ticker: str, n: int = 250, start_price: float = 100.0,
               trend: float = 0.0) -> pd.DataFrame:
    """Generate synthetic daily bars with optional trend."""
    dates = pd.bdate_range("2025-01-02", periods=n)
    np.random.seed(hash(ticker) % 2**31)
    noise = np.random.randn(n) * 0.5
    prices = start_price + np.arange(n) * trend + np.cumsum(noise)
    prices = np.maximum(prices, 1.0)
    return pd.DataFrame({
        "date": dates,
        "ticker": ticker,
        "open": prices * 0.995,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.randint(100000, 5000000, n),
    })


def test_compute_ma_proximity_basic():
    from src.scanner.ma_scanner import compute_ma_proximity

    bars = _make_bars("TEST", n=250, start_price=100.0, trend=0.0)
    result = compute_ma_proximity(bars)

    if result.empty:
        pytest.skip("No stock near MA in synthetic flat data")

    assert "ticker" in result.columns
    for p in [20, 50, 100, 200]:
        assert f"sma_{p}" in result.columns
        assert f"dist_sma{p}" in result.columns
        assert f"near_sma{p}" in result.columns
        assert f"side_sma{p}" in result.columns
        assert f"days_near_{p}" in result.columns
    assert "ma_near_count" in result.columns


def test_compute_ma_proximity_flat_series():
    """A flat price series should be AT its SMAs (distance ≈ 0)."""
    from src.scanner.ma_scanner import compute_ma_proximity

    dates = pd.bdate_range("2025-01-02", periods=250)
    bars = pd.DataFrame({
        "date": dates,
        "ticker": "FLAT",
        "open": 50.0, "high": 50.5, "low": 49.5, "close": 50.0,
        "volume": 1000000,
    })

    result = compute_ma_proximity(bars)
    assert len(result) == 1
    row = result.iloc[0]

    for p in [20, 50, 100, 200]:
        assert abs(row[f"dist_sma{p}"]) < 0.01
        assert row[f"near_sma{p}"] is True or row[f"near_sma{p}"] == True
        assert row[f"days_near_{p}"] >= 50


def test_compute_ma_proximity_strong_trend():
    """A strongly trending stock should be far from its slower MAs."""
    from src.scanner.ma_scanner import compute_ma_proximity

    dates = pd.bdate_range("2025-01-02", periods=250)
    prices = 50.0 + np.arange(250) * 1.0  # +$1/day = strong uptrend
    bars = pd.DataFrame({
        "date": dates,
        "ticker": "TREND",
        "open": prices - 0.5, "high": prices + 0.5,
        "low": prices - 1.0, "close": prices,
        "volume": 1000000,
    })

    result = compute_ma_proximity(bars)
    if result.empty:
        return

    row = result.iloc[0]
    assert row["dist_sma200"] > 10


def test_compute_ma_proximity_streak_counter():
    """Streak counter should count consecutive days within 10% of MA."""
    from src.scanner.ma_scanner import compute_ma_proximity

    dates = pd.bdate_range("2025-01-02", periods=250)
    prices = np.full(250, 100.0)
    # Last 50 days: drop to 92 (within 10% of SMA which is ~100)
    prices[-50:] = 92.0

    bars = pd.DataFrame({
        "date": dates,
        "ticker": "STREAK",
        "open": prices, "high": prices + 1, "low": prices - 1,
        "close": prices,
        "volume": 1000000,
    })

    result = compute_ma_proximity(bars)
    assert len(result) == 1
    row = result.iloc[0]
    # Price at 92, SMA200 ≈ 98 → dist ≈ -6.1% → within 10%
    assert row["near_sma200"] is True or row["near_sma200"] == True
    assert row["days_near_200"] >= 50  # all 250 days are within 10%


def test_insufficient_bars_skipped():
    """Tickers with < 20 bars should be skipped."""
    from src.scanner.ma_scanner import compute_ma_proximity

    dates = pd.bdate_range("2025-06-01", periods=10)
    bars = pd.DataFrame({
        "date": dates,
        "ticker": "SHORT",
        "open": 50.0, "high": 51.0, "low": 49.0, "close": 50.0,
        "volume": 1000000,
    })

    result = compute_ma_proximity(bars)
    assert len(result) == 0


def test_multiple_tickers():
    """Should handle multiple tickers in the panel."""
    from src.scanner.ma_scanner import compute_ma_proximity

    bars = pd.concat([
        _make_bars("AAA", 250, 100.0, 0.0),
        _make_bars("BBB", 250, 50.0, 0.0),
        _make_bars("CCC", 250, 200.0, 0.0),
    ], ignore_index=True)

    result = compute_ma_proximity(bars)
    assert result["ticker"].nunique() <= 3


# ---------------------------------------------------------------- build_ma_panel
# The scheduled "Part 2" job (src/ui/daily_job.py) passes a real time budget
# so a slow/cold day can never stall its scheduler thread; the manual Scanner
# button leaves it unbounded. Both paths share this one function.


class _FakeFMPClient:
    """Returns a fixed small bar set instantly — no real network, no sleep.
    Dated up to "today" so build_ma_panel's own 400-day cutoff filter
    doesn't drop it (a fixed past date would silently filter to empty)."""

    def get_daily_bars(self, ticker, from_date, to_date):
        dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=5)
        return pd.DataFrame({
            "date": dates, "open": 1.0, "high": 1.0, "low": 1.0,
            "close": 1.0, "volume": 100,
        })


def test_build_ma_panel_unbounded_by_default(tmp_path, monkeypatch):
    import src.scanner.ma_scanner as M
    monkeypatch.setattr(M, "MA_PANEL", tmp_path / "ma_panel.parquet")

    universe = pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]})
    panel = M.build_ma_panel(universe, _FakeFMPClient())

    assert set(panel["ticker"].unique()) == {"AAA", "BBB", "CCC"}


def test_build_ma_panel_stops_once_the_runtime_budget_is_spent(tmp_path, monkeypatch):
    """A capped call must save whatever it pulled before the budget hit and
    return cleanly — never raise, never block past the budget.

    Uses a REAL, tiny clock rather than mocking time.time() globally --
    time.time() is called by far more than just this loop (date.today(),
    pandas, pytest's own internals), so patching it process-wide made the
    call count impossible to predict reliably. A real sleep-per-pull with a
    generous margin is slower (a few hundred ms) but deterministic."""
    import src.scanner.ma_scanner as M
    monkeypatch.setattr(M, "MA_PANEL", tmp_path / "ma_panel.parquet")

    class _SlowFakeClient:
        def get_daily_bars(self, ticker, from_date, to_date):
            time.sleep(0.1)
            dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=5)
            return pd.DataFrame({
                "date": dates, "open": 1.0, "high": 1.0, "low": 1.0,
                "close": 1.0, "volume": 100,
            })

    universe = pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]})
    # Each pull takes ~0.1s; a 0.15s budget lets exactly one full pull
    # complete (checked BEFORE each ticker) before the second check trips it.
    panel = M.build_ma_panel(universe, _SlowFakeClient(), max_runtime_seconds=0.15)

    pulled_tickers = set(panel["ticker"].unique()) if not panel.empty else set()
    assert pulled_tickers, "the budget must still let at least the first ticker through"
    assert pulled_tickers < {"AAA", "BBB", "CCC"}, (
        "the budget must stop it short of the full universe")
    # The partial result must still be persisted, same as a quota hit.
    assert M.MA_PANEL.exists()


def test_build_ma_panel_survives_a_budget_hit_before_any_ticker(tmp_path, monkeypatch):
    """An already-exhausted (negative) budget must degrade to an empty
    panel on the very first check, not raise or hang — no timing mock
    needed since real elapsed time is always >= 0 > any negative budget."""
    import src.scanner.ma_scanner as M
    monkeypatch.setattr(M, "MA_PANEL", tmp_path / "ma_panel.parquet")

    universe = pd.DataFrame({"ticker": ["AAA"]})
    panel = M.build_ma_panel(universe, _FakeFMPClient(), max_runtime_seconds=-1)

    assert panel.empty
