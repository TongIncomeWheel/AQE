"""Run walk-forward + independent validation for the Precision Edge recipe.

Tests the sub-component recipe (not aggregate) across time and against random.
These are Jim Simons-grade statistical tests — each one answers a different
question using methods that share no assumptions.

Usage:
    python -m src.calibration.run_pe_validation

Output:
    data/precision_walkforward.json
    data/precision_validation.json
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

from src.calibration.walkforward import (
    walk_forward_analysis,
    format_walkforward,
    walk_forward_summary,
)
from src.calibration.independent_validation import (
    run_independent_validation,
    format_validation_report,
    results_to_dict,
)


def _load_precision_recipe() -> tuple[dict, dict] | None:
    """Load precision recipe from active_recipe.json.

    Returns (subcomp_filters, full_precision_section) or None.
    """
    recipe_path = ROOT / "data" / "active_recipe.json"
    if not recipe_path.exists():
        return None
    with open(recipe_path) as f:
        raw = json.load(f)
    precision = raw.get("precision", {})
    if not precision or not precision.get("subcomp_filters"):
        return None
    return precision.get("subcomp_filters", {}), precision


def _build_subcomp_mask(df: pd.DataFrame, subcomp_filters: dict, sc_mom_min: float) -> np.ndarray:
    """Build a boolean mask for rows passing all sub-component filters."""
    mask = df["sc_momentum"] >= sc_mom_min
    for col, spec in subcomp_filters.items():
        thresh = spec["threshold"] if isinstance(spec, dict) else spec
        if col in df.columns:
            mask &= df[col] >= thresh
    return mask.values


def main():
    data_dir = ROOT / "data"
    panel_path = data_dir / "panel_daily.parquet"
    scores_path = data_dir / "scores_daily.parquet"

    if not panel_path.exists() or not scores_path.exists():
        print("[pe-val] Missing data. Run build_panel.bat and build_scores.bat first.")
        return

    loaded = _load_precision_recipe()
    if loaded is None:
        print("[pe-val] No Precision Edge recipe found in active_recipe.json.")
        return
    subcomp_filters, precision_section = loaded
    sc_mom_min = precision_section.get("sc_mom_min", 50.0)

    fstr = ", ".join(
        f"{(spec['label'] if isinstance(spec, dict) else col)}>="
        f"{(spec['threshold'] if isinstance(spec, dict) else spec)}"
        for col, spec in subcomp_filters.items()
    )
    print(f"[pe-val] Precision Edge: SC>={sc_mom_min}, {fstr}")

    print("[pe-val] Loading data...")
    panel = pd.read_parquet(panel_path)
    scores = pd.read_parquet(scores_path)

    print("[pe-val] Detecting entry signals with DSL outcomes...")
    from src.calibration.run_optimizer import _detect_signals_with_outcomes
    outcomes = _detect_signals_with_outcomes(scores, panel)
    print(f"[pe-val] {len(outcomes)} signals with outcomes")

    if outcomes.empty:
        print("[pe-val] No signals. Cannot validate.")
        return

    # Check how many pass the PE recipe
    pe_mask = _build_subcomp_mask(outcomes, subcomp_filters, sc_mom_min)
    n_pe = int(pe_mask.sum())
    print(f"[pe-val] {n_pe} signals pass Precision Edge recipe")

    if n_pe < 50:
        print(f"[pe-val] Too few PE signals ({n_pe}). Need at least 50 for meaningful validation.")
        return

    # ---- Walk-Forward Analysis ----
    print(f"\n[pe-val] === PRECISION EDGE WALK-FORWARD (rolling mode) ===")
    t0 = time.time()
    wf_windows = walk_forward_analysis(
        outcomes,
        r_column="dsl_r_realized",
        mode="rolling",
        train_months=12,
        test_months=3,
        step_months=1,
        subcomp_filters=subcomp_filters,
        sc_mom_min=sc_mom_min,
    )
    elapsed = time.time() - t0
    print(f"[pe-val] Completed {len(wf_windows)} windows in {elapsed:.1f}s")

    if wf_windows:
        wf_report = format_walkforward(wf_windows, mode_label="PRECISION EDGE")
        print(wf_report)

        wf_summary = walk_forward_summary(wf_windows)
        wf_result = {
            "recipe_name": precision_section.get("name", "Precision Edge"),
            "subcomp_filters": {col: (spec["threshold"] if isinstance(spec, dict) else spec)
                                for col, spec in subcomp_filters.items()},
            "sc_mom_min": sc_mom_min,
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
            },
        }
        wf_path = data_dir / "precision_walkforward.json"
        with open(wf_path, "w") as f:
            json.dump(wf_result, f, indent=2)
        print(f"[pe-val] Walk-forward saved to {wf_path}")
    else:
        print("[pe-val] No walk-forward windows completed.")

    # ---- Independent Validation ----
    print(f"\n[pe-val] === PRECISION EDGE INDEPENDENT VALIDATION ===")
    val_results = run_independent_validation(outcomes, pe_mask, panel, r_column="dsl_r_realized")
    val_report = format_validation_report(val_results)
    print(val_report)

    val_dict = results_to_dict(val_results)
    val_dict["recipe_name"] = precision_section.get("name", "Precision Edge")
    val_dict["subcomp_filters"] = {col: (spec["threshold"] if isinstance(spec, dict) else spec)
                                    for col, spec in subcomp_filters.items()}
    val_path = data_dir / "precision_validation.json"
    with open(val_path, "w") as f:
        json.dump(val_dict, f, indent=2)
    print(f"[pe-val] Validation saved to {val_path}")

    print("\n" + "=" * 60)
    print("[pe-val] Done. Results ready for Streamlit UI.")


if __name__ == "__main__":
    main()
