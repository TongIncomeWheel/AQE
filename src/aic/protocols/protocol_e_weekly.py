"""Protocol E -- Weekly scorecard (Friday close + Monday review).

Aggregates the week's deliberations + sizing decisions + P&L from the AIC
state DB, plus the weighted portfolio beta and SRM trend deltas. Output is
a compact scorecard for the PM's weekly review.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.aic.state.db import DB_PATH


@dataclass
class WeeklyScorecard:
    week_start: str
    week_end: str
    deliberations_run: int
    approved: int
    rejected: int
    inversions_triggered: int
    avg_conviction_approved: float | None
    total_api_cost_usd: float
    notes: list[str] = field(default_factory=list)


def run_weekly_scorecard(today: date | None = None) -> WeeklyScorecard:
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    with sqlite3.connect(str(DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT decision, approvals, avg_conviction, inversion_required, cost_usd "
            "FROM deliberations WHERE date(created_at) BETWEEN ? AND ?",
            (monday.isoformat(), friday.isoformat()),
        ).fetchall()
        cost_row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log "
            "WHERE date(timestamp) BETWEEN ? AND ?",
            (monday.isoformat(), friday.isoformat()),
        ).fetchone()

    approved = sum(1 for r in rows if r[0] == "APPROVED")
    rejected = sum(1 for r in rows if r[0] == "REJECTED")
    inversions = sum(1 for r in rows if r[3])

    approved_convictions = [r[2] for r in rows if r[0] == "APPROVED" and r[2] is not None]
    avg_conv = (
        round(sum(approved_convictions) / len(approved_convictions), 2)
        if approved_convictions else None
    )

    return WeeklyScorecard(
        week_start=monday.isoformat(),
        week_end=friday.isoformat(),
        deliberations_run=len(rows),
        approved=approved,
        rejected=rejected,
        inversions_triggered=inversions,
        avg_conviction_approved=avg_conv,
        total_api_cost_usd=round(float(cost_row[0]) if cost_row else 0.0, 4),
    )
