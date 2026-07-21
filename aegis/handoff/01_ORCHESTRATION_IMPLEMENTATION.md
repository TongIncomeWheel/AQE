# AEGIS — ORCHESTRATION & AUTOMATION: THE IMPLEMENTATION LAYER
**How the automation actually runs · 21 Jul 2026**

This is the implementation-layer design — the wiring beneath the process skills. It describes what
literally executes, in what order, where state lives, and where the automation is solid vs. where it
depends on a runtime capability the current harness does not provide. Read `00_MASTER_CONSOLIDATION.md`
first for the what; this is the how.

---

## 1. THE EXECUTION MODEL (today, on Claude Cowork)

Each scheduled loop is a **cron trigger** that fires a **fresh, ephemeral session** in the cloud.
That session has NO inherited workspace, NO `config/.env`, and NO usable git credential. So every
scheduled prompt begins with a **STEP 0 self-bootstrap** (D-64) before any phase logic:

```
STEP 0 — BOOTSTRAP (before the phase)
  export AEGIS_PAT=<inline PAT>                 # the only channel a fresh container can read
  git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
  write /home/claude/AQE/aegis/config/.env      # GITHUB_PAT=...
  cd /home/claude/AQE ; pin git committer
  verify aegis/CONTEXT.md exists  → else page + STOP (never run on a half-built workspace)
STEP 1 — MCP warm-up (Tiger often needs one ToolSearch retry before it is up)
STEP 2 — run the phase (read CONTEXT + charter, run the skill)
STEP 3 — git push state; emit run outcome; CLOSE WITH A REAL CHAT MESSAGE (D-75)
```

`tools/bootstrap.py` encodes this contract and carries NO token (D-49 — the PAT travels only inline
in the trigger prompt). This is the single most important reliability fix in the system: without it,
scheduled sessions died silently (the original "post-market didn't run" failure).

---

## 2. THE LOOP CADENCE (live schedule, D-74)

| # | Loop | SGT | Cron (UTC) | Mechanism | Notes |
|---|---|---|---|---|---|
| 1 | Premarket | 10:00 wkdays | `0 2 * * 1-5` | cron + bootstrap | 11-voice swarm + committee |
| 2 | Market-hours liveness | 21:25 wkdays | `25 13 * * 1-5` | cron + bootstrap → self-rearm | arms the intraday /loop |
| 3 | Post-market | 05:05 (Tue–Sat effective) | `5 21 * * 1-5` | cron + bootstrap | DST-proofed at 05:05, never needs seasonal change |
| 4 | Design & Review | 08:00 (Tue–Sat) | `0 0 * * 2-6` | cron + bootstrap | results at start of PM's day |
| 5 | Weekly + janitor | Sun 06:00 | `0 22 * * 6` | cron + bootstrap | param review + hygiene |

**The intraday loop.** Market-hours is NOT a 30-min cron (that was retired). A single liveness
trigger fires at 21:25 SGT, confirms the alert engine is alive, sweeps the inbox once, then calls
`ScheduleWakeup(+30min)` to re-fire *itself* — a self-perpetuating in-session loop that runs to the
04:00 SGT close, then stops. Each wake reads the mechanical alert universe (see §4) and pages only on
actionable held-book risk or a pod-confirmed runner.

**Immutability caveat.** Cron trigger *prompts are immutable* (`prompt_update_disabled`). Any prompt
change = delete + recreate the trigger. This is why prompts carry a version suffix (v2, v3).

---

## 3. THE DATA FLOW (one full day, end to end)

```
NIGHT (AQE engine, deterministic)                  ~08:30 SGT: AQE pipeline runs (~14 min)
   AQE computes analytics → aqe_daily_export.json → Google Drive folder "AQE"

PREMARKET 10:00 SGT (fresh session, bootstrap)
   pull export from Drive (bounded retry D-70) → output/aqe_daily_export.json
   universe_screen.py           → data/sod/DATE/universe.json  (+ near_misses)
   spawn 11 voices (isolated)   → data/sod/DATE/nominations/*.json
   tally + quality_flags + board→ data/sod/DATE/{tally,quality_flags,subscore_board}.json
   event filter                 → data/sod/DATE/event_filter.json
   committee-desk (isolated)    → data/sod/DATE/committee.json
   plan assembly + sizing       → data/sod/DATE/plan.json  (status: DRAFT)
   git push (post-market does the durable push; premarket pushes SOD shelf)

PM APPROVAL by 21:00 SGT        → approved names + held book → intraday alert universe

MARKET HOURS 21:30–04:00 SGT (liveness cron → self-rearming /loop)
   alert_universe.py casting mat → data/alerts/DATE/alert_universe.json (the tiered watch set)
   AQE alert engine writes inbox → data/alerts/DATE/inbox.jsonl (every 15 min, scoped to the mat)
   sweep (alert_inbox.py) → held-book risk pages + pod on survivors → pages only on actionable CONFIRM

POST-MARKET 05:05 SGT (fresh session, bootstrap)
   reconcile fills (both brokers) → data/journal/aegis_journal_DATE.json (validated vs contract)
   PTJ to Drive (D-67)            → aegis_trade_journal_DATE_PTJ.json
   metrics, archive_ledger (D-68), scorecard, voice_memory, trailing recompute
   audits: usage/completeness + drive_ptj_check (D-69) + daily_flow_audit (flight recorder)
   git_sync.py → commit + push the whole day's state to GitHub (the durable source of truth)
```

**The invariant:** every artifact is a validated JSON file on the shelf, and **git is the source of
truth.** Any session — scheduled or interactive, on any harness — reconstitutes full state by
reading the shelf. Nothing important lives in chat memory (G3).

---

## 4. THE ALERT UNIVERSE WIRING (the mechanical casting mat, D-77)

The intraday feed is scoped by `tools/alert_universe.py` — deterministic, thresholds in
`parameters.yaml → alert_universe`. It reads the AQE export, counts 8 detection lanes per name, and
emits a tiered watch set (Tier 1 priority / Tier 2 confirmed / Tier 3 watch), striking event-driven
names. Each fired alert carries `lane_count + lanes_fired` into the pod, which reads the same numbers
the voices read to judge runner-or-not. Full recipe + the 2-day derivation: `03_LONGLIST_ALERT_UNIVERSE.md`.

This is the clean separation the PM insisted on: **the universe is a formula (mechanical, wide,
tunable); the committee/pod evaluates what fires (judgment).** The committee does NOT pre-pick the
universe.

---

## 5. STATE & MEMORY (where persistence actually lives)

| State | Where | Lifetime | Notes |
|---|---|---|---|
| Book of record | git + Drive PTJ | permanent | journal, closed-trades archive with YTD/QTD/MTD rollups |
| SOD shelf | `data/sod/DATE/` in git | permanent | universe, nominations, tally, committee, plan |
| EOD shelf | `data/eod/DATE/` in git | permanent | audits, scorecard, flow-audit flight recorder |
| Voice memory | `voice_memory.py` state in git | rolling | per-voice stats vs targets, open picks, standing lessons w/ expiry — injected at each spawn |
| dynCap ledger | `data/persistent/dyncap_ledger.json` | rolling | mark-to-market equity; de-sizes in drawdown |
| Historical store | `data/historical/` | ~6y | per-name daily bars for the store-reconcile self-heal (D-40) |
| Decisions log | `charter/decisions_log.md` | permanent | D-1..D-77 governance memory |

**What is NOT persistent today:** a live *conversation/interaction* state. Each scheduled session's
transcript is its own throwaway thread; there is no durable interactive thread that accumulates the
PM's steering across days. This is the core runtime gap — see §7 and `02_RUNTIME_INFRA_REQUIREMENTS.md`.

---

## 6. FAILURE & SELF-HEAL (the exception ladder)

One ladder governs every failure (`tools/self_heal.py`, D-45), classified into four policies:

- **transient** (feed_pull, ptj_pull, store_stale) → bounded retry / reseed, heal silently, else escalate.
- **structural** (schema, config, logic) → no auto-fix; escalate with the exact manual command.
- **gate** (tripwire, hard-gate breach) → STAND DOWN + page; never auto-healed; PM override only.
- **capacity** (usage_limit, D-72) → NOT retried (would re-hit the ceiling); escalate with "wait for
  reset, then rerun" — this is the Claude Max session/weekly cap detector.

Doctrine: order-blind (self-heal may re-run READ/COMPUTE/PLAN, never place/size/arm); bounded +
logged (`data/eod/DATE/self_heal_DATE.jsonl`); declare on exhaustion, never fabricate. Independent
assurance: `drive_ptj_check.py` (D-69) verifies Drive actually shows the file (not just that the
kernel believed it wrote it); `daily_flow_audit.py` reconstructs which hierarchy layers fired (a grey
"not run" layer is itself the signal).

**Notification / delivery (the honest state).** `notify.py` emits run_ok/run_fail; the scheduled
task's push is built from the session's *final chat message* (D-75), not the tool's stdout. This
works for the run *executing*; whether the push reliably reaches the PM's device is the unresolved
delivery question (undocumented mobile behaviour) — the reason for the runtime sourcing exercise.

---

## 7. THE ORCHESTRATION GAP → WHAT THE IMPLEMENTATION LAYER STILL NEEDS

The automation is solid on **compute and persistence**: loops fire, bootstrap, run, validate, and
push durable state to git. It is missing exactly one layer — a **persistent interactive runtime**:

1. **No always-on / resumable agent process.** Cron spawns fresh sessions; there is no long-lived
   process holding conversational state that the PM attaches to and steers, and that autonomous
   loops deliver into.
2. **No session-binding for autonomous output.** Scheduled output cannot be routed into one fixed
   interactive thread — each fire is isolated (confirmed against Anthropic docs).
3. **No two-way durable surface.** Artifacts/dashboards are display-only; the interactive surface
   (a chat) is finite and fragments across days.

The kernel is built to survive this move: harness-neutral (D-15), git-as-truth, deterministic tools,
compiled agent cards. The implementation layer that must be sourced/built on the target runtime is
specified in `02_RUNTIME_INFRA_REQUIREMENTS.md`.
