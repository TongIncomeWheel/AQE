#!/usr/bin/env python3
"""Trailing-stop + scale-out engine (D-33) — the piece premarket promised ("trailing per
calculators") but never had. Deterministic (constitution law 4); the Risk desk calls it,
the Execution gatekeeper stages whatever amendment it returns.

POLICY (PM ruling, all-recommended):
  * Hybrid trail: breakeven after +1R, then ratchet up to AQE's fresh daily OPERATIVE stop
    (the structural swing-low/VWAP stop AQE already computes). NEVER lowers — the ratchet
    invariant is the whole point of a trailing stop protecting capital/profit.
  * Milestone locks: after TP1 hit, stop >= entry; after TP2 hit, stop >= TP1.
  * Scale out: take a fraction at TP1 and TP2, run the remainder on the trail.

All parameters come from RB:trailing (parameters.yaml). Pure functions, no I/O.
"""
from __future__ import annotations


def r_multiple(entry: float, price: float, initial_risk_per_share: float) -> float:
    """How many R the position is up (or down). initial_risk_per_share = entry - initial_stop."""
    if initial_risk_per_share <= 0:
        raise ValueError("initial_risk_per_share (entry - initial_stop) must be positive")
    return round((price - entry) / initial_risk_per_share, 3)


def trail_stop(*, entry: float, price: float, current_stop: float,
               initial_risk_per_share: float, aqe_operative_stop: float | None,
               tp1_hit: bool = False, tp2_hit: bool = False, tp1: float | None = None,
               breakeven_trigger_r: float = 1.0, breakeven_buffer_pct: float = 0.0) -> dict:
    """Return the new stop and whether it moved. NEVER returns a stop below current_stop
    (ratchet). NEVER returns a stop at/above price (that's an exit, not a stop) — if the
    structural stop has caught up to price, we flag EXIT_SIGNAL and hold the stop just below.

    Returns: {new_stop, raised(bool), reason, exit_signal(bool)}.
    """
    if initial_risk_per_share <= 0 or entry <= 0 or price <= 0:
        raise ValueError("entry, price, initial_risk_per_share must be positive")
    candidates = [current_stop]           # invariant seed: never below where we are
    reasons = []
    rmult = (price - entry) / initial_risk_per_share

    # 1) breakeven after +1R
    if rmult >= breakeven_trigger_r:
        be = entry * (1 + breakeven_buffer_pct / 100.0)
        if be > current_stop:
            candidates.append(be); reasons.append(f"breakeven@{breakeven_trigger_r}R")

    # 2) structure ratchet — follow AQE's fresh operative stop upward
    exit_signal = False
    if aqe_operative_stop is not None:
        if aqe_operative_stop >= price:
            # structural stop has reached price → the structure that held is gone → exit, don't "stop above price"
            exit_signal = True; reasons.append("structure_reached_price:EXIT")
        elif aqe_operative_stop > current_stop:
            candidates.append(aqe_operative_stop); reasons.append("structure_trail")

    # 3) milestone locks
    if tp1_hit and entry > current_stop:
        candidates.append(entry); reasons.append("lock>=entry@TP1")
    if tp2_hit and tp1 is not None and tp1 > current_stop:
        candidates.append(tp1); reasons.append("lock>=TP1@TP2")

    new_stop = max(candidates)
    # never at/above price
    if new_stop >= price:
        new_stop = current_stop
    new_stop = round(new_stop, 4)
    return {"new_stop": new_stop, "raised": new_stop > current_stop,
            "reason": " + ".join(reasons) if reasons else "no_change",
            "exit_signal": exit_signal, "r_multiple": round(rmult, 3)}


def scale_out(*, shares_held: int, tp1_hit: bool, tp2_hit: bool,
              tp1_done: bool, tp2_done: bool,
              tp1_fraction: float = 0.33, tp2_fraction: float = 0.33) -> dict:
    """How much to sell now at a target. Fractions are of the ORIGINAL position; we only
    scale each target ONCE (tp*_done tracks that). Remainder runs on the trail.
    Returns {scale_shares, tp_level, remainder_runs}."""
    if tp2_hit and not tp2_done:
        n = int(shares_held * tp2_fraction)
        return {"scale_shares": max(n, 0), "tp_level": "TP2", "remainder_runs": True}
    if tp1_hit and not tp1_done:
        n = int(shares_held * tp1_fraction)
        return {"scale_shares": max(n, 0), "tp_level": "TP1", "remainder_runs": True}
    return {"scale_shares": 0, "tp_level": None, "remainder_runs": True}


if __name__ == "__main__":
    # self-test: ratchet invariant + hybrid behaviour
    e, irps = 100.0, 5.0   # entry 100, 1R = $5 (initial stop 95)
    # below 1R: structure can still lift, never lower
    a = trail_stop(entry=e, price=103, current_stop=95, initial_risk_per_share=irps, aqe_operative_stop=97)
    assert a["new_stop"] == 97 and a["raised"], a
    # at +1R: breakeven kicks in
    b = trail_stop(entry=e, price=105, current_stop=97, initial_risk_per_share=irps, aqe_operative_stop=99)
    assert b["new_stop"] == 100, b   # +1R -> breakeven(100) beats structure(99): max(97,100,99)=100
    b2 = trail_stop(entry=e, price=105, current_stop=97, initial_risk_per_share=irps, aqe_operative_stop=98)
    assert b2["new_stop"] == 100, b2  # breakeven wins
    # ratchet: a LOWER operative stop never lowers the stop
    c = trail_stop(entry=e, price=110, current_stop=104, initial_risk_per_share=irps, aqe_operative_stop=101)
    assert c["new_stop"] == 104 and not c["raised"], c
    # exit signal when structure reaches price
    d = trail_stop(entry=e, price=106, current_stop=104, initial_risk_per_share=irps, aqe_operative_stop=106)
    assert d["exit_signal"] and d["new_stop"] == 104, d
    # scale-out once per target
    s = scale_out(shares_held=300, tp1_hit=True, tp2_hit=False, tp1_done=False, tp2_done=False)
    assert s["scale_shares"] == 99 and s["tp_level"] == "TP1", s
    print("trailing_stop self-test PASSED (ratchet, breakeven, structure, exit-signal, scale-out)")
