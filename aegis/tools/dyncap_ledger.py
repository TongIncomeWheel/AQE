#!/usr/bin/env python3
"""Aegis dynamic-capital ledger (BL-029 / D-21, method revised by D-41).

dynCap = allocated_capital + realised P&L (closed AEGIS trades) + UNREALISED P&L
(open AEGIS positions, marked) = current Aegis sub-fund EQUITY (RB:capital.dyncap_method,
D-41 PM ruling 2026-07-19: mark-to-market, so sizing tracks what you actually hold).
Computed on the Aegis sub-fund book ONLY, NEVER co-mingled broker totals. Allocation comes
from config/aegis_fund.md (via fund_config.py); realised + unrealised P&L come from the Aegis
PTJ (already AEGIS-filtered, positions marked to current price).

Mark-to-market note (D-41): dynCap now moves with unrealised P&L, so it must be REFRESHED
each premarket from the fresh PTJ (Operations runs `update <ptj.json>` after the book read).
It is procyclical by design — it de-sizes in drawdown — the PM's explicit choice.

Fail-closed: if allocation is unset, dynCap is None and sizing must refuse (BL-030).

Usage:
  python3 tools/dyncap_ledger.py update <ptj.json>   # recompute (closed+open) + write ledger
  python3 tools/dyncap_ledger.py show                 # print current ledger
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fund_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "persistent", "dyncap_ledger.json")


def compute(closed_trades, open_positions=None, marked_asof=None):
    """Mark-to-market dynCap (D-41). Only AEGIS rows count.
    closed_trades: list of {ticker, strategy_tag, realised_pnl_usd}
    open_positions: list of {ticker, strategy_tag, unrealised_pnl_usd} (marked by the PTJ)."""
    alloc = fund_config.allocated_capital()
    if alloc is None:
        return {"allocated_capital_usd": None, "realised_pnl_usd": 0.0, "unrealised_pnl_usd": 0.0,
                "dyncap_usd": None, "closed_count": 0, "open_count": 0, "marked_asof": marked_asof,
                "note": "allocation unset (BL-030) — sizing must REFUSE"}
    aegis_closed = [t for t in closed_trades if t.get("strategy_tag") == "AEGIS"]
    aegis_open = [p for p in (open_positions or []) if p.get("strategy_tag") == "AEGIS"]
    realised = round(sum(float(t.get("realised_pnl_usd", 0) or 0) for t in aegis_closed), 2)
    unrealised = round(sum(float(p.get("unrealised_pnl_usd", 0) or 0) for p in aegis_open), 2)
    return {"allocated_capital_usd": alloc, "realised_pnl_usd": realised,
            "unrealised_pnl_usd": unrealised,
            "dyncap_usd": round(alloc + realised + unrealised, 2),
            "closed_count": len(aegis_closed), "open_count": len(aegis_open),
            "marked_asof": marked_asof,
            "note": "dynCap = allocation + realised + UNREALISED = current Aegis equity, mark-to-market (D-41)"}


def update(ptj_path):
    """Read the Aegis PTJ (closed_trades + open positions marked to price) and recompute."""
    doc = json.load(open(ptj_path)) if ptj_path else {}
    if isinstance(doc, list):
        closed, opened = doc, []          # bare list = closed trades (back-compat)
    else:
        closed = doc.get("closed_trades", [])
        opened = doc.get("open_positions") or doc.get("positions") or []
    marked = doc.get("marked_asof") or doc.get("as_of") if isinstance(doc, dict) else None
    led = compute(closed, opened, marked_asof=marked)
    # MED-1: validate the capital anchor against its contract before writing (fail-closed)
    try:
        import jsonschema
        schema_path = os.path.join(ROOT, "contracts", "dyncap_ledger.schema.json")
        if os.path.exists(schema_path):
            jsonschema.validate(led, json.load(open(schema_path)))
    except Exception as e:
        raise ValueError(f"dyncap ledger failed its contract, refusing to write: {e}")
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(led, open(LEDGER, "w"), indent=1)
    return led


def get_dyncap():
    """Read dynCap, CROSS-CHECKED against the live allocation anchor on every call (CRIT-1 fix).
    - allocation unset in config/aegis_fund.md -> None (refuse; BL-030 kill-switch honoured).
    - cached ledger's allocation != current config allocation -> stale cache -> None (refuse),
      so a PM zeroing/changing the allocation can never be bypassed by a stale ledger; someone
      must re-run `dyncap_ledger.py update` to serve a fresh figure. Never size on phantom capital."""
    live_alloc = fund_config.allocated_capital()
    if live_alloc is None:
        return None
    if not os.path.exists(LEDGER):
        return compute([])["dyncap_usd"]
    led = json.load(open(LEDGER))
    if led.get("allocated_capital_usd") != live_alloc:
        return None
    return led.get("dyncap_usd")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "update":
        print(json.dumps(update(sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
    else:
        print(json.dumps(json.load(open(LEDGER)) if os.path.exists(LEDGER) else compute([]), indent=1))
