# AEGIS — SCHEDULED TASKS (the clock) · Phase 6

**When:** create these ONLY AFTER the dry run (DRYRUN.md) passes. They are the autonomous clock —
until they exist, nothing fires on its own (runs are manual via KICKOFF.md Kickoff B).
**Watch the FIRST firing of each** (shadow) to confirm a scheduled fresh session bootstraps:
plugin loaded, `config/.env` readable, connectors up. That first-fire is the last real unknown.

> **RESOLVED — D-64 (21 Jul 2026): a fresh scheduled session does NOT inherit the workspace.**
> A live fired-session diagnostic proved a scheduled task starts a BRAND-NEW ephemeral container
> that has the aegis-v4 plugin + all MCP connectors (FMP/Tiger/IBKR/Drive) but **NOT**
> `/home/claude/aegis`, **NOT** `config/.env`, and **NO** usable git token (env `GH_TOKEN` is a
> `proxy-injected` sentinel). So every prompt below MUST begin with a **STEP 0 bootstrap** that
> reconstructs the workspace before the phase, or the session dies silently (no commit, no page).
> The bootstrap: `export AEGIS_PAT=<pat>` → clone `TongIncomeWheel/AQE` to `/home/claude/AQE` →
> write `aegis/config/.env` → `cd` in → verify `aegis/CONTEXT.md` → page + STOP on failure.
> `tools/bootstrap.py` encodes this contract (carries NO token — D-49; the PAT travels inline in
> the trigger prompt, the only channel a fresh container can read). Tiger MCP may need a ToolSearch
> retry before it is up. Trigger prompts are immutable (`prompt_update_disabled`) — to change one,
> recreate the trigger (v2).

**Times:** SGT is UTC+8. Cron below is written in **UTC** (confirm your scheduler's timezone;
if it takes SGT directly, use the SGT column). Each task fires a FRESH session that reads the
context, runs its phase, and (post-market) pushes state. Turn **push notifications ON** for each
so completions + failures reach your phone.

**LIVE SCHEDULE (as set 21 Jul 2026 — PM cadence; supersedes the pilot times below).**
All fresh-session cron jobs carry the D-64 STEP 0 bootstrap. Intraday is an in-session /loop, NOT cron.

| # | Task | SGT | Cron (UTC) | Engine | Status |
|---|---|---|---|---|---|
| 6 | Janitor (hygiene) | 03:50 wkdays | `50 19 * * 1-5` | cron + bootstrap | **LIVE** — just before post-market |
| 3 | Post-market | 04:05 (Tue–Sat) | `5 20 * * 1-5` | cron + bootstrap | **LIVE** |
| 4 | Design & Review | 08:00 (Tue–Sat) | `0 0 * * 2-6` | cron + bootstrap | **LIVE** — results at start of PM's day |
| 1 | Premarket build (swarm) | 10:00 wkdays | `0 2 * * 1-5` | cron + bootstrap | **LIVE** — 11 voices + committee |
| 2 | Intraday AQE sweep | mkt hours, 30 min | — (in-session) | **/loop** (ScheduleWakeup) | **LIVE** — no bootstrap needed |
| 5 | Weekly param review | Sun | `0 22 * * 6` | cron + bootstrap | not set up (optional) |

Daily SGT order: janitor 03:50 → post-market 04:05 → design&review 08:00 → premarket 10:00 → (US open 21:30, /loop sweeps 30-min) → your 21:00 approval of the premarket plan.
The old pilot times (premarket 15:50, watch 21:25, D&R 05:00, janitor 04:40) are RETIRED. 2B (hourly market-watch cron) removed — the /loop replaces it.

## The prompt for each (paste as the task's instruction)

**1 · Premarket**
> Aegis scheduled premarket. Read `aegis/CONTEXT.md` + the four `aegis/charter/*` files, run `aegis/tools/preflight.py`, then run the premarket process. Produce the Executive Action Plan and notify me for approval by 16:00 SGT. Place NO orders — previews only; autopilot acts only if I have armed it, within its caps.

**2 · Market-hours watch**
> Aegis scheduled market-hours watch. Read `aegis/CONTEXT.md` + charter, run the market_hours process. Alerts arrive via the INBOX not email (D-62): AQE writes `aegis/data/alerts/DATE/inbox.jsonl` every 15 min scoped to today's strong-momentum universe. Sweep it with `tools/alert_inbox.py` — held-book stop/approach alerts page me immediately; opportunity survivors go to the 3-lens pod and page me ONLY on a CONFIRM that clears the concentration gate; the rest is logged, not podded. Track distance-to-stop and trails on the held book. Place nothing unless autopilot is armed within its caps.

> **Scheduler vs poll (tightening — no slop):** this scheduled task is the *session liveness + bootstrap* fire (one wake at 21:25 SGT to confirm the alert engine is alive and the book is loaded — the 21:25 liveness check in `market_hours`). It is NOT the intraday clock. The **30-min full-universe polling is the AQE alert engine's job** (repo, runs on the always-on box per D-9), which *wakes* a session on a trigger. So: scheduler = liveness heartbeat + wake-on-trigger host; AQE engine = the 30-min poll. Do not add timed AI polling loops (RB:market_watch_mode) — that duplicates the engine and burns tokens.

**3 · Post-market**
> Aegis scheduled post-market. Read `aegis/CONTEXT.md` + charter, run `aegis/tools/preflight.py`, run the post_market process (journal, metrics, audit, flow audit), then run `aegis/tools/git_sync.py` to commit + push state. Notify me with the summary. Place nothing.

**4 · Design & Review**
> Aegis scheduled design & review. Read `aegis/CONTEXT.md` + charter, run the design_review process; land any change proposals in the STEER file for my approval. Change nothing without my nod.

**5 · Weekly**
> Aegis scheduled weekly. Read `aegis/CONTEXT.md` + charter, run the weekly process (parameter/criteria review, AQE contract review, historical-layer maintenance). Proposals to STEER; change nothing without my nod.

**6 · Nightly janitor**
> Aegis scheduled janitor. Read `aegis/CONTEXT.md` + charter, run `aegis/tools/janitor.py` (shelf hygiene, disk guard), then `aegis/tools/git_sync.py`. Notify only on an exception.

## Verify
After creating: the Scheduled sidebar (or `list_triggers`) shows the tasks with their next-run times.
On each task's FIRST fire, confirm the phone push arrived and `/ops` shows that loop as run.
