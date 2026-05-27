"""Momentum Persistence v1.2 — port of `sources/Momentum_Persistence_v1_2.pine`.

Outputs:
    mp_score        ∈ [0, 100]
    mp_state        ∈ {"BUILDING", "STRONG", "FADING"}
    abs_mom_score, adx_score, rel_mom_score, trend_score
    roc_zscore, excess_return, adx_val, di_bullish (diagnostics)

Composite (Pine line 69-70):
    mp_raw = abs_mom + adx + rel_mom + trend
    mp_score = clip(mp_raw, 0, 100)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(
    daily: pd.DataFrame,
    spy_daily: pd.DataFrame,
    *,
    roc_period: int = 20,
    adx_period: int = 14,
    trend_ma: int = 50,
) -> pd.DataFrame:
    """`daily` and `spy_daily` are both single-ticker frames with [date,open,high,low,close,volume]."""
    d = daily.reset_index(drop=True).copy()
    close = d["close"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)

    # ---- Component 1: Absolute Momentum (Pine 23-31) ----
    roc_val = (close / close.shift(roc_period) - 1.0) * 100.0
    roc_sma = U.sma(roc_val, 50)
    roc_stdev = U.stdev_pop(roc_val, 50)
    roc_zscore = ((roc_val - roc_sma) / roc_stdev.replace(0.0, np.nan)).fillna(0.0)

    abs_mom_score = _step_score(
        roc_zscore,
        [(2.0, 30.0), (1.5, 26.0), (1.0, 22.0), (0.5, 16.0), (0.0, 10.0), (-0.5, 5.0)],
        default=0.0,
    )

    # ---- Component 2: ADX (Pine 37-42) ----
    di_plus, di_minus, adx_val = _dmi(high, low, close, n=adx_period)
    di_bullish = di_plus > di_minus

    adx_score = pd.Series(0.0, index=close.index)
    adx_score = adx_score.where(~((adx_val >= 20) & di_bullish), 12.0)
    adx_score = adx_score.where(~((adx_val >= 25) & di_bullish), 18.0)
    adx_score = adx_score.where(~((adx_val >= 30) & di_bullish), 22.0)
    adx_score = adx_score.where(~((adx_val >= 40) & di_bullish), 25.0)

    # ---- Component 3: Relative Momentum vs SPY (Pine 46-53) ----
    spy_close_aligned = _align_to_dates(spy_daily, d["date"])
    bench_roc = (spy_close_aligned / spy_close_aligned.shift(roc_period) - 1.0) * 100.0
    stock_roc = roc_val  # same formula as Pine line 47
    excess_return = (stock_roc - bench_roc).fillna(0.0)

    rel_mom_score = _step_score(
        excess_return,
        [(15.0, 25.0), (10.0, 22.0), (5.0, 18.0), (2.0, 13.0), (0.0, 8.0), (-3.0, 3.0)],
        default=0.0,
    )

    # ---- Component 4: Trend Structure (Pine 58-66) ----
    ma_50 = U.sma(close, trend_ma)
    ma_20 = U.ema(close, 20)
    ma_50_rising = ma_50 > ma_50.shift(5)
    ma_20_rising = ma_20 > ma_20.shift(3)
    price_above_50 = close > ma_50
    price_above_20 = close > ma_20

    trend_score = pd.Series(0.0, index=close.index)
    cond_above_20_only = price_above_20 & ~price_above_50
    trend_score = trend_score.where(~cond_above_20_only, 5.0)
    cond_above_50 = price_above_50 & ~ma_50_rising
    trend_score = trend_score.where(~cond_above_50, 8.0)
    cond_50_rising = price_above_50 & ma_50_rising & ~price_above_20
    trend_score = trend_score.where(~cond_50_rising, 12.0)
    cond_stacked_basic = price_above_20 & price_above_50 & ma_50_rising & ~ma_20_rising
    trend_score = trend_score.where(~cond_stacked_basic, 16.0)
    cond_stacked_full = price_above_20 & price_above_50 & ma_20_rising & ma_50_rising
    trend_score = trend_score.where(~cond_stacked_full, 20.0)

    # ---- Composite (Pine 69-70) ----
    mp_raw = abs_mom_score + adx_score + rel_mom_score + trend_score
    mp_score = mp_raw.clip(lower=0.0, upper=100.0)
    # Warmup mask: 50-bar SMA of 20-bar ROC needs 70 bars; SMA(50) for trend needs 50.
    warm = roc_sma.notna() & ma_50.notna() & adx_val.notna()
    mp_score = mp_score.where(warm, np.nan)

    # ---- State (Pine 75-76) ----
    mp_rising = mp_score > mp_score.shift(3)
    mp_state = pd.Series("FADING", index=close.index, dtype="object")
    mp_state = mp_state.where(~(mp_rising & (mp_score < 75.0)), "BUILDING")
    mp_state = mp_state.where(~(mp_rising & (mp_score >= 75.0)), "STRONG")

    return pd.DataFrame({
        "date": d["date"],
        "mp_score": mp_score,
        "mp_state": mp_state,
        "abs_mom_score": abs_mom_score,
        "adx_score": adx_score,
        "rel_mom_score": rel_mom_score,
        "trend_score": trend_score,
        "roc_zscore": roc_zscore,
        "excess_return": excess_return,
        "adx_val": adx_val,
        "di_bullish": di_bullish,
    })


# ---------- helpers ----------


def _dmi(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Pine `ta.dmi(diLen, adxLen)` with diLen == adxLen.

    DI+/DI- use Wilder smoothing on +DM/-DM and TR. ADX is Wilder RMA of |DI+ − DI-|/(DI+ + DI-)*100.
    """
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm_raw = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move.clip(lower=0.0)
    minus_dm_raw = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move.clip(lower=0.0)
    tr = U.true_range(high, low, close)

    tr_n = U.wilder_rma(tr, n)
    plus_dm_n = U.wilder_rma(plus_dm_raw, n)
    minus_dm_n = U.wilder_rma(minus_dm_raw, n)

    di_plus = 100.0 * plus_dm_n / tr_n.replace(0.0, np.nan)
    di_minus = 100.0 * minus_dm_n / tr_n.replace(0.0, np.nan)
    dx = 100.0 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0.0, np.nan)
    adx_val = U.wilder_rma(dx.fillna(0.0), n)
    return di_plus.fillna(0.0), di_minus.fillna(0.0), adx_val.fillna(0.0)


def _step_score(x: pd.Series, thresholds: list[tuple[float, float]], default: float) -> pd.Series:
    """Pine-style descending ternary: apply highest-threshold-wins logic.

    thresholds = [(threshold, score), ...] in descending threshold order.
    Each bar gets the score of the first threshold it meets (x >= threshold);
    bars meeting none get `default`.
    """
    out = pd.Series(default, index=x.index, dtype=float)
    # Iterate ascending so higher thresholds overwrite lower ones.
    for thr, score in sorted(thresholds, key=lambda t: t[0]):
        out = out.where(~(x >= thr), score)
    return out


def _align_to_dates(other: pd.DataFrame, dates: pd.Series) -> pd.Series:
    """Left-join `other['close']` onto `dates` so the two series line up bar-for-bar."""
    if other.empty:
        return pd.Series(np.nan, index=dates.index, dtype=float)
    o = other[["date", "close"]].copy()
    o["date"] = pd.to_datetime(o["date"]).dt.normalize()
    o = o.drop_duplicates("date", keep="last")  # defensive against corrupted parquets
    lookup = o.set_index("date")["close"].astype(float)
    aligned = pd.to_datetime(dates).dt.normalize().map(lookup)
    aligned.index = dates.index
    return aligned.astype(float)
