---
name: market_hours
description: Aegis process skill — MARKET HOURS (21:30–04:00 SGT; autonomous — RB:schedule). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: MARKET HOURS (21:30–04:00 SGT; autonomous — RB:schedule)
Owner: Market-Hours Orchestrator. Principle: **code watches, agents wake** (RB:schedule.market_watch_mode).
**Model note (D-16):** this orchestrator (and the AQE watcher it wraps) is control plane — RB:model_tiers.control. Assembling the live pack and tallying the pod's verdict is sequencing, not judgment. The pod's voices (step 3c) are the same pinned RB:model_tiers.judgment agent files as the premarket swarm — spawning them on the live pack costs nothing extra to wire, the tier travels with the agent file, not with who calls it.

1. The AQE alert engine (repo, existing) polls prices for the approved alert universe. No timed AI loops.
2. On trigger fire: orchestrator wakes with the alert + the approved plan entry for that name only.
3. Re-validation (short, bounded): plan conditions still true (spot vs trigger, event check, gap sanity)? Uses live spot per RB:data_sources.
3b. **Live data pack (D-13).** Assemble before any order request: live spot · distance to stop/targets from the name's feed bracket · the name's full feed record · **live sector pulse** (`tools/srm_live.py` — 11 sector ETFs + macro proxies, TAILWIND/NEUTRAL/HEADWIND + RISK_ON/OFF tone) · macro proxies. Pulse unavailable = NEUTRAL-UNKNOWN, said out loud.
3c. **Intraday Review Pod (D-13).** The alert re-convenes a BOUNDED committee: the voices that nominated this name + Druckenmiller (macro) + the Detect lens — each spawned isolated with the live pack, returning one line: **CONFIRM** or **STAND_DOWN** + reason. Majority CONFIRM required to proceed. The pod may NOT add names, may NOT change brackets or sizes, may NOT resurrect a stood-down name — confirm or stand down, nothing else. A sector HEADWIND or RISK_OFF tone is exactly the kind of reason a pod stands down. Verdict + reasons written to intraday/DATE/pod/.
4. Action by phase (RB:orders / RB:autopilot): Phase 1 — if the PM pre-staged the bracket, log the fire and monitor; if not staged, record MISSED-BY-DESIGN with price path. Any order-shaped need routes as a REQUEST to staging-gatekeeper — this orchestrator can never stage (feeds Design & Review; this is the evidence that will justify Phase 2). Phase 2 (when enabled) — auto-stage within caps, notify.
5. Fills observed via broker pull → held-book memory updated (entry, stop, date, trigger, TPs), post-fill protocol runs in staging-gatekeeper (its owner), not here.
6. Every wake, one line to the overnight log — nothing else. No commentary, no re-deliberation of the plan.

## ON FAILURE (RB:exceptions; records to data/intraday/DATE/exceptions/)
- 21:25 liveness check: alert engine not alive → PAGE IMMEDIATELY (your call: fix, stay up, or accept broker stops for the night). BL-018.
- Live spot unavailable at re-validation → that trigger STANDS DOWN, logged MISSED_BY_FAILURE; never confirm on stale spot.
- Broker unreachable while ARMED → DISARM FIRST, then page. Preview mode: log and wait for the next fire.
- Gatekeeper cannot READ any check file → that is a refusal (fail-closed), not an override opportunity.
- Any anomaly at all while armed → DISARM FIRST, ask questions at 10am.
