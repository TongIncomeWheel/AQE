#!/usr/bin/env python3
"""Convert a journal's `closed_trades` (journal_build.py's schema) into the flat shape
archive_ledger.py's `merge` expects (D-102 fix — this conversion never existed; archive_ledger.py
was never actually reachable from the journal because the two tools speak different field names:
journal_build.py writes {ticker, qty, entry, exit, realised_usd, closed_date, broker, partial},
archive_ledger.py wants {ticker, type, exitDate, pnlUsd, winLoss, sector, broker, rRealised}.

Usage:
  python3 tools/journal_closed_to_archive_format.py --journal today.json --out closed_for_archive.json
Writes [] (empty list) if there are no closed_trades — archive_ledger.py's merge() already
treats an empty list as a legitimate no-op, so this never fabricates a merge.
"""
import argparse
import json


def convert(closed_trades):
    out = []
    for t in closed_trades or []:
        ticker = t.get("ticker")
        exit_date = t.get("closed_date")
        pnl = t.get("realised_usd")
        out.append({
            "id": f"{ticker}-{exit_date}",
            "ticker": ticker,
            "type": "STK",
            "exitDate": exit_date,
            "pnlUsd": round(float(pnl), 2) if pnl is not None else 0.0,
            "winLoss": "W" if (pnl or 0) > 0 else "L",
            "sector": "TBD",
            "broker": t.get("broker", ""),
            "rRealised": None,
            "note": t.get("source", ""),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    journal = json.load(open(args.journal))
    converted = convert(journal.get("closed_trades"))

    with open(args.out, "w") as fh:
        json.dump(converted, fh, indent=1)

    print(f"CONVERTED {len(converted)} closed trade(s) -> {args.out}")


if __name__ == "__main__":
    main()
