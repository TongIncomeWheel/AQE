"""Health Score — trend integrity for held positions.

Answers: "Should I stay in this position?"

Built from momentum-maintenance signals that differ from readiness
(compression). Here we want trend continuation, flow confirmation,
and early-warning risk flags.

Output:
    hl_score        ∈ [0, 100]  composite health
    hl_state        HOLD_ADD / HOLD / TIGHTEN / EXIT
    hl_trend        ∈ [0, 35]   trend structure sub-score
    hl_flow         ∈ [0, 25]   flow confirmation sub-score
    hl_rs           ∈ [0, 20]   relative strength sub-score
    hl_risk         ∈ [-20, 0]  risk-flag penalty
    hl_higher_lows  diagnostic: higher-low count (10-bar)
    hl_trend_bars   diagnostic: consecutive bars above EMA21
    hl_vol_updn     diagnostic: volume up/down ratio (10-bar)
    hl_atr_spike    diagnostic: ATR5/ATR14 ratio
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(
    daily: pd.DataFrame,
    spy_daily: pd.DataFrame | None = None,
    weekly: pd.DataFrame | None = None,
) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    ema21 = U.ema(close, 21)
    atr5 = U.atr(high, low, close, n=5)
    atr14 = U.atr(high, low, close, n=14)

    # ================================================================
    # A. TREND STRUCTURE (0-35 pts)
    # ================================================================

    # A1: Higher-low sequence (10-bar) — count of bars where low > prior low
    higher_low = (low > low.shift(1)).astype(float)
    hl_count_10 = higher_low.rolling(10, min_periods=1).sum()
    a1 = pd.Series(0.0, index=close.index)
    a1 = a1.where(~(hl_count_10 >= 3), 3.0)
    a1 = a1.where(~(hl_count_10 >= 4), 5.0)
    a1 = a1.where(~(hl_count_10 >= 5), 8.0)
    a1 = a1.where(~(hl_count_10 >= 6), 11.0)
    a1 = a1.where(~(hl_count_10 >= 7), 15.0)

    # A2: Consecutive bars above EMA(21)
    above_ema21 = (close > ema21).astype(float)
    trend_bars = pd.Series(0.0, index=close.index)
    arr = above_ema21.to_numpy()
    tb = np.zeros(n, dtype=float)
    for i in range(n):
        if arr[i] > 0:
            tb[i] = (tb[i - 1] + 1.0) if i > 0 else 1.0
        else:
            tb[i] = 0.0
    trend_bars = pd.Series(tb, index=close.index)

    a2 = pd.Series(0.0, index=close.index)
    a2 = a2.where(~(trend_bars >= 3), 3.0)
    a2 = a2.where(~(trend_bars >= 5), 5.0)
    a2 = a2.where(~(trend_bars >= 10), 8.0)
    a2 = a2.where(~(trend_bars >= 15), 11.0)
    a2 = a2.where(~(trend_bars >= 20), 15.0)

    # A3: Weekly trend — price above SMA(10) of weekly close (0-5)
    a3 = pd.Series(0.0, index=close.index)
    if weekly is not None and len(weekly) >= 10:
        wk = weekly.sort_values("date").reset_index(drop=True)
        wk_close = wk["close"].astype(float)
        wk_sma10 = U.sma(wk_close, 10)
        wk_above = (wk_close > wk_sma10).astype(float)
        wk_score = pd.Series(0.0, index=wk_close.index)
        wk_score = wk_score.where(~(wk_above > 0), 5.0)
        wk_vals = U.asof_weekly_value(
            d["date"],
            wk.assign(_wk_trend=wk_score),
            "_wk_trend",
        )
        a3 = wk_vals.fillna(0.0)

    trend = (a1 + a2 + a3).clip(upper=35.0)

    # ================================================================
    # B. FLOW CONFIRMATION (0-25 pts)
    # ================================================================

    # B1: MFI health — Money Flow Index (14-bar) above 50 = positive (0-15)
    mfi = _mfi(high, low, close, volume, 14)
    b1 = pd.Series(0.0, index=close.index)
    b1 = b1.where(~(mfi > 40), 3.0)
    b1 = b1.where(~(mfi > 50), 6.0)
    b1 = b1.where(~(mfi > 60), 10.0)
    b1 = b1.where(~(mfi > 70), 15.0)

    # B2: Volume up/down ratio (10-bar) — accumulation signal (0-10)
    up_day = (close > close.shift(1)).astype(float)
    dn_day = (close <= close.shift(1)).astype(float)
    vol_up = (volume * up_day).rolling(10, min_periods=1).sum()
    vol_dn = (volume * dn_day).rolling(10, min_periods=1).sum()
    vol_updn_ratio = (vol_up / vol_dn.replace(0.0, np.nan)).fillna(1.0)

    b2 = pd.Series(0.0, index=close.index)
    b2 = b2.where(~(vol_updn_ratio > 1.0), 3.0)
    b2 = b2.where(~(vol_updn_ratio > 1.2), 6.0)
    b2 = b2.where(~(vol_updn_ratio > 1.5), 10.0)

    flow_conf = (b1 + b2).clip(upper=25.0)

    # ================================================================
    # C. RELATIVE STRENGTH (0-20 pts)
    # ================================================================

    rs_score = pd.Series(0.0, index=close.index)
    if spy_daily is not None and len(spy_daily) > 60:
        spy = spy_daily.reset_index(drop=True)
        spy_close = spy["close"].astype(float)
        min_len = min(len(close), len(spy_close))
        if min_len > 60:
            sc = close.iloc[:min_len]
            spc = spy_close.iloc[:min_len]

            # C1: RS vs SPY maintenance — 20d outperformance (0-10)
            rs_20 = (sc / sc.shift(20) - 1) * 100 - (spc / spc.shift(20) - 1) * 100
            c1 = pd.Series(0.0, index=sc.index)
            c1 = c1.where(~(rs_20 > -2), 2.0)
            c1 = c1.where(~(rs_20 > 0), 5.0)
            c1 = c1.where(~(rs_20 > 3), 8.0)
            c1 = c1.where(~(rs_20 > 5), 10.0)

            # C2: RS not deteriorating — acceleration >= 0 (0-10)
            rs_60 = (sc / sc.shift(60) - 1) * 100 - (spc / spc.shift(60) - 1) * 100
            rs_accel = rs_20 - rs_60
            c2 = pd.Series(0.0, index=sc.index)
            c2 = c2.where(~(rs_accel > -2), 3.0)
            c2 = c2.where(~(rs_accel > 0), 6.0)
            c2 = c2.where(~(rs_accel > 3), 10.0)

            rs_sub = (c1 + c2).clip(upper=20.0)
            rs_score = rs_sub.reindex(close.index, fill_value=0.0)

    # ================================================================
    # D. RISK FLAGS (-20 to 0)
    # ================================================================

    # D1: ATR spike — ATR5/ATR14 volatility expansion (-10 to 0)
    atr_spike_ratio = (atr5 / atr14.replace(0.0, np.nan)).fillna(1.0)
    d1 = pd.Series(0.0, index=close.index)
    d1 = d1.where(~(atr_spike_ratio > 1.5), -5.0)
    d1 = d1.where(~(atr_spike_ratio > 2.0), -10.0)

    # D2: Close weakness — closing in bottom 30% of range on down day (-5 to 0)
    daily_range = high - low
    close_in_range = ((close - low) / daily_range.replace(0.0, np.nan)).fillna(0.5)
    down_day = close < close.shift(1)
    weak_close_count = (down_day & (close_in_range < 0.3)).astype(float).rolling(5, min_periods=1).sum()
    d2 = pd.Series(0.0, index=close.index)
    d2 = d2.where(~(weak_close_count >= 2), -3.0)
    d2 = d2.where(~(weak_close_count >= 3), -5.0)

    # D3: EMA breakdown — price below EMA21 after being above (-5 to 0)
    below_ema21 = close < ema21
    ema21_slope = ema21 - ema21.shift(1)
    ema_declining = ema21_slope < 0
    d3 = pd.Series(0.0, index=close.index)
    d3 = d3.where(~(below_ema21 & ema_declining), -5.0)

    risk_flags = (d1 + d2 + d3).clip(lower=-20.0)

    # ================================================================
    # COMPOSITE
    # ================================================================

    hl_raw = trend + flow_conf + rs_score + risk_flags
    hl_score = hl_raw.clip(lower=0.0, upper=100.0)

    state = pd.Series("EXIT", index=close.index)
    state = state.where(~(hl_score >= 30), "TIGHTEN")
    state = state.where(~(hl_score >= 50), "HOLD")
    state = state.where(~(hl_score >= 75), "HOLD_ADD")

    return pd.DataFrame({
        "date": d["date"],
        "hl_score": hl_score.round(1),
        "hl_state": state,
        "hl_trend": trend.round(1),
        "hl_flow": flow_conf.round(1),
        "hl_rs": rs_score.round(1),
        "hl_risk": risk_flags.round(1),
        "hl_higher_lows": hl_count_10.round(0),
        "hl_trend_bars": trend_bars.round(0),
        "hl_vol_updn": vol_updn_ratio.round(3),
        "hl_atr_spike": atr_spike_ratio.round(3),
    })


def _mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    n: int = 14,
) -> pd.Series:
    """Money Flow Index — RSI applied to money flow volume."""
    typical = (high + low + close) / 3.0
    mf = typical * volume
    delta = typical.diff()
    pos_mf = mf.where(delta > 0, 0.0).rolling(n, min_periods=n).sum()
    neg_mf = mf.where(delta <= 0, 0.0).rolling(n, min_periods=n).sum()
    ratio = (pos_mf / neg_mf.replace(0.0, np.nan)).fillna(1.0)
    return 100.0 - 100.0 / (1.0 + ratio)
