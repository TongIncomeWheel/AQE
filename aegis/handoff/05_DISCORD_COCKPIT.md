# AEGIS — THE DISCORD COCKPIT (interface spec)
**The operator's multi-channel cockpit · 21 Jul 2026 · interface only — the runtime drives it (see 06)**

Discord is the **presentation + control surface**, not the engine. The self-hosted runtime (doc 06)
publishes to these channels on the scheduler, listens on the interactive ones, records decisions, and
streams execution. If Discord is down the engine keeps running the book and pushing to git; only the
live window is lost. Channels map to the kernel's DESKS/loops — not to individual voices (those are
internal isolated deliberation; their synthesis IS the plan).

---

## 1. CHANNEL MAP

**Publish + command channels** — each tied to a loop/desk, each with a cadence the operator sets:

| Channel | Publishes (on schedule) | Accepts | Kernel source |
|---|---|---|---|
| **#ops** | the `/ops` liveness dashboard at set intervals (aligned to loop heartbeats) — is the machine alive, did loops fire, is state fresh | `/ops`, `/status`, `/recover`, `/arm`, `/disarm` | Operations + Engineering liveness |
| **#premarket** | the plan + conviction funnel (DATA→LENS→VOICES shortlist + contradictions, D-80) at 16:00 SGT; the **Approve/Edit/Reject buttons live here** | `/plan`, questions | Research→Risk / swarm + committee |
| **#market-hours** | held-book risk pages + pod-confirmed runner alerts, as they fire | — | market-hours loop |
| **#post-market** | journal / EOD / P&L at 05:05 SGT | `/status` | Operations |
| **#design-review** | improvement proposals at 08:00 SGT (to STEER) | approve/defer buttons | Engineering & Change |

**#interaction** — the two-way conversational point back to the orchestrator. Free-form requests land
here and the orchestrator answers here for review + conversation: *"premarket deliberation detail on
FBP," "tabular view of my live book," "why did DINO drop out," "re-run the funnel at sc-floor 72."*
Exploratory, non-binding. This is the cockpit's conversational core.

**#decisions** — the append-only LEDGER of the operator's binding calls: plan approve/reject,
engineering fix approved, autopilot arm/disarm. **Actioned in context** (Approve button in #premarket,
`/arm` in #ops) but **recorded here** as the immutable trail — mirrors `charter/decisions_log.md` + the
STEER protocol. Keeps #interaction messy-and-free while decisions stay clean-and-traceable.

**#execution** — read-only order audit. When autopilot is armed, every staging-gatekeeper action
(preview → confirm → fill → post-fill risk line) logs here; previews log here even in manual mode.
Maps to the sole order path (constitution law 1).

~8 channels. Not per-voice (that's noise) — voice-level detail is an on-demand ask in #interaction.

---

## 2. INTERACTION MODEL

- **Slash commands** map 1:1 to the existing command registry (`charter/commands.md`): `/status`
  `/ops` `/plan` `/ap` `/recover` `/repull` `/arm` `/disarm`. Discord-native, discoverable.
- **Buttons / modals** for gated actions: Approve/Edit/Reject the plan; a modal **confirm** on anything
  that arms the gatekeeper (never one-tap for order-arming — see §3).
- **Free-form** in #interaction: the runtime routes the message to the orchestrator (the Chief), which
  answers in-channel. This is where "give me X" requests are served.
- **Rendering rule:** post the decision/summary as a Discord **embed** (colored, structured); post the
  full plan / casting mat / live-book table as a **rendered image or PDF** attached (Discord doesn't do
  wide tables) — reuse the existing HTML flight-recorder / morning-summary cards → image.

---

## 3. SAFETY (order path through the cockpit)

The cockpit must preserve the constitution's one-order-path discipline:
- **Lock the bot to the operator's Discord user ID**; private server; the arm/approve commands reject
  anyone else.
- **Read commands liberal, arm/approve tight.** `/status`/`/ops`/`/plan` are open; `/arm` and order
  approval require a **modal confirm** and are the only path to autopilot.
- **#execution is read-only** and append-only — the audit trail; no commands that place orders live
  anywhere except the gatekeeper module the runtime controls.
- **Kill switch:** `/disarm` (and any kill condition) disarms first, asks later; posts to #decisions.

---

## 4. WHY THIS IS A RUNTIME REQUIREMENT, NOT A DISCORD FEATURE

Every capability above (scheduled publish, interaction routing, decision recording, execution
streaming, approval gating) is work the **runtime** does; Discord just renders it and relays taps. So
this spec is a set of requirements ON the runtime (doc 06): it must be able to publish to N channels on
a schedule, subscribe to M channels for input, gate actions behind confirms, and write an audit stream.
Build it against doc 06's component stack.
