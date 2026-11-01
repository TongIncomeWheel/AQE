"""Closed-trade streak — VALEN piece 20's context FACT, never the sizing
rule itself (that stays quoted doctrine in the UI — AQE computes no
decisions, no sizing). Reads the persistent Aegis trade journal
(`aegis/data/persistent/trade_journal.json`, built by
`aegis/tools/trade_journal.py`) via the same `github_sync` client
`src/data/ptj.py` already uses for the held-positions journal.

Read-only, best-effort — never raises. `src.valen.spec.CHECKLIST_
LAST_N_TRADES` already anticipated this exact fact ("my last five closed
trades net positive") before any reader existed for it; this module is
that reader.
"""

from __future__ import annotations

import json

TRADE_JOURNAL_PATH = "aegis/data/persistent/trade_journal.json"


def fetch_trade_journal() -> dict | None:
    """The raw persistent trade journal dict, or None on any miss —
    missing credentials, file not found, network failure, bad JSON."""
    try:
        from src.data import github_sync
        if not github_sync.is_configured():
            return None
        result = github_sync.get_file(TRADE_JOURNAL_PATH)
        if not result.get("ok"):
            return None
        return json.loads(result["text"])
    except Exception:  # noqa: BLE001
        return None


def compute_streak(trades: list[dict]) -> dict:
    """The consecutive same-sign run at the most-recent end of the ledger,
    aegis-tagged closed trades only (`tag == "aegis"`, a real net_pnl_usd).
    Sorted by `exit_time_utc` — the ledger's own natural close-order."""
    closed = [t for t in trades
             if t.get("tag") == "aegis" and t.get("net_pnl_usd") is not None]
    if not closed:
        return {"status": "UNAVAILABLE", "reason": "no closed aegis trades in the journal"}

    ordered = sorted(closed, key=lambda t: t.get("exit_time_utc") or "", reverse=True)
    last_pnl = ordered[0]["net_pnl_usd"]
    direction = 1 if last_pnl > 0 else (-1 if last_pnl < 0 else 0)

    streak = 0
    for t in ordered:
        pnl = t["net_pnl_usd"]
        sign = 1 if pnl > 0 else (-1 if pnl < 0 else 0)
        if sign == direction and sign != 0:
            streak += 1
        else:
            break

    return {
        "status": "OK",
        "streak": streak,
        "direction": "WIN" if direction > 0 else ("LOSS" if direction < 0 else "FLAT"),
        "n_considered": len(ordered),
    }


def load_streak() -> dict:
    data = fetch_trade_journal()
    if data is None:
        return {"status": "UNAVAILABLE", "reason": "trade journal not reachable on GitHub"}
    return compute_streak(data.get("trades") or [])


def compute_last_five(trades: list[dict]) -> dict:
    """PM 2026-11-01 (weather-spec item 6): the handbook's 'last five trades' check -- how the most recent five
    closed Aegis trades went, as FACTS (wins, losses, net P&L). Never a size or a stance."""
    closed = [t for t in trades if t.get("tag") == "aegis" and t.get("net_pnl_usd") is not None]
    if not closed:
        return {"status": "UNAVAILABLE", "reason": "no closed aegis trades in the journal"}
    ordered = sorted(closed, key=lambda t: t.get("exit_time_utc") or "", reverse=True)[:5]
    wins = sum(1 for t in ordered if t["net_pnl_usd"] > 0)
    losses = sum(1 for t in ordered if t["net_pnl_usd"] < 0)
    return {"status": "OK", "n": len(ordered), "wins": wins, "losses": losses,
            "net_pnl_usd": round(sum(t["net_pnl_usd"] for t in ordered), 2),
            "tickers": [t.get("ticker") or t.get("symbol") for t in ordered],
            "doctrine": "Check your last five trades before you size the next one. -- The VIV System (quoted doctrine, not an Aegis rule)",
            "is_decision": False}


def load_last_five() -> dict:
    data = fetch_trade_journal()
    if data is None:
        return {"status": "UNAVAILABLE", "reason": "trade journal not reachable on GitHub"}
    return compute_last_five(data.get("trades") or [])
