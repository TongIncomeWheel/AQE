"""Sub-Component Recipe Optimizer — mine the engine internals.

Instead of searching "Flow >= 80", search the building blocks:
  - MFI (Money Flow Index) thresholds
  - ADX trend strength
  - Squeeze score (volatility compression)
  - RS vs SPY (relative strength)
  - ROC z-score (absolute momentum)
  - Base duration days
  - Volume skew ratios
  - etc.

Approach:
  1. Load scores with ALL sub-components
  2. Detect every SC_MOMENTUM cross-up signal
  3. Compute trade outcome for each signal (simple stop/target)
  4. Rank sub-components by predictive power (correlation with R)
  5. Grid search over the top predictors
  6. Report the best recipes

Usage:
    python -m src.calibration.subcomp_optimizer
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ── Sub-components available for optimization ──────────────────────────
# Each tuple: (column_name, display_name, search_thresholds)
# Only include numeric, continuous columns that could be meaningful filters.
SUBCOMP_CANDIDATES = [
    # Flow internals
    ("flow_score", "Flow Core", [8, 10, 12, 14]),
    ("accum_score", "Accumulation", [3, 5, 6]),
    ("volume_score", "Volume Score", [3, 5, 6]),
    ("skew_score", "Volume Skew", [1.5, 2.5, 3.0]),
    ("ext_score", "Extension", [-2, 0, 2]),
    ("mfi", "MFI", [40, 50, 60, 70]),
    ("cmf", "CMF", [-0.05, 0.0, 0.05, 0.10]),
    # Energy internals
    ("vp_position_score", "VP Position", [8, 10, 13, 15]),
    ("price_action_score", "Price Action", [3, 5, 7, 9]),
    ("squeeze_score", "Squeeze", [5, 8, 10]),
    ("exhaustion_score", "Exhaustion", [7, 8, 9]),
    ("atr_score", "ATR Expand", [3, 5, 6]),
    ("en_pos50", "Energy Pos50", [30, 50, 65, 80]),
    # Structure internals
    ("rs_spy_score", "RS vs SPY Scr", [5, 8, 10, 12]),
    ("rs_accel_score", "RS Accel Scr", [5, 8, 10]),
    ("base_score", "Base Score", [3, 6, 9, 12]),
    ("ms_pos_score", "Struct Pos50", [5, 8, 10, 13]),
    ("resist_score", "Resist Clear", [3, 5, 7]),
    ("wk_score", "Weekly Trend", [5, 8, 10, 12]),
    ("rs_vs_spy", "RS vs SPY Raw", [0, 5, 10, 15]),
    ("rs_accel", "RS Accel Raw", [0, 3, 5, 8]),
    ("base_days", "Base Days", [5, 10, 20, 30]),
    ("ms_p50", "Struct Range%", [30, 50, 65, 80]),
    # MP internals
    ("abs_mom_score", "Abs Momentum", [10, 15, 20, 25]),
    ("mp_adx_score", "ADX Score (MP)", [10, 15, 20]),
    ("rel_mom_score", "Rel Momentum", [10, 15, 20]),
    ("trend_score", "Trend Score", [8, 12, 15, 18]),
    ("roc_zscore", "ROC Z-Score", [0.0, 0.5, 1.0, 1.5]),
    ("excess_return", "Excess Return", [0, 3, 5, 10]),
    ("adx_val", "ADX Value", [15, 20, 25, 30]),
    # BQ internals
    ("bq_range_tight", "Range Tight", [10, 15, 20, 25]),
    ("bq_vol_dry", "Vol Dry-Up", [10, 15, 20]),
    ("bq_ema_conv", "EMA Converge", [10, 15, 20]),
    # Pipeline Rank internals
    ("pr_rsi_score", "RSI Score", [8, 12, 15, 18]),
    ("pr_ma_score", "MA Stack", [8, 12, 15, 18]),
    ("pr_vol_score", "PR Vol Score", [8, 12, 15]),
    # Aggregate gates (keep Elder as a gate)
    ("elder_score", "Elder Impulse", [7, 8, 9]),
]


@dataclass
class SubcompRecipe:
    """A recipe built from sub-component filters."""
    filters: dict[str, float]        # column_name → minimum threshold
    n_trades: int
    win_rate: float
    avg_r: float
    median_r: float
    avg_win_r: float
    avg_loss_r: float
    payoff_ratio: float
    expectancy: float                # win_rate * avg_win - loss_rate * avg_loss
    edge_score: float                # composite ranking metric


def detect_signals(scores: pd.DataFrame) -> pd.DataFrame:
    """Find all SC_MOMENTUM cross-up-above-50 signals."""
    signals = []
    for ticker, grp in scores.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if "sc_momentum" not in grp.columns:
            continue
        sc = grp["sc_momentum"].values
        for i in range(1, len(sc)):
            if sc[i] >= 50.0 and sc[i - 1] < 50.0:
                signals.append(grp.iloc[i].to_dict())
    return pd.DataFrame(signals)


def compute_outcomes(
    signals: pd.DataFrame,
    panel: pd.DataFrame,
    max_bars: int = 63,
) -> pd.DataFrame:
    """For each signal, compute R-multiple using simple stop/target."""
    results = []
    panel_groups = {t: g.sort_values("date").reset_index(drop=True)
                    for t, g in panel.groupby("ticker")}

    for _, sig in signals.iterrows():
        ticker = sig["ticker"]
        entry_date = pd.Timestamp(sig["date"])
        atr14_val = sig.get("atr14", 0)

        if ticker not in panel_groups or atr14_val <= 0:
            continue

        p = panel_groups[ticker]
        entry_idx = p.index[p["date"] >= entry_date]
        if len(entry_idx) == 0:
            continue
        idx = entry_idx[0]

        entry_price = float(p.loc[idx, "close"])
        stop = entry_price - 2 * atr14_val
        r_size = entry_price - stop
        if r_size <= 0:
            continue

        # Scan forward
        r_realized = 0.0
        exit_bar = min(max_bars, len(p) - idx - 1)
        for b in range(1, exit_bar + 1):
            bar_idx = idx + b
            lo = float(p.loc[bar_idx, "low"])
            hi = float(p.loc[bar_idx, "high"])
            cl = float(p.loc[bar_idx, "close"])

            # Stop hit?
            if lo <= stop:
                r_realized = -1.0
                exit_bar = b
                break

            # Check close at end
            if b == exit_bar:
                r_realized = (cl - entry_price) / r_size

        row = sig.to_dict()
        row["r_realized"] = r_realized
        row["exit_bar"] = exit_bar
        row["is_win"] = r_realized > 0.0
        results.append(row)

    return pd.DataFrame(results)


def screen_predictive_power(
    trades: pd.DataFrame,
    min_nonzero: int = 50,
) -> list[tuple[str, str, float, float]]:
    """Rank sub-components by predictive power (IC with R-multiple)."""
    results = []
    for col, name, _ in SUBCOMP_CANDIDATES:
        if col not in trades.columns:
            continue
        vals = trades[col].dropna()
        if len(vals) < min_nonzero:
            continue
        valid = trades.dropna(subset=[col, "r_realized"])
        if len(valid) < min_nonzero:
            continue
        ic = valid[col].corr(valid["r_realized"])
        # Also check: does higher value → higher win rate?
        median_val = valid[col].median()
        high = valid[valid[col] >= median_val]
        low = valid[valid[col] < median_val]
        wr_high = high["is_win"].mean() if len(high) > 10 else 0
        wr_low = low["is_win"].mean() if len(low) > 10 else 0
        wr_lift = wr_high - wr_low
        results.append((col, name, ic, wr_lift))

    results.sort(key=lambda x: abs(x[2]), reverse=True)
    return results


def grid_search(
    trades: pd.DataFrame,
    top_features: list[tuple[str, str, list]],
    min_trades: int = 30,
) -> list[SubcompRecipe]:
    """Grid search over top predictive sub-components."""
    # Build threshold grids for selected features
    feature_cols = []
    feature_names = []
    threshold_lists = []

    for col, name, thresholds in top_features:
        if col not in trades.columns:
            continue
        feature_cols.append(col)
        feature_names.append(name)
        # Add "any" option (no filter on this feature)
        threshold_lists.append([None] + thresholds)

    if not feature_cols:
        return []

    total_combos = 1
    for t in threshold_lists:
        total_combos *= len(t)
    print(f"  Grid: {len(feature_cols)} features x {total_combos:,} combos")

    recipes = []
    for combo in product(*threshold_lists):
        # Build filter
        filters = {}
        mask = pd.Series(True, index=trades.index)
        for col, name, thresh in zip(feature_cols, feature_names, combo):
            if thresh is not None:
                mask &= trades[col] >= thresh
                filters[name] = thresh

        if not filters:
            continue  # skip "all None" combo

        filtered = trades[mask]
        n = len(filtered)
        if n < min_trades:
            continue

        rs = filtered["r_realized"].values
        wins = rs[rs > 0]
        losses = rs[rs <= 0]

        win_rate = len(wins) / n if n > 0 else 0
        avg_r = float(np.mean(rs))
        median_r = float(np.median(rs))
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0
        payoff = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        expectancy = win_rate * avg_win - (1 - win_rate) * abs(avg_loss)

        # Edge score: expectancy × sqrt(trades) — rewards both edge and sample size
        edge_score = expectancy * np.sqrt(n)

        recipes.append(SubcompRecipe(
            filters=filters,
            n_trades=n,
            win_rate=win_rate,
            avg_r=avg_r,
            median_r=median_r,
            avg_win_r=avg_win,
            avg_loss_r=avg_loss,
            payoff_ratio=payoff,
            expectancy=expectancy,
            edge_score=edge_score,
        ))

    recipes.sort(key=lambda r: r.edge_score, reverse=True)
    return recipes


def format_recipe(r: SubcompRecipe, rank: int) -> str:
    """Plain-text format for a single recipe."""
    lines = [f"  #{rank}: Edge={r.edge_score:.2f}  ({r.n_trades} trades)"]
    lines.append(f"    Win rate: {r.win_rate*100:.1f}% | Avg R: {r.avg_r:+.3f} | "
                 f"Median R: {r.median_r:+.3f}")
    lines.append(f"    Payoff: {r.payoff_ratio:.2f}:1 "
                 f"(W: {r.avg_win_r:+.3f}R / L: {r.avg_loss_r:.3f}R)")
    lines.append(f"    Expectancy: {r.expectancy:+.4f}R per trade")
    filters_str = " & ".join(f"{k}>={v}" for k, v in r.filters.items())
    lines.append(f"    Recipe: {filters_str}")
    return "\n".join(lines)


def main():
    data_dir = ROOT / "data"
    scores_path = data_dir / "scores_daily.parquet"
    panel_path = data_dir / "panel_daily.parquet"

    if not scores_path.exists() or not panel_path.exists():
        print("[ERROR] Need scores_daily.parquet and panel_daily.parquet")
        return

    print("=" * 70)
    print("  SUB-COMPONENT RECIPE OPTIMIZER")
    print("  Mining engine internals for the sharpest edge")
    print("=" * 70)

    # Load data
    print("\n[1/5] Loading data...")
    scores = pd.read_parquet(scores_path)
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()
    panel = pd.read_parquet(panel_path)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    available = [c for c in scores.columns if c in [x[0] for x in SUBCOMP_CANDIDATES]]
    print(f"  {len(available)} sub-components available in scores data")

    # Detect signals
    print("\n[2/5] Detecting cross-up signals...")
    t0 = time.time()
    signals = detect_signals(scores)
    print(f"  {len(signals)} signals detected in {time.time()-t0:.1f}s")

    # Compute outcomes
    print("\n[3/5] Computing trade outcomes (stop/target scan)...")
    t0 = time.time()
    trades = compute_outcomes(signals, panel)
    n_wins = trades["is_win"].sum()
    print(f"  {len(trades)} trades with outcomes in {time.time()-t0:.1f}s")
    print(f"  Baseline: {n_wins}/{len(trades)} wins ({n_wins/len(trades)*100:.1f}%) | "
          f"Avg R: {trades['r_realized'].mean():+.3f}")

    # Screen predictive power
    print("\n[4/5] Screening sub-component predictive power...")
    rankings = screen_predictive_power(trades)
    print(f"\n  {'Sub-Component':<20} {'IC':>7} {'WR Lift':>8}")
    print(f"  {'-'*20} {'-'*7} {'-'*8}")
    for col, name, ic, wr_lift in rankings[:20]:
        marker = " ***" if abs(ic) > 0.05 else ""
        print(f"  {name:<20} {ic:>+7.4f} {wr_lift:>+7.1%}{marker}")

    # Select top features for grid search
    top_n = 8
    top_features = []
    used_cols = set()
    for col, name, ic, wr_lift in rankings:
        if col in used_cols:
            continue
        # Find the thresholds for this feature
        for fc, fn, ft in SUBCOMP_CANDIDATES:
            if fc == col:
                top_features.append((col, name, ft))
                used_cols.add(col)
                break
        if len(top_features) >= top_n:
            break

    print(f"\n  Selected top {len(top_features)} features for grid search:")
    for col, name, thresholds in top_features:
        print(f"    {name}: thresholds {thresholds}")

    # Grid search
    print(f"\n[5/5] Grid searching...")
    t0 = time.time()
    recipes = grid_search(trades, top_features, min_trades=30)
    print(f"  {len(recipes)} valid recipes found in {time.time()-t0:.1f}s")

    # Report top 10
    print(f"\n{'='*70}")
    print(f"  TOP 10 SUB-COMPONENT RECIPES (by edge score)")
    print(f"  Edge = expectancy x sqrt(trades) — rewards both sharpness and volume")
    print(f"{'='*70}")
    for i, r in enumerate(recipes[:10], 1):
        print(format_recipe(r, i))
        print()

    # Compare to current aggregate recipe
    print(f"{'='*70}")
    print(f"  COMPARISON: Current aggregate recipe (SC>=75, Flow>=80, etc.)")
    print(f"{'='*70}")
    agg_mask = (
        (trades["sc_momentum"] >= 75) &
        (trades["flow_100"] >= 80) &
        (trades["energy_100"] >= 64) &
        (trades["structure_100"] >= 60) &
        (trades["mp_100"] >= 60) &
        (trades["elder_score"] >= 7)
    )
    agg = trades[agg_mask]
    if len(agg) > 0:
        agg_rs = agg["r_realized"].values
        agg_wins = agg_rs[agg_rs > 0]
        agg_losses = agg_rs[agg_rs <= 0]
        agg_wr = len(agg_wins) / len(agg)
        agg_avg_r = float(np.mean(agg_rs))
        agg_payoff = float(np.mean(agg_wins)) / abs(float(np.mean(agg_losses))) if len(agg_losses) > 0 else 0
        agg_exp = agg_wr * float(np.mean(agg_wins)) - (1-agg_wr) * abs(float(np.mean(agg_losses))) if len(agg_losses) > 0 else 0
        print(f"  Trades: {len(agg)} | Win rate: {agg_wr*100:.1f}% | Avg R: {agg_avg_r:+.3f}")
        print(f"  Payoff: {agg_payoff:.2f}:1 | Expectancy: {agg_exp:+.4f}R")
        print(f"  Edge score: {agg_exp * np.sqrt(len(agg)):.2f}")
    else:
        print("  No trades match current recipe in signal universe")

    print(f"\n{'='*70}")

    # Save results
    import json
    out = {
        "feature_rankings": [
            {"column": col, "name": name, "ic": round(ic, 4), "wr_lift": round(wr_lift, 4)}
            for col, name, ic, wr_lift in rankings[:25]
        ],
        "top_recipes": [
            {
                "rank": i + 1,
                "filters": r.filters,
                "n_trades": r.n_trades,
                "win_rate": round(r.win_rate, 4),
                "avg_r": round(r.avg_r, 4),
                "median_r": round(r.median_r, 4),
                "payoff_ratio": round(r.payoff_ratio, 3),
                "expectancy": round(r.expectancy, 5),
                "edge_score": round(r.edge_score, 3),
            }
            for i, r in enumerate(recipes[:20])
        ],
        "baseline": {
            "n_trades": len(trades),
            "win_rate": round(float(trades["is_win"].mean()), 4),
            "avg_r": round(float(trades["r_realized"].mean()), 4),
        },
    }
    out_path = data_dir / "subcomp_optimizer_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Results saved to {out_path}")


if __name__ == "__main__":
    main()
