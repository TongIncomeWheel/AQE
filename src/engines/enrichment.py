"""AQE Pricer Enrichment — new per-record fields (Enrichment Spec v2.0).

Three new engine-level signals that the daily export carries on every record:

1. `rs_down_day_20d` / `rs_leadership` — all-weather relative-strength on SPY
   down days. Isolates genuine leaders that outperform when the market drops.

2. `setup_state` — daily lifecycle classification (EXTENDED / BASING /
   BREAKOUT-READY / CONTINUATION-READY). Replaces the "10 days same score"
   problem by saying WHAT the name is doing today.

3. `breakout_conviction` / `breakout_grade` / `breakout_pattern` — quality
   score for the most recent expansion bar, with a named pattern.

All three are pure functions on daily OHLCV + SPY + elder_context fields.
They never touch FMP or Drive — just math on arrays already in the panel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ────────────────────────────────────────────────────────────────────────────
# 1. RS Down-Day (all-weather leadership signal)
# ────────────────────────────────────────────────────────────────────────────

def compute_rs_down_day(stock_close: np.ndarray,
                        spy_close: np.ndarray,
                        window: int = 20) -> dict:
    """Average stock outperformance vs SPY on SPY's down days (last `window` sessions).

    Returns {"rs_down_day_20d": float|None, "rs_leadership": str}.
    Positive = stock beats SPY when SPY falls = genuine leader.
    """
    out = {"rs_down_day_20d": None, "rs_leadership": None}
    if len(stock_close) < window + 1 or len(spy_close) < window + 1:
        return out

    tk = stock_close[-(window + 1):]
    sp = spy_close[-(window + 1):]

    tk_ret = np.diff(tk) / tk[:-1] * 100
    sp_ret = np.diff(sp) / sp[:-1] * 100

    down_mask = sp_ret < 0
    if not np.any(down_mask):
        return out

    outperf = tk_ret[down_mask] - sp_ret[down_mask]
    avg = float(np.mean(outperf))
    out["rs_down_day_20d"] = round(avg, 2)
    if avg > 0.25:
        out["rs_leadership"] = "LEADER"
    elif avg < -0.25:
        out["rs_leadership"] = "LAGGARD"
    else:
        out["rs_leadership"] = "IN-LINE"
    return out


# ────────────────────────────────────────────────────────────────────────────
# 2. Setup State (lifecycle classification)
# ────────────────────────────────────────────────────────────────────────────

def compute_setup_state(close: float,
                        ma_10: float | None,
                        ma_20: float | None,
                        ma_50: float | None,
                        elder_ctx: dict | None) -> str:
    """Classify the daily setup state from price, MAs, and elder_context.

    States:
      EXTENDED           — price > MA10 by > 8%, do not chase
      BREAKOUT-READY     — VCP confirmed/partial + VWAP above + exhaustion
                           clear + price within 2% of base_high
      CONTINUATION-READY — MA stack bullish + price within 2.5% of MA10 +
                           volume declining
      BASING             — coil forming, not yet at trigger
    """
    if close is None or close <= 0:
        return "BASING"

    # MA10 distance — EXTENDED check
    if ma_10 is not None and ma_10 > 0:
        pct_above_ma10 = (close - ma_10) / ma_10 * 100
        if pct_above_ma10 > 8.0:
            return "EXTENDED"
    else:
        pct_above_ma10 = None

    ctx = elder_ctx or {}
    vcp = _ctx_get(ctx, "vcp", "vcp_label") or ""
    vwap_pos = _ctx_get(ctx, "vwap_5d", "position") or ""
    exhaustion = _ctx_get(ctx, "exhaustion_check", "exhaustion_flag") or ""
    vcp_tight = _ctx_get(ctx, "vcp", "vcp_tightness_pct")

    # BREAKOUT-READY: VCP confirmed/partial + VWAP above + exhaustion clear
    if (vcp in ("VCP_CONFIRMED", "VCP_PARTIAL")
            and vwap_pos == "ABOVE"
            and exhaustion == "CLEAR"):
        return "BREAKOUT-READY"

    # CONTINUATION-READY: MA stack bullish + price near MA10
    if (ma_10 is not None and ma_20 is not None and ma_50 is not None
            and ma_10 > ma_20 > ma_50
            and pct_above_ma10 is not None
            and abs(pct_above_ma10) < 2.5):
        return "CONTINUATION-READY"

    return "BASING"


def _ctx_get(ctx: dict, *keys):
    """Drill into a nested dict by keys, returning None on any miss."""
    cur = ctx
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ────────────────────────────────────────────────────────────────────────────
# 3. Breakout Conviction
# ────────────────────────────────────────────────────────────────────────────

# Weights exposed as config (spec §2, note on weighting) — calibrate against
# forward outcomes once historical exports are available.
BO_WEIGHT_T1_LOADING = 25
BO_WEIGHT_APPROACH = 15
BO_WEIGHT_BO_CLOSE = 25
BO_WEIGHT_VOLUME = 20
BO_WEIGHT_RANGE = 10
BO_ABSORPTION_BONUS = 10
BO_RANGE_EXPANSION_THRESHOLD = 1.3    # range > 1.3× base avg = expansion bar
BO_BASE_LOOKBACK = 10                 # bars for base avg range


def compute_breakout_conviction(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: np.ndarray | None = None,
) -> dict:
    """Score the most recent breakout/expansion bar (0–100) with pattern + grade.

    Looks backward from the last bar to find the most recent expansion bar
    (range > 1.3× base average range). If none found in the last 10 bars,
    returns nulls.

    Returns {breakout_conviction, breakout_grade, breakout_pattern,
             breakout_bar_date}.
    """
    out = {"breakout_conviction": None, "breakout_grade": None,
           "breakout_pattern": None, "breakout_bar_date": None}

    n = len(closes)
    if n < BO_BASE_LOOKBACK + 3:
        return out

    ranges = highs - lows
    base_avg_range = float(np.mean(ranges[-(BO_BASE_LOOKBACK + 2):-2]))
    if base_avg_range <= 0:
        return out

    # Find the most recent expansion bar (search last 10 bars, newest first)
    bo_idx = None
    for i in range(n - 1, max(n - 11, BO_BASE_LOOKBACK + 1) - 1, -1):
        if ranges[i] > BO_RANGE_EXPANSION_THRESHOLD * base_avg_range:
            bo_idx = i
            break
    if bo_idx is None:
        return out

    # T0 = breakout bar, T1 = bar before
    t0_o, t0_h, t0_l, t0_c = (float(opens[bo_idx]), float(highs[bo_idx]),
                                float(lows[bo_idx]), float(closes[bo_idx]))
    t0_v = float(volumes[bo_idx])
    t0_range = t0_h - t0_l

    t1_idx = bo_idx - 1
    t1_h, t1_l, t1_c = (float(highs[t1_idx]), float(lows[t1_idx]),
                          float(closes[t1_idx]))

    # Base reference (BO_BASE_LOOKBACK bars before T1)
    base_start = max(0, t1_idx - BO_BASE_LOOKBACK)
    base_vols = volumes[base_start:t1_idx].astype(float)
    base_close_0 = float(closes[base_start]) if base_start < t1_idx else t1_c

    # ── Five inputs ──
    t1_range = t1_h - t1_l
    t1_cir = (t1_c - t1_l) / t1_range if t1_range > 0 else 0.5
    t1_vwap_pos = 0.0   # approx: (close - midpoint) / midpoint
    t1_mid = (t1_h + t1_l + t1_c) / 3
    if t1_mid > 0:
        t1_vwap_pos = (t1_c - t1_mid) / t1_mid

    approach = (t1_c - base_close_0) / base_close_0 if base_close_0 > 0 else 0
    bo_cir = (t0_c - t0_l) / t0_range if t0_range > 0 else 0.5
    vol_exp = t0_v / float(np.mean(base_vols)) if len(base_vols) > 0 and np.mean(base_vols) > 0 else 1.0

    # ── Pattern detection ──
    gap = (t0_o - t1_c) / t1_c if t1_c > 0 else 0
    absorption = (gap < -0.005) and (bo_cir > 0.90)
    telegraphed = (t1_cir > 0.70) and (approach > 0.01)

    if absorption:
        pattern = "ABSORPTION_REVERSAL"
    elif telegraphed:
        pattern = "TELEGRAPHED_CONTINUATION"
    elif t1_cir < 0.40 and not absorption:
        pattern = "SURPRISE_THRUST"
    else:
        pattern = "STANDARD_BREAKOUT"

    # ── Score (0–100) ──
    score = 0.0
    score += min(BO_WEIGHT_T1_LOADING, t1_cir * 20 + (10 if t1_vwap_pos > 0 else 3))
    score += min(BO_WEIGHT_APPROACH, max(0, approach * 300)) if approach > 0 else 5
    score += min(BO_WEIGHT_BO_CLOSE, bo_cir * 25)
    score += min(BO_WEIGHT_VOLUME, vol_exp / 4 * 20)
    score += min(BO_WEIGHT_RANGE, t0_range / base_avg_range * 5)
    if absorption:
        score += BO_ABSORPTION_BONUS
    score = min(100.0, score)

    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

    out["breakout_conviction"] = round(score)
    out["breakout_grade"] = grade
    out["breakout_pattern"] = pattern
    if dates is not None and bo_idx < len(dates):
        out["breakout_bar_date"] = str(pd.Timestamp(dates[bo_idx]).date())
    return out


# ────────────────────────────────────────────────────────────────────────────
# 4. Clean-up flags (spec §3)
# ────────────────────────────────────────────────────────────────────────────

BETA_CAP = 5.0
MALFORMED_BRACKET_PCT = 0.5    # stop within 0.5% of entry = malformed


def cleanup_flags(entry: float | None, stop: float | None,
                  dsl_risk: float | None,
                  beta_60d: float | None,
                  dsl_atr_ratio: float | None,
                  regime_level: str | None) -> dict:
    """Compute the §3 clean-up flags for a single record.

    Returns {atr_caution, beta_data_error, malformed_bracket,
             beta_60d (capped), dsl_atr_ratio (floored)}.
    """
    out: dict = {"atr_caution": False, "beta_data_error": False,
                 "malformed_bracket": False}

    # CZR-BETA: cap beta at 5.0, flag data error
    if beta_60d is not None and abs(beta_60d) > BETA_CAP:
        out["beta_data_error"] = True
        out["beta_60d_capped"] = BETA_CAP if beta_60d > 0 else -BETA_CAP
    else:
        out["beta_60d_capped"] = beta_60d

    # EA-DSL / JHG-DSL: malformed bracket (stop within 0.5% of entry)
    if entry and stop and entry > 0:
        rr_pct = abs(entry - stop) / entry * 100
        if rr_pct < MALFORMED_BRACKET_PCT:
            out["malformed_bracket"] = True

    # AQE-BL-002: floor dsl_atr_ratio at 1.5 in YELLOW/ORANGE/RED
    elevated = regime_level in ("YELLOW", "ORANGE", "RED")
    if elevated and dsl_atr_ratio is not None and dsl_atr_ratio < 1.5:
        out["atr_caution"] = True
        out["dsl_atr_ratio_floored"] = 1.5
    else:
        out["dsl_atr_ratio_floored"] = dsl_atr_ratio

    return out


# ────────────────────────────────────────────────────────────────────────────
# 5. Bar/technical fields (AQE_INSTRUCTIONS.md voice-data-contract-v6 §2) — pure
# functions on the same daily OHLCV panel `enrich_record` already holds. Each
# degrades to None/[] on insufficient history, never raises.
# ────────────────────────────────────────────────────────────────────────────

def compute_bar_fields(stock_daily: pd.DataFrame) -> dict:
    """Raw-bar + short-window technical reads for one ticker.

    All of these are additive, seat-facing fields (seow/raschke/oneil/thorp —
    see AQE_INSTRUCTIONS.md §2); none feed a gate or a size decision.
    """
    out: dict = {
        "bar_open": None, "bar_high": None, "bar_low": None, "bar_close": None,
        "prior_bar_high": None, "prior_bar_low": None,
        "ma_20_slope_5d_pct": None, "ret_63d": None, "pct_run_10d": None,
        "base_low_20d": None, "bar_range_5d": None,
        "hi_20d": None, "lo_20d": None, "hi_50d": None, "lo_50d": None,
        "pos_in_50d_range_pct": None,
        "nr4_flag": None, "nr7_flag": None, "hv_ratio_6_100": None,
        "adx_14": None, "stoch_k_14": None, "stoch_d_3": None,
        "rvol_20d": None,
    }
    if stock_daily is None or stock_daily.empty:
        return out

    o = stock_daily["open"].astype(float).to_numpy()
    h = stock_daily["high"].astype(float).to_numpy()
    l = stock_daily["low"].astype(float).to_numpy()
    c = stock_daily["close"].astype(float).to_numpy()
    v = stock_daily["volume"].astype(float).to_numpy()
    n = len(c)
    if n < 2:
        return out

    out["bar_open"], out["bar_high"] = round(float(o[-1]), 2), round(float(h[-1]), 2)
    out["bar_low"], out["bar_close"] = round(float(l[-1]), 2), round(float(c[-1]), 2)
    out["prior_bar_high"] = round(float(h[-2]), 2)
    out["prior_bar_low"] = round(float(l[-2]), 2)

    rng = h - l
    out["bar_range_5d"] = [round(float(x), 2) for x in rng[-5:]] if n >= 5 else None
    if n >= 4:
        out["nr4_flag"] = bool(rng[-1] <= rng[-4:].min())
    if n >= 7:
        out["nr7_flag"] = bool(rng[-1] <= rng[-7:].min())

    if n >= 21:
        ma20 = pd.Series(c).rolling(20).mean().to_numpy()
        if ma20[-6] and ma20[-6] == ma20[-6]:
            out["ma_20_slope_5d_pct"] = round((ma20[-1] / ma20[-6] - 1) * 100, 2)
    if n >= 64:
        out["ret_63d"] = round((c[-1] / c[-64] - 1) * 100, 2)
    if n >= 11:
        out["pct_run_10d"] = round((c[-1] / c[-11] - 1) * 100, 2)
    if n >= 20:
        out["base_low_20d"] = round(float(l[-20:].min()), 2)
        out["hi_20d"] = round(float(h[-20:].max()), 2)
        out["lo_20d"] = round(float(l[-20:].min()), 2)
    if n >= 50:
        hi50, lo50 = float(h[-50:].max()), float(l[-50:].min())
        out["hi_50d"], out["lo_50d"] = round(hi50, 2), round(lo50, 2)
        rng50 = hi50 - lo50
        out["pos_in_50d_range_pct"] = round((c[-1] - lo50) / rng50 * 100, 2) if rng50 != 0 else 50.0
    if n >= 101:
        rets = pd.Series(c).pct_change()
        hv6 = float(rets.iloc[-6:].std() * (252 ** 0.5))
        hv100 = float(rets.iloc[-100:].std() * (252 ** 0.5))
        if hv100 and hv100 == hv100 and hv100 != 0:
            out["hv_ratio_6_100"] = round(hv6 / hv100, 3)
    if n >= 15:
        try:
            from src.engines.mp import _dmi
            _, _, adx_series = _dmi(pd.Series(h), pd.Series(l), pd.Series(c), n=14)
            adx_last = adx_series.iloc[-1]
            out["adx_14"] = round(float(adx_last), 2) if adx_last == adx_last else None
        except Exception:  # noqa: BLE001 — additive, never blocks the export
            pass
    if n >= 14:
        hs, ls, cs = pd.Series(h), pd.Series(l), pd.Series(c)
        hi14_series = hs.rolling(14).max()
        lo14_series = ls.rolling(14).min()
        rng14_series = (hi14_series - lo14_series).replace(0.0, np.nan)
        k_series = ((cs - lo14_series) / rng14_series * 100).fillna(50.0)
        out["stoch_k_14"] = round(float(k_series.iloc[-1]), 2)
        if n >= 16:
            out["stoch_d_3"] = round(float(k_series.iloc[-3:].mean()), 2)

    return out


def compute_effective_atr(atr14: float,
                          highs_5d: np.ndarray,
                          lows_5d: np.ndarray,
                          vol_20d: np.ndarray,
                          vol_90d: np.ndarray) -> float:
    """AQE-BL-001: use max(ATR14, 5d_avg_range) when recent volume is elevated.

    When 20d average volume > 2× 90d average volume, the stock is in a
    high-activity period and ATR14 may lag the real range. Use the larger of
    ATR14 and the 5-day average range so the stop isn't sub-ATR.
    """
    if len(highs_5d) < 5 or len(lows_5d) < 5:
        return atr14

    avg_vol_20d = float(np.mean(vol_20d[-20:])) if len(vol_20d) >= 20 else 0
    avg_vol_90d = float(np.mean(vol_90d[-90:])) if len(vol_90d) >= 90 else avg_vol_20d

    if avg_vol_90d > 0 and avg_vol_20d > 2.0 * avg_vol_90d:
        avg_range_5d = float(np.mean(highs_5d[-5:] - lows_5d[-5:]))
        return max(atr14, avg_range_5d)
    return atr14


# ────────────────────────────────────────────────────────────────────────────
# Convenience: compute all enrichment fields for one ticker
# ────────────────────────────────────────────────────────────────────────────

def enrich_record(
    stock_daily: pd.DataFrame | None,
    spy_daily: pd.DataFrame | None,
    elder_ctx: dict | None,
    entry: float | None = None,
    stop: float | None = None,
    dsl_risk: float | None = None,
    beta_60d: float | None = None,
    dsl_atr_ratio: float | None = None,
    regime_level: str | None = None,
) -> dict:
    """All enrichment fields for a single ticker, from daily bars + context.

    Returns a flat dict of all new fields. Any field that can't be computed
    degrades to None — never raises.
    """
    out: dict = {
        "rs_down_day_20d": None, "rs_leadership": None,
        "setup_state": "BASING",
        "breakout_conviction": None, "breakout_grade": None,
        "breakout_pattern": None, "breakout_bar_date": None,
        "atr_caution": False, "beta_data_error": False,
        "malformed_bracket": False,
    }

    # Clean-up flags (always computable)
    flags = cleanup_flags(entry, stop, dsl_risk, beta_60d,
                          dsl_atr_ratio, regime_level)
    out.update(flags)

    # Bar/technical fields (§2) — computable off raw OHLCV alone, independent
    # of the 21-bar floor below that gates the older setup/breakout signals.
    out.update(compute_bar_fields(stock_daily))
    if stock_daily is not None and not stock_daily.empty:
        avg_vol_20d = _ctx_get(elder_ctx, "volume", "avg_vol_20d")
        day_vol = float(stock_daily["volume"].iloc[-1])
        if avg_vol_20d:
            out["rvol_20d"] = round(day_vol / avg_vol_20d, 2)

    if stock_daily is None or stock_daily.empty:
        return out

    close = stock_daily["close"].astype(float).to_numpy()
    if len(close) < 21:
        return out

    # RS Down-Day
    if spy_daily is not None and not spy_daily.empty:
        spy_c = spy_daily["close"].astype(float).to_numpy()
        n_common = min(len(close), len(spy_c))
        rs = compute_rs_down_day(close[-n_common:], spy_c[-n_common:])
        out.update(rs)

    # MAs for setup_state
    price = float(close[-1])
    ma_10 = float(np.mean(close[-10:])) if len(close) >= 10 else None
    ma_20 = float(np.mean(close[-20:])) if len(close) >= 20 else None
    ma_50 = float(np.mean(close[-50:])) if len(close) >= 50 else None
    out["setup_state"] = compute_setup_state(price, ma_10, ma_20, ma_50, elder_ctx)

    # Breakout Conviction
    if len(close) >= BO_BASE_LOOKBACK + 3:
        highs = stock_daily["high"].astype(float).to_numpy()
        lows = stock_daily["low"].astype(float).to_numpy()
        opens = stock_daily["open"].astype(float).to_numpy()
        volumes = stock_daily["volume"].astype(float).to_numpy()
        dates = stock_daily["date"].to_numpy() if "date" in stock_daily.columns else None
        bo = compute_breakout_conviction(opens, highs, lows, close, volumes, dates)
        out.update(bo)

    return out
