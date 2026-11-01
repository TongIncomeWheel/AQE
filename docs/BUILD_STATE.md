# Aegis redesign — BUILD STATE (living handover)

**Any fresh session resumes from here.** Read this, then `docs/AQE_CODE_AGENT_SPEC.md`, then the kernel docs the PM uploaded (`START_HERE.md`, `docs/DECISIONS_2026-10-30.md`, `BUILD_PLAN.md`). The kernel zip is `aegis-kernel-2026-10-30.zip` in the PM's uploads; unzip into an empty dir and read with `python3 -I`.

Branch: `claude/upbeat-curie-s7i1ut` (push here only; `main` release needs the PM's explicit word).
Started 2026-11-01. Model: Fable 5.1 for committee/registrar work.

## Guard rails (never bend)
1. Do NOT run `/pma` or the committee until the PM says so (~905k tokens).
2. Pushes to `main` outside `aegis/output/**` rebuild the HF Space. Branch pushes are safe (`deploy-hf.yml` fires on `main` only).
3. Nothing places an order. Voices judge; code counts, validates, records.
4. Small commits, pushed after every green step. Never leave a step half-applied.
5. Plugin tests: `cd <plugin>/aegis-core/skills/pma && python3 tests/test_pipeline.py` → expect 307 passed (self-running script). AQE: `pytest -q` (~10 min, full) — baseline has **7 known failures** (see below); only a NEW failure blocks.
6. Clean test leaks before committing (`aegis/output/alerts/`, `data/sector_map.json`, `data/universe.txt`, `output/aqe_macro_pack.json`). Stage only touched files, never `git add .`.

## Facts established (2026-11-01, Session 1)
- AQE head at start: `77baded` (data: daily output 2026-10-31). Repo attached with push access — the earlier 403 was not an attach problem.
- Plugin tests: 307/0. AQE readout subset: 134 pass / 3 fail; all 3 are in the known-7 baseline (2× HF-mirror checks in `tests/test_github_sync.py`, O'Neil canon R6 wording in `tests/test_voice_packet_spec_2026_09_05.py`). The other 4 known = Layer-0 "names on both lists" tests (retired rule).
- `AQE_CODE_AGENT_SPEC.md` lived only on diverged branch `claude/password-google-drive-access-GtUhV` (no merge base with main). Copied to this branch as a doc (`f0603128`). Leave that branch unmerged.
- Vendored drift confirmed: `aegis/skills/premarket-analysis/tools/pma_pipeline.py` + `contracts/voice_menus.json` = plugin 1.24.1; `aegis/canon/*` = voices 1.8.0 (15 dirs). Kernel plugin = aegis-core 1.31.0, aegis-voices 1.9.0.
- The 05:30 "AEGIS Daily" scheduled task (`trig_01SCdZcq9vmF9HpDU4pmM2xm`) pushed `aegis/triggers/aqe_daily_run.json` → nothing reads it, rebuilt HF Space. **Removed 2026-11-01**: stage 3 now read-only reports `aqe_last_run.json`. Original wording backed up in session only (container); the change: "do NOT push the trigger file; the 08:30 task is the only AQE start".
- Also found: stage 1's journal push to `aegis/data/journal/` ALSO rebuilds the HF Space (deploy-hf only ignores `aegis/output/**`). Not yet fixed → cleanup item.
- `aegis-core:tiger` plugin MCP fails to connect (ERR_INVALID_ARG_VALUE); `Tiger_MCPv7` connector works.
- Risk config decision (default applied): 1R = $620 lives Aegis-side only. AQE alert config ($75K/3%) untouched — spec hard-stop on sizing changes; PM rule says ignore alert share counts anyway.

## Test baseline (full `pytest -q`, 2026-11-01, 8 min)
1707 passed, **8 failed**: the known 7 (2× HF-mirror `test_github_sync.py`, 4× Layer-0 `test_layer0_committee_filter_2026_09_06.py`, 1× O'Neil R6 `test_voice_packet_spec_2026_09_05.py`) **plus** `test_crown_macro.py::test_staleness_reports_the_last_bar_and_the_lag_to_today`, which assumes today is a trading day and fails on weekends (ran Sunday). Not a regression; cleanup item (make the test use the last business day).

## Commits on this branch (newest first)
- Commit G — **the Cards (3e).** `pma_cards.py`: head pills count AGREED / CONTESTED / DROPPED; HOLD pill reads `HOLD · WATCH`; a CONTESTED ticket prints each objection and what would clear it; an AGREED ticket prints reservations; a DROPPED name says so on its PASS row; **Detect-lens top 10** panel from `lens_ranking.ranked[0:10]` (marker where a name is in the room), placed before "The plan" so the R23 fixed order holds; a missing `lens_ranking` is a declared gap. Rows without `status` render as before. Plugin suite **475/0**.
- Commit F — **AQE cleanup + the Checker.** Packets: TSVs for the 7 deciders only, macro packets retired (`cmd_packets --macro-seats` re-enables; AQE's `_build_into` passes `macro_seats=[]`); `tests/test_voice_packets.py` GROUP_A = deciders, 7 files asserted, GROUP_B asserted never built; spec test group_a = deciders. `deploy-hf.yml` also ignores `aegis/data/journal/**` (the 05:30 journal push no longer rebuilds the Space — takes effect on release to main). `CLAUDE.md` risk lines: $70K/$2,100 retired; AQE cards $2,250, Aegis 1R $620 in `aegis_fund.md`. `test_crown_macro` weekend fix (asserts against the last business day). **Checker:** `aegis-core/skills/daily-check/` (`check.py ready|chain|all`, read-only, exit 1 on any FAIL; seeded-failure test proves it names a stale marker, a pending step, a 16-ticket slate, an over-ceiling spend, a missing file, yesterday's levels). Plugin suite **465/0**. `levels_parts/part_07.json` already absent (nothing to clean). Still open for the PM: `held_sl`/`held_tp*` source; capital base 75K vs 62K.
- Commit E — **seats, Chair, checkpoint path, one risk figure.** aegis-voices → 1.10.0: the 7 decider cards (agent + skill copies — there is NO compiler; edit both) gain `## 7 · ON THE FLOOR (R36)` from `seat_skills_design` §3; Steenbarger gains `## 7 · QUALITY ASSURANCE`; Seow R10 picks the system from the name's own picture (lane = label); `skills/voice-deliberate`; weis/thorp/rogers/lynch/crown/druckenmiller/detect-lens cards → `aegis-voices/archive/` (git mv, canons untouched, README says how to re-seat). aegis-core: `agents/chair.md`, `agents/aqe-engineer.md` (spec §11), `skills/pma-deliberate`; `voice_preflight.py` (both copies) roster = deciders, quorum 6; **git_sync `--dest` + refuses to stage outside `aegis/output/`** (RUN.yaml checkpoint → `aegis/output/pma/run/<date>`; root copy mirrored); **one risk figure**: `config/aegis_fund.md one_r_usd: 620`, `fund_config.one_r_usd()`, `bracket_calc.load_params(dyncap)` sizes from it and reports `one_r_source`; `parameters.yaml` percent annotated as unused while set. **PM to confirm:** fund file still says allocated 75,000 / dynCap 66,699 vs the "$62K portfolio" of 27 Oct. Plugin suite **454/0**.
- Commit C — **the committee engine.** aegis-core → 1.32.0. RUN.yaml: MACRO retired; NOMINATE/VOTE/RATIFY seat the 7 deciders; CHALLENGE + QA = steenbarger; new FLOOR (board + floor-check), SLATE, RATIFY, QA steps; DECIDE = `ratify-count`. pma_pipeline.py: `board` (contested = blind split both ways OR named in the challenge; no verdict), `floor-check` (2 msgs/seat/name, open names only, replies must exist; hold round opens held tickets only), `ratify-count` (objection rule, thr = ceil(n/2), n ≥ 4; consensus.json keeps verdict/conviction/lane/split + adds status/objections/reservations; committee_record.json per voice per ticket), `r2digest --crown` (weather from AQE's Crown file; retired seats marked), `consensus` prints SUPERSEDED. Plugin suite **405/0**. **Gotcha:** the plugin's mini-YAML loader does NOT strip `# comments` after a value — never put an inline comment after `seats:`, `spawns:`, `after:` or a parameter in RUN.yaml (the old `checkpoint_after: true  # n seats` lines only work because a non-empty string is truthy).
- `b818e5a9` Commit B — forms: case form on every vote (R36), shortlist cap 6 + decider-only ballots (R33/R31), registrar `--kind challenge|floor|slate|ratify|qa`, six schema contracts. Date-gated on 2026-11-01; history validates as filed. 348/0.
- `599d4884` Commit A — rulings R31–R36 recorded; R14/R22/R30 superseded; roster constants; seow out of `STRENGTH_SEATS`; `R2_VOTING_SEATS = DECIDERS`. 315/0.
- `290ef63a` one code tree (step 1).
- `ed0a1f31` BUILD_STATE; `f0603128` AQE_CODE_AGENT_SPEC doc.

## Plan and status
| # | Step | Status |
|---|---|---|
| 0 | BUILD_STATE.md pushed | DONE |
| 1 | One code tree: sync vendored pipeline/menus/canon to 1.31.0/1.9.0 + drift test | DONE `290ef63a` |
| 2a | Rulings R31–R36 as data + roster constants (Commit A) | DONE |
| 2a' | `RUN.yaml` rosters → 7 deciders + Steenbarger QA; MACRO step removed; FLOOR/SLATE/RATIFY/QA steps; DECIDE → ratify-count | DONE (Commit C) |
| 2b | Revert conflicts: Seow out of `STRENGTH_SEATS` (Commit A); Seow card R10 off the lane tag (Commit E) | DONE |
| 2e | Checkpoint path → `aegis/output/pma/run/<date>/` (git_sync `--dest` + outside-output refusal) | DONE (Commit E) |
| 2f | One risk config file (Aegis side, $620 in `aegis_fund.md`) | DONE (Commit E) |
| 3a | Chair agent + `pma-deliberate` skill | DONE (Commit E) |
| 3b | `voice-deliberate` + per-decider discussion blocks + Steenbarger QA checks | DONE (Commit E) |
| 3c | `aqe-engineer` agent card | DONE (Commit E) |
| 2c | Objection rule replaces `consensus` (0 agreed / 1–3 contested / ≥4 dropped); slate cap 15; code counts; record per voice per ticket | DONE (Commit C) |
| 2d | Schemas: case form, challenge form, floor message, slate, ratification, QA note; registrar validates them | DONE (Commit B) |
| 2e | Checkpoint path → `aegis/output/pma/run/<date>/` | TODO |
| 2f | One risk config file (Aegis side, $620) | TODO |
| 3a | Chair agent + `pma-deliberate` skill (floor, slate, ratify, hold, close) | TODO |
| 3b | `voice-deliberate` + per-decider discussion blocks (from seat_skills_design) + Steenbarger QA checks | TODO |
| 3c | `aqe-engineer` agent card (from spec §11) | TODO |
| 3d | Record: per-voice per-ticket log; scorecard at own horizon; dropped/contested tracked | TODO |
| 3e | Cards: slate ≤15, objections, Detect-lens top-10 panel (`lens_ranking.ranked[0:10]`), weather from Crown file + Valen | TODO |
| 3d | Record: per-voice per-ticket log (committee_record.json) — DONE (Commit C); scorecard at own horizon — TODO (pma_scorecard reads one `--horizon`; wire `horizon_sessions` from the record) | PARTIAL |
| 3e | Cards: slate status + objections + DROPPED marks + Detect-lens top-10 panel (weather from Crown/Valen was already Part 1) | DONE (Commit G) |
| 4 | AQE cleanup: packet roster 7 (DONE F), journal-push HF rebuild (DONE F), `aegis/plugin/` refreshed (DONE 1), stale part_07 (already gone), CLAUDE.md figures (DONE F); `held_sl/tp` columns → PM decision | DONE except held_sl/tp |
| 5 | Checker `daily-check` + seeded-failure proof | DONE (Commit F) |
| 6 | Dry run on saved day (code only) → shadow run → floor test (PM's word) → test PMA (PM's word) | TODO |

## Where the Aegis code lives in this repo
Decision pending in step 1: the plugin tree is vendored under `aegis/` (today only `skills/premarket-analysis/` + `canon/`). Plan: bring the full kernel plugins in under `aegis/plugins/<name>/` as the one truth, and make `aegis/skills/premarket-analysis/tools/pma_pipeline.py` + `contracts/voice_menus.json` thin copies with a drift test.
