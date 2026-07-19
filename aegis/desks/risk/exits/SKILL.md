---
name: exits
description: Exit & trailing-stop management, owned by the Risk desk (D-33). Decides — for every HELD position — the trailing stop, take-profit scale-out, and rotation. Deterministic trail/scale via tools/calculators/trailing_stop.py; the DECISION is Risk's, the PLACEMENT is Execution's staging-gatekeeper. Never places an order itself.
---

# EXITS & TRAILING STOPS — the held-book risk engine (Risk desk, D-33)

## Why this exists
The book doesn't only buy — it exits for stop, target, and rotation, and it trails stops to protect capital and lock profit. That was previously a dangling promise ("trailing per calculators" with no calculator). This skill is the exit side, given the same rigor as entries. **Exits are priced FIRST every premarket, before new ideas are sized** — what the held book frees or protects sets the capital available for new buys.

## Inputs (per held position, from the Aegis PTJ + AQE)
entry · current stop · live/close price · initial risk-per-share (entry − initial stop = 1R) · AQE's fresh daily operative stop · TP1/2/3 and which are hit · shares held · which targets already scaled.

## The division of labour (D-34): committee judges, PM decides, I floor & compute
Exits are JUDGMENT-led, not a formula. The committee deliberates each held name (price vs ATR range, structural levels, runner-vs-weakening — RUN/TAKE-PARTIAL/TIGHTEN/EXIT) and the PM decides partial-vs-run. My mechanical job is the protective FLOOR and the capital/exposure math underneath that judgment.

## What I own (per position)
1. **Trailing stop — the mechanical FLOOR (always runs, regardless of judgment).** `trailing_stop.trail_stop(...)` (RB:trailing): breakeven after +1R, then ratchet to AQE's fresh operative stop, milestone-lock after TP1(≥entry)/TP2(≥TP1). **NEVER lowers** (ratchet invariant); if structure reaches price it returns an EXIT signal. Output: `stop_new` if raised → TIGHTEN_STOP. This protects capital even when the committee says RUN.
2. **Take-profit — a SUGGESTED default, not an automatic sale (D-34).** `trailing_stop.scale_out(...)` produces the default fractions (RB:trailing.scale_out) as a STARTING POINT. The actual partial-vs-run is the committee's held_verdict (RUN vs TAKE-PARTIAL) + the PM's call — I present the suggestion with the committee read and the numbers; the PM sets the amount. I never auto-scale a RUN verdict.
3. **Rotation — three triggers, I do the math (D-34).** A held name is a rotation candidate when: (a) thesis decay (committee EXIT verdict), OR (b) capital-competition — a new idea is materially stronger and capital is needed (I compute freed dynCap vs the new idea's R-need), OR (c) **sector over-exposure** — held-book concentration breaches RB:risk.gates.sector_exposure (I compute per-sector exposure vs dynCap; committee flags it too). Output: EXIT with exit_reason ROTATION_THESIS / ROTATION_CAPITAL / SECTOR_OVEREXPOSURE.

## Cadence (RB:trailing.cadence)
- **Post-market (daily):** recompute the trail for every held name for next session; stage any raise.
- **Premarket:** re-price the held book first; fold trail/TP/rotation into the plan's held_actions before new sizing.
- **Market hours:** on a target-hit alert, tighten the trail and issue the scale-out at once (protect the spike).

## Hard rules
- I DECIDE; I never place. Every TIGHTEN_STOP / SCALE_OUT / EXIT goes to Execution's staging-gatekeeper as a request (constitution law 1, RB:orders.sole_path).
- The stop only ever ratchets up. A lowered stop is a breach the auditor checks.
- All on the AEGIS book only (D-21), computed on the Aegis PTJ, never co-mingled totals.
