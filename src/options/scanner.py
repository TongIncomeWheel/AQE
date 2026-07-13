"""Theta scanner + best-RRR selection over a set of IBKR-sourced put contracts.

Given a flat list of put contracts (each {ticker, spot, strike, dte, iv, bid, ask,
oi, volume}), rank the cash-secured puts worth selling for the wheel, auto-build the
defined-risk put credit spreads, and pick the best risk/reward. Pure — the caller
supplies the contracts (fetched from the IBKR MCP).
"""

from __future__ import annotations

from . import config as C
from .csp import analyze_csp, analyze_put_spread
from .greeks import bs_greeks, implied_vol, year_fraction


# ── Single-contract calculator ──────────────────────────────────────────────
def calculator(contract: dict, r=None, q=None, fill="mid", cash_slot=None) -> dict:
    """Full calculator detail for one contract: BS fair value + Greeks + (for a
    PUT) the cash-secured economics. If IV is missing but a quote is present, IV is
    backed out of the mid first so the Greeks still populate."""
    c = dict(contract)
    right = (c.get("right") or "PUT").upper()
    S, K, dte = c.get("spot"), c.get("strike"), c.get("dte")
    if c.get("iv") is None and None not in (S, K, dte):
        mid = _mid(c.get("bid"), c.get("ask"))
        if mid is not None:
            c["iv"] = implied_vol(mid, S, K, year_fraction(dte), right, r, q)
    out = {"ticker": c.get("ticker"), "right": right, "iv_used": c.get("iv")}
    if None not in (S, K, dte) and c.get("iv"):
        g = bs_greeks(S, K, year_fraction(dte), c["iv"], right, r, q)
        out["greeks"] = {k: _round(g[k], 4) for k in
                         ("delta", "gamma", "vega", "rho") if g.get(k) is not None}
        out["greeks"]["theta_day"] = _round(g.get("theta"), 4)
        out["fair_value"] = _round(g.get("price"))
        out["market_mid"] = _round(_mid(c.get("bid"), c.get("ask")))
    if right == "PUT":
        out["csp"] = analyze_csp(c, r=r, q=q, fill=fill, cash_slot=cash_slot)
    return out


# ── CSP theta scanner ───────────────────────────────────────────────────────
def scan_csps(contracts, r=None, q=None, fill="mid", cash_slot=None,
              delta_min=None, delta_max=None, dte_min=None, dte_max=None,
              min_pop=None, min_annual_yield=None, min_oi=None,
              max_spread_pct=None, rank_key=None) -> dict:
    """Analyse every put, split into passed/rejected against the wheel filters,
    and rank the survivors. Filter defaults come from config; override per call.

    Returns {"passed": [...ranked], "rejected": [{...,"reasons":[...]}]}.
    """
    delta_min = C.CSP_DELTA_MIN if delta_min is None else delta_min
    delta_max = C.CSP_DELTA_MAX if delta_max is None else delta_max
    dte_min = C.CSP_DTE_MIN if dte_min is None else dte_min
    dte_max = C.CSP_DTE_MAX if dte_max is None else dte_max
    min_pop = C.CSP_MIN_POP if min_pop is None else min_pop
    min_annual_yield = C.CSP_MIN_ANNUAL_YIELD if min_annual_yield is None else min_annual_yield
    min_oi = C.CSP_MIN_OI if min_oi is None else min_oi
    max_spread_pct = C.CSP_MAX_SPREAD_PCT if max_spread_pct is None else max_spread_pct
    rank_key = C.SCAN_RANK_KEY if rank_key is None else rank_key

    passed, rejected = [], []
    for con in contracts:
        m = analyze_csp(con, r=r, q=q, fill=fill, cash_slot=cash_slot)
        if not m.get("valid"):
            rejected.append({**m, "reasons": [m.get("reason", "invalid")]})
            continue
        reasons = []
        ad = m.get("abs_delta")
        if ad is None or ad < delta_min or ad > delta_max:
            reasons.append(f"delta {ad} outside [{delta_min},{delta_max}]")
        if m["dte"] < dte_min or m["dte"] > dte_max:
            reasons.append(f"dte {m['dte']} outside [{dte_min},{dte_max}]")
        pna = m.get("pop_not_assigned")
        if pna is not None and pna < min_pop:
            reasons.append(f"POP(not assigned) {pna} < {min_pop}")
        ay = m.get("annual_yield")
        if ay is None or ay < min_annual_yield:
            reasons.append(f"annual_yield {ay} < {min_annual_yield}")
        if m.get("oi") is not None and m["oi"] < min_oi:
            reasons.append(f"oi {m['oi']} < {min_oi}")
        sp = m.get("spread_pct")
        if sp is not None and sp > max_spread_pct:
            reasons.append(f"spread {sp} > {max_spread_pct}")
        (passed if not reasons else rejected).append(
            m if not reasons else {**m, "reasons": reasons})
    passed = rank(passed, rank_key)
    return {"passed": passed, "rejected": rejected}


# ── Put credit spreads (auto-paired, defined risk) ──────────────────────────
def build_put_spreads(contracts, width=None, r=None, q=None, fill="mid",
                      risk_budget=None, min_rrr=None, rank_key="annual_yield") -> list:
    """Pair each put with a long put ~`width` below (same ticker+dte), analyse the
    credit spread, keep those clearing `min_rrr`, and rank. Legs are matched within
    the same (ticker, dte) group; the nearest available strike ≥ width below wins."""
    width = C.SPREAD_DEFAULT_WIDTH if width is None else width
    min_rrr = C.SPREAD_MIN_RRR if min_rrr is None else min_rrr

    groups: dict[tuple, list] = {}
    for c in contracts:
        if c.get("strike") is None or c.get("dte") is None:
            continue
        groups.setdefault((c.get("ticker"), c.get("dte")), []).append(c)

    spreads = []
    for (_tk, _dte), legs in groups.items():
        legs = sorted(legs, key=lambda x: x["strike"])
        strikes = [l["strike"] for l in legs]
        for short in legs:
            target = short["strike"] - width
            # nearest long strike at or below target (defined width, capped risk)
            long = None
            for l in reversed(legs):
                if l["strike"] <= target + 1e-9 and l["strike"] < short["strike"]:
                    long = l
                    break
            if long is None:
                continue
            s = analyze_put_spread(short, long, spot=short.get("spot"),
                                   r=r, q=q, fill=fill, risk_budget=risk_budget)
            if s.get("valid") and (s.get("rrr") or 0) >= min_rrr:
                spreads.append(s)
    return rank(spreads, rank_key)


# ── Ranking + selection ─────────────────────────────────────────────────────
def rank(rows, key=None):
    """Descending sort by a numeric metric; rows missing the key sink to the end."""
    key = C.SCAN_RANK_KEY if key is None else key
    return sorted(rows, key=lambda r: (r.get(key) is not None, r.get(key) or 0),
                  reverse=True)


def best(rows, key=None):
    """The single best row by `key` (the 'best RRR combi'), or None if empty."""
    r = rank(rows, key)
    return r[0] if r else None


def _mid(bid, ask):
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return 0.5 * (bid + ask)


def _round(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) else x
