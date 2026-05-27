"""Unit tests for the Pine ↔ Python utility translations.

These cover the math that the engine ports rely on. Where Pine's exact behaviour
differs from a textbook formula (Wilder seed, MACD signal kind, population stdev),
we test the Pine-faithful version.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.engines import utils as U


def _series(vals):
    return pd.Series(vals, dtype=float)


# ----- Wilder RMA ---------------------------------------------------------


def test_wilder_rma_seed_is_sma_of_first_n():
    s = _series([2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
    out = U.wilder_rma(s, n=4)
    # Bars 0..2 are warmup.
    assert all(math.isnan(v) for v in out.iloc[:3])
    # Bar 3 (the n-th, 1-indexed = 4) is the SMA of [2,4,6,8] = 5.
    assert out.iloc[3] == pytest.approx(5.0)
    # Subsequent bars apply alpha = 1/4: new = (3*prev + x) / 4
    assert out.iloc[4] == pytest.approx((3 * 5.0 + 10) / 4)
    assert out.iloc[5] == pytest.approx((3 * out.iloc[4] + 12) / 4)


def test_wilder_rma_is_not_ema():
    s = _series(list(range(1, 21)))
    rma = U.wilder_rma(s, n=14)
    ema = U.ema(s, n=14)
    # They must differ on the seed bar.
    assert rma.iloc[13] != pytest.approx(ema.iloc[13])


# ----- population stdev --------------------------------------------------


def test_stdev_pop_uses_ddof_zero():
    s = _series([1, 2, 3, 4, 5])
    out = U.stdev_pop(s, n=5)
    # Population variance of 1..5 = 2.0 → std = sqrt(2)
    assert out.iloc[-1] == pytest.approx(math.sqrt(2.0))


# ----- ATR ---------------------------------------------------------------


def test_atr_matches_pine_handcalc():
    high = _series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25])
    low = _series([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
    close = _series([9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5])
    out = U.atr(high, low, close, n=14)
    # H-L = 1 every bar. |H - prev_close| = 1.5 every bar (gap up half). TR = max = 1.5.
    # First bar TR = H-L = 1.0 (no prev_close). Wilder seed = mean(TRs) of first 14 bars ≈ 1.464.
    # ATR converges toward 1.5 as alpha=1/14 weights in subsequent 1.5 TRs.
    assert 1.4 < out.iloc[-1] < 1.55


# ----- RSI ----------------------------------------------------------------


def test_rsi_extreme_uptrend_is_100():
    # Pure uptrend → avg_loss == 0 → RSI = 100.
    s = _series([float(i) for i in range(1, 40)])
    out = U.rsi(s, n=14)
    assert out.iloc[-1] == pytest.approx(100.0)


def test_rsi_pure_downtrend_is_zero():
    s = _series([float(40 - i) for i in range(40)])
    out = U.rsi(s, n=14)
    assert out.iloc[-1] == pytest.approx(0.0)


# ----- MACD ---------------------------------------------------------------


def test_macd_signal_default_is_ema():
    close = _series([100 + i * 0.5 + (i % 3) for i in range(80)])
    res_ema = U.macd(close, signal_kind="ema")
    res_sma = U.macd(close, signal_kind="sma")
    assert not np.allclose(res_ema.signal.iloc[-1], res_sma.signal.iloc[-1])
    # hist = macd - signal
    assert res_ema.hist.iloc[-1] == pytest.approx(res_ema.macd.iloc[-1] - res_ema.signal.iloc[-1])


# ----- linreg endpoint ----------------------------------------------------


def test_linreg_endpoint_on_straight_line():
    s = _series([3.0 + 2.0 * i for i in range(20)])
    out = U.linreg_endpoint(s, n=10)
    # Perfect line → endpoint is the actual value.
    for i in range(9, 20):
        assert out.iloc[i] == pytest.approx(s.iloc[i])


# ----- crossover ---------------------------------------------------------


def test_crossover_detects_only_the_crossing_bar():
    a = _series([1, 2, 3, 4, 5, 4, 3])
    b = _series([3, 3, 3, 3, 3, 3, 3])
    out = U.crossover(a, b)
    # a crosses up b between index 2 and 3.
    assert out.tolist() == [False, False, False, True, False, False, False]


# ----- Heikin Ashi --------------------------------------------------------


def test_heikin_ashi_recursion():
    o = _series([10, 11, 12, 13, 14])
    h = _series([11, 12, 13, 14, 15])
    l = _series([9, 10, 11, 12, 13])
    c = _series([10.5, 11.5, 12.5, 13.5, 14.5])
    res = U.heikin_ashi(o, h, l, c)
    # Pine seed: HA_open[0] = (O[0] + C[0]) / 2 = 10.25
    assert res.open.iloc[0] == pytest.approx(10.25)
    # HA_close = (O+H+L+C)/4
    assert res.close.iloc[0] == pytest.approx((10 + 11 + 9 + 10.5) / 4)
    # HA_open[1] = (HA_open[0] + HA_close[0]) / 2
    expected_open_1 = (res.open.iloc[0] + res.close.iloc[0]) / 2
    assert res.open.iloc[1] == pytest.approx(expected_open_1)


# ----- weekly asof --------------------------------------------------------


def test_asof_weekly_value_no_lookahead():
    weekly = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05", "2024-01-12", "2024-01-19"]),  # Fridays
        "wclose": [100.0, 102.0, 105.0],
    })
    daily_dates = pd.Series(pd.to_datetime([
        "2024-01-08",  # after Jan 5 Friday → should use 100
        "2024-01-12",  # ON Jan 12 Friday — must NOT use that bar (look-ahead)
        "2024-01-15",  # after Jan 12 Friday → 102
        "2024-01-19",  # ON Jan 19 — must use Jan 12 (102)
        "2024-01-22",  # after Jan 19 → 105
    ]))
    out = U.asof_weekly_value(daily_dates, weekly, "wclose")
    assert out.tolist() == [100.0, 100.0, 102.0, 102.0, 105.0]
