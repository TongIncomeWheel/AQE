"""Tests for readiness engine — compression + trigger scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import readiness


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


class TestReadinessShape:
    def test_output_columns(self):
        df = readiness.compute(_synth())
        expected = [
            "date", "rd_score", "rd_state", "rd_compression",
            "rd_trigger", "rd_pos_mod", "rd_rs_bonus",
            "rd_inside_bars", "rd_range_exp", "rd_vol_surge", "rd_close_str",
        ]
        for col in expected:
            assert col in df.columns, f"Missing column: {col}"

    def test_output_length(self):
        bars = _synth(200)
        df = readiness.compute(bars)
        assert len(df) == len(bars)

    def test_score_range(self):
        df = readiness.compute(_synth())
        assert df["rd_score"].min() >= 0
        assert df["rd_score"].max() <= 100

    def test_compression_range(self):
        df = readiness.compute(_synth())
        assert df["rd_compression"].min() >= 0
        assert df["rd_compression"].max() <= 60

    def test_trigger_range(self):
        df = readiness.compute(_synth())
        assert df["rd_trigger"].min() >= 0
        assert df["rd_trigger"].max() <= 25

    def test_pos_mod_range(self):
        df = readiness.compute(_synth())
        assert df["rd_pos_mod"].min() >= -15
        assert df["rd_pos_mod"].max() <= 0

    def test_rs_bonus_range(self):
        df = readiness.compute(_synth(), _spy())
        assert df["rd_rs_bonus"].min() >= 0
        assert df["rd_rs_bonus"].max() <= 15


class TestReadinessStates:
    def test_valid_states(self):
        df = readiness.compute(_synth())
        valid = {"READY", "WATCH", "NEUTRAL", "NOT_READY"}
        assert set(df["rd_state"].unique()).issubset(valid)

    def test_state_thresholds(self):
        df = readiness.compute(_synth())
        for _, row in df.iterrows():
            s = row["rd_score"]
            st = row["rd_state"]
            if s >= 80:
                assert st == "READY"
            elif s >= 60:
                assert st == "WATCH"
            elif s >= 40:
                assert st == "NEUTRAL"
            else:
                assert st == "NOT_READY"


class TestReadinessNoSpy:
    def test_runs_without_spy(self):
        df = readiness.compute(_synth())
        assert len(df) > 0
        assert (df["rd_rs_bonus"] == 0.0).all()


class TestReadinessInsideBars:
    def test_inside_bar_detection(self):
        n = 20
        dates = pd.bdate_range("2024-01-02", periods=n)
        high = [100.0] * n
        low = [90.0] * n
        high[5] = 99.0
        low[5] = 91.0
        high[6] = 98.0
        low[6] = 91.5
        bars = pd.DataFrame({
            "date": dates,
            "open": [95.0] * n,
            "high": high,
            "low": low,
            "close": [95.0] * n,
            "volume": [1_000_000] * n,
        })
        df = readiness.compute(bars)
        assert df["rd_inside_bars"].iloc[5] >= 1
        assert df["rd_inside_bars"].iloc[6] >= 1
