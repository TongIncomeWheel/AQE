#!/usr/bin/env python3
"""Held-book AQE refresh (D-85) — the loop between post-market and premarket for held positions.

WHY THIS EXISTS (PM: "the portfolio check figures should be inside the journal... it should
hold all the data on position level from AQE on the held book, this ensures that the next
write, once AQE is run in premarket, the procedure also updates the file with new levels
(not overwrite)").

Each open_position in the journal now carries an `aqe_snapshot` (AQE's market-data view of that
name — sector, beta, ann_vol_pct, sc_momentum, structure, bracket, elder, mp_accel_state) and an
`aqe_snapshot_as_of` (the date that snapshot was actually refreshed — always shown, never hidden,
because it is very often NOT today: AQE only publishes during premarket, and post-market runs
BEFORE premarket the same day, so post-market's own run always sees data at least one refresh
cycle old).

THE LOOP, concretely:
  1. Post-market (04:00-10:00 SGT) writes today's journal from broker fills — execution truth
     only (qty, entry, stop_reference, ...). It has NO fresh AQE data available yet. Before it
     computes anything (portfolio_metrics.py), it runs `carry-forward` here to pull each held
     ticker's most recent aqe_snapshot from the PRIOR journal that has one. Honest and dated —
     if a name has never been refreshed, it stays null and portfolio_metrics.py excludes it
     rather than guessing.
  2. Premarket (10:00 SGT, same day) pulls the fresh AQE export (step 3) and, once it has it,
     runs `refresh` here on the SAME journal post-market wrote hours earlier — this is the
     "next write... updates the file with new levels, not overwrite" the PM asked for: it is a
     targeted per-ticker MERGE into `aqe_snapshot` + `aqe_snapshot_as_of`, never touching the
     execution-truth fields post-market already committed (qty, entry, entry_date, stop_reference,
     stop_live_broker, stop_match, tp1-3, trigger, broker, unrealised_usd, mark_price).
  3. Tomorrow's post-market carries THIS refreshed snapshot forward again (step 1), closing the
     loop — so the metrics post-market computes are always built from the most recent AQE data
     available, dated honestly, never faked to look same-day.

Deterministic (law 4) — no model, no network. Both operations mutate `open_positions` only;
every other journal key (dyncap, closed_trades, hedge, metrics, broker_sync) passes through
byte-identical.

Usage:
  python3 tools/held_book_refresh.py carry-forward --journal today.json --prior yesterday.json [--out today.json]
  python3 tools/held_book_refresh.py refresh --journal today.json --export aqe_daily_export.json [--out today.json]
  python3 tools/held_book_refresh.py selftest
"""
import json
import argparse
import sys

# The AQE fields captured per position. Deliberately a fixed, named set (not a blind copy of the
# whole export record) so the journal stays the "trimmed, consumed field set" discipline the rest
# of the kernel already follows (D-81) — not another 97-field byte-copy.
AQE_SNAPSHOT_FIELDS = [
    "sector", "beta", "ann_vol_pct", "sc_momentum", "structure", "elder", "elder_5d",
    "mp_accel_state", "rs_leadership", "flow", "choch_state",
    "bracket",   # the structural stop/targets trailing_stop.py needs (D-33/D-85) — without this
                 # field the loop refreshes risk metrics but not the number that actually moves stops
]


def _index_by_ticker(rows):
    return {r.get("ticker"): r for r in (rows or []) if r.get("ticker")}


def carry_forward(journal, prior_journal):
    """Pull each held ticker's most recent aqe_snapshot forward from `prior_journal` into
    `journal`, IN PLACE. The original aqe_snapshot_as_of travels with it unchanged — carrying a
    snapshot forward never pretends it is fresher than it is. Returns a report."""
    prior_by_ticker = _index_by_ticker((prior_journal or {}).get("open_positions"))
    carried, no_prior_data, already_had = [], [], []
    for pos in journal.get("open_positions", []) or []:
        t = pos.get("ticker")
        if pos.get("aqe_snapshot"):
            already_had.append(t)
            continue
        prior = prior_by_ticker.get(t)
        if prior and prior.get("aqe_snapshot"):
            pos["aqe_snapshot"] = prior["aqe_snapshot"]
            pos["aqe_snapshot_as_of"] = prior.get("aqe_snapshot_as_of")
            carried.append(t)
        else:
            pos.setdefault("aqe_snapshot", None)
            pos.setdefault("aqe_snapshot_as_of", None)
            no_prior_data.append(t)
    return {"carried": carried, "no_prior_data": no_prior_data, "already_had": already_had}


def refresh_from_export(journal, export):
    """Merge fresh AQE fields into each held ticker's aqe_snapshot from today's `export`, IN
    PLACE. A ticker not present in today's export keeps its existing (now-stale) snapshot rather
    than being blanked — a missing export row is never treated as 'no longer relevant'. Returns
    a report."""
    export_date = export.get("date")
    export_by_ticker = _index_by_ticker(export.get("daily_list"))
    refreshed, not_found_in_export = [], []
    for pos in journal.get("open_positions", []) or []:
        t = pos.get("ticker")
        rec = export_by_ticker.get(t)
        if rec is None:
            not_found_in_export.append(t)
            continue
        snap = {k: rec.get(k) for k in AQE_SNAPSHOT_FIELDS if k in rec}
        pos["aqe_snapshot"] = snap
        pos["aqe_snapshot_as_of"] = export_date
        refreshed.append(t)
    return {"refreshed": refreshed, "not_found_in_export": not_found_in_export,
            "export_date": export_date}


# --------------------------------------------------------------------------- CLI
def _load(path):
    with open(path) as fh:
        return json.load(fh)


def cmd_carry_forward(args):
    journal = _load(args.journal)
    prior = _load(args.prior) if args.prior else {}
    report = carry_forward(journal, prior)
    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    print(json.dumps({"op": "carry-forward", "out": out, **report}, indent=1))


def cmd_refresh(args):
    journal = _load(args.journal)
    export = _load(args.export)
    report = refresh_from_export(journal, export)
    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    print(json.dumps({"op": "refresh", "out": out, **report}, indent=1))


def selftest(_args=None):
    prior = {"open_positions": [
        {"ticker": "AAA", "qty": 100, "entry": 50.0,
         "aqe_snapshot": {"sector": "Tech", "beta": 1.2}, "aqe_snapshot_as_of": "2026-07-20"},
    ]}
    today = {"date": "2026-07-28", "dyncap": {"value": 65000, "one_r": 650},
             "open_positions": [
                 {"ticker": "AAA", "qty": 100, "entry": 50.0, "stop_reference": 47.0},
                 {"ticker": "BBB", "qty": 50, "entry": 20.0, "stop_reference": 18.0},
             ], "closed_trades": [], "metrics": {}}

    r1 = carry_forward(today, prior)
    assert r1["carried"] == ["AAA"], r1
    assert r1["no_prior_data"] == ["BBB"], r1
    assert today["open_positions"][0]["aqe_snapshot"] == {"sector": "Tech", "beta": 1.2}
    assert today["open_positions"][0]["aqe_snapshot_as_of"] == "2026-07-20", \
        "carry-forward must preserve the ORIGINAL as_of, never stamp today's date"
    assert today["open_positions"][1]["aqe_snapshot"] is None
    # execution-truth fields untouched
    assert today["open_positions"][0]["entry"] == 50.0 and today["open_positions"][0]["qty"] == 100

    export = {"date": "2026-07-28", "daily_list": [
        {"ticker": "AAA", "sector": "Tech", "beta": 1.35, "ann_vol_pct": 40.0, "sc_momentum": 82.0,
         "extra_field_not_in_allowlist": "should not leak"},
    ]}
    r2 = refresh_from_export(today, export)
    assert r2["refreshed"] == ["AAA"], r2
    assert r2["not_found_in_export"] == ["BBB"], r2
    snap = today["open_positions"][0]["aqe_snapshot"]
    assert snap["beta"] == 1.35 and snap["sc_momentum"] == 82.0, snap
    assert "extra_field_not_in_allowlist" not in snap, "only the named AQE_SNAPSHOT_FIELDS travel in"
    assert today["open_positions"][0]["aqe_snapshot_as_of"] == "2026-07-28", \
        "refresh MUST stamp today's export date, not carry the old one forward"
    # BBB's snapshot is untouched (still null — not found in export, never blanked-to-something-else)
    assert today["open_positions"][1]["aqe_snapshot"] is None
    # execution-truth fields still untouched after refresh too
    assert today["open_positions"][0]["stop_reference"] == 47.0
    assert today["dyncap"]["value"] == 65000, "refresh must not touch anything outside open_positions"

    print("held_book_refresh selftest OK — carry-forward preserves the original as_of date "
          "(never fakes freshness), refresh stamps today's date and only touches matched "
          "tickers' aqe_snapshot, a name missing from the export keeps its existing snapshot "
          "instead of being blanked, execution-truth fields are untouched by both operations.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Held-book AQE snapshot refresh (D-85, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("carry-forward")
    c.add_argument("--journal", required=True)
    c.add_argument("--prior")
    c.add_argument("--out")
    r = sub.add_parser("refresh")
    r.add_argument("--journal", required=True)
    r.add_argument("--export", required=True)
    r.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
    elif a.cmd == "carry-forward":
        cmd_carry_forward(a)
    elif a.cmd == "refresh":
        cmd_refresh(a)


if __name__ == "__main__":
    main()
