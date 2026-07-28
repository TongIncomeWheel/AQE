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
  3. Also in premarket, right after the fresh floor is computed: `stop-update` writes it into
     `stop_reference` and recomputes `stop_match` against the broker's live stop. A MISMATCH
     here is expected (the broker order usually hasn't been staged yet) — it is flagged, never
     blocking. `stop_live_broker` itself is execution truth and is never written here.
  4. Tomorrow's post-market carries THIS refreshed snapshot forward again (step 1), closing the
     loop — so the metrics post-market computes are always built from the most recent AQE data
     available, dated honestly, never faked to look same-day.

WRITE ALWAYS, FLAG NEVER BLOCKS: every operation here appends to the journal's `review_flags`
(ticker, type, detail, severity) whenever it finds something a person should look at — a name
that's never been refreshed, one absent from today's export, a stop mismatch. None of that ever
stops the write. This is the part of the "still write, but flag for PM attention" answer that
lives at the mechanical layer; the print-trade-journal skill is where the three orchestrators
(post-market, premarket, market-hours) each call in at their own moment.

Deterministic (law 4) — no model, no network. All three operations mutate `open_positions` (and
append to `review_flags`) only; every other journal key (dyncap, closed_trades, hedge, metrics,
broker_sync) passes through byte-identical.

Usage:
  python3 tools/held_book_refresh.py carry-forward --journal today.json --prior yesterday.json [--out today.json]
  python3 tools/held_book_refresh.py refresh --journal today.json --export aqe_daily_export.json [--out today.json]
  python3 tools/held_book_refresh.py stop-update --journal today.json --stops new_stops.json [--out today.json]
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


def _flag(journal, ticker, kind, detail, severity="medium"):
    """Append one named, actionable exception to the journal's review_flags — this is the
    'still write, but flag for PM attention' rule: nothing in this file ever blocks a write on a
    data-quality problem, it records what's wrong, on which ticker, and lets the write proceed.
    Idempotent per (ticker, kind) WITHIN this file: if an operation is re-run in the same session
    (a retry, or called twice by mistake), the existing flag's detail is refreshed in place rather
    than duplicated — review_flags reflects current conditions, not a growing log."""
    flags = journal.setdefault("review_flags", [])
    for f in flags:
        if f.get("ticker") == ticker and f.get("type") == kind:
            f["detail"], f["severity"], f["since"] = detail, severity, journal.get("date")
            return
    flags.append({"ticker": ticker, "type": kind, "detail": detail, "severity": severity,
                  "since": journal.get("date")})


def _unflag(journal, ticker, kind):
    """Remove a (ticker, kind) flag if the condition that raised it no longer holds — a
    review_flags entry reflects CURRENT state, not a history of everything that was ever wrong."""
    flags = journal.get("review_flags")
    if not flags:
        return
    journal["review_flags"] = [f for f in flags
                               if not (f.get("ticker") == ticker and f.get("type") == kind)]


def carry_forward(journal, prior_journal):
    """Pull each held ticker's most recent aqe_snapshot forward from `prior_journal` into
    `journal`, IN PLACE. The original aqe_snapshot_as_of travels with it unchanged — carrying a
    snapshot forward never pretends it is fresher than it is. A ticker with NO prior data
    anywhere is flagged `no_aqe_data` (high severity — this position is being risk-managed
    blind) rather than silently left null. Returns a report."""
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
            _flag(journal, t, "no_aqe_data",
                  "held position has never been refreshed with AQE data — excluded from "
                  "leverage/beta/sector/VaR until the next premarket refresh finds it",
                  severity="high")
    return {"carried": carried, "no_prior_data": no_prior_data, "already_had": already_had}


def refresh_from_export(journal, export):
    """Merge fresh AQE fields into each held ticker's aqe_snapshot from today's `export`, IN
    PLACE. A ticker not present in today's export keeps its existing (now-stale) snapshot rather
    than being blanked — a missing export row is never treated as 'no longer relevant', but it
    is flagged `not_in_todays_export` (low severity — informational) so it is visible, not
    silent. Returns a report."""
    export_date = export.get("date")
    export_by_ticker = _index_by_ticker(export.get("daily_list"))
    refreshed, not_found_in_export = [], []
    for pos in journal.get("open_positions", []) or []:
        t = pos.get("ticker")
        rec = export_by_ticker.get(t)
        if rec is None:
            not_found_in_export.append(t)
            _flag(journal, t, "not_in_todays_export",
                  "held ticker absent from today's AQE export — keeping its existing "
                  "(now-stale) aqe_snapshot rather than blanking it",
                  severity="low")
            continue
        snap = {k: rec.get(k) for k in AQE_SNAPSHOT_FIELDS if k in rec}
        pos["aqe_snapshot"] = snap
        pos["aqe_snapshot_as_of"] = export_date
        refreshed.append(t)
    return {"refreshed": refreshed, "not_found_in_export": not_found_in_export,
            "export_date": export_date}


def stop_update(journal, new_stops):
    """Write trailing_stop.py's freshly computed floor into `stop_reference` for each ticker in
    `new_stops` ({ticker: new_stop_value}), IN PLACE, then recompute `stop_match` against
    whatever `stop_live_broker` currently says. A MISMATCH right after this is EXPECTED — it
    means the broker order hasn't been staged yet, not that anything is broken — so it is
    flagged, never blocking. Only `stop_reference` and `stop_match` are touched; `stop_live_broker`
    is execution truth and is never written here, only compared against. Returns a report."""
    updated, mismatched, missing_broker_stop = [], [], []
    for pos in journal.get("open_positions", []) or []:
        t = pos.get("ticker")
        if t not in new_stops:
            continue
        pos["stop_reference"] = new_stops[t]
        live = pos.get("stop_live_broker")
        if live is None:
            pos["stop_match"] = "MISSING"
            missing_broker_stop.append(t)
            _flag(journal, t, "stop_missing",
                  "no live broker stop on record for this held position",
                  severity="medium")
        elif round(float(live), 4) == round(float(new_stops[t]), 4):
            pos["stop_match"] = "MATCH"
            _unflag(journal, t, "stop_mismatch")
        else:
            pos["stop_match"] = "MISMATCH"
            mismatched.append(t)
            _flag(journal, t, "stop_mismatch",
                  "kernel's new stop %.4g vs broker's live stop %.4g — order likely not "
                  "staged yet, not necessarily an error" % (new_stops[t], live),
                  severity="high")
        updated.append(t)
    return {"updated": updated, "mismatched": mismatched,
            "missing_broker_stop": missing_broker_stop}


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


def cmd_stop_update(args):
    journal = _load(args.journal)
    new_stops = _load(args.stops)   # {ticker: new_stop_value}
    report = stop_update(journal, new_stops)
    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    print(json.dumps({"op": "stop-update", "out": out, **report}, indent=1))


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

    # review_flags: BBB never got a prior snapshot (no_aqe_data, high) and was absent from the
    # export the first time it was checked... actually BBB WAS found on the second export check
    # above? no -- BBB was never in `export`, so it should carry a not_in_todays_export flag too.
    kinds = {f["type"] for f in today.get("review_flags", [])}
    assert "no_aqe_data" in kinds, today.get("review_flags")
    assert "not_in_todays_export" in kinds, today.get("review_flags")

    # stop-update: write the new floor, recompute stop_match against the broker's live value.
    today["open_positions"][0]["stop_live_broker"] = 50.0   # broker hasn't caught up yet
    today["open_positions"][1]["stop_live_broker"] = 19.0
    r3 = stop_update(today, {"AAA": 52.0, "BBB": 19.0})
    assert today["open_positions"][0]["stop_reference"] == 52.0
    assert today["open_positions"][0]["stop_match"] == "MISMATCH", today["open_positions"][0]
    assert today["open_positions"][1]["stop_match"] == "MATCH", today["open_positions"][1]
    assert r3["mismatched"] == ["AAA"], r3
    assert today["open_positions"][0]["stop_live_broker"] == 50.0, \
        "stop-update must NEVER write stop_live_broker — that is execution truth"
    kinds2 = {f["type"] for f in today.get("review_flags", [])}
    assert "stop_mismatch" in kinds2, today.get("review_flags")

    # a position with no live broker stop at all -> MISSING, flagged, never fabricated
    today["open_positions"].append({"ticker": "DDD", "qty": 10, "entry": 5.0, "stop_reference": 4.0})
    r4 = stop_update(today, {"DDD": 4.5})
    assert today["open_positions"][-1]["stop_match"] == "MISSING"
    assert r4["missing_broker_stop"] == ["DDD"], r4

    # idempotent flags: re-running stop-update on AAA (still mismatched) must REFRESH the
    # existing flag in place, not append a second one for the same (ticker, kind).
    before = len(today["review_flags"])
    stop_update(today, {"AAA": 53.0})
    after = len(today["review_flags"])
    assert after == before, "re-running the same check must not duplicate an existing flag: %d -> %d" % (before, after)
    assert [f for f in today["review_flags"] if f["ticker"] == "AAA" and f["type"] == "stop_mismatch"][0]["detail"].find("53") != -1

    # once resolved (broker catches up), the flag must be REMOVED, not left stale
    today["open_positions"][0]["stop_live_broker"] = 53.0
    stop_update(today, {"AAA": 53.0})
    assert today["open_positions"][0]["stop_match"] == "MATCH"
    assert not [f for f in today["review_flags"] if f["ticker"] == "AAA" and f["type"] == "stop_mismatch"],         "a resolved mismatch must be cleared from review_flags, not left stale"

    print("held_book_refresh selftest OK — carry-forward preserves the original as_of date "
          "(never fakes freshness) and flags no_aqe_data; refresh stamps today's date, flags a "
          "name absent from today's export instead of blanking it; stop-update writes the new "
          "floor, recomputes stop_match, never touches stop_live_broker, and flags MISMATCH/"
          "MISSING without blocking the write; execution-truth fields are untouched throughout.")


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
    su = sub.add_parser("stop-update")
    su.add_argument("--journal", required=True)
    su.add_argument("--stops", required=True, help="JSON file: {ticker: new_stop_value}")
    su.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
    elif a.cmd == "carry-forward":
        cmd_carry_forward(a)
    elif a.cmd == "refresh":
        cmd_refresh(a)
    elif a.cmd == "stop-update":
        cmd_stop_update(a)


if __name__ == "__main__":
    main()
