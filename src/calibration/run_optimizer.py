"""Run the recipe optimizer on existing signal+outcome data.

Usage: python -m src.calibration.run_optimizer [--quick]

--quick: reduced grid (486 combos instead of ~7.8K). Good for testing.
Full grid: ~7,776 combinations. Takes 30-90 seconds.

Reads targets from data/optimizer_targets.json if it exists:
  {"win_rate": 0.55, "avg_r": 0.15, "trades_per_week": 12}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.calibration.recipe_optimizer import (
    TargetProfile,
    run_grid_search,
    format_results,
)
from src.calibration.independent_validation import (
    run_independent_validation,
    format_validation_report,
    results_to_dict,
)


def main():
    quick = "--quick" in sys.argv
    data_dir = ROOT / "data"
    panel_path = data_dir / "panel_daily.parquet"
    scores_path = data_dir / "scores_daily.parquet"

    if not panel_path.exists() or not scores_path.exists():
        print("[ERROR] Missing data. Run build_panel.bat and build_scores.bat first.")
        return

    # Load targets
    targets = _load_targets(data_dir)
    print(f"[opt] Targets: Non-loss {targets.non_loss_rate*100:.0f}% | Avg R {targets.avg_r:+.2f} | {targets.trades_per_week:.0f} trades/wk")

    print("[opt] Loading data...")
    panel = pd.read_parquet(panel_path)
    scores = pd.read_parquet(scores_path)

    print("[opt] Detecting entry signals...")
    signals = _detect_signals_with_outcomes(scores, panel)
    print(f"[opt] {len(signals)} signals with DSL outcomes")

    if signals.empty:
        print("[opt] No signals. Cannot optimize.")
        return

    mode = "QUICK (reduced grid)" if quick else "FULL (all combinations)"
    print(f"[opt] Running grid search — {mode}...")
    t0 = time.time()
    results, sensitivities = run_grid_search(
        signals, targets=targets, r_column="dsl_r_realized", quick=quick,
    )
    elapsed = time.time() - t0
    print(f"[opt] Tested {len(results):,} valid combinations in {elapsed:.1f}s")

    report = format_results(results, sensitivities=sensitivities, targets=targets, top_n=20)
    print(report)

    # Save full results
    output_path = data_dir / "optimizer_results.json"
    top_50 = results[:50]
    with open(output_path, "w") as f:
        json.dump([{
            "sc_mom_min": r.sc_mom_min,
            "flow_min": r.flow_min,
            "energy_min": r.energy_min,
            "structure_min": r.structure_min,
            "mp_min": r.mp_min,
            "elder_min": r.elder_min,
            "fip_min": r.fip_min,
            "phase_filter": r.phase_filter,
            "squeeze_min": r.squeeze_min,
            "n_trades": r.n_trades,
            "win_rate": r.win_rate,
            "non_loss_rate": r.non_loss_rate,
            "avg_r": r.avg_r,
            "median_r": r.median_r,
            "expectancy_r": r.expectancy_r,
            "total_r": r.total_r,
            "sharpe": r.sharpe,
            "trades_per_week": r.trades_per_week,
            "target_distance": r.target_distance,
            "score": r.score,
            "dsr": r.dsr,
            "dsr_pass": r.dsr_pass,
            "avg_win_r": r.avg_win_r,
            "avg_loss_r": r.avg_loss_r,
            "payoff_ratio": r.payoff_ratio,
            "is_avg_r": r.is_avg_r,
            "oos_avg_r": r.oos_avg_r,
            "oos_win_rate": r.oos_win_rate,
            "oos_n": r.oos_n,
            "wfer": r.wfer,
        } for r in top_50], f, indent=2)
    print(f"\n[opt] Top 50 recipes saved to {output_path}")

    # Update active_recipe.json with best result
    active_path = data_dir / "active_recipe.json"
    best_recipe = top_50[0]
    with open(active_path, "w") as f:
        json.dump({
            "sc_mom_min": best_recipe.sc_mom_min,
            "flow_min": best_recipe.flow_min,
            "energy_min": best_recipe.energy_min,
            "structure_min": best_recipe.structure_min,
            "mp_min": best_recipe.mp_min,
            "elder_min": best_recipe.elder_min,
            "fip_min": best_recipe.fip_min,
            "phase_filter": best_recipe.phase_filter,
            "squeeze_min": best_recipe.squeeze_min,
        }, f, indent=2)
    print(f"[opt] Active recipe updated: {active_path}")

    # Save sensitivity analysis
    if sensitivities:
        sens_path = data_dir / "engine_sensitivity.json"
        with open(sens_path, "w") as f:
            json.dump([{
                "engine": s.engine,
                "correlation": s.correlation,
                "avg_r_top_quartile": s.avg_r_top_quartile,
                "avg_r_bottom_quartile": s.avg_r_bottom_quartile,
                "lift": s.lift,
            } for s in sensitivities], f, indent=2)

    # Run fixed-recipe walk-forward on best recipe
    if results:
        from src.calibration.walkforward import (
            walk_forward_analysis,
            format_walkforward,
            walk_forward_summary,
        )
        best = results[0]
        print(f"\n[opt] Running fixed-recipe walk-forward on best recipe...")
        wf_windows = walk_forward_analysis(
            signals, r_column="dsl_r_realized", mode="rolling",
            train_months=12, test_months=3, step_months=1,
            fixed_recipe=best,
        )
        if wf_windows:
            wf_report = format_walkforward(wf_windows, mode_label="FIXED RECIPE")
            print(wf_report)
            wf_summary = walk_forward_summary(wf_windows)
            wf_path = data_dir / "walkforward_results.json"
            with open(wf_path, "w") as f:
                json.dump({
                    "fixed_recipe": {
                        "summary": wf_summary,
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
                        } for w in wf_windows],
                    }
                }, f, indent=2)
            print(f"[opt] Walk-forward saved to {wf_path}")

    # Run independent validation on best recipe
    if results:
        best = results[0]
        print(f"\n[opt] Running independent validation on best recipe...")
        recipe_mask = (
            (signals["sc_momentum"] >= best.sc_mom_min) &
            (signals["flow_100"] >= best.flow_min) &
            (signals["energy_100"] >= best.energy_min) &
            (signals["structure_100"] >= best.structure_min) &
            (signals["mp_100"] >= best.mp_min)
        )
        if best.elder_min > 0 and "elder_score" in signals.columns:
            recipe_mask &= signals["elder_score"] >= best.elder_min
        if best.phase_filter != "ANY" and "mp_state" in signals.columns:
            if best.phase_filter == "BUILDING":
                recipe_mask &= signals["mp_state"] == "BUILDING"
            elif best.phase_filter == "BUILDING+STRONG":
                recipe_mask &= signals["mp_state"].isin(["BUILDING", "STRONG"])
        if best.squeeze_min > 0 and "squeeze_score" in signals.columns:
            recipe_mask &= signals["squeeze_score"] >= best.squeeze_min
        if best.fip_min > 0 and "fip_quality" in signals.columns:
            recipe_mask &= signals["fip_quality"] >= best.fip_min
        recipe_mask = recipe_mask.values

        val_results = run_independent_validation(signals, recipe_mask, panel, r_column="dsl_r_realized")
        val_report = format_validation_report(val_results)
        print(val_report)

        val_path = data_dir / "independent_validation.json"
        with open(val_path, "w") as f:
            json.dump(results_to_dict(val_results), f, indent=2)
        print(f"[opt] Validation saved to {val_path}")


def _load_targets(data_dir: Path) -> TargetProfile:
    """Load targets from JSON or use defaults."""
    targets_path = data_dir / "optimizer_targets.json"
    if targets_path.exists():
        try:
            with open(targets_path) as f:
                raw = json.load(f)
            return TargetProfile(
                non_loss_rate=float(raw.get("non_loss_rate", raw.get("win_rate", 0.55))),
                avg_r=float(raw.get("avg_r", 0.15)),
                trades_per_week=float(raw.get("trades_per_week", 12.0)),
            )
        except (json.JSONDecodeError, ValueError):
            pass
    return TargetProfile()


def _detect_signals_with_outcomes(scores: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Detect momentum signals (crossup + continuation) with 5-day cooldown.

    Fires a signal any day SC_MOMENTUM >= 50 provided at least 5 trading days
    have passed since the last signal for that ticker. This captures both initial
    crossup entries and continuation legs where momentum persists.

    DSL v2.0: passes scores_daily to compute_dsl_outcomes for flow-based TP.
    """
    from src.scanner.dsl import compute_dsl_outcomes

    COOLDOWN = 5
    THRESHOLD = 50.0

    signals = []
    n_crossup = 0
    n_continuation = 0
    scores_sorted = scores.sort_values(["ticker", "date"]).reset_index(drop=True)

    for ticker, grp in scores_sorted.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if "sc_momentum" not in grp.columns:
            continue
        sc = grp["sc_momentum"].values
        bars_since = COOLDOWN + 1

        for i in range(len(sc)):
            bars_since += 1
            if sc[i] >= THRESHOLD and bars_since > COOLDOWN:
                is_crossup = i > 0 and sc[i - 1] < THRESHOLD
                if is_crossup:
                    n_crossup += 1
                else:
                    n_continuation += 1

                row = grp.iloc[i]
                sig = {"ticker": ticker, "date": row["date"], "sc_momentum": float(sc[i])}
                for col in ["flow_100", "energy_100", "structure_100", "mp_100",
                            "elder_score", "bq_100", "k39_value", "squeeze_score",
                            "pipe_rank", "fip_quality"]:
                    if col in row.index:
                        sig[col] = float(row[col]) if pd.notna(row[col]) else 0.0
                if "mp_state" in row.index and pd.notna(row["mp_state"]):
                    sig["mp_state"] = str(row["mp_state"])
                signals.append(sig)
                bars_since = 0

    print(f"[opt] Signal breakdown: {n_crossup} crossups + {n_continuation} continuations = {len(signals)} total")

    if not signals:
        return pd.DataFrame()

    sig_df = pd.DataFrame(signals)

    from src.engines.utils import atr as compute_atr
    atr_values = []
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        a = compute_atr(grp["high"], grp["low"], grp["close"], 14)
        df_a = grp[["ticker", "date"]].copy()
        df_a["atr14"] = a.values
        atr_values.append(df_a)
    atr_df = pd.concat(atr_values, ignore_index=True)
    atr_df["date"] = pd.to_datetime(atr_df["date"]).dt.normalize()

    sig_df["date"] = pd.to_datetime(sig_df["date"]).dt.normalize()
    sig_df = sig_df.merge(atr_df, on=["ticker", "date"], how="left")
    sig_df = sig_df.dropna(subset=["atr14"])
    sig_df = sig_df.rename(columns={"atr14": "atr14_at_entry"})

    print(f"[opt] Computing DSL v2.0 outcomes for {len(sig_df)} signals (with flow TP)...")
    outcomes = compute_dsl_outcomes(sig_df, panel, max_bars=63, scores_daily=scores)
    tp_count = outcomes["dsl_tp_fired"].sum() if "dsl_tp_fired" in outcomes.columns else 0
    print(f"[opt] DSL v2.0: {int(tp_count)} trades exited via flow TP signal")
    return outcomes


if __name__ == "__main__":
    main()
