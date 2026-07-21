# Aegis Runtime — Phase 0-1 (one-click)

This is the self-hosted "brain" for Aegis. It runs the premarket — the 11 voices, the
conviction funnel, the committee — on your own box using the Claude API. Phase 0-1 is
**headless** (no Discord, no live brokers, no scheduling yet) and is here to prove the
intelligence works and to measure the real cost, cheaply.

**You do not need to know Python or Linux.** Everything runs inside Docker with one command.

---

## Run it in 3 steps (offline, free — proves it works)

On any machine (your laptop, or the VPS) that has **Docker** installed:

```
cd runtime
cp .env.example .env
docker compose up
```

That's it. It builds once, then runs a **full premarket in mock mode** — no API key, no
cost — and prints the result: 11 voices ran, the funnel shortlist, the committee verdicts.
The artifacts (the plan pieces) appear in `runtime/out/2026-07-21/`.

This is your proof the whole pipeline is wired correctly before you spend a cent.

---

## Switch to real (uses the Claude API, costs a few cents)

1. Open `.env` and set:
   - `AEGIS_MOCK=0`
   - `ANTHROPIC_API_KEY=` your key (from the Anthropic Console)
   - the three `AEGIS_MODEL_*` lines to the current model IDs (from Anthropic's docs)
2. Run one real premarket:
   ```
   docker compose run --rm runtime premarket --date 2026-07-21
   ```
3. Check your Anthropic Console usage to see the exact token cost of one run.

---

## What just ran (the two-layer orchestrator)

- **The sequencer (code):** universe → 11 voices (isolated, parallel) → tally → the
  conviction funnel (the real kernel tool: DATA leads, LENS seconds, VOICES corroborate or
  challenge, D-80) → committee → summary.
- **The Chief (a model):** try `docker compose run --rm runtime chief "run premarket for
  2026-07-21"` — the Chief interprets your instruction and dispatches. In Phase 1 it only
  knows `premarket`, but it's the piece that later turns free-form commentary into action.

## What's deliberately NOT here yet
Discord (Phase 4), live FMP/Tiger/IBKR data (Phase 3), scheduling (Phase 2), orders
(Phase 5). Phase 0-1 proves the brain + cost first. See `../handoff/07_PHASE01_CHECKLIST.md`
for the full plan and `../handoff/06_RUNTIME_BUILD.md` for the whole build.

## For the engineer
Code is in `aegis_runtime/`: `gateway.py` (LiteLLM + mock), `voices.py` (11 parallel,
schema-validated), `committee.py`, `orchestrator.py` (two layers), `cli.py`. It reads the
kernel from `/app` (voice cards from `dist/.../agents` or `skills/`, contracts from
`contracts/`, the funnel from `tools/conviction_funnel.py`, the sample SOD shelf from
`data/sod/DATE/`). Swap models in `.env`; add OpenAI/Kimi keys to route tiers elsewhere.
