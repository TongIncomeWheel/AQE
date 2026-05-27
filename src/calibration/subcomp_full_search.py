"""Full sub-component search — ALL engines, ALL sub-components.

Phase 1: Univariate screen of every numeric column for IC + WR lift
Phase 2: Greedy forward selection — add the filter that lifts WR most
Phase 3: Local grid refinement around the best recipe
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.calibration.subcomp_optimizer import detect_signals, compute_outcomes


# Columns to SKIP (identifiers, price, outcome vars, not useful as filters)
SKIP_COLS = {
    "ticker", "date", "close", "atr14", "bd_mode", "mp_state",
    "impulse_state",  # handled separately as boolean
    "sc_momentum",    # used for signal detection, not filtering
    # Outcome variables (data leak — computed AFTER entry)
    "exit_bar", "exit_type", "r_realized", "peak_r", "peak_tier",
    "exit_price", "entry_price", "stop_price",
}

# Engine labels for display
ENGINE_MAP = {
    "volume_score": "Flow", "accum_score": "Flow", "flow_score": "Flow",
    "mfi": "Flow", "cmf": "Flow", "flow_100": "Flow",
    "en_pos50": "Energy", "en_trend_bars": "Energy", "energy_100": "Energy",
    "roc_zscore": "Energy", "exhaustion_score": "Energy", "squeeze_score": "Energy",
    "trend_score": "Structure", "ms_p50": "Structure", "ms_pos_score": "Structure",
    "base_days": "Structure", "base_score": "Structure", "wk_score": "Structure",
    "structure_100": "Structure",
    "elder_score": "MP", "mp_adx_score": "MP", "adx_val": "MP",
    "di_bullish": "MP", "mp_100": "MP",
    "bq_100": "BQ", "bq_base_days": "BQ", "bq_base_dur": "BQ",
    "bq_ema_conv": "BQ", "bq_range_tight": "BQ", "bq_vol_dry": "BQ",
    "pipe_rank": "PipeRank", "pipe_tier": "PipeRank", "excess_return": "PipeRank",
    "rs_vs_spy": "PipeRank", "rs_accel": "PipeRank", "rs_accel_score": "PipeRank",
    "pr_adx_score": "PipeRank", "pr_rsi_score": "PipeRank", "pr_vol_score": "PipeRank",
    "pr_ma_score": "PipeRank", "pr_ret_12m": "PipeRank", "rs_spy_score": "PipeRank",
    "sc_position": "Scoring", "k39_value": "Scoring", "momentum_composite": "Scoring",
    "abs_mom_score": "Scoring", "rel_mom_score": "Scoring",
    "price_action_score": "Scoring", "vp_position_score": "Scoring",
    "resist_score": "Scoring", "skew_score": "Scoring",
    "ha_quality_count": "Scoring", "ext_score": "Scoring",
    "fip_quality": "Scoring", "earn_score": "Scoring",
    "atr_score": "Scoring",
}


def main():
    data_dir = ROOT / "data"
    scores = pd.read_parquet(data_dir / "scores_daily.parquet")
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()
    panel = pd.read_parquet(data_dir / "panel_daily.parquet")
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    print("Detecting signals...")
    signals = detect_signals(scores)
    print("Computing outcomes...")
    trades = compute_outcomes(signals, panel)
    print(f"{len(trades)} trades total")

    # Derive impulse_green boolean
    if "impulse_state" in trades.columns:
        trades["impulse_green"] = trades["impulse_state"] == "GREEN"

    # ================================================================
    # PHASE 1: Univariate screen of ALL numeric columns
    # ================================================================
    print()
    print("=" * 70)
    print("  PHASE 1: UNIVARIATE SCREEN — ALL SUB-COMPONENTS")
    print("  IC with R-multiple + WR lift at median split")
    print("=" * 70)

    r_vals = trades["r_realized"].values
    wins_all = r_vals[r_vals > 0]
    losses_all = r_vals[r_vals <= 0]
    wr_base = len(wins_all) / len(r_vals)

    numeric_cols = []
    for col in trades.columns:
        if col in SKIP_COLS or col == "r_realized":
            continue
        if trades[col].dtype in (np.float64, np.float32, np.int64, np.int32, np.bool_):
            non_null = trades[col].dropna()
            if len(non_null) > 100 and non_null.nunique() > 2:
                numeric_cols.append(col)

    # Also add impulse_green if it exists
    if "impulse_green" in trades.columns and "impulse_green" not in numeric_cols:
        numeric_cols.append("impulse_green")

    results = []
    for col in numeric_cols:
        vals = trades[col].values
        valid = ~np.isnan(vals.astype(float))
        v = vals[valid].astype(float)
        r = r_vals[valid]

        if len(v) < 50:
            continue

        # IC: Pearson correlation with R-multiple
        if np.std(v) > 0:
            ic = float(np.corrcoef(v, r)[0, 1])
        else:
            ic = 0.0

        # WR lift: above-median vs below-median win rate
        med = np.median(v)
        above = r[v > med]
        below = r[v <= med]
        if len(above) > 10 and len(below) > 10:
            wr_above = np.sum(above > 0) / len(above)
            wr_below = np.sum(below > 0) / len(below)
            wr_lift = wr_above - wr_below
        else:
            wr_lift = 0.0

        # Best single-threshold WR (try p25, p50, p75)
        best_wr = 0
        best_thresh = 0
        best_n = 0
        for pct in [25, 50, 75, 90]:
            thresh = np.percentile(v, pct)
            mask_above = v >= thresh
            n_above = np.sum(mask_above)
            if n_above >= 50:
                wr_t = np.sum(r[mask_above] > 0) / n_above
                if wr_t > best_wr:
                    best_wr = wr_t
                    best_thresh = thresh
                    best_n = n_above

        engine = ENGINE_MAP.get(col, "?")
        results.append({
            "col": col,
            "engine": engine,
            "ic": ic,
            "wr_lift": wr_lift,
            "best_wr": best_wr,
            "best_thresh": best_thresh,
            "best_n": best_n,
            "combined": abs(ic) + abs(wr_lift),  # ranking metric
        })

    # Sort by combined predictive power
    results.sort(key=lambda x: -x["combined"])

    print(f"\n  Screened {len(numeric_cols)} numeric columns across all engines")
    print(f"  Baseline WR: {wr_base*100:.1f}%\n")
    print(f"  {'Rank':<5} {'Column':<22} {'Engine':<10} {'IC':>7} {'WR Lift':>8} "
          f"{'Best WR':>8} {'Thresh':>8} {'Trades':>7}")
    print("  " + "-" * 85)

    for i, r in enumerate(results[:35], 1):
        print(f"  {i:<5} {r['col']:<22} {r['engine']:<10} {r['ic']:>+.4f} "
              f"{r['wr_lift']:>+.4f} {r['best_wr']*100:>7.1f}% "
              f"{r['best_thresh']:>8.1f} {r['best_n']:>7}")

    # ================================================================
    # PHASE 2: Greedy forward selection
    # ================================================================
    print()
    print("=" * 70)
    print("  PHASE 2: GREEDY FORWARD SELECTION")
    print("  Start with best single filter, add what lifts WR most")
    print("=" * 70)

    # Build candidate thresholds for all top columns
    top_cols = [r["col"] for r in results[:25]]  # top 25 predictors
    candidates = {}
    for col in top_cols:
        vals = trades[col].dropna().values.astype(float)
        if len(vals) < 50:
            continue
        if col == "impulse_green":
            candidates[col] = [True]
        else:
            # Use percentiles as thresholds
            pcts = [25, 50, 75, 90]
            thresholds = sorted(set(round(float(np.percentile(vals, p)), 2) for p in pcts))
            candidates[col] = thresholds

    # Convert trade data to numpy for speed
    trade_r = trades["r_realized"].values
    trade_arrays = {}
    for col in candidates:
        if col in trades.columns:
            trade_arrays[col] = trades[col].values.astype(float)

    # Greedy forward selection
    active_filters = {}  # col -> threshold
    base_mask = np.ones(len(trades), dtype=bool)
    best_recipes = []

    print(f"\n  Candidates: {len(candidates)} columns with thresholds")
    print(f"  Starting WR: {wr_base*100:.1f}% on {len(trades)} trades\n")

    for step in range(15):  # max 15 filters
        current_mask = base_mask.copy()
        for col, thresh in active_filters.items():
            arr = trade_arrays[col]
            if isinstance(thresh, bool):
                current_mask &= arr == float(thresh)
            else:
                current_mask &= arr >= thresh

        current_n = np.sum(current_mask)
        current_r = trade_r[current_mask]
        if current_n < 30:
            break
        current_wr = np.sum(current_r > 0) / current_n

        best_improvement = 0
        best_col = None
        best_thresh = None
        best_new_wr = 0
        best_new_n = 0

        for col, thresholds in candidates.items():
            if col in active_filters:
                continue
            if col not in trade_arrays:
                continue
            arr = trade_arrays[col]

            for thresh in thresholds:
                if isinstance(thresh, bool):
                    new_mask = current_mask & (arr == float(thresh))
                else:
                    new_mask = current_mask & (arr >= thresh)

                n = np.sum(new_mask)
                if n < 50:  # minimum trades
                    continue

                r_sub = trade_r[new_mask]
                wr = np.sum(r_sub > 0) / n
                improvement = wr - current_wr

                if improvement > best_improvement:
                    best_improvement = improvement
                    best_col = col
                    best_thresh = thresh
                    best_new_wr = wr
                    best_new_n = n

        if best_col is None or best_improvement < 0.005:  # <0.5% lift = stop
            print(f"  Step {step+1}: No filter lifts WR by 0.5%+ — stopping")
            break

        active_filters[best_col] = best_thresh
        engine = ENGINE_MAP.get(best_col, "?")
        print(f"  Step {step+1}: +{best_col}>={best_thresh} ({engine}) -> "
              f"WR={best_new_wr*100:.1f}% | {best_new_n} trades | "
              f"+{best_improvement*100:.1f}pp lift")

        # Record this recipe state
        final_mask = base_mask.copy()
        for col, thresh in active_filters.items():
            arr = trade_arrays[col]
            if isinstance(thresh, bool):
                final_mask &= arr == float(thresh)
            else:
                final_mask &= arr >= thresh

        final_r = trade_r[final_mask]
        final_n = np.sum(final_mask)
        wins = final_r[final_r > 0]
        losses = final_r[final_r <= 0]
        avg_win = float(np.mean(wins)) if len(wins) else 0
        avg_loss = float(np.mean(losses)) if len(losses) else 0
        wr = len(wins) / final_n
        payoff = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        exp = wr * avg_win - (1 - wr) * abs(avg_loss)

        best_recipes.append({
            "filters": dict(active_filters),
            "n": final_n,
            "wr": wr,
            "avg_r": float(np.mean(final_r)),
            "exp": exp,
            "payoff": payoff,
            "n_filters": len(active_filters),
        })

    # ================================================================
    # PHASE 3: Local grid refinement
    # ================================================================
    if active_filters:
        print()
        print("=" * 70)
        print("  PHASE 3: LOCAL GRID REFINEMENT")
        print("  Testing threshold variations around best recipe")
        print("=" * 70)

        # For each filter, try shifting threshold ±1 step
        base_recipe = dict(active_filters)
        refinements = [base_recipe]

        for col, thresh in base_recipe.items():
            if isinstance(thresh, bool):
                continue
            arr = trade_arrays[col]
            vals = arr[~np.isnan(arr)]
            # Try nearby thresholds
            for delta_pct in [-10, -5, +5, +10]:
                new_thresh = round(thresh * (1 + delta_pct / 100), 2)
                if new_thresh == thresh:
                    continue
                variant = dict(base_recipe)
                variant[col] = new_thresh
                refinements.append(variant)

        best_refined = []
        for recipe_filters in refinements:
            mask = np.ones(len(trades), dtype=bool)
            for col, thresh in recipe_filters.items():
                if col not in trade_arrays:
                    continue
                arr = trade_arrays[col]
                if isinstance(thresh, bool):
                    mask &= arr == float(thresh)
                else:
                    mask &= arr >= thresh

            n = np.sum(mask)
            if n < 50:
                continue

            r_sub = trade_r[mask]
            wins = r_sub[r_sub > 0]
            losses = r_sub[r_sub <= 0]
            wr = len(wins) / n
            avg_win = float(np.mean(wins)) if len(wins) else 0
            avg_loss = float(np.mean(losses)) if len(losses) else 0
            payoff = avg_win / abs(avg_loss) if avg_loss != 0 else 0
            exp = wr * avg_win - (1 - wr) * abs(avg_loss)

            best_refined.append({
                "filters": recipe_filters,
                "n": n,
                "wr": wr,
                "avg_r": float(np.mean(r_sub)),
                "exp": exp,
                "payoff": payoff,
            })

        best_refined.sort(key=lambda x: (-x["wr"], -x["exp"]))

        print(f"\n  Tested {len(refinements)} variants\n")
        for i, r in enumerate(best_refined[:5], 1):
            fstr = " & ".join(f"{k}>={v}" for k, v in r["filters"].items())
            print(f"  #{i}: WR={r['wr']*100:.1f}% | {r['n']} trades | "
                  f"Exp={r['exp']:+.4f}R | Payoff={r['payoff']:.2f}:1")
            print(f"       {fstr}")
            print()

    # ================================================================
    # FINAL COMPARISON
    # ================================================================
    print("=" * 70)
    print("  FINAL COMPARISON")
    print("=" * 70)

    # Baseline
    w_all = r_vals[r_vals > 0]
    l_all = r_vals[r_vals <= 0]
    wr_all = len(w_all) / len(r_vals)
    exp_all = wr_all * np.mean(w_all) - (1-wr_all) * abs(np.mean(l_all))
    print(f"  BASELINE (all signals):     WR={wr_all*100:.1f}% | {len(r_vals):>6} trades | Exp={exp_all:+.4f}R")

    # Current aggregate recipe
    agg_mask = (
        (trades["sc_momentum"] >= 75) & (trades["flow_100"] >= 80) &
        (trades["energy_100"] >= 64) & (trades["structure_100"] >= 60) &
        (trades["mp_100"] >= 60) & (trades["elder_score"] >= 7)
    )
    agg = trades[agg_mask]
    if len(agg):
        agg_rs = agg["r_realized"].values
        agg_w = agg_rs[agg_rs > 0]
        agg_l = agg_rs[agg_rs <= 0]
        agg_wr = len(agg_w) / len(agg)
        agg_exp = agg_wr * np.mean(agg_w) - (1-agg_wr) * abs(np.mean(agg_l))
        print(f"  CURRENT RECIPE (aggregate): WR={agg_wr*100:.1f}% | {len(agg):>6} trades | Exp={agg_exp:+.4f}R")

    # Previous deep search winner
    prev_mask = (
        (trades["volume_score"] >= 5) & (trades["trend_score"] >= 12) &
        (trades["elder_score"] >= 8) & (trades["adx_val"] >= 20) &
        (trades["squeeze_score"] >= 5) & (trades["excess_return"] >= 5) &
        (trades["rs_accel"] >= 5)
    )
    prev = trades[prev_mask]
    if len(prev):
        prev_rs = prev["r_realized"].values
        prev_w = prev_rs[prev_rs > 0]
        prev_l = prev_rs[prev_rs <= 0]
        prev_wr = len(prev_w) / len(prev)
        prev_exp = prev_wr * np.mean(prev_w) - (1-prev_wr) * abs(np.mean(prev_l))
        print(f"  PREV WR CHAMPION (11-col):  WR={prev_wr*100:.1f}% | {len(prev):>6} trades | Exp={prev_exp:+.4f}R")

    # Best from this full search
    if best_recipes:
        best = max(best_recipes, key=lambda x: x["wr"])
        fstr = " & ".join(f"{k}>={v}" for k, v in best["filters"].items())
        print(f"  FULL SEARCH WINNER:         WR={best['wr']*100:.1f}% | {best['n']:>6} trades | Exp={best['exp']:+.4f}R")
        print(f"       {fstr}")

    # Engine coverage report
    if best_recipes:
        best = max(best_recipes, key=lambda x: x["wr"])
        engines_used = set()
        for col in best["filters"]:
            engines_used.add(ENGINE_MAP.get(col, "Unknown"))
        print(f"\n  Engines represented: {', '.join(sorted(engines_used))}")
        all_engines = {"Flow", "Energy", "Structure", "MP", "BQ", "PipeRank", "Scoring"}
        missing = all_engines - engines_used
        if missing:
            print(f"  Missing engines:    {', '.join(sorted(missing))}")

    print("=" * 70)


if __name__ == "__main__":
    main()
