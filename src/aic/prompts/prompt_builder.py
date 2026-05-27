"""Voice system-prompt assembly.

Combines:
  1. The Appendix C template (identity / mandate / anchor / governance / output schema).
  2. The voice's speed-learning summary (PM upload via literature_loader, else
     `voice_config` default).
  3. Cell-specific tail: Deliberation Cell vote schema OR Risk Cell sizing-vote schema.

Returns a list of Anthropic SDK content blocks suitable for the `system` field
of `messages.create()`, with `cache_control: {"type":"ephemeral"}` so subsequent
calls within the cache TTL read at the discounted cache-read rate (spec §13).

CLI:
    python -m src.aic.prompts.prompt_builder
emits all 12 prompts as plain markdown under `src/aic/prompts/_compiled/`
for human review (the spec calls for `prompts/{voice}_system.md` files).
"""

from __future__ import annotations

from pathlib import Path

from src.aic.prompts.voice_config import (
    DELIBERATION_ORDER,
    RISK_STRUCTURE_ORDER,
    VOICES,
    VoiceConfig,
    get_voice,
)

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

DELIBERATION_OUTPUT_SCHEMA = """\
You receive: `candidate_brief` (the AQE-qualified candidate with all engine data,
PTRS components, DSL stop, R:R, DoR probabilities), `prior_voice_outputs` (the
voices that have already deliberated in this session -- REFERENCE ONLY, do not
anchor on them), and `session_state` (regime, capital, open positions, pipeline).

You PROVIDE, in this exact order:

  1. ANCHOR CITATION (1 sentence) -- first sentence MUST cite a specific
     framework or rule from your canonical text by name.
  2. ASSESSMENT through your specific lens (3-5 sentences).
  3. KEY RISK or FLAG (1-2 sentences) -- the thing that could break this trade.
  4. VOTE: APPROVE / REJECT / ABSTAIN.
  5. CONVICTION: X/10 (integer).
  6. KEY CONDITION (1 sentence) -- the single fact that would change your vote.

OUTPUT FORMAT (strict, parser will read these labels):
  ANCHOR: ...
  ASSESSMENT: ...
  RISK: ...
  VOTE: APPROVE | REJECT | ABSTAIN
  CONVICTION: X
  CONDITION: ...
"""

RISK_OUTPUT_SCHEMA = """\
You receive: `candidate_brief`, `delib_summary` (aggregate of the eight
Deliberation Cell outputs -- which voices approved, conviction, key risks),
`prior_voice_outputs` (Risk Cell voices that have already voted in this session
-- REFERENCE ONLY), and `session_state` (regime, dynamic capital, open positions,
combined stop-out risk so far).

You PROVIDE, in this exact order:

  1. ANCHOR CITATION (1 sentence) -- cite a specific framework from your text.
  2. ASSESSMENT through your specific lens (3-5 sentences).
  3. KEY RISK or FLAG (1-2 sentences).
  4. SIZING VOTE: FULL | HALF | QUARTER | BLOCK.
  5. CONVICTION: X/10 (integer).
  6. KEY CONDITION (1 sentence) -- what would change your sizing vote.

OUTPUT FORMAT (strict, parser will read these labels):
  ANCHOR: ...
  ASSESSMENT: ...
  RISK: ...
  SIZING_VOTE: FULL | HALF | QUARTER | BLOCK
  CONVICTION: X
  CONDITION: ...
"""

GOVERNANCE_BLOCK = """\
COMMITTEE GOVERNANCE (AIC Charter §3A):
  1. No validation drift. Agreement must be earned through analysis -- never deference.
  2. Challenge when warranted. Constructive dissent is an obligation, not an option.
  3. Independent conclusions first. Complete your own assessment before consensus forms.
  4. Each voice cites its own canonical literature before deliberation.
  5. Prior voice outputs are REFERENCE ONLY -- do not anchor on them.

NEVER defer to another voice. NEVER skip the anchor citation.
NEVER provide a verdict without reasoning.
"""


def _ordinal_in_cell(voice: VoiceConfig) -> str:
    if voice.cell == "deliberation":
        idx = DELIBERATION_ORDER.index(voice.voice_id) + 1
        return f"Voice {idx} of 8 in the Deliberation Cell"
    idx = RISK_STRUCTURE_ORDER.index(voice.voice_id) + 1
    return f"Voice {idx} of 4 in the Risk & Structure Cell"


def build_voice_prompt(
    voice_id: str,
    literature_override: str | None = None,
) -> str:
    """Assemble the full system prompt string for a voice.

    `literature_override` -- if PM has uploaded a richer literature summary
    via the spec's upload slots, the literature_loader passes it here and it
    replaces the default speed-learning summary. None -> use the default.
    """
    v = get_voice(voice_id)
    lit = (literature_override or v.speed_learning).strip()
    ordinal = _ordinal_in_cell(v)

    output_schema = (
        DELIBERATION_OUTPUT_SCHEMA
        if v.cell == "deliberation"
        else RISK_OUTPUT_SCHEMA
    )

    special = (
        f"\nSPECIAL AUTHORITY:\n  {v.special_authority}\n"
        if v.special_authority
        else ""
    )

    return f"""\
You are {v.name}, {v.title}, author of {v.texts}.

You are {ordinal} on the Aegis Investment Committee (AIC), governed by
Charter v1.8.2. The Deliberation Cell answers: "Is this trade worth taking?"
The Risk & Structure Cell answers: "Can the portfolio handle it, and at what size?"

You are speaking as the historical practitioner above. You ground every
assessment in your own canonical frameworks. You do not summarise other
voices; you bring your independent lens.

YOUR LITERATURE SUMMARY (cached context):
{lit}

YOUR MANDATE:
  {v.mandate}
{special}
ANCHOR REQUIREMENT: The first sentence of every assessment MUST cite a specific
framework, rule, or concept from your canonical text by name. No exceptions.

{GOVERNANCE_BLOCK}
{output_schema}
"""


def write_compiled_prompts(out_dir: Path | str | None = None) -> Path:
    """Write all 12 voice prompts to markdown files for human review.

    Spec requests `prompts/{voice}_system.md`. We honour that by emitting to
    `src/aic/prompts/_compiled/` so the live builder remains the Python module.
    """
    out_dir = Path(out_dir) if out_dir else (
        Path(__file__).resolve().parent / "_compiled"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for voice_id in VOICES:
        text = build_voice_prompt(voice_id)
        (out_dir / f"{voice_id}_system.md").write_text(text, encoding="utf-8")
    return out_dir


def build_system_blocks(
    voice_id: str,
    literature_override: str | None = None,
) -> list[dict]:
    """Return the Anthropic SDK `system` field shape with prompt caching.

    The full voice prompt is sent as a single cacheable text block per spec §13
    -- after the first call within the cache TTL, subsequent calls read it at
    the cache-read rate (90% reduction).
    """
    prompt = build_voice_prompt(voice_id, literature_override)
    return [
        {
            "type": "text",
            "text": prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


if __name__ == "__main__":
    out = write_compiled_prompts()
    print(f"Wrote {len(VOICES)} voice prompts to {out}")
    for voice_id in VOICES:
        text = build_voice_prompt(voice_id)
        print(f"  {voice_id:<14} {len(text):>5} chars")
