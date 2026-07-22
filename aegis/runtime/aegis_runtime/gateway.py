"""
gateway.py — the model gateway (Phase 1).

One interface the whole runtime calls; model choice is CONFIG, not code. Routes each
tier (voices / committee / control) to a model via LiteLLM, so the runtime can call
Claude today and swap to Kimi / a local model tomorrow by editing config only.

MOCK MODE (AEGIS_MOCK=1): returns canned structured responses WITHOUT any API call, so
the entire pipeline runs offline for free — prove the plumbing before spending a cent.
"""
import os
import json


class ModelGateway:
    def __init__(self):
        self.mock = os.environ.get("AEGIS_MOCK", "0") == "1"
        # per-tier model ids (overridable by env; defaults are sensible Claude tiers)
        self.models = {
            "voices": os.environ.get("AEGIS_MODEL_VOICES", "claude-sonnet"),
            "committee": os.environ.get("AEGIS_MODEL_COMMITTEE", "claude-opus"),
            "control": os.environ.get("AEGIS_MODEL_CONTROL", "claude-haiku"),
        }

    def complete(self, tier, system, user, max_tokens=2000, mock_response=None):
        """Return the model's text output for (system,user) at the given tier.
        In mock mode returns `mock_response` (already-shaped text) with no API call."""
        if self.mock:
            return mock_response if mock_response is not None else "{}"
        # --- real path: LiteLLM routes `model` to the provider configured in litellm_config.yaml ---
        from litellm import completion  # imported lazily so mock mode needs no dependency
        resp = completion(
            model=self.models.get(tier, self.models["control"]),
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"]

    @staticmethod
    def extract_json(text):
        """Pull the first JSON object out of a model reply (handles ```json fences)."""
        t = text.strip()
        if "```" in t:
            # take the content of the first fenced block
            parts = t.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{"):
                    t = p
                    break
        start, depth = t.find("{"), 0
        if start < 0:
            raise ValueError("no JSON object in model reply")
        for i in range(start, len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(t[start:i + 1])
        raise ValueError("unbalanced JSON in model reply")
