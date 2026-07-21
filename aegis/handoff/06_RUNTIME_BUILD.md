# AEGIS — RUNTIME BUILD BLUEPRINT & SYSTEM REQUIREMENTS
**How to build the self-hosted runtime · 21 Jul 2026**
**Context: move off the Claude subscription; host an always-on runtime that calls the Claude API (and
other models via a router), drives the Discord cockpit (doc 05), and runs the Aegis kernel unchanged.**

This is the implementation blueprint for an engineer (or the operator). It satisfies the requirements
in `02_RUNTIME_INFRA_REQUIREMENTS.md` (R/M/H/T/O/SH). The kernel — skills, tools, contracts, charter —
drops in unchanged; this doc is only the runtime *around* it.

---

## 1. TARGET ARCHITECTURE

```
  ALWAYS-ON HOST (mini-PC / NUC / home server / small cloud VM, Linux)
  ┌──────────────────────────────────────────────────────────────────────┐
  │  aegis-runtime  (one long-lived Python service, supervised)            │
  │                                                                        │
  │  ┌─ SCHEDULER (APScheduler) ── fires the 5 loops + #ops interval publish│
  │  │                                                                     │
  │  ├─ ORCHESTRATOR ── reads the kernel skill cards, sequences each loop  │
  │  │      • spawns the 11 voices + committee (async, isolated)           │
  │  │      • runs the deterministic tools (python tools/*.py)             │
  │  │      • validates every artifact vs contracts/*.json                 │
  │  │      • git pull at start / push durable state at end                │
  │  │                                                                     │
  │  ├─ MODEL GATEWAY (LiteLLM) ── one interface, routes per tier:         │
  │  │      voices→Sonnet · committee→Opus · control→Haiku · (Kimi/local ok)│
  │  │                                                                     │
  │  ├─ TOOL/CONNECTOR LAYER ── local MCP servers OR direct clients:       │
  │  │      FMP · Tiger (tigeropen) · IBKR (IB Gateway) · Google Drive     │
  │  │                                                                     │
  │  ├─ STATE ── git (source of truth) + SQLite/Postgres (loop state,      │
  │  │           checkpoints, cockpit/session memory)                      │
  │  │                                                                     │
  │  ├─ GATEKEEPER ── the ONLY order-capable module (isolated, armed-switch)│
  │  │                                                                     │
  │  └─ COCKPIT ADAPTER (discord.py) ── publishes to / listens on channels │
  │        gateway = outbound WebSocket → NO public URL / port-forward     │
  │                                                                        │
  │  SECRETS VAULT (sops/age or OS keyring) · SUPERVISOR (systemd) ·       │
  │  WATCHDOG (heartbeat → healthchecks.io) · structured logs             │
  └──────────────────────────────────────────────────────────────────────┘
         │ Anthropic API (+ others)      │ broker/data APIs        │ Discord gateway
         ▼                               ▼                         ▼
   judgment tier                   FMP/Tiger/IBKR/Drive        the operator's cockpit
```

---

## 2. COMPONENT CHOICES (recommended; alternatives noted)

| Layer | Recommended | Why / alternatives |
|---|---|---|
| **Host OS** | Ubuntu LTS (Linux) | clean service management; runs on a NUC/home box or a cloud VM |
| **Language** | Python 3.11+ | the kernel tools are already Python |
| **Orchestrator (TWO layers)** | **LangGraph** *or* a lean asyncio orchestrator | The orchestrator is NOT just code. Layer 1 = a **deterministic sequencer** running the fixed pipeline steps in order (screen→voices→tally→funnel→committee→plan). Layer 2 = an **intelligent orchestrator (the "Chief")** — a MODEL that interprets the operator's free-form commentary/intent into what to run and with what parameters ("re-run the funnel at sc-floor 72", "challenge the committee on DINO"). Both are essential; the Chief is what makes it agentic rather than a cron script. LangGraph gives the stateful loops, **checkpoint/resume** (SH-R1) and **human-in-the-loop interrupt** (approval gates, H1) for Layer 1, and hosts the Chief for Layer 2; model-agnostic. |
| **Model gateway** | **LiteLLM** | one API across Anthropic + OpenAI + Kimi/Moonshot + local (Ollama/vLLM). This is what makes "other models my runtime hooks to" native. Route per tier. |
| **Scheduler** | **APScheduler** | the 5 cron loops + the #ops interval publish. Alternative: systemd timers, or **Temporal** for enterprise-grade durable/idempotent retries (heavier; maps SH-R5). |
| **Sub-agents (11 voices)** | `asyncio.gather` over 11 model calls | each = voice card + per-voice universe (~10k tok) + memory → nomination JSON, schema-validated. No heavy framework needed. |
| **Tools/connectors** | run as **local MCP servers** (parity with today) or direct Python clients | FMP REST (key) · Tiger `tigeropen` SDK (key) · **IBKR = the awkward one:** run a **Dockerised IB Gateway + IBC** (auto-login/restart; community image e.g. `gnzsnz/ib-gateway-docker`), your code connects locally via **`ib_async`** (the maintained fork of the now-unmaintained `ib_insync`). Ongoing chore = IBKR's daily auto-restart (IBC handles) + weekly re-auth/2FA (needs occasional attention). · Google Drive API (service account) |
| **State/memory** | **git** (truth) + **SQLite** (start) / Postgres (scale) | LangGraph checkpointer can use SQLite/Postgres. Discord channel history IS the durable conversation surface; the DB holds loop/checkpoint/session state. Optional richer memory: Letta/Zep/Mem0. |
| **Cockpit** | **discord.py** | gateway is outbound → no public URL; slash commands, buttons, modals, embeds, file attachments (doc 05) |
| **Secrets** | **sops+age** encrypted files, or OS keyring / HashiCorp Vault | fixes the inline-PAT stop-gap (T2): git PAT, broker creds, API keys, Discord token |
| **Supervision** | **systemd** `Restart=always` (or Docker `restart: always`) | process auto-restart (SH-R1) |
| **Watchdog** | heartbeat → **healthchecks.io** (or a cron on a second box) | dead-man's-switch: absence of check-in = alarm (SH8/SH-R4) |
| **Packaging** | **Docker Compose** (optional) | runtime + local MCP servers + Postgres as containers; clean deploy |

---

## 3. SYSTEM REQUIREMENTS (hardware / infra)

The heavy work is **network-bound API calls, not local compute** — so the box is modest UNLESS you run
local models.

| Resource | Minimum | Comfortable | Notes |
|---|---|---|---|
| CPU | 2 vCPU | 4 vCPU | orchestration + I/O; no GPU needed unless self-hosting a model |
| RAM | 8 GB | 16 GB | Python service + IB Gateway (Java) + local MCP servers + DB |
| Disk | 50 GB SSD | 100 GB SSD | repo + ~6y historical store + logs + Postgres |
| Network | reliable broadband, always-on | low-latency to broker/data | **outbound only** — no static IP or port-forward needed |
| Uptime | must cover 21:30–04:00 SGT (US session) + loops 05:05/08:00/10:00 SGT | 24/7 | home box: add a **UPS**; or use a cloud VM for guaranteed uptime |
| GPU | none | only if running local models (Ollama/vLLM) — then 16–24GB VRAM+ | optional; the Claude/Kimi API path needs no GPU |

**Two viable host options:**
- **Home box (per D-9):** a NUC/mini-PC on a UPS, Ubuntu, always on. Cheapest; you own the data. Risk =
  home power/network — mitigate with UPS + the watchdog + git durability.
- **Cloud VM:** 2–4 vCPU / 8–16 GB / 80 GB SSD (~$20–40/mo tier). Guaranteed uptime, no home-power risk.
  Best for a live book. (GPU tiers only if self-hosting models.)

**External dependencies that must be running:** IB Gateway (headless, auto-login via IBC) for IBKR;
outbound access to Anthropic API, FMP, Tiger, Google Drive, Discord.

---

## 4. COST MODEL (metered API — the point of the move)

The dominant variable cost is the **daily premarket swarm**. Because each voice gets a **trimmed
~10k-token per-voice universe** (not the 170k-token full export), the swarm is cheap:

- **Swarm:** 11 voices × (~10k universe + ~3k card/memory ≈ 13k input) ≈ **~145k input tokens/day**;
  output is small nomination JSON (~1–2k each).
- **Committee:** larger deliberation packet (~30–50k input, Opus), output ~5–10k.
- **Other loops:** control-plane on Haiku (cheap); market-hours intraday on Haiku.

At indicative July-2026 rates (**Opus 4.8 ~$5/M, Sonnet 5 ~$2/M input** — verify at source; output is
higher), with **voices on Sonnet, committee on Opus**, the model spend is on the order of **a few dollars
a day → roughly tens of dollars a month** — i.e. potentially **at or below the $100/mo Max subscription,
with no weekly cap** (O1 solved). Two big levers: **model-tiering** (don't run voices on Opus) and
**prompt caching** (the universe/voice cards are stable within a run — Anthropic's cache discount slashes
the repeated-context cost). Add infra (~$0–40/mo VM) and your existing FMP/broker subscriptions.

**Action:** measure real token counts on the first live premarket run and cost it exactly before
scaling; do NOT assume — instrument it. (I can compute a precise estimate from the actual per-voice
files on request.)

---

## 5. BUILD SEQUENCE (phased — each phase independently testable)

**Phase 0 — Provision & smoke-test.** Host + Ubuntu + Python + `git clone`. Run the kernel selftests
(`python3 tools/alert_universe.py selftest`, `conviction_funnel.py selftest`, `self_heal.py selftest`,
`archive_ledger.py selftest`, `drive_ptj_check.py selftest`). Green = the deterministic core runs here.

**Phase 1 — Model gateway + one headless premarket.** Wire LiteLLM; port the voice + committee spawns
to API calls (isolated, schema-validated). Run a full premarket **headless** (no Discord) end-to-end
producing a valid `plan.json` + `conviction_funnel.json`. This proves the judgment plane on the API.

**Phase 2 — Scheduler + loops + git.** APScheduler fires the 5 loops at the SGT times; each does
read-kernel → run-skill → git push. Verify commits land, DST-safe post-market at 05:05.

**Phase 3 — Tools/connectors.** Stand up FMP / Tiger / IBKR (IB Gateway) / Drive as local MCP servers
or direct clients; preserve the broker preview→confirm two-step and order-path isolation.

**Phase 4 — Discord cockpit (doc 05).** discord.py bot; the ~8 channels; scheduled publishing; slash
commands; #interaction routing; Approve/Reject buttons; render tables as images.

**Phase 5 — Order path + autopilot + audit.** Gatekeeper module as sole order path; `/arm` with modal
confirm; #execution audit stream; kill switch (`/disarm` disarms first).

**Phase 6 — Resilience & secrets.** systemd `Restart=always`; LangGraph checkpoint or a job-state table
for resume (SH-R1); `/recover` re-fires a missed loop (SH-R2); heartbeat watchdog (SH8); secrets vault
(retire the inline PAT).

**Phase 7 — Shadow → go-live.** Run in PREVIEW/paper for a shadow period (per `DRYRUN.md`), reconcile
against the Cowork baseline, then flip autopilot only after a proven window (D-1/D-7 discipline).

---

## 6. WHAT MOVES, WHAT'S NEW

- **Moves unchanged (git):** all skills, tools, contracts, charter, the casting mat (D-77), the
  conviction funnel (D-78/79/80), the self-heal ladder, CONTEXT/PLATFORM_SWITCH/handoff.
- **New (this runtime):** the orchestrator service, LiteLLM gateway, APScheduler, the connector
  clients/MCP servers, the discord.py cockpit, the secrets vault, supervision + watchdog.
- **Retired:** the Cowork scheduled-task triggers, the inline-PAT-in-prompt stop-gap, the Max
  subscription. The native Cowork workflow (doc 04) can run in parallel until Phase 7 cuts over —
  zero rework, same repo.

---

## 7. EFFORT & SEQUENCING (honest)

A competent Python engineer familiar with async + one broker API can stand up Phases 0–2 (headless
runtime producing a plan on the API) in a few days; Phases 3–5 (connectors + Discord + order path) are
the bulk — one to two weeks depending on IBKR/Tiger integration depth; Phases 6–7 (resilience + shadow)
another week plus the shadow period. The critical-path risk is the **broker integrations** (IB Gateway
auth/uptime especially), not the AI — budget accordingly. Start Phase 0–1 to de-risk the model-plane
cost and correctness before committing to the full connector build.
