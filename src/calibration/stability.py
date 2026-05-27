"""Parameter Stability Analysis — Pardo RP-3, RP-4.

For each parameter in the optimal recipe set across walk-forward windows:
    CV < 0.15: STABLE     — adopt the parameter change
    CV 0.15-0.30: ACCEPTABLE — adopt with monitoring
    CV > 0.30: UNSTABLE   — keep current value, do NOT change

This protects against adopting parameters that only worked in one window
but are noise in others.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.calibration.walkforward import WFWindow


@dataclass
class ParamStability:
    """Stability assessment for one parameter."""
    name: str
    values: list[float]
    mean: float
    std: float
    cv: float
    verdict: str  # STABLE / ACCEPTABLE / UNSTABLE


def analyze_stability(windows: list[WFWindow]) -> list[ParamStability]:
    """Analyze parameter stability across walk-forward windows.

    Extracts the best recipe's parameters from each window and computes
    the coefficient of variation (CV) for each parameter.
    """
    if not windows:
        return []

    valid_windows = [w for w in windows if w.best_recipe is not None]
    if len(valid_windows) < 3:
        return []

    params = {
        "sc_mom_min": [w.best_recipe.sc_mom_min for w in valid_windows],
        "flow_min": [w.best_recipe.flow_min for w in valid_windows],
        "energy_min": [w.best_recipe.energy_min for w in valid_windows],
        "structure_min": [w.best_recipe.structure_min for w in valid_windows],
        "mp_min": [w.best_recipe.mp_min for w in valid_windows],
    }

    results = []
    for name, values in params.items():
        arr = np.array(values, dtype=float)
        non_zero = arr[arr > 0]

        if len(non_zero) < 2:
            results.append(ParamStability(
                name=name,
                values=values,
                mean=float(np.mean(arr)),
                std=0.0,
                cv=0.0,
                verdict="STABLE" if len(non_zero) == 0 else "N/A",
            ))
            continue

        mean = float(np.mean(non_zero))
        std = float(np.std(non_zero, ddof=1))
        cv = std / mean if mean > 0 else 0.0

        if cv < 0.15:
            verdict = "STABLE"
        elif cv < 0.30:
            verdict = "ACCEPTABLE"
        else:
            verdict = "UNSTABLE"

        results.append(ParamStability(
            name=name,
            values=values,
            mean=round(mean, 1),
            std=round(std, 2),
            cv=round(cv, 3),
            verdict=verdict,
        ))

    return results


def format_stability(results: list[ParamStability]) -> str:
    """Format stability report."""
    if not results:
        return "No stability data (insufficient walk-forward windows)."

    lines = []
    lines.append("=" * 70)
    lines.append("  PARAMETER STABILITY ANALYSIS (Pardo CV metric)")
    lines.append("  CV < 0.15: STABLE | CV 0.15-0.30: ACCEPTABLE | CV > 0.30: UNSTABLE")
    lines.append("=" * 70)
    lines.append(f"  {'Parameter':<15} {'Mean':>6} {'Std':>6} {'CV':>6} {'Verdict':<12}")
    lines.append("-" * 70)

    for p in results:
        lines.append(
            f"  {p.name:<15} {p.mean:>6.1f} {p.std:>6.2f} {p.cv:>6.3f} {p.verdict:<12}"
        )

    lines.append("-" * 70)

    unstable = [p for p in results if p.verdict == "UNSTABLE"]
    if unstable:
        lines.append(f"  WARNING: {len(unstable)} parameters UNSTABLE - keep current values.")
        for p in unstable:
            lines.append(f"    {p.name}: CV={p.cv:.3f} (values vary too much across windows)")
    else:
        lines.append("  All parameters stable or acceptable across walk-forward windows.")

    lines.append("=" * 70)
    return "\n".join(lines)
