#!/usr/bin/env python3
"""Aegis dynamic-capital ledger (BL-029 / D-21).

dynCap = allocated_capital + realised P&L on CLOSED AEGIS-tagged trades only
(RB:capital.dyncap_method) — computed on the Aegis sub-fund book, NEVER co-mingled
broker totals. Allocation comes from config/aegis_fund.md (via fund_config.py);
closed-trade realised P&L comes from the Aegis PTJ (already AEGIS-filtered).

Fail-closed: if allocation is unset, dynCap is None and sizing must refuse (BL-030).

Usage:
  python3 tools/dyncap_ledger.py update <closed_trades.json>   # recompute + write ledger
  python3 tools/dyncap_ledger.py show                          # print current ledger
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fund_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "persistent", "dyncap_ledger.json")


def compute(closed_trades):
    """closed_trades: list of {ticker, strategy_tag, realised_pnl_usd}. Only AEGIS rows count."""
    alloc = fund_config.allocated_capital()
    if alloc is None:
        return {"allocated_capital_usd": None, "realised_pnl_usd": 0.0, "dyncap_usd": None,
                "closed_count": 0, "note": "allocation unset (BL-030) — sizing must REFUSE"}
    aegis = [t for t in closed_trades if t.get("strategy_tag") == "AEGIS"]
    realised = round(sum(float(t.get("realised_pnl_usd", 0) or 0) for t in aegis), 2)
    return {"allocated_capital_usd": alloc, "realised_pnl_usd": realised,
            "dyncap_usd": round(alloc + realised, 2), "closed_count": len(aegis),
            "note": "dynCap = allocation + realised P&L on closed AEGIS trades (D-21)"}


def update(closed_trades_path):
    closed = json.load(open(closed_trades_path)) if closed_trades_path else []
    if isinstance(closed, dict):
        closed = closed.get("closed_trades", [])
    led = compute(closed)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(led, open(LEDGER, "w"), indent=1)
    return led


def get_dyncap():
    """Read the current ledger's dynCap (None if unset). Callers refuse on None."""
    if not os.path.exists(LEDGER):
        return compute([])["dyncap_usd"]
    return json.load(open(LEDGER)).get("dyncap_usd")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "update":
        print(json.dumps(update(sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
    else:
        print(json.dumps(json.load(open(LEDGER)) if os.path.exists(LEDGER) else compute([]), indent=1))
