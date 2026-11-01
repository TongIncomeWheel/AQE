# S8 — SELF-AUDIT (deterministic; the learning loop)

**Job.** Measure the run against itself so the kernel improves from evidence, not vibes.
Runs last, writes `data/pma/DATE/run_audit.json` (contract: `contracts/pma/run_audit.schema.json`).

**Records:**
- `data_demand`: per voice — fields its nomination actually cited vs fields its menu offers
  vs fields the feed served. Every `NOT_SERVED` a voice declared, verbatim.
- `seat_health`: seats that shortfell, re-spawned, or returned invalid JSON; time per stage.
- `bridge_integrity`: every stage output that failed schema validation (should be zero).
- `plan_traceability`: spot-check — does every ADVANCE line's anchors resolve to real values
  in the day's inputs? (The anti-hallucination tripwire on the committee itself.)
- `gaps_carried`: what the plan explicitly could not say today, and which missing data caused it.

**Why it matters.** Accumulated `run_audit.json` files are the EMPIRICAL feed for the
Voice-Data-Requirements register and the AQE change request (bridge plan Phases 1–3): after a
week of runs, "what data does the committee actually need?" is a measurement, not a workshop.
This is the self-learning loop the PM asked for — the kernel audits its own blind spots daily.

**Post-market extension (backlog, not v0.1):** score the day's plan against realized prices
via the existing `nomination_ledger.py track` checkpoints (d1/d3/d5/d10/d15) — RECORD every
round, SCORE at EOD, per the established two-cadence design.
