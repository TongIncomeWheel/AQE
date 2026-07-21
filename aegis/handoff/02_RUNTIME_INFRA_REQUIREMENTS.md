# AEGIS — RUNTIME, MEMORY, HARNESS & INFRASTRUCTURE REQUIREMENTS
**The sourcing specification · 21 Jul 2026**
**Purpose: hand this document to open-source projects, vendors, or a hybrid-build engineer to source
the runtime layer that Claude Cowork cannot provide.**

---

## 0. THE ONE-SENTENCE PROBLEM

We have a complete, harness-neutral agentic trading kernel (analytics, an 11-voice judgment swarm, a
committee, deterministic risk/journaling tools, git-as-source-of-truth). What we lack is a **runtime**
that (a) runs autonomous scheduled loops, (b) delivers their output into **one persistent, interactive
conversation the operator can see and steer**, and (c) keeps **conversation + memory state across days
and sessions** — because Claude Cowork has no client-side persistent runtime and no session-binding for
scheduled work.

**The internalised root cause (operator's words):** *"Claude has no client-side runtime, so any
open-source solution we adopt must provide this — a persistent agent process that also gives a
persistent conversation state."* This document specifies exactly that, so it can be solution-sourced.

---

## 1. WHAT WE ALREADY HAVE (do not re-buy)

- **The kernel / business logic** — skills (process), tools (deterministic Python), contracts (JSON
  schemas), charter (law/rulebook/parameters/decisions). Portable, model-agnostic, in git.
- **The analytics engine (AQE)** — nightly deterministic scoring; outputs a daily JSON export.
- **Model access** — Claude models (via API/SDK) for the judgment tier; the kernel also supports Kimi
  as a parallel engine (harness-neutral by design, D-15).
- **Source of truth** — a private git repo; every artifact is a validated file. Any runtime that can
  `git pull/push` reconstitutes full state.
- **Tool connectivity** — MCP connectors for FMP (data), Tiger + IBKR (broker), Google Drive (feed +
  book). Any target runtime must be able to speak MCP or wrap these APIs equivalently.

**So we are NOT sourcing intelligence or business logic. We are sourcing a RUNTIME + MEMORY + HARNESS
layer.**

---

## 2. THE REQUIREMENTS MATRIX (what the runtime must provide)

Rated **MUST** (non-negotiable), **SHOULD** (strongly wanted), **NICE** (bonus).

### 2.1 Runtime / execution
| # | Requirement | Priority |
|---|---|---|
| R1 | A **persistent or reliably-resumable agent process** — long-lived, or wakeable on a schedule while retaining state (not a fresh throwaway per fire). | MUST |
| R2 | **Scheduled / cron execution** of named workflows (our 5 loops), with reliable firing and failure surfacing. | MUST |
| R3 | Ability to run a **self-perpetuating intraday loop** (sweep every N minutes during market hours) without spawning a new isolated context each time. | MUST |
| R4 | **Sub-agent / parallel spawn** — run 11 isolated judgment agents concurrently, each a fresh context, then collect structured outputs. | MUST |
| R5 | **Model-agnostic** — call Claude (API) for judgment; swap to Kimi or a local model without rewriting the kernel. | SHOULD |
| R6 | Runs **unattended in the cloud** (operator's laptop closed) yet reachable from phone + desktop. | MUST |

### 2.2 Conversation & memory state (the crux)
| # | Requirement | Priority |
|---|---|---|
| M1 | **One persistent conversation/thread** that survives across days and does NOT fragment per-run or per-session — the operator's single cockpit. | MUST |
| M2 | **Session-binding for autonomous output** — a scheduled loop can post its result INTO that fixed conversation, visibly, not into a throwaway thread. | MUST |
| M3 | **Durable long-term memory** beyond the context window — the runtime (or a memory layer) persists facts, decisions, and rolling state and injects the relevant slice at each turn/spawn. (We already persist to git; we want this reflected in the *conversational* agent too.) | SHOULD |
| M4 | **Two-way** — the operator types input/approvals into the same surface and the agent acts on them (not a read-only dashboard). | MUST |
| M5 | Graceful **context-window management** (compaction/summarisation in place) so the single thread is effectively unbounded. | SHOULD |

### 2.3 Human-in-the-loop & interaction
| # | Requirement | Priority |
|---|---|---|
| H1 | **Approval gates** — the agent can pause and require an explicit operator approval (the 21:00 plan approval; any order preview) before proceeding. | MUST |
| H2 | **Proactive push** — the runtime pings the operator's phone when something needs attention (plan ready, stop hit, page), with the content, not just "a task ran". | MUST |
| H3 | **Interrupt / steer** — the operator can inject a message mid-run and redirect. | SHOULD |
| H4 | Mobile + desktop parity for viewing and approving. | SHOULD |

### 2.4 Tools, data, secrets, security
| # | Requirement | Priority |
|---|---|---|
| T1 | **MCP support** (or equivalent adapters) for FMP, Tiger, IBKR, Google Drive. | MUST |
| T2 | **Secret management** — broker/data credentials and the git PAT held securely (NOT inline in prompts, which is the current stop-gap). | MUST |
| T3 | **git integration** — pull state at start, push at end; git is the source of truth. | MUST |
| T4 | **Order-path isolation** — the runtime can enforce that only one sealed component may place orders, under an armed, expiring switch (constitution law 1). | MUST |
| T5 | **Filesystem / code execution** — run the deterministic Python tools locally. | MUST |
| T6 | Audit log of every autonomous action (we already write these; the runtime must not obstruct). | SHOULD |

### 2.5 Operational
| # | Requirement | Priority |
|---|---|---|
| O1 | **Cost model that fits heavy agentic use** — 11 opus-tier spawns/day plus loops. A metered API/self-host model is preferred over a consumer subscription with weekly caps (the current Max-5x plan risk, D-72). | SHOULD |
| O2 | **Observability** — see which loop ran, when, and its outcome (we have `/ops`; the runtime should host or not obstruct it). | SHOULD |
| O3 | **Resilience** — if the box/process dies, no committed work is lost (git); ideally the process auto-restarts and resumes. | SHOULD |
| O4 | **Self-hostable or on trusted infra** — this is a live trading book; data residency and control matter. | SHOULD |

### 2.6 Self-healing & autonomous recovery — KEY POINT (preserve the agent layer, add the runtime layer)

Self-healing is a **primary requirement, not a footnote.** Aegis already implements a mature
**agent/kernel-level** self-heal doctrine that any target runtime MUST preserve unchanged; and it needs
**runtime-level** recovery that the current harness cannot fully provide. Both must be captured in the
solution.

**Agent/kernel-level self-heal — EXISTS in the kernel, must run intact on the new runtime:**

| # | Capability | Where (decision) |
|---|---|---|
| SH1 | Classify every failure — transient / structural / gate / capacity — and act per policy: bounded retry, reseed, escalate-with-exact-manual-fix, or stand-down | `tools/self_heal.py` (D-45) |
| SH2 | **Bounded retry before stand-down** on feed/data pulls (AQE export re-checked +5/+10/+10 min) — heals a late feed silently, pages only on genuine failure | premarket step 3 (D-70) |
| SH3 | **Data-store reconcile / reseed** — a missing or stale name history is re-pulled from FMP, never faked | `historical_store.py` (D-40) |
| SH4 | **Declared-data-gap heal** — a voice DECLARES a missing field; the Chief SOURCES it (FMP or AQE re-export) and RE-RUNS that voice; a name proceeds with a gap only if genuinely unavailable, never guessed | premarket step 5 (D-55) |
| SH5 | **Independent verification (assurance)** — verify the world, not the kernel's belief about it: confirm the PTJ actually landed in Drive, not just that the write step ran | `drive_ptj_check.py` (D-69) |
| SH6 | **Session self-bootstrap** — a fresh scheduled session reconstructs its own workspace + credential + git before running; page + STOP on a half-built workspace | `bootstrap.py` (D-64) |
| SH7 | **Capacity-limit detection** — recognise a model/usage-cap hit distinctly from a data failure; escalate with wait-for-reset, do NOT retry into the same ceiling | `self_heal` usage_limit (D-72) |
| SH8 | **Dead-man's-switch check-in** — the ABSENCE of a heartbeat becomes the alarm if the box dies mid-run | `notify.py --checkin` (D-45) |

**Doctrine the runtime must not break:** self-heal is **ORDER-BLIND** (may re-run READ/COMPUTE/PLAN,
never place/size/arm); **bounded + logged** (`data/eod/DATE/self_heal_DATE.jsonl`); **declare on
exhaustion, never fabricate**; a **hard gate/tripwire is stood down, never healed** (PM override only).

**Runtime-level self-heal — the sourced runtime MUST ADD (this is what Cowork could not do):**

| # | Requirement | Priority |
|---|---|---|
| SH-R1 | **Auto-restart a died process/loop and RESUME from the last checkpoint** (git state) without duplicating side effects | MUST |
| SH-R2 | **Re-fire a scheduled loop that failed or never ran** on demand (the `/recover` lever — a missed premarket must be recoverable), with the operator notified | MUST |
| SH-R3 | **Deliver an unrecoverable failure to the operator with the exact manual fix** — the ladder already produces this text; the runtime must actually get it to the phone | MUST |
| SH-R4 | **Watchdog / liveness monitoring of the agent process itself** — extend the dead-man's-switch (SH8) from the run to the runtime | SHOULD |
| SH-R5 | **Idempotent retries** — a re-run must not double-journal, double-order, or double-commit (git + schema validation already guard this; the runtime must respect it) | MUST |

**Net:** the *intelligence* of self-healing lives in the kernel and must be preserved; the runtime must
supply the *process resilience* that keeps the self-healing agents alive, resumable, and their
escalations delivered. A candidate runtime that cannot restart/resume a loop (SH-R1) or re-fire a
missed one with notification (SH-R2/R3) leaves the self-heal doctrine half-blind.

---

## 3. THE ARCHITECTURE WE EXPECT TO BUILD (hybrid reference)

We anticipate a **hybrid**: keep Claude (or Kimi) as the *brains* via API; source/build the *runtime +
memory + cockpit* around it. A candidate shape to validate against any solution:

```
            ┌──────────────────────────────────────────────────────────┐
            │  PERSISTENT AGENT RUNTIME  (the layer we are sourcing)     │
            │                                                            │
  operator ─┤  ONE durable conversation  ◄── proactive push to phone     │
  (phone/   │        ▲     │                                             │
   desktop) │  approvals   │ delivers loop results into this thread      │
            │        │     ▼                                             │
            │  ┌───────────────────┐   scheduler   ┌──────────────────┐  │
            │  │ cockpit / session │◄──────────────│ 5 scheduled loops│  │
            │  │  state + memory   │               │ (premarket, ...) │  │
            │  └───────────────────┘               └──────────────────┘  │
            │        │  calls                              │ spawns       │
            │        ▼                                     ▼              │
            │   Claude/Kimi API (judgment)        11 isolated voices      │
            │        │                                     │              │
            │        ▼                                     ▼              │
            │   MCP tools: FMP · Tiger · IBKR · Drive   deterministic     │
            │   secrets vault · git (source of truth)   Python tools      │
            └──────────────────────────────────────────────────────────┘
```

The kernel (skills/tools/contracts/charter) drops into this unchanged. The runtime supplies R1–R6,
M1–M5, H1–H4, and the secret/order-isolation guarantees.

---

## 4. CANDIDATE SOLUTION SPACE (to evaluate — NOT endorsements)

The following are *categories and named projects to investigate* against §2. They are starting points
for the operator's sourcing, not verified recommendations — each must be checked against the matrix,
especially M1/M2 (persistent bound conversation) and H1/H2 (approval + push), which are where most
frameworks are weak.

- **Agent orchestration frameworks (self-host):** LangGraph (stateful graphs, checkpointing,
  human-in-the-loop interrupts — strong on M3/H1), CrewAI, AutoGen / AG2 (multi-agent, good for the
  swarm R4), Letta / MemGPT (purpose-built persistent memory — strong on M3/M5), OpenHands (autonomous
  dev/agent runtime, code execution T5).
- **Claude Agent SDK, self-hosted:** run the Anthropic Agent SDK on our own always-on box (gives R1/R6
  control, metered API cost O1) — this keeps the same model + tool-use loop but under our runtime,
  potentially closing R1/R3 that Cowork does not.
- **Persistent-conversation surfaces:** a chat front-end we control (e.g. a self-hosted assistant UI, a
  messaging bridge — Telegram/Slack/WhatsApp bot as the durable thread) bound to the agent process, so
  M1/M2/M4/H2 are satisfied by a channel we own rather than a vendor's session model.
- **Memory layers:** Letta, Zep, Mem0, or a simple git+vector store our tools already approximate.
- **Scheduler/infra:** a always-on VM / container (the operator's existing 24/7 PC per D-9, or a small
  cloud VM), cron or a durable workflow engine (Temporal) for R2/R3/O3.
- **Kimi / OpenClaw:** evaluate whether either provides a persistent bound conversation + scheduled
  delivery natively (the specific thing Cowork lacks) — the operator raised these; verify M1/M2/H2
  against their docs the same way we verified Cowork.

---

## 5. THE EXACT QUESTIONS TO ASK EACH CANDIDATE

Copy these into any vendor/OSS evaluation:

1. Can a scheduled/background job post its output into a **specific, pre-existing conversation** that
   the operator is viewing — so all runs accumulate in ONE thread? (M1/M2) *If no, it does not solve
   our core problem.*
2. Does that conversation **persist across days and restarts** without fragmenting into a new thread
   each session, with in-place context compaction? (M1/M5)
3. Can the operator **type back into that same thread** and have the agent act on it — approvals,
   steering? (M4/H3)
4. Can the agent **pause and require explicit approval** before a gated action, and resume on the
   operator's reply? (H1)
5. Can it **push to the operator's phone** with the *content* of what needs attention? (H2)
6. Does it run a **self-perpetuating intraday loop** while keeping state, or does each interval spawn a
   fresh isolated context? (R3)
7. Can it spawn **N isolated sub-agents in parallel** and collect structured outputs? (R4)
8. **Secrets:** are credentials held in a vault, never inline in prompts? (T2)
9. **Cost:** metered/API or self-host — no weekly usage cap that a heavy daily swarm would hit? (O1)
10. **Model-agnostic:** can we point the judgment tier at Claude today and Kimi/local tomorrow without
    rewriting business logic? (R5)
11. **Self-healing / recovery:** if a scheduled loop dies mid-run, does the runtime **auto-restart and
    resume from checkpoint** without duplicating side effects, and can the operator **re-fire a missed
    loop on demand** with notification? (SH-R1/R2/R5) Does it preserve our order-blind, bounded,
    never-fabricate self-heal doctrine (§2.6)?

Any solution that answers **yes to 1, 2, 3, 4, 5** is a genuine fit. That specific combination —
persistent bound two-way conversation + approval + push — is precisely what Claude Cowork could not
provide and what the sourcing must deliver.

---

## 6. WHAT SUCCESS LOOKS LIKE (acceptance criteria)

- The operator opens ONE app/thread. Yesterday's context is there. This morning's premarket plan
  posted itself into it overnight. The operator reads it, types "approve, but skip the two XLF adds,"
  and the agent stages the rest — all in that one thread.
- At 21:00 the same thread pings the phone: "plan still unapproved, stands down in 0 min." Intraday, a
  stop-hit page arrives in the same thread with the name and level.
- Nothing is lost if the box restarts; the thread and the book reconstitute from git + memory.
- The 11-voice swarm and committee run on metered API cost, unattended, five days a week.

When a candidate runtime can do the above with the Aegis kernel dropped in unchanged, the migration is
done.
