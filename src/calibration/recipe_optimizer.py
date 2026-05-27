"""Recipe Optimizer v3 — target-based search with phase, squeeze, and non-loss scoring.

Changes from v1:
- ALL 5 engines required (no 0-threshold "any" recipes)
- Scoring by distance to user-specified targets (win rate, avg R, trades/week)
- Engine sensitivity analysis showing which engines predict outcomes
- Walk-forward validation (IS/OOS) with WFER
- DSR for statistical significance

Design: the optimizer finds the recipe CLOSEST to what you want,
not the recipe with the highest abstract "score." If your targets are
unreachable, it tells you what IS reachable. (Pardo RP-2, Lopez MLP-1)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd
from scipy.stats import norm


# ─── Parameter Grid (ALL engines must contribute — no zeros) ──────────────
# Gate floors: Flow=60, Energy=60, Structure=55, MP=55.
# Grid starts above floors because composite crossup already enforces them.

SC_MOM_GRID = [60, 70, 75, 80]
FLOW_GRID = [64, 72, 80]
ENERGY_GRID = [64, 72, 80]
STRUCTURE_GRID = [60, 70, 80]
MP_GRID = [60, 70, 80]
ELDER_GRID = [7, 8, 9]  # Elder >= 7 REQUIRED for timing gate — no 0 option
PHASE_OPTIONS = ["ANY", "BUILDING", "BUILDING+STRONG"]
SQUEEZE_GRID = [0, 5, 10]
FIP_GRID = [0, 60, 80]

MIN_TRADES = 30
MIN_OOS_TRADES = 15


@dataclass
class TargetProfile:
    """User-specified performance targets."""
    non_loss_rate: float = 0.55
    avg_r: float = 0.15
    trades_per_week: float = 12.0


@dataclass
class RecipeResult:
    sc_mom_min: float
    flow_min: float
    energy_min: float
    structure_min: float
    mp_min: float
    elder_min: float
    fip_min: float
    phase_filter: str
    squeeze_min: float
    n_trades: int
    win_rate: float
    non_loss_rate: float
    avg_r: float
    median_r: float
    expectancy_r: float
    total_r: float
    sharpe: float
    trades_per_week: float
    target_distance: float
    score: float
    dsr: float
    dsr_pass: bool
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    payoff_ratio: float = 0.0
    is_avg_r: float = 0.0
    oos_avg_r: float = 0.0
    oos_win_rate: float = 0.0
    oos_n: int = 0
    wfer: float = 0.0


@dataclass
class EngineSensitivity:
    """How much each engine's score correlates with trade outcomes."""
    engine: str
    correlation: float
    avg_r_top_quartile: float
    avg_r_bottom_quartile: float
    lift: float


# ─── Deflated Sharpe Ratio ────────────────────────────────────────────────

def deflated_sharpe_ratio(
    observed_sharpe: float,
    num_trials: int,
    variance_of_sharpes: float,
    T: int,
) -> float:
    """Lopez de Prado (2014). Probability that observed Sharpe is genuine."""
    if num_trials <= 1 or variance_of_sharpes <= 0 or T <= 1:
        return 0.0
    std_sharpes = np.sqrt(variance_of_sharpes)
    expected_max = std_sharpes * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1 / num_trials)
        + np.euler_gamma * norm.ppf(1 - 1 / (num_trials * np.e))
    )
    se = np.sqrt((1 + 0.5 * observed_sharpe**2) / (T - 1))
    if se == 0:
        return 0.0
    return float(norm.cdf((observed_sharpe - expected_max) / se))


# ─── Engine Sensitivity Analysis ─────────────────────────────────────────

def compute_engine_sensitivity(
    df: pd.DataFrame,
    r_column: str = "dsl_r_realized",
) -> list[EngineSensitivity]:
    """Which engines predict trade outcomes? Quartile lift analysis."""
    engines = {
        "SC_Momentum": "sc_momentum",
        "Flow": "flow_100",
        "Energy": "energy_100",
        "Structure": "structure_100",
        "MP": "mp_100",
        "Elder": "elder_score",
        "FIP": "fip_quality",
    }
    results = []
    rs = df[r_column].values

    for name, col in engines.items():
        if col not in df.columns:
            continue
        vals = df[col].values
        valid = ~(np.isnan(vals) | np.isnan(rs))
        if valid.sum() < 50:
            continue

        corr = float(np.corrcoef(vals[valid], rs[valid])[0, 1])
        q75 = np.percentile(vals[valid], 75)
        q25 = np.percentile(vals[valid], 25)
        top_mask = vals >= q75
        bot_mask = vals <= q25
        top_r = float(np.mean(rs[top_mask & valid])) if (top_mask & valid).sum() > 10 else 0.0
        bot_r = float(np.mean(rs[bot_mask & valid])) if (bot_mask & valid).sum() > 10 else 0.0

        results.append(EngineSensitivity(
            engine=name,
            correlation=round(corr, 4),
            avg_r_top_quartile=round(top_r, 4),
            avg_r_bottom_quartile=round(bot_r, 4),
            lift=round(top_r - bot_r, 4),
        ))

    results.sort(key=lambda x: abs(x.lift), reverse=True)
    return results


# ─── Target Distance Scoring ────────────────────────────────────────────

def _target_score(
    non_loss_rate: float,
    avg_r: float,
    trades_per_week: float,
    oos_avg_r: float,
    oos_win_rate: float,
    wfer: float,
    targets: TargetProfile,
) -> tuple[float, float]:
    """Returns (target_distance, score). Lower distance = closer to what user wants."""
    nlr_gap = (non_loss_rate - targets.non_loss_rate) / 0.10
    r_gap = (avg_r - targets.avg_r) / 0.10
    tpw_gap = (trades_per_week - targets.trades_per_week) / 5.0
    distance = sqrt(nlr_gap**2 + r_gap**2 + tpw_gap**2)

    oos_bonus = max(0, oos_avg_r) * 3.0
    wfer_bonus = max(0, min(wfer, 2.0) - 0.20) * 1.0

    undershoot_penalty = 0.0
    if non_loss_rate < targets.non_loss_rate:
        undershoot_penalty += abs(nlr_gap) * 0.5
    if trades_per_week < targets.trades_per_week * 0.5:
        undershoot_penalty += 1.0

    score = -distance + oos_bonus + wfer_bonus - undershoot_penalty
    return round(distance, 4), round(score, 4)


# ─── Grid Search ─────────────────────────────────────────────────────────

def run_grid_search(
    outcomes: pd.DataFrame,
    targets: TargetProfile | None = None,
    r_column: str = "dsl_r_realized",
    quick: bool = False,
) -> tuple[list[RecipeResult], list[EngineSensitivity]]:
    """Search all parameter combinations against pre-computed outcomes.

    Returns (results sorted by score, engine_sensitivities).
    All 5 engines are required in every recipe — no "any" thresholds.
    """
    if targets is None:
        targets = TargetProfile()

    if outcomes.empty or r_column not in outcomes.columns:
        return [], []

    df = outcomes.copy()
    for col in ["sc_momentum", "flow_100", "energy_100", "structure_100", "mp_100"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    date_min = df["date"].min()
    date_max = df["date"].max()
    num_weeks = max(1, (date_max - date_min).days / 7)

    dates_sorted = df["date"].sort_values().unique()
    split_idx = int(len(dates_sorted) * 0.70)
    split_date = dates_sorted[split_idx]

    sensitivities = compute_engine_sensitivity(df, r_column)

    if quick:
        flow_grid = [64, 72, 85]
        energy_grid = [64, 72, 85]
        structure_grid = [60, 70, 85]
        mp_grid = [60, 70, 85]
        elder_grid = [7, 8]
        fip_grid = [0, 60]
        phase_options = ["ANY", "BUILDING"]
        squeeze_grid = [0, 5]
    else:
        flow_grid = FLOW_GRID
        energy_grid = ENERGY_GRID
        structure_grid = STRUCTURE_GRID
        mp_grid = MP_GRID
        elder_grid = ELDER_GRID
        fip_grid = FIP_GRID
        phase_options = PHASE_OPTIONS
        squeeze_grid = SQUEEZE_GRID

    has_phase = "mp_state" in df.columns
    has_squeeze = "squeeze_score" in df.columns
    has_elder = "elder_score" in df.columns
    has_fip = "fip_quality" in df.columns

    combos = list(itertools.product(
        SC_MOM_GRID, flow_grid, energy_grid, structure_grid, mp_grid,
        elder_grid, fip_grid, phase_options, squeeze_grid,
    ))
    total_trials = len(combos)

    results: list[RecipeResult] = []
    all_sharpes: list[float] = []

    for sc_min, fl_min, en_min, st_min, mp_min, eld_min, fip_min, phase, sq_min in combos:
        mask = (
            (df["sc_momentum"] >= sc_min)
            & (df["flow_100"] >= fl_min)
            & (df["energy_100"] >= en_min)
            & (df["structure_100"] >= st_min)
            & (df["mp_100"] >= mp_min)
        )
        if eld_min > 0 and has_elder:
            mask &= df["elder_score"] >= eld_min
        if fip_min > 0 and has_fip:
            mask &= df["fip_quality"] >= fip_min
        if phase != "ANY" and has_phase:
            if phase == "BUILDING":
                mask &= df["mp_state"] == "BUILDING"
            elif phase == "BUILDING+STRONG":
                mask &= df["mp_state"].isin(["BUILDING", "STRONG"])
        if sq_min > 0 and has_squeeze:
            mask &= df["squeeze_score"] >= sq_min

        subset = df.loc[mask, [r_column, "date"]].dropna(subset=[r_column])
        n = len(subset)
        if n < MIN_TRADES:
            all_sharpes.append(0.0)
            continue

        rs = subset[r_column].values
        avg_r = float(np.mean(rs))
        med_r = float(np.median(rs))
        win_rate = float(np.sum(rs > 0) / n)
        non_loss_rate = float(np.sum(rs >= 0) / n)
        total_r = float(np.sum(rs))
        tpw = n / num_weeks
        # Payoff ratio: avg winner R vs avg loser R
        _winners = rs[rs > 0.05]
        _losers = rs[rs < -0.05]
        _avg_win_r = float(np.mean(_winners)) if len(_winners) > 0 else 0.0
        _avg_loss_r = float(np.mean(_losers)) if len(_losers) > 0 else 0.0
        _payoff = abs(_avg_win_r / _avg_loss_r) if _avg_loss_r != 0 else 0.0

        std_r = float(np.std(rs))
        sharpe = avg_r / std_r if std_r > 0 else 0.0
        all_sharpes.append(sharpe)

        is_sub = subset.loc[subset["date"] < split_date, r_column]
        oos_sub = subset.loc[subset["date"] >= split_date, r_column]
        is_avg = float(np.mean(is_sub)) if len(is_sub) >= 10 else 0.0
        oos_avg = float(np.mean(oos_sub)) if len(oos_sub) >= MIN_OOS_TRADES else 0.0
        oos_wr = float(np.sum(oos_sub > 0) / len(oos_sub)) if len(oos_sub) >= MIN_OOS_TRADES else 0.0
        oos_n = len(oos_sub)
        wfer = oos_avg / is_avg if is_avg > 0 and oos_avg != 0 else 0.0

        distance, score = _target_score(
            non_loss_rate, avg_r, tpw, oos_avg, oos_wr, wfer, targets,
        )

        results.append(RecipeResult(
            sc_mom_min=sc_min,
            flow_min=fl_min,
            energy_min=en_min,
            structure_min=st_min,
            mp_min=mp_min,
            elder_min=eld_min,
            fip_min=fip_min,
            phase_filter=phase,
            squeeze_min=sq_min,
            n_trades=n,
            win_rate=round(win_rate, 4),
            non_loss_rate=round(non_loss_rate, 4),
            avg_r=round(avg_r, 3),
            median_r=round(med_r, 3),
            expectancy_r=round(avg_r, 3),
            total_r=round(total_r, 1),
            sharpe=round(sharpe, 3),
            trades_per_week=round(tpw, 1),
            target_distance=distance,
            score=score,
            dsr=0.0,
            dsr_pass=False,
            avg_win_r=round(_avg_win_r, 3),
            avg_loss_r=round(_avg_loss_r, 3),
            payoff_ratio=round(_payoff, 2),
            is_avg_r=round(is_avg, 3),
            oos_avg_r=round(oos_avg, 3),
            oos_win_rate=round(oos_wr, 4),
            oos_n=oos_n,
            wfer=round(wfer, 2),
        ))

    if not results:
        return [], sensitivities

    variance_of_sharpes = float(np.var([s for s in all_sharpes if s != 0.0])) if all_sharpes else 0.0
    for r in results:
        r.dsr = round(deflated_sharpe_ratio(
            observed_sharpe=r.sharpe,
            num_trials=total_trials,
            variance_of_sharpes=variance_of_sharpes,
            T=r.n_trades,
        ), 4)
        r.dsr_pass = r.dsr >= 0.95

    results.sort(key=lambda x: x.score, reverse=True)
    return results, sensitivities


def format_results(
    results: list[RecipeResult],
    sensitivities: list[EngineSensitivity] | None = None,
    targets: TargetProfile | None = None,
    top_n: int = 20,
) -> str:
    """Format top results as a readable table."""
    if targets is None:
        targets = TargetProfile()
    if not results:
        return "No valid recipes found (all combinations had < 30 trades)."

    lines = []
    lines.append("=" * 120)
    lines.append("  RECIPE OPTIMIZER v3 — TARGET-BASED SEARCH (all 5 engines + phase + squeeze)")
    lines.append(f"  TARGETS: Non-loss {targets.non_loss_rate*100:.0f}% | Avg R {targets.avg_r:+.2f} | Trades/Week {targets.trades_per_week:.0f}")
    lines.append("  Walk-forward: 70% In-Sample / 30% Out-of-Sample | WFER = OOS/IS ratio")
    lines.append("=" * 120)

    if sensitivities:
        lines.append("\n  ENGINE SENSITIVITY (which engines predict trade outcomes):")
        lines.append(f"  {'Engine':<14} {'Corr':>6} {'Top25% R':>9} {'Bot25% R':>9} {'Lift':>7}")
        lines.append("  " + "-" * 50)
        for s in sensitivities:
            star = " ***" if abs(s.lift) >= 0.05 else " *" if abs(s.lift) >= 0.02 else ""
            lines.append(
                f"  {s.engine:<14} {s.correlation:>+6.3f} {s.avg_r_top_quartile:>+9.4f} "
                f"{s.avg_r_bottom_quartile:>+9.4f} {s.lift:>+7.4f}{star}"
            )
        lines.append("  *** = strong discriminator  * = moderate\n")

    all_nl = [r.non_loss_rate for r in results]
    all_wr = [r.win_rate for r in results]
    all_r = [r.avg_r for r in results]
    all_tpw = [r.trades_per_week for r in results]
    lines.append(f"  ACHIEVABLE RANGES (across {len(results):,} tested recipes):")
    lines.append(f"    Non-loss (R>=0): {min(all_nl)*100:.1f}% — {max(all_nl)*100:.1f}%  (target: {targets.non_loss_rate*100:.0f}%)")
    lines.append(f"    Win Rate (R>0):  {min(all_wr)*100:.1f}% — {max(all_wr)*100:.1f}%")
    lines.append(f"    Avg R:           {min(all_r):+.3f} — {max(all_r):+.3f}  (target: {targets.avg_r:+.2f})")
    lines.append(f"    Trades/Week:     {min(all_tpw):.1f} — {max(all_tpw):.1f}  (target: {targets.trades_per_week:.0f})")

    gap_nl = targets.non_loss_rate - max(all_nl)
    gap_r = targets.avg_r - max(all_r)
    if gap_nl > 0.01:
        lines.append(f"    !! Non-loss target {targets.non_loss_rate*100:.0f}% exceeds best achievable {max(all_nl)*100:.1f}%")
    if gap_r > 0.01:
        lines.append(f"    !! Avg R target {targets.avg_r:+.2f} exceeds best achievable {max(all_r):+.3f}")

    lines.append("")
    lines.append(
        f"  {'SC_M':>4} {'Flow':>4} {'Enrg':>4} {'Strc':>4} {'MP':>4} {'Eldr':>4} {'FIP':>4} {'Phase':>8} {'Sq':>3} | "
        f"{'N':>5} {'T/wk':>5} {'NL%':>5} {'Win%':>5} {'AvgR':>5} | "
        f"{'OOS_R':>5} {'WFER':>5} | {'Score':>6}"
    )
    lines.append("-" * 135)

    seen = set()
    shown = 0
    for r in results:
        if shown >= top_n:
            break
        key = (r.n_trades, r.avg_r, r.non_loss_rate, r.phase_filter, r.elder_min, r.fip_min)
        if key in seen:
            continue
        seen.add(key)

        wfer_flag = " OK" if r.wfer >= 0.30 else " !!"
        ph_short = {"ANY": "ANY", "BUILDING": "BUILD", "BUILDING+STRONG": "BLD+STR"}.get(r.phase_filter, r.phase_filter)
        eld_str = f"{r.elder_min:>4.0f}" if r.elder_min > 0 else "  --"
        fip_str = f"{r.fip_min:>4.0f}" if r.fip_min > 0 else "  --"
        lines.append(
            f"  {r.sc_mom_min:>4.0f} {r.flow_min:>4.0f} {r.energy_min:>4.0f} "
            f"{r.structure_min:>4.0f} {r.mp_min:>4.0f} {eld_str} {fip_str} {ph_short:>8} {r.squeeze_min:>3.0f} | "
            f"{r.n_trades:>5} {r.trades_per_week:>5.1f} {r.non_loss_rate*100:>4.1f}% {r.win_rate*100:>4.1f}% {r.avg_r:>+5.2f} | "
            f"{r.oos_avg_r:>+5.2f} {r.wfer:>5.2f}{wfer_flag} | "
            f"{r.score:>+6.2f}"
        )
        shown += 1

    lines.append("-" * 120)

    passing_wfer = [r for r in results if r.wfer >= 0.30 and r.oos_avg_r > 0]
    passing_dsr = [r for r in results if r.dsr_pass]

    lines.append(f"\n  Total recipes tested:             {len(results):,}")
    lines.append(f"  Pass WFER >= 0.30 (generalises):  {len(passing_wfer)}")
    lines.append(f"  Pass DSR >= 0.95 (not luck):      {len(passing_dsr)}")

    validated = [r for r in results if r.wfer >= 0.30 and r.oos_avg_r > 0]
    if validated:
        best = validated[0]
        lines.append(f"\n  RECOMMENDED RECIPE (closest to targets + OOS validated):")
    elif results:
        best = results[0]
        lines.append(f"\n  CLOSEST MATCH (unvalidated — use with caution):")
    else:
        return "\n".join(lines)

    lines.append(f"    SC_MOMENTUM >= {best.sc_mom_min:.0f}")
    lines.append(f"    Flow        >= {best.flow_min:.0f}")
    lines.append(f"    Energy      >= {best.energy_min:.0f}")
    lines.append(f"    Structure   >= {best.structure_min:.0f}")
    lines.append(f"    MP          >= {best.mp_min:.0f}")
    lines.append(f"    Elder       >= {best.elder_min:.0f}" if best.elder_min > 0 else "    Elder:         OFF")
    lines.append(f"    FIP         >= {best.fip_min:.0f}" if best.fip_min > 0 else "    FIP:           OFF")
    lines.append(f"    Phase:         {best.phase_filter}")
    lines.append(f"    Squeeze >=     {best.squeeze_min:.0f}")
    lines.append(f"    ---")
    lines.append(f"    Trades: {best.n_trades} ({best.trades_per_week:.1f}/wk) | Non-loss: {best.non_loss_rate*100:.1f}% | Win: {best.win_rate*100:.1f}% | Avg R: {best.avg_r:+.3f}")
    lines.append(f"    Avg Win R: {best.avg_win_r:+.3f} | Avg Loss R: {best.avg_loss_r:+.3f} | Payoff: {best.payoff_ratio:.2f}:1")
    lines.append(f"    OOS: R={best.oos_avg_r:+.3f}, Win={best.oos_win_rate*100:.1f}% ({best.oos_n} trades)")
    lines.append(f"    WFER: {best.wfer:.2f} | DSR: {best.dsr:.4f}")
    lines.append(f"    Distance from targets: {best.target_distance:.2f} | Score: {best.score:+.2f}")

    lines.append("=" * 120)
    return "\n".join(lines)
