"""The volatility complex, straight from Cboe. No key, no plan, no vendor.

FMP gates `^VIXEQ`, `^VIX3M`, `^VIX9D` and the correlation indices behind a
higher tier. Cboe **computes** those indices and publishes their full history as
free CSVs, so — exactly as with COT — we take them from the publisher rather
than pay a reseller for a public file.

    https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYMBOL>_History.csv

Verified live 2026-08-09: every symbol below returns HTTP 200. VIXEQ carries
3,052 sessions back to 2014-06-19.

**This replaces the realised-dispersion proxy.** `vol.py` kept a realised
stand-in because the implied series was unavailable; it is available, so the
implied spread is now the primary reading and the proxy is a last resort.

Three instruments, not one, because they answer the same question from different
angles and disagreeing is informative:

  * **VIXEQ − VIX** — Crown's own tool (§2.4). Single-stock vol minus index vol.
  * **DSPX** — Cboe's purpose-built S&P 500 Dispersion Index. Same question,
    constructed by the people who define the inputs.
  * **COR1M** — implied correlation. The mechanical other side of dispersion:
    index variance is constituent variance times correlation, so a collapsing
    correlation IS a widening spread. It moves opposite by construction
    (measured -0.61 against the spread over the common history).
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from src.data.paths import DATA_DIR

CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"
CBOE_CACHE = DATA_DIR / "crown_cboe.parquet"
HTTP_TIMEOUT = 60

# What each series is for. Keys are OUR names; values are Cboe's symbols.
SERIES = {
    "vix": "VIX",          # 30-day SPX implied vol
    "vixeq": "VIXEQ",      # S&P 500 constituent volatility — Crown's single-stock leg
    "dspx": "DSPX",        # Cboe S&P 500 Dispersion Index
    "cor1m": "COR1M",      # 1-month implied correlation
    "cor3m": "COR3M",
    "vix3m": "VIX3M",      # term structure
    "vix9d": "VIX9D",
    "vvix": "VVIX",        # vol of vol
    "rvx": "RVX",          # Russell 2000 vol — small-cap stress
}

# The full complex is ~9 requests. Everything the kernel actually routes on is
# in this subset, so a fast path exists for the daily run.
CORE = ("vix", "vixeq", "dspx", "cor1m", "vix3m", "vix9d")


def parse_history(text: str, symbol: str) -> pd.DataFrame:
    """One Cboe history CSV -> (date, close). Pure; no network.

    Two shapes ship from the same endpoint: the older indices carry
    OPEN/HIGH/LOW/CLOSE, the newer ones (VIXEQ, DSPX) carry a single column
    named after the symbol. The header is located rather than assumed, because
    some files lead with a disclaimer line.
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().upper().startswith("DATE")), None)
    if start is None:
        return pd.DataFrame()

    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df.columns = [str(c).strip().upper() for c in df.columns]
    if "DATE" not in df.columns:
        return pd.DataFrame()

    col = ("CLOSE" if "CLOSE" in df.columns
           else (symbol.upper() if symbol.upper() in df.columns else None))
    if col is None:
        # Fall back to the only non-date numeric column, if there is exactly one.
        others = [c for c in df.columns if c != "DATE"]
        if len(others) != 1:
            return pd.DataFrame()
        col = others[0]

    out = pd.DataFrame({
        "date": pd.to_datetime(df["DATE"], errors="coerce"),
        "close": pd.to_numeric(df[col], errors="coerce"),
    }).dropna()
    return out.sort_values("date").reset_index(drop=True)


def fetch_series(symbol: str) -> pd.DataFrame:
    """One index's full history. Empty frame on failure — the caller reports."""
    try:
        r = requests.get(CBOE_URL.format(symbol=symbol), timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": "AQE/1.0 (research)"})
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"[crown.cboe] fetch failed {symbol}: {exc}", flush=True)
        return pd.DataFrame()
    return parse_history(r.text, symbol)


def refresh(keys=CORE, *, cache=None) -> dict:
    """Pull the complex and cache it. Returns a status dict.

    Cached beside the panels and carried by Daily Persist so the percentile
    windows survive a container recycle. Unlike COT this is cheap to re-pull in
    full (each file is one request for the entire history), so there is no
    incremental-append complexity to get wrong.
    """
    path = CBOE_CACHE if cache is None else cache
    frames, got, bad = [], [], []
    for key in keys:
        sym = SERIES.get(key, key.upper())
        df = fetch_series(sym)
        if df.empty:
            bad.append(sym)
            continue
        df = df.assign(series=key)
        frames.append(df)
        got.append(key)

    if not frames:
        return {"ok": False, "reason": "no Cboe series fetched",
                "series": [], "missing": bad, "as_of": None}

    all_df = (pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset=["series", "date"], keep="last")
                .sort_values(["series", "date"])
                .reset_index(drop=True))
    try:
        all_df.to_parquet(path, index=False)
    except Exception as exc:
        print(f"[crown.cboe] cache write failed: {exc}", flush=True)

    as_of = all_df["date"].max()
    return {"ok": True, "series": got, "missing": bad,
            "rows": int(len(all_df)),
            "as_of": as_of.date().isoformat() if pd.notna(as_of) else None}


def load_cached() -> pd.DataFrame:
    if not CBOE_CACHE.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(CBOE_CACHE)
    except Exception:
        return pd.DataFrame()


def series_frames(df: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Split the cache into {key: (date, close)} frames, the shape `vol.py` wants."""
    if df is None:
        df = load_cached()
    if df is None or df.empty:
        return {}
    return {k: g[["date", "close"]].sort_values("date").reset_index(drop=True)
            for k, g in df.groupby("series")}
