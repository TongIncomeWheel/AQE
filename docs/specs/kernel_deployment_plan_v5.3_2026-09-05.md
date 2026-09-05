# AEGIS KERNEL PLUGIN — DEPLOYMENT PLAN v5.3
Date 2026-09-05 · Fixes the efficiency, reliability and selection problems of the last two weeks · Every item names the file, the change, and the test that proves it

Plugin source lives in `TongIncomeWheel/AQE` under `aegis/skills`, `aegis/tools`, and the voice cards under the `aegis-voices` plugin. Deploy = edit in repo → push (connector) → `packaging/build_claude.py` → reinstall plugin in Cowork.

---

## PHASE 1 — STOP THE BLEEDING (before the next run, ~2 hours, all mine)

| # | File | Change | Test |
|---|---|---|---|
| 1.1 | `aegis/skills/pma/SKILL.md` (conductor card) | **Mandatory snapshot after every tick:** after each `registrar.py tick`, write `SNAPSHOT_<stage>.json` (manifest + all committed forms) to the project store. A failed store write is a hard stop, per v5 §6. | Kill the session after NOMINATE; `/pma resume` in a fresh session must rebuild from the project snapshot without re-spawning any seat. |
| 1.2 | `aegis/skills/pma/SKILL.md` | **Seat spawn pattern:** never spawn `aegis-voices:*`. Spawn `general-purpose`; prompt = read own card from `/root/.claude/plugins/synced/*/aegis-voices/agents/voice-<seat>.md` + read packet from the shared outputs dir; return MD5 of packet + verbatim line N. Registrar rejects any return whose MD5 or proof line does not match before validating the form. | Spawn one seat with a deliberately wrong expected MD5 → must be rejected. |
| 1.3 | `aegis/skills/pma/SKILL.md` | **VOTE in two waves of ≤6**, snapshot between waves. | A rate-limit kill mid-wave-2 costs ≤6 seats, never the round. |
| 1.4 | `aegis/skills/premarket-analysis/tools/pma_pipeline.py` — new `cmd_r2digest` | **Round-2 packet built by tool, not by hand.** Inputs: phase4.json, candidate_set.json, fundamentals_pack.json, 4 challenge JSONs. Output: one text packet with (a) the deliberation rows using the export's real field names (`stop_type`, not `stop_basis`), (b) each seat's R1 reason attributed, (c) each challenge doc reduced to its `findings[]` + `obligations[]` only — no declarations, no per-name verbatim reads. Target ≤70KB (was 183KB). | Byte count ≤70KB; every ticker in phase4 present; zero `None` where the export has a value. |
| 1.5 | `aegis/tools/preflight.py` | Missing `GITHUB_PAT` is a **warning, not a stop**, when the session has the GitHub connector. Print which push path will be used. | Fresh container, no `.env`: preflight exits 0 with "push path: connector". |
| 1.6 | `aegis/skills/ptj/SKILL.md` + `aegis/skills/premarket/SKILL.md` | After the batch stamps `partial` on push-fail only, the conductor pushes the changed files via connector and re-stamps `ok` with the connector commit SHA in the note. Documented as the standard path, not a workaround. | Next-morning gate reads READY, not BLOCKED. |
| 1.7 | `aegis-core/agents/brief-writer.md` | **The brief opens with the verdict table**: ticker · AQE rank · door(s) · seats · verdict · one-line condition. Prose follows. Held-book table second. Everything else after. | `gate` adds check Q1T: first table in the brief is the verdict table with every deliberated ticker. |

## PHASE 2 — THE SELECTION FIX (next morning, ~3 hours)

| # | File | Change | Test |
|---|---|---|---|
| 2.1 | `pma_pipeline.py cmd_rank` | **Four admission doors**, union, cap 30: DOOR1 seats≥2 (always kept) · DOOR2 `elder_5d[-3:]` all ≥7 AND `lens` strong count ≥3 · DOOR3 pm_lens ≥5/6 (rank now reads pm_lens.json, so PM-LENS runs before RANK) · DOOR4 `elder_pattern∈{SUSTAINED,ACCELERATION}` AND `rs_leadership=LEADER` AND `mp_state=STRONG`. Doors 2–4 fill to 30 by AQE `rank`. Each name carries `doors:[...]`. `--solo-min` removed. | On the 09-04 export: 46 admitted, 30 after cap, VLO/MPC/DINO/DUOL present, CB present via DOOR1. |
| 2.2 | `pma_pipeline.py cmd_r2digest` | Print `doors` on every deliberation row so voters see how the name arrived. | Visible in packet. |
| 2.3 | `pma_pipeline.py cmd_ledger`, `purity_check.py` | Ledger logs all admitted names with their doors. Purity invariance test re-run with doors on: rank must still be invariant to bracket/fundamental fields (doors use neither). | `purity_check` PASS. |
| 2.4 | `registrar.py validate --round 2` | Ticker set must equal the **admitted** set (30), not the old 20-cap set. | Rejects a ballot missing a DOOR4 name. |
| 2.5 | `aegis/skills/pma/SKILL.md` | Map order: RANK → PM-LENS → ADMIT (PM-LENS is now an input to ADMIT, still never an input to any seat's judgment). Quorum unchanged. | Manifest shows PM_LENS ticked before ADMIT. |

## PHASE 3 — CARDS AND DEAD CODE (same day, ~2 hours)

| # | File | Change | Test |
|---|---|---|---|
| 3.1 | `aegis-voices/agents/voice-oneil.md`, `voice-raschke.md`, `voice-wyckoff.md` | **Delete** every line that makes `bracket.valid=false`, `bracket.risk_pct`, or `rr` a reject. PM ruling R1. | `grep -n "bracket.valid.*reject"` returns nothing. |
| 3.2 | `voice-livermore.md` | Fix R1: `sma_distance_pct` is distance from the 50-day SMA, not from a recent high. Until `pct_from_52w_high` ships, use `structure_shift=BULLISH_BOS` + `mp_accel_state` for "fresh new high"; never read sma_distance as proximity-to-high. Resolve the "SEAT STATUS — NOT DECIDED" header: PM to ratify or unseat. | Card text; PM decision recorded. |
| 3.3 | all nominator cards | Retire phantom field names: `rvol→day_vol`, `knn_significant→knn_threshold_clear`, `energy.squeeze_score→squeeze_breakout_state`, `bq.*→elder_context.vcp.*`. | `grep` across cards returns nothing. |
| 3.4 | `voice-lynch.md` | Replace "not one field is a fundamental" with the FMP pack contract: pack arrives at GATHER, judge from it, never fetch. | Card text. |
| 3.5 | `voice-weis.md` | Return format aligned to `nomination.schema.json` (conviction 1–5, checklist_trace). `catalyst` optional until `next_earnings_date` ships. | Registrar validates a weis form first pass. |
| 3.6 | `aegis/skills/premarket/SKILL.md` | Drop step 8's `dyncap_ledger.py update`. The journal's D-99 recompute is the only dynCap. | Report shows one dynCap number, not two. |
| 3.7 | `aegis/skills/pma/SKILL.md` | Replace data-steward agent with a script step: `pma_pipeline.py gather --date` copies export/crown/ledgers, hashes them, writes `data_health.json`. No agent. | Manifest GATHER ticks `done`, not `degraded`. |
| 3.8 | `contracts/voice_menus.json` | Apply the per-seat **+/−** from `aqe_voice_packet_spec`. Add only fields AQE serves today; the 18 new fields join as AQE ships them. | `emit_packets.py` receipt: `missing_menu_fields none`. |

## PHASE 4 — AQE SIDE (AQE's schedule, spec already handed over)

`docs/specs/aqe_voice_packet_spec_2026-09-05.md` in the repo. 18 fields to add, 11 to surface, 6 to retire. `elder_hi7_streak` unlocks DOOR2 as a served field; `rs_rank_pct` + `pct_from_52w_high` upgrade DOOR4 from the 3-bucket proxy to the real Minervini/O'Neil leader test.

---

## ACCEPTANCE — what "it works" means

| Test | Pass condition |
|---|---|
| **T1 clean run** | `/premarket` then `/pma`, one session, ≤90 min, ≤2.5M tokens, zero questions to the PM, brief opens with the verdict table. |
| **T2 wipe survival** | Kill the container after CHALLENGE. Fresh session, `/pma resume`: VOTE runs, no seat before it re-spawned. |
| **T3 rate-limit survival** | Kill during VOTE wave 2. Resume completes wave 2 only. |
| **T4 leaders seen** | On any day with ≥1 AQE leader (DOOR4), that name appears in the vote and in the brief's table with a verdict — never silently absent. |
| **T5 no bracket gate** | Grep all cards: zero reject rules on bracket/rr. Registrar lint flags BRACKET_BASIS but never rejects. |
| **T6 fresh container** | No `.env`, no PAT: preflight passes, premarket pushes via connector, gate reads READY next morning. |

## TOKEN BUDGET, before → after

| Stage | Before | After | How |
|---|---|---|---|
| NOMINATE + MACRO | ~1.1M | ~1.1M | unchanged |
| CHALLENGE | ~0.5M | ~0.5M | unchanged |
| VOTE | **~2.0M** | **~0.9M** | 70KB packet not 183KB; findings not full JSON |
| BRIEF | ~0.2M | ~0.2M | unchanged |
| Rework from wipes/limits | **1–3M** | **~0** | snapshots + waves |
| **Run** | **4–7M** | **~2.7M** | |

## ORDER OF OPERATIONS

Phase 1 → run it live once → Phase 2 → run live once → Phase 3 → rebuild plugin → T1–T6. Nothing in Phase 2 or 3 starts until Phase 1 has produced one clean run. That is the rule this plan follows, because it is the rule the last two weeks did not.
