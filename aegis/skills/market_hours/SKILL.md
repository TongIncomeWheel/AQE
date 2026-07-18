---
name: market_hours
description: Aegis process skill — MARKET HOURS (21:30–04:00 SGT; autonomous — RB:schedule). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: MARKET HOURS (21:30–04:00 SGT; autonomous — RB:schedule)
Owner: Market-Hours Orchestrator. Principle: **code watches, agents wake** (RB:schedule.market_watch_mode).

1. The AQE alert engine (repo, existing) polls prices for the approved alert universe. No timed AI loops.
2. On trigger fire: orchestrator wakes with the alert + the approved plan entry for that name only.
3. Re-validation (short, bounded): plan conditions still true (spot vs trigger, event check, gap sanity)? Uses live spot per RB:data_sources.
4. Action by phase (RB:orders / RB:autopilot): Phase 1 — if the PM pre-staged the bracket, log the fire and monitor; if not staged, record MISSED-BY-DESIGN with price path. Any order-shaped need routes as a REQUEST to staging-gatekeeper — this orchestrator can never stage (feeds Design & Review; this is the evidence that will justify Phase 2). Phase 2 (when enabled) — auto-stage within caps, notify.
5. Fills observed via broker pull → held-book memory updated (entry, stop, date, trigger, TPs), post-fill protocol runs in staging-gatekeeper (its owner), not here.
6. Every wake, one line to the overnight log — nothing else. No commentary, no re-deliberation of the plan.
