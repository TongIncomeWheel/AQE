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


def main(argv):
    from src.data import universe as U
    from src.data.fmp_client import FMPClient, FMPError

    scored_path = Path(argv[0]) if argv and argv[0].endswith(".json") else ROOT / "aegis/output/aqe_universe_rows.json"
    watch = [a.upper() for a in (argv[1:] if argv and argv[0].endswith(".json") else argv)] or DEFAULT_WATCH
    scored = {r["ticker"] for r in json.load(open(scored_path))["rows"]} if scored_path.exists() else set()
    print(f"scored universe file: {scored_path} -> {len(scored)} names")

    client = FMPClient()
    raw = client.get_screener(min_mcap=U.SCREEN_MCAP, min_price=5.0, min_volume=500_000, exchanges=U.UNIVERSE_EXCHANGES, limit=5000)
    print(f"[stage 1] screener rows: {len(raw)}")
    print("          exchange mix:", dict(collections.Counter(r.get("exchangeShortName") or r.get("exchange") for r in raw)))
    print("          country mix (top 8):", collections.Counter(r.get("country") for r in raw).most_common(8))
    by_sym = {(r.get("symbol") or "").upper().strip(): r for r in raw}
    cand = [s for s in by_sym if s and not any(s.endswith(x) for x in U.EXCLUDED_SUFFIXES) and "." not in s and " " not in s]
    print(f"[stage 2] candidates after suffix/dot filter: {len(cand)} (dropped {len(by_sym) - len(cand)}: e.g. "
          f"{[s for s in by_sym if s not in set(cand)][:12]})")

    quotes, failed_chunks, failed_names = {}, 0, []
    for i in range(0, len(cand), 50):
        chunk = cand[i:i + 50]
        try:
            q = client.get_quotes_batch(chunk, chunk=50)
        except FMPError as exc:
            failed_chunks += 1; failed_names += chunk; print(f"          quote chunk {i // 50} FAILED: {exc}"); continue
        quotes.update(q)
        if len(q) < len(chunk):
            failed_names += [c for c in chunk if c not in q]
    missing = [c for c in cand if c not in quotes]
    print(f"[stage 3] quotes returned: {len(quotes)} of {len(cand)}; chunks failed: {failed_chunks}; names with NO quote: {len(missing)} {missing[:15]}")
    no_av = [c for c in cand if c in quotes and quotes[c].get("avg_volume") is None]
    print(f"          quote present but avgVolume null: {len(no_av)} {no_av[:15]}")

    passed, verify, rej = [], [], []
    for tk in cand:
        av = (quotes.get(tk) or {}).get("avg_volume")
        if av is None:
            verify.append(tk)
        elif av >= U.SCREEN_AVG_VOL_HIGH:
            passed.append(tk)
        elif av < U.SCREEN_AVG_VOL_PREFILTER:
            rej.append(tk)
        else:
            verify.append(tk)
    print(f"[stage 4] avgVolume split: admitted unverified {len(passed)} (>= {U.SCREEN_AVG_VOL_HIGH:,}), rejected cheap {len(rej)} (< {U.SCREEN_AVG_VOL_PREFILTER:,}), "
          f"to verify {len(verify)}; verification cap {U.SCREEN_MAX_BAR_CALLS} -> over the cap: {max(0, len(verify) - U.SCREEN_MAX_BAR_CALLS)}")
    print(f"          admitted-unverified names NOT in the scored file: {len([t for t in passed if t not in scored])} of {len(passed)}")

    def stage(tk):
        if tk not in by_sym: return "not in the FMP screener (mcap / price / volume / exchange / activity filter)"
        if tk not in cand: return "dropped by the symbol filter"
        if tk not in quotes: return "NO QUOTE returned (chunk failure or symbol absent)"
        if tk in passed: return f"admitted unverified (avgVolume {quotes[tk]['avg_volume']:,.0f})"
        if tk in rej: return f"rejected cheap (avgVolume {quotes[tk]['avg_volume']:,.0f})"
        return f"to verify (avgVolume {quotes[tk].get('avg_volume')})"
    print("[trace] watch list through pass 1 (country from the screener row):")
    for tk in watch:
        r = by_sym.get(tk) or {}
        print(f"   {tk:6} country={r.get('country')} mcap={r.get('marketCap')} | {stage(tk)} | scored: {tk in scored}")

    print("[real dry run] build_universe(dry_run=True) ...")
    res = U.build_universe(dry_run=True)
    got = set(res.get("tickers") or [])
    print(f"[result] status={res.get('status')} total={res.get('total')} errors={len(res.get('errors') or [])} {(res.get('errors') or [])[:5]}")
    print(f"[diff vs scored file] dry run admits {len(got)}; in dry run but NOT scored: {len(got - scored)}; scored but NOT in dry run: {len(scored - got)}")
    print("   dry-run-only (first 40):", sorted(got - scored)[:40])
    print("   scored-only (first 40):", sorted(scored - got)[:40])
    for tk in watch:
        print(f"   {tk:6} in dry-run result: {tk in got} | scored: {tk in scored}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
