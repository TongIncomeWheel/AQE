#!/usr/bin/env python3
"""Data janitor — keeps the four shelves from growing forever (runs in Post Market, last step).
Policy from parameters.yaml retention: raw dated folders (sod/intraday/eod) older than raw_days are
rolled up (one summary json per day kept forever) and zipped into archive/YYYY-MM.zip; raw folder removed.
Persistent shelf: ledger rows already close at window; pipeline prunes CLOSED items older than raw_days.
Usage: python3 janitor.py [--data DIR] [--dry-run]
"""
import argparse, json, os, shutil, zipfile
from datetime import date, datetime, timedelta
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RET = yaml.safe_load(open(os.path.join(ROOT, "charter", "parameters.yaml")))["retention"]

def rollup(day_dir):
    s = {"date": os.path.basename(day_dir), "files": {}}
    for root, _, files in os.walk(day_dir):
        for f in files:
            p = os.path.join(root, f)
            entry = {"bytes": os.path.getsize(p)}
            if f.endswith(".json"):
                try:
                    d = json.load(open(p))
                    entry["keys"] = list(d)[:12] if isinstance(d, dict) else f"list[{len(d)}]"
                    for k in ("count", "summary", "approval", "metrics"):
                        if isinstance(d, dict) and k in d: entry[k] = d[k]
                except Exception: pass
            s["files"][os.path.relpath(p, day_dir)] = entry
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data")); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cutoff = date.today() - timedelta(days=int(RET["raw_days"]))
    for shelf in ("sod", "intraday", "eod"):
        base = os.path.join(a.data, shelf)
        if not os.path.isdir(base): continue
        for day in sorted(os.listdir(base)):
            try: d = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError: continue
            if d >= cutoff: continue
            day_dir = os.path.join(base, day)
            if a.dry_run: print(f"would archive {day_dir}"); continue
            rdir = os.path.join(a.data, "persistent", "rollups", shelf); os.makedirs(rdir, exist_ok=True)
            json.dump(rollup(day_dir), open(os.path.join(rdir, f"{day}.json"), "w"), indent=1)
            adir = os.path.join(a.data, "archive"); os.makedirs(adir, exist_ok=True)
            zpath = os.path.join(adir, f"{shelf}-{day[:7]}.zip")
            with zipfile.ZipFile(zpath, "a", zipfile.ZIP_DEFLATED) as z:
                for root, _, files in os.walk(day_dir):
                    for f in files:
                        p = os.path.join(root, f); z.write(p, os.path.relpath(p, base))
            shutil.rmtree(day_dir)
            print(f"archived {shelf}/{day} -> {os.path.basename(zpath)} (+rollup kept)")

if __name__ == "__main__":
    main()
