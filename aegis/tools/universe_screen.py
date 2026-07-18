#!/usr/bin/env python3
"""Daily Universe Screen — Decision D-3. The screen IS the universe.

Criteria (RB:universe.screen — change them in rulebook.yaml, not here):
  - US primary listings, common stock only (no ETFs/ADR-secondaries/OTC)
  - close at/above ANY of EMA20 / EMA50 / EMA100
  - market cap >= $2bn
  - current volume >= 30-day average volume

Data source: FMP (API key in env FMP_API_KEY).
Output: data/universe/universe_YYYY-MM-DD.json — the ONLY universe file any voice sees.

Usage: python3 universe_screen.py [--out data/universe/] [--dry-run]
"""
import argparse, json, os, sys, time, urllib.request
from datetime import date

import yaml

FMP = "https://financialmodelingprep.com/stable"
_C = os.path.join(os.path.dirname(__file__), "..", "charter")
_P = yaml.safe_load(open(os.path.join(_C, "parameters.yaml")))
SCREEN = _P["universe"]["screen"]   # QA-F1 fix: screen params live in parameters.yaml
KEY = os.environ.get("FMP_API_KEY", "")


def _get(path, **params):
    params["apikey"] = KEY
    q = "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(f"{FMP}/{path}?{q}", timeout=60) as r:
        return json.load(r)


def base_pool():
    """FMP company screener does the cheap cuts server-side: US, mcap, exchange, type."""
    rows = _get(
        "company-screener",
        marketCapMoreThan=int(SCREEN["market_cap_min_usd"]),
        isEtf="false", isFund="false", isActivelyTrading="true",
        country="US", exchange="NYSE,NASDAQ,AMEX", limit=5000,
    )
    return [r["symbol"] for r in rows if r.get("symbol")]  # DS-F8: keep BRK.B-class symbols; ADR/secondary filtering via exchange param


def ema(closes, n):
    if len(closes) < n:
        return None
    k = 2 / (n + 1)
    e = sum(closes[:n]) / n
    for c in closes[n:]:
        e = c * k + e * (1 - k)
    return e


def passes(symbol):
    """EMA + volume cuts need bars: 1 call per name (batch where plan allows)."""
    try:
        bars = _get("historical-price-eod/light", symbol=symbol, limit=400)  # DS-F6: EMA100 needs ~4x n bars to converge
    except Exception:
        return None
    if not isinstance(bars, list) or len(bars) < 40:
        return None
    bars = sorted(bars, key=lambda b: b["date"])
    closes = [b["price"] if "price" in b else b.get("close") for b in bars]
    vols = [b.get("volume", 0) for b in bars]
    close = closes[-1]          # last COMPLETED bar (run premarket; FMP eod bars only)
    emas = {n: ema(closes, n) for n in (20, 50, 100)}
    above_any = any(e is not None and close >= e for e in emas.values())
    prior30 = vols[-31:-1] if len(vols) > 31 else vols[:-1]   # DS-F7: compare vs prior 30, EXCLUDING the compared bar
    vol_ok = vols[-1] >= (sum(prior30) / max(len(prior30), 1))
    if above_any and vol_ok:
        return {"ticker": symbol, "close": close,
                "above_ema": [n for n, e in emas.items() if e and close >= e],
                "vol_vs_30d": round(vols[-1] / max(sum(vols[-30:]) / 30, 1), 2)}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/universe")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-names", type=int, default=0, help="cap for testing")
    a = ap.parse_args()
    pool = base_pool()
    print(f"server-side pool: {len(pool)} names", file=sys.stderr)
    if a.max_names:
        pool = pool[: a.max_names]
    out, dropped = [], 0
    for i, s in enumerate(pool):
        r = passes(s)
        if r:
            out.append(r)
        else:
            dropped += 1
        if i % 200 == 0:
            print(f"  {i}/{len(pool)} screened, {len(out)} passing", file=sys.stderr)
        time.sleep(0.05)  # FMP plan courtesy; tune per plan rate limit
    doc = {"date": str(date.today()), "criteria": SCREEN, "count": len(out), "names": out}
    if a.dry_run:
        print(json.dumps({**doc, "names": out[:10]}, indent=1))
        return
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"universe_{date.today()}.json")
    json.dump(doc, open(path, "w"), indent=1)
    print(f"wrote {path}: {len(out)} names ({dropped} dropped at bar-level)")


if __name__ == "__main__":
    main()
