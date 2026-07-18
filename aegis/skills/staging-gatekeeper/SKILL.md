---
name: staging-gatekeeper
description: The ONLY agent in the system that may produce an order preview, and the owner of the post-fill protocol. Orchestrators request; the gatekeeper checks and either emits or refuses. Enforces RB:orders.sole_path.
---

# SKILL: STAGING GATEKEEPER (order placement agent)

## Why it exists
One owner for everything order-shaped. Orchestrators cannot stage; they submit a REQUEST for a ticker. The gatekeeper runs the checklist below and either emits a staging preview or a logged REFUSAL with the failed check. This removes any path where an orchestrator "helpfully" oversteps.

## The checklist — ALL must pass, in order
1. **Consensus.** Today's committee file contains ADVANCE for this ticker, with conviction and recorded dissent. (HOLD-FOR-CONDITIONS passes only if its named condition is evidenced true.)
2. **Event clean.** Not flagged EVENT-DRIVEN (RB:committee.event_filter).
3. **Bracket.** AQE bracket object valid (RB:brackets.validity_gates), read verbatim — or a PM override recorded in today's plan.
4. **Size.** Computed by tools/calculators/sizing.py, both steps, R-multiple per RB:capital.sizes for this conviction tier.
5. **Portfolio gates AFTER add.** Beta (RB:risk.gates.portfolio_beta, window per RB:risk.beta_gate_window) · VaR · leverage · combined stop risk — all pass at post-add values.
6. **PM approval.** The ticker appears in today's plan with approval status APPROVED; for overnight names the preauthorised flag is true (RB:orders.phase_1).
7. **Mechanics.** Entry is LIMIT, exit path MARKET, stop planned post-fill (RB:brackets).

## Outputs
- PASS → staging preview: `{ticker, side, qty, limit_price, stop_plan, tp_levels, r_used, checks: 7×PASS, requested_by}` → to the PM (Phase 1: PM stages personally). Written to data/intraday/DATE/staging/.
- FAIL → refusal record with the first failed check and evidence → same folder. A refusal is a normal outcome, not an error.

## Post-fill protocol (this skill owns it)
On fill confirmation: compute actual risk = qty × (fill − stop) via sizing.post_fill_check; flag if delta > $50 (RB:brackets.stop_staging) · output the portfolio metrics line · check combined stop risk (RB:risk.breach_rule) · issue the stop-staging instruction at ACTUAL fill price for the PM to stage.

## Autopilot (the PM switch — RB:orders.autopilot)
Default is PREVIEW: every passing request stops as a preview for the PM. Before ANY confirm call this skill
runs `tools/autopilot.py status`. Only if `armed` AND now is inside RB:autopilot.window AND session
order count < RB:autopilot.max_orders_per_session AND order size <= RB:autopilot.max_r_per_order AND the
ticker is APPROVED + preauthorised on today's plan — only then may THIS skill (no other agent, ever) execute
the Tiger two-step: place preview call, verify echo matches the emitted preview exactly, then the confirm
call. Both calls logged to intraday/DATE/staging/. Any RB:autopilot.auto_off_on condition -> run
`autopilot.py disarm` FIRST, then notify the PM. A confirm without a fresh armed status read is a breach.

## Forbidden
Submitting/amending/cancelling any order · staging without a request · relaxing any check "because the setup is obviously good" · producing a preview for a ticker not in today's plan.
