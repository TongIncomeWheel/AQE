---
name: premarket-analysis
description: "PMA — the analysis-only morning kernel. Turns the day's AQE export + Nick Crown macro file into an actionable, PM-reviewable trading plan via eight staged skills bridged by JSON files. No brokers, no held book, no orders, no position sizing — the FRAME. Trigger: /premarket-analysis."
---

# /premarket-analysis — the morning analysis kernel (v0.1, design milestone 2026-08-11)

**What this is.** One command that runs the committee's *thinking* for the day: ingest the
data AQE already calculated, frame the market, let every voice read it in isolation, challenge
the consensus, deliberate, and hand the PM one actionable plan. Everything between stages
travels as a JSON file — that is the bridge, and it is also the audit trail.

**What this is NOT (v0.1 scope, PM directive 2026-08-11).** No held-book work, no per-position
management, no broker pulls, no order staging, no dollar sizing. Those live in the existing
`/premarket` + `/committee-pm` + gatekeeper machinery. This kernel is analysis-only and can
run standalone. Constitution law 1 is untouched: nothing here places, sizes, or arms anything.

**Output.** `data/pma/DATE/premarket_plan.json` + a phone-readable `plan.md`. The plan is a
DRAFT until the PM says otherwise. Silence never trades.

---

## The pipeline — 8 stages, JSON in / JSON out

```
S1 INGEST            Drive → aqe_daily_export.json + aqe_crown_macro.json   → ingest_receipt.json
S2 MARKET FRAME      what kind of day is this? (deterministic distill)      → market_frame.json
S3 CANDIDATE FRAME   what is on the table today? (deterministic distill)    → candidate_set.json
S4 VOICE SWARM       10 isolated voices read S2+S3 via JSON packets         → voices/<voice>.json + tally.json
S5 CHALLENGE+WEATHER rogers challenges the tally; crown NOW + druck NEXT    → challenge.json + weather.json
S6 DELIBERATION      one isolated committee-desk pass → verdicts            → committee_read.json
S7 PLAN ASSEMBLY     deterministic render → the PM's one page               → premarket_plan.json + plan.md
S8 SELF-AUDIT        what was asked vs served; gaps; voice health           → run_audit.json
```

Stage cards live in `stages/S1_ingest.md` … `stages/S8_audit.md`. Contracts in
`contracts/pma/`. Each stage reads ONLY the JSON of prior stages — no stage reaches around
the bridge, because the bridge is what makes the run inspectable afterwards.

**Control vs judgment (D-16).** The orchestrator running this card is control plane:
sequence, validate, move on. Judgment happens ONLY inside spawned agents: the ten voices
(S4), the challenge seat (S5), the committee desk (S6). S1/S2/S3/S7/S8 are deterministic —
same inputs, same outputs, no model opinion.

**Isolation (anti-anchoring).** Each S4 voice is a FRESH agent: its own methodology card +
its JSON packet + its ledger memory. No voice sees another voice, the tally, or any hint of
ordering. Crown/Druckenmiller/Rogers run AFTER the tally by design — weather and challenge
inform, they never gate (D-4, D-97).

## Failure ladder (every failure is declared, never silent)

- **S1 fails (file missing / stale / schema-invalid):** STOP. No plan. Emit `ingest_receipt.json`
  with the exact failure. A missing input is refused, not zeroed (Crown C30).
- **Crown file missing but export fine:** run WITHOUT the macro layer; plan headline carries
  "Crown macro absent — regime read is AQE-only" (precedent: 2026-07-21 "bellwether letters
  not supplied — context absent, declared").
- **A voice returns nothing/invalid:** re-spawn once; still bad → empty seat recorded in
  `tally.json.shortfalls`, run continues at ≥8 seats, S8 flags it.
- **Deliberation fails:** no ADVANCE possible; plan ships watch-table-only with the failure
  in the headline.
- **Anything DEGRADED upstream (`status: DEGRADED` in the crown file, tripwire warnings in
  the export):** propagates into the plan headline. The PM sees data quality before ideas.

## Reuse, not clone

Existing machinery this kernel calls rather than re-implements: `tools/tripwires.py` (S1),
`tools/voice_memory.py render` (S4 packets), `tools/nomination_ledger.py record` (S4 tally →
ledger), `contracts/nomination.schema.json` (the voice bridge contract, unchanged),
`contracts/aqe_export.schema.json` (S1 validation). New contracts are pma-scoped and live in
`contracts/pma/`.

## The self-learning loop (S8 is not decoration)

Every run's `run_audit.json` records which fields each voice ASKED for vs what the feed
SERVED, which seats shortfell, and what the plan could not say because data was missing.
Accumulated audits are the empirical input to the Voice-Data-Requirements register and the
AQE change-request (bridge plan, Phases 1–3) — the kernel measures its own gaps daily instead
of waiting for a one-off study.

## Open design decisions

All framed with recommended answers in plain English in
`aegis/design/pma_design_decisions_2026-08-11.md`. Nothing in this card overrides a PM ruling.
