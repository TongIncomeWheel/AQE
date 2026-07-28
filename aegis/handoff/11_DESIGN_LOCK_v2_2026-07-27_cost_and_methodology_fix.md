# Design Lock v2 — Cost Fix + Voice Methodology Fix (2026-07-27, same-day revision)

**Supersedes/refines:** `10_DESIGN_LOCK_2026-07-27_deliberation_and_ledger.md`. That doc got the
shape of Half 1 / Half 2 / the Ledger right; this revision fixes three things the PM caught
before any code was written: (1) Half 1 needs an explicit dependency gate, not just a clock
time; (2) the actual cost blow-up mechanism — every query re-running all 11 voices — needed a
root-cause diagnosis, not an assumption; (3) the Ledger only takes what the committee proposes,
not a blanket sweep. Nothing built yet. This is still Phase 2 design.

---

## 1. Phase 0 — a genuine dependency gate, not a clock guess

**PM's point:** Half 1 (auto build) must be ready by a fixed morning time, and its real
prerequisite is post-market's journal being current — not "premarket happens to fire a few
hours after post-market usually finishes." **PM's second point:** should this freshness check
be its own Claude Code scheduled task, since that's lighter on token use.

**Confirmed correct, with the reasoning made explicit:** a scheduled task fires a fresh,
minimal-context session. If Phase 0 is its OWN tiny task — check journal current + AQE export
fresh, nothing else — a failure costs almost nothing (no swarm, no universe build, not even the
premarket skill's own overhead spins up) and it can retry/reschedule itself until the
precondition is met, THEN fire Half 1. Contrast with today's design, where the freshness check
is step 1 of the same session that goes on to do the full build regardless — if it's folded in,
a stale-data morning still pays for spinning up the larger session before halting. Splitting it
out is strictly cheaper and is the right "loop technique" instinct.

**Design:** `Phase 0` = a small scheduled task, fires shortly after post-market's expected
completion (its own schedule, not tied to Half 1's clock), does exactly two deterministic
reads (journal current? AQE export dated today?), and only on both-pass does it `fire_trigger`
the Half 1 (auto-build) task. On failure: bounded retry per the existing self-heal doctrine
(`tools/self_heal.py`), never blocks silently, pages if still stale past the retry budget —
reusing the exact ladder premarket step 1/3 already uses today, just relocated to run BEFORE
the expensive half exists at all, rather than inside it.

---

## 2. The actual cost mechanism — diagnosed, not assumed

**PM's report:** "every query I did, it restarted all 11 swarms." Investigated and confirmed:
the system today has exactly ONE entry point for "premarket" — the full build skill. There is no
separate "just answer a question about today's already-built shortlist" path. So any follow-up
question the PM asked, however small, necessarily re-invoked the same top-level skill that
re-runs universe → all 11 voices → tally → committee from scratch, because nothing in the
system distinguishes *build* from *query*.

**Two further, connected findings from the investigation** (this is why "make each voice a
skill" wasn't the fix, and what the real fix has to touch):

- **The voices' methodology is genuinely inconsistent, and it's a contract problem, not a
  packaging problem.** `voice-common`'s procedure is self-attested prose — "apply IN ORDER,"
  "say so," collapsing a 5-item checklist into one ≤300-char free-text `reason`. Nothing
  enforces that every checklist item was actually walked; a voice that silently applies only
  item 1 of 5 still produces perfectly schema-valid output. The compiled agent file spawned
  today is a byte-identical concatenation of that same loose prose — compiling it into "a
  skill" changes packaging, not rigor.
- **There is no memory of a voice's actual reasoning anywhere** — only outcome stats (hit rate,
  open picks, standing lessons). The one-line `reason` from the day's nomination is never even
  carried into voice memory. So today, even if the PM wanted to just READ what a voice concluded
  and why, in detail, there is nothing on disk to read — the ONLY way to get more than one
  sentence out of a voice is to re-spawn it.

These two findings explain the cost problem directly: **there is no cheap thing to read, so the
system's only tool is the expensive thing — re-run everything.**

### The fix — three parts, addressing both the cost and the quality complaint together

**(a) Schema-enforced checklist trace (fixes "slipping steps").** Extend
`contracts/nomination.schema.json` with a required `checklist_trace` array — one entry per item
in the voice's own declared checklist (`{item, applied: bool, evidence, note}`), so a voice
cannot produce valid output without accounting for every step, even if the honest account is
"N/A — data unavailable." The `reason` field stays as the human-readable synthesis; the trace
becomes the enforced backbone. This is genuinely mechanical (law 4) — the schema itself is what
catches drift, not a prompt asking nicely.

**(b) A real per-voice memory artifact (the "noted MD" the PM described).** Alongside the
terse `nomination.json`, each voice ALSO writes its full reasoning for the day — not capped at
300 chars — to `data/sod/DATE/voice_analysis/<voice>.md`. Written once, at the same spawn,
zero extra cost. This is the artifact a later question gets answered from. Committee-desk's
richer output (it already has a mandatory `bear_case` + `data_anchors`) is the equivalent for
deliberated names and needs no new spawn to be useful this way — it already exists, just wasn't
being treated as the PM's first stop.

**(c) Split "build" from "deliberate/query" as genuinely separate operations.** This is the
core architectural fix. Premarket becomes two distinct invocable behaviors, not one skill with
one entry point:
  - **premarket-build (Half 1, unchanged):** the auto pipeline, gated by Phase 0, runs once,
    writes the shelf (universe, 11 nominations + voice_analysis MDs, tally, committee, shortlist).
  - **premarket-deliberate (Half 2, new):** what the PM actually opens. Its FIRST move on any
    question is a deterministic read of today's shelf — nomination + voice_analysis MD +
    committee.json — zero agent spawns, this answers the large majority of "why did X get
    picked" questions for free. Only when the PM's question is a genuine CHALLENGE requiring
    reconsideration (not recall) does it spawn — **one agent**, the specific voice or
    committee-desk being challenged, given its own prior file as context plus the PM's exact
    challenge, so it revises rather than restates from zero. Never the full swarm again for a
    follow-up question. This is the concrete mechanism behind "independence but not stupidity
    loops" — the voices stay isolated from each other (anti-anchoring intact), but a single
    challenged voice is one call, not eleven.

This needs a short operating rule stated plainly wherever the deliberation session's context is
governed (its CLAUDE.md-equivalent / the premarket-deliberate skill's own header): *a question
about today's record is answered by reading the shelf first; a fresh spawn happens only for an
explicit challenge, and only the ONE name/voice being challenged, never a rebuild.*

---

## 3. Ledger — narrowed to committee's own proposal, not a blanket sweep

**Correction from v1:** not "post-market classifies everything that didn't advance." Only
names the **committee itself proposes** for the Ledger, based on its own read of setup quality,
get added — a judgment call made once, at deliberation time, folded into committee-desk's
existing verdict output (no extra spawn). Requires one addition to `contracts/committee.schema.json`:
a `ledger_proposal` field per verdict — `{propose: bool, classification: "daily_reconsider" |
"trigger_silent", trigger (if trigger_silent), reason}` — the field the investigation confirmed
doesn't exist today and would need adding deliberately.

Reconciling with the earlier interview answer ("post-market sorts it, I confirm at premarket"):
the committee PROPOSES (live, during Half 2, the PM already sees it in that same session);
post-market PERSISTS what was proposed (a mechanical write into the Ledger store, no new
judgment); the next premarket's Half 2 opening surfaces the Ledger's current state for the PM
to glance at/override. Committee decides what's worth keeping; post-market just files it.

---

## What's unchanged from v1
- The 11-voice swarm's isolation for the DAILY BUILD — unchanged, still the intentional
  anti-anchoring cost, still runs once per day.
- Market-hours: autonomous by default, opportunistic live-grill only if the PM is present —
  unchanged.
- `/cockpit`, `/status`, `/ops`, `/recover` — unchanged, zero-spawn PM surface.

## Still open before build
- Exact `checklist_trace` shape needs to be derived per-voice from each card's existing
  numbered checklist (11 cards to update, mechanical work, not a new design decision).
- Where premarket-deliberate physically lives (new skill file vs. a mode of the existing
  premarket skill) — leaning new skill file, cleaner separation, avoids the single-entry-point
  problem that caused this issue in the first place.
