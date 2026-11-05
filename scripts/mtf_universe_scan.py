"""Swing-structure scan of every name in the export (read-only; conductor/PM 2026-11-05).

Same path as the room rebuild and the nightly (committee_data.build_grid, FMP daily + hourly, bars cut at the run date), for ALL daily_list names.
Prints one `UNIJSON {...}` line per name (class per frame, the daily close vs the latest daily swing high, sessions since that swing high, the
distance under the 20-day high, rank, sector, list flags, whether it is in the committee room) and a MEASUREMENT line. Writes nothing to the repo.

  python -m scripts.mtf_universe_scan aegis/output/aqe_daily_export.json aegis/output/pma/run/2026-11-05/phase4.json 2026-11-05
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from src.data.fmp_client import FMPClient
from src.pipeline import committee_data as CD

export_p, phase4_p, run_date = sys.argv[1], sys.argv[2], sys.argv[3]
tool = Path("aegis/plugin/aegis-core/skills/pma/tools/mtf.py")
spec = importlib.util.spec_from_file_location("mtf_uni", tool)
mtf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mtf)

export = json.load(open(export_p))
rows = {r["ticker"]: r for r in export.get("daily_list") or [] if r.get("ticker")}
room = set(json.load(open(phase4_p)).get("deliberation_set") or [])
tickers = list(rows)
print(f"universe {len(tickers)} names, room {len(room)}, run date {run_date}, export {export.get('date')}", flush=True)
f = CD.Fetcher(FMPClient(), budget_s=1700)
grid = CD.build_grid(f, tickers, run_date, export, {}, mtf)
print(f"fetched with {f.calls} FMP calls; errors: {f.errors[:3]}; coverage {grid['coverage']}", flush=True)

for t in tickers:
    g, r = grid["names"].get(t) or {}, rows[t]
    W, D, H = (g.get(k) or {} for k in ("W", "D", "H1"))
    sw = D.get("swing") or {}
    lsh = (sw.get("last_swing_high") or {}).get("date")
    since = None
    if lsh and D.get("last_bar_date"):
        since = int(np.busday_count(lsh, D["last_bar_date"][:10]))      # weekday count between the swing-high bar and the last bar (holidays ignored)
    print("UNIJSON " + json.dumps({
        "t": t, "served": bool(g.get("served")), "W": W.get("swing_class"), "D": D.get("swing_class"), "H1": H.get("swing_class"),
        "w_served": bool(W.get("served")), "d_served": bool(D.get("served")), "h_served": bool(H.get("served")),
        "d_vs_sh": sw.get("close_vs_swing_high_pct"), "sh": (sw.get("last_swing_high") or {}).get("price"), "sh_date": lsh, "since_sh": since,
        "d_under_20hi": D.get("dist_to_20bar_high_pct"), "hi20_date": D.get("high_20bar_date"), "close": D.get("close"),
        "momentum": (g.get("momentum") or {}).get("flag"), "rank": r.get("rank"), "sector": r.get("gics_sector_name"),
        "ll": bool(r.get("on_longlist")), "el": bool(r.get("on_elder")), "room": t in room}, separators=(",", ":")), flush=True)
print("MEASUREMENT", json.dumps(grid["coverage"]))
print("UNI_DONE")
