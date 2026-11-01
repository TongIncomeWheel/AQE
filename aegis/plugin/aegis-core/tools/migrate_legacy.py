#!/usr/bin/env python3
"""ONE-TIME legacy sweep for the old Drive journal mess (run on the locally-synced Drive copy).
Keeps the newest valid journal as data/persistent/journal_seed.json; every other legacy file moves to
data/archive/legacy_<today>/ with a manifest.csv (old name, size, modified, new location). Deletes nothing.
Usage: python3 migrate_legacy.py --src ~/Drive/AegisJournals --data ./data [--dry-run]
"""
import argparse, csv, json, os, shutil
from datetime import date

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--data", default="data"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    files = []
    for root, _, fs in os.walk(a.src):
        for f in fs: files.append(os.path.join(root, f))
    journals = []
    for p in files:
        try:
            d = json.load(open(p))
            if isinstance(d, dict) and ("open_positions" in d or "positions" in d):
                journals.append((os.path.getmtime(p), p))
        except Exception: pass
    journals.sort(reverse=True)
    seed = journals[0][1] if journals else None
    dest = os.path.join(a.data, "archive", f"legacy_{date.today()}"); man = []
    if not a.dry_run: os.makedirs(dest, exist_ok=True)
    for p in files:
        if p == seed: continue
        new = os.path.join(dest, os.path.basename(p))
        i = 1
        while os.path.exists(new): new = os.path.join(dest, f"{i}_{os.path.basename(p)}"); i += 1
        man.append([os.path.relpath(p, a.src), os.path.getsize(p), new])
        if not a.dry_run: shutil.move(p, new)
    if not a.dry_run:
        if seed:
            os.makedirs(os.path.join(a.data, "persistent"), exist_ok=True)
            shutil.copy(seed, os.path.join(a.data, "persistent", "journal_seed.json"))
        with open(os.path.join(dest, "manifest.csv"), "w", newline="") as f:
            csv.writer(f).writerows([["original", "bytes", "archived_to"], *man])
    print(f"seed: {seed}\narchived: {len(man)} files -> {dest} {'(dry-run)' if a.dry_run else ''}")

if __name__ == "__main__":
    main()
