# AEGIS — SCHEDULED TASKS (the clock) · Phase 6

**When:** create these ONLY AFTER the dry run (DRYRUN.md) passes. They are the autonomous clock —
until they exist, nothing fires on its own (runs are manual via KICKOFF.md Kickoff B).
**Watch the FIRST firing of each** (shadow) to confirm a scheduled fresh session bootstraps:
plugin loaded, `config/.env` readable, connectors up. That first-fire is the last real unknown.

**Times:** SGT is UTC+8. Cron below is written in **UTC** (confirm your scheduler's timezone;
if it takes SGT directly, use the SGT column). Each task fires a FRESH session that reads the
context, runs its phase, and (post-market) pushes state. Turn **push notifications ON** for each
so completions + failures reach your phone.

| # | Task | SGT | Cron (UTC) | Core? |
|---|---|---|---|---|
| 1 | Premarket build | 15:50 wkdays | `50 7 * * 1-5` | **yes** |
| 2 | Market-hours watch | 21:25 wkdays | `25 13 * * 1-5` | **yes** |
| 3 | Post-market | 04:05 (Tue–Sat) | `5 20 * * 1-5` | **yes** |
| 4 | Design & Review | 05:00 wkdays | `0 21 * * 1-5` | optional |
| 5 | Weekly | Sun 06:00 | `0 22 * * 6` | optional |
| 6 | Nightly janitor | 04:40 daily | `40 20 * * *` | optional |

Start with the three **core** tasks for the pilot; add 4–6 once the core is trusted.

## The prompt for each (paste as the task's instruction)

**1 · Premarket**
> Aegis scheduled premarket. Read `aegis/CONTEXT.md` + the four `aegis/charter/*` files, run `aegis/tools/preflight.py`, then run the premarket process. Produce the Executive Action Plan and notify me for approval by 16:00 SGT. Place NO orders — previews only; autopilot acts only if I have armed it, within its caps.

**2 · Market-hours watch**
> Aegis scheduled market-hours watch. Read `aegis/CONTEXT.md` + charter, run the market_hours process — track distance-to-stop and trails on the held book, page me only on a trigger. Place nothing unless autopilot is armed within its caps.

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
