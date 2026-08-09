"""Feeds for the Crown layer. All network lives here; the engines stay pure.

Nothing in this module decides anything. It fetches, normalises, and — where a
feed is missing or plan-gated — says so out loud in a `status` field rather than
returning an empty frame that reads downstream as "calm market".

Sources, and why each one:
  * RSP / SPY / equity ETFs .... FMP daily bars (the panel already carries SPY)
  * futures ..................... FMP continuous front-month, same EOD endpoint
  * ^VIX ........................ FMP index EOD — verified on our Starter plan
  * ^VIXEQ / ^VIX3M / ^VIX9D .... FMP index EOD — NOT on Starter; attempted,
                                  and the failure is reported, never swallowed
  * COT ......................... cftc.gov direct (see cot.py)
  * option chains ............... Alpaca snapshots, BOTH rights, with open
                                  interest — which the CSP adapter deliberately
                                  skips, so gamma needs its own fetch
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.data.fmp_client import FMPClient
from src.data.paths import DATA_DIR
from . import spec as S
from .cta import MARKETS

# Enough history for the 252-session lookback plus the 200-session average plus
# a vol window, with slack for holidays.
BAR_YEARS = 4
PANEL_DAILY = DATA_DIR / "panel_daily.parquet"


# ── the client, which is itself allowed to be missing ────────────────────

def make_client() -> tuple[FMPClient | None, str | None]:
    """(client, reason). A missing FMP key is a DEGRADATION, not a crash.

    `FMPClient()` raises when the key is absent, and an unhandled raise here
    would take down the whole Crown page — including COT, which needs no key at
    all and would otherwise still be perfectly readable.
    """
    try:
        return FMPClient(), None
    except Exception as exc:
        return None, f"FMP client unavailable: {exc}"


def _client(client: FMPClient | None) -> FMPClient | None:
    if client is not None:
        return client
    c, _ = make_client()
    return c


# ── equity + index + futures bars ─────────────────────────────────────────

def fetch_bars(symbol: str, years: int = BAR_YEARS,
               client: FMPClient | None = None) -> pd.DataFrame:
    """Daily OHLCV for anything FMP prices on the EOD endpoint — equities, ETFs,
    index symbols (`^VIX`) and continuous futures (`ZNUSD`) all share it.

    Returns an EMPTY frame on failure, and the caller is responsible for saying
    so. This function does not print, because it is called in loops where one
    line per miss would bury the real problem.
    """
    c = _client(client)
    if c is None:
        return pd.DataFrame()
    start = date.today() - timedelta(days=int(years * 365.25))
    try:
        df = c.get_daily_bars(symbol, from_date=start)
    except Exception:
        return pd.DataFrame()
    if df is None or len(df) == 0:
        return pd.DataFrame()
    return df


def fetch_many(symbols, years: int = BAR_YEARS,
               client: FMPClient | None = None) -> tuple[dict, list[str]]:
    """Bars for several symbols. Returns (frames, failures) — the failure list is
    the point, and every caller is expected to surface it."""
    c = _client(client)
    if c is None:
        return {}, list(symbols)
    out, bad = {}, []
    for s in symbols:
        df = fetch_bars(s, years, c)
        if len(df):
            out[s] = df
        else:
            bad.append(s)
    return out, bad


def heartbeat_bars(client: FMPClient | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """RSP and SPY. SPY is preferred from the local panel when it is there —
    it is the same series and it saves a call the pipeline already made."""
    c = _client(client)
    spy = _panel_series(S.HEARTBEAT_DEN)
    if spy is None or len(spy) < S.HB_LOOKBACK_DAYS:
        spy = fetch_bars(S.HEARTBEAT_DEN, client=c)
    rsp = _panel_series(S.HEARTBEAT_NUM)
    if rsp is None or len(rsp) < S.HB_LOOKBACK_DAYS:
        rsp = fetch_bars(S.HEARTBEAT_NUM, client=c)
    missing = [n for n, d in ((S.HEARTBEAT_NUM, rsp), (S.HEARTBEAT_DEN, spy))
               if d is None or len(d) == 0]
    return (rsp if rsp is not None else pd.DataFrame(),
            spy if spy is not None else pd.DataFrame(), missing)


def _panel_series(ticker: str) -> pd.DataFrame | None:
    """One ticker's bars out of the daily panel, if the panel has it."""
    if not PANEL_DAILY.exists():
        return None
    try:
        p = pd.read_parquet(PANEL_DAILY, columns=["ticker", "date", "open", "high",
                                                  "low", "close", "volume"])
    except Exception:
        return None
    sub = p[p["ticker"] == ticker]
    if sub.empty:
        return None
    return sub.drop(columns=["ticker"]).sort_values("date").reset_index(drop=True)


def futures_bars(client: FMPClient | None = None) -> tuple[dict, list[str]]:
    """Bars for the replicated CTA universe, keyed by our market key (ES, ZN…)."""
    c = _client(client)
    frames, bad = {}, []
    for key, meta in MARKETS.items():
        df = fetch_bars(meta["fmp"], client=c)
        if len(df) >= S.CTA_MIN_HISTORY:
            frames[key] = df
        else:
            bad.append(f"{key} ({meta['fmp']})")
    return frames, bad


def vix_bars(client: FMPClient | None = None) -> dict:
    """The VIX complex. `^VIX` is expected to work; the rest are expected to fail
    on our plan, and the dict says which did."""
    c = _client(client)
    out = {"vix": None, "vixeq": None, "vix3m": None, "vix9d": None,
           "unavailable": []}
    for key, sym in (("vix", S.VIX_SYMBOL), ("vixeq", S.VIXEQ_SYMBOL),
                     ("vix3m", S.VIX3M_SYMBOL), ("vix9d", S.VIX9D_SYMBOL)):
        df = fetch_bars(sym, client=c)
        if len(df):
            out[key] = df
        else:
            out["unavailable"].append(sym)
    return out


def panel_for_dispersion() -> pd.DataFrame | None:
    """The long-format daily panel, for the realised-dispersion fallback."""
    if not PANEL_DAILY.exists():
        return None
    try:
        return pd.read_parquet(PANEL_DAILY, columns=["ticker", "date", "close"])
    except Exception:
        return None


# ── option chains with OPEN INTEREST (gamma's missing input) ──────────────

def _oi(snap: dict) -> float | None:
    """Open interest under any of the names a feed might use for it."""
    for k in ("openInterest", "open_interest", "oi"):
        v = snap.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def fetch_gamma_chain(underlying: str, spot: float, *, today: date | None = None,
                      http_get=None) -> dict:
    """Both rights, near the money, with gamma and open interest.

    The CSP adapter fetches puts only and skips open interest by design — right
    for a cash-secured-put sweep, useless for a gamma map, which needs both sides
    and the OI is the whole weight. So this is a separate call rather than a flag
    on that one.

    Returns {"spot", "contracts", "oi_available", "reason"}. When the feed does
    not carry open interest, `oi_available` is False and `contracts` is empty:
    a gamma profile built on assumed OI would be fiction with a number on it.
    """
    from src.options.providers.alpaca import (_http_get, parse_occ_symbol)

    today = today or date.today()
    getter = http_get or _http_get
    if not spot or spot <= 0:
        return {"spot": spot, "contracts": [], "oi_available": False,
                "reason": "no spot price"}

    lo = round(float(spot) * (1 - S.GAMMA_STRIKE_BAND), 2)
    hi = round(float(spot) * (1 + S.GAMMA_STRIKE_BAND), 2)
    params = {
        "limit": 1000,
        "expiration_date_gte": today.isoformat(),
        "expiration_date_lte": (today + timedelta(days=S.GAMMA_DTE_MAX)).isoformat(),
        "strike_price_gte": lo, "strike_price_lte": hi,
    }

    rows, token, saw_oi, saw_any = [], None, False, False
    try:
        for _ in range(12):
            if token:
                params["page_token"] = token
            resp = getter(f"/v1beta1/options/snapshots/{underlying}", params)
            for occ, snap in (resp.get("snapshots") or {}).items():
                saw_any = True
                try:
                    _root, expiry, right, strike = parse_occ_symbol(occ)
                except (ValueError, IndexError):
                    continue
                g = (snap.get("greeks") or {})
                gamma = g.get("gamma")
                oi = _oi(snap)
                if oi is not None:
                    saw_oi = True
                if gamma is None or oi is None:
                    continue
                rows.append({
                    "occ": occ, "strike": float(strike), "right": right,
                    "dte": (expiry - today).days, "gamma": float(gamma),
                    "open_interest": float(oi),
                })
            token = resp.get("next_page_token")
            if not token:
                break
    except Exception as exc:
        return {"spot": spot, "contracts": [], "oi_available": False,
                "reason": f"chain fetch failed: {exc}"}

    if not saw_any:
        reason = "chain returned no snapshots"
    elif not saw_oi:
        reason = ("the options feed did not return open interest — a gamma map "
                  "cannot be built without it (IBKR get_option_data and Tiger "
                  "get_option_briefs both carry OI as alternatives)")
    elif not rows:
        reason = "snapshots carried neither gamma nor open interest"
    else:
        reason = None

    return {"spot": float(spot), "contracts": rows, "oi_available": saw_oi,
            "reason": reason}


def fetch_gamma_chains(underlyings=S.GAMMA_UNDERLYINGS,
                       client: FMPClient | None = None) -> tuple[dict, dict]:
    """Chains for the index underlyings. Returns (chains, failures)."""
    c = _client(client)
    if c is None:
        return {}, {u: "FMP client unavailable (no spot price)" for u in underlyings}
    chains, bad = {}, {}
    try:
        quotes = c.get_quotes_batch(list(underlyings))
    except Exception as exc:
        return {}, {u: f"spot lookup failed: {exc}" for u in underlyings}

    # get_quotes_batch returns {ticker: {price, prev_close, ...}}.
    spots = {}
    for sym, q in (quotes or {}).items():
        px = (q or {}).get("price") or (q or {}).get("prev_close")
        if px:
            spots[sym] = float(px)

    for u in underlyings:
        spot = spots.get(u)
        if not spot:
            bad[u] = "no spot price from FMP"
            continue
        got = fetch_gamma_chain(u, spot)
        if got.get("contracts"):
            chains[u] = got
        else:
            bad[u] = got.get("reason") or "no contracts"
    return chains, bad
