"""Tests for health engine — trend integrity for held positions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import health


def _synth(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    trend = np.linspace(100, 180, n)
    noise = rng.normal(0, 1.5, n).cumsum() * 0.3
    close = trend + noise
    high = close + rng.uniform(0.2, 1.5, n)
    low = close - rng.uniform(0.2, 1.5, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({
        "date": dates, "open": open_, "high": high,
        "low": low, "close": close, "volume": volume,
    })


def _spy(n: int = 300, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    close = 400 + np.linspace(0, 40, n) + rng.normal(0, 1.5, n).cumsum() * 0.2
    return pd.DataFrame({
        "date": dates, "open": close, "high": close + 1,
        "low": close - 1, "close": close,
        "volume": rng.integers(50_000_000, 100_000_000, n),
    })


def _weekly_from(daily: pd.DataFrame) -> pd.DataFrame:
    idx = daily.set_index("date")
    w = pd.DataFrame({
        "open": idx["open"].resample("W-FRI").first(),
        "high": idx["high"].resample("W-FRI").max(),
        "low": idx["low"].resample("W-FRI").min(),
        "close": idx["close"].resample("W-FRI").last(),
        "volume": idx["volume"].resample("W-FRI").sum(),
    }).dropna(subset=["close"]).reset_index()
    return w


class TestHealthShape:
    def test_output_columns(self):
        df = health.compute(_synth())
        expected = [
            "date", "hl_score", "hl_state", "hl_trend",
            "hl_flow", "hl_rs", "hl_risk",
            "hl_higher_lows", "hl_trend_bars", "hl_vol_updn", "hl_atr_spike",
        ]
        for col in expected:
            assert col in df.columns, f"Missing column: {col}"

    def test_output_length(self):
        bars = _synth(200)
        df = health.compute(bars)
        assert len(df) == len(bars)

    def test_score_range(self):
        df = health.compute(_synth())
        assert df["hl_score"].min() >= 0
        assert df["hl_score"].max() <= 100

    def test_trend_range(self):
        df = health.compute(_synth())
        assert df["hl_trend"].min() >= 0
        assert df["hl_trend"].max() <= 35

    def test_flow_range(self):
        df = health.compute(_synth())
        assert df["hl_flow"].min() >= 0
        assert df["hl_flow"].max() <= 25

    def test_rs_range(self):
        df = health.compute(_synth(), _spy())
        assert df["hl_rs"].min() >= 0
        assert df["hl_rs"].max() <= 20

    def test_risk_range(self):
        df = health.compute(_synth())
        assert df["hl_risk"].min() >= -20
        assert df["hl_risk"].max() <= 0


class TestHealthStates:
    def test_valid_states(self):
        df = health.compute(_synth())
        valid = {"HOLD_ADD", "HOLD", "TIGHTEN", "EXIT"}
        assert set(df["hl_state"].unique()).issubset(valid)

    def test_state_thresholds(self):
        df = health.compute(_synth())
        for _, row in df.iterrows():
            s = row["hl_score"]
            st = row["hl_state"]
            if s >= 75:
                assert st == "HOLD_ADD"
            elif s >= 50:
                assert st == "HOLD"
            elif s >= 30:
                assert st == "TIGHTEN"
            else:
                assert st == "EXIT"


class TestHealthNoSpy:
    def test_runs_without_spy(self):
        df = health.compute(_synth())
        assert len(df) > 0
        assert (df["hl_rs"] == 0.0).all()


class TestHealthWithWeekly:
    def test_weekly_trend_contributes(self):
        bars = _synth(300, seed=42)
        weekly = _weekly_from(bars)
        df_no_wk = health.compute(bars)
        df_with_wk = health.compute(bars, weekly=weekly)
        assert len(df_with_wk) == len(bars)


class TestHealthHigherLows:
    def test_staircase_trend(self):
        n = 30
        dates = pd.bdate_range("2024-01-02", periods=n)
        lows = [100 + i * 0.5 for i in range(n)]
        highs = [l + 2.0 for l in lows]
        closes = [l + 1.0 for l in lows]
        bars = pd.DataFrame({
            "date": dates,
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000_000] * n,
        })
        df = health.compute(bars)
        assert df["hl_higher_lows"].iloc[-1] >= 5


class TestHealthAtrSpike:
    def test_volatile_bars_penalized(self):
        n = 50
        dates = pd.bdate_range("2024-01-02", periods=n)
        close = [100.0] * n
        high = [101.0] * n
        low = [99.0] * n
        for i in range(45, 50):
            high[i] = 105.0
            low[i] = 95.0
        bars = pd.DataFrame({
            "date": dates,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": [1_000_000] * n,
        })
        df = health.compute(bars)
        assert df["hl_atr_spike"].iloc[-1] > 1.0
