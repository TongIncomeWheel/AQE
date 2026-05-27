"""Protocol D -- Market close brief (04:00 SGT / 16:00 ET) + PTJ auto-run (04:30 SGT).

Composes the close brief (session P&L, EOD positions, trail events, SRM
delta, IBKR updates required, etc.) and triggers the PTJ pipeline.

The PTJ run itself is a separate component (existing AQE infrastructure or
the spec-referenced print-trade-journal SKILL). This protocol wires the
trigger + delivery; the PTJ engine is upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.aic.state import AICStateDB


@dataclass
class CloseBrief:
    timestamp_sgt: str
    session_pnl: float | None
    realised_pnl: float | None
    unrealised_pnl: float | None
    q2_cumulative_realised: float | None
    eod_positions: list[dict[str, Any]]
    trail_events: list[dict[str, Any]]
    srm_delta: list[dict[str, Any]]
    ibkr_updates: list[str]
    api_cost_today_usd: float
    notes: list[str] = field(default_factory=list)


def run_close_brief(
    session_id: str,
    eod_positions: list[dict[str, Any]] | None = None,
    trail_events: list[dict[str, Any]] | None = None,
    srm_delta: list[dict[str, Any]] | None = None,
    ibkr_updates: list[str] | None = None,
    db: AICStateDB | None = None,
) -> CloseBrief:
    db = db or AICStateDB()
    api_cost = db.session_cost_usd(session_id)
    return CloseBrief(
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        session_pnl=None,                # TODO: pull from PTJ
        realised_pnl=None,
        unrealised_pnl=None,
        q2_cumulative_realised=None,
        eod_positions=eod_positions or [],
        trail_events=trail_events or [],
        srm_delta=srm_delta or [],
        ibkr_updates=ibkr_updates or [],
        api_cost_today_usd=round(api_cost, 4),
    )


def run_ptj_auto(session_id: str) -> dict[str, Any]:
    """Trigger the print-trade-journal pipeline (existing component).

    This stub records that PTJ was requested. The actual PTJ engine lives
    outside the AIC layer per the spec ("PTJ JSON is canonical portfolio
    source. Never infer positions from conversation history.").
    """
    # TODO(deeper-build): subprocess.run or in-process call to the PTJ skill.
    return {
        "session_id": session_id,
        "ptj_triggered_at": datetime.now().isoformat(timespec="seconds"),
        "status": "queued",
        "note": "PTJ auto-run wiring is a stub. Hook to print-trade-journal SKILL.",
    }
