"""Frequency-aware sub-component search — ALL engines, ~10 signals/week target.

Constraint: minimum 2,000 trades (~7/week over 286 weeks).
Goal: maximize WR while maintaining actionable signal frequency.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.calibration.subcomp_optimizer import detect_signals, compute_outcomes

# Columns to SKIP
SKIP_COLS = {
    "ticker", "date", "close", "atr14", "bd_mode", "mp_state",
    "impulse_state", "sc_momentum",
    "exit_bar", "exit_type", "r_realized", "peak_r", "peak_tier",
    "exit_price", "entry_price", "stop_price",
}

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
    "fip_quality": "Scoring", "earn_score": "Scoring", "atr_score": "Scoring",
}

# Frequency targets
MIN_TRADES = 2000       # ~7/week floor
TARGET_TRADES = 2860    # ~10/week sweet spot
WEEKS = 286             # total weeks in dataset


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
    print(f"{len(trades)} trades total = {len(trades)/WEEKS:.1f}/week")

    if "impulse_state" in trades.columns:
        trades["impulse_green"] = trades["impulse_state"] == "GREEN"

    r_vals = trades["r_realized"].values
    wins_all = r_vals[r_vals > 0]
    losses_all = r_vals[r_vals <= 0]
    wr_base = len(wins_all) / len(r_vals)
    avg_win_base = float(np.mean(wins_all))
    avg_loss_base = float(np.mean(losses_all))
    exp_base = wr_base * avg_win_base - (1 - wr_base) * abs(avg_loss_base)

    print(f"Baseline: WR={wr_base*100:.1f}% | Exp={exp_base:+.4f}R | "
          f"Payoff={avg_win_base/abs(avg_loss_base):.2f}:1")

    # ================================================================
    # Build candidate thresholds for ALL numeric columns
    # ================================================================
    numeric_cols = []
    for col in trades.columns:
        if col in SKIP_COLS or col == "r_realized":
            continue
        if trades[col].dtype in (np.float64, np.float32, np.int64, np.int32, np.bool_):
            non_null = trades[col].dropna()
            if len(non_null) > 1000 and non_null.nunique() > 2:
                numeric_cols.append(col)
    if "impulse_green" in trades.columns and "impulse_green" not in numeric_cols:
        numeric_cols.append("impulse_green")

    print(f"\n{len(numeric_cols)} candidate columns across all engines")

    # Pre-compute numpy arrays for speed
    trade_r = trades["r_realized"].values
    trade_arrays = {}
    candidates = {}  # col -> list of thresholds

    for col in numeric_cols:
        arr = trades[col].values.astype(float)
        trade_arrays[col] = arr
        vals = arr[~np.isnan(arr)]
        if col == "impulse_green":
            candidates[col] = [True]
        else:
            # Use percentiles: 25th, 50th, 75th
            # But only keep thresholds that leave >= MIN_TRADES
            thresholds = []
            for pct in [25, 40, 50, 60, 75]:
                t = round(float(np.percentile(vals, pct)), 2)
                n_above = np.sum(arr >= t)
                if n_above >= MIN_TRADES:
                    thresholds.append(t)
            if thresholds:
                candidates[col] = sorted(set(thresholds))

    print(f"{len(candidates)} columns with valid thresholds (>= {MIN_TRADES} trades)")

    # ================================================================
    # PHASE 1: Single-filter screen (what lifts WR most alone?)
    # ================================================================
    print()
    print("=" * 80)
    print("  PHASE 1: SINGLE FILTER SCREEN (min 2000 trades)")
    print("=" * 80)

    single_results = []
    for col, thresholds in candidates.items():
        arr = trade_arrays[col]
        for thresh in thresholds:
            if isinstance(thresh, bool):
                mask = arr == float(thresh)
            else:
                mask = arr >= thresh
            n = np.sum(mask)
            if n < MIN_TRADES:
                continue
            r_sub = trade_r[mask]
            wins = r_sub[r_sub > 0]
            losses = r_sub[r_sub <= 0]
            wr = len(wins) / n
            avg_w = float(np.mean(wins)) if len(wins) else 0
            avg_l = float(np.mean(losses)) if len(losses) else 0
            payoff = avg_w / abs(avg_l) if avg_l != 0 else 0
            exp = wr * avg_w - (1 - wr) * abs(avg_l)

            single_results.append({
                "col": col, "thresh": thresh, "engine": ENGINE_MAP.get(col, "?"),
                "n": n, "wr": wr, "exp": exp, "payoff": payoff,
                "per_week": n / WEEKS,
            })

    single_results.sort(key=lambda x: (-x["wr"], -x["exp"]))

    print(f"\n  {'Rank':<5} {'Filter':<30} {'Engine':<10} {'WR':>7} "
          f"{'Trades':>7} {'/wk':>6} {'Exp':>9} {'Payoff':>8}")
    print("  " + "-" * 90)
    for i, r in enumerate(single_results[:25], 1):
        print(f"  {i:<5} {r['col']}>={r['thresh']:<17} {r['engine']:<10} "
              f"{r['wr']*100:>6.1f}% {r['n']:>7} {r['per_week']:>5.1f} "
              f"{r['exp']:>+8.4f}R {r['payoff']:>7.2f}:1")

    # ================================================================
    # PHASE 2: Greedy forward selection (floor = 2000 trades)
    # ================================================================
    print()
    print("=" * 80)
    print("  PHASE 2: GREEDY FORWARD SELECTION (min 2000 trades)")
    print("=" * 80)

    active_filters = {}
    best_recipes = []

    print(f"\n  Target: ~{TARGET_TRADES} trades ({TARGET_TRADES/WEEKS:.0f}/week)")
    print(f"  Floor:  {MIN_TRADES} trades ({MIN_TRADES/WEEKS:.0f}/week)")
    print(f"  Starting: WR={wr_base*100:.1f}% on {len(trades)} trades\n")

    for step in range(10):
        # Current state
        current_mask = np.ones(len(trades), dtype=bool)
        for col, thresh in active_filters.items():
            arr = trade_arrays[col]
            if isinstance(thresh, bool):
                current_mask &= arr == float(thresh)
            else:
                current_mask &= arr >= thresh

        current_n = int(np.sum(current_mask))
        if current_n < MIN_TRADES:
            print(f"  Step {step+1}: Below {MIN_TRADES} trade floor -- stopping")
            break

        current_r = trade_r[current_mask]
        current_wr = np.sum(current_r > 0) / current_n

        best_score = -999
        best_col = None
        best_thresh = None
        best_new_wr = 0
        best_new_n = 0
        best_new_exp = 0

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

                n = int(np.sum(new_mask))
                if n < MIN_TRADES:
                    continue

                r_sub = trade_r[new_mask]
                wins = r_sub[r_sub > 0]
                losses = r_sub[r_sub <= 0]
                wr = len(wins) / n
                avg_w = float(np.mean(wins)) if len(wins) else 0
                avg_l = float(np.mean(losses)) if len(losses) else 0
                exp = wr * avg_w - (1 - wr) * abs(avg_l)

                # Score: WR improvement, but penalize for going too far below target
                wr_lift = wr - current_wr
                freq_penalty = max(0, (MIN_TRADES - n) / MIN_TRADES) * 0.1
                score = wr_lift - freq_penalty

                if score > best_score and wr_lift > 0.003:  # at least 0.3pp lift
                    best_score = score
                    best_col = col
                    best_thresh = thresh
                    best_new_wr = wr
                    best_new_n = n
                    best_new_exp = exp

        if best_col is None:
            print(f"  Step {step+1}: No filter lifts WR by 0.3%+ above {MIN_TRADES} floor -- stopping")
            break

        active_filters[best_col] = best_thresh
        engine = ENGINE_MAP.get(best_col, "?")
        wr_lift = best_new_wr - current_wr
        print(f"  Step {step+1}: +{best_col}>={best_thresh} ({engine}) -> "
              f"WR={best_new_wr*100:.1f}% | {best_new_n} trades ({best_new_n/WEEKS:.1f}/wk) | "
              f"Exp={best_new_exp:+.4f}R | +{wr_lift*100:.1f}pp")

        # Record recipe snapshot
        final_mask = np.ones(len(trades), dtype=bool)
        for col, thresh in active_filters.items():
            arr = trade_arrays[col]
            if isinstance(thresh, bool):
                final_mask &= arr == float(thresh)
            else:
                final_mask &= arr >= thresh

        final_r = trade_r[final_mask]
        final_n = int(np.sum(final_mask))
        wins = final_r[final_r > 0]
        losses = final_r[final_r <= 0]
        wr = len(wins) / final_n
        avg_w = float(np.mean(wins)) if len(wins) else 0
        avg_l = float(np.mean(losses)) if len(losses) else 0
        payoff = avg_w / abs(avg_l) if avg_l != 0 else 0
        exp = wr * avg_w - (1 - wr) * abs(avg_l)
        med_r = float(np.median(final_r))

        best_recipes.append({
            "filters": dict(active_filters),
            "n": final_n,
            "wr": wr,
            "avg_r": float(np.mean(final_r)),
            "med_r": med_r,
            "exp": exp,
            "payoff": payoff,
            "per_week": final_n / WEEKS,
            "n_filters": len(active_filters),
            "engines": set(ENGINE_MAP.get(c, "?") for c in active_filters),
        })

    # ================================================================
    # PHASE 3: Also try brute-force 2-filter and 3-filter combos
    # at different frequency tiers
    # ================================================================
    print()
    print("=" * 80)
    print("  PHASE 3: BRUTE-FORCE 2-FILTER & 3-FILTER COMBOS")
    print(f"  Min {MIN_TRADES} trades, ranked by WR")
    print("=" * 80)

    # Flatten all (col, thresh) pairs
    flat_filters = []
    for col, thresholds in candidates.items():
        if col not in trade_arrays:
            continue
        for thresh in thresholds:
            flat_filters.append((col, thresh))

    print(f"\n  {len(flat_filters)} individual filter options")

    # Pre-compute masks for each filter
    filter_masks = []
    for col, thresh in flat_filters:
        arr = trade_arrays[col]
        if isinstance(thresh, bool):
            mask = arr == float(thresh)
        else:
            mask = arr >= thresh
        filter_masks.append(mask)

    # 2-filter combos
    print("  Searching 2-filter combos...")
    t0 = time.time()
    combo2_results = []
    n_flat = len(flat_filters)

    for i in range(n_flat):
        col_i, thresh_i = flat_filters[i]
        mask_i = filter_masks[i]
        for j in range(i + 1, n_flat):
            col_j, thresh_j = flat_filters[j]
            if col_i == col_j:
                continue  # skip same column
            mask_j = filter_masks[j]
            combined = mask_i & mask_j
            n = int(np.sum(combined))
            if n < MIN_TRADES:
                continue
            r_sub = trade_r[combined]
            wins = np.sum(r_sub > 0)
            wr = wins / n
            if wr <= wr_base + 0.02:  # need at least 2pp over baseline
                continue
            avg_w = float(np.mean(r_sub[r_sub > 0])) if wins else 0
            losses = r_sub[r_sub <= 0]
            avg_l = float(np.mean(losses)) if len(losses) else 0
            exp = wr * avg_w - (1 - wr) * abs(avg_l)
            combo2_results.append({
                "filters": {col_i: thresh_i, col_j: thresh_j},
                "n": n, "wr": wr, "exp": exp,
                "per_week": n / WEEKS,
                "engines": {ENGINE_MAP.get(col_i, "?"), ENGINE_MAP.get(col_j, "?")},
            })

    combo2_results.sort(key=lambda x: (-x["wr"], -x["exp"]))
    elapsed2 = time.time() - t0
    print(f"  Found {len(combo2_results)} 2-filter recipes with WR>{(wr_base+0.02)*100:.0f}% "
          f"and {MIN_TRADES}+ trades ({elapsed2:.1f}s)")

    if combo2_results:
        print(f"\n  TOP 10 two-filter combos:")
        for i, r in enumerate(combo2_results[:10], 1):
            fstr = " & ".join(f"{k}>={v}" for k, v in r["filters"].items())
            engines = ",".join(sorted(r["engines"]))
            print(f"  #{i}: WR={r['wr']*100:.1f}% | {r['n']:>5} ({r['per_week']:.1f}/wk) | "
                  f"Exp={r['exp']:+.4f}R | [{engines}]")
            print(f"       {fstr}")

    # 3-filter combos (use top 2-filter results as seeds)
    print(f"\n  Searching 3-filter combos (seeded from top 2-filter)...")
    t0 = time.time()
    combo3_results = []

    # Take top 50 2-filter results as seeds
    seeds = combo2_results[:50]
    for seed in seeds:
        seed_cols = set(seed["filters"].keys())
        # Rebuild seed mask
        seed_mask = np.ones(len(trades), dtype=bool)
        for col, thresh in seed["filters"].items():
            arr = trade_arrays[col]
            if isinstance(thresh, bool):
                seed_mask &= arr == float(thresh)
            else:
                seed_mask &= arr >= thresh

        # Try adding each remaining filter
        for k in range(n_flat):
            col_k, thresh_k = flat_filters[k]
            if col_k in seed_cols:
                continue
            mask_k = filter_masks[k]
            combined = seed_mask & mask_k
            n = int(np.sum(combined))
            if n < MIN_TRADES:
                continue
            r_sub = trade_r[combined]
            wins = np.sum(r_sub > 0)
            wr = wins / n
            if wr <= seed["wr"] + 0.005:  # needs to improve
                continue
            avg_w = float(np.mean(r_sub[r_sub > 0])) if wins else 0
            losses = r_sub[r_sub <= 0]
            avg_l = float(np.mean(losses)) if len(losses) else 0
            exp = wr * avg_w - (1 - wr) * abs(avg_l)

            new_filters = dict(seed["filters"])
            new_filters[col_k] = thresh_k
            combo3_results.append({
                "filters": new_filters,
                "n": n, "wr": wr, "exp": exp,
                "per_week": n / WEEKS,
                "engines": {ENGINE_MAP.get(c, "?") for c in new_filters},
            })

    # Deduplicate by filter set
    seen = set()
    unique3 = []
    for r in combo3_results:
        key = tuple(sorted(r["filters"].items()))
        if key not in seen:
            seen.add(key)
            unique3.append(r)
    unique3.sort(key=lambda x: (-x["wr"], -x["exp"]))

    elapsed3 = time.time() - t0
    print(f"  Found {len(unique3)} unique 3-filter recipes ({elapsed3:.1f}s)")

    if unique3:
        print(f"\n  TOP 10 three-filter combos:")
        for i, r in enumerate(unique3[:10], 1):
            fstr = " & ".join(f"{k}>={v}" for k, v in r["filters"].items())
            engines = ",".join(sorted(r["engines"]))
            print(f"  #{i}: WR={r['wr']*100:.1f}% | {r['n']:>5} ({r['per_week']:.1f}/wk) | "
                  f"Exp={r['exp']:+.4f}R | [{engines}]")
            print(f"       {fstr}")

    # ================================================================
    # FINAL COMPARISON
    # ================================================================
    print()
    print("=" * 80)
    print("  FINAL COMPARISON")
    print("=" * 80)
    print(f"  BASELINE:               WR={wr_base*100:.1f}% | {len(trades):>6} trades ({len(trades)/WEEKS:.0f}/wk) | Exp={exp_base:+.4f}R")

    # Current aggregate
    agg_mask = (
        (trades["sc_momentum"] >= 75) & (trades["flow_100"] >= 80) &
        (trades["energy_100"] >= 64) & (trades["structure_100"] >= 60) &
        (trades["mp_100"] >= 60) & (trades["elder_score"] >= 7)
    )
    agg = trades[agg_mask]
    if len(agg):
        agg_r = agg["r_realized"].values
        agg_w = agg_r[agg_r > 0]
        agg_l = agg_r[agg_r <= 0]
        agg_wr = len(agg_w) / len(agg)
        agg_exp = agg_wr * np.mean(agg_w) - (1-agg_wr) * abs(np.mean(agg_l))
        print(f"  CURRENT AGGREGATE:      WR={agg_wr*100:.1f}% | {len(agg):>6} trades ({len(agg)/WEEKS:.1f}/wk) | Exp={agg_exp:+.4f}R")

    # Greedy winner
    if best_recipes:
        best_greedy = max(best_recipes, key=lambda x: x["wr"])
        fstr = " & ".join(f"{k}>={v}" for k, v in best_greedy["filters"].items())
        eng = ",".join(sorted(best_greedy["engines"]))
        print(f"  GREEDY WINNER:          WR={best_greedy['wr']*100:.1f}% | {best_greedy['n']:>6} trades ({best_greedy['per_week']:.1f}/wk) | Exp={best_greedy['exp']:+.4f}R")
        print(f"       [{eng}] {fstr}")

    # Best 2-filter
    if combo2_results:
        b2 = combo2_results[0]
        fstr = " & ".join(f"{k}>={v}" for k, v in b2["filters"].items())
        eng = ",".join(sorted(b2["engines"]))
        print(f"  BEST 2-FILTER:          WR={b2['wr']*100:.1f}% | {b2['n']:>6} trades ({b2['per_week']:.1f}/wk) | Exp={b2['exp']:+.4f}R")
        print(f"       [{eng}] {fstr}")

    # Best 3-filter
    if unique3:
        b3 = unique3[0]
        fstr = " & ".join(f"{k}>={v}" for k, v in b3["filters"].items())
        eng = ",".join(sorted(b3["engines"]))
        print(f"  BEST 3-FILTER:          WR={b3['wr']*100:.1f}% | {b3['n']:>6} trades ({b3['per_week']:.1f}/wk) | Exp={b3['exp']:+.4f}R")
        print(f"       [{eng}] {fstr}")

    print("=" * 80)


if __name__ == "__main__":
    main()
