#!/usr/bin/env python3
"""
AQE Daily Pipeline — single entry point.
Replaces all run_*.bat files.

Usage:
    python run_daily.py              # full pipeline (pull + score + export)
    python run_daily.py --no-pull    # skip data pull, use cached panel
    python run_daily.py --date 2026-07-23  # specific date
"""
import sys
import argparse
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.daily_orchestrator import run_daily

def main():
    ap = argparse.ArgumentParser(description="AQE Daily Pipeline")
    ap.add_argument("--no-pull", action="store_true", help="Skip incremental data pull")
    ap.add_argument("--date", type=str, default=None, help="Run date (YYYY-MM-DD)")
    args = ap.parse_args()

    run_date = date.fromisoformat(args.date) if args.date else None
    result = run_daily(run_date=run_date, skip_pull=args.no_pull)

    if result:
        print(f"\n[OK] Pipeline complete. Export: {result.get('export_path', 'unknown')}")
    else:
        print("\n[FAIL] Pipeline returned no result")
        sys.exit(1)

if __name__ == "__main__":
    main()
