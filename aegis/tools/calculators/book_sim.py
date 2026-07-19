#!/usr/bin/env python3
"""Book simulator (D-35) — the "what does the book look like AFTER this?" engine.

Risk is NOT a one-layer calculator that emits a single size. It advises: it runs
SCENARIOS (0.5R vs 1R), it SIMULATES the post-action book (what leverage / beta /
sector-exposure / combined-stop-risk become after a proposed entry, exit, scale or
rotation), and it hands the PM options with a recommendation — a conversation, not a
one-way gate. This tool is the simulation underneath that advisory role.

Deterministic (law 4). Pure functions; the Risk desk calls it to build scenarios.
"""
from __future__ import annotations
from copy import deepcopy


def metrics(positions: list, dyncap: float) -> dict:
    """Portfolio metrics for a book. positions: [{ticker,sector,exposure_usd,beta,risk_usd}]."""
    if dyncap <= 0:
        raise ValueError("dyncap must be positive")
    gross = sum(p.get("exposure_usd", 0) for p in positions)
    beta = round(sum(p.get("exposure_usd", 0) * p.get("beta", 0) for p in positions) / gross, 3) if gross else 0.0
    sect: dict = {}
    for p in positions:
        sect[p.get("sector", "?")] = sect.get(p.get("sector", "?"), 0) + p.get("exposure_usd", 0)
    sector_pct = {s: round(v / dyncap * 100, 1) for s, v in sect.items()}
    combined_stop = round(sum(p.get("risk_usd", 0) for p in positions) / dyncap * 100, 2)
    return {"gross_exposure_usd": round(gross, 2), "leverage_x": round(gross / dyncap, 2),
            "portfolio_beta": beta, "sector_exposure_pct": dict(sorted(sector_pct.items(), key=lambda x: -x[1])),
            "combined_stop_risk_pct": combined_stop, "position_count": len(positions),
            "top_sector_pct": max(sector_pct.values()) if sector_pct else 0.0}


def apply(positions: list, actions: list) -> list:
    """Apply proposed actions to a copy of the book. actions: [{op, ticker, ...}].
    op in ADD (needs sector/exposure_usd/beta/risk_usd) · EXIT · TRIM|SCALE (needs fraction)."""
    book = {p["ticker"]: deepcopy(p) for p in positions}
    for a in actions:
        op = a["op"].upper(); t = a["ticker"]
        if op == "ADD":
            book[t] = {"ticker": t, "sector": a.get("sector", "?"),
                       "exposure_usd": a.get("exposure_usd", 0), "beta": a.get("beta", 0),
                       "risk_usd": a.get("risk_usd", 0)}
        elif op == "EXIT":
            book.pop(t, None)
        elif op in ("TRIM", "SCALE") and t in book:
            keep = 1 - a.get("fraction", 0)
            book[t]["exposure_usd"] *= keep; book[t]["risk_usd"] *= keep
            if keep <= 0: book.pop(t, None)
    return list(book.values())


def simulate(positions: list, actions: list, dyncap: float) -> dict:
    """Before/after book metrics + the deltas — what Risk shows the PM for a proposed action set."""
    before = metrics(positions, dyncap)
    after = metrics(apply(positions, actions), dyncap)
    delta = {k: round(after[k] - before[k], 2) for k in ("leverage_x", "portfolio_beta", "combined_stop_risk_pct", "top_sector_pct")}
    return {"before": before, "after": after, "delta": delta}


def size_scenarios(entry: float, stop: float, dyncap: float, one_r_pct: float,
                   r_options=(0.5, 1.0, 2.0)) -> list:
    """Risk's VOICE on sizing: present 0.5R / 1R / 2R as scenarios with shares + $risk,
    so the PM chooses conviction — not a single imposed number."""
    per_share = entry - stop
    out = []
    for r in r_options:
        budget = one_r_pct / 100.0 * dyncap * r
        shares = int(budget / per_share) if per_share > 0 else 0
        out.append({"r_multiple": r, "shares": shares, "risk_usd": round(shares * per_share, 2),
                    "exposure_usd": round(shares * entry, 2)})
    return out


if __name__ == "__main__":
    book = [{"ticker": "NVDA", "sector": "XLK", "exposure_usd": 20000, "beta": 1.8, "risk_usd": 800},
            {"ticker": "IBM", "sector": "XLK", "exposure_usd": 15000, "beta": 0.9, "risk_usd": 600},
            {"ticker": "XOM", "sector": "XLE", "exposure_usd": 10000, "beta": 0.8, "risk_usd": 500}]
    dc = 60000
    # simulate rotating out of IBM (XLK over-heavy) into a new XLE name
    sim = simulate(book, [{"op": "EXIT", "ticker": "IBM"},
                          {"op": "ADD", "ticker": "CVX", "sector": "XLE", "exposure_usd": 12000, "beta": 0.85, "risk_usd": 600}], dc)
    assert sim["after"]["position_count"] == 3
    assert sim["before"]["sector_exposure_pct"]["XLK"] > sim["after"]["sector_exposure_pct"]["XLK"]  # XLK reduced
    sc = size_scenarios(entry=50, stop=47, dyncap=dc, one_r_pct=1.5)
    assert sc[1]["r_multiple"] == 1.0 and sc[1]["shares"] > 0
    print("book_sim self-test PASSED — rotation cut XLK from",
          f'{sim["before"]["sector_exposure_pct"]["XLK"]}% to {sim["after"]["sector_exposure_pct"]["XLK"]}%;',
          "leverage delta", sim["delta"]["leverage_x"], "| 1R scenario:", sc[1]["shares"], "shares")
