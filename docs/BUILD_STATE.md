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

## Plan and status
| # | Step | Status |
|---|---|---|
| 0 | BUILD_STATE.md pushed | DONE |
| 1 | One code tree: sync vendored pipeline/menus/canon to 1.31.0/1.9.0 + drift test | TODO |
| 2a | `RUN.yaml` rosters → 7 deciders + Steenbarger QA; shortlist cap 6; macro seats removed | TODO |
| 2b | Revert conflicts: Seow out of `STRENGTH_SEATS`; Seow card R10 off the lane tag; all 7 count on every name | TODO |
| 2c | Objection rule replaces `consensus` (0 agreed / 1–3 contested / ≥4 dropped); slate cap 15; code counts | TODO |
| 2d | Schemas: case form, challenge form, floor message, slate, ratification; registrar validates them | TODO |
| 2e | Checkpoint path → `aegis/output/pma/run/<date>/` | TODO |
| 2f | One risk config file (Aegis side, $620) | TODO |
| 3a | Chair agent + `pma-deliberate` skill (floor, slate, ratify, hold, close) | TODO |
| 3b | `voice-deliberate` + per-decider discussion blocks (from seat_skills_design) + Steenbarger QA checks | TODO |
| 3c | `aqe-engineer` agent card (from spec §11) | TODO |
| 3d | Record: per-voice per-ticket log; scorecard at own horizon; dropped/contested tracked | TODO |
| 3e | Cards: slate ≤15, objections, Detect-lens top-10 panel (`lens_ranking.ranked[0:10]`), weather from Crown file + Valen | TODO |
| 4 | AQE cleanup: packet roster (tests assert 11 files), journal-push HF rebuild, `aegis/plugin/` archive, stale `levels_parts/part_07.json`, `held_sl/tp` columns, $70K/$75K in CLAUDE.md | TODO |
| 5 | Checker `daily-check` + seeded-failure proof | TODO |
| 6 | Dry run on saved day (code only) → shadow run → floor test (PM's word) → test PMA (PM's word) | TODO |

## Where the Aegis code lives in this repo
Decision pending in step 1: the plugin tree is vendored under `aegis/` (today only `skills/premarket-analysis/` + `canon/`). Plan: bring the full kernel plugins in under `aegis/plugins/<name>/` as the one truth, and make `aegis/skills/premarket-analysis/tools/pma_pipeline.py` + `contracts/voice_menus.json` thin copies with a drift test.
