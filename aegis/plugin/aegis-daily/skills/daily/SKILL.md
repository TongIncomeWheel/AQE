---
name: daily
description: "AEGIS DAILY — the one scheduled command. Three stages, in order, every trading day: (1) close the book — pull Tiger, run the PTJ batch for real, push the journal to GitHub; (2) print the trade journal on screen and prove the file AQE reads is on GitHub main; (3) trigger the AQE daily run and watch it to completion, paging the PM on failure and never retrying on its own. Deterministic tools only. No voices, no committee, no orders."
model: sonnet  # sonnet [RB:model_tiers.control] — PINNED, not inherited (D-92). packaging/build_claude.py hard-fails the build if this literal ever drifts from charter/parameters.yaml.
---

# DAILY — close the book, show it, hand it to AQE

**Three stages. Always in this order. One command runs all three without stopping to ask.** It stops only to page.

| Stage | What it does | Done when |
|---|---|---|
| **1 — Close** | Pull Tiger, run the PTJ batch for real, push the journal to GitHub (`skills/ptj/SKILL.md`, MODE C — that file is the only copy of the procedure; do not restate it here). | `post_market` gate stamped and the journal is on GitHub main. |
| **2 — Show** | Print the trade journal on screen as tables, and read the journal back from GitHub main to prove AQE can see it. | The PM has the book in front of him and the file is confirmed on `main`. |
| **3 — Trigger AQE** | Push the trigger file that fires `daily-run.yml`, then watch `aegis/output/aqe_last_run.json` until AQE reports today's run finished. | AQE's marker shows `status: success` for today — or the PM has been paged with exactly why not. |

**Order-blind (constitution law 1).** Nothing here places, sizes or arms an order. **Data plane only (law 4).** Every step is a deterministic tool call plus GitHub reads/writes. No judgment-tier agent is ever spawned by this skill. If you want a voice's opinion you are in the wrong command — that is `/pma`, later, after this has finished.

---

## Stage 0 — Workspace and date (every run, no memory assumed)

1. **Fresh checkout.** A scheduled session starts empty. `git clone https://github.com/TongIncomeWheel/AQE.git` to a fresh path and `cd aegis/`. Never trust a stale prior clone — the journal and the gate file live in git and are pushed back to git; a stale clone is how yesterday's book gets re-closed.
2. **Stamp the clock.** Run `date` live for SGT and US Eastern. Never assert a date from memory.
3. **Pick the journal date.** Read `data/persistent/phase_state.json` and `ls data/journal/`. `DATE` is the next US trading day after the most recent journal already processed (skip weekends and any date in `data/persistent/market_holidays.json` if that file exists). If more than one trading day is missing, run all three stages for each missing date, oldest first — do not skip a day to catch up.
4. **Is today a run day for AQE?** AQE's pipeline skips when it is Sunday or Monday in SGT (US market was shut). Note this now; Stage 3 needs it.

---

## Stage 1 — Close the book

Open `skills/ptj/SKILL.md` and run **MODE C** end to end for `DATE`: the Tiger pull (Step 1), the batch (`bash scripts/run_post_market.sh DATE`, Step 2), and the mandatory GitHub-connector push-and-verify that file's D-110/D-111 section spells out. Nothing about the pull, the batch, or the push is repeated here — that file is the one copy.

Then read its result:

| PTJ MODE C ended | Do this |
|---|---|
| exit 0 — gate stamped `ok` | Say one line: "Book closed and pushed." Go to Stage 2. |
| exit 1 — degraded, gate stamped `partial` | Go to Stage 2. Carry every degraded line into the Stage 2 print, verbatim. |
| exit 2 — halted | **Stop.** Do not run Stage 2 or 3. Page with what failed, verbatim. The lever is `/recover post-market`. |
| D-100 halt (a position vanished with no matching fill) | `get_transactions(symbol=TICKER)` for each vanished name, append the missing close to `tiger_filled_orders.json` with a `d100_recovery_note`, re-run Stage 1. |

Aegis membership is automatic (D-106): any equity fill not already on the membership file and not on the exclusions file is auto-included and flagged `auto_included_unrecognized`. You do not decide membership and you do not ask — you report every such flag by name in Stage 2. The PM's only lever is `held_book_refresh.py reject` afterward.

---

## Stage 2 — Show the book, prove AQE can see it

**Print, do not send a file.** Render `skills/ptj/SKILL.md` Step 3's print spec on screen, as markdown tables, in this order: held book · overnight (opened / closed with realised P&L / stops that moved — say "nothing changed overnight" plainly if empty) · the day · realised P&L MTD / WTD / YTD · open risk (with any `unknown_stop` name called out) · capital (dynCap, 1R, gross exposure, leverage, **book beta**, **book exposure**, 1-month VaR — beta and exposure on their own line) · anything not clean (every `auto_included_unrecognized` name, every `pending_review` option leg, `no_live_stop`, `entry_date_unknown`, stop MISMATCH, any D-100 recovery). Then one plain closing line: what the book is worth, what is at risk, anything needing a decision.

**Then prove the handoff, do not assume it.** AQE reads the PTJ journal straight from git (`aegis/data/journal/` — D-84), so "picked up by AQE" means one thing: the file is on `main`. Read `aegis/data/journal/aegis_journal_DATE.json` back from GitHub `main` via the connector (`get_file_contents`), `json.loads()` it, and confirm its date field is `DATE` and it parses. Print one line: "Journal for DATE confirmed on GitHub main (commit SHA)." If it is not there, Stage 1's push did not land — go back and finish D-110's push-and-verify; do not start Stage 3 on a journal AQE cannot see.

---

## Stage 3 — Trigger the AQE daily run and watch it land

**Why a file push, not a dispatch call (D-113).** This session cannot call the GitHub Actions API: the connector has no `workflow_dispatch` tool, and direct `api.github.com` calls are refused by the sandbox proxy. `daily-run.yml` therefore also fires on a **push to one dedicated file**, path-filtered so nothing else on `main` can trigger it. Pushing that file IS the dispatch. If a future connector exposes `workflow_dispatch` and run-status tools, switch this stage to them and keep the same completion contract below — nothing else changes.

1. **Sunday or Monday in SGT?** AQE's pipeline skips those days (US market was shut). Say "AQE does not run today (Sun/Mon SGT) — Stage 3 skipped" and go to the closing report. Do not push the trigger and do not wait for a marker that will not change.
2. **Already done today?** Read `aegis/output/aqe_last_run.json` from GitHub `main`. If `date_sgt` is today's SGT date and `status` is `success`, say so with its `finished_at`, and go to the closing report. Nothing to trigger.
3. **Push the trigger.** Via the connector (`push_files` to `main`), write `aegis/triggers/aqe_daily_run.json`:
   ```json
   {"requested_at_utc": "<now, ISO-8601>", "journal_date": "DATE", "requested_by": "aegis-daily /daily stage 3", "note": "push to this path fires .github/workflows/daily-run.yml (D-113)"}
   ```
   Commit message: `aegis-daily: trigger AQE daily run for DATE`. Record the commit SHA. This carries no `force`, so AQE's own Sun/Mon and already-ran-today checks still apply.
4. **Watch the marker, not the clock.** Every 3–5 minutes, read `aegis/output/aqe_last_run.json` from `main` again. The pipeline writes this file itself when it finishes, success or failure. A full run legitimately takes 20–35 minutes against FMP's rate limits — an unchanged marker at minute 20 is not stuck. Keep watching for up to **45 minutes** from the trigger commit.
   - **`date_sgt` = today and `status` = `success`** → note `finished_at` and `exported_at` in the closing report. No page.
   - **`date_sgt` = today and `status` ≠ `success`** → page the PM now with: the status, the `tail` / `reason` field verbatim (that is the job log's last lines — the pipeline publishes them into the marker on failure), the trigger commit SHA, and the Actions page `https://github.com/TongIncomeWheel/AQE/actions/workflows/daily-run.yml`. **Do not re-push the trigger. Do not retry.** A real failure needs a human look, not a blind re-run.
   - **45 minutes and the marker still shows a prior date** → page the PM with the same details and "no completion marker after 45 minutes — run still in progress, never started, or the trigger did not fire". Do not retry.
5. **A page is a chat message, not a file, and not a tool's draft** (D-75). Say it in the closing report and, if `tools/notify.py` is configured, also `tools/notify.py run_fail --loop daily --step "AQE daily run"`.

---

## Closing report — the whole thing, on screen, every run

State plainly which `DATE`(s) were processed, then the Stage 2 tables, then three status lines:

| | |
|---|---|
| **Book** | closed / degraded (which lines) / halted — and the `post_market` gate status as stamped |
| **GitHub** | journal for DATE confirmed on `main` (commit SHA) — or not, and why |
| **AQE** | success at HH:MM SGT / failed (tail quoted) / no marker after 45 min / skipped (Sun-Mon) / already done today |

Then one line: "`/premarket` (data prep) and `/pma` are now unblocked" — only if AQE reported success. Otherwise say what is blocking them.

**Never report a stage as done that you did not see finish.** A trigger you pushed is not a run that succeeded; a marker you did not read is not a status you know. The same discipline as D-111: an honest "couldn't confirm" beats a fabricated pass every time.

---

## What this skill must not do

Spawn a voice, the committee desk, or any judgment-tier agent · run `/premarket`'s AQE-export pull or coverage checks (those consume the export this skill's Stage 3 produces — they run later, from `/premarket`, once AQE has finished) · re-dispatch or retry a failed AQE run · place, stage, or modify a broker order · restate the broker pull or the batch here instead of calling `skills/ptj/SKILL.md` MODE C · report success it has not read back from GitHub.
