"""Base Quality (BQ) sub-engine — used by SC_POSITION composite.

Output:
    bq_100          ∈ [0, 100]
    bq_range_tight, bq_vol_dry, bq_base_dur, bq_ema_conv (diagnostics)

Components (per Design Committee Spec):
    BQ1: Range Tightness   — ATR(5)/ATR(20) ratio        (max 30)
    BQ2: Volume Dry-Up     — SMA(vol,5)/SMA(vol,20)      (max 25)
    BQ3: Base Duration      — 3-mode + DSG-02 latch/decay (max 20)
    BQ4: EMA Convergence   — EMA spread / ATR(20)         (max 25)

BQ raw max = 100 (already normalised).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    atr5 = U.atr(high, low, close, n=5)
    atr20 = U.atr(high, low, close, n=20)

    # ---- BQ1: Range Tightness (30 pts) ----
    rt_ratio = (atr5 / atr20.replace(0.0, np.nan)).fillna(1.0)
    bq_range_tight = pd.Series(0.0, index=close.index)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 1.0), 4.0)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 0.9), 8.0)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 0.8), 14.0)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 0.7), 20.0)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 0.6), 25.0)
    bq_range_tight = bq_range_tight.where(~(rt_ratio < 0.5), 30.0)

    # ---- BQ2: Volume Dry-Up (25 pts) ----
    v5 = U.sma(volume, 5)
    v20 = U.sma(volume, 20)
    vd_ratio = (v5 / v20.replace(0.0, np.nan)).fillna(1.0)
    bq_vol_dry = pd.Series(0.0, index=close.index)
    bq_vol_dry = bq_vol_dry.where(~(vd_ratio < 1.1), 5.0)
    bq_vol_dry = bq_vol_dry.where(~(vd_ratio < 0.95), 10.0)
    bq_vol_dry = bq_vol_dry.where(~(vd_ratio < 0.8), 15.0)
    bq_vol_dry = bq_vol_dry.where(~(vd_ratio < 0.65), 20.0)
    bq_vol_dry = bq_vol_dry.where(~(vd_ratio < 0.5), 25.0)

    # ---- BQ3: Base Duration (20 pts) ----
    # Uses same 3-mode system as Structure BD but with 60-bar pivot and 8% band.
    pivot_60 = U.highest(high, 60)
    band_8pct = pivot_60 * 0.08
    in_band_basic = (pivot_60 - close) <= band_8pct

    sma_50 = U.sma(close, 50)
    uptrend_sma50 = (close > sma_50) & (sma_50 > sma_50.shift(5))
    local_high_10 = U.highest(high, 10)
    pullback_from_high = ((local_high_10 - close) / local_high_10.replace(0.0, np.nan) * 100.0).fillna(100.0)
    shallow_pullback = (pullback_from_high >= 1.5) & (pullback_from_high < 8.0)
    inc = (low > low.shift(1)).astype(int)
    stair_hl_count = inc + inc.shift(1).fillna(0) + inc.shift(2).fillna(0) + inc.shift(3).fillna(0) + inc.shift(4).fillna(0)
    has_staircase = stair_hl_count >= 2
    mode2_staircase = uptrend_sma50 & shallow_pullback & has_staircase & in_band_basic

    ema_20 = U.ema(close, 20)
    ema20_rising = ema_20 > ema_20.shift(3)
    near_ema20 = ((close - ema_20).abs() <= atr20 * 1.0) & atr20.notna() & (atr20 != 0)
    mode3_smooth = ema20_rising & near_ema20 & (close > sma_50) & in_band_basic

    in_base = (in_band_basic | mode2_staircase | mode3_smooth).fillna(False)

    # Stateful loop: accumulation, breakout detect, latch (DSG-02), decay.
    in_base_arr = in_base.to_numpy()
    high_arr = high.to_numpy()
    close_arr = close.to_numpy()
    volume_arr = volume.to_numpy()
    vol_sma20 = v20.to_numpy()
    decay_window = 10

    raw_base_count = np.zeros(n, dtype=int)
    latched_base_days = np.zeros(n, dtype=int)
    bars_since_breakout = np.full(n, 999, dtype=int)

    for t in range(n):
        prev_raw = raw_base_count[t - 1] if t > 0 else 0
        raw_base_count[t] = prev_raw + 1 if in_base_arr[t] else 0

        if t == 0:
            continue
        prev_base_len = max(int(prev_raw), 1)
        capped_len = min(prev_base_len, 60)
        window_start = max(0, t - capped_len)
        consolidation_high = float(np.nanmax(high_arr[window_start:t]))

        cond_break = (
            close_arr[t] > consolidation_high
            and not in_base_arr[t]
            and prev_raw >= 3
            and not np.isnan(vol_sma20[t])
            and volume_arr[t] > vol_sma20[t]
        )

        prev_latched = latched_base_days[t - 1]
        prev_bsb = bars_since_breakout[t - 1]
        if cond_break:
            latched_base_days[t] = int(prev_raw)
            bars_since_breakout[t] = 0
        else:
            latched_base_days[t] = prev_latched
            bars_since_breakout[t] = prev_bsb + 1

    base_days = np.where(bars_since_breakout <= decay_window, latched_base_days, raw_base_count).astype(int)
    base_days_s = pd.Series(base_days, index=close.index)

    # BQ3 scoring tiers (different from Structure)
    bq_base_dur = pd.Series(0.0, index=close.index)
    bq_base_dur = bq_base_dur.where(~((base_days_s >= 3) & (base_days_s <= 4)), 4.0)
    bq_base_dur = bq_base_dur.where(~((base_days_s >= 5) & (base_days_s <= 6)), 8.0)
    bq_base_dur = bq_base_dur.where(~((base_days_s >= 7) & (base_days_s <= 9)), 14.0)
    bq_base_dur = bq_base_dur.where(~((base_days_s >= 10) & (base_days_s <= 25)), 20.0)
    bq_base_dur = bq_base_dur.where(~((base_days_s >= 25) & (base_days_s <= 35)), 14.0)
    bq_base_dur = bq_base_dur.where(~(base_days_s > 35), 8.0)

    # ---- BQ4: EMA Convergence (25 pts) ----
    e8 = U.ema(close, 8)
    e13 = U.ema(close, 13)
    e21 = U.ema(close, 21)
    ema_max = pd.concat([e8, e13, e21], axis=1).max(axis=1)
    ema_min = pd.concat([e8, e13, e21], axis=1).min(axis=1)
    spread = ema_max - ema_min
    norm_spread = (spread / atr20.replace(0.0, np.nan)).fillna(5.0)
    bq_ema_conv = pd.Series(0.0, index=close.index)
    bq_ema_conv = bq_ema_conv.where(~(norm_spread < 2.5), 5.0)
    bq_ema_conv = bq_ema_conv.where(~(norm_spread < 1.8), 10.0)
    bq_ema_conv = bq_ema_conv.where(~(norm_spread < 1.2), 15.0)
    bq_ema_conv = bq_ema_conv.where(~(norm_spread < 0.8), 20.0)
    bq_ema_conv = bq_ema_conv.where(~(norm_spread < 0.5), 25.0)

    # ---- Composite ----
    bq_100 = (bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv).clip(lower=0.0, upper=100.0)
    # Warmup: need ATR(20) + SMA(50) + 60-bar highest
    warm = atr20.notna() & sma_50.notna() & pivot_60.notna()
    bq_100 = bq_100.where(warm, np.nan)

    return pd.DataFrame({
        "date": d["date"],
        "bq_100": bq_100,
        "bq_range_tight": bq_range_tight,
        "bq_vol_dry": bq_vol_dry,
        "bq_base_dur": bq_base_dur,
        "bq_ema_conv": bq_ema_conv,
        "bq_base_days": base_days_s,
    })
