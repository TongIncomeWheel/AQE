"""Run the M&A flag scan over an export's tickers and print the flagged list (PM 2026-11-04). Used by
.github/workflows/ma-flag-dryrun.yml with FMP_API_KEY; writes data/ma_flags.json (the same cache the nightly reads)."""
from __future__ import annotations

import json
import sys
from datetime import date

from src.data import ma_flag as M
from src.data.fmp_client import FMPClient

path = sys.argv[1] if len(sys.argv) > 1 else "aegis/output/aqe_daily_export.json"
exp = json.load(open(path, encoding="utf-8"))
tickers = {r["ticker"] for r in (exp.get("daily_list") or []) if r.get("ticker")} | {r["ticker"] for r in (exp.get("held_positions") or []) if r.get("ticker")}
print(f"scanning {len(tickers)} tickers from {path} (export date {exp.get('date')})")
art = M.refresh(sorted(tickers), FMPClient(), today=date.today(), breaker=False)      # dry-run shows the raw flags; the nightly keeps the circuit breaker
n_t = sum(1 for v in art['tickers'].values() if v['ma_status'] == 'PENDING_TARGET')
print(f"PENDING_TARGET={n_t}; the nightly circuit breaker trips above {max(5, int(0.03 * art['n_scanned']))}")
print(f"scan_status={art['scan_status']} scanned={art['n_scanned']} failed={art['n_failed']} flagged={art['n_flagged']}")
if art["failed"]:
    print("FAILED:", art["failed"])
for tk, v in sorted(art["tickers"].items()):
    if v["ma_status"] not in ("NONE",):
        print(f"{tk:7s} {v['ma_status']:17s} {v['ma_note']}")
        if v.get("ma_evidence"):
            print(f"        url={v['ma_evidence'].get('url')} terms={v['ma_evidence'].get('terms')}")
