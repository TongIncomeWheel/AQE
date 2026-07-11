"""Economics of the two wheel-entry structures: the cash-secured put and the
defined-risk put credit spread.

Pure functions over one contract (CSP) or a two-leg pair (spread) + the pricing
assumptions. Each returns a flat dict of the numbers a seller actually decides on:
credit, collateral/max-loss, static + annualised yield, breakeven, downside cushion,
probability of profit, the daily theta credit, and the model edge vs the quote.
"""

from __future__ import annotations

import math

from . import config as C
from .greeks import bs_greeks, prob_below, year_fraction


def _mid(bid, ask):
    """Quote midpoint, or None when the two-sided market is missing."""
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return 0.5 * (bid + ask)


def _fill(bid, ask, fair, mode):
    """The credit a seller books, per share.

    mode 'mid'  → quote mid (fair-ish assumption)
         'bid'  → the bid (conservative: a marketable sell hits the bid)
         'fair' → the BS model value (when there's no live quote)
    Falls back to fair whenever the requested price is unavailable.
    """
    mid = _mid(bid, ask)
    if mode == "bid" and bid and bid > 0:
        return bid
    if mode == "mid" and mid is not None:
        return mid
    if mode == "fair" and fair is not None:
        return fair
    return mid if mid is not None else fair


def _spread_pct(bid, ask):
    mid = _mid(bid, ask)
    if mid is None or mid <= 0:
        return None
    return (ask - bid) / mid


def analyze_csp(contract: dict, r=None, q=None, fill="mid",
                cash_slot=None) -> dict:
    """Cash-secured short-put economics for one contract.

    `contract` needs: ticker, spot, strike, iv, and either dte or expiry-derived
    dte; optionally bid, ask, oi, volume. Returns a flat metrics dict (never raises
    on a well-formed contract; missing inputs degrade to None).
    """
    S = contract.get("spot")
    K = contract.get("strike")
    iv = contract.get("iv")
    dte = contract.get("dte")
    bid, ask = contract.get("bid"), contract.get("ask")
    if S is None or K is None or dte is None:
        return {"ticker": contract.get("ticker"), "valid": False,
                "reason": "missing spot/strike/dte"}

    T = year_fraction(dte)
    g = bs_greeks(S, K, T, iv, "PUT", r, q) if iv else {}
    fair = g.get("price")
    credit = _fill(bid, ask, fair, fill)          # per share
    if credit is None:
        return {"ticker": contract.get("ticker"), "valid": False,
                "reason": "no price (no quote and no iv)"}

    collateral = K * 100.0                         # cash-secured, per contract
    credit_pc = credit * 100.0
    static_yield = credit / K if K else None
    annual_yield = (static_yield * C.YEAR_DAYS / dte) if (static_yield and dte) else None
    breakeven = K - credit
    cushion = (S - breakeven) / S if S else None

    # Probabilities (risk-neutral). Assignment = finish below the short strike.
    assign_prob = prob_below(S, K, T, iv, r, q) if iv else None
    pop = (1.0 - prob_below(S, breakeven, T, iv, r, q)) if iv else None  # finish above BE
    pop_not_assigned = (1.0 - assign_prob) if assign_prob is not None else None

    theta_day = (-g["theta"] * 100.0) if g.get("theta") is not None else None  # seller's daily credit
    theta_eff = (theta_day / collateral) if theta_day is not None else None
    mid = _mid(bid, ask)
    edge = ((credit - fair) * 100.0) if fair is not None else None  # >0 = sell above model
    slot = C.CAPITAL / C.MAX_POSITIONS if cash_slot is None else cash_slot
    max_contracts = int(slot // collateral) if collateral else 0

    return {
        "ticker": contract.get("ticker"), "strike": K, "dte": dte,
        "structure": "CSP", "valid": True,
        "spot": S, "iv": iv,
        "delta": g.get("delta"), "abs_delta": abs(g["delta"]) if g.get("delta") is not None else None,
        "gamma": g.get("gamma"), "vega": g.get("vega"),
        "fair_value": _round(fair), "market_mid": _round(mid),
        "bid": bid, "ask": ask, "spread_pct": _round(_spread_pct(bid, ask), 4),
        "credit_per_share": _round(credit), "credit_per_contract": _round(credit_pc, 2),
        "collateral": _round(collateral, 2),
        "static_yield": _round(static_yield, 4), "annual_yield": _round(annual_yield, 4),
        "breakeven": _round(breakeven), "downside_cushion": _round(cushion, 4),
        "assignment_prob": _round(assign_prob, 4), "pop": _round(pop, 4),
        "pop_not_assigned": _round(pop_not_assigned, 4),
        "theta_credit_day": _round(theta_day, 2), "theta_efficiency": _round(theta_eff, 6),
        "edge_vs_model": _round(edge, 2),
        "max_contracts": max_contracts,
        "oi": contract.get("oi"), "volume": contract.get("volume"),
    }


def analyze_put_spread(short_leg: dict, long_leg: dict, spot=None,
                       r=None, q=None, fill="mid", risk_budget=None) -> dict:
    """Put credit spread: sell `short_leg` (higher strike), buy `long_leg` (lower).

    Each leg dict needs: strike, iv, dte, and optionally bid/ask. `spot` (shared
    underlying) may be passed once or read from either leg. Defined-risk: collateral
    = max loss.
    """
    S = spot if spot is not None else (short_leg.get("spot") or long_leg.get("spot"))
    Ks, Kl = short_leg.get("strike"), long_leg.get("strike")
    dte = short_leg.get("dte") or long_leg.get("dte")
    if S is None or Ks is None or Kl is None or dte is None or Kl >= Ks:
        return {"valid": False, "reason": "need spot + short>long strikes + dte"}

    T = year_fraction(dte)
    gs = bs_greeks(S, Ks, T, short_leg.get("iv"), "PUT", r, q) if short_leg.get("iv") else {}
    gl = bs_greeks(S, Kl, T, long_leg.get("iv"), "PUT", r, q) if long_leg.get("iv") else {}
    short_credit = _fill(short_leg.get("bid"), short_leg.get("ask"), gs.get("price"), fill)
    long_debit = _fill(long_leg.get("bid"), long_leg.get("ask"), gl.get("price"), fill)
    if short_credit is None or long_debit is None:
        return {"valid": False, "reason": "no price on a leg"}

    net_credit = short_credit - long_debit         # per share
    width = Ks - Kl
    max_profit = net_credit * 100.0
    max_loss = (width - net_credit) * 100.0
    breakeven = Ks - net_credit
    rrr = (max_profit / max_loss) if max_loss > 0 else None      # reward : risk
    annual_yield = (rrr * C.YEAR_DAYS / dte) if (rrr and dte) else None
    pop = (1.0 - prob_below(S, breakeven, T, short_leg.get("iv"), r, q)) \
        if short_leg.get("iv") else None
    net_theta = None
    if gs.get("theta") is not None and gl.get("theta") is not None:
        net_theta = (-gs["theta"] + gl["theta"]) * 100.0        # seller's daily credit
    budget = C.RISK_BUDGET if risk_budget is None else risk_budget
    contracts = int(budget // max_loss) if max_loss > 0 else 0

    return {
        "ticker": short_leg.get("ticker"), "structure": "PUT_SPREAD", "valid": True,
        "spot": S, "dte": dte, "short_strike": Ks, "long_strike": Kl, "width": width,
        "short_delta": gs.get("delta"), "abs_delta": abs(gs["delta"]) if gs.get("delta") is not None else None,
        "net_credit_per_share": _round(net_credit), "net_credit": _round(max_profit, 2),
        "max_profit": _round(max_profit, 2), "max_loss": _round(max_loss, 2),
        "collateral": _round(max_loss, 2),
        "rrr": _round(rrr, 3), "static_yield": _round(rrr, 3),
        "annual_yield": _round(annual_yield, 4),
        "breakeven": _round(breakeven), "pop": _round(pop, 4),
        "theta_credit_day": _round(net_theta, 2),
        "theta_efficiency": _round((net_theta / max_loss) if (net_theta is not None and max_loss > 0) else None, 6),
        "max_contracts": contracts,
    }


def _round(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) else x
