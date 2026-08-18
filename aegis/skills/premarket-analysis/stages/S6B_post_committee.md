# PMA · POST-COMMITTEE PIPELINE — S6.5 → S7P (v4.3, PM-ratified rulings applied)
**Owner: Alfred (orchestrator — sequencing and completeness only, no market opinion).**
**This file is the persistent definition of everything that happens AFTER the S6 consensus closes and BEFORE the PM sees the daily PMA.**

## Consensus rule (corrected 2026-08-17, supersedes prior arithmetic)
ADVANCE requires ALL of: `support > oppose` · `support >= 2` · `median support conviction >= 3`.
Else `support >= 2` → HOLD-FOR-CONDITIONS. Else PASS.
Caps only ever LOWER conviction: steenbarger audit flag → cap 3 · support < 3 → cap 4 · non-ADVANCE → cap 3.
(The prior rule advanced names with more OPPOSE than SUPPORT; caught by the S7Q gate on the 2026-08-17 dry run.)

## Phase map (nomination → cap), named for plain reference
PHASE 1 SWARM · 9 nominators (elder-lens, livermore, minervini, oneil, raschke, seow, thorp, wyckoff,
  weis), blind, full universe LESS names held out for zero technical coverage (see NO-BLANK-DATA
  below — 7 held out on the 2026-08-17 export, 272/279 served), free nomination + conviction 1-5.
  kratter and ceponas join once their books are ingested (target 11).
PHASE 2 TALLY · mechanical count per ticker: seat_count, conviction_sum. No judgment.
PHASE 3 QUALIFY · mechanical threshold: seat_count>=2 OR solo conviction>=4. No sector/fundamental term.
PHASE 4 CAP · qualifiers ranked and truncated to `deliberation_cap` (below). This is the ranking step —
  everything that reaches Phase 4 is logged to the rolling ledger (see below) whether or not it survives the cap.
PHASE 5a CHALLENGE · Rogers + Steenbarger activate ONLY on names that survive the Phase 4 cap.
PHASE 5b FUNDAMENTALS + LENS · Lynch + Detect-lens activate ONLY on names that survive the Phase 4 cap.
PHASE 6 ROUND 2/3 DELIBERATION · full obligation register, consensus rule, on the capped set only.
  11 seats vote: 9 nominators + Lynch + Detect-lens.
  QUORUM NOTE: the standing floor is 8, leaving 3 seats of margin at 11. Re-derive on roster change.

## SEAT INDEPENDENCE (standing check, 2026-08-17 — no open instance)
The tally's epistemic claim is that seats are INDEPENDENT. `seat_count >= 2` means two analysts
converged. If two seats carried the SAME author's doctrine, a name they both flag would record
2 seats while representing one method — manufacturing qualification, concentrated on the setups
that doctrine is best at rather than spread randomly.
BEFORE SEATING ANY NEW VOICE: diff its canon sources against every seated canon's sources.
CHECK AGAINST `canon.lock.yaml` FILES ONLY — the signed, deployed artifacts — never against
project prose, which may describe superseded designs.

### Correction note (2026-08-17) — a wrong finding, recorded rather than deleted
A blocking collision was asserted between `weis` and `detect-lens` based on the project doc
`canon_detect_lens_24_principles_2026-08-10.md`, which described detect-lens as a four-book
composite carrying Weis as C19-C24. That document was a PROPOSAL — it states on its own face
"PENDING YOUR SIGN-OFF. Nothing here is locked" — and was never deployed. The DEPLOYED lock,
`aegis/canon/detect-lens/canon.lock.yaml` (pm_signed: Ash), was rebuilt CODE-FIRST on 2026-08-11:
its sources are `src/engines/*.py` + the AQE field dictionary, 33 principles, cited by file+line.
It reads NO BOOKS — "the only non-human seat -- its canon is running code, not a book."
There is no overlap. The PM's ruling that weis and detect-lens are complementary stands: detect-lens
reports what the engine computed; weis interprets what the tape did.

## NO-BLANK-DATA (standing rule, 2026-08-17 — PM: "there should be no blank data, all fields
should be available and used") — closed against the live export, no open instance
Two failure modes were live before this fix, found by a full per-ticker (not per-column) null
audit of every seated voice's menu against the real daily export:
1. **Buried, not blank.** `bracket.valid==false` on 233/279 rows (84% of the universe) — the
   correct engine behaviour, not a fault, since most names don't clear all three structural
   bracket gates (atr>=1.0, rr>=2.0, risk% <= regime ceiling). The engine's own fallback
   (`bracket.atr_fallback_stop` + `bracket.invalid_reason`) already existed for exactly this case,
   but only `oneil`/`thorp`/`weis` had it as a named column. Every other bracket-reading seat either
   read the bare `bracket` object (the fallback was technically present but unlabelled inside a JSON
   blob — present in the data, not "used" in any meaningful sense) or, in `seow`'s case, had no
   fallback path at all — genuinely blind on stop/risk data for 84% of names.
   FIX: bare `bracket` retired everywhere; every bracket-reading seat now carries explicit
   `bracket.valid` / `bracket.stop` / `bracket.stop_type` / `bracket.risk_pct` /
   `bracket.atr_fallback_stop` / `bracket.invalid_reason` columns. `elder-lens` and `druckenmiller`
   carry NO bracket fields — by design, not gap: neither voice makes an entry/stop/risk call
   (elder-lens is Elder Ray oscillator/pulse pattern-reading only; druckenmiller is macro/sector/
   theme only), so a bracket column would sit unused, which the rule forbids in the other direction.
2. **Blank cells reading as ambiguous.** TSV writer rendered `None` as an empty cell — indistinguishable
   from a genuinely empty string or a parsing artifact. FIX: every null now serializes as the literal
   token `null` in every TSV cell, no exceptions.

Two further per-ticker gaps, found the same audit pass, are NOT column-level (missing_menu_fields
below stays empty either way — every field resolves on SOME row) and needed a different treatment:
- **NO_TECHNICAL_COVERAGE** — 7 tickers on the 2026-08-17 export (AUB, ELS, EQR, FITB, KSS, NNN,
  OKTA; all `source=="qs"`), null on every one of `sc_momentum/flow/energy/structure/mp/elder/entry`
  — this matches the export's own `data_quality.flagged` block exactly. Nothing exists for any voice
  to honestly assess, so `pma_pipeline.py packets` now holds these out of every nominator TSV
  entirely (never serves a wall of `null`) and writes them to `no_technical_coverage.json`. They
  remain in `candidate_set.json` and can still carry a QS card line at S7 (PM request, render-only).
- **PATTERN_FIELD_GAP** — 14 tickers on the 2026-08-17 export (ABNB, P, TPG, TEVA, NESR, BETA, PYPL,
  BILL, WPM, APO, DLR, SSRM, NBIS, LITE; all `source=="longlist"`, core fields real and present) null
  on every one of `pin_bar_state/inside_bar/choch_state/div_state/knn_prob/squeeze_breakout_state/
  was_squeezed`. This is NOT caught by the export's own `data_quality` self-check — an undeclared
  upstream gap in the pattern-detection engine, not a "no signal" state. NOT excluded (these names
  have real technical data on everything else); `pma_pipeline.py packets` prints a loud
  `pattern_field_gap` WARNING every run instead so it can't quietly undercount. This is a
  data-engineering-owned gap, not something the pipeline can manufacture — reported, not patched.

**Ruled legitimate, no fix applied (do not re-flag as a bug):** `elder_pattern` null on 44% of rows
(categorical "no pattern currently detected", a real state) · `thematic_basket`/`thematic_grade`
null on 69% (ticker isn't in any tracked thematic basket, a real state) · `ma_200` null on exactly 4
tickers where `ma_50`/`ma_100` are both populated (insufficient trading history for a 200-day
average — young listings, a structural null).

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

## PHASE 4 · TICKER LEDGER (new — deterministic, 0 spawns, runs every session regardless of publish outcome)
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

**Downstream consumer (added 2026-08-18, closes the "reconstruct by hand" gap on §4 of the report).**
`phase4_ledger.json` is the INPUT that drives `data/pma/verdict_ledger.json` and the REPEAT WATCH
table — see S6.7 below. The ledger itself does not change: it still logs every Phase-4 name, cap
survivors and cap-dropped alike, deterministically, every session. What changed is that a cap-dropped
name is no longer a dead end for accountability — `pma_pipeline.py record-verdicts` now reads the
same session's rank/deliberation output and writes a `NEAR-MISS` row to `verdict_ledger.json` for
every ticker Phase 4 dropped before a vote, so a REPEAT-flagged ticker's full history (verdict AND
price, every appearance) is always mechanically recoverable — no PM memory or hand transcription
required.

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

## S6.7 · LOCK VERDICTS + REPEAT WATCH (tool, mandatory — PM standing rule, 2026-08-18:
"I want it automated, not by hand, which means gaps and forget will occur.")
**Deterministic, 0 spawns. Runs every session, after S6.6, before S7 render — never optional, never
deferred to "reconstruct by hand if the data's missing."**
1. `pma_pipeline.py record-verdicts --date <date> --consensus <consensus.json> --phase4 <rank/deliberation
   output>` — writes one WRITE-ONCE row per `(date, ticker)` to `data/pma/verdict_ledger.json`:
   - every consensus-closed name (ADVANCE / HOLD-FOR-CONDITIONS / PASS) with its verdict, conviction,
     support/oppose/abstain split, reference price + price source, bracket, and `record_source: "live"`.
   - every Phase-4 `dropped` (cap-cut) name gets a `NEAR-MISS` row — verdict `NEAR-MISS`, no vote split
     (never voted), reference price from the universe row's entry/bracket, `record_source: "live"`,
     `event_based.status: "not_applicable"` (cut before any argument, nothing to event-grade).
   - a row already present for that `(date, ticker)` is never overwritten — the ledger is append-only,
     one truth per day per name.
   - the one-time historical exception (2026-08-17 rows, written by hand on 2026-08-18 before this tool
     existed) is tagged `record_source: "backfilled_manual_2026-08-18"` — declared, not hidden, and the
     ONLY rows in the ledger not produced by this step. No future session repeats that exception; if a
     gap is ever found, it is logged as a gap in the tool's own output (see next), never silently
     re-typed.
2. `pma_pipeline.py repeat-watch --date <date>` — reads `phase4_ledger.json`'s `repeat_flags` +
   `verdict_ledger.json`, and for every REPEAT-flagged ticker walks its full appearance history,
   computing `% vs last COB` from each pair of consecutive `ref_price` values and pulling `state`
   straight from the matching verdict row. Writes `data/pma/<date>/repeat_watch.json`:
   `{ "as_of": <date>, "rows": [{ticker, date, pct_vs_last_close, state, gap}], "markdown": "<table>" }`.
   If a `(date, ticker)` the ledger flags has no matching verdict_ledger row, the row's `gap` field
   states why (e.g. "no verdict_ledger row -- record-verdicts was not run, or predates the ledger") —
   the tool NEVER invents a number or silently drops the row.
3. §4 of the rendered report (REPEAT WATCH) is the `markdown` field of `repeat_watch.json`, pasted
   verbatim — never hand-typed, never re-derived by Alfred. S7Q's Q6r family (below) fails the gate
   if §4 doesn't match the tool's own output.

## S7 · RENDER (deterministic, 0 spawns) — fixed report contract
Eight sections, this order: 1 Regime (three reads) · 2 Sector & thematic alignment · 3 Held book review ·
4 REPEAT WATCH (S6.7 tool output, verbatim — visibility only, not fed to the R2 committee vote, PM
ruling 2026-08-18) · 5 QS LIST (full ticker-level regime-model shortlist, PM-only, render-only) ·
6 Shortlist as TICKER CARDS · 7 Near misses (PM manual look) · 8 Action plan / next steps.
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
          Repeat: (only if Phase-4 ledger count >= 2 of trailing 5 — "REPEAT Nx/5, PM manual look") ·
          QS: (MANDATORY on every card, shortlist and near-miss alike — see below)

**QS line (new, 2026-08-17, PM request).** Every card carries the PM's own QS regime read for that
ticker, sourced verbatim from `candidate_set.json`'s per-ticker `qs` block — RENDER-ONLY, added
after S6.5 consensus closes, regardless of whether the name was ever nominated, deliberated, or
carries a verdict at all. Format: `QS: <signal> · conv <conviction_word>(<conviction>) · edge
<odds.edge as %> · target +<objective.target_pct>% (2xATR) / give-up <path.typical_dip_pct>%`. If
`qs.signal == "NONE"` and `qs.eligible == false`, still print the line — do not suppress it; that
absence of a QS read is itself information. This does NOT relax R3: QS never entered any seat
packet at any stage before this point — `pma_pipeline.py packets` hard-fails the build if any
voice menu names `qs`/`on_qs`, checked before a single TSV is written. R3 governs seat INPUT only;
this is PM-facing OUTPUT, after deliberation, and the two are not in tension.
Note: `qs`/`on_qs` are live in the daily export but undocumented in
`aegis/contracts/aqe_export.schema.json` / `universe.schema.json` — schema drift, not a blocker,
worth closing when convenient.

Language rule: consensus and recommendation only. No persuasion narration. Every number traceable
to a stage artifact; a number with no source is deleted, not patched.
NEAR MISSES = every name that qualified for deliberation but was cut by the cap, plus radar names
outside the daily list. Always printed, never silently dropped. Carries List/Elder/SRM/Thematic/Repeat/QS
same as shortlist cards — near-miss status does not exempt a name from the same disclosure fields.

## S7Q · PERFORMANCE AUDIT (interim gate BEFORE publishing to PM — tools/s7q_gate)
Four families, all must PASS to publish:
  QUALITY       quorum >= 8 · coverage matrix complete · consensus rule correctly applied ·
                R1 (zero bracket-gate breaches) · R3 (QS absent from every seat packet;
                crown_agreement filed) · Phase-4 ranking key fully resolves (no undeclared ties) ·
                SEAT INDEPENDENCE (no two canon.lock.yaml files share a source) ·
                FIELD SERVICE (packets receipt missing_menu_fields is empty, else DEGRADED declared;
                no_technical_coverage exclusions and pattern_field_gap flags both DECLARED in the
                header verbatim, never silently absorbed — see NO-BLANK-DATA)
  COMPLETENESS  every card carries all 6 score elements + List/Elder/SRM/Thematic + levels +
                Committee/Risk/Condition/QS lines · every HOLD-FOR-CONDITIONS carries a condition line ·
                every ADVANCE carries attributed opposing case + falsifier · near-miss list present ·
                staleness + DEGRADED flags in header
  COMPOSITION   report follows the 8-section contract (S7) · shortlist appears ONCE, as cards ·
                zero narration phrasing · action plan addressed to PM
  Q6r           (2026-08-18, closes "gaps and forget will occur") — `repeat_watch.json` exists for
                this session · it covers every ticker in `phase4_ledger.json`'s `repeat_flags` for
                this date (none missing) · every repeat-flagged ticker's name actually appears in the
                rendered §4 text. This is a PROVENANCE check, not a numbers check — a hand-typed §4
                fails Q6r even if its numbers happen to be correct, because the point is that the
                tool ran, not that a human got the math right this one time.
FAIL → route to owning stage (render fails re-render; missing obligations re-open S6 close; seat
breach re-runs that seat; Q6r fails route back to S6.7 — run record-verdicts + repeat-watch, then
re-render §4 from the tool's own markdown). Max 2 loops. Whatever still fails is DECLARED in the
footer — the PMA never ships a silent defect, and never ships without this gate's PASS record attached.

## S7P · PUBLISH
data/pma/<date>/ (all stage artifacts, git, including phase4_ledger.json append, verdict_ledger.json
update, and repeat_watch.json) · aegis/reports/pma/<date>.md + latest.md (byte-identical) · project doc ·
AND printed in full on screen for the PM.
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
