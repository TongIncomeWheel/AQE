#!/usr/bin/env python3
"""Daily Universe Screen — Decision D-3.

================================ DEPRECATED (handoff/08, Lane 1) ================================
  NO LONGER the production universe source. FMP feeds the AQE engine UPSTREAM; the kernel does
  NOT re-screen FMP. The production universe is built by tools/universe_build.py from
  output/aqe_daily_export.json (the AQE export IS the scored universe, D-66). This second FMP
  screen is dead in the scheduled container anyway (no FMP_API_KEY). It is KEPT ON DISK because
  it is a valid STANDALONE FMP screen (ad-hoc research / a sanity cross-check), but it is retired
  from the premarket path and must not write the production data/sod/DATE/universe.json.
==================================================================================================

The screen IS the universe.

Criteria (RB:universe.screen — change them in rulebook.yaml, not here):
  - US primary listings, common stock only (no ETFs/ADR-secondaries/OTC)
  - close at/above ANY of EMA20 / EMA50 / EMA100
  - market cap >= $2bn
  - current volume >= 30-day average volume

Data source: FMP (API key in env FMP_API_KEY).
Output: data/sod/YYYY-MM-DD/universe.json — the ONLY universe file any voice sees
(the standard SOD shelf layout every skill/tool writes to — BL-012).

Usage: python3 universe_screen.py [--out data/sod] [--dry-run]
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


NEAR = _P["universe"].get("near_miss", {"ema_band_pct": 2.0, "vol_band_pct": 10.0})   # D-37


def evaluate(symbol):
    """Return ('PASS'|'NEAR'|'FAIL', record|None). NEAR (D-37) = fails the screen but is
    within band on the criteria it missed — surfaced for PM/committee revival, NOT nominated,
    so the screen stops being a silent early cut."""
    try:
        bars = _get("historical-price-eod/light", symbol=symbol, limit=400)  # DS-F6
    except Exception:
        return ("FAIL", None)
    if not isinstance(bars, list) or len(bars) < 40:
        return ("FAIL", None)
    bars = sorted(bars, key=lambda b: b["date"])
    closes = [b["price"] if "price" in b else b.get("close") for b in bars]
    vols = [b.get("volume", 0) for b in bars]
    close = closes[-1]
    emas = {n: ema(closes, n) for n in (20, 50, 100)}
    valid_emas = [e for e in emas.values() if e is not None]
    above_any = any(close >= e for e in valid_emas)
    prior30 = vols[-31:-1] if len(vols) > 31 else vols[:-1]
    avg30 = sum(prior30) / max(len(prior30), 1)
    vol_ok = vols[-1] >= avg30
    vol_ratio = round(vols[-1] / max(avg30, 1), 2)
    if above_any and vol_ok:
        return ("PASS", {"ticker": symbol, "close": close,
                         "above_ema": [n for n, e in emas.items() if e and close >= e],
                         "vol_vs_30d": vol_ratio})
    # near-miss bands
    nearest = min((e for e in valid_emas if e > close), default=None)  # closest EMA above price
    ema_near = above_any or (nearest is not None and close >= nearest * (1 - NEAR["ema_band_pct"] / 100.0))
    vol_near = vol_ok or (vols[-1] >= avg30 * (1 - NEAR["vol_band_pct"] / 100.0))
    if ema_near and vol_near:
        why = []
        if not above_any and nearest: why.append(f"{round((nearest-close)/close*100,1)}% below EMA")
        if not vol_ok: why.append(f"vol {vol_ratio}x (just under)")
        return ("NEAR", {"ticker": symbol, "close": close, "vol_vs_30d": vol_ratio,
                         "near_miss_reason": " · ".join(why) or "borderline"})
    return ("FAIL", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sod", help="SOD shelf root; file lands at <out>/<DATE>/universe.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-names", type=int, default=0, help="cap for testing")
    a = ap.parse_args()
    pool = base_pool()
    print(f"server-side pool: {len(pool)} names", file=sys.stderr)
    if a.max_names:
        pool = pool[: a.max_names]
    out, near, dropped = [], [], 0
    for i, s in enumerate(pool):
        status, r = evaluate(s)
        if status == "PASS":
            out.append(r)
        elif status == "NEAR":
            near.append(r)          # D-37: surfaced for revival, NOT nominated
        else:
            dropped += 1
        if i % 200 == 0:
            print(f"  {i}/{len(pool)} screened, {len(out)} passing, {len(near)} near", file=sys.stderr)
        time.sleep(0.05)
    doc = {"date": str(date.today()), "criteria": SCREEN, "count": len(out), "names": out,
           "near_misses": near}   # D-37: visible list; the committee/PM may revive one, it is NOT auto-nominated
    if a.dry_run:
        print(json.dumps({**doc, "names": out[:10], "near_misses": near[:10]}, indent=1))
        return
    outdir = os.path.join(a.out, str(date.today()))   # SOD shelf: data/sod/DATE/ (BL-012)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "universe.json")
    json.dump(doc, open(path, "w"), indent=1)
    print(f"wrote {path}: {len(out)} names, {len(near)} near-misses ({dropped} dropped)")


if __name__ == "__main__":
    main()
