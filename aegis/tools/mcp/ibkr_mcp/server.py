#!/usr/bin/env python3
"""IBKR MCP server — the one broker service that needs building (Tiger & Alpaca are reused, PM instruction).

Wraps IBKR's Client Portal Web API (the same API the desktop Client Portal Gateway serves on
https://localhost:5000/v1/api). READ-ONLY by design: positions, balances, orders, trades, snapshot.
NO order placement tools exist in this server — the execution boundary (constitution law 1) is
enforced in code, not prose. If Phase 2 is ever ratified, staging tools get added behind the
same preview/confirm double-call pattern as the Tiger MCP.

Prereq: IBKR Client Portal Gateway running and authenticated on the same machine
        (https://www.interactivebrokers.com/en/trading/ib-api.php → Client Portal API).
Run:    pip install "mcp[cli]" requests && python3 server.py
        (stdio transport; add to harness mcp config. For HTTP: mcp run --transport sse server.py)
Env:    IBKR_GATEWAY=https://localhost:5000/v1/api   IBKR_ACCOUNT=U1234567   IBKR_VERIFY_SSL=0
"""
import os
import requests
from mcp.server.fastmcp import FastMCP

GATEWAY = os.environ.get("IBKR_GATEWAY", "https://localhost:5000/v1/api")
ACCOUNT = os.environ.get("IBKR_ACCOUNT", "")
VERIFY = os.environ.get("IBKR_VERIFY_SSL", "0") == "1"

mcp = FastMCP("ibkr", instructions="IBKR read-only data: positions, balances, orders, trades, snapshots. "
                                   "Broker pull is execution truth (RB:data_sources.positions_fills). "
                                   "This server cannot place, amend or cancel orders — by design.")


def _get(path, **params):
    r = requests.get(f"{GATEWAY}{path}", params=params, verify=VERIFY, timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def auth_status() -> dict:
    """Check gateway session status. Call first; if unauthenticated the PM must log in to the gateway."""
    try:
        r = requests.post(f"{GATEWAY}/iserver/auth/status", verify=VERIFY, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e), "hint": "Is the Client Portal Gateway running and logged in?"}


@mcp.tool()
def positions() -> list:
    """All positions for the configured account (USD instruments included as-is; filter downstream)."""
    return _get(f"/portfolio/{ACCOUNT}/positions/0")


@mcp.tool()
def balances() -> dict:
    """Account ledger/balances summary."""
    return _get(f"/portfolio/{ACCOUNT}/ledger")


@mcp.tool()
def open_orders() -> dict:
    """Live orders including stops — the live-stop truth for the stop audit."""
    return _get("/iserver/account/orders")


@mcp.tool()
def trades(days: int = 7) -> list:
    """Recent executions (fills) — execution truth for the journal reconcile."""
    return _get("/iserver/account/trades", days=str(days))


@mcp.tool()
def snapshot(conids: str) -> list:
    """Market data snapshot for comma-separated contract ids (fields: last, bid, ask, volume)."""
    return _get("/iserver/marketdata/snapshot", conids=conids, fields="31,84,86,87")


@mcp.tool()
def search_contract(symbol: str) -> list:
    """Resolve a ticker to IBKR contract ids (needed by snapshot)."""
    return _get("/iserver/secdef/search", symbol=symbol)


if __name__ == "__main__":
    mcp.run()
