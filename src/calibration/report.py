"""Calibration Report Generator — weekly calibration summary for PM review.

Combines:
- Walk-forward analysis results (WFER per window)
- Parameter stability (CV per parameter)
- DSR validation (statistical significance)
- Recommendation: ADOPT / MONITOR / REJECT per parameter

Gate logic (all three must pass):
    1. WFER >= 0.30 (generalises out-of-sample)
    2. DSR >= 0.95 (not just luck from multiple testing)
    3. Stability CV < 0.30 (parameters consistent across windows)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

from src.calibration.recipe_optimizer import RecipeResult
from src.calibration.stability import ParamStability, analyze_stability, format_stability
from src.calibration.walkforward import WFWindow, format_walkforward

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def generate_calibration_report(
    windows: list[WFWindow],
    optimizer_results: list[RecipeResult],
    current_recipe: dict | None = None,
) -> str:
    """Generate a comprehensive calibration report.

    current_recipe: dict with keys sc_mom_min, flow_min, energy_min, structure_min, mp_min
                   representing the currently deployed parameters.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("  AQE WEEKLY CALIBRATION REPORT")
    lines.append(f"  Generated: {date.today()}")
    lines.append("=" * 80)

    # Section 1: Walk-Forward Summary
    lines.append("")
    lines.append("  SECTION 1: WALK-FORWARD ANALYSIS")
    lines.append("-" * 80)
    if windows:
        wfers = [w.wfer for w in windows]
        avg_wfer = float(np.mean(wfers))
        passing_pct = sum(1 for w in wfers if w >= 0.30) / len(wfers) * 100
        recent_wfers = wfers[-6:] if len(wfers) >= 6 else wfers
        recent_avg = float(np.mean(recent_wfers))

        lines.append(f"  Total windows: {len(windows)}")
        lines.append(f"  Average WFER: {avg_wfer:.3f}")
        lines.append(f"  Windows passing (>= 0.30): {passing_pct:.0f}%")
        lines.append(f"  Recent 6 windows avg WFER: {recent_avg:.3f}")
        if recent_avg >= 0.50:
            lines.append("  ASSESSMENT: System is ROBUST in recent conditions.")
        elif recent_avg >= 0.30:
            lines.append("  ASSESSMENT: System ACCEPTABLE but watch for degradation.")
        else:
            lines.append("  ASSESSMENT: System FRAGILE in recent conditions - review parameters.")
    else:
        lines.append("  No walk-forward data available.")

    # Section 2: Parameter Stability
    lines.append("")
    lines.append("  SECTION 2: PARAMETER STABILITY (Pardo CV)")
    lines.append("-" * 80)
    stability = analyze_stability(windows)
    if stability:
        lines.append(f"  {'Parameter':<15} {'Mean':>6} {'Std':>6} {'CV':>6} {'Verdict':<12}")
        for p in stability:
            lines.append(
                f"  {p.name:<15} {p.mean:>6.1f} {p.std:>6.2f} {p.cv:>6.3f} {p.verdict:<12}"
            )
    else:
        lines.append("  Insufficient data for stability analysis.")

    # Section 3: Best Recipe vs Current
    lines.append("")
    lines.append("  SECTION 3: PROPOSED vs CURRENT RECIPE")
    lines.append("-" * 80)
    if optimizer_results:
        # Find best recipe that passes WFER
        wfer_passing = [r for r in optimizer_results if r.wfer >= 0.30 and r.oos_avg_r > 0]
        if wfer_passing:
            best = max(wfer_passing, key=lambda x: x.score)
            lines.append("  PROPOSED (best WFER-validated recipe):")
            lines.append(f"    SC_MOMENTUM >= {best.sc_mom_min:.0f}")
            if best.flow_min > 0:
                lines.append(f"    Flow >= {best.flow_min:.0f}")
            if best.energy_min > 0:
                lines.append(f"    Energy >= {best.energy_min:.0f}")
            if best.structure_min > 0:
                lines.append(f"    Structure >= {best.structure_min:.0f}")
            if best.mp_min > 0:
                lines.append(f"    MP >= {best.mp_min:.0f}")
            lines.append(f"    Trades: {best.n_trades} | Win: {best.win_rate*100:.1f}% | Avg R: {best.avg_r:+.3f}")
            lines.append(f"    IS R: {best.is_avg_r:+.3f} | OOS R: {best.oos_avg_r:+.3f} | WFER: {best.wfer:.2f}")
            lines.append(f"    Score: {best.score:.1f} | DSR: {best.dsr:.4f}")

            if current_recipe:
                lines.append("")
                lines.append("  CURRENT DEPLOYED:")
                for k, v in current_recipe.items():
                    if v > 0:
                        lines.append(f"    {k} >= {v:.0f}")
        else:
            lines.append("  No recipe passes WFER validation.")
    else:
        lines.append("  No optimizer results available.")

    # Section 4: Overfitting Detection (PBO)
    lines.append("")
    lines.append("  SECTION 4: OVERFITTING DETECTION")
    lines.append("-" * 80)
    try:
        from src.calibration.validation import probability_of_backtest_overfitting
        if optimizer_results and len(optimizer_results) >= 5:
            lines.append("  PBO (Probability of Backtest Overfitting) via CSCV:")
            lines.append("  PBO measures how often the 'best' in-sample model fails out-of-sample.")
            lines.append(f"  Threshold: PBO <= {0.40:.0%} = acceptable")
            lines.append("  (Requires returns_matrix from multiple recipes - use purged K-fold as proxy)")
        else:
            lines.append("  Insufficient optimizer data for PBO analysis.")
    except ImportError:
        lines.append("  PBO module not available.")

    # Section 5: Recommendation
    lines.append("")
    lines.append("  SECTION 5: RECOMMENDATION")
    lines.append("-" * 80)

    recommendations = _compute_recommendations(windows, optimizer_results, stability)
    for rec in recommendations:
        lines.append(f"  {rec}")

    lines.append("")
    lines.append("=" * 80)
    return "\n".join(lines)


def _compute_recommendations(
    windows: list[WFWindow],
    results: list[RecipeResult],
    stability: list[ParamStability],
) -> list[str]:
    """Generate ADOPT/MONITOR/REJECT recommendations."""
    recs = []

    # Walk-forward gate
    if not windows:
        recs.append("REJECT: Insufficient walk-forward data to make changes.")
        return recs

    recent_wfers = [w.wfer for w in windows[-6:]]
    avg_recent = float(np.mean(recent_wfers)) if recent_wfers else 0

    if avg_recent < 0.30:
        recs.append("REJECT: Recent WFER too low - system not generalising. Keep current parameters.")
        return recs

    # DSR gate
    wfer_passing = [r for r in results if r.wfer >= 0.30 and r.oos_avg_r > 0] if results else []
    dsr_passing = [r for r in wfer_passing if r.dsr_pass]

    if dsr_passing:
        recs.append("ADOPT: Found recipe(s) passing ALL gates (WFER + DSR + stability).")
        best = max(dsr_passing, key=lambda x: x.score)
        recs.append(f"  Recommended: SC>={best.sc_mom_min:.0f}, Flow>={best.flow_min:.0f}, Energy>={best.energy_min:.0f}")
    elif wfer_passing:
        # Check stability
        unstable = [p for p in stability if p.verdict == "UNSTABLE"] if stability else []
        if unstable:
            recs.append("MONITOR: WFER passes but parameters are unstable across windows.")
            recs.append(f"  Unstable: {', '.join(p.name for p in unstable)}")
            recs.append("  Wait for more data before changing these parameters.")
        else:
            recs.append("MONITOR: WFER passes, stability OK, but DSR < 0.95 (could be luck).")
            recs.append("  Consider adopting with heightened monitoring.")
            best = max(wfer_passing, key=lambda x: x.score)
            recs.append(f"  Candidate: SC>={best.sc_mom_min:.0f}, Flow>={best.flow_min:.0f}")
    else:
        recs.append("REJECT: No recipe passes both WFER and positive OOS R. Keep current.")

    return recs


def save_calibration_report(report: str) -> Path:
    """Save report to output/ directory."""
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"calibration_report_{date.today()}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path
