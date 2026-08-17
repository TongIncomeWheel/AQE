# PMA · POST-COMMITTEE PIPELINE — S6.5 → S7P (v4.1, PM-ratified rulings applied)
**Owner: Alfred (orchestrator — sequencing and completeness only, no market opinion).**
**This file is the persistent definition of everything that happens AFTER the S6 consensus closes and BEFORE the PM sees the daily PMA.**

## Consensus rule (corrected 2026-08-17, supersedes prior arithmetic)
ADVANCE requires ALL of: `support > oppose` · `support >= 2` · `median support conviction >= 3`.
Else `support >= 2` → HOLD-FOR-CONDITIONS. Else PASS.
Caps only ever LOWER conviction: steenbarger audit flag → cap 3 · support < 3 → cap 4 · non-ADVANCE → cap 3.
(The prior rule advanced names with more OPPOSE than SUPPORT; caught by the S7Q gate on the 2026-08-17 dry run.)

## S6.5 · SYNTHESIS (deterministic + Alfred, 0 spawns)
Compile per-name verdict records from round2/*.json: verdict, conviction + cap, stance split,
strongest opposing argument (verbatim, attributed), falsifier set, fundamental memo line, promotion
condition for every HOLD-FOR-CONDITIONS. No new judgment. No narration of who persuaded whom in the
PM output — the exchange record stays in the artifacts for audit, not in the report.

## S6.6 · AUTO-BRACKET (R8 — PM ruling 2026-08-17)
**Every name at phase 3 or beyond (the deliberation set) automatically activates the /bracket read
from AQE data.** Deterministic, 0 spawns, never a gate:
- bracket.valid=true  → structural stop + stop_type + TP ladder + R:R, verbatim from the export.
- bracket.valid=false → atr_fallback_stop, LABELLED "FB", + nearest overhead targets/MA levels present in the row.
- All levels carry their price basis (prior close). Live refresh remains the PM's /bracket call at the open.
Levels are information on the card. They filter nothing, rank nothing, veto nothing (R1).

## S7 · RENDER (deterministic, 0 spawns) — fixed report contract
Six sections, this order: 1 Macro position + highlights · 2 Sector & thematics · 3 Held book review ·
4 Shortlist as TICKER CARDS · 5 Near misses (PM manual look) · 6 Action plan / next steps.
CARD contract (every card, every element, no omissions):
  header  ticker · verdict · conviction(+cap reason) · vote S-O-A · sector
  scores  conviction | detect (lens strong /6) | coil | momentum (sc_m + mp_state) |
          accumulation (flow + insti lens) | structure (0-100)
  levels  px · stop (structural | FB) · TP1/TP2 · R:R · ATR
  lines   Committee: (consensus recommendation, 1-2 sentences, executive) ·
          Risk: (strongest opposing case + fundamental flag) ·
          Condition/Invalidation: (observable)
Language rule: consensus and recommendation only. No persuasion narration. Every number traceable
to a stage artifact; a number with no source is deleted, not patched.
NEAR MISSES = every name that qualified for deliberation but was cut by the cap, plus radar names
outside the daily list. Always printed, never silently dropped.

## S7Q · PERFORMANCE AUDIT (interim gate BEFORE publishing to PM — tools/s7q_gate)
Three families, all must PASS to publish:
  QUALITY       quorum >= 8 · coverage matrix complete · consensus rule correctly applied ·
                R1 (zero bracket-gate breaches) · R3 (QS absent from every seat packet;
                crown_agreement filed)
  COMPLETENESS  every card carries all 6 score elements + levels + Committee/Risk/Condition lines ·
                every ADVANCE carries attributed opposing case + falsifier · near-miss list present ·
                staleness + DEGRADED flags in header
  COMPOSITION   report follows the 6-section contract · shortlist appears ONCE, as cards ·
                zero narration phrasing · action plan addressed to PM
FAIL → route to owning stage (render fails re-render; missing obligations re-open S6 close; seat
breach re-runs that seat). Max 2 loops. Whatever still fails is DECLARED in the footer — the PMA
never ships a silent defect, and never ships without this gate's PASS record attached.

## S7P · PUBLISH
data/pma/<date>/ (all stage artifacts, git) · aegis/reports/pma/<date>.md + latest.md ·
project doc · AND printed in full on screen for the PM. Footer always:
"DRAFT — PM approval required. Nothing is staged, nothing is armed."

## S8 · LEARNING LOOP
run_audit.json (stages present, seat health, asked-vs-served, traceability, gaps carried) +
nomination_ledger scoring d1/d3/d5/d10/d15 per voice → seat scorecards. Feeds the next morning's
memory injection (R1 AND R2 — R2 injection is an open build item, flagged until closed).

## PM parameters
deliberation_cap (default 12 — 2026-08-17 run dropped 16 qualifiers incl two 6/6-lens names; PM may raise) ·
max_quality_loops (2) · cards_soft_max (5 actionable; extras render with a note).
