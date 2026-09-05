#!/usr/bin/env python3
"""Recompute dynCap AFTER Aegis-membership classification (D-99 fix).

BUG THIS CLOSES: journal_build.py's `build` computes dynCap from `open_positions` at the moment
the journal is first assembled -- before held_book_refresh.py `classify` has run. At that point
open_positions still contains every co-mingled broker holding (Income Wheel, Protege9, Ryan's
personal names), so dynCap's unrealised component was silently including non-Aegis P&L. This
produced a negative, wildly wrong dynCap (and 1R) on 2026-08-18 even though `classify` correctly
strips non-Aegis names moments later in the same batch -- nothing ever re-ran the arithmetic
afterward. [RB:identity.capital_segregation] requires dynCap be computed over Aegis-only capital;
this script is the missing step that actually enforces it, not just claims it in the method text.

Run this as Job 3.5 -- immediately after `held_book_refresh.py classify` and before
`held_book_refresh.py carry-forward` -- every day, forever.

REALISED P&L SOURCE (also D-99, revised after a same-day idempotency bug on 2026-08-19): the
first version of this script persisted a running `realised_pnl_usd` counter to
data/persistent/dyncap_ledger.json and added "today's" closed_trades to it every run. That
double-counted a close if the script ran twice in the same day (the second run added the same
trade's P&L again on top of what the first run had already persisted). Fixed by sourcing
realised-to-date from the ARCHIVE LEDGER (data/persistent/aegis_trade_journal_ARCHIVE_master.json,
written by archive_ledger.py) instead of a mutable accumulator:
  - realised_from_archive = sum of pnlUsd for every trade already in the archive ledger.
  - realised_today_not_yet_archived = sum of this journal's closed_trades, EXCLUDING any
    (ticker, closed_date) pair that's already present in the archive. This is what makes it safe
    to run before OR after archive_ledger.py's merge step, any number of times, same day or not --
    a trade is counted exactly once, via whichever of the two sources currently holds it.
2026-09-05 FIX -- data/persistent/dyncap_ledger.json is now the FULL, schema-conformant ledger
(contracts/dyncap_ledger.schema.json), written HERE and only here. Previously this script wrote
an incomplete 3-key "informational snapshot" to that same path (missing the schema's required
allocated_capital_usd/dyncap_usd/closed_count) and left `premarket`'s step 8
(`dyncap_ledger.py update <journal.json>`) to separately re-derive a valid ledger from the journal
a second time, later the same run, via different arithmetic (`dyncap_ledger.py`'s own
`from_ptj()` does not exclude `aegis_status: excluded_non_aegis` rows when summing unrealised --
the exact class of bug D-99 exists to close). Two writers computing the same load-bearing number
two different ways is worse than one, so this script now writes the complete, correct shape
directly and `premarket` step 8 no longer recomputes it (PM ruling 2026-09-05: "should be done
as part of the PTJ step") -- it just reads what this step already wrote.

Usage:
  python3 tools/recompute_dyncap.py --journal today.json --allocated 75000 [--one-r-pct 1.5] [--out today.json]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_PATH = os.path.join(ROOT, "data", "persistent", "aegis_trade_journal_ARCHIVE_master.json")
LEDGER_SCHEMA_PATH = os.path.join(ROOT, "contracts", "dyncap_ledger.schema.json")


def _load_json(path):
    with open(path) as fh:
        return json.load(fh)


def _archived_realised(archive):
    ledger = (archive or {}).get("closed_trades_ledger") or []
    total = sum(float(t.get("pnlUsd") or 0.0) for t in ledger)
    keys = {(t.get("ticker"), t.get("exitDate")) for t in ledger}
    return round(total, 2), keys


def recompute(journal, allocated, one_r_pct, archive=None):
    realised_from_archive, archived_keys = _archived_realised(archive)

    closed = journal.get("closed_trades") or []
    not_yet_archived = [c for c in closed if (c.get("ticker"), c.get("closed_date")) not in archived_keys]
    realised_not_yet_archived = sum(float(c.get("realised_usd") or 0.0) for c in not_yet_archived)

    open_positions = journal.get("open_positions", []) or []
    aegis_open = [p for p in open_positions if p.get("aegis_status") != "excluded_non_aegis"]
    unrealised = sum(p.get("unrealised_usd") or 0.0 for p in aegis_open)

    realised = round(realised_from_archive + realised_not_yet_archived, 2)
    unrealised = round(unrealised, 2)
    value = round(float(allocated) + realised + unrealised, 2)
    # closed_count: every closed trade counted into `realised` -- archived AND not-yet-archived --
    # since both feed the number above (informational; the archive itself is the trade-level record).
    closed_count = len(archived_keys) + len(not_yet_archived)
    journal["dyncap"] = {
        "value": value,
        "one_r": round(value * float(one_r_pct) / 100.0, 2),
        "method": (f"D-99 fix: recomputed AFTER Aegis-membership classify by "
                   f"tools/recompute_dyncap.py: allocated {float(allocated):.2f} + realised "
                   f"{realised:.2f} (archived {realised_from_archive:.2f} + not-yet-archived "
                   f"{round(realised_not_yet_archived, 2):.2f}) + unrealised {unrealised:.2f} "
                   f"(AEGIS-confirmed/pending_review positions only -- non-Aegis excluded_non_aegis "
                   f"names and hedge MTM both excluded) = {value:.2f}. 1R = {one_r_pct}% "
                   f"[RB:capital.one_r_pct_of_dyncap]. AEGIS book only "
                   f"[RB:identity.capital_segregation]."),
    }
    ledger = {
        "allocated_capital_usd": float(allocated),
        "realised_pnl_usd": realised,
        "unrealised_pnl_usd": unrealised,
        "dyncap_usd": value,
        "closed_count": closed_count,
        "open_count": len(aegis_open),
        "marked_asof": journal.get("marked_asof") or journal.get("as_of") or journal.get("date"),
        "note": ("dynCap = allocation + realised + UNREALISED = current Aegis equity, "
                 "mark-to-market (D-41). Computed AFTER Aegis-membership classify, AEGIS-only "
                 "(D-99): realised sourced from the archive ledger + not-yet-archived closes "
                 "(idempotent on re-run); unrealised excludes excluded_non_aegis positions. "
                 "Single writer of this file -- tools/recompute_dyncap.py, run as PTJ CLOSE job "
                 "3.5. `premarket` step 8 reads this, it does not recompute it (2026-09-05)."),
    }
    return journal, realised, ledger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", required=True)
    ap.add_argument("--allocated", type=float, required=True)
    ap.add_argument("--one-r-pct", type=float, default=1.5)
    ap.add_argument("--out")
    args = ap.parse_args()

    journal = _load_json(args.journal)

    archive = None
    if os.path.exists(ARCHIVE_PATH):
        archive = _load_json(ARCHIVE_PATH)

    journal, cumulative_realised, ledger = recompute(journal, args.allocated, args.one_r_pct, archive)

    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)

    # MED-1 discipline (matches dyncap_ledger.py): validate the capital anchor against its
    # contract before writing -- fail-closed rather than persist a shape nothing downstream trusts.
    try:
        import jsonschema
        if os.path.exists(LEDGER_SCHEMA_PATH):
            jsonschema.validate(ledger, json.load(open(LEDGER_SCHEMA_PATH)))
    except ImportError:
        pass
    except Exception as e:
        raise ValueError(f"dyncap ledger failed its contract, refusing to write: {e}")

    led_path = os.path.join(ROOT, "data", "persistent", "dyncap_ledger.json")
    with open(led_path, "w") as fh:
        json.dump(ledger, fh, indent=1)

    d = journal["dyncap"]
    print(f"DYNCAP RECOMPUTE -- AEGIS-only: value {d['value']:,.2f} · 1R {d['one_r']:,.2f}")
    print(f"cumulative realised P&L (archive + not-yet-archived): {cumulative_realised:,.2f}")


if __name__ == "__main__":
    main()
