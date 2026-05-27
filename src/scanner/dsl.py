"""DSL v2.0 — Dynamic Stop Loss with R-tiered trailing + flow-based take-profit.

Initial stop: tactical profile.
    struct_low = lowest(low, 5)
    buffered_stop = struct_low - 0.5 * ATR(14)
    raw_distance = entry - buffered_stop
    clamped = clamp(raw_distance, 0.75 * ATR, 2.0 * ATR)
    initial_stop = entry - clamped

Tiers (trail WIDENS as position proves itself):
    T1  (0-0.5R):   session_low - 1.0 * ATR  (daily)
    T1b (0.5-1R):   session_low - 1.0 * ATR  (daily), floor = entry (breakeven)
    T2  (1-2R):     session_low - 1.5 * ATR  (daily), floor = entry
    T3  (2-4R):     weekly_low  - 2.0 * ATR  (weekly), floor = entry + 1.5R
    T4  (4R+):      max(weekly_low - 2.5*ATR, T1_target - 1*ATR), floor = entry + 3R

v1.5 change: breakeven trigger at +0.5R. Once price reaches +0.5R profit,
the stop floor is raised to entry price. This converts Tier 1 near-miss
trades from small losses into breakeven exits.

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


def compute_initial_stop(
    entry_price: float,
    atr14: float,
    recent_lows: np.ndarray,
) -> tuple[float, float]:
    """Return (initial_stop_price, risk_per_share = 1R).

    recent_lows: the last 5 low values up to and including the entry bar.
    """
    struct_low = float(np.nanmin(recent_lows[-5:])) if len(recent_lows) >= 5 else float(np.nanmin(recent_lows))
    buffered_stop = struct_low - 0.5 * atr14
    raw_distance = entry_price - buffered_stop
    clamped = max(min(raw_distance, atr14 * 2.0), atr14 * 0.75)
    initial_stop = entry_price - clamped
    risk = clamped  # 1R = distance from entry to initial stop
    return initial_stop, risk


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
) -> dict:
    """Walk forward from entry+1, applying DSL v2.0 tiered trailing + flow TP.

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

        # Compute new trail based on current tier
        if highest_tier == 1:
            new_trail = bar_low - 1.0 * atr14
            if be_triggered:
                new_trail = max(new_trail, entry_price)  # BE floor after +0.5R
        elif highest_tier == 2:
            new_trail = bar_low - 1.5 * atr14
            new_trail = max(new_trail, entry_price)  # T2+ floor: breakeven
        elif highest_tier == 3:
            new_trail = bar_low - 2.0 * atr14
            new_trail = max(new_trail, entry_price + 1.5 * risk)  # T3+ floor
        else:  # T4
            trail_a = bar_low - 2.5 * atr14
            trail_b = target_2r - 1.0 * atr14
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
) -> pd.DataFrame:
    """Add DSL v2.0 columns to signals frame.

    Requires signals to have: date, ticker, atr14_at_entry (or atr14).
    panel_daily: full daily OHLCV.
    scores_daily: optional — when provided, enables flow-based TP.
        Must contain columns: ticker, date, flow_100.

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

        initial_stop, risk = compute_initial_stop(entry_price, atr14, recent_lows)

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
