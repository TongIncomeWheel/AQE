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

## Where the build stands at hand-off (2026-11-01, end of Session 1)
**Built and tested (plugin suite 476/0; `build.py` produces all five `.plugin` zips; drift CLEAN):** the roster, rulings R31–R36, the case form, the five deliberation forms, `board` / `floor-check` / `ratify-count` with the objection rule and the per-voice record, RUN.yaml's FLOOR/SLATE/RATIFY/QA rounds, the Chair + `pma-deliberate` + `voice-deliberate`, the seven decider cards' floor blocks, Steenbarger's QA block, Seow R10 off the lane, archived cards, `aqe-engineer`, the checkpoint path with the outside-output refusal, the one risk figure, the packet roster (7), the HF ignore for the journal push, the Checker with a seeded-failure proof, the Cards (status, objections, DROPPED, Detect-lens top 10). **Nothing has run a committee. Nothing is on `main`.**

**Not done (in order of value):**
1. **Phase 1b floor test** — two real seats, one contested name, floor + ratify + hold on real forms. PM's word only (costs tokens). This is the untested mechanism (agent messaging proven on trivial agents only).
2. **Dry run on a saved day** (`docs/DRYRUN.md`, code only, no model) → **shadow run** publishing to `aegis/output/assess/shadow/` → the **test PMA**. Each on the PM's word.
3. **Release to `main`** (`aqe-release`): PM's word; safe window (not during a run / US session); it WILL rebuild the HF Space once (source change); then the Checker confirms the next nightly run.
4. Scorecard at each voice's own horizon (`pma_scorecard.py` still grades one `--horizon`; the ledger row and `committee_record.json` already carry the per-ticket / per-voice horizons).
5. The one voice dataset + query helper (Phase 2; prototype in the kernel's `prototypes/one_dataset/`) — packets stay the data path until then.
6. AQE engineer backlog #2: Elder's missing fields (`impulse_state`, force index EMAs, channel, weekly resample).
7. PM decisions pending: `held_sl`/`held_tp*` source; capital base 75K vs 62K in `aegis_fund.md`.
8. The installed plugins on the PM's machine are still 1.31.0 / 1.9.0 — install `aegis/plugin/dist/*.plugin` (rebuilt by `build.py`) once the PM accepts the branch.

**Full AQE suite at hand-off (run after Commit F, 7m55s):** 1708 passed, 1 skipped, 7 failed = the known baseline at that point. **Then O'Neil R6 was fixed** (its trigger line named the barred bracket fields — the caution stays, reworded; lock + compiled card) → the known baseline is now **6**: 2× HF-mirror `test_github_sync.py` (stale assertions from the 2026-09-15 canon merge — cleanup item) and 4× Layer-0 `test_layer0_committee_filter_2026_09_06.py` (encode the retired both-lists rule). No new failure anywhere on the branch.

## RELEASE-READY, awaiting the PM's push (2026-11-01 ~17:00 UTC)
Final full AQE suite on the finished tree: **1716 passed, 6 failed = the known baseline only.** Plugin suite 491/0. `origin/main` = `d6fef9dd`; this branch is 21 commits ahead and a **fast-forward**. The push `git push origin HEAD:main` was refused by the session's permission classifier (Production Deploy) — correct: it rebuilds the HF Space and goes live. **The PM runs it** (or allows it), in a safe window (not during a run or the US session):
```
git fetch origin && git checkout claude/upbeat-curie-s7i1ut && git pull && git push origin HEAD:main
```
Then dispatch `daily-run.yml` on `main` with `force: true` (Actions → daily-run → Run workflow) so Friday's close is rebuilt on the new code; confirm `aegis/output/aqe_last_run.json` (status success, packets 7/7). Install `aegis/plugin/dist/*.plugin` (rebuilt from this tree). The pilot's first READY post fires Tue 03 Nov 07:10 SGT.

## The daily chain as scheduled tasks (built 2026-11-01 evening; PM: "resume and complete")
| SGT | Task (id) | State | Notes |
|---|---|---|---|
| 05:30 Tue–Sat | `AEGIS Daily` (`trig_01SCdZcq9vmF9HpDU4pmM2xm`) | enabled | `/daily`; trigger-file push removed |
| **06:30** Tue–Sat | `AQE daily pipeline trigger (06:30 SGT)` (`trig_01EFjk2zPDG1VnzhPyR1GuYt`) | enabled | moved from 08:30 per the PM; dispatches `daily-run.yml`, verifies the dated output |
| 07:10 Tue–Sat | `AEGIS READY post (Checker)` (`trig_01CQvuMH8BzUHtTnyr83puZX`) | **enabled** | fresh session; reads `aqe_last_run.json` from origin/main; posts READY / NOT READY; push notification; never starts anything |
| 07:20 Tue–Sat | `AEGIS pma-auto` (`trig_01Rhb3tZXFtEz88Cf3QW2wGa`) | **DISABLED** | the full `/pma` chain unattended, progress only when stuck or done, due 14:00; ceiling 1.5× baseline. **Enabling it is the PM's tap** (guard rail: no committee without his word). |
| 18:00 Tue–Sat | `AEGIS 18:00 approve-or-load gate` (`trig_01SXtDSVZ4oskfL5BB47KyBS`) | **DISABLED** | read-only Checker: confirms today's levels are live ("load by default") or says the PMA did not publish. Enable with pma-auto. |
| US session | `alerts.yml` cron → **every 30 min** (`*/30 13-21 * * 1-5`); in-app poller `ALERT_MINUTES` → 30 | code change on this branch | takes effect on release to main |
**Caveat from the task creator:** the three new tasks store **no connectors** (the creating session had none to pass). The READY post and the 18:00 gate need only git, so they work. `pma-auto` needs Gmail (INBOX-CLEAN — declares and continues without it) and a GitHub push path (`git_sync.py` needs a PAT in the environment, or the GitHub connector). **Before enabling pma-auto, recreate it from the claude.ai routines UI with the Gmail + GitHub connectors attached, or confirm `GITHUB_PAT` is in the environment.** The Oct 29 run pushed via the connector.

## End-state daily schedule (PM 2026-11-01 — the design target the tasks above implement)
| SGT | What | State today |
|---|---|---|
| 06:30 | AQE daily run starts (US close is in; no need to wait for 08:30) | task fires 08:30 — move the cron when the PM says |
| on READY | PMA runs automatically (prep → committee → publish); reports progress to the PM **when stuck or done**; **due 14:00** | PM taps `/pma` today; the Checker's READY post exists but is not scheduled |
| by 18:00 | PM approves the PMA; **if he is busy it loads by default** (levels published, alerts armed) | not built: an approval window with a default-load fallback |
| US open | AQE alerts run **every 30 min** | `alerts.yml` runs every 15 min 21:00–05:45 SGT; cadence + content cleanup = backlog 2 |
Build order when the PM says go: (1) move the AQE task to 06:30; (2) schedule the Checker READY post; (3) a `pma-auto` scheduled task that starts the chain on READY and posts progress; (4) the 18:00 approve-or-load gate; (5) alerts cadence 15 → 30 min.

## PM rulings on the weather-spec conflicts (2026-11-01, ~15:30 SGT) — NEXT WORK, in this order
| # | Ruling | Build |
|---|---|---|
| 3 | **Agreed**: update Crown's canon text to say dealer gamma is ON in the daily run — *unless* the gamma read can be sourced from Tiger or the PMA instead of FMP. | Wording fix in the Crown canon/charter now; engineer assesses a Tiger/PMA gamma source as a backlog note. |
| 5 | **Keep Valen's breadth on AQE's panel for now.** Whole-market only if it can run without breaking the FMP Starter plan. | Engineer assessment: call budget for a whole-tape daily scan vs Starter limits; report, don't build. |
| 6 | **Build** the missing Valen items. | Priority: (1) the manage note driven by net new highs, (2) per-position trim/trail rows — both act on the held book; then 3-month 25% count, last-5-trades check, % above 20/50/200, NAAIM, the three risk limits, the drawdown ladder. AQE side (`src/valen/`), additive export fields, Cards Part 1. |
| 7 | **Agreed**: move the Valen parabolic/no-buy text out of every vote row into a risk block beside the verdict. | Record as R37; change `pma_pipeline.py r2digest` (`_valen_lines`) so per-name rows carry setup status + checks only and the warnings print once in a RISK block; Cards show ⛔ beside the verdict; test that no vote row carries the warning text. |
| then | **Complete the multi-agent build** (the end-state schedule above): 06:30 AQE task → scheduled READY post → `pma-auto` chain with progress reports (due 14:00) → 18:00 approve-or-default-load gate → alerts every 30 min. | After 3/5/6/7. Floor test still gates the first live committee. |
**Progress on these (same day):** #3 DONE `4995394c`; #7 DONE `d8d4f070` (R37); #5 assessed below; #6 planned below. Plugin suite 489/0.

### #5 assessment — whole-market Valen breadth on the FMP Starter plan (engineer, 2026-11-01; from code, not run)
- Limits in code: Starter 300 calls/min (`src/data/fmp_client.py:3`), client capped at 250/min, **80/min on the cloud** (the HF Space IP-rate behaviour). No daily request cap is coded; whether Starter has one is **unverified**.
- Today's panel: ~684 scored / 256 on the list; `build_universe()` Pass 1 already pulls the FMP screener + batch quotes at ~1 call per 50 names.
- **Cheap half (feasible):** the batch quote carries each stock's 50-/200-day averages and today's % change, so "% above 50/200" and "today's 4% movers" for ~6,000 US listings cost ~120 batch calls (~2 min at the cloud limit). *To confirm the two average fields against the client's quote parser before relying on it.*
- **Expensive half (not feasible on Starter as coded):** T2108 (40-day), the 20-day, net new highs, and the monthly 25% counts need per-symbol history — ~6,000 single-symbol EOD calls (~75 min at 80/min) every night, or the bulk endpoints FMP gates above Starter. Would roughly double the nightly FMP load and the run time.
- **Recommendation (the PM's ruling stands):** keep breadth on the panel; optionally add the cheap half as *labelled whole-market* rows (population = screener count) so two of Valen's instruments become real. Decision for the PM only if he wants that half.

### #6 build plan — the missing Valen items (PM: "build"; first two act on the held book)
Code sits in `src/valen/` (`management.py` → `held_book_facts`, `daily.py` → `run_playbook` writes `management.held_facts` + `streak`; `card.py` → `management_block`; spec thresholds in `spec.py`; 244 Valen tests across `tests/test_valen*.py`). Every field additive on the export/dashboard; Cards render by code.
1. **Manage note driven by net new highs** — handbook rule: the net-new-highs row alone decides how open trades are managed. Add `management.manage_note` {rule, value, note} from the breadth row; Cards Part 1 block 5 + each held row. Tests: note flips with the row; never a size.
2. **Per-position trim/trail rows** — per held name: entry, live, R multiple (exists in `held_facts`), days held, + handbook trail/trim state (e.g. at +2R trail; after TP1 trim) as *doctrine labels*, never an order. Cards "What it means for your book" gains the two columns.
3. Then: 3-month 25% count; last-5-trades check (from the journal); % above 20/50/200 (panel, labelled); NAAIM (new source — check availability first); the three risk limits (from OPERATING_RULES §A: stop-out gate, per-trade stop distance, beta gate — render, do not decide); drawdown ladder (from the portfolio ledger).
Each item: targeted tests → full suite vs the known-6 baseline → its own commit.

### Resume order after this session (multi-agent build, PM: "once done")
1. #6 items 1–2 (above) → 2. move the AQE task to 06:30 SGT (`update_trigger` on `trig_01EFjk2zPDG1VnzhPyR1GuYt`, cron `30 22 * * 1-5` UTC) → 3. schedule the Checker READY post (fresh session, `daily-check ready`, ~07:05) → 4. `pma-auto`: a scheduled task that starts the chain on READY, posts progress when stuck or done, due 14:00 SGT → 5. the 18:00 approve-or-default-load gate (a one-shot wake that publishes levels unless the PM objected) → 6. alerts cadence 15 → 30 min (`alerts.yml` cron + `scripts/scheduler_daemon.py`), content per backlog 2 → 7. the floor test, which still gates the first live committee.

**State at this note:** everything through `d8d4f070` is pushed; tree clean; plugin 489/0; AQE known baseline 6. If this session is cut, resume at #6 item 1.

## `main` moved under this branch (2026-11-01 13:02 UTC)
The `pma-levels-alerts` session (`session_01JpH6G9mKRHcVAqWcm5fxAD`) merged its branch `claude/password-google-drive-access-GtUhV` into `main` (`77baded8..d6fef9dd`, "ahead 202"; 2,830 commits of that branch's history; one source commit that mattered — the agent spec — and the 1.24.1/1.8.0 vendoring already in our base). A trial merge was clean; `origin/main` is merged into this branch (merge commit, no rewrite). That push also rebuilt the HF Space (source change outside `aegis/output/`). Release of this branch is now a plain merge.

## Backlog recorded 2026-11-01 (PM, end of Session 1)
1. **Crown and Valen reading documents** — neither has a skill/card any more (Crown's seat is stood down; Valen never had one): how the committee and the Cards read `aqe_crown_macro.json` (`the_call`, `scenario`, `read_me_first.what_would_change_it`) and `aqe_valen_dashboard.json` lived in the PM's memory and the old macro cards. **PM to port a handover document**; the engineer then turns it into `docs/` reading guides + a Checker check that both files are served. Until then the Cards' Part 1 and `r2digest --crown` read the fields named in the AQE engineer readout §3(b).
2a. **Weather cards — DONE 2026-11-01.** `aegis-voices/skills/weather-crown` + `weather-valen` (reading cards, not voices) with the PM's extracted spec beside them (`weather_spec_2026-11-01.md`); brief-writer and the WRITE step read them; test pins it. From the spec's own conflict table (§6): #1 MACRO step — already retired (Commit C); #2 lead with `read_me_first` — applied (r2digest --crown, Cards Part 1); #4 VIX percentile inversion — **fixed in `src/macro/crown/explain.py`** ("higher than X% of days", quiet only below the median); #8 sizing — settled at $620. **Still open:** #3 Crown charter says dealer gamma is off in the daily run but the file shows it on (canon text, stale caveat); #5 Valen breadth is panel-only (PM decision on the breadth substrate); #6 missing Valen items (manage note on net new highs, 3-month 25% count, last-5-trades check, % above 20/50/200, NAAIM, trim/trail rows, risk limits, drawdown ladder); #7 the Valen parabolic/no-buy text in every vote row (cited in ~26% of opposes) — proposed move to a risk block beside the verdict, PM ruling; #9 Valen now has an owner: the brief-writer via the card, the Checker for "file served".
2. **AQE alerts content + recurring market-hours alerts** — what exists: `.github/workflows/alerts.yml` cron `*/15 13-21 * * 1-5` (every 15 min, 21:00–05:45 SGT), the in-app poller on the HF Space at the same cadence (`scripts/scheduler_daemon.py` → `src/alerts/engine.py`), ONE digest email per cycle built by `src/alerts/condition_cycle.py` (condition cards off `aegis/output/pma/pma_levels.json`, U&R setups via `live_unr.py` + `live_measures.py`, held-position events, dated `Data:` header) with Drive-synced dedup state. The PM's rulings on card shape are in `CLAUDE.md` (Live alerts). **Target (PM 2026-11-01): every 30 min from the US open**, content cleaned up. The source session (`pma-levels-alerts`, session_01JpH6G9mKRHcVAqWcm5fxAD) was reached; its alert discussion sits weeks back in the transcript (the Oct 23 pages are packet work) — the engineer should scope from `CLAUDE.md` + `src/alerts/` and confirm the content rules with the PM rather than page the whole transcript. — clean up the digest content and the recurring alert cadence during the US session (U&R vs committee lines vs the weekly/daily/1h logic; START_HERE backlog #1). Source material is in the PM's "momentum AQE" sub-session, not in this repo. Engineer item once the PM points at the notes.
3. **Scheduled-task visibility** — verified 2026-11-01 from the account's task list: `AQE daily pipeline trigger` 08:30 SGT Tue–Sat (persistent session; dispatches `daily-run.yml`, verifies the dated output); `AEGIS Daily` 05:30 SGT Tue–Sat (fresh session, `/daily`; trigger-file push removed today); `Income ledger` 05:35 (not Aegis). The 11 exec-review reminders were one-shots bound to the Windows desktop app and the last fired 30/31 Oct — **none are booked for the coming week**. **There is no PMA routine by design** (DECISIONS 1.3: the PM taps `/pma` after READY). Wiring the Checker's READY post as a morning task is Phase 5.
4. Carried: scorecard at each voice's own horizon; the one-dataset query helper (Phase 2); Elder's missing export fields.

## Where the Aegis code lives in this repo
Decision pending in step 1: the plugin tree is vendored under `aegis/` (today only `skills/premarket-analysis/` + `canon/`). Plan: bring the full kernel plugins in under `aegis/plugins/<name>/` as the one truth, and make `aegis/skills/premarket-analysis/tools/pma_pipeline.py` + `contracts/voice_menus.json` thin copies with a drift test.
