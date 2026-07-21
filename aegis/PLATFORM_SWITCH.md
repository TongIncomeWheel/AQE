# AEGIS — PLATFORM SWITCH CONTEXT
**Instructions for moving the Aegis kernel to another harness/runtime · 21 Jul 2026**
**Read this first if you are a new harness (Kimi, OpenClaw, a self-hosted Agent SDK runtime, LangGraph,
etc.) picking up Aegis, or a human wiring the kernel into one.**

---

## 1. THE PROMISE: THE KERNEL IS HARNESS-NEUTRAL (D-15)

Aegis was built so the AI harness is an **interchangeable engine**. The business logic, process, risk
rules, contracts, and memory all live in this git repo as plain files. Nothing important lives in any
one vendor's session or memory. To move platforms you re-point the *runtime* at this repo; you do not
rebuild the system.

**What is portable (all of it — this repo):**
- `charter/` — constitution (law), rulebook (doctrine), parameters (numbers), decisions_log (D-1..D-77).
- `skills/` — the process, as markdown cards. A harness reads these and executes them.
- `tools/` — deterministic Python (no model). Runs anywhere with Python 3.
- `contracts/` — JSON schemas every artifact validates against.
- `CONTEXT.md` — the load-first orientation file.
- Git history — the full book of record and decision memory.

**What is harness-specific (must be re-provided by the target runtime):**
- The scheduler (how the 5 loops fire).
- Sub-agent spawning (how the 11 voices + committee are invoked as isolated contexts).
- Model access (Claude/Kimi/local via API).
- MCP / tool connectivity (FMP, Tiger, IBKR, Drive).
- Secrets handling and the git credential.
- The interactive surface (the cockpit) + notifications.

---

## 2. MINIMUM CONTRACT A NEW RUNTIME MUST HONOR

1. **Read the kernel first.** On any session/loop start: read `CONTEXT.md` + the four `charter/*`
   files. These are the source of behavior. Do not infer rules; read them.
2. **git is truth.** `git pull` at start; run the phase; `git push` durable state at end. Every
   artifact is a validated JSON file on the `data/` shelf. State reconstitutes from git — never from
   conversation memory.
3. **Isolation for judgment.** The 11 voices and the committee-desk MUST run as fresh, isolated
   contexts (no shared session, no cross-voice leakage) on the judgment model tier. This is the
   anti-anchoring guarantee — consensus is counted, not negotiated.
4. **The control plane never analyses.** The orchestrator sequences, validates contracts, calls tools.
   Real judgment is always delegated to a spawned judgment-tier agent.
5. **One order path.** Only the staging-gatekeeper may place an order, only under an armed, dated,
   auto-expiring switch. Default is PREVIEW. Never wire a second order path.
6. **Read, never invent.** Voices read AQE data; a missing field is sourced by the orchestrator (FMP or
   AQE re-export), never guessed. Fabrication is the gravest breach.
7. **Every change retires something.** Route changes through `skills/development` (capture → approve →
   branch → verify → ship → remember). No unmanaged edits.

If a runtime honors these seven, Aegis behaves identically regardless of vendor.

---

## 3. STEP-BY-STEP: STANDING AEGIS UP ON A NEW RUNTIME

1. **Clone the repo** and ensure Python 3 + the deterministic tools run (`python3 tools/alert_universe.py
   selftest`, `python3 tools/self_heal.py selftest`, etc. — the selftests are the smoke test).
2. **Wire model access** for the judgment tier (Claude via API recommended; Kimi supported). Map
   "spawn an isolated agent with this prompt + this file, return structured JSON" to the runtime's
   sub-agent primitive. The voice cards are in `skills/voice-*` / compiled `agents/voice-*.md`.
3. **Wire the MCP tools** (FMP, Tiger, IBKR, Drive) or equivalent adapters. Broker tools must preserve
   the preview-then-confirm two-step and the order-path isolation.
4. **Wire secrets** into the runtime's vault (git PAT, broker creds). Remove the inline-PAT stop-gap
   once the vault exists (see `02_RUNTIME_INFRA_REQUIREMENTS.md` T2).
5. **Wire the scheduler** to fire the 5 loops at the SGT times in `SCHEDULERS.md`. Each loop = read
   kernel → run skill → push git → deliver outcome.
6. **Wire the cockpit + notifications** — the persistent interactive thread and push (the layer Cowork
   lacked; see the requirements doc §2 M1/M2/H1/H2).
7. **Verify** with a dry run (`DRYRUN.md`) before enabling live scheduling.

---

## 4. WHY WE ARE CONSIDERING A SWITCH (context for the receiving team)

Claude Cowork runs the compute well but does not provide a **persistent, interactive, proactive single
cockpit** (no session-binding for scheduled output; display-only artifacts; no durable two-way thread —
verified against Anthropic docs). For a live trading book the operator must be able to see, interrogate,
and steer the system in one coherent place. That runtime layer is what a switch (or hybrid) must supply.
The full specification and the evaluation questions are in `handoff/02_RUNTIME_INFRA_REQUIREMENTS.md` —
that is the document to solution against.

**Evaluate the target against the five make-or-break questions** (requirements doc §5): can a scheduled
job post into one persistent conversation (1), that survives across days (2), that the operator can type
back into (3), with pause-for-approval (4), and phone push of the actual content (5). Yes to all five =
a genuine fit.

---

## 5. DO-NOT-BREAK LIST (the hard-won invariants)

- Voices isolated; consensus counted not negotiated.
- Event filter is the only hard exclusion; everything else is weather/context.
- Momentum-first; extension is strength; risk lives in the bracket (not a gate).
- Sector concentration is context, PM decides.
- dynCap/gates apply to the Aegis-tagged book only, never co-mingled broker totals.
- The alert universe is a mechanical formula (the casting mat), not a hand-picked list.
- One order path; preview by default; the arming switch expires.
- git is the source of truth; nothing critical in chat memory.
- Self-heal is order-blind, bounded, logged, and never fabricates; a hard gate is stood down, never
  healed. Preserve the agent-level self-heal ladder intact and add runtime-level restart/resume/re-fire
  (see `handoff/02_RUNTIME_INFRA_REQUIREMENTS.md §2.6`).
