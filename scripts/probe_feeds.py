"""One-shot probe of the data feeds' publish times and plan limits (conductor 2026-11-04, Q1/Q3/Q5). Prints evidence only;
never writes. Run by .github/workflows/probe-feeds.yml with FMP_API_KEY."""
from __future__ import annotations

import os
import sys

import requests

BASE = "https://financialmodelingprep.com/stable"
KEY = os.environ.get("FMP_API_KEY", "")
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-11-03"


def fmp(path, **params):
    params["apikey"] = KEY
    try:
        r = requests.get(f"{BASE}/{path}", params=params, timeout=90)
        body = r.text
        n = body.count("\n") + 1
        print(f"FMP {path} {({k: v for k, v in params.items() if k != 'apikey'})}: HTTP {r.status_code}, {len(r.content):,} bytes, ~{n:,} lines")
        print("   head:", body[:230].replace("\n", " | "))
    except Exception as e:  # noqa: BLE001
        print(f"FMP {path}: ERROR {e.__class__.__name__}: {e}")


print("== Q3 FMP bulk / market-wide endpoints on OUR plan ==")
fmp("eod-bulk", date=DATE)
fmp("batch-exchange-quote", exchange="NASDAQ")
fmp("batch-exchange-quote", exchange="NYSE")
fmp("batch-quote", symbols="AAPL,MSFT,NVDA")
fmp("historical-price-eod/full", symbol="AAPL", **{"from": DATE, "to": DATE})
print("== Q2 FMP index series same-day ==")
for s in ("^VIX", "^VIX3M", "^VIX9D", "^VIXEQ", "^DSPX", "^COR1M"):
    fmp("historical-price-eod/light", symbol=s, **{"from": "2026-11-01", "to": DATE})
print("== Q1 Cboe publish times (Last-Modified of each CORE file; also its newest row) ==")
for s in ("VIX", "VIXEQ", "VIX3M", "VIX9D", "DSPX", "COR1M"):
    u = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{s}_History.csv"
    try:
        r = requests.get(u, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        last = r.text.strip().splitlines()[-1]
        print(f"CBOE {s}: HTTP {r.status_code} Last-Modified={r.headers.get('Last-Modified')} newest_row={last[:40]}")
    except Exception as e:  # noqa: BLE001
        print(f"CBOE {s}: ERROR {e}")
print("== Q5 CFTC file's own report date ==")
try:
    r = requests.get("https://www.cftc.gov/dea/newcot/deafut.txt", timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    lines = r.text.splitlines()
    print(f"CFTC deafut.txt: HTTP {r.status_code}, Last-Modified={r.headers.get('Last-Modified')}, {len(lines)} rows")
    print("   first row:", lines[0][:120] if lines else None)
    dates = sorted({l.split(",")[2].strip().strip('"') for l in lines if l.count(",") > 3})
    print("   report dates in file:", dates[-3:])
except Exception as e:  # noqa: BLE001
    print(f"CFTC: ERROR {e}")
