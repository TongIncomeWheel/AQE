"""Tiger option-chain adapter — the open-interest source that is known to work.

Proven live on 2026-08-10: SPY's 21-Aug chain came back with real open interest
(58,308 at the 750 put, 82,245 at the 785 call) and the Crown gamma engine
produced a complete map from it. Alpaca *should* also work now that the fetch
points at the trading host, but this exists because it has actually been seen to
carry the data.

**What is missing to switch this on is credentials, not code.** Tiger does not
authenticate with a simple key pair in a header — it signs requests with an RSA
private key, so three Space secrets are needed:

    TIGER_ID           your tiger id
    TIGER_ACCOUNT      the account number
    TIGER_PRIVATE_KEY  the RSA private key, PEM contents (newlines as \\n is fine)

Then add `tigeropen` to requirements.txt. Until all three are present
`is_configured()` returns False and the gamma layer simply stays on Alpaca.

The parsing is pure and unit-testable against recorded rows; only `fetch_chain`
touches the network, so the shape of the data can be tested without an account.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

TIGER_ID_ENV = "TIGER_ID"
TIGER_ACCOUNT_ENV = "TIGER_ACCOUNT"
TIGER_KEY_ENV = "TIGER_PRIVATE_KEY"


def is_configured() -> bool:
    """All three secrets present AND the SDK importable."""
    if not all(os.environ.get(k) for k in
               (TIGER_ID_ENV, TIGER_ACCOUNT_ENV, TIGER_KEY_ENV)):
        return False
    try:
        import tigeropen  # noqa: F401
    except ImportError:
        return False
    return True


def missing_requirements() -> list[str]:
    """What is stopping it, in the words needed to fix it."""
    out = []
    for k in (TIGER_ID_ENV, TIGER_ACCOUNT_ENV, TIGER_KEY_ENV):
        if not os.environ.get(k):
            out.append(f"secret {k} not set")
    try:
        import tigeropen  # noqa: F401
    except ImportError:
        out.append("tigeropen not installed (add it to requirements.txt)")
    return out


# ── parsing (pure — no SDK, no network) ──────────────────────────────────

def _expiry_date(v) -> date | None:
    """Tiger returns epoch milliseconds; tolerate ISO strings too."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v) / 1000.0, timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _num(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip().rstrip("%")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def parse_chain_rows(rows, underlying: str, spot: float,
                     today: date | None = None,
                     dte_max: int = 45) -> list[dict]:
    """Tiger chain records -> the contract dicts the gamma engine expects.

    Gamma is computed here with our own Black-Scholes rather than taken from the
    vendor, for the same reason the options scanner does it: one gamma
    definition across the whole system, so two layers can never disagree about
    the same contract.

    Rows without open interest are dropped. That is the whole point of this
    adapter — a contract with no OI contributes nothing to a dealer-gamma map,
    and silently treating it as zero would be inventing data.
    """
    from src.options.greeks import bs_greeks, year_fraction

    today = today or date.today()
    out = []
    for r in (rows or []):
        oi = _num(r.get("open_interest"))
        strike = _num(r.get("strike"))
        if not oi or oi <= 0 or not strike or strike <= 0:
            continue

        right = str(r.get("put_call") or r.get("right") or "").upper()[:1]
        right = {"P": "PUT", "C": "CALL"}.get(right)
        if right is None:
            continue

        exp = _expiry_date(r.get("expiry") or r.get("expiration"))
        if exp is None:
            continue
        dte = (exp - today).days
        if dte < 0 or dte > dte_max:
            continue

        iv = _num(r.get("volatility") or r.get("implied_vol") or r.get("iv"))
        if iv is None or iv <= 0:
            continue
        if iv > 3.0:                      # "13.96%" style — a percent, not a rate
            iv = iv / 100.0

        rate = _num(r.get("rates_bonds")) or 0.04
        g = bs_greeks(float(spot), float(strike), year_fraction(dte), iv,
                      right, rate, 0.0).get("gamma")
        if not g:
            continue

        out.append({"occ": r.get("identifier") or r.get("symbol"),
                    "strike": float(strike), "right": right, "dte": int(dte),
                    "gamma": float(g), "open_interest": float(oi)})
    return out


# ── network ──────────────────────────────────────────────────────────────

def normalise_private_key(raw: str) -> str:
    """Accept the key in whatever form it was pasted, return what Tiger wants.

    `tigeropen.read_private_key` strips the PEM header and footer and keeps only
    the base64 body, so handing the SDK a full `-----BEGIN RSA PRIVATE KEY-----`
    block fails with an opaque signature error rather than a useful one. Since
    the PM pastes this into a web form once and cannot debug it from a terminal,
    every plausible paste has to work:

      * full PEM with real newlines (what the file looks like)
      * full PEM with literal \\n (what a one-line form field turns it into)
      * the bare base64 body (what read_private_key returns)
      * PKCS#8 headers instead of PKCS#1
    """
    if not raw:
        return ""
    text = raw.strip().replace("\\n", "\n")
    body = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("-----")]
    return "\n".join(body).strip()


def _client():
    from tigeropen.common.consts import Language
    from tigeropen.quote.quote_client import QuoteClient
    from tigeropen.tiger_open_config import TigerOpenClientConfig

    cfg = TigerOpenClientConfig()
    cfg.tiger_id = os.environ[TIGER_ID_ENV].strip()
    cfg.account = os.environ[TIGER_ACCOUNT_ENV].strip()
    cfg.private_key = normalise_private_key(os.environ[TIGER_KEY_ENV])
    cfg.language = Language.en_US
    return QuoteClient(cfg)


def fetch_chain(underlying: str, spot: float, *, today: date | None = None,
                dte_max: int = 45, max_expiries: int = 3) -> dict:
    """Chain with open interest for one underlying.

    Returns {"spot", "contracts", "oi_available", "reason"} — the same shape the
    Alpaca path returns, so the gamma layer does not care which one produced it.
    """
    if not is_configured():
        return {"spot": spot, "contracts": [], "oi_available": False,
                "reason": "Tiger not configured: " + "; ".join(missing_requirements())}

    today = today or date.today()
    try:
        client = _client()
        expiries = (client.get_option_expirations(symbols=[underlying]) or {})
        # The SDK returns either a dict or a frame depending on version.
        if hasattr(expiries, "to_dict"):
            dates = sorted({_expiry_date(v) or v
                            for v in expiries.get("date", [])})
        else:
            dates = sorted(expiries.get(underlying, []))
        usable = []
        for d in dates:
            dd = d if isinstance(d, date) else _expiry_date(d) or (
                date.fromisoformat(str(d)[:10]) if str(d)[:4].isdigit() else None)
            if dd and 0 <= (dd - today).days <= dte_max:
                usable.append(dd)
        usable = usable[:max_expiries]
        if not usable:
            return {"spot": spot, "contracts": [], "oi_available": False,
                    "reason": f"no {underlying} expiries inside {dte_max} days"}

        rows = []
        for d in usable:
            chain = client.get_option_chain(underlying, d.isoformat())
            rows += (chain.to_dict("records") if hasattr(chain, "to_dict")
                     else list(chain or []))
    except Exception as exc:  # noqa: BLE001
        return {"spot": spot, "contracts": [], "oi_available": False,
                "reason": f"Tiger chain fetch failed: {exc}"}

    contracts = parse_chain_rows(rows, underlying, spot, today, dte_max)
    return {
        "spot": float(spot), "contracts": contracts,
        "oi_available": bool(contracts),
        "expiries_used": [d.isoformat() for d in usable],
        "reason": None if contracts else
                  (f"{len(rows)} chain rows returned but none carried open "
                   "interest, an expiry and an implied vol together"),
    }
