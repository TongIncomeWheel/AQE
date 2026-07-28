# Agentic System Audit — Backend vs PM-Interactive, vs Operations Atlas

**Date:** 2026-07-27. **Guiding reference:** `OPERATIONS_ATLAS.html` (kernel v5.3, 18 Jul 2026).
**Purpose:** Phase 1 of the PM's requested redesign — audit only, no code changed. Maps every
skill's actual current behaviour against the Atlas's auto/PM classification, finds where the
live system has drifted, and locates the token/interface cost that's driving "too many tokens,
not the 1-agent interface I want."

**Headline finding:** the *design* is not the problem. The Atlas's own classification —
almost everything auto/backend, PM touches only the 4pm approval + ad hoc commands + the 10am
summary — is sound and the live skills mostly still honour it. The actual gap is **how the
backend gets run**: when a premarket/market-hours/post-market pass executes in the PM's own
live chat instead of a scheduled background session, the PM watches 12+ subagent spawns unfold
directly in their transcript — which reads exactly like "too many tokens, not one agent," even
though the design intends that swarm to be invisible backend cost. That's the primary lever.
Six secondary drift/cleanup items are also real and independently worth fixing.

---

## 1. Phase-by-phase classification (current, verified against live SKILL.md files)

### Premarket (`skills/premarket/SKILL.md`) — matches Atlas shape closely

| Steps | Class | Spawns |
|---|---|---|
| 0–8, 9b, 9c | BACKEND-ONLY | 0 (deterministic tools/scripts) |
| 5 (the swarm) | BACKEND-ONLY | **11** isolated voice spawns (10 canonical + Elder lens, D-51), plus **unbounded re-spawns** on any data-gap self-heal (D-55) |
| 9 (deliberation) | MIXED — backend record, drives the PM plan | **1** committee-desk spawn (opus/judgment) |
| 9a (reactive/off-cycle) | MIXED | +1 committee-desk spawn per off-cycle check, conditional |
| 10 (plan assembly + alert list) | **PM-MUST-SEE** | 0 — the actual 4pm render |
| 11 (approval) | **PM-MUST-SEE** | 0 — the one genuine interactive gate |
| 12 (close message) | **PM-MUST-SEE** | 0 |

**Core daily spawn count: 12** (11 voices + 1 committee-desk) before self-heal re-spawns.
This matches the Atlas's own design (10 voices → 1 committee) almost exactly — the swarm size
is the intentional cost of anti-anchoring, not drift.

### Market hours (`skills/market_hours/SKILL.md`) — matches Atlas shape, with two text bugs

| Steps | Class | Spawns |
|---|---|---|
| 1, 2, 3, 3b, 5, 6 | BACKEND-ONLY | 0 (deterministic; step 1a runs haiku/watch-tier, ~13 wakes/night on the 30-min sweep — a small standing cost floor, by design D-58) |
| 3c (Intraday Review Pod) | MIXED — verdict only advances on CONFIRM | **N+2** isolated spawns (nominating voice(s) + Druckenmiller + Detect lens), judgment tier, gated to survivors only |
| 4, 4b, 1b(iii) | MIXED | +1 staging-gatekeeper spawn when an order-shaped action is requested |
| ON FAILURE ladder | **PM-MUST-SEE** (all page or log) | 0 |

**Worst case per alert-to-action cycle: ~12 spawns** (all-voices pod + gatekeeper); **best case
on a quiet night: 0 judgment spawns**, only the cheap haiku sweep. This is correctly cheap-by-
default — the judgment spend is reserved for confirmed survivors, exactly as D-58 intends.

### Post market (`skills/post_market/SKILL.md`) — genuinely lightened since the Atlas

| Steps | Class | Spawns |
|---|---|---|
| 0, 1, 1b, 2, 2c | BACKEND-ONLY / MIXED (halts + pages on failure) | 0 |
| 2b (scorer) | BACKEND-ONLY | **0 named** — see Finding F3 below |
| 3 (audits) | **PM-MUST-SEE** (flow-audit rides the 10am summary) | **1** auditor spawn |
| 4, 5 | **PM-MUST-SEE** | 0 |

**Core spawn count: 1** (auditor only). The Atlas originally specified 3 spawns here
(auditor + performance_scorer + learning_agent) — this is real, verified architectural
improvement: `performance_scorer` now runs in Design & Review step 2, `learning_agent` in
Design & Review steps 3–4. Post-market got lighter, not heavier, over the system's evolution.

### Everything else (`skills/*` — 25 remaining skills)

| Category | Skills | Class | Spawn cost |
|---|---|---|---|
| PM-facing utilities, built post-Atlas | `cockpit`, `recover`, `status`, `ops-status` | PM-facing, ad hoc command | **0** — pure read/render of existing shelf files, no judgment call |
| Weekly + Design & Review | `weekly`, `design_review` | PM-facing (Sunday report / steer file in 10am summary) | Yes, orchestrates conditional sub-spawns |
| Engineering Bench ×5 | `eng-data/governance/indicator/process/technical` | Supporting, spawned only on contested/deep findings | Yes, conditional |
| Assurance agents | `auditor`, `performance_scorer`, `learning_agent` | Supporting, feed the PM-facing summary | Yes, 1 each, scheduled placement |
| Voice roster ×11 + engine | `voice-*`, `voice-common` | Supporting (the swarm itself) | Yes — this IS the 11-spawn cost center |
| Deliberation / execution | `committee-desk`, `staging-gatekeeper` | Supporting, feeds PM-facing plan/preview | Yes, by design isolated (security + anti-anchoring) |
| `development` | The learning→build pipeline | Backend infrastructure (PM approves gates within it) | No — orchestration only |

**cockpit / recover / status / ops-status carry zero spawn cost** — confirmed clean. These are
exactly the "1-agent interface" primitives the PM already has: a single command, a single
read-only render, no swarm underneath. This is the right pattern to lean on harder (§4 below).

---

## 2. Drift-from-Atlas findings (six items, independently worth fixing)

- **F1 — Duplicate scoring passes (premarket step 6 vs 6b).** The Data Board and the
  Conviction Funnel are two separate deterministic tools re-tiering materially the same
  universe/tally data on overlapping axes (data-strength, detect count, consensus). The skill
  text acknowledges this ("complements... the data board, which stays") — not accidental, but
  still two mechanisms doing adjacent work. Candidate for the same kind of consolidation just
  done in D-81/D-82.
- **F2 — Stale cadence text (market_hours step 1b).** Still reads "so a 15-min cadence stays
  cheap" — a direct leftover from before D-82 changed the AQE feed to 30-min. One-line fix.
- **F3 — Two undocumented "no named tool" steps.** Premarket step 9's "Risk" read and
  post-market step 2b's "scorer" both produce real outputs with **no spawn directive and no
  named deterministic script** — unlike every sibling step, which cites either a tool or an
  explicit spawn. This is a genuine ambiguity: either the orchestrator (control-plane, meant to
  sequence not analyze, per D-16) is doing real judgment inline, or these silently duplicate
  work `performance_scorer`/committee-desk already do elsewhere. Needs a definitive answer, not
  just a documentation fix — this is the one finding with a real correctness question behind it.
- **F4 — Duplicated procedure description (market_hours 1b(ii) vs 3c).** The Intraday Review
  Pod is fully re-specified in two places instead of one cross-reference — exactly the kind of
  two-copies-desync that produced F2.
- **F5 — Overloaded step numbering (post_market step 3).** Three distinct audit functions
  (completeness audit, independent Drive-PTJ verification, flow-audit) share one step number,
  producing 4 artifacts. Each is real and necessary; the numbering just makes it hard to audit
  at a glance.
- **F6 — One likely-orphaned artifact.** `data/eod/DATE/ptj_drive_listing.json` (post-market
  step 3) appears to be written and never read again downstream — provenance only, cheap but
  dead weight, same class as the AQE-JSON noise already cleaned up under D-81.

None of these six are urgent — they're the kind of tidy-up D-81/D-82 already demonstrated the
playbook for (reuse, consolidate, name the tool, retire the duplicate).

---

## 3. Why it doesn't feel like "1 agent" — the actual lever

The Atlas's design already answers "backend trigger vs PM must see it" correctly: everything
through premarket step 10, all of market-hours except a paging event, and post-market through
step 4 are backend-only by design — the PM's total daily interactive surface is meant to be the
4pm plan approval, ad hoc `/status` `/ops` `/recover` `/cockpit` commands, and the 10am summary.
That's already close to a 1-agent interface *on paper*.

The mismatch is **execution context, not architecture**. Aegis's committee methodology
(D-5's whole premise) *requires* the voices to run in genuinely isolated contexts — that
isolation is what prevents anchoring, and collapsing it into "1 agent" would break the thing
that makes the committee's judgment trustworthy. That cost is real, unavoidable, and by design.

But that cost is only supposed to be paid **once, silently, on a schedule** — a background
session spawns the 12 premarket agents, writes the plan, and the *cockpit* pattern (`/cockpit
arm`, D-76) delivers just the one rendered result into whatever chat the PM is watching. When
premarket is instead run by directly invoking the skill in the PM's own live foreground
session, Cowork shows all 11+ subagent tool calls unfolding directly in that transcript — the
PM is watching (and paying attention-cost for) exactly the swarm the design meant to hide. That
is the concrete mechanism behind "too many tokens, not the 1-agent interface I want" — it is a
real, fixable, and *already-half-built* problem (the cockpit/scheduled-trigger machinery
exists), not evidence the design needs a rebuild.

**The lever, concretely:** run the three daily phases as scheduled background triggers (as they
already are meant to be per D-64/D-74), and use `/cockpit arm` + the existing `/status` /
`/ops` commands as the PM's entire live-session surface. If that pattern isn't holding
today — worth confirming directly, since this session's own history includes at least one
scheduled post-market silently not firing (07-21) — the fix is to harden the scheduling/cockpit
delivery reliability (an operational fix), not to re-architect the swarm.

---

## 4. Recommended next steps (Phase 2, not yet started — awaiting PM direction)

1. **Confirm the actual usage pattern**: are premarket/market-hours/post-market currently
   firing on their scheduled triggers reliably, with `/cockpit` delivering the result — or is
   the PM regularly invoking these skills directly in a live chat and watching the swarm run?
   This single answer determines whether the fix is operational (harden scheduling/cockpit) or
   needs a genuine interface change.
2. **Fix F1–F6** — low-risk, same consolidation pattern as D-81/D-82, no design decision needed.
3. **If the PM wants a leaner default swarm**: the 11-voice/1-committee cost is a real design
   parameter (`RB:committee.*`), not fixed in stone — could scale it PM's-call (e.g. a smaller
   daily panel with the full 11 reserved for higher-conviction/contested names), but this
   trades against the anti-anchoring guarantee and should be an explicit, informed decision.
