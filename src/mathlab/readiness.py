"""AQE Momentum Intelligence — per-ticker momentum state for new + held positions.

Classifies each ticker's momentum lifecycle state from observable daily conditions.
Same logic for watchlist names (is this coiling toward a trigger?) and held positions
(is this pullback healthy or is the trend broken?).

States (from most to least constructive):
  HIGH_CONVICTION  — volume expansion + trend aligned + close quality = go signal
  BUILDING         — vol contracting, MAs stacking, higher closes accumulating
  PULLBACK_HEALTHY — price pulling back within intact trend (MAs ordered, vol quiet)
  COILING          — tight ranges + low volume, consolidating = spring loading
  STALLING         — trend intact but momentum fading (lower closes, vol flat)
  BREAKING_DOWN    — MAs crossing over, closing below structure, vol expanding down

Each state is defined by specific, testable conditions — not a blended score.
The backtest proved vol_contraction (+4.4pp edge) and ma_stack (+1.4pp) are the
only EOD conditions that predict forward outcomes. The states are built from those
plus trend structure (higher lows, MA ordering) and volume character.

Additionally computes a conviction score (0-100) within each state for ranking —
so "BUILDING at 78" sorts above "BUILDING at 55" on the daily list.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ────────────────────────────────────────────────────────────────────────────
# State definitions
# ────────────────────────────────────────────────────────────────────────────
STATES = [
    "HIGH_CONVICTION",
    "BUILDING",
    "PULLBACK_HEALTHY",
    "COILING",
    "STALLING",
    "BREAKING_DOWN",
]

# State ordering for ranking (lower = more constructive)
STATE_RANK = {s: i for i, s in enumerate(STATES)}

# ────────────────────────────────────────────────────────────────────────────
# Configurable thresholds — tunable via backtest
# ────────────────────────────────────────────────────────────────────────────
VOL_CONTRACT_THRESH = 0.70       # 3d avg vol / 20d avg vol < this = contracting
VOL_EXPAND_THRESH = 1.50         # today vol / base avg vol > this = expanding
RANGE_CONTRACT_THRESH = 0.65     # 3d avg range / ATR14 < this = tight
CIR_STRONG = 0.60                # close-in-range > this = strong close
CIR_WEAK = 0.35                  # close-in-range < this = weak close
HIGHER_LOW_LOOKBACK = 5          # sessions to check for higher lows
CLOSE_TREND_LOOKBACK = 5         # sessions to check close trend
MA_NEAR_PCT = 0.03               # within 3% of MA = "near"
FAILED_BO_RANGE_MULT = 1.5       # range > this * ATR = expansion bar
FAILED_BO_CIR_THRESH = 0.30      # CIR below this on expansion = failed BO


@dataclass
class TickerState:
    """Per-ticker persistent state across days."""
    vol_contract_days: int = 0    # consecutive days of vol contraction
    trend_up_days: int = 0        # consecutive days of higher closes
    pullback_days: int = 0        # consecutive days pulling back within trend


def compute_momentum_series(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    op: np.ndarray,
    vol: np.ndarray,
) -> list[dict]:
    """Classify daily momentum state for a ticker's full bar history.

    Inputs are aligned float64 arrays (ascending date order).
    Returns a list of dicts, one per bar (after warmup).
    """
    n = len(cl)
    if n < 50:
        return []

    state = TickerState()
    results: list[dict] = []

    for i in range(20, n):
        today_c = float(cl[i])
        today_h = float(hi[i])
        today_l = float(lo[i])
        today_o = float(op[i])
        today_v = float(vol[i])
        today_range = today_h - today_l

        # ── ATR14 ──
        trs = []
        for j in range(max(1, i - 13), i + 1):
            h, l, pc = float(hi[j]), float(lo[j]), float(cl[j - 1])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = float(np.mean(trs)) if trs else 1.0
        if atr14 <= 0:
            atr14 = 1.0

        # ── MAs ──
        ma10 = float(np.mean(cl[max(0, i - 9):i + 1]))
        ma20 = float(np.mean(cl[max(0, i - 19):i + 1]))
        ma50 = float(np.mean(cl[max(0, i - 49):i + 1]))

        # ── Volume conditions ──
        avg_vol_20 = float(np.mean(vol[max(0, i - 19):i + 1]))
        recent_vol_3d = float(np.mean(vol[max(0, i - 2):i + 1]))
        vol_ratio_3d = recent_vol_3d / avg_vol_20 if avg_vol_20 > 0 else 1.0
        vol_contracting = vol_ratio_3d < VOL_CONTRACT_THRESH

        # Volume expansion relative to recent base (last 10 non-today bars)
        base_vol_slice = vol[max(0, i - 10):i]
        base_avg_vol = float(np.mean(base_vol_slice)) if len(base_vol_slice) > 0 else avg_vol_20
        vol_expansion = today_v / base_avg_vol if base_avg_vol > 0 else 1.0
        vol_expanding_up = (vol_expansion > VOL_EXPAND_THRESH
                            and today_c > today_o)

        # ── Range conditions ──
        recent_ranges = hi[max(0, i - 2):i + 1] - lo[max(0, i - 2):i + 1]
        range_ratio = float(np.mean(recent_ranges)) / atr14 if atr14 > 0 else 1.0
        range_tight = range_ratio < RANGE_CONTRACT_THRESH

        # ── Close quality ──
        cir = (today_c - today_l) / today_range if today_range > 0 else 0.5
        close_strong = cir > CIR_STRONG
        close_weak = cir < CIR_WEAK

        # ── MA stack (trend structure) ──
        ma10_above_20 = ma10 > ma20
        ma20_above_50 = ma20 > ma50
        mas_stacked = ma10_above_20 and ma20_above_50
        price_above_ma10 = today_c > ma10
        price_above_ma20 = today_c > ma20
        price_above_ma50 = today_c > ma50

        price_near_ma10 = abs(today_c - ma10) / ma10 < MA_NEAR_PCT if ma10 > 0 else False
        price_near_ma20 = abs(today_c - ma20) / ma20 < MA_NEAR_PCT if ma20 > 0 else False

        # ── Higher lows (trend health) ──
        hl_count = 0
        lookback_start = max(0, i - HIGHER_LOW_LOOKBACK)
        for j in range(lookback_start + 1, i + 1):
            if float(lo[j]) >= float(lo[j - 1]) - atr14 * 0.1:
                hl_count += 1
        higher_lows = hl_count >= (HIGHER_LOW_LOOKBACK - 1)

        # ── Close trend (momentum direction) ──
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

        # ── Failed breakout ──
        is_failed_bo = (
            today_range > FAILED_BO_RANGE_MULT * atr14
            and cir < FAILED_BO_CIR_THRESH
            and today_c < today_o
        )

        # ── Update counters ──
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

        # ────────────────────────────────────────────────────────────────
        # STATE CLASSIFICATION — ordered from most to least constructive
        # Each state has specific, testable conditions.
        # ────────────────────────────────────────────────────────────────

        if (vol_expanding_up and mas_stacked and close_strong
                and price_above_ma10 and not is_failed_bo):
            momentum_state = "HIGH_CONVICTION"

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

        # Override: failed breakout always = BREAKING_DOWN
        if is_failed_bo:
            momentum_state = "BREAKING_DOWN"

        # ────────────────────────────────────────────────────────────────
        # CONVICTION SCORE (0-100) within the state — for ranking
        # Built only from conditions the backtest proved matter:
        # vol_contraction, ma_stack, vol_expansion, close quality
        # ────────────────────────────────────────────────────────────────

        conviction = 0.0

        # Volume contraction depth (0-30) — the strongest predictor
        if vol_contracting:
            depth = max(0.0, 1.0 - vol_ratio_3d) / (1.0 - VOL_CONTRACT_THRESH)
            conviction += min(30.0, depth * 30.0)
        conviction += min(10.0, state.vol_contract_days * 2.0)

        # MA alignment quality (0-25)
        if mas_stacked:
            conviction += 15.0
        elif ma10_above_20:
            conviction += 8.0
        elif ma20_above_50:
            conviction += 4.0
        if price_above_ma10 and price_near_ma10:
            conviction += 10.0
        elif price_above_ma10:
            conviction += 5.0

        # Close quality (0-15)
        if close_strong:
            conviction += 15.0
        elif cir > 0.5:
            conviction += 8.0

        # Volume expansion on up day (0-20) — trigger confirmation
        if vol_expanding_up:
            expansion_score = min(1.0, (vol_expansion - 1.0) / 2.0)
            conviction += expansion_score * 20.0

        # Trend consistency bonus (0-10)
        if state.trend_up_days >= 3:
            conviction += min(10.0, state.trend_up_days * 2.0)

        # Higher lows bonus (0-10)
        if higher_lows and price_above_ma20:
            conviction += 10.0

        # Penalties
        if close_weak:
            conviction -= 15.0
        if is_failed_bo:
            conviction -= 30.0
        if not price_above_ma50:
            conviction -= 20.0

        conviction = max(0.0, min(100.0, conviction))

        results.append({
            "idx": i,
            "state": momentum_state,
            "conviction": round(conviction, 1),
            "conditions": {
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
        })

    return results


def momentum_for_bars(bars_df) -> list[dict]:
    """Convenience: compute momentum states from a DataFrame with OHLCV columns."""
    import pandas as pd

    if bars_df.empty or len(bars_df) < 50:
        return []

    bars = bars_df.sort_values("date").reset_index(drop=True)
    hi = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    cl = bars["close"].to_numpy(dtype=float)
    op = bars["open"].to_numpy(dtype=float)
    v = bars["volume"].to_numpy(dtype=float)
    dates = bars["date"].tolist()

    raw = compute_momentum_series(hi, lo, cl, op, v)

    for r in raw:
        r["date"] = dates[r["idx"]]
        del r["idx"]

    return raw


def classify_trajectory(states_5d: list[str]) -> str:
    """Trajectory from last 5 days of states."""
    if len(states_5d) < 3:
        return "INSUFFICIENT"
    ranks = [STATE_RANK.get(s, 5) for s in states_5d]
    last3 = ranks[-3:]
    if last3[0] > last3[1] > last3[2]:
        return "IMPROVING"
    if last3[0] < last3[1] < last3[2]:
        return "DETERIORATING"
    if max(ranks) - min(ranks) <= 1:
        return "STABLE"
    return "MIXED"
