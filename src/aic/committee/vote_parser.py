"""Parse voice response text into structured dicts.

The voice system prompts (prompt_builder.py) instruct each model to emit
labelled sections (ANCHOR, ASSESSMENT, RISK, VOTE, CONVICTION, CONDITION).
Risk Cell voices emit SIZING_VOTE instead of VOTE. This module parses that.

Robustness: models occasionally vary case or whitespace; the parser is
case-insensitive on labels and accepts inline-or-block content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


VOTE_VALUES = {"APPROVE", "REJECT", "ABSTAIN"}
SIZING_VALUES = {"FULL", "HALF", "QUARTER", "BLOCK"}

# Captures `LABEL: <text>` until next labelled line or end of string.
def _section(label: str, text: str) -> str | None:
    pat = rf"(?im)^\s*{re.escape(label)}\s*:\s*(.*?)(?=^\s*[A-Z_]+\s*:|\Z)"
    m = re.search(pat, text, flags=re.DOTALL | re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


@dataclass
class DeliberationVote:
    voice_id: str
    anchor: str
    assessment: str
    risk: str
    vote: str            # APPROVE / REJECT / ABSTAIN
    conviction: int      # 1-10
    condition: str
    raw_text: str

    @property
    def is_approve(self) -> bool:
        return self.vote == "APPROVE"


@dataclass
class SizingVote:
    voice_id: str
    anchor: str
    assessment: str
    risk: str
    sizing_vote: str     # FULL / HALF / QUARTER / BLOCK
    conviction: int
    condition: str
    raw_text: str


def parse_conviction(raw: str | None) -> int:
    """Pull an integer 1-10 from a conviction line. Defaults to 5 if unclear."""
    if not raw:
        return 5
    m = re.search(r"(-?\d+)", raw)
    if not m:
        return 5
    try:
        v = int(m.group(1))
    except ValueError:
        return 5
    return max(1, min(10, v))


def _normalise_vote(raw: str | None, allowed: set[str]) -> str:
    if not raw:
        return "ABSTAIN" if "ABSTAIN" in allowed else "BLOCK"
    token = raw.strip().split()[0].upper().strip(".,:|/")
    if token in allowed:
        return token
    for value in allowed:
        if value in raw.upper():
            return value
    return "ABSTAIN" if "ABSTAIN" in allowed else "BLOCK"


def parse_deliberation_vote(voice_id: str, text: str) -> DeliberationVote:
    return DeliberationVote(
        voice_id=voice_id,
        anchor=_section("ANCHOR", text) or "",
        assessment=_section("ASSESSMENT", text) or "",
        risk=_section("RISK", text) or "",
        vote=_normalise_vote(_section("VOTE", text), VOTE_VALUES),
        conviction=parse_conviction(_section("CONVICTION", text)),
        condition=_section("CONDITION", text) or "",
        raw_text=text,
    )


def parse_sizing_vote(voice_id: str, text: str) -> SizingVote:
    return SizingVote(
        voice_id=voice_id,
        anchor=_section("ANCHOR", text) or "",
        assessment=_section("ASSESSMENT", text) or "",
        risk=_section("RISK", text) or "",
        sizing_vote=_normalise_vote(_section("SIZING_VOTE", text), SIZING_VALUES),
        conviction=parse_conviction(_section("CONVICTION", text)),
        condition=_section("CONDITION", text) or "",
        raw_text=text,
    )
