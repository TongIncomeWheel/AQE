"""Read-only IBKR Client Portal API integration.

Fetches open stock positions + attached stop orders from IBKR's local Client
Portal Web API gateway (https://localhost:5000) and writes them to
output/held_positions.json in the same format that ptj.py produces —
so the rest of AQE (Charts overlay, HELD alerts, export held=true) works
unchanged.

Setup (one-time, on the user's PC):
  1. Download + start the IBKR Client Portal API gateway:
     https://www.interactivebrokers.com/en/trading/ib-api.php  (CP Web API)
  2. Log in at https://localhost:5000 in your browser.
  3. Optionally set IBKR_BASE_URL env var if you run it on a different port.
     Default: https://localhost:5000/v1/api

Environment variables:
  IBKR_BASE_URL   Gateway base (default https://localhost:5000/v1/api)
  IBKR_ACCOUNT    Account ID; if unset the first account returned is used
  IBKR_TIMEOUT    Request timeout seconds (default 10)

Failures degrade gracefully — returns empty list or cached positions.
"""

from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone

from src.data.paths import OUTPUT_DIR

IBKR_CACHE = OUTPUT_DIR / "held_positions.json"

_DEFAULT_BASE = "https://localhost:5000/v1/api"


def _base() -> str:
    return (os.environ.get("IBKR_BASE_URL") or _DEFAULT_BASE).rstrip("/")


def _timeout() -> int:
    try:
        return int(os.environ.get("IBKR_TIMEOUT") or 10)
    except (TypeError, ValueError):
        return 10


def _get(path: str) -> dict | list | None:
    """GET from the local CP API gateway; returns parsed JSON or None."""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        url = f"{_base()}{path}"
        r = requests.get(url, verify=False, timeout=_timeout())
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:  # noqa: BLE001
        return None


def _post(path: str, body: dict | None = None) -> dict | list | None:
    """POST to the local CP API gateway."""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        url = f"{_base()}{path}"
        r = requests.post(url, json=body or {}, verify=False, timeout=_timeout())
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:  # noqa: BLE001
        return None


def is_configured() -> bool:
    """True if the CP gateway appears reachable (quick /tickle check)."""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get(f"{_base()}/iserver/auth/status",
                         verify=False, timeout=3)
        if r.status_code == 200:
            data = r.json()
            return bool(data.get("authenticated"))
        return False
    except Exception:  # noqa: BLE001
        return False


def _get_account() -> str | None:
    """Return account ID from env or the first account in the portfolio."""
    acct = os.environ.get("IBKR_ACCOUNT", "").strip()
    if acct:
        return acct
    data = _get("/portfolio/accounts")
    if isinstance(data, list) and data:
        return data[0].get("id") or data[0].get("accountId")
    data = _get("/iserver/accounts")
    if isinstance(data, dict):
        accts = data.get("accounts") or []
        if accts:
            return accts[0]
    return None


def _reauthenticate() -> None:
    """Nudge the gateway to re-auth (sometimes needed after idle)."""
    _post("/iserver/reauthenticate")


def _get_positions(account_id: str) -> list[dict]:
    """Fetch all stock positions; auto-pages."""
    positions: list[dict] = []
    page = 0
    while True:
        data = _get(f"/portfolio/{account_id}/positions/{page}")
        if not data or not isinstance(data, list):
            break
        stocks = [p for p in data
                  if p.get("assetClass") == "STK" and (p.get("position") or 0) > 0]
        positions.extend(stocks)
        if len(data) < 100:  # last page
            break
        page += 1
    return positions


def _get_stop_orders() -> dict[int, float]:
    """Return {conid: stop_price} for open STOP/STP orders.

    Handles both `STP` (IBKR internal) and `STOP` order types.
    Also handles OCA groups where a STP is part of a bracket.
    """
    data = _get("/iserver/account/orders")
    if not data:
        return {}
    orders = data if isinstance(data, list) else (data.get("orders") or [])
    stops: dict[int, float] = {}
    for o in orders:
        otype = (o.get("orderType") or o.get("order_type") or "").upper()
        status = (o.get("status") or "").upper()
        if status in ("CANCELLED", "FILLED", "INACTIVE"):
            continue
        if otype in ("STP", "STOP", "STPLMT"):
            conid = o.get("conid") or o.get("conId")
            price = o.get("auxPrice") or o.get("stopPrice") or o.get("price")
            if conid and price is not None:
                try:
                    stops[int(conid)] = float(price)
                except (TypeError, ValueError):
                    pass
    return stops


def fetch_ibkr_positions() -> list[dict]:
    """Fetch open positions from IBKR CP API.

    Returns list of position dicts matching the PTJ open_positions schema:
      ticker, qty, entry, sl, livePx, unrealUsd, exposure, entryDate
    """
    try:
        _reauthenticate()
        account = _get_account()
        if not account:
            return []
        raw = _get_positions(account)
        if not raw:
            return []
        stops = _get_stop_orders()
        positions = []
        for p in raw:
            ticker = (p.get("ticker") or p.get("contractDesc") or "").upper().strip()
            if not ticker:
                continue
            conid = p.get("conid") or p.get("conId")
            qty = p.get("position") or 0
            entry = p.get("avgCost") or p.get("avgPrice") or 0.0
            live_px = p.get("mktPrice") or None
            unreal = p.get("unrealizedPnl") or 0.0
            mkt_value = p.get("mktValue") or 0.0
            sl = stops.get(int(conid)) if conid else None
            positions.append({
                "ticker": ticker,
                "qty": int(round(qty)),
                "entry": float(entry),
                "sl": float(sl) if sl is not None else None,
                "livePx": float(live_px) if live_px is not None else None,
                "unrealUsd": float(unreal),
                "exposure": float(mkt_value),
                "entryDate": None,   # CP API doesn't expose this; leave for UI
                "notes": f"IBKR live | acct {account}",
            })
        return positions
    except Exception:  # noqa: BLE001
        return []


def refresh_held_positions() -> list[dict]:
    """Fetch IBKR positions, cache to held_positions.json, return them.

    Falls back to the local cache on any failure — same contract as ptj.py.
    """
    positions = fetch_ibkr_positions()
    if not positions:
        return load_held_positions()
    cache = {
        "source": "ibkr",
        "source_file": None,
        "modified": datetime.now(timezone.utc).isoformat(),
        "snapshot": None,
        "positions": positions,
        "options": [],
    }
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        IBKR_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return positions


def load_ibkr_cache() -> dict:
    """The cached IBKR snapshot."""
    try:
        if IBKR_CACHE.exists():
            return json.loads(IBKR_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {}


def load_held_positions() -> list[dict]:
    """Held positions from the local cache — no IBKR call."""
    return load_ibkr_cache().get("positions") or []
