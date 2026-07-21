---
name: cockpit
description: The RESULTS-DELIVERY cockpit (D-76) — makes every autonomous loop's output appear in the session the PM is actually looking at, instead of dying invisibly in a fresh scheduled session. Triggers on "/cockpit", "/cockpit arm", "/cockpit status". Read-only display layer; places/sizes/arms NOTHING (constitution law 1). Reuses tools/ops_status.py, tools/status.py, tools/daily_flow_audit.py — never re-implements them.
---

# /cockpit — put the output where the PM is looking

## The problem this exists to solve (PM, repeatedly, wk of 14–21 Jul)
"Kinda stupid agents do their work with no visible output." Every Aegis loop
(premarket, post-market, D&R, market-hours) fires as a **scheduled trigger**,
which by platform design starts a **brand-new ephemeral session the PM views
independently** — and on mobile those scheduled-task sessions **are not surfaced
yet**, and the push notification did not reliably arrive. So the work completed
(git proves it) but the PM saw nothing. Patching the notification text (D-75) did
not fix this: a fresh session cannot post into the chat the PM is reading. The
ONLY mechanism that delivers into the PM's live session is `send_later` (a
self-bound Routine → this session). This skill packages that into the kernel so
it survives session death — the whole point of the PM's ask: "pack this into the
kernel, so when this session ends or gets full it's repeatable in the next
session."

## The model (decoupled — this is the anti-spaghetti core)
- **Compute stays durable, server-side, unchanged.** The cron triggers
  (premarket 10:00 / D&R 08:00 / post-market 05:05 / market-hours 21:25 SGT) still
  do the real work in fresh bootstrapped sessions and PUSH results to git (D-64).
  No work is ever lost, even if no cockpit is open — it lands in the repo.
- **Visibility is a separate, lightweight render loop.** A cockpit session is any
  live chat the PM has open that has run `/cockpit arm`. It does NOT recompute —
  it PULLS the freshest state from git and RENDERS it here, via the existing
  read-only cards (`/ops`, `/status`, the flow-audit HTML). Cheap, deterministic,
  no swarm, no model spend on judgment.
- **Delivery = `send_later` into THIS session.** On arm, the cockpit schedules a
  `send_later` a few minutes AFTER each cron loop is expected to have pushed, so
  when it fires back into this session the fresh result is already in git to show.

## `/cockpit arm` — procedure (run in ANY session to make IT the cockpit)
1. **Render now.** Immediately pull latest (`git -C <repo> pull --ff-only`), then
   render the current picture here: `tools/ops_status.py <today>` (the machine
   card) + the `/status` book card (that skill reads today's shelf) +
   `tools/morning_summary.py <data_dir> <today>` when a plan/journal exists — and
   note the newest artifact per loop (premarket plan, post-market journal, D&R
   proposals) with its git timestamp, so the PM sees live state the instant they
   arm, not just a promise.
2. **Arm the day's remaining deliveries.** For each loop whose cron fires later
   today (SGT), schedule ONE `send_later` into this session, timed a safe margin
   after the cron completes+pushes:
   - post-market  cron 05:05 → deliver **05:25 SGT**
   - design&review cron 08:00 → deliver **08:20 SGT**
   - premarket    cron 10:00 → deliver **10:40 SGT** (swarm can run long; a
     re-spawn day pushed ~11:11 once — the delivery re-checks freshness, see 4)
   - market-hours: the 21:25 liveness + its 30-min self-rearm already speak in
     their own fresh sessions; the cockpit delivers a **single 04:10 SGT** wrap of
     the night's alert activity rather than 30-min chatter here.
   The `send_later` message body must instruct the fired turn to: pull git →
   check the loop's artifact is dated today → render the matching card HERE as the
   reply → **re-arm tomorrow's same delivery** (the loop self-perpetuates, like the
   market_hours ScheduleWakeup pattern, so one arm sustains indefinitely).
3. **Record the arm.** Write `data/cockpit/armed.json` (session-agnostic marker:
   date armed, the delivery times scheduled, "cockpit is live"). This is how a
   later session or `/cockpit status` knows whether delivery is currently covered.
4. **Freshness guard on each delivery.** When a delivery fires, if the loop's
   artifact is NOT yet dated today (cron ran long or failed), do NOT render stale
   data — say so plainly ("post-market hasn't pushed yet, re-checking in 15 min"),
   arm a short follow-up `send_later`, and let the durable cron/self-heal own the
   actual failure. The cockpit never masks a missing run as a present one.

## `/cockpit status` — is delivery currently covered?
Read `data/cockpit/armed.json`. Report: is a cockpit armed, for what date, which
deliveries are pending today, and — honestly — the standing limitation below.

## THE HONEST LIMITATION (state it every time, do not bury it)
A `send_later` is bound to the session that created it. It survives that session
**compacting / "getting full"** (same session id — delivery continues). It does
NOT survive the session being truly **closed/replaced by a brand-new chat** — the
binding dies with the old session. There is no API to inject into a session that
does not exist yet. So the durable contract is:
- **Within a session:** fully autonomous and self-perpetuating once armed. Proven.
- **Across a NEW session:** the PM (or the first Aegis command in that new chat)
  runs `/cockpit arm` ONCE to re-establish delivery. Because compute+git are
  durable, the new cockpit shows the correct current state the instant it arms —
  nothing was lost in the gap, it was just briefly unseen.
- **Backstop:** the durable cron triggers remain the safety net — they run and
  push regardless of whether any cockpit is open, so a dead cockpit degrades
  visibility, never the work. `/ops` in any fresh session always reads true state
  from git (it never trusts chat memory).

CONTEXT.md Part-load note: a fresh Aegis session should surface "cockpit not armed
— run `/cockpit arm` to get live delivery here" so the re-arm is self-advertising,
not tribal knowledge.

## Doctrine
- **Reuse, not clone.** Renders come from `ops_status.py`/`status.py`/
  `daily_flow_audit.py`. This skill adds only the delivery loop, no new render code.
- **Display only (law 1).** It pulls and shows. It never places, sizes, arms, or
  mutates the book. A cockpit that reaches an order-shaped item still only routes a
  REQUEST to the staging-gatekeeper like any orchestrator.
- **Fail-visible (law 3).** A missing/stale artifact is shown as missing, never
  rendered as if fresh.
