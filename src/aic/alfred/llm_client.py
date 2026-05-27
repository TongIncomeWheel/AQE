"""Anthropic SDK wrapper for the AIC layer.

Per spec §13:
  - Voice calls (Deliberation + Risk Cell) use `claude-opus-4-6`.
  - Alfred orchestration uses `claude-sonnet-4-6`.
  - System prompts are sent as a single text block with
    `cache_control: {"type": "ephemeral"}` so subsequent calls within the
    cache TTL read at the cache-read rate (90% reduction).
  - Cost is tracked per call and persisted to `state.db.cost_log`.

Per spec §15:
  - On HTTP 529 (overloaded) -> exponential backoff retry, 3 attempts.
  - On persistent failure -> raise; caller parks candidate as WATCH.

Dependencies:
  - `anthropic` SDK (added to requirements.txt by this build).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from src.aic.config import assert_required, get_credential
from src.aic.prompts import build_system_blocks


# Pricing per spec §13 — $/token (already divided by 1e6).
RATES: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 5.0/1e6,  "output": 25.0/1e6, "cache_read": 0.5/1e6},
    "claude-sonnet-4-6": {"input": 3.0/1e6,  "output": 15.0/1e6, "cache_read": 0.3/1e6},
}

# Model assignments
MODEL_VOICE = "claude-opus-4-6"
MODEL_ALFRED = "claude-sonnet-4-6"

# Retry behaviour for 529 / transient errors (spec §15)
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2.0


class APIOverloadedError(RuntimeError):
    """Raised when Anthropic returns 529 after all retries (spec §15)."""


@dataclass
class LLMCallResult:
    """Structured result of a single LLM call (voice or Alfred)."""
    text: str
    model: str
    voice_id: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    raw_response: Any = field(repr=False, default=None)


def _ensure_sdk():
    try:
        import anthropic  # noqa: F401
        return anthropic
    except ImportError as e:
        raise RuntimeError(
            "The `anthropic` Python SDK is not installed. "
            "Add it to requirements.txt and run `pip install anthropic`. "
            f"Original error: {e}"
        ) from e


def _track_cost(model: str, usage: Any) -> tuple[int, int, int, float]:
    """Extract token counts + cost. Tolerates the cache-token attribute being absent."""
    rates = RATES[model]
    inp = int(getattr(usage, "input_tokens", 0))
    out = int(getattr(usage, "output_tokens", 0))
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cost = inp * rates["input"] + out * rates["output"] + cache_read * rates["cache_read"]
    return inp, out, cache_read, round(cost, 6)


class AICLLMClient:
    """Anthropic client with model routing, prompt caching, and cost tracking.

    Construct once per session. The Anthropic client itself is thread-safe; we
    keep the wrapper synchronous to make the deliberation sequence easy to
    reason about (each voice runs to completion before the next starts).
    """

    def __init__(self) -> None:
        assert_required("anthropic")
        anthropic_sdk = _ensure_sdk()
        self._client = anthropic_sdk.Anthropic(
            api_key=get_credential("ANTHROPIC_API_KEY")
        )

    # ----------------------------------------------------------------- voice

    def voice_call(
        self,
        voice_id: str,
        candidate_brief: dict,
        prior_outputs: list[dict],
        session_state: dict,
        delib_summary: dict | None = None,
        literature_override: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> LLMCallResult:
        """Issue a single voice call (Deliberation or Risk & Structure Cell).

        Returns the full assistant text + structured cost. Parser for the
        anchor/assessment/vote/conviction fields lives in
        `committee.vote_parser` so this wrapper stays content-agnostic.
        """
        system_blocks = build_system_blocks(voice_id, literature_override)
        user_payload = self._build_user_payload(
            candidate_brief, prior_outputs, session_state, delib_summary
        )
        return self._call_with_retry(
            model=MODEL_VOICE,
            system_blocks=system_blocks,
            user_text=user_payload,
            voice_id=voice_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # ---------------------------------------------------------------- alfred

    def alfred_call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        """Issue an Alfred orchestrator call (Sonnet 4.6).

        Alfred's system prompt is provided externally so the orchestrator can
        inject the live Charter v1.8.2 markdown into the cacheable block.
        """
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        return self._call_with_retry(
            model=MODEL_ALFRED,
            system_blocks=system_blocks,
            user_text=user_message,
            voice_id="alfred",
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # ------------------------------------------------------- internals

    @staticmethod
    def _build_user_payload(
        candidate_brief: dict,
        prior_outputs: list[dict],
        session_state: dict,
        delib_summary: dict | None,
    ) -> str:
        parts = [
            "CANDIDATE BRIEF:",
            json.dumps(candidate_brief, indent=2, default=str),
            "",
            "PRIOR VOICE OUTPUTS (reference only -- do not anchor):",
            json.dumps(prior_outputs, indent=2, default=str) if prior_outputs else "(none)",
            "",
            "SESSION STATE:",
            json.dumps(session_state, indent=2, default=str),
        ]
        if delib_summary is not None:
            parts.extend([
                "",
                "DELIBERATION SUMMARY (Risk Cell context):",
                json.dumps(delib_summary, indent=2, default=str),
            ])
        parts.extend([
            "",
            "Provide your independent assessment per your mandate.",
        ])
        return "\n".join(parts)

    def _call_with_retry(
        self,
        model: str,
        system_blocks: list[dict],
        user_text: str,
        voice_id: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMCallResult:
        backoff = INITIAL_BACKOFF_SECONDS
        last_err: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user_text}],
                )
            except Exception as e:                          # noqa: BLE001
                last_err = e
                # Anthropic SDK surfaces 529 as either anthropic.APIStatusError(529)
                # or a generic transient. Retry on the obvious transients; raise others.
                msg = str(e).lower()
                if "529" in msg or "overloaded" in msg or "rate" in msg:
                    if attempt < MAX_RETRIES:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise APIOverloadedError(
                        f"Anthropic API overloaded after {MAX_RETRIES} attempts: {e}"
                    ) from e
                raise

            text_parts = [
                getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"
            ]
            text = "".join(text_parts)
            inp, out, cache_read, cost = _track_cost(model, response.usage)
            return LLMCallResult(
                text=text,
                model=model,
                voice_id=voice_id,
                input_tokens=inp,
                output_tokens=out,
                cache_read_tokens=cache_read,
                cost_usd=cost,
                raw_response=response,
            )
        # unreachable
        raise APIOverloadedError(f"Exhausted retries: {last_err}")
