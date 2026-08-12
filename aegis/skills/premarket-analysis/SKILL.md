---
name: premarket-analysis
description: "PMA — the analysis-only morning kernel. Turns the day's AQE export + Nick Crown macro file into a CIO decision page via eight staged skills bridged by JSON files in the repo. Adversarial deliberation (bull/bear/judge) at its core. No brokers, no held book, no orders, no sizing — the FRAME. Trigger: /premarket-analysis."
---

# /premarket-analysis — the morning analysis kernel (v0.2, design 2026-08-12)

**What this is.** One command that runs the committee's *thinking*: pull the day's data into
the repo, frame the market, let every seat read it in isolation, challenge the consensus,
argue each idea adversarially, and hand the CIO one decision page. Every stage boundary is a
JSON file in git — that is the bridge, the audit trail, and the reason any morning's reasoning
can be reconstructed six weeks later.

**What this is NOT (v0.2 scope, PM directive).** No held-book work, no per-position management,
no broker pulls, no order staging, no dollar sizing. Those live in the existing `/premarket` +
gatekeeper machinery. PMA is analysis-only and runs standalone. Constitution law 1 untouched:
nothing here places, sizes, or arms anything.

---

## Source of record: the repo, not Drive

**PM ruling 2026-08-12 — nothing sits in Drive.** AQE writes there; Aegis does not read from
there. S1 is the only component permitted to touch Drive, and its single job is to land the
day's data in the repo at a fixed path:

```
data/aqe/<YYYY-MM-DD>/  aqe_daily_export.json.gz · aqe_crown_macro.json · manifest.json
data/aqe/latest.json    the only pointer anything follows
data/pma/<YYYY-MM-DD>/  every stage output for that run
```

Gzipping the export (~2.6 MB → ~250 KB) is what makes daily commits affordable: ~90 MB/yr in
tree, pruned to monthly archives after 90 days. Every stage after S1 reads the repo.

---

## The pipeline

```
S1 INGEST       Drive → repo, validate, staleness           → ingest_receipt.json
S2 MARKET FRAME what kind of day is this?                    → market_frame.json
S3 CANDIDATES   what is on the table?                        → candidate_set.json
S4 VOICE SWARM  11 isolated seats, inline JSON packets       → voices/*.json + tally.json
S5 CHALLENGE    rogers challenges the tally                  → challenge.json
   + WEATHER    crown NOW (verbatim) · druckenmiller NEXT    → weather.json
S6 DELIBERATION bull → bear → judge, per name; then CIO      → committee_read.json + cio_synthesis.json
S7 CIO OUTPUT   the decision page, fixed order               → premarket_plan.json + plan.md
S8 SELF-AUDIT   asked-vs-served, traceability, gaps          → run_audit.json
```

Stage cards: `stages/S1_ingest.md` … `stages/S8_audit.md`. Contracts: `contracts/pma/`.
Each stage reads only prior stages' JSON — no stage reaches around the bridge, because the
bridge is what makes the run inspectable.

**S6 is the committee.** S1–S3 are plumbing, S7–S8 are formatting. The design weight sits in
S4 (manufacturing independence) and S6 (adversarial argument). Read those two cards first.

---

## Control plane vs judgment plane (D-16)

The orchestrator running this card is **control**: sequence, validate, move on. It forms no
market opinion. Judgment happens ONLY inside spawned agents — the 11 voices (S4), rogers +
druckenmiller (S5), and bull/bear/judge/CIO (S6). S1, S2, S3, S7, S8 are deterministic: same
inputs, same outputs, no model in the path.

## Isolation

Each S4 seat is a fresh agent: its own card, its own inline packet, its own ledger memory. No
seat sees another seat, the tally, or any ordering hint (candidate rows are shuffled per seat).
Weather and challenge run strictly after the tally so they cannot steer what they react to.

**Packets are inlined, never passed as paths.** Compiled voice agents are toolless; handed a
path, they fabricate rather than fail (finding F1, 2026-08-11 — four seats invented file
listings and market values in test). This is a correctness rule, not a preference.

## Failure ladder — every failure is declared, never silent

- **Export missing / invalid / tripwired** → STOP. No plan.
- **Crown missing** → run continues AQE-only; the headline says so.
- **Anything DEGRADED** → propagates verbatim into the plan headline. Data quality is read
  before ideas.
- **A seat returns nothing/invalid** → one re-spawn; still bad → empty seat in
  `tally.json.shortfalls`, run continues at ≥8 seats, S8 flags it.
- **Deliberation fails** → no ADVANCE; watch-table-only plan with the failure in the headline.
- **Drive unreachable** → fall back to the newest date already in the repo, mark staleness.

## Reuse, not clone

`tools/tripwires.py` · `tools/voice_memory.py render` · `tools/nomination_ledger.py record` ·
`contracts/nomination.schema.json` (the voice bridge, unchanged) · `contracts/aqe_export.schema.json`.
New contracts are pma-scoped under `contracts/pma/`.

## The learning loop

S8 writes a run audit daily: what each seat asked for vs what the feed served, which seats
shortfell, whether every plan anchor resolves to real data. Accumulated audits turn "what does
the committee need from AQE?" into a measurement rather than a workshop — feeding the
requirements register and the AQE change request directly.

## Open design decisions

Framed with recommended answers in plain English in
`aegis/design/pma_design_decisions_2026-08-11.md`. Nothing here overrides a PM ruling.
