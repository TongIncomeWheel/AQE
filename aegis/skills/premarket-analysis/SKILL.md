---
name: pma
description: "PMA — Premarket Analysis, the committee morning. Trigger: /pma. One command, repeatable by hand or on a scheduler: pulls the day's AQE export + Crown macro file from the repo, spawns the macro voices and the 9-seat blind swarm, tallies, ranks to the Phase-4 cap, runs challenge + fundamentals + Round-2 deliberation on the capped set, closes consensus arithmetically, auto-brackets everything phase-3+, renders the fixed 6-section CIO report with ticker cards, passes the S7Q quality gate, publishes to git + project doc + on screen. Analysis only — no brokers, no orders, no sizing (constitution law 1 untouched). v4.2, PM-ratified 2026-08-17; validated end-to-end on the 2026-08-17 dry run (25 spawns, 0 errors)."
---

# /pma — PREMARKET ANALYSIS (v4.2 operational card — supersedes the v0.4 design card)

**Source of truth: `TongIncomeWheel/AQE` branch `main`. Everything this run reads and writes lives there.**
Inputs: `aegis/output/aqe_daily_export.json` + `aegis/output/aqe_crown_macro.json` (fixed names, overwritten daily — the ONLY data sources, never Drive).
Code: `aegis/skills/premarket-analysis/tools/pma_pipeline.py` + `contracts/voice_menus.json` (fetch fresh from main every run — never a cached copy).
Spec annex: `aegis/skills/premarket-analysis/stages/S6B_post_committee.md` (post-committee contract — consensus rule, ranking key, ledger, card contract, S7Q families). On any conflict, S6B wins.
State: `data/pma/<date>/` (run artifacts) · `data/pma/phase4_ledger.json` (rolling repeat ledger) · `aegis/reports/pma/<date>.md` + `latest.md`.

**Control vs judgment (D-16).** The session running this card is CONTROL: fetch, validate, spawn, collect, run the tool, render, publish. It forms no market opinion. Judgment happens only inside spawned voice agents. Every arithmetic step runs through `pma_pipeline.py` — same inputs, same outputs, no model in the path.

**Unattended rule.** A scheduled firing has no PM watching. Never block on a question: apply the failure ladder, declare every degradation in the report header, and publish. The report footer is always: "DRAFT — PM approval required. Nothing is staged, nothing is armed."

## Procedure

**S0 · PREFLIGHT.** Confirm the GitHub MCP connector answers (one `get_file_contents` on `aegis/output/`). If absent → STOP, no plan, page the PM: the run cannot read its inputs or persist its outputs. Confirm the `aegis-voices` agent types are available (they ship in the aegis-voices plugin). Note UTC/SGT date; the run date is the SGT calendar date.

**S1 · INGEST.** Fetch both input files from `main` (always `ref: refs/heads/main`, never a pinned SHA). Validate: export has `daily_list`, `srm`, `regime`, `macro_weather`; crown file parses. Record staleness (export date vs run date) and every DEGRADED flag — they travel verbatim into the report header. Export missing/invalid → STOP. Crown missing → continue AQE-only, headline says so. Fetch `pma_pipeline.py`, `voice_menus.json`, `S6B_post_committee.md`, and `data/pma/phase4_ledger.json` to the working dir.

**S2 · TRIM + PACKETS (tool).** `pma_pipeline.py trim` → `candidate_set.json` (full 279-row CONSUMED trim, keeps `source`/`on_longlist`/`in_ledger`/`elder*`). Then `pma_pipeline.py packets` → per-voice menu-sliced shuffled TSVs + crown/druckenmiller macro packets. The tool asserts R3 (no `qs_market` in any seat packet) and fails loudly on breach. `qs_market` is PM-only: it appears in the report's macro section as the PM's regime read, never in any seat's input. **The packets receipt prints `missing_menu_fields` — any menu field null on every row. Non-empty = a seat is being served a blank column: treat as a DEGRADED flag, declare it in the report header (field-audit rule, 2026-08-17).**

**P0 · MACRO VOICES (2 spawns, parallel).** Spawn `aegis-voices:voice-druckenmiller` and the crown voice with their JSON packets INLINED in the prompt (never a path — toolless agents fabricate when handed paths, finding F1). Crown reads its own macro file + the export's sector/theme layer (R6). Druckenmiller reads all macro weather + Crown DATA POINTS, never Crown's prose, never QS (R3); he MUST file `agrees_on`/`differs_on` vs Crown — conflicts are surfaced to the PM, never resolved by the committee.

**S4 · SWARM (9 spawns, parallel, blind).** One isolated spawn per nominator: `elder-lens, livermore, minervini, oneil, raschke, seow, thorp, wyckoff, weis`. `kratter` and `ceponas` join once their books are ingested. Each gets: its own agent card (the plugin agent type carries it) + its own TSV packet inlined + nothing else. No tally, no other voices, no ordering hints. Each returns nominations with ticker, conviction 1–5, reason, `fields_cited`. One re-spawn on invalid return; still bad → seat marked `absent`, quorum check at S6 (≥8). Lynch, Rogers, steenbarger, detect-lens are NOT nominators.

**PHASES 2–4 · TALLY → QUALIFY → RANK → CAP (tool).** `pma_pipeline.py tally` then `rank --cap 20`. Qualification: seat_count ≥2 OR solo conviction ≥4. Ranking key (fixed, v4.2): seat_count → conviction_sum → SRM support (sector `entry_gate`: PASS>CAUTION>WATCH>BLOCKED) → thematic support (DEPLOY grade or LEADING/IMPROVING rrg) → sc_momentum. Top-20 = deliberation set. **No gate anywhere in this chain — no sector, fundamental, or bracket term (R1).** Then `pma_pipeline.py ledger` — append ALL qualifiers (survivors + cap-cut) to `phase4_ledger.json`; any ticker at ≥2 appearances in the trailing 5 sessions gets a REPEAT flag → PM manual look.

**S5a · CHALLENGE (2 spawns, after the cap).** Rogers and Steenbarger get the deliberation set + nomination counts → challenge documents (Rogers: crowding, certainty, timing risk; Steenbarger: conviction audit, structural weakness, conviction change risk). Both documents join the Round-2 packet.

**S5b · FUNDAMENTALS + LENS (2 spawns, after the cap).** Lynch activates ONLY on the deliberation set (R5/R7): FMP MCP + web grounding, six-category quick pass per name, every figure with source+date. Detect-lens activates on the deliberation set: technical structure assessment, pattern confirmation, momentum lens. Both memos join the Round-2 packet. If FMP/web is unavailable in this session, Lynch files with an explicit "fundamentals unserved" flag per name — the run continues, degradation declared.

**S6 · ROUND 2 (11 spawns: 9 nominators + lynch + detect-lens as voting seats).** Every seat files SUPPORT/OPPOSE/ABSTAIN on EVERY deliberation-set name plus the obligation register (O1–O8: opposing argument on every OPPOSE, self-counter on high-conviction SUPPORT, falsifier, conviction-change reason, Rogers/Steenbarger challenge answer, direct-challenge replies, Steenbarger conviction_audit). Packets carry: the name's full universe row + all Round-1 reasons (attributed) + Rogers' and Steenbarger's challenges + Lynch's fundamentals memo + Detect-lens's technical lens assessment. Quorum <8 → no ADVANCE possible, watch-table-only run. At 11 voting seats the floor of 8 leaves 3 seats of margin; re-derive on roster change.

**S6.5 · CONSENSUS + SYNTHESIS (tool + compile).** `pma_pipeline.py consensus`: ADVANCE = support>oppose AND support≥2 AND median support conviction ≥3; else support≥2 → HOLD-FOR-CONDITIONS; else PASS. Caps only lower conviction (steenbarger flag→3, support<3→4, non-ADVANCE→3). Compile per-name verdict records: split, strongest opposing case (verbatim, attributed), falsifiers, fundamental line. **Every HOLD-FOR-CONDITIONS gets a mandatory observable condition line** — from a seat's filed promotion condition, else synthesized from the strongest opposing case. No persuasion narration anywhere.

**S6.6 · AUTO-BRACKET (R8, tool-read).** Every deliberation-set name gets levels verbatim from its export `bracket` block: structural stop/TP/R:R if `valid`, else `atr_fallback_stop` labelled FB + nearest overhead levels. Informational only — filters nothing, ranks nothing, vetoes nothing (R1).

**S7 · RENDER.** Fixed 6 sections: 1 Macro position (Crown + Druckenmiller + the PM-only QS read, conflicts surfaced) · 2 Sector & thematics (SRM table + baskets) · 3 Held book review (from export `held_book`; if stale, one line saying so — the PM refreshes via PTJ) · 4 Shortlist as TICKER CARDS · 5 Near misses (every cap-cut qualifier, one row each, never grouped) · 6 Action plan addressed to the PM. Card contract (no omissions): header (ticker·verdict·conviction+cap reason·vote S-O-A·sector) · List line (source track + Elder score/pattern/5d + SRM gate + thematic) · scores (conviction/detect/coil/momentum/accumulation/structure) · levels (px/stop[structural|FB]/TP1-2/R:R/ATR) · Committee/Risk/Condition lines · REPEAT flag if ledgered ≥2x/5.

**S7Q · QUALITY GATE (tool).** `pma_pipeline.py gate` — mechanical checks: every ADVANCE has support>oppose; every HOLD has a Condition line; all 6 sections present; List/Elder present; zero persuasion phrasing; DRAFT footer. FAIL → fix at the owning stage, max 2 loops, residuals DECLARED in the footer. Never publish silently defective.

**S7P · PUBLISH.** Push to `main`: `data/pma/<date>/` (candidate_set, tally, phase4, consensus, run record) + updated `phase4_ledger.json` + `aegis/reports/pma/<date>.md` + `aegis/reports/pma/latest.md`. Write the report to the claude.ai project doc (`claude/pma_dryrun_brief_<date>.md` naming continues as `claude/pma_brief_<date>.md`). Print the full report on screen. If the session can send files, send the .md.

**S8 · AUDIT.** Write `data/pma/<date>/run_audit.json`: seats spawned/responded, stage receipts, gate result, degradations, spawn count, wall time. This is the learning loop's input.

## Voice roster (v4.2 architecture — 2026-08-17 update)

**S4 Nominators (9 live, 11 once kratter + ceponas land):**
- elder-lens, livermore, minervini, oneil, raschke, seow, thorp, wyckoff
- **weis** — 23 principles, `aegis/canon/weis/`, grounded 2026-08-17, 34-field menu. The failed-breakout seat: buys the break that does not follow through. No canon overlap with detect-lens, which is CODE-grounded (`src/engines/*.py`, 33 principles, pm_signed Ash) and reads no books.
- Pending their books: kratter, ceponas.

**S5a Challenge (2):**
- Rogers (locked)
- Steenbarger (locked; moved from S4 nominator to challenge role)

**S5b Fundamentals + Lens (2):**
- Lynch (locked; fundamentals + Round-2 voting seat)
- Detect-lens (locked; technical lens + Round-2 voting seat)

**S6 Round-2 Voting (11 seats):**
- 9 nominators from S4
- Lynch (voting + fundamentals)
- Detect-lens (voting + technical lens)

## Field-audit rule (2026-08-17)
Every field on every seat menu MUST resolve to real data on the live export. The packets receipt
prints `missing_menu_fields` per run; any dead column is a DEGRADED flag in the report header and
an S8 audit entry. Root causes fixed 2026-08-17: (1) `_slice` resolved only `bracket.*` dotted
fields — all other dotted fields silently nulled; (2) CONSUMED dropped `ma_100`,
`runner_conviction`, `premove_conviction`, `sc_m_gate_detail`, `sc_p_gate_detail` which exist in
the raw export; (3) menus named phantom fields (`energy.squeeze_score`, `bq.*`,
`knn_significant`, `rvol`) — remapped to `squeeze_breakout_*`, `elder_context.vcp.*`,
`knn_threshold_clear`; rvol dropped. The per-ticker `qs.*` block is PM-ONLY (R3): it must never
appear on a seat menu even when a needed field only exists there — use the nearest non-QS proxy
and declare it.

## PM parameters (change here + S6B together)
`deliberation_cap=20` · `solo_high_conviction_min=4` · `phase4_window=5 sessions, repeat_threshold=2` · `max_quality_loops=2` · `cards_soft_max=5 actionable`.

## Failure ladder (unattended-safe)
Export missing/invalid → STOP, no plan · Crown missing → AQE-only, declared · seat absent after re-spawn → quorum math, declared · FMP absent → Lynch files unserved flags · missing_menu_fields non-empty → DEGRADED flag in header · GitHub write fails at S7P → report still prints on screen + project doc, push retried once, failure declared · anything DEGRADED → verbatim in the header.