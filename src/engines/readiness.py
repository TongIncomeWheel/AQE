"""Readiness Score — entry timing from compression + release signals.

Answers: "Is this name ready to move NOW?"

Built from the Section 7 backtest finding that compression features
(range tightness, squeeze, volume dry-up, EMA convergence) are the ONLY
subcomponents with positive TP1 spread. Quality/momentum scores are
inverted (high score = already moved = fewer TP1 hits).

Output:
    rd_score        ∈ [0, 100]  composite readiness
    rd_state        READY / WATCH / NEUTRAL / NOT_READY
    rd_compression  ∈ [0, 60]   compression sub-score
    rd_trigger      ∈ [0, 25]   release/trigger sub-score
    rd_pos_mod      ∈ [-15, 0]  position penalty
    rd_rs_bonus     ∈ [0, 15]   RS acceleration bonus
    rd_inside_bars  diagnostic: inside bar count (5-bar)
    rd_range_exp    diagnostic: range expansion ratio
    rd_vol_surge    diagnostic: volume surge ratio
    rd_close_str    diagnostic: close strength on expansion bars
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(daily: pd.DataFrame, spy_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    atr5 = U.atr(high, low, close, n=5)
    atr20 = U.atr(high, low, close, n=20)
    atr14 = U.atr(high, low, close, n=14)

    # ================================================================
    # A. COMPRESSION STATE (0-60 pts)
    # ================================================================

    # A1: Range tightness — ATR5/ATR20 (rescaled from BQ's 0-30 to 0-18)
    rt_ratio = (atr5 / atr20.replace(0.0, np.nan)).fillna(1.0)
    a1 = pd.Series(0.0, index=close.index)
    a1 = a1.where(~(rt_ratio < 1.0), 3.0)
    a1 = a1.where(~(rt_ratio < 0.9), 6.0)
    a1 = a1.where(~(rt_ratio < 0.8), 9.0)
    a1 = a1.where(~(rt_ratio < 0.7), 12.0)
    a1 = a1.where(~(rt_ratio < 0.6), 15.0)
    a1 = a1.where(~(rt_ratio < 0.5), 18.0)

    # A2: Squeeze — BB inside KC + width percentile (rescaled 0-12.5 to 0-8)
    bb_mid = U.sma(close, 20)
    bb_dev = 2.0 * U.stdev_pop(close, 20)
    bb_upper = bb_mid + bb_dev
    bb_lower = bb_mid - bb_dev
    bw = ((bb_upper - bb_lower) / bb_mid.replace(0.0, np.nan) * 100).fillna(0.0)
    bw_lo = U.lowest(bw, 50)
    bw_hi = U.highest(bw, 50)
    bw_range = bw_hi - bw_lo
    bwp = ((bw - bw_lo) / bw_range.replace(0.0, np.nan) * 100).fillna(50.0)
    kc_range = U.atr(high, low, close, n=20)
    kc_upper = bb_mid + kc_range * 1.5
    kc_lower = bb_mid - kc_range * 1.5
    sq = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    a2 = pd.Series(0.0, index=close.index)
    a2 = a2.where(~(bwp < 50), 2.5)
    a2 = a2.where(~(bwp < 30), 5.0)
    a2 = a2.where(~sq, 3.0)
    a2 = a2.where(~(sq & (bwp < 50)), 5.0)
    a2 = a2.where(~(sq & (bwp < 35)), 6.5)
    a2 = a2.where(~(sq & (bwp < 20)), 8.0)

    # A3: Volume dry-up — SMA5/SMA20 vol (rescaled 0-25 to 0-15)
    v5 = U.sma(volume, 5)
    v20 = U.sma(volume, 20)
    vd_ratio = (v5 / v20.replace(0.0, np.nan)).fillna(1.0)
    a3 = pd.Series(0.0, index=close.index)
    a3 = a3.where(~(vd_ratio < 1.1), 3.0)
    a3 = a3.where(~(vd_ratio < 0.95), 6.0)
    a3 = a3.where(~(vd_ratio < 0.8), 9.0)
    a3 = a3.where(~(vd_ratio < 0.65), 12.0)
    a3 = a3.where(~(vd_ratio < 0.5), 15.0)

    # A4: EMA convergence — EMA 8/13/21 spread / ATR20 (rescaled 0-25 to 0-10)
    ema8 = U.ema(close, 8)
    ema13 = U.ema(close, 13)
    ema21 = U.ema(close, 21)
    ema_max = pd.concat([ema8, ema13, ema21], axis=1).max(axis=1)
    ema_min = pd.concat([ema8, ema13, ema21], axis=1).min(axis=1)
    ema_spread = (ema_max - ema_min) / atr20.replace(0.0, np.nan)
    ema_spread = ema_spread.fillna(5.0)
    a4 = pd.Series(0.0, index=close.index)
    a4 = a4.where(~(ema_spread < 2.5), 2.0)
    a4 = a4.where(~(ema_spread < 1.8), 4.0)
    a4 = a4.where(~(ema_spread < 1.2), 6.0)
    a4 = a4.where(~(ema_spread < 0.8), 8.0)
    a4 = a4.where(~(ema_spread < 0.5), 10.0)

    # A5: Inside bar count (5-bar) — NEW
    inside = ((high < high.shift(1)) & (low > low.shift(1))).astype(float)
    ib_count = inside.rolling(5, min_periods=1).sum()
    a5 = pd.Series(0.0, index=close.index)
    a5 = a5.where(~(ib_count >= 1), 2.0)
    a5 = a5.where(~(ib_count >= 2), 4.0)
    a5 = a5.where(~(ib_count >= 3), 6.0)
    a5 = a5.where(~(ib_count >= 4), 8.0)
    a5 = a5.where(~(ib_count >= 5), 9.0)

    compression = (a1 + a2 + a3 + a4 + a5).clip(upper=60.0)

    # ================================================================
    # B. TRIGGER / RELEASE (0-25 pts)
    # ================================================================

    daily_range = high - low
    range_sma5 = U.sma(daily_range, 5)
    range_exp_ratio = (daily_range / range_sma5.replace(0.0, np.nan)).fillna(1.0)
    is_compressed = compression >= 20

    # B1: Range expansion (0-12) — only fires if compressed
    b1 = pd.Series(0.0, index=close.index)
    b1 = b1.where(~(is_compressed & (range_exp_ratio > 1.3)), 4.0)
    b1 = b1.where(~(is_compressed & (range_exp_ratio > 1.5)), 7.0)
    b1 = b1.where(~(is_compressed & (range_exp_ratio > 2.0)), 12.0)

    # B2: Volume surge from dry-up (0-10) — only fires if volume was dry
    vol_was_dry = a3 >= 6
    vol_surge_ratio = (volume / v5.replace(0.0, np.nan)).fillna(1.0)
    b2 = pd.Series(0.0, index=close.index)
    b2 = b2.where(~(vol_was_dry & (vol_surge_ratio > 1.5)), 4.0)
    b2 = b2.where(~(vol_was_dry & (vol_surge_ratio > 2.0)), 7.0)
    b2 = b2.where(~(vol_was_dry & (vol_surge_ratio > 3.0)), 10.0)

    # B3: Close strength on expansion bars (0-3)
    close_in_range = ((close - low) / daily_range.replace(0.0, np.nan)).fillna(0.5)
    has_expansion = range_exp_ratio > 1.3
    b3 = pd.Series(0.0, index=close.index)
    b3 = b3.where(~(has_expansion & (close_in_range > 0.7)), 3.0)

    trigger = (b1 + b2 + b3).clip(upper=25.0)

    # ================================================================
    # C. POSITION MODIFIER (-15 to 0)
    # ================================================================

    # en_pos50 equivalent: 50d range position
    hi50 = U.highest(high, 50)
    lo50 = U.lowest(low, 50)
    pos50 = ((close - lo50) / (hi50 - lo50).replace(0.0, np.nan) * 100).fillna(50.0)

    # Elder score equivalent: EMA13 slope + MACD histogram direction
    ema13_slope = ema13 - ema13.shift(1)
    macd_line = U.ema(close, 12) - U.ema(close, 26)
    macd_signal = U.ema(macd_line, 9)
    macd_hist = macd_line - macd_signal
    macd_hist_rising = macd_hist > macd_hist.shift(1)
    ema13_rising = ema13_slope > 0
    elder_proxy = (ema13_rising.astype(int) + macd_hist_rising.astype(int)) * 5

    pos_mod = pd.Series(0.0, index=close.index)
    pos_mod = pos_mod.where(~(pos50 > 90), -12.0)
    pos_mod = pos_mod.where(~((pos50 > 80) & (pos50 <= 90)), -8.0)
    elder_penalty = pd.Series(0.0, index=close.index)
    elder_penalty = elder_penalty.where(~(elder_proxy >= 8), -3.0)
    pos_mod = (pos_mod + elder_penalty).clip(lower=-15.0)

    # ================================================================
    # D. RS ACCELERATION BONUS (0-15)
    # ================================================================

    rs_bonus = pd.Series(0.0, index=close.index)
    if spy_daily is not None and len(spy_daily) > 60:
        spy = spy_daily.reset_index(drop=True)
        spy_close = spy["close"].astype(float)
        min_len = min(len(close), len(spy_close))
        if min_len > 60:
            sc = close.iloc[:min_len]
            spc = spy_close.iloc[:min_len]
            rs_20 = (sc / sc.shift(20) - 1) * 100 - (spc / spc.shift(20) - 1) * 100
            rs_60 = (sc / sc.shift(60) - 1) * 100 - (spc / spc.shift(60) - 1) * 100
            rs_accel = rs_20 - rs_60
            rs_b = pd.Series(0.0, index=sc.index)
            rs_b = rs_b.where(~(rs_accel > 0), 5.0)
            rs_b = rs_b.where(~(rs_accel > 2), 10.0)
            rs_b = rs_b.where(~(rs_accel > 5), 15.0)
            rs_bonus = rs_b.reindex(close.index, fill_value=0.0)

    # ================================================================
    # COMPOSITE
    # ================================================================

    rd_raw = compression + trigger + pos_mod + rs_bonus
    rd_score = rd_raw.clip(lower=0.0, upper=100.0)

    state = pd.Series("NOT_READY", index=close.index)
    state = state.where(~(rd_score >= 40), "NEUTRAL")
    state = state.where(~(rd_score >= 60), "WATCH")
    state = state.where(~(rd_score >= 80), "READY")

    return pd.DataFrame({
        "date": d["date"],
        "rd_score": rd_score.round(1),
        "rd_state": state,
        "rd_compression": compression.round(1),
        "rd_trigger": trigger.round(1),
        "rd_pos_mod": pos_mod.round(1),
        "rd_rs_bonus": rs_bonus.round(1),
        "rd_inside_bars": ib_count.round(0),
        "rd_range_exp": range_exp_ratio.round(3),
        "rd_vol_surge": vol_surge_ratio.round(3),
        "rd_close_str": close_in_range.round(3),
    })
