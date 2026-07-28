---
name: phase_zero
description: Aegis process skill — PHASE 0, the cheap dependency gate (RB:schedule.phase_zero). Runs on its own scheduled task, checks that post-market finished and today's AQE export landed, and only then fires the expensive premarket build. Two file reads, no models, no swarm.
---

# PROCESS: PHASE 0 — the gate before the expensive half (D-83)

**What this is for.** The premarket build spends 12 agent spawns (11 voices + committee-desk). It is only worth spending if post-market's journal is current — otherwise every size, every dynCap number and every held-book read is computed off stale truth. Until now that dependency was a **clock guess**: premarket was scheduled a few hours after post-market, and its freshness check (step 1) ran *inside* the same session that would go on to do the full build anyway. So a stale-data morning still paid to spin up the big session before halting.

This skill is that check, **pulled out and run first, on its own**. It costs two file reads. It is deliberately the cheapest thing in the system.

**Model note (D-16):** control plane — RB:model_tiers.control, and barely that. There is no judgement here. Run one command, read one exit code, take one of three actions. Do not analyse, do not summarise the book, do not read the plan. If you find yourself reasoning, you are in the wrong skill.

## PROCEDURE

1. **Check.** Run `python3 tools/phase_gate.py check --json`. It reports on exactly two things and never guesses at a third: (a) did post-market stamp a clean finish today, and does the journal it claims to have written actually exist and parse — the D-69 discipline of auditing the world, not the kernel's belief about the world; (b) is `output/aqe_daily_export.json` dated today and non-empty.

2. **Branch on the exit code. This is the whole skill.**
   - **0 = READY** → run `python3 tools/phase_gate.py claim --phase premarket_build`. If the claim is **won**, fire the premarket build (`mcp__claude-code-remote__fire_trigger` on the premarket task) and stop. If the claim is **lost**, today's build already fired on an earlier firing of this task — **do nothing, say nothing, exit**. The claim is what makes a repeating schedule safe; never fire without winning it.
   - **1 = NOT_READY** → something that fixes itself with time (post-market hasn't run yet, or AQE hasn't published today's export — AQE is an external box on its own schedule). **Do not page, do not retry in-session, do not fire anything.** Exit quietly; the next scheduled firing (RB:schedule.phase_zero.repeat_minutes) is the retry. **One exception:** if the current time is past RB:schedule.phase_zero.page_after_sgt, the retry budget is spent — PAGE with `tools/notify.py run_fail` carrying the check's own `reasons` verbatim, then exit. The plan is due at 16:00 SGT; paging at 14:30 leaves the PM room to fix AQE or re-run post-market by hand.
   - **2 = BLOCKED** → post-market ran and **failed**, or it claims a journal that is not on disk. Time will not fix this and the next firing will find the same thing. **PAGE immediately** (`tools/notify.py run_fail`) with the check's `reasons` and the manual fix — `/recover post-market` — and **do not fire the build**. Building a plan on a failed post-market is exactly the outcome this gate exists to prevent.

3. **One line out, always.** Whatever happened, close with a plain sentence: what the verdict was, and what you did or didn't fire. On a NOT_READY that is not yet past the page deadline, that line is for the log only — do not push it to the PM's phone. Silence on a quiet check is the point.

## WHAT THIS SKILL MUST NOT DO
Build a universe · pull AQE · spawn any agent · read the book, the plan, the ledger, or the committee record · attempt to fix post-market itself (that is `/recover post-market`, the PM's lever) · fire the build without winning the claim · page on a NOT_READY before the deadline. Every one of those turns the cheapest step in the system back into an expensive one, which is the whole thing this exists to stop.

## ON FAILURE (RB:exceptions; records to data/eod/DATE/exceptions/)
- `phase_gate.py check` itself errors (state file corrupt, unreadable paths) → treat as **BLOCKED**: page, do not fire. A gate that cannot evaluate itself is never an open gate (fail-closed, same rule as the staging-gatekeeper's read refusal).
- `fire_trigger` fails after the claim was won → **release the claim** (`phase_gate.py claim --phase premarket_build --release`) so the next firing can retry, then page. A won claim with no build behind it would silence every remaining firing of the morning.
- Weekend / market holiday → post-market does not run and no export lands, so the check reads NOT_READY all day and pages once at the deadline. That is noise, not a fault; the PM disables or narrows the schedule rather than the skill inventing a trading calendar it has no source for.
