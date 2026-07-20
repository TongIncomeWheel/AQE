# AEGIS INSTALLER — AI-actionable deployment runbook

**Audience: a fresh AI agent in a new, empty workspace** (Claude Cowork or Kimi), given
repository access and the account's connectors. You are the EXECUTOR. This file is your
instruction set. You already have the four things you need:

1. **CONTEXT** — `aegis/CONTEXT.md` + the four charter files (load these FIRST).
2. **INSTRUCTION** — this file (`aegis/INSTALL.md`) + its machine-readable twin `aegis/contracts/install_manifest.json`.
3. **KERNEL** — the `aegis/` tree at the root of the `TongIncomeWheel/AQE` repo (`main`).
4. **ENVIRONMENT** — your shell, `python3`/`node`, and the account connectors (FMP, Tiger, Drive; Alpaca read-only baked in).

> This is a deploy of ONE kernel into a running system. It never "goes live" on its own:
> the end state is **Phase-1** — the PM stages every order by hand — and the overnight
> autopilot is a separate, PM-gated switch reached only after a supervised dry run and a
> shadow week. Nothing in this runbook arms anything.

---

## HOW TO EXECUTE THIS FILE

1. **Load context first.** Read `aegis/CONTEXT.md` and `aegis/charter/{constitution.md|rulebook.yaml|parameters.yaml|decisions_log.md}`. You cannot install what you don't understand — the charter is the source of truth; this runbook is mechanics.
2. **Work phases in order (0→8).** Each step is tagged:
   - `[AI]` — you execute it (a command or tool call). Deterministic; safe to re-run (idempotent).
   - `[PM]` — a human-only gate (a credential, a policy choice, an approval). **STOP, state exactly what you need and why, and wait.** Never guess a secret or a money decision.
   - `CHECK:` — an assertion you MUST verify before advancing. On failure: STOP, report the failing check verbatim, do not proceed.
3. **Track state.** After each phase, write/update `aegis/data/persistent/install_state.json` (see schema in the manifest): `{phase, status, checks:[{name,pass}], notes, ts_from_env}`. This makes the install RESUMABLE — on restart, read it and continue from the first incomplete phase. (Get the timestamp from the environment; do not invent one.)
4. **Never commit a secret.** Tokens/keys live only in gitignored config (Phase 3). If you would write a secret into a tracked file, STOP.
5. **When a phase says "report to PM," surface a short status** (what passed, what's pending, any `[PM]` gate) rather than silently continuing.

---

## PHASE 0 — Preconditions (environment probe) `[AI]`
- Confirm tools: `git --version`, `python3 --version`, `node --version`.
- Confirm Python deps or install: `pip install pyyaml jsonschema pyarrow pandas --break-system-packages` (pyarrow/pandas only needed if you will (re)seed the historical store).
- Confirm connectors are reachable via ToolSearch: FMP, Tiger, Google Drive. Record which are present; a missing connector is a `[PM]` gate later, not a stop now.
- **CHECK:** git + python3 present; at least FMP + Drive connectors resolvable. If not → STOP, report.

## PHASE 1 — Get the kernel `[AI]`
- If the repo isn't already present: `git clone https://github.com/TongIncomeWheel/AQE.git` (public read needs no token). Otherwise `git pull` on `main`.
- Confirm `aegis/` sits at the repo root. Record `git rev-parse --short HEAD`.
- **CHECK:** `aegis/charter/rulebook.yaml` exists AND `aegis/charter/decisions_log.md` contains `D-43` (proves you have the current kernel, not a stale copy).

## PHASE 2 — Build the packages `[AI]`
- `python3 aegis/packaging/build_claude.py` (always). For the Kimi deployment also `python3 aegis/packaging/build_kimi.py`.
- **CHECK:** `aegis/dist/claude-plugin/aegis-v4/` exists and contains `agents/` with exactly the 12 standing agents (10 `voice-*.md` + `committee-desk.md` + `staging-gatekeeper.md`) and `skills/`. Kimi build (if run) must NOT contain `staging-gatekeeper` (D-30 read-only). If the counts differ → STOP.
- **CHECK (D-45):** the self-heal layer shipped — `tools/{notify.py,self_heal.py,ops_status.py}` and `skills/{ops-status,recover}/SKILL.md` are present in the built package, and `contracts/{self_heal,ops_status}.schema.json` too. Note: these are tools/skills, NOT compiled agents — the agent count stays **12** (do not expect 14). If any are missing → STOP.

## PHASE 3 — Config & secrets `[PM]` gates for values, `[AI]` for wiring
- **Fund config** (`aegis/config/aegis_fund.md`): already carries `allocated_capital_usd`, `dyncap_usd`, `brokers`, `ptj_drive_folder_id`. `[AI]` confirm it parses via `python3 aegis/tools/fund_config.py`. If `allocated_capital_usd` is null → `[PM]` gate (BL-030): ask the PM for the allocation; do not size on a null anchor.
- **Secrets** live in a gitignored file — `aegis/config/.env` (copy from `aegis/config/env.example`). Required: `FMP_API_KEY` `[PM]`. The GitHub token for push/pull-of-feed `[PM]` lives here too (or in the host's credential store) — NEVER in a tracked file. Alpaca read-only keys are already embedded per PM ruling.
- **Notification secrets (D-45, optional but recommended)** `[PM]`: for the self-heal phone alerts, set the WhatsApp channel (`WHATSAPP_TOKEN`/`WHATSAPP_PHONE_ID`/`WHATSAPP_TO`, or the `TWILIO_*` alternative) and `WATCHDOG_URL` (an external healthchecks.io/cloud-cron ping URL). All in `aegis/config/.env`. If unset, `notify.py` degrades gracefully to print-only and `/ops` reports the channels as OFF — no crash, just no phone pings.
- **Endpoints** (`aegis/config/endpoints.json`): `tiger_mcp.url` `[PM]` (from the account's Tiger connector) — needed for scheduled/headless runs; interactive sessions may inherit it.
- **CHECK:** `fund_config.allocated_capital()` returns a number; `.env` exists and is gitignored (`git check-ignore aegis/config/.env` returns the path); no secret appears in `git status` staged/tracked files.

## PHASE 4 — Data bridge & shelf `[AI]`
- Verify the historical store: `python3 aegis/tools/historical_store.py` → record `n_tickers` and `date_range`.
- Confirm the field dictionary + contracts load: every `aegis/contracts/*.json` is valid JSON; `aegis/contracts/field_dictionary.json` has entries.
- Pull today's inputs via connectors: the AQE daily export (validate vs `contracts/aqe_export.schema.json`, run `tools/tripwires.py`) and the latest Aegis PTJ from `RB:data_sources.ptj.drive_folder_id` → refresh dynCap: `python3 aegis/tools/dyncap_ledger.py update <ptj.json>`.
- **CHECK:** historical store `n_tickers > 500`; tripwires PASS on today's export; `dyncap_ledger.get_dyncap()` is non-null and its `marked_asof` is today. If the export/PTJ can't be reached → this is the DEPLOY residue (headless connector access): report as a `[PM]`/verify item, do not fake data.

## PHASE 5 — Install as a running workspace `[AI]` package + `[PM]` install (HARD PLATFORM GATE)
- **Claude (Cowork):** `[AI]` zip `aegis/dist/claude-plugin/aegis-v4/` into a `.plugin` file and deliver it to the PM. **STOP HERE — this is not optional.** Plugin installation in Cowork can ONLY be performed from the **desktop app**; a remote/cloud execution container (this runbook's own executor) has no `/mnt/.local-plugins` or `/mnt/.plugins` mount and CANNOT install, enable, or replace a plugin itself, no matter how the CHECK is retried. `[PM]` gate: open the delivered `.plugin` file in the Cowork desktop app and install it — this replaces/supersedes any older `aegis-cic`/prior-version plugin still live on the account. Do not attempt a workaround (writing to a container mount, editing account state directly, etc.) — none exists; wait for the PM.
- **Kimi:** `aegis/packaging/build_kimi.py` output → install skills into the Claw workspace; register the voice subagents from `aegis-agent.yaml`. (Kimi's install path does not carry this desktop-only constraint — confirm before assuming it applies.)
- **CHECK:** a trivial skill loads and both `/fa` (book from state) and `/ops` (system liveness, D-45) render without error, using the NEWLY installed plugin (verify skill/version, not just that *a* plugin responds — a stale prior plugin can mask this check). A first `/ops` will honestly report the notification channels OFF until Phase 6 — that PARTIAL is expected, not a failure.
- If blocked: write `install_state.json` with `status: "blocked_pm"`, `phase: 5`, and `pm_gate` stating exactly this ask, then STOP and report to the PM. Do not mark Phase 5 passed on the strength of packaging alone.

## PHASE 6 — The standing clock `[PM]` (create scheduled tasks)
- Create the scheduled tasks on the app's own scheduler (NOT the in-process cron): premarket build (plan ready 16:00 SGT), market-hours watch session (from ~21:25 SGT), post-market (~04:05), design & review (after post-market), Sunday weekly, nightly janitor. Use the `create_trigger` scheduled-task tool; each fires a fresh session that pulls the repo, runs its phase, and commits.
- **Heartbeat + dead-man's-switch (D-45)** `[PM]`: also create a light heartbeat task that fires `tools/notify.py pre_run` at T-minus `RB:notifications.pre_run_minutes` before each `RB:notifications.key_runs` entry (premarket, ptj, post-market) and checks in with the watchdog (`notify.py --checkin ok`). Register the matching external watchdog (healthchecks.io or a cloud cron) to expect those check-ins so a missed one pages you — this is the only way box-death becomes an alarm rather than silence. **CHECK addendum:** `list_triggers` shows the heartbeat task, and a manual `notify.py --checkin ok` turns the external watchdog green. **Copy-paste setup:** `aegis/NOTIFICATIONS_SETUP.md` walks the whole thing (WhatsApp/Twilio, healthchecks.io, `.env`, the two Windows batch files + `schtasks` lines) in ~20 minutes.
- This is a `[PM]` gate because it commits the account to a recurring cadence and (for headless firings) may need the packaged `.mcp.json`/Tiger URL fallback — confirm with the PM before creating.
- **CHECK:** `list_triggers` shows the created tasks with the intended cron/next-run.

## PHASE 7 — Smoke test / UAT `[AI]` supervised
- One SUPERVISED end-to-end premarket: run the `premarket` skill against today's data → confirm a schema-valid plan (`contracts/plan.schema.json`) with all 10 nomination files present, `committee.json` written, sizing + gates computed against the live dynCap, and the daily flow audit renders (`tools/daily_flow_audit.py DATE --render`).
- Forced-failure checks: a tripwire block STANDS DOWN the phase and pages; the gatekeeper REFUSES a dummy request missing consensus and logs it.
- **Self-heal layer UAT (D-45):** `/ops` renders the liveness card; `notify.py run_fail --dry-run` renders and its failure page is visibly distinct from a green ping; with the channel set, one live `notify.py pre_run` arrives on the phone; `self_heal.py <loop> --failure ptj_pull --dry-run` reports **healed** (transient) while `--failure tripwire` reports **stand_down / not healed** (gate — never auto-healed); `notify.py --checkin ok` turns the external watchdog green; and a paused watchdog check pages the PM (proves box-death is caught). Confirm NONE of `/heal /recover /repull /reseed` can place an order — a recovered loop reaching execution still stops at a gatekeeper preview.
- **CHECK:** the DEPLOY.md §C acceptance checklist passes item by item AND the self-heal UAT above passes each item. Record results into `install_state.json`. Any FAIL → STOP, report.

## PHASE 8 — Go-live gating `[PM]` — NOT automated
- Shadow/practice week: the system runs on the clock but the PM hand-stages every order; build trust in the plans.
- Only after that, on a night the PM chooses, `/arm` — within the caps (RB:autopilot: ≤1R/order, ≤3/session, auto-off on any breach, fixed 05:30 SGT expiry, PM-approved preauthorised names only). One deployment armed at a time, ever.
- **This runbook STOPS here. Arming is the PM's decision, never the installer's.**

---

## KICKOFF PROMPT (what the PM pastes into a fresh workspace)
> "This workspace is a new Aegis deployment. Clone/pull `TongIncomeWheel/AQE`, then read
> `aegis/CONTEXT.md` and the charter, then execute `aegis/INSTALL.md` phase by phase. Run
> every CHECK, write `install_state.json` as you go, and STOP at every `[PM]` gate and ask me.
> Do not arm anything."

## FAILURE / ROLLBACK
- A `[AI]` step failing a CHECK: STOP that phase, report the exact failing check; the shelf/config are additive so re-running after a fix is safe.
- A build produces the wrong agent set: delete `aegis/dist/` and rebuild (generated, never hand-edited).
- Never proceed past a red CHECK by loosening it — a CHECK is the contract that the phase actually worked.
