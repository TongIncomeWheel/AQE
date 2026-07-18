#!/usr/bin/env python3
"""Kernel accessor for the layered historical store (D-32).

The store itself is built/owned by AQE (Engineering & Change desk) — a data-objects
database LAYERED AWAY from the daily feed. This is the read-only accessor the kernel's
skills/tools use to ANCHOR on it (DoR empirical return distribution, forward-return
context, sizing sanity) — queried ON DEMAND for a named ticker, never bulk-streamed
into the agents' daily read.

Path: config HIST_DIR env, else data/historical/ next to the workspace.
Usage: python3 tools/historical_store.py <TICKER>
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_DIR = os.environ.get("AEGIS_HIST_DIR", os.path.join(ROOT, "data", "historical"))


def get(ticker):
    p = os.path.join(HIST_DIR, f"{ticker}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def monthly_returns(ticker):
    """List of month-over-month close returns (%) — the DoR/anchoring input. [] if absent."""
    o = get(ticker)
    return [m["ret_pct"] for m in o["monthly"] if m.get("ret_pct") is not None] if o else []


def stats(ticker):
    """Anchoring stats (n_months, mean, std, ann_vol) or None if the ticker isn't in the store."""
    o = get(ticker)
    return o["stats"] if o else None


def coverage():
    man = os.path.join(HIST_DIR, "manifest.json")
    return json.load(open(man)) if os.path.exists(man) else {}


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else None
    if not t:
        print(json.dumps({"coverage": coverage()}, indent=1)); sys.exit(0)
    s = stats(t)
    if not s:
        print(f"{t}: not in historical store (run AQE historical_store.load_ticker('{t}'))"); sys.exit(1)
    print(json.dumps({"ticker": t, "stats": s, "n_returns": len(monthly_returns(t))}, indent=1))
