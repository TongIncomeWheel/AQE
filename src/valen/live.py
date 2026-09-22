"""VALEN live refresh — recompute trend + extension during market hours.

Reuses house infra rather than building a parallel live path:
  - `src.alerts.engine.in_market_window()` — the one market-open gate AQE
    already has (Mon-Fri, 09:45-16:15 ET, padded).
  - `FMPClient.get_quotes_batch()` — one FMP call for every symbol this
    needs (SPY, QQQ, ^VIX), previously defined but unused anywhere in the
    repo; exactly built for this.

Click-to-refresh, not auto-polling — matches the house pattern in
src/ui/pages/3_Charts_and_Trade_Entry.py (a button, not st.fragment/
st.rerun/a cache TTL). A live pull never overwrites the nightly batch
artifact on disk; it returns a fresh dict for the CURRENT page render only.

Breadth (the four whole-market instruments) cannot be refreshed live even
once Phase 2 ships it — computing "% of ~7,000 stocks above their 40-day
line" on every page load is not a per-click operation. Only trend and
extension refresh live; breadth stays at its last nightly batch read,
labelled with its own `as_of`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.alerts.engine import in_market_window
from src.data.fmp_client import FMPClient
from src.macro.crown import cboe

from . import extension, trend

LIVE_SYMBOLS = ("SPY", "QQQ", "^VIX")


def market_is_open() -> bool:
    return in_market_window()


def pull_live(panel_daily_path, panel_weekly_path, panel_daily_bars) -> dict:
    """One FMP call, then recompute trend + the index/VIX legs of extension.

    `panel_daily_bars` = the already-loaded [date,ticker,open,high,low,close]
    DataFrame for SPY/QQQ (callers already have this loaded for the nightly
    path; passed in rather than re-read here so this stays a pure function
    of its inputs, same discipline as the rest of this package).

    Returns None (never raises) if the FMP pull fails outright — callers
    fall back to the nightly batch artifact, which is always the safe
    default the page loads before any click.
    """
    try:
        quotes = FMPClient().get_quotes_batch(list(LIVE_SYMBOLS))
    except Exception:  # noqa: BLE001 — a live refresh must never crash the page
        return None
    if not quotes:
        return None

    live_prices = {sym: q["price"] for sym, q in quotes.items()
                   if sym in ("SPY", "QQQ") and q.get("price") is not None}
    live_vix = (quotes.get("^VIX") or {}).get("price")
    live_ts = (quotes.get("^VIX") or quotes.get("SPY") or {}).get("ts")

    t = trend.compute_market_trend(panel_daily_path, panel_weekly_path,
                                    live_prices=live_prices)

    # ATR-14 and SMA-50 are both multi-day and don't meaningfully move
    # intraday, so the index-extension leg is left at its EOD read here —
    # only trend.py's SMA10/20 cross (above) is fast enough to matter live.
    frames = cboe.series_frames()
    idx = {sym: extension.index_atr_multiple(
               panel_daily_bars[panel_daily_bars["ticker"] == sym])
           for sym in ("SPY", "QQQ")}

    ext = {
        "index_atr": idx,
        "vix_vix3m": extension.vix_vix3m(
            frames.get("vix"), frames.get("vix3m"),
            live_vix=live_vix, live_vix_ts=live_ts),
    }

    return {
        "trend": t, "extension": ext,
        "pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quotes_used": sorted(live_prices) + (["^VIX"] if live_vix is not None else []),
    }
