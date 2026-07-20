# AEGIS — DRY-RUN TEST PACK (D-50)

> **NO ORDERS. NOTHING ARMS.** Every execution step stops at a gatekeeper *preview*.
> Autopilot stays OFF the entire time.
>
> **This tests the WHOLE agentic system running itself — the scheduled clock included (Part E),
> not just a hand-triggered run.** It is safe to let the schedulers fire during the dry run
> precisely because the system is order-blind: an autonomous run can build a plan, notify, and
> persist, but it cannot trade. So the manual trigger (Part C) proves the *logic*, and the
> scheduled firing (Part E) proves the *automation* — both are the point. Run it inside the
> **installed aegis-v4 session**.

## Before you start (2 checks)
- [ ] **Old `aegis-cic` plugin is DISABLED** (only `aegis-v4` + `cowork-plugin-management` enabled). Two plugins collide.
- [ ] Connectors enabled in this chat: **FMP, Google Drive, Tiger, IBKR**. (Notifications are Cowork-native — nothing to set.)

---

## PART A — Deterministic core (one command)
Run:
```
python3 aegis/tools/dryrun.py
```
**PASS =** `ALL GREEN ✓` (kernel current, contracts valid, fund_config, historical store, GITHUB_PAT present, git push auth reachable, /ops renders, notify cowork-native, self-heal doctrine).
If any line is `FAIL`, stop and fix that one thing (the line says what) before Part B.

---

## PART B — Connectivity (the last-12-hours pain point; fail-visible)
Ask the session to run each and report back. Each is READ-only.
- [ ] **Drive read** — list the PTJ folder; confirm the latest `aegis_trade_journal_YYYY-MM-DD_PTJ.json` is visible.
- [ ] **Drive write** — `git_sync`/`/ptj` path already proven; skip unless you want a fresh write.
- [ ] **FMP** — pull a quote for `SPY`; confirm a price returns.
- [ ] **Tiger** — `get_stock_positions`; confirm the Aegis book returns.
- [ ] **IBKR** — `get_account_positions`; confirm it returns (IBKR has been intermittent — if it errors, note it; Tiger is primary for the book).

**PASS =** Drive + FMP + at least one broker (Tiger) return live data. A dead IBKR is a *noted* amber, not a stop — the kernel is built to degrade on one broker.

---

## PART C — The agentic flow (supervised, still no orders)
- [ ] **`/ops`** → liveness card renders; alert channel shows **cowork-native**.
- [ ] **`/status`** → book cockpit renders (12 open positions, dynCap).
- [ ] **`/pm`** (premarket) → let it run the full pass. Verify at the end:
  - a schema-valid plan (`data/sod/DATE/plan_*.json`),
  - **10 nomination files** present (the voice swarm actually spawned),
  - `committee.json` written,
  - sizing + gates computed against the **live dynCap**,
  - the flow audit renders (`/ops --render` or `daily_flow_audit.py DATE --render`).
  - **It must STOP at previews / plan-for-approval — nothing stages.**
- [ ] **Gatekeeper refusal** — ask it to stage a name that has NO committee consensus. Expect a **REFUSAL**, logged; `/killed` shows it. (Proves law 1 holds.)
- [ ] **`/fa`** → quick book view renders.

**PASS =** the plan is produced with all 10 voices + committee + risk gates, and the gatekeeper refuses the no-consensus stage. Any order attempt should be impossible.

---

## PART D — Persistence (proves the autonomous loop closes)
- [ ] The `/pm` and post-market runs write to `data/sod|eod/DATE/` **and** push via `tools/git_sync.py` (state lands on GitHub `main`).
- [ ] The book of record is on **Google Drive** (PTJ).

**PASS =** state is committed to GitHub (check the repo shows a new commit) AND the PTJ is on Drive — the loop persists with no human credential step.

---

## PART E — The autonomous clock (the real system test)
This is the part that proves the *automation*, not just the flow. It is safe because nothing here can place an order.
- [ ] **Create the 3 core scheduled tasks** from `SCHEDULERS.md` (premarket, market-watch, post-market), push notifications ON.
- [ ] **One-off test fire (watch it now):** create a `run_once_at` task ~10 min out with the premarket prompt, so you don't wait until 15:50 SGT. Then WATCH a *scheduled fresh session* do the whole thing on its own:
  - the task fires → a fresh session starts,
  - it bootstraps (reads CONTEXT + charter, runs preflight),
  - it runs premarket (10 voices, committee, risk, gates),
  - it produces the plan and **pushes a notification to your phone**,
  - it persists (git push + Drive), and **stops at previews — no order**.
- [ ] **Verify from your phone:** the completion push arrived; `/ops` shows that loop as *run*; the repo shows a new commit; the plan is in `data/sod/DATE/`.

**PASS =** a task you did NOT trigger by hand fired a fresh session that bootstrapped, ran the full premarket, notified you, and persisted — with zero orders. That is the autonomous system working end to end. A grey/again-not-run loop in `/ops`, a missing phone push, or a scheduled session that failed to bootstrap (couldn't read `config/.env` / connectors) is the exact failure this part exists to catch — before it matters.

## STOP / ROLLBACK
- Any Part-A `FAIL` → fix that line, re-run Part A.
- A `/pm` run that tries to place an order → **stop immediately and report** — that is a law-1 breach and must not happen.
- A connector down → note it, continue if it's IBKR (Tiger primary); stop if it's Drive or FMP (core data).

## KICKOFF PROMPT (paste into the fresh installed session)
> "This is the Aegis dry run. Load CONTEXT.md + charter, run `aegis/tools/preflight.py` then
> `aegis/tools/dryrun.py` and show me the result. Then run Parts B, C, D and E of `aegis/DRYRUN.md`
> step by step, reporting PASS/FAIL each — Part E includes creating the scheduled tasks and a
> one-off test fire so we watch the autonomous clock run a premarket on its own. Place NO orders —
> previews only. Autopilot stays OFF."

---
*Order-blind by construction. Autopilot is never armed during a dry run. This pack tests that the system RUNS and that it REFUSES to trade on its own — both are the point.*
