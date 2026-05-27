"""Smoke tests: each engine produces a sane output shape on synthetic bars.

These don't validate Pine-exact values (that's a manual eyeball job on
TradingView). They DO validate:

  - Output frame has the expected columns and length.
  - All scores are within their documented range (0-100 for engines, 0-10 for
    Elder).
  - No NaN floods after the warmup region.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import bq, elder, energy, flow, mp, pipeline_rank, scoring, structure


def _synth(n: int = 500, seed: int = 7) -> pd.DataFrame:
    """Build a synthetic OHLCV frame: slow drift + noise + occasional spikes."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    trend = np.linspace(100, 180, n)
    noise = rng.normal(0, 1.5, n).cumsum() * 0.3
    close = trend + noise
    high = close + rng.uniform(0.2, 1.5, n)
    low = close - rng.uniform(0.2, 1.5, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.integers(1_000_000, 5_000_000, n)
    df = pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return df


def _spy(n: int = 500, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    close = 400 + np.linspace(0, 40, n) + rng.normal(0, 1.5, n).cumsum() * 0.2
    df = pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": rng.integers(50_000_000, 100_000_000, n),
    })
    return df


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


def test_elder_in_range():
    out = elder.compute(_synth())
    assert len(out) == 500
    vals = out["elder_score"].dropna()
    assert (vals >= 0).all() and (vals <= 10).all()


def test_mp_in_range():
    daily = _synth()
    out = mp.compute(daily, _spy())
    vals = out["mp_score"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()
    assert set(out["mp_state"].dropna().unique()).issubset({"BUILDING", "STRONG", "FADING"})


def test_flow_in_range():
    out = flow.compute(_synth())
    vals = out["flow_100"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()


def test_energy_in_range():
    out = energy.compute(_synth())
    vals = out["energy_100"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()


def test_structure_in_range():
    daily = _synth()
    out = structure.compute(daily, _spy(), _weekly_from(daily))
    vals = out["structure_100"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()


def test_scoring_composite():
    daily = _synth()
    spy = _spy()
    weekly = _weekly_from(daily)
    f = flow.compute(daily)
    e = energy.compute(daily)
    s = structure.compute(daily, spy, weekly)
    m = mp.compute(daily, spy)
    el = elder.compute(daily)
    sc = scoring.compute(f["flow_100"], e["energy_100"], s["structure_100"], m["mp_score"], el["elder_score"])
    assert len(sc) == len(daily)
    vals = sc.dropna()
    assert (vals >= 0).all() and (vals <= 100).all()
    # After ~150 warmup bars, sc_momentum should be well-defined for most bars.
    late = sc.iloc[200:]
    assert late.notna().mean() > 0.9


def test_pipeline_rank_in_range():
    out = pipeline_rank.compute(_synth())
    vals = out["pipe_rank"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()
    assert set(out["pipe_tier"].dropna().unique()).issubset({"A-TIER", "B-STRONG", "C-WATCH", "D-SKIP"})
    # After 252-bar warmup, should have scores
    late = out["pipe_rank"].iloc[260:]
    assert late.notna().mean() > 0.8


def test_bq_in_range():
    out = bq.compute(_synth())
    vals = out["bq_100"].dropna()
    assert (vals >= 0).all() and (vals <= 100).all()
    assert len(out) == 500
    late = out["bq_100"].iloc[100:]
    assert late.notna().mean() > 0.8


def test_scoring_gate_enforcement():
    """If any engine floor fails, SC_MOMENTUM must be capped at 49.0."""
    n = 10
    # All engines at 80 → raw = 80, all gates pass → should be 80.
    high_all = pd.Series([80.0] * n)
    elder_high = pd.Series([8.0] * n)
    sc = scoring.compute(high_all, high_all, high_all, high_all, elder_high)
    assert (sc == 80.0).all()

    # Flow drops to 50 (below 60 floor) → cap at 49.
    flow_low = pd.Series([50.0] * n)
    sc_capped = scoring.compute(flow_low, high_all, high_all, high_all, elder_high)
    assert (sc_capped <= 49.0).all()

    # Elder drops to 5.0 (below 6.5 gate) → cap at 49.
    elder_low = pd.Series([5.0] * n)
    sc_elder = scoring.compute(high_all, high_all, high_all, high_all, elder_low)
    assert (sc_elder <= 49.0).all()

    # All engines below all floors — raw is low anyway, cap still applies.
    low_all = pd.Series([30.0] * n)
    elder_ok = pd.Series([7.0] * n)
    sc_low = scoring.compute(low_all, low_all, low_all, low_all, elder_ok)
    assert (sc_low <= 49.0).all()
    assert (sc_low == 30.0).all()  # raw=30 < 49, so min(30, 49) = 30
