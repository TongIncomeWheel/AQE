"""AQE Readiness Score — progressive daily score (0–100) per ticker.

Tells the PM WHEN to enter, not just WHICH names have momentum.
Builds progressively over days as conditions accumulate. Carried as a
5-day array (like elder_5d). Handles both breakout and continuation entries.

Design principles:
  1. Progressive build via EMA smoothing (no choppy oscillation)
  2. Coil evidence persists via high-water marks (doesn't vanish on breakout day)
  3. Failed breakout detection halves coil memory (BROS Jun 22 case)
  4. Volume expansion ADDS to persisted coil evidence = score peaks on trigger

Components (weights are starting values — backtested for optimal config):
  1. Volume contraction evidence  (high-water mark, 0–W1)
  2. Range compression evidence   (high-water mark, 0–W2)
  3. VWAP positioning             (EMA smoothed,    0–W3)
  4. Structure proximity          (EMA smoothed,    0–W4)
  5. Close quality                (EMA smoothed,    0–W5)
  6. MA stack / trend quality     (daily,           0–W6)
  7. Volume expansion / trigger   (daily,           0–W7)
  8. Base length bonus            (daily,           0–W8)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ────────────────────────────────────────────────────────────────────────────
# Default weights (sum = 100). Tunable via backtest.
# ────────────────────────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "vol_coil": 18,
    "range_coil": 15,
    "vwap": 12,
    "proximity": 15,
    "close_quality": 10,
    "ma_stack": 10,
    "trigger": 15,
    "base_len": 5,
}

EMA_ALPHA = 0.35
COIL_DECAY = 0.02
COIL_FAILURE_RESET = 0.50
FAILED_BO_CIR_THRESH = 0.30
FAILED_BO_RANGE_MULT = 1.5
TRIGGER_VOL_MULT = 1.5
TRIGGER_CIR_THRESH = 0.55
PROXIMITY_ATR_RANGE = 3.0
BASE_EXPANSION_MULT = 2.0
BASE_LOOKBACK = 30
BASE_LEN_FULL = 10

STAGES = [
    (90, "TRIGGERED"),
    (75, "READY"),
    (60, "APPROACHING"),
    (40, "COIL_TIGHTENING"),
    (20, "BASE_FORMING"),
    (0, "MONITORING"),
]


def classify_stage(score: float) -> str:
    for threshold, name in STAGES:
        if score >= threshold:
            return name
    return "MONITORING"


def classify_trajectory(scores_5d: list[float]) -> str:
    if len(scores_5d) < 3:
        return "INSUFFICIENT"
    s = scores_5d
    last3 = s[-3:]
    if last3[0] < last3[1] < last3[2]:
        return "BUILDING"
    if last3[0] > last3[1] > last3[2]:
        return "DEGRADING"
    if max(s) - min(s) < 8:
        return "STABLE"
    return "CHOPPY"


# ────────────────────────────────────────────────────────────────────────────
# Per-ticker state (persists across days)
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class ReadinessState:
    best_vol_ratio: float = 1.0
    best_range_ratio: float = 1.0
    vwap_ema: float = 0.5
    prox_ema: float = 0.0
    close_ema: float = 0.5
    score_ema: float = 0.0
    base_sessions: int = 0

    def decay_coil(self):
        self.best_vol_ratio += (1.0 - self.best_vol_ratio) * COIL_DECAY
        self.best_range_ratio += (1.0 - self.best_range_ratio) * COIL_DECAY

    def reset_coil(self):
        self.best_vol_ratio += (1.0 - self.best_vol_ratio) * COIL_FAILURE_RESET
        self.best_range_ratio += (1.0 - self.best_range_ratio) * COIL_FAILURE_RESET

    def update_coil(self, vol_ratio: float, range_ratio: float):
        if vol_ratio < self.best_vol_ratio:
            self.best_vol_ratio = vol_ratio
        if range_ratio < self.best_range_ratio:
            self.best_range_ratio = range_ratio


# ────────────────────────────────────────────────────────────────────────────
# Core computation
# ────────────────────────────────────────────────────────────────────────────

def compute_readiness_series(
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    op: np.ndarray,
    vol: np.ndarray,
    weights: dict | None = None,
) -> list[dict]:
    """Compute daily readiness scores for a ticker's full bar history.

    Inputs are aligned arrays of float64 (ascending date order).
    Returns a list of dicts, one per bar (after warmup), with:
      score, stage, components dict, failed_breakout flag.
    """
    w = weights or DEFAULT_WEIGHTS
    n = len(cl)
    if n < 20:
        return []

    state = ReadinessState()
    results: list[dict] = []

    for i in range(14, n):
        lookback = min(i + 1, BASE_LOOKBACK)
        start = i - lookback + 1

        # ── ATR14 ──
        trs = []
        for j in range(max(1, i - 13), i + 1):
            h, l, pc = float(hi[j]), float(lo[j]), float(cl[j - 1])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = float(np.mean(trs)) if trs else 1.0
        if atr14 <= 0:
            atr14 = 1.0

        # ── Base detection ──
        base_start = start
        for j in range(i - 1, max(start, i - BASE_LOOKBACK) - 1, -1):
            if (float(hi[j]) - float(lo[j])) > BASE_EXPANSION_MULT * atr14:
                base_start = j + 1
                break

        base_start = max(base_start, 0)
        if base_start > i:
            base_start = max(0, i - 5)

        base_hi = hi[base_start:i + 1]
        base_lo = lo[base_start:i + 1]
        base_vol = vol[base_start:i + 1]
        base_cl = cl[base_start:i + 1]
        base_len = len(base_hi)

        # ── MAs ──
        ma10 = float(np.mean(cl[max(0, i - 9):i + 1]))
        ma20 = float(np.mean(cl[max(0, i - 19):i + 1]))
        i50 = max(0, i - 49)
        ma50 = float(np.mean(cl[i50:i + 1])) if i >= 19 else ma20

        today_c = float(cl[i])
        today_h = float(hi[i])
        today_l = float(lo[i])
        today_o = float(op[i])
        today_v = float(vol[i])
        today_range = today_h - today_l

        # VWAP proxy = typical price
        vwap_proxy = (today_h + today_l + today_c) / 3.0

        # ── Failed breakout detection ──
        cir = (today_c - today_l) / today_range if today_range > 0 else 0.5
        is_failed_bo = (
            today_range > FAILED_BO_RANGE_MULT * atr14
            and cir < FAILED_BO_CIR_THRESH
            and today_c < today_o
        )

        # ── Component 1: Volume contraction evidence ──
        avg_vol_20 = float(np.mean(vol[max(0, i - 19):i + 1]))
        if avg_vol_20 > 0:
            # 3-day average volume ratio
            recent_vol = vol[max(base_start, i - 2):i + 1]
            vol_ratio_3d = float(np.mean(recent_vol)) / avg_vol_20
        else:
            vol_ratio_3d = 1.0

        if is_failed_bo:
            state.reset_coil()
        else:
            state.update_coil(vol_ratio_3d, 0.0)
            state.decay_coil()

        vol_coil_raw = max(0.0, 1.0 - state.best_vol_ratio)
        vol_coil = vol_coil_raw * w["vol_coil"]

        # ── Component 2: Range compression evidence ──
        if atr14 > 0 and base_len >= 3:
            recent_ranges = hi[max(base_start, i - 2):i + 1] - lo[max(base_start, i - 2):i + 1]
            range_ratio_3d = float(np.mean(recent_ranges)) / atr14
        else:
            range_ratio_3d = 1.0

        if not is_failed_bo:
            if range_ratio_3d < state.best_range_ratio:
                state.best_range_ratio = range_ratio_3d

        range_coil_raw = max(0.0, 1.0 - state.best_range_ratio)
        range_coil = range_coil_raw * w["range_coil"]

        # ── Component 3: VWAP positioning ──
        vwap_above = 1.0 if today_c > vwap_proxy else 0.0
        state.vwap_ema = EMA_ALPHA * vwap_above + (1 - EMA_ALPHA) * state.vwap_ema
        vwap_score = state.vwap_ema * w["vwap"]

        # ── Component 4: Structure proximity ──
        base_high = float(np.max(base_hi)) if base_len > 0 else today_c
        targets = [base_high]
        if ma10 > ma20 > ma50 and today_c > ma20:
            targets.append(ma10)

        min_dist_atr = min(abs(today_c - t) / atr14 for t in targets)
        prox_raw = max(0.0, 1.0 - min_dist_atr / PROXIMITY_ATR_RANGE)
        state.prox_ema = EMA_ALPHA * prox_raw + (1 - EMA_ALPHA) * state.prox_ema
        prox_score = state.prox_ema * w["proximity"]

        # ── Component 5: Close quality ──
        state.close_ema = EMA_ALPHA * cir + (1 - EMA_ALPHA) * state.close_ema
        close_score = state.close_ema * w["close_quality"]

        # ── Component 6: MA stack / trend quality ──
        ma_stack_pts = 0.0
        if ma10 > ma20:
            ma_stack_pts += 3.0
        if ma20 > ma50:
            ma_stack_pts += 3.0
        if today_c > ma10 and abs(today_c - ma10) / ma10 < 0.03:
            ma_stack_pts += 4.0
        elif today_c > ma10:
            ma_stack_pts += 2.0
        ma_score = ma_stack_pts / 10.0 * w["ma_stack"]

        # ── Component 7: Volume expansion / trigger ──
        trigger_score = 0.0
        base_avg_vol = float(np.mean(base_vol[:-1])) if base_len > 1 else avg_vol_20
        if base_avg_vol > 0:
            vol_expansion = today_v / base_avg_vol
        else:
            vol_expansion = 1.0
        if (vol_expansion > TRIGGER_VOL_MULT
                and today_c > today_o
                and cir > TRIGGER_CIR_THRESH):
            trigger_score = min(1.0, (vol_expansion - 1.0) / 2.0) * w["trigger"]

        # ── Component 8: Base length bonus ──
        if today_range < FAILED_BO_RANGE_MULT * atr14:
            state.base_sessions += 1
        else:
            if is_failed_bo:
                state.base_sessions = max(0, state.base_sessions - 3)
        base_len_score = min(1.0, state.base_sessions / BASE_LEN_FULL) * w["base_len"]

        # ── Composite ──
        raw = (vol_coil + range_coil + vwap_score + prox_score
               + close_score + ma_score + trigger_score + base_len_score)
        raw = max(0.0, min(100.0, raw))

        # EMA smooth the final score
        state.score_ema = EMA_ALPHA * raw + (1 - EMA_ALPHA) * state.score_ema
        score = max(0.0, min(100.0, state.score_ema))

        results.append({
            "idx": i,
            "score": round(score, 1),
            "stage": classify_stage(score),
            "raw": round(raw, 1),
            "failed_breakout": is_failed_bo,
            "components": {
                "vol_coil": round(vol_coil, 1),
                "range_coil": round(range_coil, 1),
                "vwap": round(vwap_score, 1),
                "proximity": round(prox_score, 1),
                "close_quality": round(close_score, 1),
                "ma_stack": round(ma_score, 1),
                "trigger": round(trigger_score, 1),
                "base_len": round(base_len_score, 1),
            },
            "state": {
                "best_vol_ratio": round(state.best_vol_ratio, 3),
                "best_range_ratio": round(state.best_range_ratio, 3),
                "base_sessions": state.base_sessions,
            },
        })

    return results


def readiness_for_bars(bars_df, weights: dict | None = None) -> list[dict]:
    """Convenience: compute readiness from a DataFrame with OHLCV columns.

    Returns list of {date, score, stage, ...} dicts.
    """
    import pandas as pd

    if bars_df.empty or len(bars_df) < 20:
        return []

    bars = bars_df.sort_values("date").reset_index(drop=True)
    hi = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    cl = bars["close"].to_numpy(dtype=float)
    op = bars["open"].to_numpy(dtype=float)
    v = bars["volume"].to_numpy(dtype=float)
    dates = bars["date"].tolist()

    raw_results = compute_readiness_series(hi, lo, cl, op, v, weights)

    for r in raw_results:
        r["date"] = dates[r["idx"]]
        del r["idx"]

    return raw_results
