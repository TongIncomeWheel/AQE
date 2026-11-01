#!/usr/bin/env python3
"""Two-step position sizing — the ONLY place sizing arithmetic lives (constitution law 4).
Step 1: R-size. Step 2: vol-cap. Final = smaller of the two. Both steps mandatory.
All parameters come from rulebook.yaml; callers pass values, never re-derive rules.
"""
import math

def r_size(r_budget_usd: float, entry: float, stop: float) -> int:
    if r_budget_usd <= 0 or entry <= 0:
        raise ValueError("r_budget and entry must be positive")
    if entry <= stop:
        raise ValueError("entry must be above stop for a long")
    return math.floor(r_budget_usd / (entry - stop))

def vol_cap_size(entry: float, vol_30d_ann: float, vol_cap_pct: float, dyncap: float) -> int:
    if not (0 < vol_30d_ann < 3):   # DS-F9: catches zero, negatives, and percent-passed-as-45 unit errors
        raise ValueError(f"vol_30d_ann {vol_30d_ann} outside sane band (0,3) — pass a decimal fraction")
    if dyncap <= 0:
        raise ValueError("dyncap must be positive")
    daily_vol = vol_30d_ann / math.sqrt(252)
    cap_usd = vol_cap_pct / 100.0 * dyncap
    return math.floor(cap_usd / (entry * daily_vol))

def size(dyncap: float, one_r_pct: float, r_multiple: float, entry: float, stop: float,
         vol_30d_ann: float, vol_cap_pct: float) -> dict:
    r_budget = dyncap * one_r_pct / 100.0 * r_multiple
    s_r = r_size(r_budget, entry, stop)
    s_v = vol_cap_size(entry, vol_30d_ann, vol_cap_pct, dyncap)
    shares = min(s_r, s_v)
    return {"shares": shares, "shares_r": s_r, "shares_volcap": s_v,
            "capped_by": "vol" if s_v < s_r else "r",
            "risk_usd": round(shares * (entry - stop), 2), "r_budget_usd": round(r_budget, 2)}

def post_fill_check(qty: int, fill: float, stop: float, r_budget_usd: float, tol_usd: float = 50.0) -> dict:
    actual = qty * (fill - stop)
    return {"actual_risk_usd": round(actual, 2), "delta_usd": round(actual - r_budget_usd, 2),
            "flag": abs(actual - r_budget_usd) > tol_usd}
