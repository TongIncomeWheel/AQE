"""Deliberation Cell -- 8 voting voices, sequential, 5/8 approval threshold.

Charter §3A. Runs BEFORE Risk Cell. Each voice receives the candidate_brief,
prior voice outputs (reference only), and the session_state. Each emits a
vote (APPROVE/REJECT/ABSTAIN) with conviction 1-10 and an anchor citation.

Inversion Mandate: 8/8 unanimous (either direction) -> Steenbarger argues
the strongest counter-case before Risk Cell is invoked. Owned by Steenbarger
per Charter §3A rule 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.aic.alfred.llm_client import AICLLMClient, APIOverloadedError
from src.aic.committee.literature_loader import load_literature
from src.aic.committee.vote_parser import (
    DeliberationVote,
    parse_deliberation_vote,
)
from src.aic.prompts.voice_config import DELIBERATION_ORDER


# 5/8 majority approves. avg-conviction below this is flagged but does NOT auto-reject.
APPROVAL_THRESHOLD = 5
AVG_CONVICTION_FLAG = 6.5


@dataclass
class DeliberationResult:
    candidate_ticker: str
    decision: str                      # "APPROVED" or "REJECTED"
    approvals: int                     # 0..8
    rejections: int
    abstentions: int
    avg_conviction: float
    low_conviction_flag: bool          # avg < 6.5
    inversion_required: bool           # 0/8 or 8/8 unanimous
    voice_votes: list[DeliberationVote]
    cost_usd_total: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_summary(self) -> dict:
        """Compact summary -- the structure handed to the Risk Cell as `delib_summary`."""
        return {
            "decision": self.decision,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "abstentions": self.abstentions,
            "avg_conviction": round(self.avg_conviction, 2),
            "low_conviction_flag": self.low_conviction_flag,
            "inversion_required": self.inversion_required,
            "voice_votes": [
                {
                    "voice_id": v.voice_id,
                    "vote": v.vote,
                    "conviction": v.conviction,
                    "anchor": v.anchor[:200],
                    "risk": v.risk[:200],
                    "condition": v.condition[:200],
                }
                for v in self.voice_votes
            ],
        }


def run_deliberation_cell(
    candidate_brief: dict,
    session_state: dict,
    llm_client: AICLLMClient | None = None,
    spec_path: str | None = None,
) -> DeliberationResult:
    """Execute the 8-voice Deliberation Cell sequentially.

    The sequence is fixed (Charter §3A): each voice sees the brief + the
    voices that ran before it (REFERENCE only). On API failure for a given
    voice, the cell raises APIOverloadedError up to the caller -- candidate
    is parked as WATCH per spec §15 / Screen S18.
    """
    if llm_client is None:
        llm_client = AICLLMClient()

    literature = load_literature(spec_path)
    voice_votes: list[DeliberationVote] = []
    prior_outputs: list[dict] = []
    total_cost = 0.0

    for voice_id in DELIBERATION_ORDER:
        try:
            result = llm_client.voice_call(
                voice_id=voice_id,
                candidate_brief=candidate_brief,
                prior_outputs=prior_outputs,
                session_state=session_state,
                literature_override=literature.get(voice_id),
            )
        except APIOverloadedError:
            # Surface to caller; candidate must be parked.
            raise

        parsed = parse_deliberation_vote(voice_id, result.text)
        voice_votes.append(parsed)
        total_cost += result.cost_usd

        # Pass a compact reference into the next voice -- not the full text.
        prior_outputs.append({
            "voice_id": voice_id,
            "vote": parsed.vote,
            "conviction": parsed.conviction,
            "anchor": parsed.anchor[:200],
            "risk_flag": parsed.risk[:200],
        })

    approvals = sum(1 for v in voice_votes if v.vote == "APPROVE")
    rejections = sum(1 for v in voice_votes if v.vote == "REJECT")
    abstentions = sum(1 for v in voice_votes if v.vote == "ABSTAIN")
    avg_conviction = sum(v.conviction for v in voice_votes) / max(1, len(voice_votes))

    decision = "APPROVED" if approvals >= APPROVAL_THRESHOLD else "REJECTED"
    low_flag = avg_conviction < AVG_CONVICTION_FLAG
    inversion_required = (approvals == 0 or approvals == 8)

    notes: list[str] = []
    if low_flag and decision == "APPROVED":
        notes.append(
            f"Avg conviction {avg_conviction:.2f} below {AVG_CONVICTION_FLAG}: "
            "advance to PM with flag (Charter §3A)."
        )
    if inversion_required:
        notes.append(
            f"{approvals}/8 unanimous -- Steenbarger Inversion mandate triggered. "
            "Counter-argument required before Risk Cell runs."
        )

    return DeliberationResult(
        candidate_ticker=str(candidate_brief.get("ticker", "?")),
        decision=decision,
        approvals=approvals,
        rejections=rejections,
        abstentions=abstentions,
        avg_conviction=round(avg_conviction, 2),
        low_conviction_flag=low_flag,
        inversion_required=inversion_required,
        voice_votes=voice_votes,
        cost_usd_total=round(total_cost, 4),
        notes=notes,
    )


def run_steenbarger_inversion(
    candidate_brief: dict,
    deliberation_result: DeliberationResult,
    session_state: dict,
    llm_client: AICLLMClient | None = None,
    spec_path: str | None = None,
) -> tuple[str, float]:
    """Ask Steenbarger to argue the strongest counter-case to a unanimous consensus.

    Returns (counter_argument_text, cost_usd). The PM reviews this text
    before the Risk Cell is allowed to run (UI screen S09 enforces a
    scroll-to-bottom proceed gate -- not yet built; surface via STATUS).
    """
    if llm_client is None:
        llm_client = AICLLMClient()
    literature = load_literature(spec_path)

    inversion_brief = {
        **candidate_brief,
        "INVERSION_MANDATE": (
            f"The Deliberation Cell reached {deliberation_result.approvals}/8 consensus. "
            "Per Charter §3A rule 3, you (Steenbarger) MUST argue the strongest possible "
            "counter-case before the Risk Cell runs. Unanimous consensus conceals blind "
            "spots. Stress-test the dependencies, the macro, the sizing, and the process. "
            "Do not vote -- argue."
        ),
        "deliberation_summary": deliberation_result.as_summary(),
    }
    result = llm_client.voice_call(
        voice_id="steenbarger",
        candidate_brief=inversion_brief,
        prior_outputs=[],
        session_state=session_state,
        literature_override=literature.get("steenbarger"),
        max_tokens=1800,
        temperature=0.5,
    )
    return result.text, result.cost_usd
