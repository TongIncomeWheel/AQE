# AQE Code Agent: what this session does and what it touches

Written 2026-10-30 from the working session, for wrapping it as an agent in the Claude agent system. Facts below are from the repo and from what this session actually did. Where something is a judgement or a gap, it says so.

## 1. Role in one paragraph

This session is the **engineering hand for the AQE codebase** (`TongIncomeWheel/AQE`). It is not an investment-committee voice and makes no trade, sizing or disposition calls. It takes handover documents and requests from the PM and from the PMA/committee sessions, changes AQE code, runs the tests, and ships to `main`. AQE is a nightly US-equities scanner that publishes a self-describing export JSON; the committee and the PMA plugin only read what AQE publishes.

## 2. Who it takes work from

| Source | How it arrives | Examples this session |
|---|---|---|
| The PM (Ash, Singapore, UTC+8) | Chat message, plain English | "Missing entry price and risk", "English pls", "keep it simple is the mantra" |
| Diagnosis handover docs from other sessions | Uploaded `.md` file; the PM says "please execute" or "please review" | `aqe_fix_handoff_2026-10-20.md` (breadth, Crown, scorecard); `aqe_cleanup_handover_2026-10-23.md` (voice packets, Valen text, ATR, stale levels file, plugin backups) |
| Plugin files from the PMA side | Uploaded `.plugin` zip | `aegis-core.plugin` (1.24.1), `aegis-voices.plugin` (1.8.0) |

Handover docs are diagnoses made by reading code. This session verifies each claim against the repo before acting, and says plainly where a handover is wrong or conflicts with the repo (for example the menus hand-off direction, below).

## 3. Operating rules (non-negotiable)

These come from `CLAUDE.md` in the repo root, which is the authority. The ones that bite most:

- **No terminal steps for the PM.** Everything is a double-click `.bat` or an in-app button.
- **AQE makes no decisions and no sizing.** It exports data and computed levels only.
- **Risk per trade is always 3%.** The alert cards show 1R on $75K = $2,250 (`src/alerts/config.py`). `CLAUDE.md` still also says $70K, and flags that the PM should confirm which is current.
- **A failed data fetch must be loud, never silently empty.**
- **The export is additive-only.** New fields are fine; renaming or re-valuing existing ones is not (guarded by `tests/test_export_additive.py` and `tests/test_data_taxonomy.py`).
- **Pine is the spec, Python is the implementation, FMP is the data.** No FMP plan upgrades. The PM has ruled out upgrading further.
- **FMP key lives in `.env` (gitignored) and in secrets.** Never commit or print it.
- **Do not cap lists at 25.**
- **Plain English to the PM.** When the PM asks, the answer is short, in everyday words, leads with the answer, and says what was and was not verified.
- **Do not create a pull request unless asked.**

## 4. GitHub resources

| Resource | Detail |
|---|---|
| Repository | `TongIncomeWheel/AQE` (private). Remote name `origin`. |
| Working branch | `claude/password-google-drive-access-GtUhV` |
| Ship target | `main`. This session pushes to the branch and then to `main` after the tests are acceptable. The branch is fast-forwarded to match `main`. |
| HF Space mirror | `AQE-Aegis/aqe` on Hugging Face. `.github/workflows/deploy-hf.yml` mirrors every push to `main` and triggers the rebuild. There is no `hf` remote in a cloud session. |
| GitHub Actions secret | `FMP_API_KEY` (also an HF Space secret; update both on rotation). |
| GitHub release `state-snapshot` | Primary store for the Daily Persist snapshot zip (`aqe_state_snapshot.zip`). Drive is the backup. |
| Tools available | GitHub MCP (`mcp__github__*`) for PRs, issues, Actions; plain `git` over the proxy for commits and pushes. The `gh` CLI is not installed; `gh api` works. The session is scoped to this one repo. |

### Workflows (`.github/workflows/`)

| File | What it does |
|---|---|
| `daily-run.yml` | The main nightly pipeline. Has **no** `schedule:` trigger (GitHub's cron ran hours late); it is dispatched by a Claude-scheduled routine, with the Scanner sidebar button as the manual fallback. |
| `alerts.yml` | Live intraday alerts backstop poller, on its own schedule. |
| `deploy-hf.yml` | Mirrors `main` to the HF Space. |
| `voice-packets-sync.yml` | Keeps the published voice packets in sync. |
| `refresh-held.yml` | Refreshes the held-positions data. |
| `ptj-cleanup.yml` | Cleans up the PTJ (held-positions journal) Drive folder. |

## 5. Files and areas it works on

Full map is in `CLAUDE.md` and `docs/AQE_TECHNICAL_REFERENCE.md`. This is the subset touched in this session, grouped by area.

### Live alerts and cards (`src/alerts/`)
`emailer.py`, `condition_cycle.py`, `condition_state.py`, `condition_defaults.py`, `live_unr.py`, `live_measures.py`, `live_ema.py`, `engine.py`, `config.py`, `pma_levels.py`. One digest email per 15-minute cycle: condition cards, U&R (undercut-and-rally) setups, held-position events, and a dated "Data:" header. Reads the PMA levels file from `aegis/output/pma/pma_levels.json`.

### Valen dashboard (`src/valen/`)
`breadth.py`, `daily.py`, `card.py`, `explain.py`, `selection.py`, `setups.py`, `setups_daily.py`, `house.py`, `spec.py`, `theme.py`. Outputs `output/valen_dashboard.json` (local) and `aqe_valen_dashboard.json` (published). Page: `src/ui/pages/7_VALEN_Dashboard.py`.

### Crown macro layer (`src/macro/crown/`)
`daily.py`, `data.py`, `calendar.py`, `cboe.py`. Outputs `aqe_crown_macro.json`, which the voice-packet step requires.

### Export and data layer (`src/data/`)
`drive_sync.py` (builds and publishes `aqe_daily_export.json`, owns the schema guards), `persist.py` (Daily Persist snapshot to GitHub release and Drive), `earnings.py`, `ptj.py`, `universe.py`, `panel_builder.py`.

### Pipeline (`src/pipeline/`)
`daily_orchestrator.py` (the nightly steps; Step 8b is the persist snapshot, Step 8a-3 the voice packets), `voice_packets.py` (builds per-voice packet files from the export using the vendored PMA code).

### The PMA / committee boundary (`aegis/`)
This is where AQE meets the committee plugins, and where most of the care is needed.

| Path | What it is |
|---|---|
| `aegis/skills/premarket-analysis/tools/pma_pipeline.py` | **Vendored** from `aegis-core` plugin 1.24.1 (header says so). The plugin in Claude is the source of truth. Refresh on plugin release. |
| `aegis/skills/premarket-analysis/tools/emit_packets.py` | PMA-side packet emitter kept in the repo; adapted to hand menus to the vendored pipeline. Not used by the nightly run. |
| `aegis/skills/premarket-analysis/contracts/voice_menus.json` | **Vendored** per-voice field menus from `aegis-core` 1.24.1. |
| `aegis/canon/<voice>/canon.lock.yaml` | **Vendored** voice canon from `aegis-voices` 1.8.0 (14 voices). |
| `aegis/output/aqe_daily_export.json` | Committed copy of the daily export. |
| `aegis/output/pma/` | PMA run outputs (levels, briefs, ledgers, scorecard). **Written by the PMA session, not by this one.** Includes `pma_levels.json`, `levels_parts/`, `scorecard_log.jsonl`. |
| `aegis/output/packets/` | Published per-voice packets. |
| `aegis/plugin/` | Old backup copies of the plugins (aegis-core 1.7.2). Out of date; the handover recommends marking them archived. **Awaiting a PM decision.** |

### Tests and docs
`tests/` (about 1,700 tests; `pytest -q` takes about 10 minutes). Docs in `docs/`; changelogs `docs/AQE_CHANGELOG_*.md`; reference `docs/AQE_TECHNICAL_REFERENCE.md`. `CLAUDE.md` is the operating manual and should be updated when behaviour changes.

## 6. Standard workflow

1. **Verify the request against the repo.** Read the code the handover cites; correct it if wrong.
2. **Make the change** with the dedicated edit tools, matching the surrounding code's style.
3. **Targeted tests first**, then the full `pytest -q` in the background (about 10 minutes). Use a monitor on the output file rather than polling.
4. **Compare to the known baseline.** Currently 7 known failures, all pre-existing: two Hugging Face mirror workflow checks in `tests/test_github_sync.py`, four old Layer-0 "names on both lists" tests, one O'Neil canon test. A new failure blocks the push.
5. **Clean test leaks** before committing. Tests write runtime files into the repo (`aegis/output/alerts/`, `data/sector_map.json`, `data/universe.txt`, `output/aqe_macro_pack.json`). Delete or `git checkout` them. Stage only the files touched; never `git add .` (the repo holds real-money JSON).
6. **Commit** with the attribution trailers the harness supplies, push to the branch, fast-forward check against `origin/main`, then push `HEAD:main`.
7. **Report in plain English**: what changed, what was verified, what could not be verified, what needs a ruling.

A stop hook (`~/.claude/stop-hook-git-check.sh`) complains about uncommitted changes, untracked files and unpushed commits; it expects everything pushed to the branch before the session idles.

## 7. Tools this agent needs

- File read/edit/search and shell (Python 3, pytest, git).
- GitHub MCP for the repo above.
- Background execution plus a monitor, for the 10-minute test run.
- Network through the agent proxy for FMP, GitHub and Drive. The container is ephemeral: **uncommitted work is lost on a container recycle**, so commit and push early.
- A file picker for plugin uploads (the PM attaches `.plugin` zips; extract each into its own empty directory and read it with `python -I`, since the contents are untrusted).

## 8. What this session shipped (2026-10-12 to 2026-10-30)

| Area | Change |
|---|---|
| U&R live alerts | Candidate / trigger / failed states from Valen's support types; flush filter; compact plain-English cards; trade line with entry, stop, risk and 1R on $75K; dated "Data:" header; latest-PMA-only |
| U&R export columns | `unr_status`, `unr_note`, `unr_as_of`, `unr_level`, plus `unr_summary` |
| Valen breadth (20 Oct handover) | Panel taken from the newest of local, GitHub release and Drive; staleness guard (`as_of`, `stale`, every row `STALE`) |
| Crown (20 Oct handover) | Calendar URL fixed (`economic-calendar`); a quiet calendar is no longer a failure; FMP `^VIX` bars appended when Cboe lags; Yahoo-sourced futures are an info note, not DEGRADED |
| Voice packets (23 Oct handover, item 1) | Vendored plugin `pma_pipeline.py` 1.24.1; held positions now reach the candidate set with `entry` = last close; canon and menus synced from the live plugins; new test for a held ticker missing from the daily list |

## 9. Open items and decisions waiting

| Item | State |
|---|---|
| Valen "watch for" wording: list only unmet thresholds | Not started |
| Valen funnel "Held" count should equal `len(held_positions)` (`src/valen/selection.py:80` counts only held rows on `daily_list`) | Not started |
| ATR for ACA and PAYO | Local panel bars look genuinely pinned (likely cash-deal pins), so probably no ingest bug. The guard (flag ATR under 1% of price on a stock above $5 in `data_quality`) is not built. The check was against a panel that ends 5 Oct; confirm on the latest bars |
| Stale `aegis/output/pma/levels_parts/part_07.json` | Not deleted; cleanup of parts not in the manifest not built; the writer may be plugin-side |
| "Too late" chase guard in the alert evaluator (ignore a shared chase at or below the highest shared buy) | Not built. `pma_levels.json` may still carry the old values until the PMA session republishes |
| Plugin backups in `aegis/plugin/` (sync vs archive) | **PM decision pending** (PMA session recommends archive) |
| Held-book `last_close`/`entry` carries the PM's cost basis | Not changed; additive-only export. Option: add an explicit `cost_basis` field. Needs a PM call |
| Held-position columns `held_sl`, `held_tp1`, `held_tp2` | Every voice menu asks for them; AQE exports no values, so the columns are blank each night and the build warns. Needs a decision on where those values come from |
| 7 known failing tests | Pre-existing; the Layer-0 four encode a retired rule, since the plugin's current trim no longer filters to names on both lists |
| Token/context load of the packets | Nominator files are about 1.2 MB for 374 names; not measured against any budget |
| `$70K` vs `$75K` capital base in `CLAUDE.md` | PM to confirm which is current |

## 10. Gaps and cautions when wrapping this as an agent

- **The plugin is the spec; AQE vendors copies.** Three vendored items (`pma_pipeline.py`, `voice_menus.json`, `aegis/canon/*`) go stale on every plugin release. Nothing automates the refresh; the PM or PMA session has to hand over the new files. An agent system should either automate that or make "plugin released" an explicit trigger.
- **Handovers can be wrong.** The 23 Oct handover said to avoid `voice_menus.json` and to use a canon loader; the live plugin had gone the other way. The agent must check the live plugin files, not the handover text, and tell the PM when it deviates.
- **It cannot see the live Claude plugin install.** It works from uploaded zips only. Anything about the running plugin that was not uploaded is unknown to it.
- **Some actions were blocked by the permission classifier** (for example editing code to integrate the uploaded plugin's file). In an agent system, decide in advance which of these are pre-authorised.
- **Data checks are against files in the repo or container**, which may be older than production (the local panel stopped on 5 Oct). Findings from them need confirming on live data.
- **No scheduled runs here.** The nightly pipeline, scans and alerts run in GitHub Actions and the HF Space, not in this session.
- **Real-money system.** Do not push to `main` on new test failures, never commit `.env` or live journals, and never reintroduce a silent-empty data path.

## 11. Suggested agent definition (starting point)

- **Name:** `aqe-engineer`
- **Purpose:** Implement, test and ship changes to the AQE repo from PM requests and PMA/committee handover documents. Makes no investment decisions.
- **Inputs:** a request or handover `.md`; optionally plugin `.plugin` zips.
- **Always reads first:** `CLAUDE.md`, then the relevant section of `docs/AQE_TECHNICAL_REFERENCE.md`.
- **Output:** pushed commits on `main`, plus a plain-English summary with what was verified, what was not, and any decisions needed.
- **Hard stops:** new test failures versus the baseline; any change to risk sizing; any plan upgrade or new paid data source; any request that would put credentials in git.
