"""Yahoo daily bars — the futures our data plan will not sell us.

**Scope: the Crown CTA universe only.** By PM exception (2026-08-10), and
deliberately not wired into the scanner, the universe builder or anything that
touches a trade. Those stay on FMP.

The problem this solves is not the ETFs — those already work. It is that FMP's
plan gates 14 of the 18 futures symbols, so `ZNUSD` and `NQUSD` return ACCESS
DENIED and the layer falls back to IEF and QQQ. The trend direction survives
that substitution; the **flip levels do not**. "Trend funds turn seller of the
10-year below 107.20" is a sentence you can act on. "…below IEF 94.10" is not.

Yahoo carries every contract we need with five years of daily history, verified
2026-08-10:

    ES=F NQ=F YM=F RTY=F ZN=F ZB=F ZF=F ZT=F CL=F BZ=F NG=F
    GC=F SI=F HG=F ZC=F ZS=F ZW=F  and  DX-Y.NYB for the dollar

**This endpoint is undocumented and unofficial.** It is not a supported API, it
carries no uptime promise, and it can rate-limit or change shape without notice.
So it sits in the MIDDLE of the chain, never at the front:

    FMP futures  ->  Yahoo futures  ->  ETF proxy

FMP stays first because it is the paid, supported source and it does work for
ES, BZ, GC and SI. The ETF proxy stays last so that if Yahoo disappears the
layer degrades to exactly what it does today rather than losing the market
entirely — `flip_risk` is extremes over the number of markets, so a shrinking
denominator quietly re-rates every reading.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HTTP_TIMEOUT = 30
# Yahoo rejects a bare python-requests user agent often enough to matter.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AQE/1.0)"}
MIN_INTERVAL = 0.35            # seconds between calls; 18 symbols once a day
_last_call = [0.0]

# Our market key -> Yahoo's symbol. The dollar is the odd one out: there is no
# `DX=F`, it is the ICE index under its own ticker.
SYMBOLS = {
    "ES": "ES=F", "NQ": "NQ=F", "YM": "YM=F", "RTY": "RTY=F",
    "ZN": "ZN=F", "ZB": "ZB=F", "ZF": "ZF=F", "ZT": "ZT=F",
    "CL": "CL=F", "BZ": "BZ=F", "NG": "NG=F",
    "GC": "GC=F", "SI": "SI=F", "HG": "HG=F",
    "DX": "DX-Y.NYB",
    "ZC": "ZC=F", "ZS": "ZS=F", "ZW": "ZW=F",
}


def parse_chart(payload: dict) -> pd.DataFrame:
    """Yahoo chart JSON -> the OHLCV frame the rest of AQE expects.

    Pure, so the shape can be tested against a recorded response without the
    network. Rows where Yahoo sends a null close are dropped rather than
    forward-filled: a hole in a futures series is a missing session, and
    inventing a bar there would put a fabricated price into a trend model.
    """
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        return pd.DataFrame()
    r = result[0]
    ts = r.get("timestamp") or []
    quote = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    if not ts or not quote.get("close"):
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": pd.to_datetime(pd.Series(ts, dtype="int64"), unit="s").dt.normalize(),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close"),
        "volume": quote.get("volume"),
    })
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).drop_duplicates(subset=["date"], keep="last")
    # A futures session with no open still has a usable close; fill the OHLC
    # legs from it rather than losing the bar.
    for c in ("open", "high", "low"):
        df[c] = df[c].fillna(df["close"])
    return df.sort_values("date").reset_index(drop=True)


def _pace() -> None:
    wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def fetch_bars(symbol: str, *, years: int = 5, http_get=None) -> pd.DataFrame:
    """Daily bars for one Yahoo symbol. Empty frame on any failure."""
    params = {"range": f"{int(years)}y", "interval": "1d"}
    try:
        if http_get is not None:
            payload = http_get(CHART_URL.format(symbol=symbol), params)
        else:
            _pace()
            resp = requests.get(CHART_URL.format(symbol=symbol), params=params,
                                headers=HEADERS, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[crown.yahoo] {symbol}: {exc}", flush=True)
        return pd.DataFrame()
    return parse_chart(payload)


def fetch_market(market_key: str, *, years: int = 5, http_get=None) -> pd.DataFrame:
    """Bars for one of OUR market keys (ES, ZN, DX...). Empty if unmapped."""
    sym = SYMBOLS.get(market_key)
    if not sym:
        return pd.DataFrame()
    return fetch_bars(sym, years=years, http_get=http_get)
