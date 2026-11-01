---
name: daily-check
description: The CHECKER (operating model E1, PM 2026-10-30) — proves the chain actually ran, by someone who did not do the work. READY check (aqe_last_run.json dated today, status success) before the PM taps /pma; chain proof after a run (every step ticked, forms present, floor caps held, slate <= 15, levels dated, spend under the ceiling). Read-only. Prints "Healthy" or exactly what broke. Never fixes, never trades, never re-runs.
---
# DAILY-CHECK — did the chain really run?

**Job:** one line in chat the PM can trust: `Healthy` or `what broke`. A green tick is never proof; the dated
output file is. **Owner agent:** the Checker — a fresh session or agent that did NOT do the work it checks.
**Tools:** `check.py` beside this file. Read-only: it opens files and prints; it changes nothing.

## When it runs (operating model §8, target triggers)
| Moment | Command | Proves |
|---|---|---|
| Morning, after the AQE run (~09:00 SGT) | `check.py ready --last-run aegis/output/aqe_last_run.json` | AQE finished TODAY with `status: success` — the READY post. `partial` = export current but a tail step failed; the post says so |
| After `/pma` publishes | `check.py chain --run-dir aegis/output/pma/run/<date> --date <date> --levels aegis/output/pma/pma_levels.json` | every RUN.yaml step ticked done/degraded; consensus + record + slate present and dated; floor-check ok; slate <= 15; levels for today; spend <= ceiling |
| Evening | both | nothing silently stale for tomorrow |

`check.py data --output-dir aegis/output` — **the AQE → voices HANDOFF GATE** (PM 2026-11-01: never run the committee on data nobody checked): export dated to the run, no null core fields, held book LIVE, lens ranking present, candidate set inside the export and carrying every held name, one packet per decider (7) each non-empty, every packet ticker inside the candidate set, no PM-only field, no stray packet, Crown + Valen dated to the run, generated runtime copies not drifted. READY means run finished **and** this gate Healthy.
`check.py all --last-run … --output-dir … --run-dir … --date … --levels …` runs ready + data + chain and prints one line each.

## What "Healthy" means (every line must hold)
1. `aqe_last_run.json`: `date_sgt == today (SGT)` and `status == "success"`.
2. `run_manifest.json`: every step named in RUN.yaml is `done` or `degraded` (degraded is listed, never hidden); none `pending` / `in_flight` / `failed`.
3. `consensus.json` present, every row carries `status` (AGREED / CONTESTED / DROPPED / NOT_SLATED) — the R34 count ran, not the retired rule.
4. `committee_record.json` present with one row per decider present per room name (R35).
5. `slate.json`: `len(tickets) <= 15` (R34). `floor_check.json`: `ok: true` (R36 caps).
6. `pma_levels.json` carries today's run (`date` / `run_date` == date).
7. Spend: the manifest's estimated tokens `<= ceiling` (default 1.5 × 905k = 1,357,500; PM design default). Over = reported to the PM; it is the one thing the Checker tells him unprompted.

## What it never does
Fix a file · re-run a step · touch a broker · edit a form · judge a verdict · guess a missing field (a missing
file is a FAIL line, never "probably fine").

## Seeded-failure proof
`tests/test_pipeline.py::test_the_checker_catches_a_seeded_failure` feeds it a stale `aqe_last_run.json`, a manifest
with VOTE still pending, a 16-ticket slate and an over-ceiling spend, and asserts each is named. A checker that has
never failed has proven nothing.
