---
name: design_review
description: Aegis process skill — DESIGN & REVIEW (after post-market; autonomous; asks land in the 10:00 summary). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: DESIGN & REVIEW (after post-market; autonomous; asks land in the 10:00 summary)
**Desk (D-26/D-32):** the Chief adopts **Engineering & Change** throughout. The five bench lenses (technical · indicator · data · process · governance-chair) run INLINE as a review skill (D-27) — a seat is spawned as its own agent only for a deep/contested finding, never by default. Physical move to `orchestration/` = BL-033.
1. **Assurance report.** Process compliance, skill usage, completeness of voices vs tickers analysed (from post-market audit).
2. **Performance measurement.** Today's actual runners vs what AQE surfaced and what the committee nominated — did the system SEE the winners? (Ledger + AQE export comparison, `tools/nomination_ledger.py report`.)
3. **Learning pass.** RB:retention.learning_lookback_days window: winners' fingerprints vs our nominations; misses classified (not in universe / in universe not nominated / nominated not deliberated / deliberated not advanced / advanced not actioned) — each class has a different fix.
4. **Bench triage (D-14).** Every finding routes to its owning seat: signal/field claims → indicator design (measured on the panel BEFORE anything advances) · shape/lineage → data design · architecture/blast-radius → technical design · runbook/phase/exception → process engineering. Each seat returns its block (SPEC / MEASURED / DATA-IMPACT / PROCESS). Governance (chair) routes the result: parameter tweak vs change item vs law path — and enforces the retirement.
5. **Proposal measurement.** Any field-conditional idea is measured on the enriched panel BEFORE it can advance to a change item (`tools/measure_proposal.py` — the BULLISH_BOS lesson, permanent). Runs here so nothing enters the backlog unmeasured.
6. **Backlog.** Measured/routed items enter the DEVELOPMENT pipeline (capture → PM approve → branch → shadow → ship → re-measure at 15 sessions). Each pipeline stage has a bench-lens owner: spec = owning lens · shadow review = owning lens · ship packaging = governance.
7. **PM STEER FILE (governance chair assembles — contracts/steer.schema.json).** One screen, four sections: FYI (no action) · DECIDE (your one-tap items with options + recommendation + days-pending — unanswered items re-surface EVERY day, never dropped) · PRE-FIX (what will change, when, what it retires, shadow planned) · POST-FIX (what changed, shadow result, re-measure date). Lands in the 10am summary; /steer any time.
