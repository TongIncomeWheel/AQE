# AEGIS — PHASE 0–1 BUILD CHECKLIST (de-risk the runtime)
**Written for the operator (concepts + plan) with technical steps flagged FOR THE ENGINEER · 21 Jul 2026**

**Goal of Phase 0–1:** stand up a rented VPS that can, on one command, produce a full premarket plan
(the 11-voice swarm → conviction funnel → committee → plan) using the Claude API — with **no Discord,
no live brokers, no scheduling yet**. This proves the *intelligence* works on your own infrastructure
and tells you the *real token cost*, cheaply, before committing to the bigger plumbing. It is the
de-risking step. ~2–4 days of an engineer's time.

---

## HOW ORCHESTRATION ACTUALLY WORKS HERE (read this first)

The runtime has **two layers**, and both get built from Phase 1 — this is not "just code":

1. **The deterministic sequencer** — runs the fixed premarket pipeline in order (universe screen →
   spawn voices → tally → funnel → event filter → committee → plan). The order never changes, so this
   part is code.
2. **The intelligent orchestrator (the "Chief")** — a MODEL that reads your commentary/intent and
   decides what to run and how ("re-run the funnel at sc-floor 72", "challenge the committee on DINO",
   "just show me the live book"). This is the agentic brain that turns your words into orchestrated
   action. In Phase 1 it is minimal (one command = "run premarket"), but it is built as a model-driven
   interpreter FROM THE START, because it is the piece that later makes the whole system respond to you
   in natural language.

Everything below builds toward: the sequencer runs the pipeline, the Chief will front it.

---

## PHASE 0 — Stand up the box, prove the deterministic core

**What you get:** a VPS you own, with the Aegis code on it, and all the "math" parts (screens, funnel,
self-heal, ledgers) passing their built-in self-checks. No AI yet — just proof the foundation runs.

| # | Step (plain) | For the engineer |
|---|---|---|
| 0.1 | **Rent a VPS.** Ubuntu, US-East, mid-size. | Ubuntu 22.04/24.04 LTS · 4 vCPU / 8–16 GB / 80 GB SSD · US-East region (near brokers/data) · **SSH-key login only**, password login disabled, firewall on (outbound + SSH in only). Reputable host (Hetzner/DigitalOcean/Linode/Vultr/Lightsail). |
| 0.2 | **Install the basics.** | `python3.11+`, `git`, `pip`/`uv`; Docker + Docker Compose (recommended — used later for IB Gateway). |
| 0.3 | **Put the Aegis code on the box.** | `git clone` the private repo via a **read/write deploy key** (not the inline PAT). Working dir e.g. `/opt/aegis`. |
| 0.4 | **Run the self-checks.** Each math tool has a built-in test; all must pass. | `python3 tools/alert_universe.py selftest` · `conviction_funnel.py selftest` · `self_heal.py selftest` · `archive_ledger.py selftest` · `drive_ptj_check.py selftest`. |

**Done when:** every selftest prints PASS. The deterministic core runs on your infrastructure.

---

## PHASE 1 — Wire the intelligence, produce ONE plan on the API

**What you get:** you (or the engineer) type one command on the VPS, and it runs a full premarket — the
11 voices, the funnel, the committee, the plan — using the Claude API, and writes a real `plan.json`.
Still headless (no Discord, no live brokers). Then you read the actual cost.

| # | Step (plain) | For the engineer |
|---|---|---|
| 1.1 | **Get an Anthropic API key + set a spend cap.** | Anthropic Console → API key → set a monthly usage limit (safety). Add OpenAI/Kimi/Moonshot keys later if wanted — not needed for Phase 1. |
| 1.2 | **Install the model gateway (LiteLLM).** The piece that lets the runtime call Claude now and swap models later. | LiteLLM config with tiers: `voices→Sonnet`, `committee→Opus`, `control→Haiku`. One interface the kernel calls; model choice is config, not code. Enable **prompt caching** (big cost lever). |
| 1.3 | **Build the two-layer orchestrator.** The code sequencer + the intelligent Chief in front (minimal for now). | (a) A Python sequencer that runs the premarket skill steps in order. (b) A thin "Chief" entrypoint = one model call that takes an instruction ("run premarket") and dispatches — built as an interpreter so it extends to free-form commentary later. |
| 1.4 | **Port the voices + committee to API calls.** Each voice = one call; run all 11 at once; committee = one Opus call. | Each voice: its `agents/voice-*.md` card + its **trimmed per-voice universe (~10k tokens)** + its `voice_memory` block → returns `nomination.json`, **validated against `contracts/nomination.schema.json`**. `asyncio.gather` the 11. Committee: the deliberation packet → `committee.json` vs its schema. |
| 1.5 | **Feed it a saved AQE export** (no live data wiring yet). | Drop a real `aqe_daily_export.json` on disk; point the run at it. Live Drive/FMP/broker pulls are Phase 3. |
| 1.6 | **Run it end-to-end → a real plan.** | One command produces `data/sod/DATE/{universe,nominations/*,tally,conviction_funnel,committee,plan}.json`, each schema-valid. |
| 1.7 | **Read the real cost.** | Anthropic Console usage → measured input/output tokens for the run → your true daily model cost. Compare to the ~$1–3/day estimate. |

**Done when:** one command produces a valid, schema-passing premarket plan on the Claude API, and you
have the *measured* cost in hand.

---

## WHAT PHASE 0–1 DELIBERATELY LEAVES OUT (on purpose)

- **No Discord** — that's Phase 4.
- **No live broker/data connections** — Phase 3; Phase 1 uses a saved AQE export.
- **No scheduling** — Phase 2; you run it by hand for now.
- **No orders / no IBKR** — Phase 5. (IBKR wiring, when you get there: a Dockerised **IB Gateway +
  IBC** on the VPS, your code connects locally via **`ib_async`** — the maintained fork of `ib_insync`;
  the one ongoing chore is IBKR's weekly re-login. Not needed until you go live.)

This ordering is deliberate: **prove the brain and the cost first, cheaply**, before building the
plumbing that takes real time (the broker integrations, not the AI, are the critical path).

---

## WHAT YOU NEED TO PROVIDE / DECIDE

- A VPS provider + region (recommend US-East, reputable host).
- An Anthropic API account with a spend cap.
- An engineer for ~2–4 days for Phase 0–1 — OR ask and I can generate the actual setup scripts, the
  LiteLLM config, and the voice-spawn/orchestrator code so the engineer is assembling, not designing.

## DEFINITION OF SUCCESS FOR THE WHOLE OF PHASE 0–1

You sit at the VPS, run one command, and watch it produce today's Aegis plan — the voices deliberated,
the funnel shortlisted, the committee ruled — entirely on your own box, on metered API, for a measured
handful of cents. That is the proof that the migration works and is affordable, before a dollar goes
into brokers, Discord, or scheduling.
