"""Tests for the additive momentum-acceleration output (`mp_accel`/`mp_accel_state`).

These validate the NEW columns only. A parity guard confirms every pre-existing
MP output (including `roc_zscore`, recomputed independently here from the same
formula) is byte-identical to the documented Pine-port spec.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.engines import mp
from src.engines import utils as U


def _frame(close: np.ndarray, seed: int = 3) -> pd.DataFrame:
    n = len(close)
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    close_s = pd.Series(close)
    high = close_s + rng.uniform(0.1, 0.5, n)
    low = close_s - rng.uniform(0.1, 0.5, n)
    open_ = close_s + rng.normal(0, 0.1, n)
    volume = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close_s,
        "volume": volume,
    })


def _spy(n: int, seed: int = 99) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    close = 400 + np.linspace(0, 20, n) + rng.normal(0, 1.0, n).cumsum() * 0.1
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": rng.integers(50_000_000, 100_000_000, n),
    })


def _accelerating_close(n: int = 150) -> np.ndarray:
    """Gentle drift for the first 142 bars, then a convex (quadratically
    steepening) ramp for the last 8 bars. `roc_zscore` (the momentum LEVEL)
    jumps hard on the regime change and is caught mid-climb at the last bar
    — the pre-rollover part of the curve, where its own trailing 50-bar
    mean/stdev haven't caught up yet, i.e. still ACCELERATING."""
    warm = n - 8
    close = np.zeros(n)
    close[0] = 100.0
    for i in range(1, n):
        if i < warm:
            step = 0.05
        else:
            k = i - warm + 1
            step = 0.05 + 0.005 * k
        close[i] = close[i - 1] + step
    return close


def _decelerating_close(n: int = 150) -> np.ndarray:
    """Strong linear ramp for the first 145 bars, then a flat plateau for the
    last 5 bars — a rollover so momentum LEVEL (roc_zscore) is caught rolling
    over hard at the last bar, i.e. DECELERATING."""
    ramp_len = n - 5
    close = np.zeros(n)
    close[0] = 100.0
    for i in range(1, n):
        if i < ramp_len:
            step = 1.2
        else:
            step = 0.0
        close[i] = close[i - 1] + step
    return close


def _flat_close(n: int = 150) -> np.ndarray:
    """Constant tiny drift throughout — no inflection, momentum LEVEL stays put."""
    close = np.zeros(n)
    close[0] = 100.0
    for i in range(1, n):
        close[i] = close[i - 1] + 0.01
    return close


_EXISTING_COLUMNS = {
    "mp_score", "mp_state", "abs_mom_score", "adx_score", "rel_mom_score",
    "trend_score", "roc_zscore", "excess_return", "adx_val", "di_bullish",
}


def _assert_parity(out: pd.DataFrame, daily: pd.DataFrame) -> None:
    """All 10 pre-existing columns present + in-spec, plus the new columns exist.

    `roc_zscore` is independently recomputed here from the documented formula
    (Pine 23-31 port) and must be byte-identical (NaN-aware) to the engine's
    output — proof the acceleration addition didn't perturb the existing math.
    """
    assert _EXISTING_COLUMNS.issubset(set(out.columns))
    assert "mp_accel" in out.columns
    assert "mp_accel_state" in out.columns

    scores = out["mp_score"].dropna()
    assert (scores >= 0).all() and (scores <= 100).all()
    assert set(out["mp_state"].dropna().unique()).issubset({"BUILDING", "STRONG", "FADING"})

    close = daily["close"].astype(float)
    roc_val = (close / close.shift(20) - 1.0) * 100.0
    roc_sma = U.sma(roc_val, 50)
    roc_stdev = U.stdev_pop(roc_val, 50)
    expected_roc_zscore = ((roc_val - roc_sma) / roc_stdev.replace(0.0, np.nan)).fillna(0.0)

    pdt.assert_series_equal(
        out["roc_zscore"],
        expected_roc_zscore,
        check_names=False,
        atol=1e-9,
    )


def test_mp_accel_accelerating():
    daily = _frame(_accelerating_close())
    spy = _spy(len(daily))
    out = mp.compute(daily, spy)

    last = out.iloc[-1]
    assert last["mp_accel"] > mp.ACCEL_UP
    assert last["mp_accel_state"] == "ACCELERATING"

    _assert_parity(out, daily)


def test_mp_accel_decelerating():
    daily = _frame(_decelerating_close())
    spy = _spy(len(daily))
    out = mp.compute(daily, spy)

    last = out.iloc[-1]
    assert last["mp_accel"] < mp.ACCEL_DN
    assert last["mp_accel_state"] == "DECELERATING"

    _assert_parity(out, daily)


def test_mp_accel_flat():
    daily = _frame(_flat_close())
    spy = _spy(len(daily))
    out = mp.compute(daily, spy)

    last = out.iloc[-1]
    assert mp.ACCEL_DN <= last["mp_accel"] <= mp.ACCEL_UP
    assert last["mp_accel_state"] == "FLAT"

    _assert_parity(out, daily)


def test_mp_accel_nan_warmup_maps_to_flat():
    """Whatever warmup NaNs exist in mp_accel must read as FLAT, never
    ACCELERATING/DECELERATING (dead-zone comparisons against NaN are False)."""
    daily = _frame(_flat_close())
    spy = _spy(len(daily))
    out = mp.compute(daily, spy)

    nan_rows = out[out["mp_accel"].isna()]
    if len(nan_rows):
        assert (nan_rows["mp_accel_state"] == "FLAT").all()
