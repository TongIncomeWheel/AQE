"""Energy v1.3.1 — port of `sources/Energy_v1_3_1.pine`.

The real volume-profile array (POC / VAH / VAL) is DIAGNOSTIC ONLY in Pine
(Pine line 117 comment). The headline VP-position score uses the range-position
proxy (Pine 25-35). We implement only the proxy here; VP array math is omitted.

Output:
    energy_100      ∈ [0, 100]
    vp_position_score, price_action_score, squeeze_score, exhaustion_score, atr_score
    en_pos50, en_trend_bars (diagnostics)

Composite (Pine 199-200):
    en_raw = vp_proxy + price_action + squeeze + exhaustion + atr
    energy_100 = clip(en_raw / 59.5 * 100, 0, 100)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(
    daily: pd.DataFrame,
    *,
    vol_period: int = 20,
    atr_length: int = 20,
    exh_trend_min: int = 15,
) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    # ---- Component 1: VP Position proxy (Pine 26-35) ----
    hi50 = U.highest(high, 50)
    lo50 = U.lowest(low, 50)
    rng50 = (hi50 - lo50)
    en_pos50 = pd.Series(50.0, index=close.index)
    nz = rng50 != 0
    en_pos50 = en_pos50.where(~nz, (close - lo50) / rng50.replace(0.0, np.nan) * 100.0)
    en_pos50 = en_pos50.fillna(50.0)

    # Pine 30 — bracketed step score on en_pos50.
    en_psc = pd.Series(3.0, index=close.index)
    en_psc = en_psc.where(~(en_pos50 >= 30), 5.0)
    en_psc = en_psc.where(~(en_pos50 >= 45), 8.0)
    en_psc = en_psc.where(~(en_pos50 >= 60), 12.0)
    en_psc = en_psc.where(~(en_pos50 >= 75), 17.0)
    en_psc = en_psc.where(~(en_pos50 >= 90), 15.0)
    # Yes, 90+ scores 15 (not 17). That's Pine line 30 as written: a deliberate "extension" penalty.

    en_r5t = U.highest(high, 5) - U.lowest(low, 5)
    en_atr_vp = U.atr(high, low, close, n=20)
    en_tt = (en_pos50 > 75) & (en_r5t < en_atr_vp * 2.0)
    en_lvn_proxy = en_tt.astype(float) * 1.5
    vp_position_score = (en_psc + en_lvn_proxy).clip(upper=17.5)

    # ---- Component 2: Price Action (Pine 119-143) ----
    # Higher lows count over last 4 comparisons: Pine `for i = 1 to 4: if low[i-1] > low[i]`
    # → low[t-(i-1)] > low[t-i] for i in 1..4
    # → count of (low[t] > low[t-1]) + (low[t-1] > low[t-2]) + (low[t-2] > low[t-3]) + (low[t-3] > low[t-4])
    inc = (low > low.shift(1)).astype(int)
    hl_count = (inc + inc.shift(1).fillna(0) + inc.shift(2).fillna(0) + inc.shift(3).fillna(0))
    structure_score = pd.Series(0.0, index=close.index)
    structure_score = structure_score.where(~(hl_count >= 1), 1.5)
    structure_score = structure_score.where(~(hl_count >= 2), 3.0)
    structure_score = structure_score.where(~(hl_count >= 3), 4.0)
    structure_score = structure_score.where(~(hl_count >= 4), 5.0)

    range_5d = U.highest(high, 5) - U.lowest(low, 5)
    range_20d = U.highest(high, 20) - U.lowest(low, 20)
    compression_ratio = (range_5d / range_20d.replace(0.0, np.nan)).fillna(1.0)
    tightness_base = pd.Series(0.0, index=close.index)
    tightness_base = tightness_base.where(~(compression_ratio < 0.9), 1.0)
    tightness_base = tightness_base.where(~(compression_ratio < 0.7), 2.0)
    tightness_base = tightness_base.where(~(compression_ratio < 0.5), 3.5)
    tightness_base = tightness_base.where(~(compression_ratio < 0.3), 4.5)

    ema_20 = U.ema(close, 20)
    trending_up = (close > ema_20) & (close > close.shift(5))
    tightness_score = tightness_base.where(~trending_up, (tightness_base + 1.5).clip(upper=4.5))

    recent_high = U.highest(high, 20)
    pullback_pct = ((recent_high - close) / recent_high.replace(0.0, np.nan) * 100.0).fillna(0.0)
    pullback_score = pd.Series(0.0, index=close.index)
    pullback_score = pullback_score.where(~(pullback_pct < 25), 1.0)
    pullback_score = pullback_score.where(~(pullback_pct < 15), 2.0)
    pullback_score = pullback_score.where(~(pullback_pct < 10), 2.5)
    pullback_score = pullback_score.where(~(pullback_pct < 5), 3.0)

    pa_raw = structure_score + tightness_score + pullback_score
    # Pine 143: depth modifier
    price_action_score = pa_raw.copy()
    price_action_score = price_action_score.where(~(en_pos50 < 45), pa_raw * 0.7)
    price_action_score = price_action_score.where(~(en_pos50 < 30), pa_raw * 0.5)

    # ---- Component 3: Squeeze (Pine 145-159) ----
    bb = U.sma(close, 20)
    bd = 2.0 * U.stdev_pop(close, 20)
    bu = bb + bd
    bl = bb - bd
    bw = ((bu - bl) / bb.replace(0.0, np.nan) * 100.0).fillna(0.0)
    bwl = U.lowest(bw, 50)
    bwh = U.highest(bw, 50)
    bwr = (bwh - bwl)
    bwp = ((bw - bwl) / bwr.replace(0.0, np.nan) * 100.0).fillna(50.0)
    kcr = U.atr(high, low, close, n=20)
    kcu = bb + kcr * 1.5
    kcl = bb - kcr * 1.5
    sq = (bl > kcl) & (bu < kcu)

    squeeze_score = pd.Series(0.0, index=close.index)
    # bottom-up so highest-priority branch wins.
    squeeze_score = squeeze_score.where(~(bwp < 50), 4.0)
    squeeze_score = squeeze_score.where(~(bwp < 30), 8.5)
    squeeze_score = squeeze_score.where(~sq, 5.0)
    squeeze_score = squeeze_score.where(~(sq & (bwp < 50)), 7.5)
    squeeze_score = squeeze_score.where(~(sq & (bwp < 35)), 10.0)
    squeeze_score = squeeze_score.where(~(sq & (bwp < 20)), 12.5)

    # ---- Component 4: Exhaustion (Pine 161-188) ----
    # Pine 162-163: `var int en_trend_bars` — stateful counter.
    above_ema = (close > ema_20).to_numpy()
    en_trend_arr = np.zeros(n, dtype=int)
    for i in range(n):
        prev = en_trend_arr[i - 1] if i > 0 else 0
        en_trend_arr[i] = prev + 1 if above_ema[i] else 0
    en_trend_bars = pd.Series(en_trend_arr, index=close.index)
    en_trend_mature = en_trend_bars >= exh_trend_min

    vol_avg_20 = U.sma(volume, vol_period)
    vol_ratio = (volume / vol_avg_20.replace(0.0, np.nan)).fillna(1.0)
    price_gain_pct = ((close - close.shift(1)) / close.shift(1).replace(0.0, np.nan) * 100.0).fillna(0.0)
    climactic_penalty = pd.Series(0.0, index=close.index)
    climactic_penalty = climactic_penalty.where(~((vol_ratio > 2.5) & (price_gain_pct < 3)), -2.5)
    climactic_penalty = climactic_penalty.where(~((vol_ratio > 3.0) & (price_gain_pct < 2)), -4.0)

    mfi_14 = _mfi(close, volume, 14)  # Pine uses `ta.mfi(close, 14)` — close as the source
    mfi_prev_high = mfi_14.rolling(5, min_periods=5).max().shift(1)
    price_new_high = high == U.highest(high, 10)
    mfi_lower_high = mfi_14 < mfi_prev_high
    macd_line = U.ema(close, 12) - U.ema(close, 26)
    macd_prev_high = macd_line.rolling(5, min_periods=5).max().shift(1)
    macd_lower_high = macd_line < macd_prev_high
    divergence_penalty = pd.Series(0.0, index=close.index)
    divergence_penalty = divergence_penalty.where(~(price_new_high & macd_lower_high), -2.0)
    divergence_penalty = divergence_penalty.where(~(price_new_high & mfi_lower_high), -3.0)

    bar_range = high - low
    atr_val = U.atr(high, low, close, n=atr_length)
    bar_range_ratio = (bar_range / atr_val.replace(0.0, np.nan)).fillna(1.0)
    follow_through = ((close.shift(1) < close) & (high.shift(1) < high)).astype(float)
    # Pine: if bar_range_ratio > 2.0: follow_through_check := 1 if condition else 0 ; else 0 (initial).
    follow_through_check = follow_through.where(bar_range_ratio > 2.0, 0.0)
    wide_spread_penalty = pd.Series(0.0, index=close.index)
    wide_spread_penalty = wide_spread_penalty.where(~((bar_range_ratio > 1.5) & (vol_ratio > 1.5)), -1.5)
    wide_spread_penalty = wide_spread_penalty.where(
        ~((bar_range_ratio > 2.0) & (vol_ratio > 2.0) & (follow_through_check == 0)),
        -3.0,
    )

    exhaustion_full = (10.0 + climactic_penalty + divergence_penalty + wide_spread_penalty).clip(lower=0.0)
    exhaustion_score = exhaustion_full.where(en_trend_mature, 10.0)

    # ---- Component 5: ATR Expansion (Pine 190-195) ----
    atr_5d = U.sma(atr_val, 5)
    atr_20d = U.sma(atr_val, 20)
    atr_expansion_pct = ((atr_5d - atr_20d) / atr_20d.replace(0.0, np.nan) * 100.0).fillna(0.0)
    # Pine ternary (line 195):
    #   pct >= 20 and <= 80 ? 7 :
    #   pct > 150 ? 2 :
    #   pct > 80 ? 4 :
    #   pct >= 15 ? 5.5 :
    #   pct >= 10 ? 4 :
    #   pct >= 0 ? 1 :
    #   pct >= -10 ? 0.5 : 0
    atr_score = pd.Series(0.0, index=close.index)
    atr_score = atr_score.where(~(atr_expansion_pct >= -10), 0.5)
    atr_score = atr_score.where(~(atr_expansion_pct >= 0), 1.0)
    atr_score = atr_score.where(~(atr_expansion_pct >= 10), 4.0)
    atr_score = atr_score.where(~(atr_expansion_pct >= 15), 5.5)
    atr_score = atr_score.where(~((atr_expansion_pct > 80) & ~((atr_expansion_pct >= 20) & (atr_expansion_pct <= 80))), 4.0)
    atr_score = atr_score.where(~((atr_expansion_pct > 150) & ~((atr_expansion_pct >= 20) & (atr_expansion_pct <= 80))), 2.0)
    atr_score = atr_score.where(~((atr_expansion_pct >= 20) & (atr_expansion_pct <= 80)), 7.0)

    # ---- Composite (Pine 199-200) ----
    en_raw = vp_position_score + price_action_score + squeeze_score + exhaustion_score + atr_score
    energy_100 = (en_raw / 59.5 * 100.0).clip(lower=0.0, upper=100.0)
    # Warmup: highest/lowest over 50 of bb_width (which is itself 20-bar based) = 70 bars.
    warm = bwl.notna() & ema_20.notna() & atr_val.notna()
    energy_100 = energy_100.where(warm, np.nan)

    return pd.DataFrame({
        "date": d["date"],
        "energy_100": energy_100,
        "vp_position_score": vp_position_score,
        "price_action_score": price_action_score,
        "squeeze_score": squeeze_score,
        "exhaustion_score": exhaustion_score,
        "atr_score": atr_score,
        "en_pos50": en_pos50,
        "en_trend_bars": en_trend_bars,
    })


def _mfi(source: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    """Pine `ta.mfi(source, length)`.

    raw_mf = source * volume
    upper = sum of raw_mf where source > source[1] over `length` bars
    lower = sum of raw_mf where source < source[1] over `length` bars
    mfi = 100 - 100/(1 + upper/lower)
    """
    change = source.diff()
    raw_mf = source * volume
    up_contrib = raw_mf.where(change > 0, 0.0)
    dn_contrib = raw_mf.where(change < 0, 0.0)
    upper = up_contrib.rolling(length, min_periods=length).sum()
    lower = dn_contrib.rolling(length, min_periods=length).sum()
    out = 100.0 - 100.0 / (1.0 + upper / lower.replace(0.0, np.nan))
    zero_loss = (lower == 0.0) & (upper > 0.0)
    out = out.where(~zero_loss, 100.0)
    return out.fillna(50.0)
