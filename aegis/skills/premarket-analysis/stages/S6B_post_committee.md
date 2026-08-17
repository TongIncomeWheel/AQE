# PMA · POST-COMMITTEE PIPELINE — S6.5 → S7P (v4.2, PM-ratified rulings applied)
**Owner: Alfred (orchestrator — sequencing and completeness only, no market opinion).**
**This file is the persistent definition of everything that happens AFTER the S6 consensus closes and BEFORE the PM sees the daily PMA.**

## Consensus rule (corrected 2026-08-17, supersedes prior arithmetic)
ADVANCE requires ALL of: `support > oppose` · `support >= 2` · `median support conviction >= 3`.
Else `support >= 2` → HOLD-FOR-CONDITIONS. Else PASS.
Caps only ever LOWER conviction: steenbarger audit flag → cap 3 · support < 3 → cap 4 · non-ADVANCE → cap 3.
(The prior rule advanced names with more OPPOSE than SUPPORT; caught by the S7Q gate on the 2026-08-17 dry run.)

## Phase map (nomination → cap), named for plain reference
PHASE 1 SWARM · 8 nominators live (elder-lens, livermore, minervini, oneil, raschke, seow, thorp, wyckoff), blind,
  full 279-name universe, free nomination + conviction 1-5. Two more (weis, kratter) are grounded but
  SEATING-BLOCKED pending the detect-lens decomposition ruling — both already sit inside detect-lens
  (C19-C24 Weis, C1-C5 Kratter), so seating them un-decomposed makes one method vote twice into
  seat_count and manufactures 2-seat qualification. ceponas is NOT seated: Level 2/tape canon, zero
  servable premarket fields (ruled NOT_APPLICABLE 2026-08-09). Target once ruled: 10.
PHASE 2 TALLY · mechanical count per ticker: seat_count, conviction_sum. No judgment.
PHASE 3 QUALIFY · mechanical threshold: seat_count>=2 OR solo conviction>=4. No sector/fundamental term.
PHASE 4 CAP · qualifiers ranked and truncated to `deliberation_cap` (below). This is the ranking step —
  everything that reaches Phase 4 is logged to the rolling ledger (see below) whether or not it survives the cap.
PHASE 5a CHALLENGE · Rogers + Steenbarger activate ONLY on names that survive the Phase 4 cap.
PHASE 5b FUNDAMENTALS + LENS · Lynch + Detect-lens activate ONLY on names that survive the Phase 4 cap.
PHASE 6 ROUND 2/3 DELIBERATION · full obligation register, consensus rule, on the capped set only.
  10 seats vote today: 8 nominators + Lynch + Detect-lens. 12 once weis/kratter are ruled in.
  QUORUM NOTE: the standing quorum floor is 8. At 10 voting seats that floor is 80% of the room —
  a single absent seat leaves almost no margin. Re-derive the floor when the roster changes.

## SEAT INDEPENDENCE (new, 2026-08-17 — the reason weis/kratter are blocked)
The tally's entire epistemic claim is that seats are INDEPENDENT. `seat_count >= 2` means two
analysts converged. If two seats carry the SAME author's doctrine, a name they both flag records
2 seats while representing one method. That manufactures qualification, and it does so
preferentially on the setups that doctrine is best at — so the corruption concentrates in exactly
the names most likely to reach the cap. It is not random noise.
BEFORE SEATING ANY NEW VOICE: diff its canon against every seated canon. Overlapping source
material must be decomposed (one author, one seat) or the new seat must not be seated.
Open instance: detect-lens is a FOUR-BOOK composite (Kratter C1-C5, Ceponas C6-C11, Clenow
C12-C18, Weis C19-C24). Three of those four authors are queued as standalone seats.

## Phase 4 ranking key (corrected 2026-08-17 — was underspecified, caused an unresolved 3-way tie at cap=12)
Sort qualifiers descending on, in order:
  1. seat_count
  2. conviction_sum
  3. **SRM support** — the qualifier's GICS sector's `srm.entry_gate`, ranked PASS(3) > CAUTION(2) > WATCH(1) > BLOCKED(0)
  4. **Thematic support** — 1 if the ticker's `thematic_grade == DEPLOY` OR `thematic_rrg_quadrant` in {LEADING, IMPROVING}, else 0
  5. sc_momentum (final tiebreak; ticker alpha only if still tied, which the 2026-08-17 run's full 28-name
     qualifying set never required past step 4 — chain fully resolves in practice)
This closes the design gap flagged same day: at cap=12, TAK/NWS/LYV tied 2-seats/conviction-sum-6 with
no defined tiebreak. Re-run under this key: NWS and LYV rank above TAK on SRM support (Comm Svcs PASS
vs Healthcare CAUTION) — same outcome as the original run, now traceable rather than arbitrary.

## PHASE 4 · TICKER LEDGER (deterministic, 0 spawns, runs every session regardless of publish outcome)
Every session, log the full Phase-4 list (every ticker that reached ranking, cap survivors AND
cap-dropped alike — the point is repeat *interest*, not repeat *selection*) to a persistent, append-only
ledger: `data/pma/phase4_ledger.json`, one dated entry per session:
  `{ "date": "YYYY-MM-DD", "tickers": ["CNC","CVX", ...] }`
At render time, compute each ticker's count of appearances across the **trailing 5 sessions** (today
inclusive). **Any ticker appearing in Phase 4 on 2 or more of the trailing 5 sessions gets a REPEAT flag
— routed to the PM for a manual look**, regardless of whether it survived that session's cap or holds a
committee verdict at all. This is a persistence signal (the swarm keeps independently re-finding the
name), not a conviction signal — it stands alongside, never instead of, the committee's own verdict.
Ledger retention: keep 20 trading sessions rolling, prune older on write. First 4 sessions after this
rule goes live cannot produce a REPEAT flag (insufficient history) — expected, not a defect; state it
in the report footer until the window fills.

## S6.5 · SYNTHESIS (deterministic + Alfred, 0 spawns)
Compile per-name verdict records from round2/*.json: verdict, conviction + cap, stance split,
strongest opposing argument (verbatim, attributed), falsifier set, fundamental memo line, promotion
condition for every HOLD-FOR-CONDITIONS. No new judgment. No narration of who persuaded whom in the
PM output — the exchange record stays in the artifacts for audit, not in the report.

**HOLD-FOR-CONDITIONS condition line is now MANDATORY, not optional (corrected 2026-08-17 — several
cards on the first dry run shipped a HOLD verdict with no stated condition).** Source order:
  1. If a seat filed an explicit promotion condition in Round 2 (O5/O7 obligations), use it verbatim.
  2. Else Alfred synthesizes ONE observable, falsifiable condition from the strongest opposing case on
     record — an observable price/structure/flow threshold, never a vague "wait and see."
A HOLD-FOR-CONDITIONS card with no condition line is a Q2-family FAIL at S7Q — same severity as a
missing bear case on an ADVANCE. It does not ship.

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
  list    List (longlist/elder_list/qs/radar-runner sourcing) · Elder (score + pattern + 5d trace) ·
          SRM (sector grade/entry_gate) · Thematic (basket + grade/rrg, or "none")
  scores  conviction | detect (lens strong /6) | coil | momentum (sc_m + mp_state) |
          accumulation (flow + insti lens) | structure (0-100)
  levels  px · stop (structural | FB) · TP1/TP2 · R:R · ATR
  lines   Committee: (consensus recommendation, 1-2 sentences, executive) ·
          Risk: (strongest opposing case + fundamental flag) ·
          Condition: (MANDATORY on every HOLD-FOR-CONDITIONS — see S6.5) ·
          Repeat: (only if Phase-4 ledger count >= 2 of trailing 5 — "REPEAT Nx/5, PM manual look")
Language rule: consensus and recommendation only. No persuasion narration. Every number traceable
to a stage artifact; a number with no source is deleted, not patched.
NEAR MISSES = every name that qualified for deliberation but was cut by the cap, plus radar names
outside the daily list. Always printed, never silently dropped. Carries List/Elder/SRM/Thematic/Repeat
same as shortlist cards — near-miss status does not exempt a name from the same disclosure fields.

## S7Q · PERFORMANCE AUDIT (interim gate BEFORE publishing to PM — tools/s7q_gate)
Three families, all must PASS to publish:
  QUALITY       quorum >= 8 · coverage matrix complete · consensus rule correctly applied ·
                R1 (zero bracket-gate breaches) · R3 (QS absent from every seat packet;
                crown_agreement filed) · Phase-4 ranking key fully resolves (no undeclared ties) ·
                SEAT INDEPENDENCE (no two seated canons share a source author)
  COMPLETENESS  every card carries all 6 score elements + List/Elder/SRM/Thematic + levels +
                Committee/Risk/Condition lines · every HOLD-FOR-CONDITIONS carries a condition line ·
                every ADVANCE carries attributed opposing case + falsifier · near-miss list present ·
                staleness + DEGRADED flags in header
  COMPOSITION   report follows the 6-section contract · shortlist appears ONCE, as cards ·
                zero narration phrasing · action plan addressed to PM
FAIL → route to owning stage (render fails re-render; missing obligations re-open S6 close; seat
breach re-runs that seat). Max 2 loops. Whatever still fails is DECLARED in the footer — the PMA
never ships a silent defect, and never ships without this gate's PASS record attached.

## S7P · PUBLISH
data/pma/<date>/ (all stage artifacts, git, including phase4_ledger.json append) ·
aegis/reports/pma/<date>.md + latest.md · project doc · AND printed in full on screen for the PM.
Footer always: "DRAFT — PM approval required. Nothing is staged, nothing is armed."

## S8 · LEARNING LOOP
run_audit.json (stages present, seat health, asked-vs-served, traceability, gaps carried) +
nomination_ledger scoring d1/d3/d5/d10/d15 per voice → seat scorecards. Feeds the next morning's
memory injection (R1 AND R2 — R2 injection is an open build item, flagged until closed).

## PM parameters
deliberation_cap (**20**, raised 2026-08-17 from the original default of 12 — the 12-name cap systematically
starved thin-nomination/high-sector-weight sectors, e.g. Technology at 29% of the universe but only
2 qualifiers, both cut; at 20 both surface) ·
phase4_ledger_window (5 trading sessions, repeat threshold >=2) ·
max_quality_loops (2) · cards_soft_max (5 actionable; extras render with a note).