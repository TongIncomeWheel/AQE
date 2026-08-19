#!/usr/bin/env python3
"""Reconcile vanished equity positions against the saved fills payload (D-100 fix).

BUG THIS CLOSES: on 2026-08-18, Tiger's get_filled_orders tool silently omitted a STOP-TRIGGERED
equity close (AVAV, 100sh @ 175.4819, stopped out 21:30:12 SGT) even though the fill sits in
Tiger's own per-symbol transaction ledger (get_transactions) for the same window. journal_build.py
only ever looks at tiger_filled_orders.json (Step 1's "day's fills list") to detect closes
(_closed_trades in journal_build.py matches fills against the prior journal's open_positions) —
so AVAV's position simply disappeared from open_positions between the 08-18 and 08-19 journals
with NOTHING recorded: no closed_trades entry, no realised P&L, no dynCap impact. The loss was
real and booked at the broker; it was invisible in the book of record.

Root cause is upstream (the MCP tool), not fixable here. What IS fixable here: never let a
position vanish silently again. This script is a HARD GATE that runs in Step 1, right after the
broker pull is saved and BEFORE the batch (journal_build.py) runs:

  1. Diffs prior_journal's open_positions equity tickers against today's tiger_stock_positions.json.
  2. For every ticker that HELD yesterday and is ABSENT today, checks whether tiger_filled_orders.json
     contains a closing fill for it.
  3. Any vanished ticker with NO matching fill in the saved payload is a HALT (exit 2) — the run
     must not proceed with a broker pull that is silently missing a real, capital-affecting event.
     The operator is told exactly what to do: pull get_transactions(symbol=TICKER) live, verify
     the close, and manually append the fill to tiger_filled_orders.json before re-running.

Usage:
  python3 tools/reconcile_vanished_positions.py --prior PRIOR_JOURNAL --stock-positions PULLED_STOCK_JSON --filled-orders PULLED_FILLED_JSON
Exit 0 = clean (nothing vanished, or everything vanished has a matching fill).
Exit 2 = HALT — unexplained vanished position(s), listed on stdout.
"""
import argparse
import json
import sys


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def reconcile(prior_journal, stock_positions_payload, filled_orders_payload):
    prior_tickers = {p.get("ticker") for p in (prior_journal.get("open_positions") or [])
                     if p.get("ticker")}
    today_tickers = {r.get("symbol") for r in (stock_positions_payload.get("result") or [])
                     if r.get("symbol")}
    vanished = prior_tickers - today_tickers

    fills_by_ticker = set()
    for f in (filled_orders_payload.get("result") or []):
        if f.get("sec_type") == "STK" and f.get("symbol"):
            fills_by_ticker.add(f["symbol"])

    unexplained = sorted(t for t in vanished if t not in fills_by_ticker)
    explained = sorted(t for t in vanished if t in fills_by_ticker)
    return {"vanished": sorted(vanished), "explained_by_fill": explained,
            "unexplained": unexplained}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", required=True)
    ap.add_argument("--stock-positions", required=True)
    ap.add_argument("--filled-orders", required=True)
    args = ap.parse_args()

    prior = _load(args.prior)
    stock = _load(args.stock_positions)
    filled = _load(args.filled_orders)

    report = reconcile(prior, stock, filled)
    print(json.dumps(report, indent=1))

    if report["unexplained"]:
        print(f"\nHALT (D-100): {len(report['unexplained'])} position(s) vanished from the "
              f"broker book with NO matching fill in tiger_filled_orders.json: "
              f"{', '.join(report['unexplained'])}", file=sys.stderr)
        print("Tiger's get_filled_orders is known to silently drop stop-triggered equity closes "
              "(D-100, confirmed on AVAV 2026-08-18). Before proceeding: call "
              "get_transactions(symbol=TICKER, days>=N since last known held date) for each name "
              "above, confirm the close, and manually append the fill to "
              "tiger_filled_orders.json. Do NOT let journal_build.py run against an unexplained "
              "vanish — it will silently produce a journal with the position simply gone and no "
              "realised P&L booked.", file=sys.stderr)
        sys.exit(2)

    print("\nRECONCILE OK — no unexplained vanished positions.")
    sys.exit(0)


if __name__ == "__main__":
    main()
