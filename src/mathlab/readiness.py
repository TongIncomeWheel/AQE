"""AQE Momentum Intelligence — dual-state classifier for new + held positions.

TWO outputs per ticker-day:
  MOMENTUM STATE — where is this ticker in its momentum lifecycle?
    ACCELERATING / BUILDING / PULLBACK_HEALTHY / COILING / STALLING / BREAKING_DOWN
  READINESS STATE — how close to an actionable trigger?
    READY_NOW / SETTING_UP / WAIT / STAND_DOWN

Inputs are split into two groups:
  A-inputs (raw daily bar conditions): vol contraction, MA stack, close quality,
    volume expansion, higher lows, range contraction, failed breakout.
    These determine the momentum state.
  C-inputs (AQE engine score trajectories computed from bars): Elder Impulse
    (EMA13 + MACD histogram), ADX, RSI — and their 3-day direction.
    These combine with momentum state to determine readiness.

The backtest proves whether C-inputs add predictive power on top of A-inputs.
If they don't, readiness collapses to momentum state alone and C is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────────────
# State definitions
# ────────────────────────────────────────────────────────────────────────────
MOMENTUM_STATES = [
    "ACCELERATING",
    "BUILDING",
    "PULLBACK_HEALTHY",
    "COILING",
    "STALLING",
    "BREAKING_DOWN",
]

READINESS_STATES = [
    "READY_NOW",
    "SETTING_UP",
    "WAIT",
    "STAND_DOWN",
]

MOMENTUM_RANK = {s: i for i, s in enumerate(MOMENTUM_STATES)}
READINESS_RANK = {s: i for i, s in enumerate(READINESS_STATES)}

# ────────────────────────────────────────────────────────────────────────────
# A-input thresholds (tunable via backtest)
# ────────────────────────────────────────────────────────────────────────────
VOL_CONTRACT_THRESH = 0.70
VOL_EXPAND_THRESH = 1.50
RANGE_CONTRACT_THRESH = 0.65
CIR_STRONG = 0.60
CIR_WEAK = 0.35
HIGHER_LOW_LOOKBACK = 5
CLOSE_TREND_LOOKBACK = 5
MA_NEAR_PCT = 0.03
FAILED_BO_RANGE_MULT = 1.5
FAILED_BO_CIR_THRESH = 0.30

# C-input thresholds
ELDER_GREEN_THRESH = 7       # elder_score >= this = strong impulse
ELDER_RED_THRESH = 3         # elder_score <= this = bearish impulse
ADX_TRENDING_THRESH = 20     # ADX > this = trending (not range-bound)
RSI_BULL_THRESH = 50         # RSI above this = bullish bias


@dataclass
class TickerState:
    vol_contract_days: int = 0
    trend_up_days: int = 0
    pullback_days: int = 0


# ────────────────────────────────────────────────────────────────────────────
# C-input computation (Elder, ADX, RSI from raw bars)
# ────────────────────────────────────────────────────────────────────────────

def _compute_c_inputs(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
                      ) -> dict[str, np.ndarray]:
    """Pre-compute C-inputs as numpy arrays aligned to the bar arrays."""
    n = len(cl)
    close_s = pd.Series(cl, dtype=float)
    high_s = pd.Series(hi, dtype=float)
    low_s = pd.Series(lo, dtype=float)

    # ── Elder Impulse (EMA13 + MACD histogram) ──
    ema13 = close_s.ewm(span=13, adjust=False).mean()
    ema13_prev = ema13.shift(1)
    ema_rising = ema13 > ema13_prev

    macd_fast = close_s.ewm(span=12, adjust=False).mean()
    macd_slow = close_s.ewm(span=26, adjust=False).mean()
    macd_line = macd_fast - macd_slow
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    hist_prev = macd_hist.shift(1)
    hist_rising = macd_hist > hist_prev

    impulse_green = ema_rising & hist_rising
    impulse_red = (~ema_rising) & (~hist_rising)

    # Elder score (0-10) matching elder.py logic
    ema13_prev3 = ema13.shift(3)
    ema_slope = ((ema13 - ema13_prev3) / ema13.replace(0.0, np.nan) * 100.0).fillna(0.0)

    state_score = pd.Series(0.0, index=close_s.index)
    state_score = state_score.where(~impulse_green, 4.0)
    state_score = state_score.where(~(~impulse_green & ~impulse_red), 2.0)

    slope_score = pd.Series(0.0, index=close_s.index)
    slope_score = slope_score.where(~(ema_slope > 0.0), 1.0)
    slope_score = slope_score.where(~(ema_slope > 0.3), 2.0)
    slope_score = slope_score.where(~(ema_slope > 1.0), 3.0)

    hist_accel = macd_hist - hist_prev
    hist_score = pd.Series(0.0, index=close_s.index)
    hist_score = hist_score.where(~((macd_hist > 0) & ~(hist_accel > 0)), 2.0)
    hist_score = hist_score.where(~(~(macd_hist > 0) & (hist_accel > 0)), 1.0)
    hist_score = hist_score.where(~((macd_hist > 0) & (hist_accel > 0)), 3.0)

    elder_score = (state_score + slope_score + hist_score).clip(0.0, 10.0)

    # ── ADX (14-period, Wilder smoothing) ──
    prev_hi = high_s.shift(1)
    prev_lo = low_s.shift(1)
    prev_cl = close_s.shift(1)

    plus_dm = (high_s - prev_hi).clip(lower=0.0)
    minus_dm = (prev_lo - low_s).clip(lower=0.0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    tr = pd.concat([
        (high_s - low_s).abs(),
        (high_s - prev_cl).abs(),
        (low_s - prev_cl).abs(),
    ], axis=1).max(axis=1)
    tr.iloc[0] = abs(float(hi[0]) - float(lo[0]))

    atr14 = _wilder_rma_arr(tr.to_numpy(), 14)
    plus_dm_smooth = _wilder_rma_arr(plus_dm.to_numpy(), 14)
    minus_dm_smooth = _wilder_rma_arr(minus_dm.to_numpy(), 14)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = np.where(atr14 > 0, 100.0 * plus_dm_smooth / atr14, 0.0)
        minus_di = np.where(atr14 > 0, 100.0 * minus_dm_smooth / atr14, 0.0)
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

    adx = _wilder_rma_arr(dx, 14)

    # ── RSI (14-period, Wilder smoothing) ──
    delta = np.diff(cl, prepend=cl[0])
    gain = np.clip(delta, 0, None)
    loss = np.clip(-delta, 0, None)
    avg_gain = _wilder_rma_arr(gain, 14)
    avg_loss = _wilder_rma_arr(loss, 14)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
    rsi_arr = 100.0 - 100.0 / (1.0 + rs)

    return {
        "elder_score": elder_score.to_numpy(),
        "impulse_green": impulse_green.to_numpy(),
        "impulse_red": impulse_red.to_numpy(),
        "adx": adx,
        "rsi": rsi_arr,
    }


def _wilder_rma_arr(arr: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing (RMA) on a numpy array. Seeded with SMA of first n bars."""
    out = np.full_like(arr, 0.0, dtype=float)
    if len(arr) < n:
        return out
    out[n - 1] = np.nanmean(arr[:n])
    alpha = 1.0 / n
    for i in range(n, len(arr)):
        v = arr[i]
        if np.isnan(v):
            out[i] = out[i - 1]
        else:
            out[i] = alpha * v + (1.0 - alpha) * out[i - 1]
    return out


# ────────────────────────────────────────────────────────────────────────────
# Main computation
# ────────────────────────────────────────────────────────────────────────────

def compute_dual_state_series(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    op: np.ndarray,
    vol: np.ndarray,
) -> list[dict]:
    """Classify momentum + readiness state for a ticker's full bar history.

    Returns a list of dicts (one per bar after warmup), each with:
      momentum_state, readiness_state, conviction, conditions, c_inputs
    """
    n = len(cl)
    if n < 50:
        return []

    c = _compute_c_inputs(hi, lo, cl)
    state = TickerState()
    results: list[dict] = []

    for i in range(30, n):  # 30-bar warmup (ADX needs 28, MACD needs 26+9)
        today_c = float(cl[i])
        today_h = float(hi[i])
        today_l = float(lo[i])
        today_o = float(op[i])
        today_v = float(vol[i])
        today_range = today_h - today_l

        # ── A-inputs ──

        # ATR14
        trs = []
        for j in range(max(1, i - 13), i + 1):
            h, l, pc = float(hi[j]), float(lo[j]), float(cl[j - 1])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = float(np.mean(trs)) if trs else 1.0
        if atr14 <= 0:
            atr14 = 1.0

        # MAs
        ma10 = float(np.mean(cl[max(0, i - 9):i + 1]))
        ma20 = float(np.mean(cl[max(0, i - 19):i + 1]))
        ma50 = float(np.mean(cl[max(0, i - 49):i + 1]))

        # Volume conditions
        avg_vol_20 = float(np.mean(vol[max(0, i - 19):i + 1]))
        recent_vol_3d = float(np.mean(vol[max(0, i - 2):i + 1]))
        vol_ratio_3d = recent_vol_3d / avg_vol_20 if avg_vol_20 > 0 else 1.0
        vol_contracting = vol_ratio_3d < VOL_CONTRACT_THRESH

        base_vol_slice = vol[max(0, i - 10):i]
        base_avg_vol = float(np.mean(base_vol_slice)) if len(base_vol_slice) > 0 else avg_vol_20
        vol_expansion = today_v / base_avg_vol if base_avg_vol > 0 else 1.0
        vol_expanding_up = vol_expansion > VOL_EXPAND_THRESH and today_c > today_o

        # Range conditions
        recent_ranges = hi[max(0, i - 2):i + 1] - lo[max(0, i - 2):i + 1]
        range_ratio = float(np.mean(recent_ranges)) / atr14 if atr14 > 0 else 1.0
        range_tight = range_ratio < RANGE_CONTRACT_THRESH

        # Close quality
        cir = (today_c - today_l) / today_range if today_range > 0 else 0.5
        close_strong = cir > CIR_STRONG
        close_weak = cir < CIR_WEAK

        # MA stack
        ma10_above_20 = ma10 > ma20
        ma20_above_50 = ma20 > ma50
        mas_stacked = ma10_above_20 and ma20_above_50
        price_above_ma10 = today_c > ma10
        price_above_ma20 = today_c > ma20
        price_above_ma50 = today_c > ma50

        price_near_ma10 = abs(today_c - ma10) / ma10 < MA_NEAR_PCT if ma10 > 0 else False
        price_near_ma20 = abs(today_c - ma20) / ma20 < MA_NEAR_PCT if ma20 > 0 else False

        # Higher lows
        hl_count = 0
        lookback_start = max(0, i - HIGHER_LOW_LOOKBACK)
        for j in range(lookback_start + 1, i + 1):
            if float(lo[j]) >= float(lo[j - 1]) - atr14 * 0.1:
                hl_count += 1
        higher_lows = hl_count >= (HIGHER_LOW_LOOKBACK - 1)

        # Close trend
        ct_start = max(0, i - CLOSE_TREND_LOOKBACK)
        closes_window = cl[ct_start:i + 1]
        if len(closes_window) >= 3:
            up_closes = sum(1 for j in range(1, len(closes_window))
                           if float(closes_window[j]) > float(closes_window[j - 1]))
            close_trend_up = up_closes >= len(closes_window) * 0.6
            close_trend_down = up_closes <= len(closes_window) * 0.3
        else:
            close_trend_up = False
            close_trend_down = False

        # Failed breakout
        is_failed_bo = (
            today_range > FAILED_BO_RANGE_MULT * atr14
            and cir < FAILED_BO_CIR_THRESH
            and today_c < today_o
        )

        # Update counters
        if vol_contracting:
            state.vol_contract_days += 1
        else:
            state.vol_contract_days = 0

        if close_trend_up and price_above_ma20:
            state.trend_up_days += 1
        else:
            state.trend_up_days = 0

        if (mas_stacked and not price_above_ma10
                and price_above_ma20 and not close_trend_down):
            state.pullback_days += 1
        else:
            state.pullback_days = 0

        # ── C-inputs (pre-computed, indexed) ──
        elder_val = float(c["elder_score"][i]) if not np.isnan(c["elder_score"][i]) else 5.0
        elder_green = bool(c["impulse_green"][i])
        elder_red = bool(c["impulse_red"][i])
        adx_val = float(c["adx"][i])
        rsi_val = float(c["rsi"][i])

        # C-input trajectories (3-day direction)
        j3 = max(0, i - 3)
        elder_prev3 = float(c["elder_score"][j3]) if not np.isnan(c["elder_score"][j3]) else 5.0
        elder_rising = elder_val > elder_prev3
        adx_prev3 = float(c["adx"][j3])
        adx_rising = adx_val > adx_prev3
        rsi_prev3 = float(c["rsi"][j3])
        rsi_rising = rsi_val > rsi_prev3

        elder_strong = elder_val >= ELDER_GREEN_THRESH
        elder_weak = elder_val <= ELDER_RED_THRESH
        adx_trending = adx_val > ADX_TRENDING_THRESH
        rsi_bullish = rsi_val > RSI_BULL_THRESH

        # ────────────────────────────────────────────────────────────────
        # MOMENTUM STATE (A-inputs only)
        # ────────────────────────────────────────────────────────────────

        if (vol_expanding_up and mas_stacked and close_strong
                and price_above_ma10 and not is_failed_bo):
            momentum_state = "ACCELERATING"

        elif (mas_stacked and price_above_ma10 and close_trend_up
              and (vol_contracting or state.vol_contract_days >= 2)
              and not is_failed_bo):
            momentum_state = "BUILDING"

        elif (mas_stacked and price_above_ma20 and not price_above_ma10
              and higher_lows and not vol_expanding_up
              and not close_trend_down):
            momentum_state = "PULLBACK_HEALTHY"

        elif ((vol_contracting or state.vol_contract_days >= 3)
              and range_tight and price_above_ma50
              and not close_trend_down):
            momentum_state = "COILING"

        elif (price_above_ma20 and not close_trend_up
              and not vol_expanding_up and not range_tight):
            momentum_state = "STALLING"

        else:
            momentum_state = "BREAKING_DOWN"

        if is_failed_bo:
            momentum_state = "BREAKING_DOWN"

        # ────────────────────────────────────────────────────────────────
        # READINESS STATE (A + C combined)
        # ────────────────────────────────────────────────────────────────

        if is_failed_bo:
            readiness_state = "STAND_DOWN"

        elif (momentum_state in ("ACCELERATING", "BUILDING")
              and elder_green
              and (adx_trending or adx_rising)
              and not close_weak):
            readiness_state = "READY_NOW"

        elif (momentum_state == "COILING"
              and not elder_red
              and state.vol_contract_days >= 3
              and rsi_bullish):
            readiness_state = "READY_NOW"

        elif (momentum_state in ("BUILDING", "PULLBACK_HEALTHY", "COILING")
              and not elder_red
              and rsi_val > 40):
            readiness_state = "SETTING_UP"

        elif momentum_state == "BREAKING_DOWN":
            readiness_state = "STAND_DOWN"

        elif (elder_red and not adx_rising and rsi_val < 40):
            readiness_state = "STAND_DOWN"

        else:
            readiness_state = "WAIT"

        # ────────────────────────────────────────────────────────────────
        # CONVICTION SCORE (0-100) — for ranking within states
        # ────────────────────────────────────────────────────────────────

        conviction = 0.0

        # A-input contributions (60 pts max)
        if vol_contracting:
            depth = max(0.0, 1.0 - vol_ratio_3d) / (1.0 - VOL_CONTRACT_THRESH)
            conviction += min(20.0, depth * 20.0)
        conviction += min(10.0, state.vol_contract_days * 2.0)

        if mas_stacked:
            conviction += 10.0
        elif ma10_above_20:
            conviction += 5.0

        if close_strong:
            conviction += 10.0
        elif cir > 0.5:
            conviction += 5.0

        if vol_expanding_up:
            expansion_score = min(1.0, (vol_expansion - 1.0) / 2.0)
            conviction += expansion_score * 10.0

        # C-input contributions (40 pts max)
        if elder_strong:
            conviction += 15.0
        elif elder_val >= 5:
            conviction += 8.0
        elif elder_weak:
            conviction -= 10.0

        if elder_rising:
            conviction += 5.0

        if adx_trending:
            conviction += 10.0
        elif adx_val > 15:
            conviction += 5.0

        if rsi_bullish:
            conviction += 5.0

        if adx_rising and rsi_rising:
            conviction += 5.0

        # Penalties
        if close_weak:
            conviction -= 10.0
        if is_failed_bo:
            conviction -= 30.0
        if not price_above_ma50:
            conviction -= 15.0
        if elder_red and not adx_trending:
            conviction -= 10.0

        conviction = max(0.0, min(100.0, conviction))

        results.append({
            "idx": i,
            "momentum_state": momentum_state,
            "readiness_state": readiness_state,
            "conviction": round(conviction, 1),
            "a_conditions": {
                "vol_ratio_3d": round(vol_ratio_3d, 3),
                "vol_contracting": vol_contracting,
                "vol_contract_days": state.vol_contract_days,
                "vol_expansion": round(vol_expansion, 2),
                "vol_expanding_up": vol_expanding_up,
                "range_ratio": round(range_ratio, 3),
                "range_tight": range_tight,
                "cir": round(cir, 3),
                "close_strong": close_strong,
                "close_weak": close_weak,
                "mas_stacked": mas_stacked,
                "ma10_gt_20": ma10_above_20,
                "ma20_gt_50": ma20_above_50,
                "price_above_ma10": price_above_ma10,
                "price_above_ma20": price_above_ma20,
                "price_above_ma50": price_above_ma50,
                "higher_lows": higher_lows,
                "close_trend_up": close_trend_up,
                "close_trend_down": close_trend_down,
                "trend_up_days": state.trend_up_days,
                "failed_breakout": is_failed_bo,
            },
            "c_inputs": {
                "elder_score": round(elder_val, 1),
                "elder_green": elder_green,
                "elder_red": elder_red,
                "elder_rising": elder_rising,
                "adx": round(adx_val, 1),
                "adx_rising": adx_rising,
                "adx_trending": adx_trending,
                "rsi": round(rsi_val, 1),
                "rsi_bullish": rsi_bullish,
                "rsi_rising": rsi_rising,
            },
        })

    return results


def dual_state_for_bars(bars_df) -> list[dict]:
    """Compute dual states from a DataFrame with OHLCV columns."""
    if bars_df.empty or len(bars_df) < 50:
        return []

    bars = bars_df.sort_values("date").reset_index(drop=True)
    hi = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    cl = bars["close"].to_numpy(dtype=float)
    op = bars["open"].to_numpy(dtype=float)
    v = bars["volume"].to_numpy(dtype=float)
    dates = bars["date"].tolist()

    raw = compute_dual_state_series(hi, lo, cl, op, v)
    for r in raw:
        r["date"] = dates[r["idx"]]
        del r["idx"]
    return raw


def classify_trajectory(states_5d: list[str], rank_map: dict[str, int]) -> str:
    """Trajectory from last 5 days of states (works for either state type)."""
    if len(states_5d) < 3:
        return "INSUFFICIENT"
    ranks = [rank_map.get(s, len(rank_map)) for s in states_5d]
    last3 = ranks[-3:]
    if last3[0] > last3[1] > last3[2]:
        return "IMPROVING"
    if last3[0] < last3[1] < last3[2]:
        return "DETERIORATING"
    if max(ranks) - min(ranks) <= 1:
        return "STABLE"
    return "MIXED"


def momentum_trajectory(states_5d: list[str]) -> str:
    return classify_trajectory(states_5d, MOMENTUM_RANK)


def readiness_trajectory(states_5d: list[str]) -> str:
    return classify_trajectory(states_5d, READINESS_RANK)
