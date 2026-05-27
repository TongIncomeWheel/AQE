"""Risk & Structure Cell -- 4 voting voices, sequential, sizing vote.

Charter §3A + §6A. Runs only AFTER the Deliberation Cell approves (>=5/8).
Each voice votes FULL / HALF / QUARTER / BLOCK. Majority 3/4 carries.
Elder holds hard-block authority -- combined stop-out >5% of dynamic capital
triggers BLOCK regardless of other votes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from src.aic.alfred.llm_client import AICLLMClient
from src.aic.alfred.orchestrator import (
    StopOutAssessment,
    assess_combined_stopout,
)
from src.aic.committee.literature_loader import load_literature
from src.aic.committee.vote_parser import (
    SizingVote,
    parse_sizing_vote,
)
from src.aic.prompts.voice_config import RISK_STRUCTURE_ORDER


SIZING_MAJORITY = 3                  # 3/4 needed for FULL/HALF/QUARTER
SIZING_FALLBACK = "QUARTER"          # if no majority, default to most conservative non-BLOCK


@dataclass
class RiskCellResult:
    candidate_ticker: str
    sizing: str                      # FULL / HALF / QUARTER / BLOCK
    elder_hard_block: bool
    stopout: StopOutAssessment | None
    voice_votes: list[SizingVote]
    cost_usd_total: float = 0.0
    notes: list[str] = field(default_factory=list)


def _tally_sizing(votes: list[SizingVote]) -> tuple[str, list[str]]:
    """Pick the sizing winner. Returns (sizing, notes)."""
    counts = Counter(v.sizing_vote for v in votes)
    notes: list[str] = []

    # Elder BLOCK is hard regardless of count -- but the hard-block check is
    # done separately at assess_combined_stopout level; here we still respect
    # Elder if it voted BLOCK on the 2% rule etc.
    if any(v.voice_id == "elder" and v.sizing_vote == "BLOCK" for v in votes):
        return "BLOCK", ["Elder voted BLOCK (Charter §6A or 2% rule)."]

    most_common, count = counts.most_common(1)[0]
    if count >= SIZING_MAJORITY:
        return most_common, [f"{count}/4 majority for {most_common}."]

    # No majority -- be conservative.
    notes.append(
        f"No 3/4 majority (votes={dict(counts)}). Defaulting to {SIZING_FALLBACK}."
    )
    return SIZING_FALLBACK, notes


def run_risk_cell(
    candidate_brief: dict,
    delib_summary: dict,
    session_state: dict,
    *,
    proposed_entry: float,
    proposed_stop: float,
    proposed_shares: int,
    open_positions: list[dict],
    dynamic_capital_usd: float,
    llm_client: AICLLMClient | None = None,
    spec_path: str | None = None,
) -> RiskCellResult:
    """Execute the 4-voice Risk & Structure Cell sequentially.

    The cell sees the candidate brief + the deliberation summary (the 8 voices
    that approved). It produces a sizing recommendation.

    Elder hard-block: if combined stop-out post-entry >5% of dynamic capital,
    the cell short-circuits to BLOCK before any LLM call. Cheap and correct.
    """
    if llm_client is None:
        llm_client = AICLLMClient()

    # ---- Elder mechanical hard-block (Charter §6A) ----
    stopout = assess_combined_stopout(
        open_positions=open_positions,
        proposed_entry=proposed_entry,
        proposed_stop=proposed_stop,
        proposed_shares=proposed_shares,
        dynamic_capital_usd=dynamic_capital_usd,
    )
    if stopout.breaches_5pct:
        return RiskCellResult(
            candidate_ticker=str(candidate_brief.get("ticker", "?")),
            sizing="BLOCK",
            elder_hard_block=True,
            stopout=stopout,
            voice_votes=[],
            cost_usd_total=0.0,
            notes=[
                "Elder hard-block triggered before Risk Cell ran: "
                f"combined stop-out {stopout.combined_usd:.0f} "
                f"({stopout.combined_pct:.2f}%) exceeds 5% of dynamic capital "
                f"({dynamic_capital_usd:.0f}). Charter §6A: no override.",
            ],
        )

    # ---- Otherwise: full 4-voice sequential vote ----
    literature = load_literature(spec_path)
    voice_votes: list[SizingVote] = []
    prior_outputs: list[dict] = []
    total_cost = 0.0

    for voice_id in RISK_STRUCTURE_ORDER:
        result = llm_client.voice_call(
            voice_id=voice_id,
            candidate_brief=candidate_brief,
            prior_outputs=prior_outputs,
            session_state=session_state,
            delib_summary=delib_summary,
            literature_override=literature.get(voice_id),
        )
        parsed = parse_sizing_vote(voice_id, result.text)
        voice_votes.append(parsed)
        total_cost += result.cost_usd
        prior_outputs.append({
            "voice_id": voice_id,
            "sizing_vote": parsed.sizing_vote,
            "conviction": parsed.conviction,
            "anchor": parsed.anchor[:200],
            "risk_flag": parsed.risk[:200],
        })

    sizing, tally_notes = _tally_sizing(voice_votes)

    return RiskCellResult(
        candidate_ticker=str(candidate_brief.get("ticker", "?")),
        sizing=sizing,
        elder_hard_block=False,
        stopout=stopout,
        voice_votes=voice_votes,
        cost_usd_total=round(total_cost, 4),
        notes=tally_notes,
    )
