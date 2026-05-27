"""Run walk-forward analysis on existing signal+outcome data.

Usage:
    python -m src.calibration.run_walkforward              # fixed-recipe (default)
    python -m src.calibration.run_walkforward --reoptimize  # re-optimize per window
    python -m src.calibration.run_walkforward --anchored    # anchored mode
    python -m src.calibration.run_walkforward --both        # run both fixed + reopt

Default mode: fixed-recipe. Holds your active recipe constant across all windows
to answer "does MY recipe generalise?" This is the number that matters for trading.

--reoptimize runs classic Pardo walk-forward (re-optimizes per window).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.calibration.recipe_optimizer import RecipeResult
from src.calibration.walkforward import (
    walk_forward_analysis,
    format_walkforward,
    walk_forward_summary,
)


def _load_active_recipe() -> RecipeResult | None:
    """Load active recipe from JSON and convert to RecipeResult."""
    recipe_path = ROOT / "data" / "active_recipe.json"
    if not recipe_path.exists():
        return None
    with open(recipe_path) as f:
        raw = json.load(f)
    return RecipeResult(
        sc_mom_min=raw.get("sc_mom_min", 75),
        flow_min=raw.get("flow_min", 80),
        energy_min=raw.get("energy_min", 64),
        structure_min=raw.get("structure_min", 60),
        mp_min=raw.get("mp_min", 60),
        elder_min=raw.get("elder_min", 0),
        fip_min=raw.get("fip_min", 0),
        phase_filter=raw.get("phase_filter", "ANY"),
        squeeze_min=raw.get("squeeze_min", 0),
        n_trades=0, win_rate=0, non_loss_rate=0, avg_r=0,
        median_r=0, expectancy_r=0, total_r=0, sharpe=0,
        trades_per_week=0, target_distance=0, score=0, dsr=0, dsr_pass=False,
    )


def main():
    args = set(sys.argv[1:])
    anchored = "--anchored" in args
    do_reopt = "--reoptimize" in args or "--both" in args
    do_fixed = "--both" in args or not do_reopt
    mode = "anchored" if anchored else "rolling"

    data_dir = ROOT / "data"
    panel_path = data_dir / "panel_daily.parquet"
    scores_path = data_dir / "scores_daily.parquet"

    if not panel_path.exists() or not scores_path.exists():
        print("[wf] Missing data. Run build_panel.bat and build_scores.bat first.")
        return

    print("[wf] Loading data...")
    panel = pd.read_parquet(panel_path)
    scores = pd.read_parquet(scores_path)

    print("[wf] Detecting entry signals with DSL outcomes...")
    from src.calibration.run_optimizer import _detect_signals_with_outcomes
    outcomes = _detect_signals_with_outcomes(scores, panel)
    print(f"[wf] {len(outcomes)} signals with outcomes")

    if outcomes.empty:
        print("[wf] No signals. Cannot run walk-forward.")
        return

    all_results = {}

    # ---- Fixed-recipe walk-forward ----
    if do_fixed:
        recipe = _load_active_recipe()
        if recipe is None:
            print("[wf] No active_recipe.json found. Run the optimizer first.")
        else:
            print(f"\n[wf] === FIXED-RECIPE WALK-FORWARD ({mode} mode) ===")
            print(f"[wf] Recipe: SC>={recipe.sc_mom_min} Flow>={recipe.flow_min} "
                  f"Energy>={recipe.energy_min} Struct>={recipe.structure_min} "
                  f"MP>={recipe.mp_min} Elder>={recipe.elder_min}")
            t0 = time.time()
            fixed_windows = walk_forward_analysis(
                outcomes,
                r_column="dsl_r_realized",
                mode=mode,
                train_months=12,
                test_months=3,
                step_months=1,
                fixed_recipe=recipe,
            )
            elapsed = time.time() - t0
            print(f"[wf] Completed {len(fixed_windows)} windows in {elapsed:.1f}s")

            report = format_walkforward(fixed_windows, mode_label="FIXED RECIPE")
            print(report)

            summary = walk_forward_summary(fixed_windows)
            all_results["fixed_recipe"] = {
                "summary": summary,
                "windows": [{
                    "window_id": w.window_id,
                    "train_start": w.train_start,
                    "train_end": w.train_end,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    "is_avg_r": w.is_avg_r,
                    "oos_avg_r": w.oos_avg_r,
                    "oos_n_trades": w.oos_n_trades,
                    "oos_win_rate": w.oos_win_rate,
                    "wfer": w.wfer,
                    "status": w.status,
                } for w in fixed_windows],
            }

    # ---- Re-optimize walk-forward (classic Pardo) ----
    if do_reopt:
        print(f"\n[wf] === RE-OPTIMIZE WALK-FORWARD ({mode} mode) ===")
        t0 = time.time()
        reopt_windows = walk_forward_analysis(
            outcomes,
            r_column="dsl_r_realized",
            mode=mode,
            train_months=12,
            test_months=3,
            step_months=1,
            fixed_recipe=None,
        )
        elapsed = time.time() - t0
        print(f"[wf] Completed {len(reopt_windows)} windows in {elapsed:.1f}s")

        report = format_walkforward(reopt_windows, mode_label="RE-OPTIMIZE PER WINDOW")
        print(report)

        summary = walk_forward_summary(reopt_windows)
        all_results["reoptimize"] = {
            "summary": summary,
            "windows": [{
                "window_id": w.window_id,
                "train_start": w.train_start,
                "train_end": w.train_end,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "is_avg_r": w.is_avg_r,
                "oos_avg_r": w.oos_avg_r,
                "oos_n_trades": w.oos_n_trades,
                "oos_win_rate": w.oos_win_rate,
                "wfer": w.wfer,
                "status": w.status,
            } for w in reopt_windows],
        }

    # Save all results
    output_path = data_dir / "walkforward_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[wf] Results saved to {output_path}")


if __name__ == "__main__":
    main()
