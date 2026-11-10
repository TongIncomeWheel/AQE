#!/usr/bin/env python3
"""universe_diagnose.py -- find the stage that trims the scan universe (PM 2026-11-10: TTD and ~400 rule-qualifying names are not scored).

Writes nothing. Re-runs build_universe's own pass 1 stage by stage with every count printed (screener rows, country and exchange mix, candidates,
quote chunks that failed, names with no quote, the avgVolume split, the verification cap), traces a watch list through each stage, then runs the
REAL build_universe(dry_run=True) and diffs its result against the scored universe file (aegis/output/aqe_universe_rows.json by default), naming
what the dry run admits that was never scored and what was scored that the dry run does not admit.

    python -m scripts.universe_diagnose [scored_rows.json] [WATCH ...]
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_WATCH = ["ADM", "MCHP", "CPRT", "DXCM", "EQT", "CCJ", "RPRX", "FISV", "VYLR", "TTD", "MOS", "CLF", "KTOS", "HUT", "CAVA",
                 "TD", "TTE", "BNS", "NWG", "BIRK", "GLBE", "G", "SBSW", "LU"]


def probe():
    """Which quote endpoint answers a comma-separated batch? Prints the raw shape of each; changes nothing."""
    from src.data import fmp_client as F
    c = F.FMPClient()
    syms = ["AAPL", "MSFT", "ADM", "MCHP", "TTD"]
    base = F.FMP_BASE_STABLE
    tries = [("quote?symbol=a,b,c", f"{base}/quote", {"symbol": ",".join(syms)}),
             ("quote?symbols=a,b,c", f"{base}/quote", {"symbols": ",".join(syms)}),
             ("batch-quote?symbols=a,b,c", f"{base}/batch-quote", {"symbols": ",".join(syms)}),
             ("quote-short?symbol=a,b,c", f"{base}/quote-short", {"symbol": ",".join(syms)}),
             ("quote?symbol=AAPL (single)", f"{base}/quote", {"symbol": "AAPL"})]
    for name, url, params in tries:
        try:
            r = c._get_json(url, params=dict(params, apikey=c.config.api_key))
            keys = sorted(r[0].keys())[:14] if isinstance(r, list) and r and isinstance(r[0], dict) else None
            print(f"[probe] {name}: type={type(r).__name__} len={len(r) if hasattr(r, '__len__') else '-'} "
                  f"symbols={[x.get('symbol') for x in r][:6] if isinstance(r, list) else None} avgVolume={[x.get('avgVolume') for x in r][:3] if isinstance(r, list) else None} keys={keys}")
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] {name}: ERROR {type(exc).__name__}: {str(exc)[:160]}")
    for tk in ["TD", "TTE", "BNS", "NWG", "TCOM", "JBS", "RYAAY", "TECK", "EC", "ARM", "SHOP", "SPOT", "ACN", "LIN", "ETN", "CCJ", "BIRK", "GLBE", "PDD",
               "TSM", "ASML", "HSBC", "BABA", "G", "SBSW", "LU", "AAPL"]:
        try:
            r = c._get_json(f"{base}/profile", params={"symbol": tk, "apikey": c.config.api_key})
            r = (r[0] if isinstance(r, list) and r else r) or {}
            print(f"[probe] profile {tk:6} isAdr={r.get('isAdr')} isEtf={r.get('isEtf')} isFund={r.get('isFund')} country={r.get('country')} "
                  f"exchange={r.get('exchange')} currency={r.get('currency')} cik={r.get('cik')} isin={r.get('isin')}")
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] profile {tk}: ERROR {str(exc)[:120]}")
    rows = c.get_screener(min_mcap=2_000_000_000, min_price=5.0, min_volume=500_000, exchanges=["NASDAQ", "NYSE"], limit=5)
    print("[probe] screener row keys:", sorted(rows[0].keys()) if rows else None)
    for name, extra in (("country=US", {"country": "US"}), ("isAdr=false", {"isAdr": "false"}), ("isFund=false", {"isFund": "false"})):
        try:
            params = {"apikey": c.config.api_key, "marketCapMoreThan": "2000000000", "exchange": "NASDAQ,NYSE", "isActivelyTrading": "true",
                      "isEtf": "false", "volumeMoreThan": "500000", "priceMoreThan": "5", "limit": "5000", **extra}
            r = c._get_json(f"{base}/company-screener", params=params)
            import collections
            print(f"[probe] screener {name}: rows={len(r)} countries={dict(collections.Counter(x.get('country') for x in r).most_common(5))}")
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] screener {name}: ERROR {exc}")


def main(argv):
    if argv and argv[0] == "--probe":
        probe(); return 0
    from src.data import universe as U
    from src.data.fmp_client import FMPClient, FMPError

    scored_path = Path(argv[0]) if argv and argv[0].endswith(".json") else ROOT / "aegis/output/aqe_universe_rows.json"
    watch = [a.upper() for a in (argv[1:] if argv and argv[0].endswith(".json") else argv)] or DEFAULT_WATCH
    scored = {r["ticker"] for r in json.load(open(scored_path))["rows"]} if scored_path.exists() else set()
    print(f"scored universe file: {scored_path} -> {len(scored)} names")

    client = FMPClient()
    raw = client.get_screener(min_mcap=U.SCREEN_MCAP, min_price=0, min_volume=0, exchanges=U.UNIVERSE_EXCHANGES, limit=5000)
    print(f"[screener] rows: {len(raw)}; exchange mix:", dict(collections.Counter(r.get("exchangeShortName") or r.get("exchange") for r in raw)))
    print("           country mix (top 8):", collections.Counter(r.get("country") for r in raw).most_common(8))
    by_sym = {(r.get("symbol") or "").upper().strip(): r for r in raw}
    print("[trace] watch list (the screener row; the build's own split decides admit / verify / reject):")
    for tk in watch:
        r = by_sym.get(tk)
        if r is None:
            print(f"   {tk:6} NOT in the screener (mcap / exchange / activity)"); continue
        av = r.get("avgVolume")
        band = ("admit (>= %s)" % f"{U.SCREEN_AVG_VOL_HIGH:,}" if av and av >= U.SCREEN_AVG_VOL_HIGH else
                "reject cheap" if av is not None and av < U.SCREEN_AVG_VOL_PREFILTER else "verify on bars")
        ov = U.load_universe_overrides()
        tag = "override: EXCLUDE (PM ADR list)" if tk in ov["exclude"] else "override: INCLUDE (PM ordinary-share list)" if tk in ov["include"] else \
              ("US-domiciled, no ADR check" if (r.get("country") or "").upper() == "US" else "foreign-domiciled: profiled for isAdr")
        print(f"   {tk:6} country={r.get('country')} mcap={r.get('marketCap')} avgVolume={av} -> {band} | {tag} | scored: {tk in scored}")

    print("[real dry run] build_universe(dry_run=True) ...")
    res = U.build_universe(dry_run=True)
    got = set(res.get("tickers") or [])
    print(f"[result] status={res.get('status')} total={res.get('total')} reason={res.get('reason')} errors={len(res.get('errors') or [])} {(res.get('errors') or [])[:5]}")
    print("[stages]", res.get("stages"))
    print(f"[diff vs scored file] dry run admits {len(got)}; in dry run but NOT scored: {len(got - scored)}; scored but NOT in dry run: {len(scored - got)}")
    print("   dry-run-only (first 40):", sorted(got - scored)[:40])
    print("   scored-only (first 40):", sorted(scored - got)[:40])
    for tk in watch:
        print(f"   {tk:6} in dry-run result: {tk in got} | scored: {tk in scored}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
