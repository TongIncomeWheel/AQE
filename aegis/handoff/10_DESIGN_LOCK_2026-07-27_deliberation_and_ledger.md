# Design Lock — Live Deliberation Gate + Pipeline Ledger (2026-07-27)

**Status:** LOCKED from PM interview (this session). Phase 2 of the agentic-system redesign
(Phase 1 = the backend-vs-PM-interactive audit, `handoff/09_...md`). Not yet built.

**PM's governing goal (verbatim intent):** a highly automated daily process, context-tight,
where the ONLY thing the PM concentrates on and deliberates hard is trade selection with the
committee — with real discussion and challenge, not a report to rubber-stamp. Everything else
should run itself.

---

## What changes vs today

Today: premarket runs fully automated end-to-end (universe → swarm → committee → plan), and
the PM's only touchpoint is approving or rejecting the finished plan at step 11. The committee's
deliberation (step 9) is one isolated agent spawn, invisible to the PM, producing a static
verdict file.

**New shape: premarket splits into two halves.**

### Half 1 — AUTO BUILD (unattended, unchanged from today)
Universe build → AQE pull/validate → held-book/hedge math → the 11-voice swarm → tally →
event filter → weather → conviction-funnel shortlist → **committee's FIRST PASS** (still one
spawn per name/sleeve, still produces the structured case + dissent + mandatory bear case).
Runs on schedule, silent, exactly as audited in Phase 1. No PM presence required. Not "ready by
4pm" anymore in a hard sense — ready whenever the PM chooses to open it.

### Half 2 — LIVE DELIBERATION GATE (new — requires the PM present)
The PM opens a session against the day's shortlist + first-pass committee reports. Per name,
PM's choice (confirmed in interview):
- **Fast path (default):** read the structured report (case, dissent, bear case, data anchors)
  and approve/reject — no extra agent spend beyond the background first pass already done.
- **Grill path (PM's call, per name):** open a live challenge — the PM questions the committee's
  case directly, gets real pushback, before deciding. Mechanically: **continue the SAME
  committee-desk agent spawn** (via the Agent-continuation mechanism this harness already
  supports — resume by agent ID, not a stateless re-spawn) so the PM's challenge lands in the
  same context that produced the verdict, and the committee can revise its read live rather than
  restate itself from zero.

The plan is not finalized until this live half completes — approval (today's step 11) is no
longer a separate late-day gate, it's the natural end of the same live session. This merges
today's step 9 (deliberation) and step 11 (approval) into one continuous PM-paced session.

### Everything that doesn't advance → the Ledger, not dropped
A name the committee didn't advance today no longer just disappears into the watch table.
Per the interview: **the PM does not classify it live** (keeps the deliberation session focused
purely on trade selection, per the stated goal) — **post-market sorts it** at close-out, using a
mechanical default (e.g., DATA_LED/mechanically-strong → `daily_reconsider`; consensus-only/weak
→ `trigger_silent` with a condition; genuinely dead → drop, logged not deleted). The PM sees and
can override the day's classifications the next time they open premarket — a glance, not a task.

---

## The Pipeline Ledger (new persistent store)

Distinct from the existing outcome-tracking Nomination Ledger (day-1/3/5/10/15 hit-rate
tracking) — this is a **lifecycle store for ideas that haven't fired yet**. Proposed shape,
`data/persistent/pipeline_ledger.json`, one row per idea:

```
{ ticker, origin_date, origin_session (which committee pass produced it),
  case_snapshot (the committee's stored reasoning, so re-surfacing doesn't need re-nomination),
  classification: "daily_reconsider" | "trigger_silent" | "dropped",
  trigger (only if trigger_silent): { field, op, value } e.g. sc_momentum >= 75, or a price level,
  status: "active" | "fired" | "expired",
  expiry: a bounded TTL (reuse the voice-memory pattern — dies stale unless re-confirmed) }
```

**Two lifecycle modes, both live in the same store (PM confirmed both are wanted):**
- `daily_reconsider` — automatically re-fed into the NEXT premarket's tally/committee pass, so
  it's re-scored fresh each morning without the PM re-nominating it from scratch.
- `trigger_silent` — parked, silent, watched continuously; only resurfaces when its condition
  fires. **Watched by market-hours' EXISTING 30-min alert sweep** (`tools/alert_inbox.py`,
  extended membership: `alert_list.json` ∪ the Ledger's active `trigger_silent` rows) — no new
  loop, per the interview answer; reuses the D-82 sweep rather than building a parallel watcher.

## Market-hours — unchanged in autonomy, gains one opportunistic affordance

The Intraday Review Pod stays **fully autonomous by default** (confirm/stand-down, page only on
real conviction) — the PM is asleep for most of this window and does not want to be grilling
voices at 2am. The only addition: **if the PM happens to have a live session open and watching**
when a pod runs, the same live-challenge affordance from premarket is available opportunistically
— not a required gate, not something that blocks the autonomous path when the PM isn't there.

## Post-market — gains one new responsibility

Alongside its existing reconcile/journal/audit/score/learn sequence, post-market now also
**sorts today's non-advancing committee names into the Ledger** (the classification step
above). This is the same kind of miss-classification logic `performance_scorer` already does
elsewhere in the system — same discipline, new target. Surfaces in the 10am summary alongside
the existing journal/audit content, so the PM sees the Ledger's state without a separate check.

---

## What stays exactly as audited in Phase 1 (no change)
- The 11-voice swarm's isolation (anti-anchoring) — unchanged, still the intentional cost.
- Post-market's already-lightened spawn count (1: auditor) — unchanged.
- `/cockpit`, `/status`, `/ops`, `/recover` — unchanged, still the PM's zero-spawn ad hoc surface.
- The six F1–F6 drift/cleanup items from Phase 1 — still open, independent of this change.

## Open build questions (Phase 2 implementation, not yet decided)
- Exact default classification rule for post-market's Ledger sort (DATA_LED→reconsider,
  consensus_only→trigger_silent — proposed, needs confirming against `conviction_funnel.py`'s
  existing `class` field, which may already carry enough signal to drive this for free).
- Ledger TTL / expiry window (voice-memory uses 30 sessions as precedent).
- Exact mechanics of "continue the same committee-desk agent" inside a Cowork-triggered
  premarket session vs a manually-opened one — needs a concrete implementation check before
  committing to the pattern system-wide.
