"""Run ONLY Step 8a-4 (the committee's FMP inputs) against the export already on main (PM 2026-11-03).

Used by .github/workflows/committee-data.yml: proves the fetch live without redoing the 28-minute daily pipeline
and without touching the day's export, packets, levels or alerts. Writes and publishes ONLY
aegis/output/committee_data/ (manifest last). Safe to rerun: fundamentals already fetched in the last 5 days are
carried (a rerun is fast), publishing identical content is a no-op, and a FAILED or PARTIAL rerun never overwrites
an OK set already published for the same run date.

    python -m scripts.committee_data_run [--export aegis/output/aqe_daily_export.json] [--run-date YYYY-MM-DD]
                                         [--budget-minutes 30] [--no-publish]
Exit 0 = the set is OK (and published); 1 = anything else. The log carries the numbers (cd.describe).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import committee_data as cd  # noqa: E402

OUT_DIR = ROOT / "aegis" / "output" / "committee_data"


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except ValueError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export", default=str(ROOT / "aegis" / "output" / "aqe_daily_export.json"))
    ap.add_argument("--run-date", default=None, help="default: the export's own date (the SGT run date it was built for)")
    ap.add_argument("--budget-minutes", type=float, default=30.0)
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    a = ap.parse_args(argv)
    out_dir = Path(a.out_dir)

    export = _read(Path(a.export))
    if not isinstance(export, dict) or not export.get("daily_list"):
        print(f"FAILED: {a.export} is missing, unreadable or has no daily_list - nothing to fetch for")
        return 1
    run_date = (a.run_date or str(export.get("date") or "")[:10]) or datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()
    print(f"export {a.export}: date {export.get('date')}, exported_at {export.get('exported_at')}, "
          f"{len(export['daily_list'])} daily_list rows, {len(export.get('held_positions') or [])} held; run date {run_date}")

    existing_manifest = _read(out_dir / "manifest.json")
    previous_pack = _read(out_dir / "fundamentals_pack.json")
    print(f"previous pack on disk: {'yes, ' + str(len((previous_pack or {}).get('tickers') or {})) + ' names (young entries are carried)' if previous_pack else 'none - every name is fetched'}")

    res = cd.run(export, run_date, previous_pack=previous_pack, universe_previous=_read(out_dir / cd.UNIVERSE_HISTORY), budget_s=a.budget_minutes * 60)
    print(cd.describe(res))
    m = res["manifest"]

    if (existing_manifest or {}).get("status") == "OK" and existing_manifest.get("run_date") == run_date and m["status"] != "OK":
        print(f"\nNOT publishing: this run is {m['status']} and an OK set for {run_date} is already on disk "
              f"(generated {existing_manifest.get('generated_at')}). Kept it. Fix the cause and rerun.")
        return 1

    cd.write_local(res, out_dir)
    if a.no_publish:
        print("\n--no-publish: written locally only")
        return 0 if m["status"] == "OK" else 1
    pub = cd.publish(res)
    print("\n" + cd.summary_line(res, pub))
    if pub["failed"]:
        for x in pub["failed"]:
            print(f"  PUBLISH FAILED: {x}")
    return 0 if (m["status"] == "OK" and pub["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
