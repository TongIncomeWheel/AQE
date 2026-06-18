"""Glue: one ticker's AQE record + intraday bars → a single trade plan.

Recommend-only. Produces a structured plan + a one-line verdict + an
IBKR-ready bracket spec (for later placement via an IBKR connector). No network
I/O — the caller (the Claude Code `intraday-plan` skill) fetches bars/quotes via
the financial MCP and passes them in.
"""

from __future__ import annotations

from . import config as C
from .momentum import intraday_momentum
from .bracket import build_bracket


def intraday_plan(rec: dict, bars5, regime=None,
                  risk_budget: float = C.RISK_BUDGET) -> dict:
    """Full intraday plan for one ticker.

    rec        : the AQE export record (carries entry, dsl_*, atr_14d,
                 structural_levels, structural_targets, max_chase_tp2, …)
    bars5      : list of 5-min OHLCV bars (FMP `chart intraday-5-min` shape)
    regime     : the export's `regime` dict or level string (for the stop ceiling)
    """
    from .momentum import normalize_bars
    ticker = rec.get("ticker", "?")
    mom = intraday_momentum(bars5, rec)
    bars = normalize_bars(bars5)
    brk = build_bracket(rec, bars, mom, regime=regime, risk_budget=risk_budget)

    return {
        "ticker": ticker,
        "source": rec.get("source") or ("held" if rec.get("held") else None),
        "ims": mom.get("ims"),
        "state": mom.get("state"),
        "momentum": mom.get("components", {}),
        "action": brk["action"],
        "entry_zone": brk["entry_zone"],
        "operative_stop": brk["operative_stop"],
        "tp_ladder": brk["tp_ladder"],
        "rr": brk["rr"],
        "shares": brk["shares"],
        "planned_entry": brk.get("planned_entry"),
        "verdict": brk["verdict"],
        "ibkr_spec": _ibkr_spec(ticker, brk),
    }


def _ibkr_spec(ticker: str, brk: dict) -> dict | None:
    """A recommend-only IBKR bracket spec (NOT placed) for phase-2 execution."""
    op = brk.get("operative_stop")
    if brk["action"] == "STAND_DOWN" or not op or op.get("price") is None:
        return None
    zone = brk["entry_zone"]
    tp2 = None
    if len(brk["tp_ladder"]) >= 2:
        tp2 = brk["tp_ladder"][1]["price"]
    elif brk["tp_ladder"]:
        tp2 = brk["tp_ladder"][0]["price"]
    order_type = {"now": "MKT/LMT", "limit": "LMT",
                  "stop_breakout": "STP"}.get(zone.get("kind"), "LMT")
    return {
        "symbol": ticker, "action": "BUY", "order_type": order_type,
        "entry": zone.get("high"), "entry_low": zone.get("low"),
        "stop": op.get("price"), "take_profit": tp2,
        "quantity": brk["shares"],
        "note": "Recommend-only — review before transmitting to IBKR.",
    }


def rank_plans(plans: list[dict]) -> list[dict]:
    """Sort: actionable ENTER first, then by IMS desc; stand-downs last."""
    order = {"ENTER": 0, "CAUTION": 1, "STAND_DOWN": 2}
    return sorted(
        plans,
        key=lambda p: (order.get(p.get("action"), 3), -(p.get("ims") or 0)),
    )
