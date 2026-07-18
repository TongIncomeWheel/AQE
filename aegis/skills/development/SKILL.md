---
name: development
description: The learning→development bridge — how enhancements get specified, built, tested, shipped and remembered. This loop is WHY spaghetti never comes back; unmanaged change is the one thing this system refuses to do.
---

# SKILL: DEVELOPMENT (managed change pipeline)

## Why it exists
The old system decayed because change had no pipeline: every fix was an edit, every edit was forever, nothing was tested against outcomes, and nothing was ever retired. This skill is the bridge from "we learned something" to "the system is now different, provably better, and the change is remembered."

## The pipeline — every change walks these stages
1. **CAPTURE.** Findings arrive from Design & Review (scorer/learning agent), from a PM idea, or from a breach. Each becomes a backlog item in `data/persistent/backlog.jsonl` (contracts/backlog.schema.json) — finding, evidence, proposed change, expected effect, **what it retires** (mandatory, minLength enforced), owner (code / rulebook / parameters / voice-card / skill / contract). Field-conditional proposals must carry `measured_on_panel: true` (tools/measure_proposal.py) before they can advance. Status: PROPOSED.
2. **APPROVE.** Items surface in the PM's 10:00 morning summary. Parameter tweaks → set_param immediately (done, logged). Law changes → committee path. Everything else → PM one-tap: PM_APPROVED or REJECTED.
3. **BUILD.** A coding agent implements on a git branch named `dev/<item-id>`. Never on main. The change must include: the code/skill/card edit, a contract update if data shapes change, and the retirement (deletion) it promised.
4. **VERIFY.** On the branch: all python compiles · contracts validate · tripwires pass on the latest export · packaging builds both harness installs · if behaviour-facing, one **shadow day**: tomorrow's run executes BOTH versions side-by-side (or replays today), diff attached to the item. Status: IN_SHADOW.
5. **SHIP.** PM sees the diff in the morning summary and approves merge. Version bumped, decisions_log entry if law/parameters touched, adapters rebuilt, CHANGELOG line written. Status: SHIPPED. The branch dies.
6. **REMEMBER.** The item stays in the backlog file forever with its evidence and shadow result — the system's development memory. Design & Review re-measures shipped items after 15 sessions: did the expected effect materialise? If not → new finding, back to stage 1 (possibly reverting — a revert is also a managed change).

## Standing rules
- No edit outside this pipeline except PM parameter tweaks (which self-log via set_param).
- An item without a retirement is invalid at CAPTURE — the schema enforces it.
- Two failed shadow days = automatic REJECTED; the idea returns to evidence-gathering.
- The pipeline itself is versioned: changing THIS skill walks through this skill.
