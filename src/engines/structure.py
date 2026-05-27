"""Structure v1.5.0 — port of `sources/Structure_v1.5.pine`.

Output:
    structure_100   ∈ [0, 100]
    rs_spy_score, rs_accel_score, base_score, ms_pos, resist_score, wk_score, earn_score
    base_days, bd_mode, ms_p50 (diagnostics)

Composite (Pine 171-173):
    ms_raw = rs_spy + rs_accel + base + ms_pos + resist + wk + earn
    structure_100 = clip(ms_raw / 95 * 100, 0, 100)

v2: earn_score uses FMP earnings calendar when available.
Scoring: <=5d -> 0, <=10d -> 4, <=20d -> 7, >20d/unknown -> 10.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(
    daily: pd.DataFrame,
    spy_daily: pd.DataFrame,
    weekly: pd.DataFrame,
    *,
    earn_score_override: float = 10.0,
    earnings_cal: dict[str, str] | None = None,
    ticker: str = "",
) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    # ---- 1. RS vs SPY (Pine 31-37) ----
    spy_close = _align_spy_close(spy_daily, d["date"])
    stock_perf = (close - close.shift(60)) / close.shift(60).replace(0.0, np.nan) * 100.0
    bench_perf = (spy_close - spy_close.shift(60)) / spy_close.shift(60).replace(0.0, np.nan) * 100.0
    rs_vs_spy = (stock_perf - bench_perf).fillna(0.0)
    rs_spy_score = pd.Series(0.0, index=close.index)
    rs_spy_score = rs_spy_score.where(~(rs_vs_spy > -3), 3.0)
    rs_spy_score = rs_spy_score.where(~(rs_vs_spy > 0), 6.0)
    rs_spy_score = rs_spy_score.where(~(rs_vs_spy > 2), 10.0)
    rs_spy_score = rs_spy_score.where(~(rs_vs_spy > 5), 12.0)
    rs_spy_score = rs_spy_score.where(~(rs_vs_spy > 10), 15.0)

    # ---- 2. RS Acceleration (Pine 40-42) ----
    rs_short = (close - close.shift(20)) / close.shift(20).replace(0.0, np.nan) * 100.0 \
        - (spy_close - spy_close.shift(20)) / spy_close.shift(20).replace(0.0, np.nan) * 100.0
    rs_accel = (rs_short - rs_vs_spy).fillna(0.0)
    rs_accel_score = pd.Series(0.0, index=close.index)
    rs_accel_score = rs_accel_score.where(~(rs_accel > -5), 3.0)
    rs_accel_score = rs_accel_score.where(~(rs_accel > -2), 6.0)
    rs_accel_score = rs_accel_score.where(~(rs_accel > 0), 9.0)
    rs_accel_score = rs_accel_score.where(~(rs_accel > 2), 12.0)
    rs_accel_score = rs_accel_score.where(~(rs_accel > 5), 15.0)

    # ---- 3. Base Duration 3-mode + latch (Pine 44-128) ----
    atr_val = U.atr(high, low, close, n=20)
    range_10 = U.highest(high, 10) - U.lowest(low, 10)
    range_pct = (range_10 / close.replace(0.0, np.nan) * 100.0).fillna(100.0)
    mode1_vcp = range_pct <= 15.0

    sma_50 = U.sma(close, 50)
    uptrend_sma50 = (close > sma_50) & (sma_50 > sma_50.shift(5))
    local_high_10 = U.highest(high, 10)
    pullback_from_high = ((local_high_10 - close) / local_high_10.replace(0.0, np.nan) * 100.0).fillna(100.0)
    shallow_pullback = (pullback_from_high >= 1.5) & (pullback_from_high < 8.0)
    # Pine: for i = 1 to 5: if low[i-1] > low[i]   → 5 comparisons of (low[t-(i-1)] > low[t-i])
    inc = (low > low.shift(1)).astype(int)
    stair_hl_count = (
        inc + inc.shift(1).fillna(0) + inc.shift(2).fillna(0) + inc.shift(3).fillna(0) + inc.shift(4).fillna(0)
    )
    has_staircase = stair_hl_count >= 2
    mode2_staircase = uptrend_sma50 & shallow_pullback & has_staircase

    ema_20_struct = U.ema(close, 20)
    ema20_rising = ema_20_struct > ema_20_struct.shift(3)
    near_ema20 = ((close - ema_20_struct).abs() <= atr_val * 1.0) & atr_val.notna() & (atr_val != 0)
    mode3_smooth = ema20_rising & near_ema20 & (close > sma_50)

    in_base = (mode1_vcp | mode2_staircase | mode3_smooth).fillna(False)
    mode_count = mode1_vcp.astype(int) + mode2_staircase.astype(int) + mode3_smooth.astype(int)
    bd_mode = pd.Series(0, index=close.index)
    bd_mode = bd_mode.where(~mode1_vcp, 1)
    bd_mode = bd_mode.where(~mode2_staircase, 2)
    bd_mode = bd_mode.where(~mode3_smooth, 3)
    bd_mode = bd_mode.where(~(mode_count >= 2), 4)

    # Stateful loop: raw_base_count, breakout detection, latch (DSG-02), decay.
    in_base_arr = in_base.to_numpy()
    high_arr = high.to_numpy()
    close_arr = close.to_numpy()
    volume_arr = volume.to_numpy()
    vol_sma20 = U.sma(volume, 20).to_numpy()
    min_base_days_param = 3
    decay_window = 10

    raw_base_count = np.zeros(n, dtype=int)
    breakout_bar = np.zeros(n, dtype=bool)
    latched_base_days = np.zeros(n, dtype=int)
    bars_since_breakout = np.full(n, 999, dtype=int)

    for t in range(n):
        # Phase 1: raw accumulation
        prev_raw = raw_base_count[t - 1] if t > 0 else 0
        raw_base_count[t] = prev_raw + 1 if in_base_arr[t] else 0

        # Phase 2: breakout detection (Pine 90-102).
        # consolidation_high seeds at high[t-1] (i=1) and walks back i=1..capped_len
        # taking the running max. That is just the max of high over the window
        # high_arr[t-capped_len : t] (inclusive of t-capped_len, exclusive of t).
        if t == 0:
            continue
        prev_base_len = max(int(prev_raw), 1)
        capped_len = min(prev_base_len, 60)
        window_start = max(0, t - capped_len)
        consolidation_high = float(np.nanmax(high_arr[window_start:t]))

        cond_break = (
            close_arr[t] > consolidation_high
            and not in_base_arr[t]
            and prev_raw >= min_base_days_param
            and not np.isnan(vol_sma20[t])
            and volume_arr[t] > vol_sma20[t]
        )
        breakout_bar[t] = cond_break

        # Phase 3: latch (DSG-02)
        prev_latched = latched_base_days[t - 1]
        prev_bsb = bars_since_breakout[t - 1]
        if cond_break:
            latched_base_days[t] = int(prev_raw)
            bars_since_breakout[t] = 0
        else:
            latched_base_days[t] = prev_latched
            bars_since_breakout[t] = prev_bsb + 1

    # Phase 4: reported base_days with decay
    base_days = np.where(bars_since_breakout <= decay_window, latched_base_days, raw_base_count).astype(int)
    base_days_s = pd.Series(base_days, index=close.index)

    # Scoring tiers (Pine 118)
    base_raw = pd.Series(0.0, index=close.index)
    base_raw = base_raw.where(~(base_days_s < 5), 3.0)
    base_raw = base_raw.where(~((base_days_s >= 5) & (base_days_s < 7)), 6.0)
    base_raw = base_raw.where(~((base_days_s >= 7) & (base_days_s < 10)), 10.0)
    base_raw = base_raw.where(~((base_days_s >= 10) & (base_days_s <= 25)), 15.0)
    base_raw = base_raw.where(~((base_days_s > 25) & (base_days_s <= 30)), 12.0)
    base_raw = base_raw.where(~((base_days_s > 30) & (base_days_s <= 35)), 8.0)
    base_raw = base_raw.where(~(base_days_s > 35), 5.0)
    base_raw = base_raw.where(~(base_days_s < 3), 0.0)

    # Higher-Lows quality multiplier (Pine 120-127)
    hl_lookback_arr = np.minimum(base_days, 10).astype(int)
    hl_in_base_arr = np.zeros(n, dtype=int)
    low_arr = low.to_numpy()
    for t in range(n):
        lk = int(hl_lookback_arr[t])
        count = 0
        # Pine: for i = 1 to 10: if i <= hl_lookback and low[i] > low[i+1]
        # → indices i in 1..lk → compare low[t-i] > low[t-i-1]
        for i in range(1, lk + 1):
            if t - i - 1 < 0:
                break
            if low_arr[t - i] > low_arr[t - i - 1]:
                count += 1
        hl_in_base_arr[t] = count
    hl_in_base = pd.Series(hl_in_base_arr, index=close.index)
    base_quality_mult = pd.Series(0.6, index=close.index)
    base_quality_mult = base_quality_mult.where(~(hl_in_base >= 2), 0.8)
    base_quality_mult = base_quality_mult.where(~(hl_in_base >= 4), 1.0)
    base_score = (base_raw * base_quality_mult).clip(upper=15.0)

    # ---- 4. Range Position 50d (Pine 140-144) ----
    ms_h50 = U.highest(high, 50)
    ms_l50 = U.lowest(low, 50)
    ms_r50 = ms_h50 - ms_l50
    ms_p50 = pd.Series(50.0, index=close.index)
    ms_p50 = ms_p50.where(~(ms_r50 != 0), (close - ms_l50) / ms_r50.replace(0.0, np.nan) * 100.0)
    ms_p50 = ms_p50.fillna(50.0)
    ms_pos = pd.Series(0.0, index=close.index)
    ms_pos = ms_pos.where(~(ms_p50 >= 45), 4.0)
    ms_pos = ms_pos.where(~(ms_p50 >= 60), 7.0)
    ms_pos = ms_pos.where(~(ms_p50 >= 75), 10.0)
    ms_pos = ms_pos.where(~(ms_p50 >= 85), 13.0)
    ms_pos = ms_pos.where(~(ms_p50 >= 95), 15.0)

    # ---- 5. Resistance Clearance (Pine 153-156) ----
    dist_to_resist = ((ms_h50 - close) / close.replace(0.0, np.nan) * 100.0).fillna(0.0)
    resist_score = pd.Series(0.0, index=close.index)
    resist_score = resist_score.where(~(dist_to_resist <= 15), 3.0)
    resist_score = resist_score.where(~(dist_to_resist <= 8), 5.0)
    resist_score = resist_score.where(~(dist_to_resist <= 3), 10.0)
    resist_score = resist_score.where(~(dist_to_resist <= 0), 7.0)

    # ---- 6. Weekly Trend (Pine 158-163) ----
    wk_sma10, wk_sma10_prev, wk_close = _weekly_features(weekly, d["date"])
    wk_rising = wk_sma10 > wk_sma10_prev
    wk_score = pd.Series(7.5, index=close.index)
    has_weekly = wk_sma10.notna() & wk_close.notna() & wk_sma10_prev.notna()
    # Build from lowest tier up so the highest matching one wins.
    wk_score_calc = pd.Series(0.0, index=close.index)
    wk_score_calc = wk_score_calc.where(~(wk_close > wk_sma10 * 0.93), 2.0)
    wk_score_calc = wk_score_calc.where(~(wk_close > wk_sma10 * 0.97), 5.0)
    wk_score_calc = wk_score_calc.where(~(wk_close > wk_sma10), 10.0)
    wk_score_calc = wk_score_calc.where(~((wk_close > wk_sma10) & wk_rising), 15.0)
    wk_score = wk_score.where(~has_weekly, wk_score_calc)

    # ---- 7. Earnings proximity (Component 3G) ----
    if earnings_cal and ticker and ticker in earnings_cal:
        from src.data.earnings import build_earnings_series
        earn_score = build_earnings_series(d["date"], ticker, earnings_cal)
    else:
        earn_score = pd.Series(earn_score_override, index=close.index)

    # ---- Composite ----
    ms_raw = rs_spy_score + rs_accel_score + base_score + ms_pos + resist_score + wk_score + earn_score
    structure_100 = (ms_raw / 95.0 * 100.0).clip(lower=0.0, upper=100.0)
    # Warmup: 60-bar RS lookback + 50-bar SMA + weekly SMA(10).
    warm = sma_50.notna() & spy_close.shift(60).notna() & close.shift(60).notna()
    structure_100 = structure_100.where(warm, np.nan)

    return pd.DataFrame({
        "date": d["date"],
        "structure_100": structure_100,
        "rs_spy_score": rs_spy_score,
        "rs_accel_score": rs_accel_score,
        "base_score": base_score,
        "ms_pos_score": ms_pos,
        "resist_score": resist_score,
        "wk_score": wk_score,
        "earn_score": earn_score,
        "base_days": base_days_s,
        "bd_mode": bd_mode.astype(int),
        "ms_p50": ms_p50,
        "rs_vs_spy": rs_vs_spy,
        "rs_accel": rs_accel,
    })


# ---------- helpers ----------


def _align_spy_close(spy_daily: pd.DataFrame, dates: pd.Series) -> pd.Series:
    if spy_daily.empty:
        return pd.Series(np.nan, index=dates.index, dtype=float)
    o = spy_daily[["date", "close"]].copy()
    o["date"] = pd.to_datetime(o["date"]).dt.normalize()
    o = o.drop_duplicates("date", keep="last")  # defensive: corrupted parquets can dup-date
    lookup = o.set_index("date")["close"].astype(float)
    aligned = pd.to_datetime(dates).dt.normalize().map(lookup)
    aligned.index = dates.index
    return aligned.astype(float)


def _weekly_features(weekly: pd.DataFrame, daily_dates: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (wk_sma10, wk_sma10_prev, wk_close) aligned to daily_dates with no look-ahead."""
    if weekly is None or weekly.empty:
        idx = daily_dates.index
        empty = pd.Series(np.nan, index=idx, dtype=float)
        return empty, empty, empty
    wk = weekly[["date", "close"]].copy()
    wk["date"] = pd.to_datetime(wk["date"]).dt.normalize()
    wk = wk.sort_values("date").reset_index(drop=True)
    wk["sma10"] = wk["close"].rolling(10, min_periods=10).mean()
    wk["sma10_prev"] = wk["sma10"].shift(1)
    sma10 = U.asof_weekly_value(daily_dates, wk.rename(columns={"sma10": "x"})[["date", "x"]], "x")
    sma10_prev = U.asof_weekly_value(daily_dates, wk.rename(columns={"sma10_prev": "x"})[["date", "x"]], "x")
    wk_close = U.asof_weekly_value(daily_dates, wk.rename(columns={"close": "x"})[["date", "x"]], "x")
    return sma10, sma10_prev, wk_close
