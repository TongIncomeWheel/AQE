"""Walk-Forward Analysis v2 — Pardo RP-1, RP-4.

Two modes:
  1. Re-optimize: classic Pardo — optimize per window, test OOS. Shows if the
     *grid* generalises, not your specific recipe.
  2. Fixed-recipe: hold YOUR recipe constant, measure IS vs OOS across windows.
     Shows if YOUR recipe works across time. This is what matters for trading.

Rolling and anchored walk-forward:
    - Rolling: 12-month train, 3-month test, 1-month step
    - Anchored: fixed start, growing train, 3-month test, 1-month step

WFER interpretation:
    > 0.50: Robust — parameters generalise well
    0.30-0.50: Acceptable — some degradation but viable
    < 0.30: Fragile — system is curve-fit
    < 0: Broken — loses money out of sample
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.calibration.recipe_optimizer import run_grid_search, RecipeResult


MIN_OOS_TRADES = 20  # Minimum test trades for a valid window


@dataclass
class WFWindow:
    """One walk-forward window result."""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_recipe: RecipeResult | None
    is_avg_r: float
    oos_avg_r: float
    oos_n_trades: int
    oos_win_rate: float
    wfer: float
    status: str  # ROBUST, OK, FRAGILE, BROKEN


def _classify_wfer(wfer: float) -> str:
    if wfer >= 0.50:
        return "ROBUST"
    elif wfer >= 0.30:
        return "OK"
    elif wfer >= 0:
        return "FRAGILE"
    else:
        return "BROKEN"


def walk_forward_analysis(
    outcomes: pd.DataFrame,
    r_column: str = "dsl_r_realized",
    mode: str = "rolling",
    train_months: int = 12,
    test_months: int = 3,
    step_months: int = 1,
    fixed_recipe: RecipeResult | None = None,
    subcomp_filters: dict | None = None,
    sc_mom_min: float = 50.0,
) -> list[WFWindow]:
    """Run walk-forward analysis across the outcome dataset.

    Parameters
    ----------
    fixed_recipe : if provided, tests THIS recipe unchanged across all windows.
        No re-optimization per window. This is the "does my recipe generalise?"
        test. If None, re-optimizes each window (classic Pardo).
    subcomp_filters : if provided, uses sub-component column filters instead of
        aggregate RecipeResult. Dict of {column: threshold}. Ignores fixed_recipe.
    sc_mom_min : minimum sc_momentum for sub-component mode (crossup gate).

    For each window:
    1. Either use fixed_recipe or optimize recipe on training period
    2. Apply recipe to BOTH train and test period
    3. Compute WFER = test avg R / train avg R

    Returns list of WFWindow results.
    """
    if outcomes.empty or r_column not in outcomes.columns:
        return []

    df = outcomes.copy()
    df["date"] = pd.to_datetime(df["date"])
    min_date = df["date"].min()
    max_date = df["date"].max()

    windows: list[WFWindow] = []
    window_id = 0

    if mode == "anchored":
        anchor_start = min_date

    current_test_start = min_date + pd.DateOffset(months=train_months)

    while current_test_start + pd.DateOffset(months=test_months) <= max_date:
        test_end = current_test_start + pd.DateOffset(months=test_months)

        if mode == "rolling":
            train_start = current_test_start - pd.DateOffset(months=train_months)
        else:  # anchored
            train_start = anchor_start

        train_mask = (df["date"] >= train_start) & (df["date"] < current_test_start)
        test_mask = (df["date"] >= current_test_start) & (df["date"] < test_end)

        train_data = df.loc[train_mask]
        test_data = df.loc[test_mask]

        if len(train_data) < 30 or len(test_data) < MIN_OOS_TRADES:
            current_test_start += pd.DateOffset(months=step_months)
            continue

        if subcomp_filters is not None:
            # Sub-component mode (Precision Edge): same filters for all windows
            is_rs = _apply_subcomp_recipe(train_data, subcomp_filters, sc_mom_min, r_column)
            is_avg_r = float(np.mean(is_rs)) if len(is_rs) >= 10 else 0.0
            best = None
        elif fixed_recipe is not None:
            # Fixed-recipe mode: use the SAME recipe for all windows
            best = fixed_recipe
            # Compute IS avg R by applying fixed recipe to training data
            is_rs = _apply_recipe(train_data, best, r_column)
            is_avg_r = float(np.mean(is_rs)) if len(is_rs) >= 10 else 0.0
        else:
            # Re-optimize mode: grid search on training data
            results, _ = run_grid_search(train_data, r_column=r_column, quick=True)
            if not results:
                current_test_start += pd.DateOffset(months=step_months)
                continue
            best = results[0]
            is_avg_r = best.avg_r

        # Apply recipe to test data
        if subcomp_filters is not None:
            test_filtered = _apply_subcomp_recipe(test_data, subcomp_filters, sc_mom_min, r_column)
        else:
            test_filtered = _apply_recipe(test_data, best, r_column)
        oos_n = len(test_filtered)

        if oos_n < MIN_OOS_TRADES:
            # Not enough OOS trades — skip this window
            current_test_start += pd.DateOffset(months=step_months)
            continue

        oos_avg_r = float(np.mean(test_filtered))
        oos_win_rate = float(np.sum(test_filtered > 0) / oos_n) if oos_n > 0 else 0.0
        wfer = oos_avg_r / is_avg_r if is_avg_r > 0 else 0.0
        status = _classify_wfer(wfer)

        windows.append(WFWindow(
            window_id=window_id,
            train_start=str(train_start.date()),
            train_end=str(current_test_start.date()),
            test_start=str(current_test_start.date()),
            test_end=str(test_end.date()),
            best_recipe=best,
            is_avg_r=round(is_avg_r, 4),
            oos_avg_r=round(oos_avg_r, 4),
            oos_n_trades=oos_n,
            oos_win_rate=round(oos_win_rate, 4),
            wfer=round(wfer, 3),
            status=status,
        ))

        window_id += 1
        current_test_start += pd.DateOffset(months=step_months)

    return windows


def _apply_subcomp_recipe(
    data: pd.DataFrame,
    subcomp_filters: dict,
    sc_mom_min: float,
    r_column: str,
) -> np.ndarray:
    """Filter data by sub-component thresholds (Precision Edge), return R values."""
    mask = data["sc_momentum"] >= sc_mom_min
    for col, spec in subcomp_filters.items():
        thresh = spec["threshold"] if isinstance(spec, dict) else spec
        if col in data.columns:
            mask &= data[col] >= thresh
    filtered = data.loc[mask, r_column].dropna()
    return filtered.values


def _apply_recipe(data: pd.DataFrame, recipe: RecipeResult, r_column: str) -> np.ndarray:
    """Filter data by recipe thresholds, return R values."""
    mask = data["sc_momentum"] >= recipe.sc_mom_min
    if recipe.flow_min > 0 and "flow_100" in data.columns:
        mask &= data["flow_100"] >= recipe.flow_min
    if recipe.energy_min > 0 and "energy_100" in data.columns:
        mask &= data["energy_100"] >= recipe.energy_min
    if recipe.structure_min > 0 and "structure_100" in data.columns:
        mask &= data["structure_100"] >= recipe.structure_min
    if recipe.mp_min > 0 and "mp_100" in data.columns:
        mask &= data["mp_100"] >= recipe.mp_min
    if recipe.elder_min > 0 and "elder_score" in data.columns:
        mask &= data["elder_score"] >= recipe.elder_min
    if recipe.fip_min > 0 and "fip_quality" in data.columns:
        mask &= data["fip_quality"] >= recipe.fip_min
    if recipe.phase_filter != "ANY" and "mp_state" in data.columns:
        if recipe.phase_filter == "BUILDING":
            mask &= data["mp_state"] == "BUILDING"
        elif recipe.phase_filter == "BUILDING+STRONG":
            mask &= data["mp_state"].isin(["BUILDING", "STRONG"])
    if recipe.squeeze_min > 0 and "squeeze_score" in data.columns:
        mask &= data["squeeze_score"] >= recipe.squeeze_min

    filtered = data.loc[mask, r_column].dropna()
    return filtered.values


def format_walkforward(windows: list[WFWindow], mode_label: str = "") -> str:
    """Format walk-forward results with honest reporting."""
    if not windows:
        return "No walk-forward windows completed (need >= 20 OOS trades per window)."

    lines = []
    lines.append("=" * 100)
    label = f"  WALK-FORWARD ANALYSIS{' — ' + mode_label if mode_label else ''}"
    lines.append(label)
    lines.append("=" * 100)
    lines.append(
        f"  {'#':>2} {'Train':>22} {'Test':>22} | "
        f"{'IS_R':>6} {'OOS_R':>6} {'N_OOS':>5} {'WinR':>5} {'WFER':>6} {'Status':>8}"
    )
    lines.append("-" * 100)

    for w in windows:
        lines.append(
            f"  {w.window_id:>2} {w.train_start} to {w.train_end} "
            f"{w.test_start} to {w.test_end} | "
            f"{w.is_avg_r:>+5.3f} {w.oos_avg_r:>+5.3f} {w.oos_n_trades:>5} "
            f"{w.oos_win_rate:>4.1%} {w.wfer:>+5.2f}  {w.status:>8}"
        )

    # Health summary with median (robust to outliers)
    wfers = [w.wfer for w in windows]
    median_wfer = float(np.median(wfers))
    mean_wfer = float(np.mean(wfers))
    n_robust = sum(1 for w in wfers if w >= 0.50)
    n_ok = sum(1 for w in wfers if 0.30 <= w < 0.50)
    n_fragile = sum(1 for w in wfers if 0.0 <= w < 0.30)
    n_broken = sum(1 for w in wfers if w < 0)
    n_total = len(wfers)
    pass_pct = (n_robust + n_ok) / n_total * 100 if n_total > 0 else 0

    # Worst consecutive broken/fragile streak
    max_bad_streak = 0
    current_streak = 0
    for w in wfers:
        if w < 0.30:
            current_streak += 1
            max_bad_streak = max(max_bad_streak, current_streak)
        else:
            current_streak = 0

    # Recent vs early performance
    half = n_total // 2
    if half > 0:
        early_wfers = wfers[:half]
        recent_wfers = wfers[half:]
        early_median = float(np.median(early_wfers))
        recent_median = float(np.median(recent_wfers))
    else:
        early_median = median_wfer
        recent_median = median_wfer

    lines.append("-" * 100)
    lines.append(f"  WINDOW HEALTH: {n_robust} ROBUST | {n_ok} OK | {n_fragile} FRAGILE | {n_broken} BROKEN  ({n_total} total)")
    lines.append(f"  Median WFER: {median_wfer:+.3f} | Mean WFER: {mean_wfer:+.3f}")
    lines.append(f"  Pass rate (WFER >= 0.30): {pass_pct:.0f}%")
    lines.append(f"  Worst bad streak: {max_bad_streak} consecutive FRAGILE/BROKEN windows")
    lines.append(f"  Early half median: {early_median:+.3f} | Recent half median: {recent_median:+.3f}")

    if median_wfer >= 0.50:
        verdict = "ROBUST — recipe generalises well across time."
    elif median_wfer >= 0.30:
        verdict = "ACCEPTABLE — some degradation but tradeable."
    elif median_wfer >= 0:
        verdict = "FRAGILE — recipe may be curve-fit. Consider looser filters."
    else:
        verdict = "BROKEN — recipe loses money out of sample."

    # Override: if recent half is significantly better
    if recent_median >= 0.50 and early_median < 0.30 and median_wfer < 0.30:
        verdict += "\n  NOTE: Recent windows are ROBUST. Early weakness may be regime-driven (bear market 2022-2023)."

    lines.append(f"  VERDICT: {verdict}")
    lines.append("=" * 100)

    return "\n".join(lines)


def walk_forward_summary(windows: list[WFWindow]) -> dict:
    """Return a summary dict for JSON export."""
    if not windows:
        return {"n_windows": 0, "median_wfer": 0.0, "pass_rate": 0.0}

    wfers = [w.wfer for w in windows]
    n_total = len(wfers)
    n_pass = sum(1 for w in wfers if w >= 0.30)

    return {
        "n_windows": n_total,
        "median_wfer": round(float(np.median(wfers)), 3),
        "mean_wfer": round(float(np.mean(wfers)), 3),
        "pass_rate": round(n_pass / n_total, 3) if n_total > 0 else 0.0,
        "n_robust": sum(1 for w in wfers if w >= 0.50),
        "n_ok": sum(1 for w in wfers if 0.30 <= w < 0.50),
        "n_fragile": sum(1 for w in wfers if 0.0 <= w < 0.30),
        "n_broken": sum(1 for w in wfers if w < 0),
        "recent_half_median": round(float(np.median(wfers[n_total // 2:])), 3) if n_total > 1 else 0.0,
        "early_half_median": round(float(np.median(wfers[:n_total // 2])), 3) if n_total > 1 else 0.0,
    }
