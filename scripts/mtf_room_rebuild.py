"""Rebuild a finished run's mtf.json with the CURRENT mtf.py (render-only; PM/conductor 2026-11-05).

Same path the nightly uses: committee_data.build_grid (FMP daily + hourly, bars cut at the run date) -> mtf.py build --grid -> mtf.json.
Prints the result between MTF_JSON_BEGIN / MTF_JSON_END (one compact line) plus one SWING line per room name, and writes nothing to the repo.

  python -m scripts.mtf_room_rebuild aegis/output/pma/run/2026-11-05 2026-11-05
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from src.data.fmp_client import FMPClient
from src.pipeline import committee_data as CD

run_dir, run_date = Path(sys.argv[1]), sys.argv[2]
tool = Path("aegis/plugin/aegis-core/skills/pma/tools/mtf.py")
spec = importlib.util.spec_from_file_location("mtf_rebuild", tool)
mtf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mtf)

room = list(json.load(open(run_dir / "phase4.json")).get("deliberation_set") or [])
export = json.load(open("aegis/output/aqe_daily_export.json"))
print(f"room {len(room)} names, run date {run_date}, export {export.get('date')}", flush=True)
f = CD.Fetcher(FMPClient())
grid = CD.build_grid(f, room, run_date, export, {}, mtf)          # no panel in the runner: every name is fetched from FMP
print(f"fetched with {f.calls} FMP calls; errors: {f.errors[:3]}; coverage {grid['coverage']}", flush=True)
with tempfile.TemporaryDirectory() as td:
    gp, out = Path(td) / "mtf_grid.json", Path(td) / "mtf.json"
    gp.write_text(json.dumps(grid))
    r = subprocess.run([sys.executable, str(tool), "build", "--grid", str(gp), "--phase4", str(run_dir / "phase4.json"), "--date", run_date, "--out", str(out)],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-500:], flush=True)
    if r.returncode != 0:
        sys.exit(f"mtf.py build failed ({r.returncode})")
    doc = json.loads(out.read_text())
for t, row in doc["names"].items():
    if row.get("served"):
        cl = lambda tf: (row.get(tf) or {}).get("swing_class") or ("not served" if not (row.get(tf) or {}).get("served") else "none")
        sh = ((row.get("D") or {}).get("swing") or {}).get("close_vs_swing_high_pct")
        print(f"SWING {t:6s} W={cl('W'):10s} D={cl('D'):10s} H1={cl('H1'):10s} dailyCloseVsSwingHigh={sh} momentum={(row.get('momentum') or {}).get('flag')}")
    else:
        print(f"SWING {t:6s} NOT SERVED: {row.get('reason')}")
print("MEASUREMENT", json.dumps(doc["measurement"]))
print("MTF_JSON_BEGIN")
print(json.dumps(doc, separators=(",", ":")))
print("MTF_JSON_END")
