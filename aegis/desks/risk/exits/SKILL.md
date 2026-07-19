---
name: exits
description: Exit & trailing-stop management, owned by the Risk desk (D-33). Decides — for every HELD position — the trailing stop, take-profit scale-out, and rotation. Deterministic trail/scale via tools/calculators/trailing_stop.py; the DECISION is Risk's, the PLACEMENT is Execution's staging-gatekeeper. Never places an order itself.
---

# EXITS & TRAILING STOPS — the held-book risk engine (Risk desk, D-33)

## Why this exists
The book doesn't only buy — it exits for stop, target, and rotation, and it trails stops to protect capital and lock profit. That was previously a dangling promise ("trailing per calculators" with no calculator). This skill is the exit side, given the same rigor as entries. **Exits are priced FIRST every premarket, before new ideas are sized** — what the held book frees or protects sets the capital available for new buys.

## Inputs (per held position, from the Aegis PTJ + AQE)
entry · current stop · live/close price · initial risk-per-share (entry − initial stop = 1R) · AQE's fresh daily operative stop · TP1/2/3 and which are hit · shares held · which targets already scaled.

## What I decide (per position)
1. **Trailing stop** — `trailing_stop.trail_stop(...)` (RB:trailing): breakeven after +1R, then ratchet up to AQE's fresh operative stop, milestone-lock after TP1 (≥entry) and TP2 (≥TP1). **It NEVER lowers the stop** (the ratchet invariant) and never sits at/above price — if structure has reached price it returns an EXIT signal instead. Output: `stop_new` if raised → a TIGHTEN_STOP action for Execution.
2. **Take-profit scale-out** — `trailing_stop.scale_out(...)` (RB:trailing.scale_out): take the configured fraction at TP1 and TP2 (once each), run the remainder on the trail. Output: SCALE_OUT action with tp_level + scale_shares.
3. **Rotation** — a held name exits when EITHER Research flags thesis decay (EXIT-CASE) OR a new idea is materially stronger and capital is needed; I do the head-to-head capital math (freed dynCap vs the new idea's R-need). Output: EXIT action with the reason.

## Cadence (RB:trailing.cadence)
- **Post-market (daily):** recompute the trail for every held name for next session; stage any raise.
- **Premarket:** re-price the held book first; fold trail/TP/rotation into the plan's held_actions before new sizing.
- **Market hours:** on a target-hit alert, tighten the trail and issue the scale-out at once (protect the spike).

## Hard rules
- I DECIDE; I never place. Every TIGHTEN_STOP / SCALE_OUT / EXIT goes to Execution's staging-gatekeeper as a request (constitution law 1, RB:orders.sole_path).
- The stop only ever ratchets up. A lowered stop is a breach the auditor checks.
- All on the AEGIS book only (D-21), computed on the Aegis PTJ, never co-mingled totals.
