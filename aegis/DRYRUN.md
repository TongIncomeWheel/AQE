# AEGIS — DRY-RUN TEST PACK (D-50)

> **NO ORDERS. NOTHING ARMS.** Every execution step stops at a gatekeeper *preview*.
> Autopilot stays OFF the entire time. This proves the machinery end-to-end without
> touching a live order. Run it inside the **installed aegis-v4 session**.

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

## STOP / ROLLBACK
- Any Part-A `FAIL` → fix that line, re-run Part A.
- A `/pm` run that tries to place an order → **stop immediately and report** — that is a law-1 breach and must not happen.
- A connector down → note it, continue if it's IBKR (Tiger primary); stop if it's Drive or FMP (core data).

## KICKOFF PROMPT (paste into the fresh installed session)
> "This is the Aegis dry run. Load CONTEXT.md + charter, run `aegis/tools/preflight.py` then
> `aegis/tools/dryrun.py` and show me the result. Then run Parts B and C of `aegis/DRYRUN.md`
> step by step, reporting PASS/FAIL each. Place NO orders — previews only. Autopilot stays OFF."

---
*Order-blind by construction. Autopilot is never armed during a dry run. This pack tests that the system RUNS and that it REFUSES to trade on its own — both are the point.*
