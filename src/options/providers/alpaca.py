"""Alpaca options-data adapter — the throttle-proof feed for the universe sweep.

One call to the option-chain **snapshot** endpoint returns a whole underlying's
chain with IV + greeks + latest quote (the free "indicative" feed). We request only
`type=put` in the DTE window, so 600 names = ~600 calls, not ~7,200 per-contract
snapshots. Open interest is deliberately NOT fetched — liquidity is implicit (liquid
universe + round strikes).

The HTTP layer is a thin wrapper; the parsing (`parse_occ_symbol`, `parse_chain`) is
pure so it unit-tests against recorded fixtures without a network or API keys.

Env keys (set as HF/deploy secrets, like FMP): `ALPACA_API_KEY_ID`,
`ALPACA_API_SECRET_KEY`.
"""

from __future__ import annotations

import os
import time
import threading
from datetime import date, timedelta

from .. import config as C

# Client-side rate limiter — calls are sequential, so a single min-interval gate
# keeps us under Alpaca's free 200/min data cap (the root cause of the mass errors).
_MIN_INTERVAL = 60.0 / max(C.ALPACA_MAX_RPM, 1)
_last_call = [0.0]
_rl_lock = threading.Lock()


# ── OCC symbol + response parsing (pure) ────────────────────────────────────
def parse_occ_symbol(sym: str):
    """`MRVL260821P00195000` → ("MRVL", date(2026,8,21), "PUT", 195.0).

    OCC format: root + YYMMDD + C/P + strike×1000 zero-padded to 8 digits. Parsed
    from the right so variable-length roots work.
    """
    strike = int(sym[-8:]) / 1000.0
    right = "PUT" if sym[-9].upper() == "P" else "CALL"
    yy, mm, dd = int(sym[-15:-13]), int(sym[-13:-11]), int(sym[-11:-9])
    root = sym[:-15]
    return root, date(2000 + yy, mm, dd), right, strike


def _get(d, *keys, default=None):
    """First present key (handles camel/snake + short quote keys defensively)."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def parse_chain(resp: dict, underlying: str, spot: float, today: date,
                dte_min: int, dte_max: int, strike_step: float = None,
                right: str = "PUT") -> list[dict]:
    """Alpaca `/options/snapshots/{underlying}` JSON → engine contract dicts.

    Keeps only `right` contracts in the DTE window whose strike is a multiple of
    `strike_step` (round-strike liquidity proxy). Missing IV/quote degrade to None;
    the engine can back IV out of the mid downstream.
    """
    step = C.ROUND_STRIKE_STEP if strike_step is None else strike_step
    out = []
    for occ, snap in (resp.get("snapshots") or {}).items():
        try:
            root, expiry, r, strike = parse_occ_symbol(occ)
        except (ValueError, IndexError):
            continue
        if r != right:
            continue
        dte = (expiry - today).days
        if dte < dte_min or dte > dte_max:
            continue
        if step and abs((strike / step) - round(strike / step)) > 1e-9:
            continue                                    # not a round strike → skip
        q = _get(snap, "latestQuote", "latest_quote", default={}) or {}
        g = _get(snap, "greeks", default={}) or {}
        out.append({
            "ticker": underlying, "spot": spot, "strike": strike, "dte": dte,
            "iv": _get(snap, "impliedVolatility", "implied_volatility"),
            "bid": _get(q, "bp", "bid_price"), "ask": _get(q, "ap", "ask_price"),
            "right": right, "occ": occ,
            "alpaca_delta": _get(g, "delta"),           # cross-check vs engine BS
        })
    return out


def parse_spots(resp: dict) -> dict:
    """Batched stock-snapshot JSON → {symbol: last price}. Prefers the latest trade,
    falls back to the daily-bar close (EOD-consistent)."""
    snaps = resp.get("snapshots", resp) if isinstance(resp, dict) else {}
    spots = {}
    for sym, s in (snaps or {}).items():
        if not isinstance(s, dict):
            continue
        lt = _get(s, "latestTrade", "latest_trade", default={}) or {}
        db = _get(s, "dailyBar", "daily_bar", default={}) or {}
        px = _get(lt, "p", "price") or _get(db, "c", "close")
        if px:
            spots[sym] = px
    return spots


# ── HTTP layer (thin; skipped in unit tests) ────────────────────────────────
def _auth_headers() -> dict:
    kid = os.environ.get(C.ALPACA_KEY_ID_ENV)
    sec = os.environ.get(C.ALPACA_SECRET_ENV)
    if not kid or not sec:
        raise RuntimeError(
            f"Alpaca keys missing: set {C.ALPACA_KEY_ID_ENV} + {C.ALPACA_SECRET_ENV} "
            "as deploy secrets (like FMP_API_KEY).")
    return {"APCA-API-KEY-ID": kid, "APCA-API-SECRET-KEY": sec}


def _pace() -> None:
    """Block until at least _MIN_INTERVAL has elapsed since the last request."""
    with _rl_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


def _http_get(path: str, params: dict) -> dict:
    """Paced + retried GET. Honours 429 Retry-After and backs off on 5xx, so a
    transient rate-limit/blip no longer turns a whole name into a hard error."""
    import requests
    url = f"{C.ALPACA_DATA_URL}{path}"
    last_exc = None
    for attempt in range(C.ALPACA_MAX_RETRIES + 1):
        _pace()
        try:
            r = requests.get(url, params=params, headers=_auth_headers(),
                             timeout=C.ALPACA_TIMEOUT)
        except requests.RequestException as exc:            # network blip → retry
            last_exc = exc
            time.sleep(min(2 ** attempt, 30))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            if attempt < C.ALPACA_MAX_RETRIES:
                retry_after = r.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2 ** attempt
                time.sleep(min(delay, 30))
                continue
        r.raise_for_status()
        return r.json()
    if last_exc:
        raise last_exc
    raise RuntimeError("Alpaca request failed after retries")


def fetch_put_chain(underlying: str, spot: float, today: date = None,
                    dte_min: int = None, dte_max: int = None,
                    feed: str = None, http_get=None) -> list[dict]:
    """Pull one underlying's put chain (all pages) and map to contract dicts.

    `http_get` is injectable for tests (defaults to the live Alpaca call).
    """
    today = today or date.today()
    dte_min = C.UNIVERSE_DTE_MIN if dte_min is None else dte_min
    dte_max = C.UNIVERSE_DTE_MAX if dte_max is None else dte_max
    getter = http_get or _http_get
    # Bound the request server-side to the DTE window AND to OTM strikes below spot.
    # Without expiration_date_lte, Alpaca returns the ENTIRE forward chain (out
    # years of LEAPS) per name — huge payloads that force pagination and blow the
    # rate cap. This is the fix for the mass "names_errored" on liquid names.
    params = {
        "feed": feed or C.ALPACA_FEED, "type": "put", "limit": 1000,
        "expiration_date_gte": today.isoformat(),
        "expiration_date_lte": (today + timedelta(days=dte_max)).isoformat(),
    }
    if spot:
        params["strike_price_lte"] = round(float(spot), 2)   # OTM puts only
        params["strike_price_gte"] = round(float(spot) * (1 - C.ALPACA_MAX_OTM_FRAC), 2)
    rows, token = [], None
    for _ in range(10):                                 # page cap (safety)
        if token:
            params["page_token"] = token
        resp = getter(f"/v1beta1/options/snapshots/{underlying}", params)
        rows += parse_chain(resp, underlying, spot, today, dte_min, dte_max)
        token = resp.get("next_page_token")
        if not token:
            break
    return rows


def fetch_spots(symbols: list[str], http_get=None) -> dict:
    """Batched last prices for many symbols (chunked stock-snapshot calls)."""
    getter = http_get or _http_get
    spots = {}
    for i in range(0, len(symbols), C.ALPACA_SPOT_CHUNK):
        chunk = symbols[i:i + C.ALPACA_SPOT_CHUNK]
        resp = getter("/v2/stocks/snapshots", {"symbols": ",".join(chunk)})
        spots.update(parse_spots(resp))
    return spots
