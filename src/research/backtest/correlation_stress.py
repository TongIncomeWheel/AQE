"""Correlated Loss Stress Test — the gap Monte Carlo can't see.

Monte Carlo shuffles trade order, which breaks natural loss clustering.
In reality, when the market drops, multiple positions stop out together.
This module reconstructs actual concurrent exposure from the trade log
and measures the REAL worst-case scenarios.

Questions answered:
  1. What was the worst day/week when multiple positions lost simultaneously?
  2. How long were you underwater and how long to recover?
  3. If ALL positions stopped out on the same day, what's the damage?
  4. Do your trade losses actually correlate (move together)?

Integrated into the portfolio sim output and the Streamlit dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StressResult:
    """Complete correlated loss stress test output."""
    # Concurrent exposure
    max_concurrent_positions: int
    max_concurrent_risk_pct: float      # peak % of capital simultaneously at risk
    avg_concurrent_positions: float

    # Worst realized losses (from actual trade log)
    worst_week_loss_pct: float           # worst calendar week P&L as % of capital
    worst_week_date: str                 # start of the worst week
    worst_week_n_losses: int             # how many positions lost that week

    # Drawdown duration
    max_underwater_days: int             # longest consecutive period below peak equity
    avg_underwater_days: float           # average drawdown recovery time

    # Theoretical max loss
    max_simultaneous_stop_pct: float     # if ALL open positions hit stop at once
    max_simultaneous_stop_dollar: float

    # Loss correlation
    loss_cluster_ratio: float            # % of losing trades that occur in clusters (>=2 losses same week)
    avg_losses_per_loss_week: float      # when you lose, how many losses at once?
    worst_cluster_n: int                 # biggest single-week loss cluster
    worst_cluster_r: float               # total R lost in worst cluster

    # Recovery
    longest_losing_streak: int           # consecutive losing trades
    longest_flat_streak: int             # consecutive trades with |R| < 0.1

    # Verdict
    survives_max_stress: bool            # can you survive worst-case and still trade?
    stress_grade: str                    # A/B/C/D/F


def run_correlation_stress(
    trades: list[dict],
    initial_capital: float = 70_000.0,
    risk_pct: float = 0.03,
    max_positions: int = 6,
) -> StressResult:
    """Run the full correlated loss stress test on a trade log.

    trades: list of trade dicts from portfolio_sim (must have entry_date,
            exit_bar, r_realized, net_pnl, shares, risk_per_share, sector).
    """
    if not trades:
        return _empty_stress()

    df = pd.DataFrame(trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df = df.sort_values("entry_date").reset_index(drop=True)

    # ── 1. Concurrent exposure ──────────────────────────────────────────
    # Estimate exit dates from entry + exit_bar trading days
    df["exit_date_est"] = df.apply(
        lambda r: r["entry_date"] + pd.offsets.BDay(int(r["exit_bar"])), axis=1
    )

    # Build daily concurrent position count
    all_dates = pd.bdate_range(df["entry_date"].min(), df["exit_date_est"].max())
    daily_concurrent = []
    daily_risk = []

    for d in all_dates:
        open_mask = (df["entry_date"] <= d) & (df["exit_date_est"] > d)
        n_open = open_mask.sum()
        risk_at_stake = df.loc[open_mask, "dollar_risk"].sum() if "dollar_risk" in df.columns else n_open * initial_capital * risk_pct
        daily_concurrent.append(n_open)
        daily_risk.append(risk_at_stake)

    max_concurrent = int(max(daily_concurrent)) if daily_concurrent else 0
    avg_concurrent = float(np.mean(daily_concurrent)) if daily_concurrent else 0
    max_risk = max(daily_risk) if daily_risk else 0
    max_risk_pct = max_risk / initial_capital * 100

    # ── 2. Weekly P&L clustering ────────────────────────────────────────
    df["entry_week"] = df["entry_date"].dt.to_period("W").dt.start_time
    df["exit_week"] = df["exit_date_est"].dt.to_period("W").dt.start_time

    # Group losses by the week they closed (exited)
    df["is_loss"] = df["r_realized"] < -0.05
    weekly_pnl = df.groupby("exit_week").agg(
        total_pnl=("net_pnl", "sum"),
        n_trades=("net_pnl", "count"),
        n_losses=("is_loss", "sum"),
        total_r=("r_realized", "sum"),
    ).reset_index()

    weekly_pnl["pnl_pct"] = weekly_pnl["total_pnl"] / initial_capital * 100

    if not weekly_pnl.empty:
        worst_week_idx = weekly_pnl["pnl_pct"].idxmin()
        worst_week = weekly_pnl.iloc[worst_week_idx]
        worst_week_pct = float(worst_week["pnl_pct"])
        worst_week_date = str(worst_week["exit_week"].date()) if hasattr(worst_week["exit_week"], "date") else str(worst_week["exit_week"])[:10]
        worst_week_n = int(worst_week["n_losses"])
    else:
        worst_week_pct = 0.0
        worst_week_date = "N/A"
        worst_week_n = 0

    # ── 3. Loss clusters ────────────────────────────────────────────────
    loss_weeks = weekly_pnl[weekly_pnl["n_losses"] >= 2]
    clustered_losses = int(loss_weeks["n_losses"].sum()) if not loss_weeks.empty else 0
    total_losses = int(df["is_loss"].sum())
    cluster_ratio = clustered_losses / total_losses if total_losses > 0 else 0

    loss_week_counts = weekly_pnl.loc[weekly_pnl["n_losses"] > 0, "n_losses"]
    avg_losses_per_week = float(loss_week_counts.mean()) if not loss_week_counts.empty else 0

    if not loss_weeks.empty:
        worst_cluster_idx = loss_weeks["n_losses"].idxmax()
        worst_cluster = loss_weeks.loc[worst_cluster_idx]
        worst_cluster_n = int(worst_cluster["n_losses"])
        worst_cluster_r = float(worst_cluster["total_r"])
    else:
        worst_cluster_n = 0
        worst_cluster_r = 0.0

    # ── 4. Drawdown duration ────────────────────────────────────────────
    pnls = df["net_pnl"].values
    equity_curve = np.cumsum(pnls) + initial_capital
    peak_equity = np.maximum.accumulate(equity_curve)
    in_drawdown = equity_curve < peak_equity

    # Find consecutive drawdown stretches
    underwater_stretches = []
    current_stretch = 0
    for is_dd in in_drawdown:
        if is_dd:
            current_stretch += 1
        else:
            if current_stretch > 0:
                underwater_stretches.append(current_stretch)
            current_stretch = 0
    if current_stretch > 0:
        underwater_stretches.append(current_stretch)

    max_underwater = max(underwater_stretches) if underwater_stretches else 0
    avg_underwater = float(np.mean(underwater_stretches)) if underwater_stretches else 0

    # Convert trade-count underwater to approximate calendar days
    avg_hold = float(df["exit_bar"].mean()) if not df.empty else 7
    max_underwater_days = int(max_underwater * avg_hold)
    avg_underwater_days = avg_underwater * avg_hold

    # ── 5. Theoretical max simultaneous stop-out ────────────────────────
    # Worst case: all positions at max capacity hit their stop on the same bar
    max_simul_loss = max_concurrent * initial_capital * risk_pct
    max_simul_pct = max_simul_loss / initial_capital * 100

    # ── 6. Streak analysis ──────────────────────────────────────────────
    rs = df["r_realized"].values

    # Losing streak
    max_lose_streak = 0
    current_streak = 0
    for r in rs:
        if r < -0.05:
            current_streak += 1
            max_lose_streak = max(max_lose_streak, current_streak)
        else:
            current_streak = 0

    # Flat streak (breakeven trades, |R| < 0.1 — dead money)
    max_flat_streak = 0
    current_streak = 0
    for r in rs:
        if abs(r) < 0.10:
            current_streak += 1
            max_flat_streak = max(max_flat_streak, current_streak)
        else:
            current_streak = 0

    # ── 7. Verdict ──────────────────────────────────────────────────────
    # Can you survive worst case and keep trading?
    # Worst case = max simultaneous stop + worst week repeated twice
    worst_scenario_pct = max_simul_pct + abs(worst_week_pct)

    if worst_scenario_pct <= 15:
        grade = "A"
    elif worst_scenario_pct <= 22:
        grade = "B"
    elif worst_scenario_pct <= 30:
        grade = "C"
    elif worst_scenario_pct <= 40:
        grade = "D"
    else:
        grade = "F"

    survives = worst_scenario_pct < 50  # can lose 50% and still trade

    return StressResult(
        max_concurrent_positions=max_concurrent,
        max_concurrent_risk_pct=round(max_risk_pct, 1),
        avg_concurrent_positions=round(avg_concurrent, 1),
        worst_week_loss_pct=round(worst_week_pct, 2),
        worst_week_date=worst_week_date,
        worst_week_n_losses=worst_week_n,
        max_underwater_days=max_underwater_days,
        avg_underwater_days=round(avg_underwater_days, 1),
        max_simultaneous_stop_pct=round(max_simul_pct, 1),
        max_simultaneous_stop_dollar=round(max_simul_loss, 0),
        loss_cluster_ratio=round(cluster_ratio, 3),
        avg_losses_per_loss_week=round(avg_losses_per_week, 1),
        worst_cluster_n=worst_cluster_n,
        worst_cluster_r=round(worst_cluster_r, 2),
        longest_losing_streak=max_lose_streak,
        longest_flat_streak=max_flat_streak,
        survives_max_stress=survives,
        stress_grade=grade,
    )


def format_stress_report(s: StressResult, capital: float = 70_000.0) -> str:
    """Plain-text stress test report."""
    lines = []
    lines.append("=" * 80)
    lines.append("  CORRELATED LOSS STRESS TEST")
    lines.append("  What Monte Carlo can't see: losses that cluster together")
    lines.append("=" * 80)

    lines.append("\n  CONCURRENT EXPOSURE")
    lines.append("  " + "-" * 50)
    lines.append(f"  Peak concurrent positions:  {s.max_concurrent_positions}")
    lines.append(f"  Avg concurrent positions:   {s.avg_concurrent_positions:.1f}")
    lines.append(f"  Peak capital at risk:        {s.max_concurrent_risk_pct:.1f}% (${s.max_concurrent_risk_pct/100*capital:,.0f})")

    lines.append("\n  WORST WEEK (actual, from trade log)")
    lines.append("  " + "-" * 50)
    lines.append(f"  Worst week P&L:             {s.worst_week_loss_pct:+.2f}% (${s.worst_week_loss_pct/100*capital:+,.0f})")
    lines.append(f"  Week of:                    {s.worst_week_date}")
    lines.append(f"  Losing trades that week:    {s.worst_week_n_losses}")

    lines.append("\n  LOSS CLUSTERING")
    lines.append("  " + "-" * 50)
    lines.append(f"  Losses in clusters (2+/wk): {s.loss_cluster_ratio*100:.0f}% of all losses")
    lines.append(f"  Avg losses per loss-week:   {s.avg_losses_per_loss_week:.1f}")
    lines.append(f"  Worst single cluster:       {s.worst_cluster_n} losses, {s.worst_cluster_r:+.1f}R total")

    lines.append("\n  DRAWDOWN DURATION")
    lines.append("  " + "-" * 50)
    lines.append(f"  Longest underwater:         ~{s.max_underwater_days} calendar days")
    lines.append(f"  Avg recovery time:          ~{s.avg_underwater_days:.0f} calendar days")

    lines.append("\n  THEORETICAL MAX LOSS (all positions stopped same day)")
    lines.append("  " + "-" * 50)
    lines.append(f"  Max positions x 3% risk:    {s.max_simultaneous_stop_pct:.1f}% = ${s.max_simultaneous_stop_dollar:,.0f}")
    lines.append(f"  Your capital after:         ${capital - s.max_simultaneous_stop_dollar:,.0f}")

    lines.append("\n  STREAKS")
    lines.append("  " + "-" * 50)
    lines.append(f"  Longest losing streak:      {s.longest_losing_streak} consecutive losses")
    lines.append(f"  Longest flat streak:         {s.longest_flat_streak} consecutive breakeven trades")

    lines.append("\n  " + "=" * 50)
    lines.append(f"  STRESS GRADE: {s.stress_grade}")
    if s.stress_grade == "A":
        lines.append("  Max stress < 15% of capital. Comfortable.")
    elif s.stress_grade == "B":
        lines.append("  Max stress 15-22%. Manageable but painful.")
    elif s.stress_grade == "C":
        lines.append("  Max stress 22-30%. You WILL question the system.")
    elif s.stress_grade == "D":
        lines.append("  Max stress 30-40%. Psychologically brutal. Consider smaller size.")
    else:
        lines.append("  Max stress > 40%. Account survival at risk. Reduce position count or risk%.")

    lines.append(f"  Survives worst case: {'YES' if s.survives_max_stress else 'NO — reduce risk'}")
    lines.append("=" * 80)

    return "\n".join(lines)


def stress_to_dict(s: StressResult) -> dict:
    """Convert to JSON-serializable dict (pure Python types)."""
    def _py(v):
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
        return v

    return {k: _py(v) for k, v in {
        "max_concurrent_positions": s.max_concurrent_positions,
        "max_concurrent_risk_pct": s.max_concurrent_risk_pct,
        "avg_concurrent_positions": s.avg_concurrent_positions,
        "worst_week_loss_pct": s.worst_week_loss_pct,
        "worst_week_date": s.worst_week_date,
        "worst_week_n_losses": s.worst_week_n_losses,
        "max_underwater_days": s.max_underwater_days,
        "avg_underwater_days": s.avg_underwater_days,
        "max_simultaneous_stop_pct": s.max_simultaneous_stop_pct,
        "max_simultaneous_stop_dollar": s.max_simultaneous_stop_dollar,
        "loss_cluster_ratio": s.loss_cluster_ratio,
        "avg_losses_per_loss_week": s.avg_losses_per_loss_week,
        "worst_cluster_n": s.worst_cluster_n,
        "worst_cluster_r": s.worst_cluster_r,
        "longest_losing_streak": s.longest_losing_streak,
        "longest_flat_streak": s.longest_flat_streak,
        "survives_max_stress": s.survives_max_stress,
        "stress_grade": s.stress_grade,
    }.items()}


def _empty_stress() -> StressResult:
    return StressResult(
        max_concurrent_positions=0, max_concurrent_risk_pct=0, avg_concurrent_positions=0,
        worst_week_loss_pct=0, worst_week_date="N/A", worst_week_n_losses=0,
        max_underwater_days=0, avg_underwater_days=0,
        max_simultaneous_stop_pct=0, max_simultaneous_stop_dollar=0,
        loss_cluster_ratio=0, avg_losses_per_loss_week=0,
        worst_cluster_n=0, worst_cluster_r=0,
        longest_losing_streak=0, longest_flat_streak=0,
        survives_max_stress=True, stress_grade="A",
    )
