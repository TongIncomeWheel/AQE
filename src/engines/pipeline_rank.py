"""Pipeline Rank v1.0 — Stage 1 universe screener.

PIPELINE_RANK = Momentum_Composite × 0.70 + FIP_Quality × 0.30

Momentum Composite (5 sub-components, 0-100):
    1. 12-month return (skip 1 month)
    2. ADX trend strength
    3. RSI momentum zone
    4. Volume confirmation
    5. MA structure

FIP Path Quality (0-100):
    Fraction-of-Informed-Pricing measure + spike penalty.

All from daily OHLCV — zero weekly/benchmark dependency.
Filter: PIPE_RANK >= 60 advances to full scoring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def _fip_step_score(raw: float) -> float:
    """Map FIP raw value to 0-100 quality score using step-function buckets."""
    if raw > 0.10:
        return 10.0
    if raw > 0.0:
        return 30.0
    if raw >= -0.05:
        return 60.0
    if raw >= -0.10:
        return 80.0
    return 100.0


def _detect_prior_spike(
    close: pd.Series,
    lookback: int = 252,
    spike_return_threshold: float = 0.30,
    spike_min_age_bars: int = 126,
    spike_confirm_drawdown: float = 0.30,
    spike_exclusion_window: int = 21,
) -> tuple[bool, int | None, int | None, int | None]:
    """Detect a prior speculative spike-and-collapse in the lookback window.

    Returns (spike_found, spike_peak_bar, excl_start, excl_end) relative
    to the lookback window slice.
    """
    px = close.iloc[-lookback:].values
    n = len(px)

    for i in range(20, n):
        bars_from_end = n - i
        if bars_from_end < spike_min_age_bars:
            break

        base = px[i - 20]
        if base == 0:
            continue
        r21 = (px[i] - base) / base
        if abs(r21) < spike_return_threshold:
            continue

        peak_price = max(px[i - 20 : i + 1])
        if peak_price == 0:
            continue
        subsequent = px[i + 1 :]
        if len(subsequent) == 0:
            continue
        trough = min(subsequent)
        drawdown = (peak_price - trough) / peak_price
        if drawdown >= spike_confirm_drawdown:
            excl_start = max(0, i - spike_exclusion_window)
            excl_end = min(n - 1, i + spike_exclusion_window)
            return True, i, excl_start, excl_end

    return False, None, None, None


def _fip_spike_asof(close: pd.Series, daily_ret: pd.Series, lookback: int = 252,
                    spike_return_threshold: float = 0.30, spike_min_age_bars: int = 126,
                    spike_confirm_drawdown: float = 0.30, spike_exclusion_window: int = 21):
    """DSG-20 prior-spike exclusion evaluated AS OF EVERY BAR (shadow v2, 2026-11-21 review item 6).

    The live path applies the exclusion on the LAST bar only, so every historical bar keeps the un-excluded FIP and the stored history differs from
    what the live formula would have produced on that day. This runs the same detector on the trailing `lookback` window ending at each bar t, with
    the same thresholds, then re-scores FIP on the returns outside the exclusion band. ONE sign rule: the sign of the COMPOUNDED return of the included
    days (np.sign, 0 at 0), the rule the non-excluded path uses at pipeline_rank.py `cum_ret_sign` (the live exclusion branch used the arithmetic sum, -1 at 0).

    Returns (excluded[bool], eff_window[int], raw[float], quality[float]); raw / quality are NaN where no spike applies (the caller keeps the base value).
    """
    px = close.to_numpy(dtype=float)
    dr = daily_ret.to_numpy(dtype=float)
    n = len(px)
    excluded = np.zeros(n, dtype=bool)
    eff = np.full(n, lookback, dtype=int)
    raw = np.full(n, np.nan)
    qual = np.full(n, np.nan)
    if n < lookback:
        return excluded, eff, raw, qual
    # candidate spike bars g: a >=30% move over 20 bars, with the 21-bar peak
    cand, peak = [], {}
    for g in range(20, n):
        base = px[g - 20]
        if base == 0 or np.isnan(base) or np.isnan(px[g]):
            continue
        if abs((px[g] - base) / base) < spike_return_threshold:
            continue
        pk = np.nanmax(px[g - 20: g + 1])
        if pk == 0:
            continue
        cand.append(g)
        peak[g] = pk
    if not cand:
        return excluded, eff, raw, qual
    cand_arr = np.asarray(cand)
    for t in range(lookback - 1, n):
        s0 = t - (lookback - 1)
        lo, hi = s0 + 20, s0 + (lookback - spike_min_age_bars)        # local i in [20, lookback-126]
        a, b = np.searchsorted(cand_arr, lo, "left"), np.searchsorted(cand_arr, hi, "right")
        found = None
        for g in cand_arr[a:b]:
            sub = px[g + 1: t + 1]
            if len(sub) == 0:
                continue
            if (peak[g] - np.nanmin(sub)) / peak[g] >= spike_confirm_drawdown:
                found = int(g)
                break
        if found is None:
            continue
        es, ee = max(s0, found - spike_exclusion_window), min(t, found + spike_exclusion_window)
        win = dr[s0: t + 1].copy()
        win[es - s0: ee - s0 + 1] = np.nan                              # excluded band
        inc = win[~np.isnan(win)]
        if len(inc) == 0:
            continue
        pp, pn = float((inc > 0).mean()), float((inc < 0).mean())
        sign = float(np.sign(np.prod(1.0 + inc) - 1.0))
        r = (pn - pp) * sign
        q = _fip_step_score(r)
        if np.nanmax(np.abs(dr[t - 4: t + 1])) > 0.08:
            q = max(0.0, q - 30.0)
        excluded[t], eff[t], raw[t], qual[t] = True, len(inc), r, q
    return excluded, eff, raw, qual


def compute(daily: pd.DataFrame) -> pd.DataFrame:
    """Compute Pipeline Rank for a single ticker's daily OHLCV frame."""
    d = daily.reset_index(drop=True).copy()
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    n = len(close)

    # ---- 1. 12-Month Return, skip 1 month (20 pts) ----
    # 252 - 21 = 231 bars lookback
    ret_12m = (close / close.shift(231).replace(0.0, np.nan) - 1.0) * 100.0
    ret_score = pd.Series(0.0, index=close.index)
    ret_score = ret_score.where(~(ret_12m > -10), 4.0)
    ret_score = ret_score.where(~(ret_12m > 0), 8.0)
    ret_score = ret_score.where(~(ret_12m > 10), 12.0)
    ret_score = ret_score.where(~(ret_12m > 25), 16.0)
    ret_score = ret_score.where(~(ret_12m > 50), 20.0)

    # ---- 2. ADX Trend Strength (20 pts) ----
    adx_val = _adx(high, low, close, 14)
    di_plus, di_minus = _dmi(high, low, close, 14)
    di_bullish = di_plus > di_minus

    adx_score = pd.Series(0.0, index=close.index)
    adx_score = adx_score.where(~(adx_val > 15), 5.0)
    adx_score = adx_score.where(~((adx_val > 20) & di_bullish), 10.0)
    adx_score = adx_score.where(~((adx_val > 25) & di_bullish), 15.0)
    adx_score = adx_score.where(~((adx_val > 30) & di_bullish), 20.0)

    # ---- 3. RSI Momentum Zone (20 pts) ----
    rsi_val = U.rsi(close, 14)
    rsi_score = pd.Series(0.0, index=close.index)
    # Constructive zone: 40-70
    rsi_score = rsi_score.where(~(rsi_val > 30), 5.0)
    rsi_score = rsi_score.where(~(rsi_val > 40), 10.0)
    rsi_score = rsi_score.where(~(rsi_val > 50), 15.0)
    rsi_score = rsi_score.where(~((rsi_val >= 50) & (rsi_val <= 70)), 20.0)
    # Overbought penalty
    rsi_score = rsi_score.where(~(rsi_val > 80), 10.0)

    # ---- 4. Volume Confirmation (20 pts) ----
    v5 = U.sma(volume, 5)
    v20 = U.sma(volume, 20)
    vol_ratio = (v5 / v20.replace(0.0, np.nan)).fillna(1.0)
    vol_score = pd.Series(0.0, index=close.index)
    vol_score = vol_score.where(~(vol_ratio > 0.7), 5.0)
    vol_score = vol_score.where(~(vol_ratio > 0.9), 10.0)
    vol_score = vol_score.where(~(vol_ratio > 1.0), 15.0)
    vol_score = vol_score.where(~(vol_ratio > 1.2), 20.0)

    # ---- 5. MA Structure (20 pts) ----
    ema20 = U.ema(close, 20)
    ema50 = U.ema(close, 50)
    ema150 = U.ema(close, 150)
    ema200 = U.ema(close, 200)
    sma50 = U.sma(close, 50)

    above_20 = close > ema20
    above_50 = close > ema50
    above_150 = close > ema150
    above_200 = close > ema200
    ma_stack = (ema20 > ema50) & (ema50 > ema150) & (ema150 > ema200)
    sma50_rising = sma50 > sma50.shift(5)

    ma_score = pd.Series(0.0, index=close.index)
    ma_score = ma_score + above_20.astype(float) * 4.0
    ma_score = ma_score + above_50.astype(float) * 4.0
    ma_score = ma_score + above_150.astype(float) * 3.0
    ma_score = ma_score + above_200.astype(float) * 3.0
    ma_score = ma_score + ma_stack.astype(float) * 3.0
    ma_score = ma_score + sma50_rising.astype(float) * 3.0
    ma_score = ma_score.clip(upper=20.0)

    momentum_composite = (ret_score + adx_score + rsi_score + vol_score + ma_score).clip(lower=0.0, upper=100.0)

    # ---- FIP Path Quality (0-100) ----
    daily_ret = close.pct_change()
    lookback = 252

    pct_positive = (daily_ret > 0).astype(float).rolling(lookback, min_periods=lookback).mean()
    pct_negative = (daily_ret < 0).astype(float).rolling(lookback, min_periods=lookback).mean()
    cum_ret_sign = np.sign((close / close.shift(lookback) - 1.0).fillna(0.0))

    fip_raw = (pct_negative - pct_positive) * cum_ret_sign

    # Map FIP to 0-100 quality score
    # FIP < -0.10 → SMOOTH (high quality) → 100
    # FIP -0.10 to 0.00 → MODERATE → 60-90
    # FIP > 0.00 → JUMPY (fragile) → 0-50
    fip_quality = pd.Series(50.0, index=close.index)
    fip_quality = fip_quality.where(~(fip_raw > 0.10), 10.0)
    fip_quality = fip_quality.where(~((fip_raw > 0.0) & (fip_raw <= 0.10)), 30.0)
    fip_quality = fip_quality.where(~((fip_raw >= -0.05) & (fip_raw <= 0.0)), 60.0)
    fip_quality = fip_quality.where(~((fip_raw >= -0.10) & (fip_raw < -0.05)), 80.0)
    fip_quality = fip_quality.where(~(fip_raw < -0.10), 100.0)

    # 5-day spike penalty
    abs_ret = daily_ret.abs()
    max_5d_move = abs_ret.rolling(5, min_periods=1).max()
    spike_penalty = (max_5d_move > 0.08).astype(float) * 30.0
    fip_quality = (fip_quality - spike_penalty).clip(lower=0.0, upper=100.0)

    fip_raw_base, fip_quality_base = fip_raw.copy(), fip_quality.copy()      # shadow v2 starts from these (before the live last-bar override)

    # ---- DSG-20: Prior spike exclusion (last bar only) ----
    fip_spike_excluded = pd.Series(False, index=close.index)
    fip_window_effective = pd.Series(252, index=close.index, dtype=int)

    if n >= lookback:
        spike_found, spike_peak_bar, excl_start, excl_end = _detect_prior_spike(close)
        if spike_found and spike_peak_bar is not None and excl_start is not None and excl_end is not None:
            last_idx = close.index[-1]
            fip_spike_excluded.iloc[-1] = True

            window_returns = daily_ret.iloc[-lookback:]
            included = [
                window_returns.iloc[j]
                for j in range(len(window_returns))
                if not (excl_start <= j <= excl_end)
            ]
            eff_n = len(included)
            fip_window_effective.iloc[-1] = eff_n

            if eff_n > 0:
                pp = sum(1 for r in included if r > 0) / eff_n
                pn = sum(1 for r in included if r < 0) / eff_n
                cum = sum(included)
                msign = 1.0 if cum > 0 else -1.0
                raw_excl = (pn - pp) * msign
                fip_excl = _fip_step_score(raw_excl)

                last_5 = daily_ret.iloc[-5:]
                if last_5.abs().max() > 0.08:
                    fip_excl = max(0.0, fip_excl - 30.0)

                fip_quality.iloc[-1] = fip_excl
                fip_raw.iloc[-1] = raw_excl

    # ---- Pipeline Rank composite ----
    pipe_rank = (momentum_composite * 0.70 + fip_quality * 0.30).clip(lower=0.0, upper=100.0)

    # Warmup: need 252 bars for FIP + 231 for 12m return
    warm = close.shift(231).notna() & pct_positive.notna()
    pipe_rank = pipe_rank.where(warm, np.nan)
    momentum_composite = momentum_composite.where(warm, np.nan)
    fip_quality = fip_quality.where(warm, np.nan)

    # Classification tier
    tier = pd.Series("D-SKIP", index=close.index)
    tier = tier.where(~(pipe_rank >= 45), "C-WATCH")
    tier = tier.where(~(pipe_rank >= 60), "B-STRONG")
    tier = tier.where(~(pipe_rank >= 75), "A-TIER")
    tier = tier.where(pipe_rank.notna(), np.nan)

    # ================= SHADOW v2 (research-review items 4, 5, 6; live fields above are untouched) =================
    # 4. 12-month return with the real skip-month: close[t-21] / close[t-252] - 1 (the live line uses close / close.shift(231): no skip).
    ret_12m_v2 = (close.shift(21) / close.shift(252).replace(0.0, np.nan) - 1.0) * 100.0
    ret_score_v2 = pd.Series(0.0, index=close.index)
    ret_score_v2 = ret_score_v2.where(~(ret_12m_v2 > -10), 4.0)
    ret_score_v2 = ret_score_v2.where(~(ret_12m_v2 > 0), 8.0)
    ret_score_v2 = ret_score_v2.where(~(ret_12m_v2 > 10), 12.0)
    ret_score_v2 = ret_score_v2.where(~(ret_12m_v2 > 25), 16.0)
    ret_score_v2 = ret_score_v2.where(~(ret_12m_v2 > 50), 20.0)
    # 5. ADX: every band requires DI+ > DI- (the live first band credits 5 points to a DOWNtrend).
    adx_score_v2 = pd.Series(0.0, index=close.index)
    adx_score_v2 = adx_score_v2.where(~((adx_val > 15) & di_bullish), 5.0)
    adx_score_v2 = adx_score_v2.where(~((adx_val > 20) & di_bullish), 10.0)
    adx_score_v2 = adx_score_v2.where(~((adx_val > 25) & di_bullish), 15.0)
    adx_score_v2 = adx_score_v2.where(~((adx_val > 30) & di_bullish), 20.0)
    momentum_composite_v2 = (ret_score_v2 + adx_score_v2 + rsi_score + vol_score + ma_score).clip(lower=0.0, upper=100.0)
    # 6. FIP: spike exclusion as-of every bar, one sign rule.
    fip_raw_v2 = fip_raw_base.copy()
    fip_quality_v2 = fip_quality_base.copy()
    ex_v2, eff_v2, raw_ex_v2, q_ex_v2 = _fip_spike_asof(close, daily_ret, lookback)
    fip_spike_excluded_v2 = pd.Series(ex_v2, index=close.index)
    fip_window_effective_v2 = pd.Series(eff_v2, index=close.index, dtype=int)
    fip_raw_v2 = fip_raw_v2.where(~fip_spike_excluded_v2, pd.Series(raw_ex_v2, index=close.index))
    fip_quality_v2 = fip_quality_v2.where(~fip_spike_excluded_v2, pd.Series(q_ex_v2, index=close.index))
    pipe_rank_v2 = (momentum_composite_v2 * 0.70 + fip_quality_v2 * 0.30).clip(lower=0.0, upper=100.0)
    warm_v2 = close.shift(252).notna() & pct_positive.notna()
    pipe_rank_v2 = pipe_rank_v2.where(warm_v2, np.nan)
    momentum_composite_v2 = momentum_composite_v2.where(warm_v2, np.nan)
    fip_quality_v2 = fip_quality_v2.where(warm_v2, np.nan)
    tier_v2 = pd.Series("D-SKIP", index=close.index)
    tier_v2 = tier_v2.where(~(pipe_rank_v2 >= 45), "C-WATCH")
    tier_v2 = tier_v2.where(~(pipe_rank_v2 >= 60), "B-STRONG")
    tier_v2 = tier_v2.where(~(pipe_rank_v2 >= 75), "A-TIER")
    tier_v2 = tier_v2.where(pipe_rank_v2.notna(), np.nan)

    return pd.DataFrame({
        "date": d["date"],
        "ret_12m_pct_v2": ret_12m_v2,
        "ret_12m_score_v2": ret_score_v2,
        "adx_score_v2": adx_score_v2,
        "momentum_composite_v2": momentum_composite_v2,
        "fip_quality_v2": fip_quality_v2,
        "fip_raw_v2": fip_raw_v2,
        "fip_spike_excluded_v2": fip_spike_excluded_v2,
        "fip_window_effective_v2": fip_window_effective_v2,
        "pipe_rank_v2": pipe_rank_v2,
        "pipe_tier_v2": tier_v2,
        "pipe_rank": pipe_rank,
        "pipe_tier": tier,
        "momentum_composite": momentum_composite,
        "fip_quality": fip_quality,
        "fip_raw": fip_raw,
        "fip_spike_excluded": fip_spike_excluded,
        "fip_window_effective": fip_window_effective,
        "ret_12m_score": ret_score,
        "adx_score": adx_score,
        "rsi_score": rsi_score,
        "vol_score": vol_score,
        "ma_score": ma_score,
    })


def _dmi(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> tuple[pd.Series, pd.Series]:
    """Directional Movement Index: returns (DI+, DI-)."""
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    atr_val = U.atr(high, low, close, n)
    smoothed_plus = U.wilder_rma(plus_dm, n)
    smoothed_minus = U.wilder_rma(minus_dm, n)
    di_plus = (smoothed_plus / atr_val.replace(0.0, np.nan) * 100.0).fillna(0.0)
    di_minus = (smoothed_minus / atr_val.replace(0.0, np.nan) * 100.0).fillna(0.0)
    return di_plus, di_minus


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Average Directional Index."""
    di_plus, di_minus = _dmi(high, low, close, n)
    dx = ((di_plus - di_minus).abs() / (di_plus + di_minus).replace(0.0, np.nan) * 100.0).fillna(0.0)
    return U.wilder_rma(dx, n)
