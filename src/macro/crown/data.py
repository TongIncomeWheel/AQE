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
    """RSP and SPY, preferring the local panel ONLY while it is current.

    The panel is free and already built, so it is worth preferring — but a stale
    panel must lose to a live fetch. `_panel_series` now enforces that, and
    anything that comes back stale from BOTH sources is named rather than used.
    """
    c = _client(client)
    notes: list[str] = []
    out: dict[str, pd.DataFrame] = {}
    for name in (S.HEARTBEAT_NUM, S.HEARTBEAT_DEN):
        df = _panel_series(name)
        source = "panel"
        if df is None or len(df) < S.HB_LOOKBACK_DAYS:
            df = fetch_bars(name, client=c)
            source = "fmp"
        if df is None or len(df) == 0:
            notes.append(f"{name}: no bars from panel or FMP")
            out[name] = pd.DataFrame()
            continue
        if is_stale(df):
            s = staleness(df)
            notes.append(f"{name}: STALE — last bar {s['as_of']} "
                         f"({s['days_stale']}d old, source={source})")
        out[name] = df
    return out[S.HEARTBEAT_NUM], out[S.HEARTBEAT_DEN], notes


def last_date(df) -> pd.Timestamp | None:
    """The most recent bar date in a frame, or None."""
    if df is None or len(df) == 0 or "date" not in getattr(df, "columns", []):
        return None
    d = pd.to_datetime(pd.DataFrame(df)["date"], errors="coerce").dropna()
    return d.max() if len(d) else None


def staleness(df) -> dict:
    """{as_of, days_stale} for any bar frame. The thing every feed must carry."""
    d = last_date(df)
    if d is None:
        return {"as_of": None, "days_stale": None}
    return {"as_of": d.date().isoformat(),
            "days_stale": int((pd.Timestamp.today().normalize() - d.normalize()).days)}


def is_stale(df, max_days: int = S.MAX_BAR_STALENESS_DAYS) -> bool:
    s = staleness(df)
    return s["days_stale"] is None or s["days_stale"] > max_days


def _panel_series(ticker: str,
                  max_stale_days: int = S.PANEL_MAX_STALENESS_DAYS) -> pd.DataFrame | None:
    """One ticker's bars out of the daily panel — only if the panel is CURRENT.

    The recency test is the whole point. Preferring the panel is a good idea (it
    is free and already built), but the original guard checked only LENGTH, so a
    panel that stopped updating months ago passed trivially and silently
    displaced a live fetch. A stale local file must lose to the network, not beat
    it on row count.
    """
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
    out = sub.drop(columns=["ticker"]).sort_values("date").reset_index(drop=True)
    if is_stale(out, max_stale_days):
        return None
    return out


def futures_bars(client: FMPClient | None = None) -> tuple[dict, list[str], dict]:
    """Bars for the replicated CTA universe, keyed by our market key (ES, ZN…).

    Returns (frames, missing, sources). A market whose futures symbol is
    unavailable or stale falls back to its tracking ETF rather than dropping out,
    because `flip_risk` is extremes / n_markets — losing the whole rates complex
    silently changes the denominator and re-rates every reading. `sources` records
    which leg each market actually came from, so a proxy is never mistaken for
    the future itself.
    """
    c = _client(client)
    frames, bad, sources = {}, [], {}
    for key, meta in MARKETS.items():
        sym = meta["fmp"]
        df = fetch_bars(sym, client=c)
        used, stale = "futures", False

        if len(df) < S.CTA_MIN_HISTORY or is_stale(df):
            fb = meta.get("fallback")
            alt = fetch_bars(fb, client=c) if fb else pd.DataFrame()
            if len(alt) >= S.CTA_MIN_HISTORY and not is_stale(alt):
                df, sym, used = alt, fb, "etf_fallback"
            elif len(df) >= S.CTA_MIN_HISTORY:
                used, stale = "futures", True      # keep it, but say it is stale
            else:
                bad.append(f"{key} ({meta['fmp']}"
                           + (f" / {fb}" if fb else "") + ")")
                continue

        frames[key] = df
        sources[key] = {"symbol": sym, "via": used, "stale": stale,
                        **staleness(df)}
    return frames, bad, sources


def vix_bars(client: FMPClient | None = None, *, refresh: bool = True) -> dict:
    """The volatility complex — **Cboe first**, FMP only as a fallback for VIX.

    Cboe computes these indices and publishes their full history free, so there
    is nothing to gain from a reseller and one thing to lose: FMP gates VIXEQ,
    VIX3M and VIX9D above our plan, which is what forced the realised proxy in
    the first place. With Cboe the implied spread is simply available.
    """
    from . import cboe

    out = {"vix": None, "vixeq": None, "vix3m": None, "vix9d": None,
           "dspx": None, "cor1m": None, "unavailable": [], "source": None}

    if refresh:
        st = cboe.refresh()
        if not st.get("ok"):
            out["unavailable"].append(f"Cboe: {st.get('reason')}")

    frames = cboe.series_frames()
    for key in ("vix", "vixeq", "vix3m", "vix9d", "dspx", "cor1m"):
        df = frames.get(key)
        if df is not None and len(df):
            out[key] = df
        else:
            out["unavailable"].append(f"Cboe {cboe.SERIES.get(key, key)}")
    if any(out[k] is not None for k in ("vix", "vixeq")):
        out["source"] = "cboe"

    # FMP can still cover VIX if Cboe is unreachable. It cannot cover VIXEQ,
    # which is the whole reason Cboe is primary.
    if out["vix"] is None:
        df = fetch_bars(S.VIX_SYMBOL, client=_client(client))
        if len(df):
            out["vix"], out["source"] = df, "fmp_fallback"
        else:
            out["unavailable"].append(S.VIX_SYMBOL)
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
