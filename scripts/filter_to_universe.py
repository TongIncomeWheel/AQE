#!/usr/bin/env python3
"""filter_to_universe.py -- an EMERGENCY filter for the run-150 leak (2026-11-18), until a clean re-run replaces the export.

Run 150 scored Valen's context-only baskets and group ETFs, so the universe rows and the export's daily_list / lens_ranking carry names that are NOT in data/universe.txt. This keeps only names in the
screened universe (plus the held book, always) and writes FILTERED COPIES; it never edits the inputs. It filters the row lists only: the export's derived top-level counts and lists (summary, unr_summary,
the longlist / Elder name lists) were computed WITH the leaked rows and are NOT recomputed here, so the printed report says so. The proper repair is a re-run after src/valen/baskets.context_only() is merged.

    python scripts/filter_to_universe.py --export aqe_daily_export.json --universe-rows aqe_universe_rows.json --universe data/universe.txt [--out-dir .]
"""
import argparse
import json
import os
import sys


def read_universe(path):
    return {ln.strip() for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")}


def filter_rows(rows, universe, held=()):
    keep = [r for r in rows if r.get("ticker") in universe or r.get("ticker") in held]
    return keep, [r.get("ticker") for r in rows if r.get("ticker") not in universe and r.get("ticker") not in held]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", required=True)
    ap.add_argument("--universe-rows", required=True)
    ap.add_argument("--universe", required=True)
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args(argv)
    uni = read_universe(a.universe)
    ex = json.load(open(a.export, encoding="utf-8"))
    held = {h.get("ticker") for h in ex.get("held_positions") or []}
    ur = json.load(open(a.universe_rows, encoding="utf-8"))
    report = []
    ur["rows"], dropped = filter_rows(ur["rows"], uni, held)
    ur["count"] = len(ur["rows"])
    report.append(f"universe rows: kept {len(ur['rows'])}, dropped {len(dropped)}")
    ur["filtered_by"] = "scripts/filter_to_universe.py (run 150 leak); " + str(len(dropped)) + " non-universe rows removed"
    for key in ("daily_list", "lens_ranking"):
        if isinstance(ex.get(key), list):
            ex[key], d = filter_rows(ex[key], uni, held)
            report.append(f"{key}: kept {len(ex[key])}, dropped {len(d)}: {d[:40]}")
    ex["filtered_by"] = "scripts/filter_to_universe.py (run 150 leak): row lists only; summary / unr_summary / list-name counts NOT recomputed"
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(ur, open(os.path.join(a.out_dir, "aqe_universe_rows.filtered.json"), "w", encoding="utf-8"), indent=1)
    json.dump(ex, open(os.path.join(a.out_dir, "aqe_daily_export.filtered.json"), "w", encoding="utf-8"), indent=1)
    print("\n".join(report))
    print("NOT recomputed: summary, unr_summary and every count derived from the leaked rows. Re-run the pipeline for a clean export.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
