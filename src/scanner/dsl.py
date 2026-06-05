"""DSL v2.1 + v1.5 — Dynamic Stop Loss.

v2.1: β-adjusted stops, MP-gated trails, min hold period, flow TP,
      R-tiered trailing. Used by the backtest simulator.
v1.5: Dynamic ATR ratio driven by regime + elder + whippiness.
      Used by the Scanner export (levels_for_ticker path).

DSL v2.1 — Dynamic Stop Loss with β-adjusted stops, MP-gated trails,
minimum hold period, flow-based take-profit, and R-tiered trailing.

Initial stop: tactical profile (β-adjusted).
    struct_low = lowest(low, 5)
    buffered_stop = struct_low - 0.5 * ATR(14)
    raw_distance = entry - buffered_stop
    upper_clamp:
        β ≥ 2.0  →  2.5 × ATR   (wider room for high-β names)
        β ≥ 1.5  →  2.25 × ATR  (intermediate)
        default  →  2.0 × ATR
    clamped = clamp(raw_distance, 0.75 * ATR, upper_clamp)
    initial_stop = entry - clamped

Trail ATR multiplier (applied to all tier formulas):
    FADING mp_state              →  0.85× (tighten when momentum decays)
    β ≥ 2.0 and NOT FADING       →  1.25× (high-β in good momentum = wider)
    1.5 ≤ β < 2.0 and NOT FADING →  1.10×
    default                      →  1.00×

Minimum hold period (default 3 bars):
    Trail stop does not ratchet upward during the first min_hold_bars bars,
    preventing an early intraday sweep from raising the stop against us
    before the trade has had a chance to develop.

Tiers (trail WIDENS as position proves itself, using atr_eff = ATR × trail_mult):
    T1  (0-0.5R):   session_low - 1.0 * atr_eff  (daily)
    T1b (0.5-1R):   session_low - 1.0 * atr_eff  (daily), floor = entry (BE)
    T2  (1-2R):     session_low - 1.5 * atr_eff  (daily), floor = entry
    T3  (2-4R):     weekly_low  - 2.0 * atr_eff  (weekly), floor = entry + 1.5R
    T4  (4R+):      max(weekly_low - 2.5*atr_eff, T1_target - 1*atr_eff), floor = entry + 3R

v2.0 change: flow-based take-profit. While in Tier 1, if the trade is
profitable (R > 0.2) and flow_100 drops below 65, exit at close. Flow
below 65 = no longer a momentum stock. Only fires in Tier 1 (0 to +1R)
so big winners (Tier 2+) are never interrupted. 2-bar grace period lets
the trade develop before TP can fire.

Trail ratchets upward only. Highest tier locks (never demotes).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.utils import atr as compute_atr, lowest


def _upper_atr_clamp(atr14: float, beta: float | None) -> float:
    """β-adjusted upper clamp for the initial stop distance.

    High-β names have wider intraday swings, so a tighter ATR clamp causes
    premature stop-outs on normal volatility rather than genuine reversals.
        β ≥ 2.0  →  2.5 × ATR
        β ≥ 1.5  →  2.25 × ATR
        default  →  2.0 × ATR (unchanged from DSL v2.0)
    """
    if beta is not None and beta >= 2.0:
        return atr14 * 2.5
    if beta is not None and beta >= 1.5:
        return atr14 * 2.25
    return atr14 * 2.0


def _trail_mult(beta: float | None, mp_state: str | None) -> float:
    """ATR multiplier applied to all trail-tier ATR terms.

    FADING momentum always tightens regardless of beta — don't give room
    to a name that's losing its edge. High-beta in good momentum gets wider
    trail room to survive normal volatility without early exit.
    """
    if mp_state is not None and mp_state.upper() == "FADING":
        return 0.85
    if beta is not None and beta >= 2.0:
        return 1.25
    if beta is not None and beta >= 1.5:
        return 1.10
    return 1.0


def compute_initial_stop(
    entry_price: float,
    atr14: float,
    recent_lows: np.ndarray,
    beta: float | None = None,
) -> tuple[float, float]:
    """Return (initial_stop_price, risk_per_share = 1R).

    recent_lows: the last 5 low values up to and including the entry bar.
    beta: optional 30-day beta vs SPY. When ≥ 1.5, widens the upper ATR
        clamp so high-volatility names are not stopped out by normal swings.
    """
    struct_low = float(np.nanmin(recent_lows[-5:])) if len(recent_lows) >= 5 else float(np.nanmin(recent_lows))
    buffered_stop = struct_low - 0.5 * atr14
    raw_distance = entry_price - buffered_stop
    upper = _upper_atr_clamp(atr14, beta)
    clamped = max(min(raw_distance, upper), atr14 * 0.75)
    initial_stop = entry_price - clamped
    risk = clamped  # 1R = distance from entry to initial stop
    return initial_stop, risk


# ---------------------------------------------------------------------------
# DSL v1.5 — Dynamic ATR ratio (regime + elder + whippiness)
# ---------------------------------------------------------------------------

_REGIME_RATIO: dict[str, float] = {
    "GREEN":  1.5,
    "YELLOW": 2.0,
    "ORANGE": 2.5,
    # RED excluded — RED = hard stop, no new entries allowed
}

_RATIO_FLOOR = 1.0
_RATIO_CEIL  = 3.5


def compute_dynamic_atr_ratio(
    regime_level: str | None,
    elder_score: float | None,
    highs_14: np.ndarray,
    lows_14: np.ndarray,
    atr14: float,
) -> tuple[float, float]:
    """DSL v1.5 dynamic ATR ratio — the INPUT that drives stop width.

    Three additive components:
      1. Regime base: GREEN=1.5, YELLOW=2.0, ORANGE=2.5.
         RED defaults to GREEN (hard stop — no new entries). Missing → GREEN.
      2. Elder impulse: ≥8 tightens by -0.25 (strong momentum, tighter OK).
         ≤4 widens by +0.50 (weak impulse, needs room). Else 0.
      3. Whippiness proxy: avg(high-low, 14 bars) / atr_14d.
         Measures intraday range vs total volatility (including gaps).
         >0.85 → +0.50 (very whippy, intraday noise sweeps stops).
         >0.70 → +0.25 (moderately whippy).
         Else 0.

    Returns (clamped_ratio, daily_range_proxy).
    """
    # 1. Regime base
    level = (regime_level or "GREEN").upper()
    if level == "RED":
        level = "GREEN"
    base = _REGIME_RATIO.get(level, 1.5)

    # 2. Elder adjustment
    elder_adj = 0.0
    if elder_score is not None and np.isfinite(elder_score):
        if elder_score >= 8.0:
            elder_adj = -0.25
        elif elder_score <= 4.0:
            elder_adj = 0.50

    # 3. Whippiness (daily range proxy for atr_1h / atr_14d)
    whip_adj = 0.0
    daily_range_proxy = 0.0
    if (len(highs_14) >= 14 and len(lows_14) >= 14
            and atr14 > 0 and np.isfinite(atr14)):
        avg_range = float(np.nanmean(highs_14[-14:] - lows_14[-14:]))
        daily_range_proxy = avg_range / atr14
        if daily_range_proxy > 0.85:
            whip_adj = 0.50
        elif daily_range_proxy > 0.70:
            whip_adj = 0.25

    raw = base + elder_adj + whip_adj
    return float(np.clip(raw, _RATIO_FLOOR, _RATIO_CEIL)), round(daily_range_proxy, 3)


def compute_initial_stop_v15(
    entry_price: float,
    atr14: float,
    recent_lows: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    regime_level: str | None = None,
    elder_score: float | None = None,
    beta: float | None = None,
) -> tuple[float, float, float, float]:
    """DSL v1.5 dynamic stop with regime/elder/whippiness-driven ATR ratio.

    Returns (initial_stop, risk, dynamic_ratio, daily_range_proxy).
      - dynamic_ratio: the clamped [1.0, 3.5] ATR multiplier
      - daily_range_proxy: avg(H-L, 14) / ATR (whippiness, for export)

    Stop = entry - (dynamic_ratio × atr_14d), optionally widened to
    the structural swing low (from fractal pivot detection) if that sits
    further below entry. Final distance clamped to [1.0, 3.5] × ATR.
    """
    # 1. Dynamic ratio
    dynamic_ratio, daily_range_proxy = compute_dynamic_atr_ratio(
        regime_level, elder_score, highs, lows, atr14,
    )

    # 2. Dynamic stop from ratio
    dynamic_distance = dynamic_ratio * atr14
    dynamic_stop = entry_price - dynamic_distance

    # 3. Structural swing low widening — use existing fractal detector
    from src.scanner.levels import find_swing  # local import avoids circular
    swing = find_swing(highs, lows)
    if swing is not None:
        swing_stop = swing["low"] - 0.5 * atr14  # buffer below support
        if swing_stop < dynamic_stop:
            # Swing low is further away — widen to structural support
            dynamic_stop = swing_stop
            dynamic_distance = entry_price - dynamic_stop

    # 4. Final clamp: distance must stay in [1.0, 3.5] × ATR
    min_distance = _RATIO_FLOOR * atr14
    max_distance = _RATIO_CEIL * atr14
    clamped_distance = max(min(dynamic_distance, max_distance), min_distance)
    final_stop = entry_price - clamped_distance
    risk = clamped_distance

    # Recompute the effective ratio for export (may differ from dynamic_ratio
    # if swing widening or clamping changed the distance)
    effective_ratio = round(clamped_distance / atr14, 2) if atr14 > 0 else dynamic_ratio

    return final_stop, risk, effective_ratio, daily_range_proxy


def simulate_dsl_trade(
    entry_price: float,
    atr14: float,
    risk: float,
    bars_open: np.ndarray,
    bars_high: np.ndarray,
    bars_low: np.ndarray,
    bars_close: np.ndarray,
    initial_stop: float,
    max_bars: int = 63,
    bar_flow: np.ndarray | None = None,
    tp_flow_floor: float = 65.0,
    tp_min_r: float = 0.2,
    tp_grace_bars: int = 2,
    # v2.1 additions
    beta: float | None = None,
    mp_state: str | None = None,
    min_hold_bars: int = 3,
) -> dict:
    """Walk forward from entry+1, applying DSL v2.1 tiered trailing + flow TP.

    Parameters
    ----------
    bar_flow : optional array of flow_100 values, one per forward bar.
        When provided, enables signal-driven take-profit: if the trade is
        in Tier 1, profitable (R >= tp_min_r), past the grace period, and
        flow drops below tp_flow_floor → exit at close. Flow < 65 means
        the stock is no longer a momentum trade.
    tp_flow_floor : flow_100 level below which TP fires (default 65).
    tp_min_r : minimum R-multiple before TP can fire (default 0.2).
    tp_grace_bars : don't fire TP in first N bars (default 2).
    beta : 30-day beta vs SPY. Widens trail ATR multiplier for high-β names.
    mp_state : 'STRONG' / 'BUILDING' / 'FADING'. FADING tightens trail
        multiplier regardless of beta — don't hold a fading name loosely.
    min_hold_bars : trail stop does not ratchet upward during the first N bars
        (default 3). Prevents early sweeps from raising the stop into the
        trade before it has a chance to develop.

    Returns a dict with:
        exit_bar, exit_price, exit_type, peak_tier, r_realized, peak_r,
        be_triggered, tp_fired.
    """
    n = len(bars_close)
    if n == 0 or risk <= 0:
        return _no_trade(entry_price, risk)

    has_flow = bar_flow is not None and len(bar_flow) > 0
    target_2r = entry_price + 2.0 * risk
    trail_stop = initial_stop
    highest_tier = 1
    be_triggered = False
    peak_r = 0.0

    # v2.1: effective ATR for trail formulas, adjusted for beta and MP state
    mult = _trail_mult(beta, mp_state)
    atr_eff = atr14 * mult

    for i in range(min(n, max_bars)):
        bar_open = float(bars_open[i])
        bar_high = float(bars_high[i])
        bar_low = float(bars_low[i])
        bar_close = float(bars_close[i])

        # Gap-down exit: open below trailing stop
        if bar_open <= trail_stop:
            exit_price = bar_open
            r = (exit_price - entry_price) / risk
            return {
                "exit_bar": i + 1,
                "exit_price": exit_price,
                "exit_type": "gap_stop",
                "peak_tier": highest_tier,
                "r_realized": r,
                "peak_r": peak_r,
                "be_triggered": be_triggered,
                "tp_fired": False,
            }

        # Intraday stop: low touches trail
        if bar_low <= trail_stop:
            exit_price = trail_stop
            r = (exit_price - entry_price) / risk
            return {
                "exit_bar": i + 1,
                "exit_price": exit_price,
                "exit_type": "trail_stop",
                "peak_tier": highest_tier,
                "r_realized": r,
                "peak_r": peak_r,
                "be_triggered": be_triggered,
                "tp_fired": False,
            }

        # Still alive — update R-multiple and tier
        current_r = (bar_close - entry_price) / risk
        high_r = (bar_high - entry_price) / risk
        peak_r = max(peak_r, high_r)

        # Breakeven trigger: once intraday high reaches +0.5R, lock BE floor
        if not be_triggered and high_r >= 0.5:
            be_triggered = True

        # Determine highest tier reached (locks, never demotes)
        if current_r >= 4.0 and highest_tier < 4:
            highest_tier = 4
        elif current_r >= 2.0 and highest_tier < 3:
            highest_tier = 3
        elif current_r >= 1.0 and highest_tier < 2:
            highest_tier = 2

        # --- v2.0: Flow-based take-profit ---
        # Only in Tier 1 (trade hasn't reached +1R), profitable, past grace.
        # If flow dropped below floor, the stock lost momentum — close at market.
        if (has_flow
                and i >= tp_grace_bars
                and current_r >= tp_min_r
                and highest_tier <= 1
                and i < len(bar_flow)):
            flow_val = float(bar_flow[i])
            if np.isfinite(flow_val) and flow_val < tp_flow_floor:
                r = (bar_close - entry_price) / risk
                return {
                    "exit_bar": i + 1,
                    "exit_price": bar_close,
                    "exit_type": "tp_flow",
                    "peak_tier": highest_tier,
                    "r_realized": r,
                    "peak_r": peak_r,
                    "be_triggered": be_triggered,
                    "tp_fired": True,
                }

        # --- v2.1: Minimum hold period ---
        # Don't ratchet the trail upward in the first min_hold_bars bars.
        # The initial stop still protects against gap-downs and intraday sweeps
        # (checked above), but we don't tighten until the trade has developed.
        if i < min_hold_bars:
            continue

        # Compute new trail based on current tier (using β/MP-adjusted atr_eff)
        if highest_tier == 1:
            new_trail = bar_low - 1.0 * atr_eff
            if be_triggered:
                new_trail = max(new_trail, entry_price)  # BE floor after +0.5R
        elif highest_tier == 2:
            new_trail = bar_low - 1.5 * atr_eff
            new_trail = max(new_trail, entry_price)  # T2+ floor: breakeven
        elif highest_tier == 3:
            new_trail = bar_low - 2.0 * atr_eff
            new_trail = max(new_trail, entry_price + 1.5 * risk)  # T3+ floor
        else:  # T4
            trail_a = bar_low - 2.5 * atr_eff
            trail_b = target_2r - 1.0 * atr_eff
            new_trail = max(trail_a, trail_b)
            new_trail = max(new_trail, entry_price + 3.0 * risk)  # T4+ floor

        # Ratchet: trail only moves up
        trail_stop = max(trail_stop, new_trail)

    # Time exit at end of window
    exit_price = float(bars_close[min(n, max_bars) - 1]) if n > 0 else entry_price
    r = (exit_price - entry_price) / risk
    return {
        "exit_bar": min(n, max_bars),
        "exit_price": exit_price,
        "exit_type": "time",
        "peak_tier": highest_tier,
        "r_realized": r,
        "peak_r": peak_r,
        "be_triggered": be_triggered,
        "tp_fired": False,
    }


def compute_dsl_outcomes(
    signals: pd.DataFrame,
    panel_daily: pd.DataFrame,
    max_bars: int = 63,
    scores_daily: pd.DataFrame | None = None,
    tp_flow_floor: float = 65.0,
    betas: dict | None = None,
) -> pd.DataFrame:
    """Add DSL v2.1 columns to signals frame.

    Requires signals to have: date, ticker, atr14_at_entry (or atr14).
    panel_daily: full daily OHLCV.
    scores_daily: optional — when provided, enables flow-based TP.
        Must contain columns: ticker, date, flow_100.
    betas: optional {ticker: {30: float, 60: float}} from load_betas().
        When provided, uses 30-day beta for β-adjusted initial stop and
        trail multiplier. If signals already have a beta_30d column, that
        takes precedence.

    Adds columns: dsl_exit_bar, dsl_exit_price, dsl_exit_type,
                  dsl_peak_tier, dsl_r_realized, dsl_peak_r,
                  dsl_initial_stop, dsl_risk, dsl_be_triggered,
                  dsl_tp_fired.
    """
    if signals.empty:
        return signals.copy()

    panel = panel_daily.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel_groups = {t: g.reset_index(drop=True) for t, g in panel.groupby("ticker", sort=False)}

    # Build score lookup for flow TP
    has_scores = (scores_daily is not None
                  and not scores_daily.empty
                  and "flow_100" in scores_daily.columns)
    score_groups: dict = {}
    if has_scores:
        sc = scores_daily[["ticker", "date", "flow_100"]].copy()
        sc["date"] = pd.to_datetime(sc["date"]).dt.normalize()
        for t, g in sc.groupby("ticker", sort=False):
            g = g.sort_values("date").reset_index(drop=True)
            score_groups[t] = {d: i for i, d in enumerate(g["date"].to_numpy())}, g["flow_100"].to_numpy()

    results: list[dict] = []
    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()

    for _, row in sig.iterrows():
        ticker = row["ticker"]
        bars = panel_groups.get(ticker)
        if bars is None or bars.empty:
            results.append(_empty_dsl_row())
            continue

        bars_dates = bars["date"].to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}
        entry_idx = date_to_idx.get(np.datetime64(row["date"], "ns"))
        if entry_idx is None:
            results.append(_empty_dsl_row())
            continue

        entry_price = float(bars["close"].iloc[entry_idx])
        atr_col = "atr14_at_entry" if "atr14_at_entry" in row.index else "atr14"
        atr14 = float(row.get(atr_col, np.nan))
        if not np.isfinite(atr14) or atr14 <= 0:
            results.append(_empty_dsl_row())
            continue

        # Get recent lows for structural stop
        low_start = max(0, entry_idx - 4)
        recent_lows = bars["low"].iloc[low_start:entry_idx + 1].astype(float).to_numpy()

        # v2.1: resolve beta + mp_state for this ticker
        # Row-level columns take precedence; fall back to betas dict.
        beta = None
        if "beta_30d" in row.index and pd.notna(row["beta_30d"]):
            beta = float(row["beta_30d"])
        elif betas is not None:
            beta = (betas.get(ticker) or {}).get(30)

        mp_state = str(row["mp_state"]) if "mp_state" in row.index and pd.notna(row.get("mp_state")) else None

        initial_stop, risk = compute_initial_stop(entry_price, atr14, recent_lows, beta=beta)

        # Forward bars (entry+1 onward)
        fwd_start = entry_idx + 1
        fwd_end = min(fwd_start + max_bars, len(bars))
        if fwd_start >= len(bars):
            results.append(_empty_dsl_row())
            continue

        fwd_open = bars["open"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_high = bars["high"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_low = bars["low"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_close = bars["close"].iloc[fwd_start:fwd_end].astype(float).to_numpy()

        # Look up flow_100 for each forward bar (for TP signal)
        bar_flow = None
        if has_scores and ticker in score_groups:
            sc_idx_map, sc_flow_arr = score_groups[ticker]
            fwd_dates = bars["date"].iloc[fwd_start:fwd_end].to_numpy()
            flow_vals = []
            for d in fwd_dates:
                si = sc_idx_map.get(d)
                flow_vals.append(float(sc_flow_arr[si]) if si is not None else np.nan)
            bar_flow = np.array(flow_vals)

        trade = simulate_dsl_trade(
            entry_price, atr14, risk,
            fwd_open, fwd_high, fwd_low, fwd_close,
            initial_stop, max_bars,
            bar_flow=bar_flow,
            tp_flow_floor=tp_flow_floor,
            beta=beta,
            mp_state=mp_state,
        )
        trade["dsl_initial_stop"] = initial_stop
        trade["dsl_risk"] = risk
        results.append(trade)

    dsl_df = pd.DataFrame(results)
    dsl_df.columns = [f"dsl_{c}" if not c.startswith("dsl_") else c for c in dsl_df.columns]
    return pd.concat([sig.reset_index(drop=True), dsl_df.reset_index(drop=True)], axis=1)


def _no_trade(entry_price: float, risk: float) -> dict:
    return {
        "exit_bar": 0,
        "exit_price": entry_price,
        "exit_type": "no_data",
        "peak_tier": 0,
        "r_realized": 0.0,
        "peak_r": 0.0,
        "be_triggered": False,
        "tp_fired": False,
    }


def _empty_dsl_row() -> dict:
    return {
        "exit_bar": np.nan,
        "exit_price": np.nan,
        "exit_type": np.nan,
        "peak_tier": np.nan,
        "r_realized": np.nan,
        "peak_r": np.nan,
        "be_triggered": np.nan,
        "tp_fired": np.nan,
        "dsl_initial_stop": np.nan,
        "dsl_risk": np.nan,
    }
