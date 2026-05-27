"""Protocol B -- Candidate qualification (spec §11 + §9B + §3A).

The end-to-end candidate flow:
  B1 sourcing       AQE PIPE_RANK >=60 (top 10-15) -- read from AQE export.
  B2 engine gates   SC_MOMENTUM, Elder, all engine floors.
  B3 PTRS           Alfred computes; >=65 qualifies.
  B4 portfolio risk beta, correlation, sector exposure, combined stop-out.
  B5 R:R            >=2:1 vs committee-designated target.
  B6 Deliberation   8 voices, 5/8 majority. Inversion if 8/8.
  B7 Risk Cell      4 voices, 3/4 sizing. Elder hard-block if >5%.
  B8 Execution brief assembled. PM decides BRACKET / WATCH / KILL.

This function returns a structured `QualificationResult` for the UI / PM
notification. It does not (yet) push to Telegram or write to Drive -- those
external integrations are wired separately in `delivery.telegram_client`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from src.aic.alfred.llm_client import AICLLMClient, APIOverloadedError
from src.aic.alfred.orchestrator import (
    GateSequenceResult,
    RAStatus,
    classify_regime,
    run_gate_sequence,
)
from src.aic.committee.deliberation_cell import (
    DeliberationResult,
    run_deliberation_cell,
    run_steenbarger_inversion,
)
from src.aic.committee.risk_cell import RiskCellResult, run_risk_cell
from src.aic.data.aqe_reader import CandidateBrief
from src.aic.state import AICStateDB


QualOutcome = Literal[
    "QUALIFIED_BRACKET",     # delib approved + risk cell sized
    "QUALIFIED_INVERSION",   # delib unanimous; awaiting PM ack on inversion
    "REJECTED_GATE",         # one of gates 1-8 failed
    "REJECTED_DELIBERATION", # <5/8 approval
    "BLOCKED_RISK",          # Elder hard-block or 4/4 BLOCK from Risk Cell
    "ERROR_API",             # API overloaded after retries (Anthropic 529)
]


@dataclass
class QualificationResult:
    candidate_ticker: str
    outcome: QualOutcome
    gate_result: GateSequenceResult | None = None
    deliberation: DeliberationResult | None = None
    inversion_text: str | None = None
    risk: RiskCellResult | None = None
    sizing: str | None = None        # FULL / HALF / QUARTER / BLOCK
    cost_usd_total: float = 0.0
    notes: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def qualify_candidate(
    candidate: CandidateBrief,
    *,
    session_id: str,
    session_state: dict,
    pipeline_count: int,
    ra_status: RAStatus,
    vix: float,
    proposed_shares: int,
    open_positions: list[dict],
    dynamic_capital_usd: float,
    llm_client: AICLLMClient | None = None,
    db: AICStateDB | None = None,
    auto_run_inversion: bool = True,
) -> QualificationResult:
    """End-to-end Protocol B for one candidate.

    Returns a `QualificationResult` describing exactly where the candidate
    landed in the funnel. Side-effects: writes the deliberation + inversion
    (if triggered) to the AIC state DB so the UI can render history.
    """
    db = db or AICStateDB()
    notes: list[str] = []

    # ---- Gates 1-8 (Charter §9B) ----
    rr_to_target = _safe_rr(candidate)
    gate = run_gate_sequence(
        ticker=candidate.ticker,
        sc_momentum=candidate.sc_momentum,
        elder_score=candidate.elder_score,
        flow_100=candidate.flow_100,
        energy_100=candidate.energy_100,
        structure_100=candidate.structure_100,
        mp_100=candidate.mp_100,
        sector_grade=candidate.sector_grade or "WATCH",
        sector_corr=candidate.sector_corr,
        rr_to_committee_target=rr_to_target,
        sma_distance_pct=candidate.sma_distance_pct or 0.0,
        ra_status=ra_status,
        vix=vix,
        pipeline_count=pipeline_count,
    )
    if not gate.qualified:
        return QualificationResult(
            candidate_ticker=candidate.ticker,
            outcome="REJECTED_GATE",
            gate_result=gate,
            notes=[f"Failed at gate {gate.failed_gate}."],
        )

    # ---- Deliberation Cell (§3A) ----
    brief = _candidate_to_brief(candidate, gate)
    try:
        delib = run_deliberation_cell(
            candidate_brief=brief,
            session_state=session_state,
            llm_client=llm_client,
        )
    except APIOverloadedError as e:
        return QualificationResult(
            candidate_ticker=candidate.ticker,
            outcome="ERROR_API",
            gate_result=gate,
            notes=[f"Anthropic API overloaded: {e}. Candidate parked as WATCH."],
        )

    deliberation_id = f"delib-{candidate.ticker}-{uuid.uuid4().hex[:8]}"
    db.record_deliberation(
        deliberation_id=deliberation_id,
        session_id=session_id,
        ticker=candidate.ticker,
        decision=delib.decision,
        approvals=delib.approvals,
        rejections=delib.rejections,
        abstentions=delib.abstentions,
        avg_conviction=delib.avg_conviction,
        inversion_required=delib.inversion_required,
        sizing=None,
        cost_usd=delib.cost_usd_total,
        payload=delib.as_summary(),
    )

    if delib.decision == "REJECTED":
        return QualificationResult(
            candidate_ticker=candidate.ticker,
            outcome="REJECTED_DELIBERATION",
            gate_result=gate,
            deliberation=delib,
            cost_usd_total=delib.cost_usd_total,
            notes=delib.notes,
        )

    # ---- Inversion mandate (8/8 unanimous either direction) ----
    inversion_text: str | None = None
    inversion_cost = 0.0
    if delib.inversion_required and auto_run_inversion:
        inversion_text, inversion_cost = run_steenbarger_inversion(
            candidate_brief=brief,
            deliberation_result=delib,
            session_state=session_state,
            llm_client=llm_client,
        )
        db.record_inversion(
            inversion_id=f"inv-{deliberation_id}",
            deliberation_id=deliberation_id,
            counter_argument=inversion_text,
            cost_usd=inversion_cost,
        )
        # Per Charter §3A rule 3 + Screen S09: PM must read inversion before
        # Risk Cell runs. Return early so the UI gates on PM acknowledgement.
        return QualificationResult(
            candidate_ticker=candidate.ticker,
            outcome="QUALIFIED_INVERSION",
            gate_result=gate,
            deliberation=delib,
            inversion_text=inversion_text,
            cost_usd_total=delib.cost_usd_total + inversion_cost,
            notes=delib.notes + [
                "PM must acknowledge Steenbarger Inversion before Risk Cell runs."
            ],
        )

    # ---- Risk & Structure Cell (§6A) ----
    risk = run_risk_cell(
        candidate_brief=brief,
        delib_summary=delib.as_summary(),
        session_state=session_state,
        proposed_entry=candidate.entry or 0.0,
        proposed_stop=candidate.stop or 0.0,
        proposed_shares=proposed_shares,
        open_positions=open_positions,
        dynamic_capital_usd=dynamic_capital_usd,
        llm_client=llm_client,
    )

    if risk.elder_hard_block or risk.sizing == "BLOCK":
        return QualificationResult(
            candidate_ticker=candidate.ticker,
            outcome="BLOCKED_RISK",
            gate_result=gate,
            deliberation=delib,
            risk=risk,
            sizing=risk.sizing,
            cost_usd_total=delib.cost_usd_total + inversion_cost + risk.cost_usd_total,
            notes=delib.notes + risk.notes,
        )

    return QualificationResult(
        candidate_ticker=candidate.ticker,
        outcome="QUALIFIED_BRACKET",
        gate_result=gate,
        deliberation=delib,
        risk=risk,
        sizing=risk.sizing,
        cost_usd_total=delib.cost_usd_total + inversion_cost + risk.cost_usd_total,
        notes=delib.notes + risk.notes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_rr(c: CandidateBrief) -> float:
    """R:R vs committee-designated target. Best-effort from available levels."""
    if c.entry and c.stop and c.tp_2r:
        risk = max(0.001, c.entry - c.stop)
        return round((c.tp_2r - c.entry) / risk, 2)
    if c.rr_est is not None:
        return float(c.rr_est)
    return 0.0


def _candidate_to_brief(c: CandidateBrief, gate: GateSequenceResult) -> dict:
    """Compact dict handed to every voice and Alfred."""
    return {
        "ticker": c.ticker,
        "source": c.source,
        "engines": {
            "flow": c.flow_100, "energy": c.energy_100,
            "structure": c.structure_100, "mp": c.mp_100,
            "elder": c.elder_score, "bq": c.bq_100,
        },
        "sc_momentum": c.sc_momentum,
        "sc_momentum_raw": c.sc_momentum_raw,
        "pipe_rank": c.pipe_rank,
        "levels": {
            "entry": c.entry, "stop": c.stop,
            "tp_1r": c.tp_1r, "tp_2r": c.tp_2r, "tp_3r": c.tp_3r,
            "rr_pct": c.rr_pct, "rr_est": c.rr_est,
            "shares": c.shares,
        },
        "fib": c.fib,
        "elder_5d": c.elder_5d,
        "beta_30d": c.beta_30d, "beta_60d": c.beta_60d,
        "dsg13": {
            "sector_corr": c.sector_corr,
            "breakout_stop": c.breakout_stop,
            "gics_sector": c.gics_sector,
            "sma_distance_pct": c.sma_distance_pct,
            "held": c.held,
        },
        "sector_grade": c.sector_grade,
        "ptrs": {
            "value": gate.ptrs.ptrs if gate.ptrs else None,
            "sc_momentum": gate.ptrs.sc_momentum if gate.ptrs else None,
            "sh": gate.ptrs.sh if gate.ptrs else None,
            "ra": gate.ptrs.ra if gate.ptrs else None,
            "rl": gate.ptrs.rl if gate.ptrs else None,
            "regime": gate.ptrs.regime if gate.ptrs else None,
        },
    }
