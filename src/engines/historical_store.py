"""Historical data store — the layered anchoring store (D-32).

A data-objects database LAYERED AWAY from the daily feed. Pulled from FMP, resampled to
compact MONTHLY OHLC + return stats per ticker, written to data/historical/<ticker>.json.
Its purpose is ANCHORING — empirical return distributions (DoR), kNN/CHoCH context,
forward-return ledger tracking, backtests — queried on demand. It must NEVER be streamed
into the agents' daily 177-name feed (that stays lean); this store is a separate layer.

Production: `load_ticker(ticker)` uses AQE's FMPClient. Ingestion is pure (`ingest_fmp_eod`)
so it is testable from any raw FMP EOD list.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "data" / "historical"


def ingest_fmp_eod(ticker: str, eod_rows: list, from_date: str = "", to_date: str = "") -> dict:
    """Resample a raw FMP EOD list (each {date, price/close, ...}, any order) into the
    compact monthly store object (contracts/historical_store.schema.json)."""
    rows = sorted(
        ({"date": r["date"],
          "o": r.get("open", r.get("price")), "h": r.get("high", r.get("price")),
          "l": r.get("low", r.get("price")), "c": r.get("close", r.get("price"))}
         for r in eod_rows if r.get("date")),
        key=lambda x: x["date"])
    # group by YYYY-MM
    months: dict[str, list] = {}
    for r in rows:
        months.setdefault(r["date"][:7], []).append(r)
    monthly = []
    prev_close = None
    for m in sorted(months):
        bars = months[m]
        o = bars[0]["o"]; c = bars[-1]["c"]
        h = max(b["h"] for b in bars); l = min(b["l"] for b in bars)
        ret = round((c / prev_close - 1) * 100, 2) if prev_close else None
        rng = round((h - l) / prev_close * 100, 2) if prev_close else None
        monthly.append({"month": m, "o": round(o, 4), "h": round(h, 4), "l": round(l, 4),
                        "c": round(c, 4), "ret_pct": ret, "range_pct": rng})
        prev_close = c
    rets = [x["ret_pct"] for x in monthly if x["ret_pct"] is not None]
    mean = round(sum(rets) / len(rets), 3) if rets else None
    std = round((sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5, 3) if len(rets) > 1 else None
    stats = {"n_months": len(monthly), "monthly_ret_mean_pct": mean, "monthly_ret_std_pct": std,
             "ann_vol_pct": round(std * math.sqrt(12), 2) if std is not None else None}
    return {"ticker": ticker, "source": "FMP", "as_of": to_date or (rows[-1]["date"] if rows else ""),
            "from_date": from_date or (rows[0]["date"] if rows else ""),
            "to_date": to_date or (rows[-1]["date"] if rows else ""),
            "monthly": monthly, "stats": stats}


def save(obj: dict) -> str:
    STORE.mkdir(parents=True, exist_ok=True)
    path = STORE / f"{obj['ticker']}.json"
    json.dump(obj, open(path, "w"), indent=1)
    # update the manifest (coverage index) — NOT the daily feed
    man = STORE / "manifest.json"
    m = json.load(open(man)) if man.exists() else {}
    m[obj["ticker"]] = {"as_of": obj["as_of"], "n_months": obj["stats"]["n_months"]}
    json.dump(m, open(man, "w"), indent=1)
    return str(path)


def load_ticker(ticker: str) -> dict:
    """Production loader: pull EOD from FMP and store. Uses AQE's FMPClient."""
    from src.data.fmp_client import FMPClient  # AQE's existing client
    eod = FMPClient().historical_price(ticker)  # returns the EOD list
    obj = ingest_fmp_eod(ticker, eod)
    save(obj)
    return obj


def get(ticker: str) -> dict | None:
    path = STORE / f"{ticker}.json"
    return json.load(open(path)) if path.exists() else None
