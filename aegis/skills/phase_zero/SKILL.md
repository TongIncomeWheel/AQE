---
name: phase_zero
description: Aegis process skill — PHASE 0, the cheap dependency gate in front of premarket (RB:schedule.phase_zero). Decides which of premarket's two halves is next — the cheap data half or the expensive judgement half — and fires only that one. One command, one exit code, no models, no swarm.
---

# PROCESS: PHASE 0 — the gate in front of premarket (D-83, split-aware D-91)

**What this is for.** The premarket judgement half spends 12 agent spawns (11 voices + committee-desk). It is only worth spending if the data underneath it is real: post-market's journal current, today's AQE export fetched and proven complete. Until D-83 that dependency was a **clock guess** — premarket was scheduled a few hours after post-market and checked freshness *inside* the same session that would go on to do the full build anyway, so a stale-data morning still paid to spin up the big session before halting.

This skill is that check, **pulled out and run first, on its own**. It costs one command. It is deliberately the cheapest thing in the system.

**What changed at D-91.** Premarket is now **two processes**, not one:

| | `premarket_data` (cheap) | `premarket` / premarket_build (expensive) |
|---|---|---|
| Does | fetches the export, proves it complete + fresh, builds the universe, refreshes held book / stops / dynCap / metrics, pushes, stamps | swarm, tally, funnel, deliberation, plan, PM approval |
| Spawns | nothing | 11 voices + committee-desk |
| Needs | post-market stamped ok | post-market **and** today's export on disk **and** an ok `premarket_data` stamp for today |

So Phase 0's question is no longer *"is it ready?"* but **"which of the two is next?"** — and it must ask the gate about the right one, because the two gates give different answers on the same disk state by design. The data half is the process that FETCHES the export, so it is deliberately **not** gated on the export existing; gating it that way was a deadlock in which nothing could ever fetch anything.

**Model note (D-16):** control plane — RB:model_tiers.control, and barely that. There is no judgement here. Run a command, read an exit code, take one action. Do not analyse, do not summarise the book, do not read the plan. If you find yourself reasoning, you are in the wrong skill.

**Nothing here is scheduled.** No task exists for Phase 0, for the data half, or for the build. RB:schedule.phase_zero describes the cadence this *would* run at; every run today is started by hand. Where this skill says "the next firing is the retry," that means the next time a human runs it. Never write or say otherwise.

## PROCEDURE

1. **Ask about the data half first.** Run `python3 tools/phase_gate.py check --for premarket_data --json`. That gate reports on one thing and never guesses at a second: did post-market stamp a clean finish today, and does the journal it claims to have written actually exist and parse — the D-69 discipline of auditing the world, not the kernel's belief about the world. **It does not check the export, on purpose:** the process it is gating is the one that downloads the export.

2. **Branch on that exit code.**
   - **1 = NOT_READY** → post-market has not run yet. Time fixes this. **Do not page, do not retry in-session, do not fire anything.** Exit quietly; the next run of this skill (RB:schedule.phase_zero.repeat_minutes) is the retry. **One exception:** past RB:schedule.phase_zero.page_after_sgt the retry budget is spent — PAGE with `tools/notify.py run_fail` carrying the check's own `reasons` verbatim, then exit.
   - **2 = BLOCKED** → post-market ran and **failed**, or claims a journal that is not on disk. Time will not fix it and the next run finds the same thing. **PAGE immediately** with the check's `reasons` and the manual fix — `/recover post-market` — and fire nothing. A morning built on a failed post-market is exactly what this gate exists to prevent.
   - **0 = READY** → the data half is startable. Go to step 3.

3. **Has the data half already run today?** Read the `premarket_data` stamp out of the same `check` output you already have (`upstream` is populated when you ask about the build; ask about the build now — `python3 tools/phase_gate.py check --for premarket_build --json` — and read its `upstream` field rather than re-deriving anything from disk).
   - **No stamp for today** → the data half is what is next. Claim it: `python3 tools/phase_gate.py claim --phase premarket_data`. If the claim is **won**, fire the data half and stop. If the claim is **lost**, it already fired on an earlier run — **do nothing, say nothing, exit**. The claim is what makes a repeating gate safe; never fire without winning it.
     **Firing it, honestly:** RB:schedule.phase_zero.fires_data_trigger_id is `null` — no scheduled task for the data half has ever been created, so there is nothing to fire. While that key is null, this branch does not pretend: it **releases the claim** (`claim --phase premarket_data --release`) and closes with one line telling the PM the data half is ready to run and needs to be started by hand. Do not invent a trigger, do not create one, and do not report a fire that did not happen.
   - **Stamped `fail` today** → the data half tried and could not produce the data. **PAGE** with its note verbatim and the fix (`re-run premarket_data`), and **do not fire the build**. Spending eleven judgment-tier voices on absent data is the single outcome the split exists to prevent. Never treat this as retry-later.
   - **Stamped `ok` today** → go to step 4.

4. **Ask about the build half, then branch the same way.** You already have the `--for premarket_build` result from step 3. Read its exit code.
   - **0 = READY** → claim it: `python3 tools/phase_gate.py claim --phase premarket_build`. If **won**, fire the build — `mcp__claude-code-remote__fire_trigger` on **RB:schedule.phase_zero.fires_trigger_id**. Fire that recorded target, never a new session started by hand: there is one build path and this skill only decides *when* it runs. **If that task is not enabled** — and as of this writing none of them are — do not fabricate a fire: release the claim, and close with one line saying the build is ready and needs starting by hand. If **lost**, today's build already fired; do nothing, exit.
   - **1 = NOT_READY** → the export is late even though the data half stamped ok, which is unusual enough to read the `reasons` rather than assume. Same quiet-retry / page-after-deadline rule as step 2.
   - **2 = BLOCKED** → PAGE, fire nothing.

5. **One line out, always.** Whatever happened, close with a plain sentence: which half was next, what the verdict was, and what you did or did not start. On a NOT_READY that is not yet past the page deadline, that line is for the log only — do not push it to the PM's phone. Silence on a quiet check is the point.

## WHAT THIS SKILL MUST NOT DO
Build a universe · pull AQE · refresh the held book · spawn any agent · read the book, the plan, the ledger, or the committee record · attempt to fix post-market itself (that is `/recover post-market`, the PM's lever) · **run `check` without `--for`** (it would silently take the data half's weaker gate and could green-light the build on an export nobody fetched) · fire anything without winning the claim · **report a fire when the target task does not exist** · create a scheduled task to make any of this run on its own · page on a NOT_READY before the deadline. Every one of those turns the cheapest step in the system back into an expensive one, which is the whole thing this exists to stop.

## ON FAILURE (RB:exceptions; records to data/eod/DATE/exceptions/)
- `phase_gate.py check` itself errors (state file corrupt, unreadable paths, an unrecognised `--for`) → treat as **BLOCKED**: page, fire nothing. A gate that cannot evaluate itself is never an open gate (fail-closed, same rule as the staging-gatekeeper's read refusal). An unknown `--for` is a hard stop by design and never falls back to the permissive gate.
- A fire fails after the claim was won → **release the claim** (`phase_gate.py claim --phase <that phase> --release`) so the next run can retry, then page. A won claim with no process behind it would silence every remaining run of the morning.
- **One firing authority.** If a fixed-time task for either half is ever created, it must be OFF while Phase 0 owns the firing. Two ways to start the same half gives the morning a path that runs on whatever state exists — the exact thing this gate was built to stop. (The claim latch stops Phase 0 double-firing itself; it does not know about a task firing behind its back.)
- Weekend / market holiday → post-market does not run and no export lands, so the check reads NOT_READY all day and pages once at the deadline. That is noise, not a fault; the PM narrows the cadence rather than the skill inventing a trading calendar it has no source for.
