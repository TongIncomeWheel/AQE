#!/usr/bin/env python3
"""aqe_coverage.py — did AQE actually finish the job? (D-91)

WHAT THIS ANSWERS, IN ONE SENTENCE:
  the export parsed and validated, but is it COMPLETE, is it TODAY'S, and does it cover the
  names we actually own?

Schema validation says the shape is legal. `tripwires.py` says nothing ANOMALOUS is in it. Neither
asks the question this file asks, which is whether the run finished: every longlist name scored,
every score present rather than null, every held position covered, every sub-block computed on the
same date as the export that carries it. An export can be schema-valid, tripwire-clean, and still
be half a run — AQE writes its blocks in stages, and a stage that fell over leaves a file that
looks perfectly well-formed with a hole in the middle of it.

THIS IS NOT A SECOND TRIPWIRES AND MUST NOT BE MERGED INTO ONE.
  tripwires.py  = ANOMALY detection. Is a value wrong/impossible/frozen? (enum dead-states, the
                  bracket-valid band, glossary drift, journal-vs-feed held mismatch,
                  held_positions_status). It answers "is what is here believable?"
  aqe_coverage.py = COMPLETENESS + FRESHNESS. Is what should be here actually here, and is it
                  from today? It answers "is all of it here?"
  A file can pass either one and fail the other, in both directions. They are two different
  questions and collapsing them produces a check that does neither well.

DETERMINISTIC (law 4). No model, no network, no clock-dependent judgement beyond the `--today`
date the caller passes in — pass it explicitly so a re-run of an old export reproduces the same
verdict rather than drifting with the wall clock.

EXIT CODES (same three-way grammar as phase_gate.py, deliberately):
  0 = COMPLETE   — fit to build a plan on.
  1 = INCOMPLETE — gaps that time may fix (AQE still running, today's export not published yet).
                   Retry later. Do NOT spend the expensive half on it.
  2 = DEGRADED   — the export is here and finished, but has holes that will silently corrupt
                   downstream numbers if used as-is. Page; the PM decides whether to proceed.

Usage:
  python3 tools/aqe_coverage.py check --export output/aqe_daily_export.json \\
      [--journal data/journal/aegis_journal_YYYY-MM-DD.json] [--today YYYY-MM-DD] [--json]
  python3 tools/aqe_coverage.py selftest
"""
import json
import argparse
import datetime
import os
import sys

# --- Every daily_list row must carry these, non-null. The list is the CONSUMED set: a field is
# here because something downstream reads it and would produce a wrong number (not an error) if it
# were missing. It is deliberately NOT the full 97-field record — demanding fields nobody reads
# manufactures failures.
REQUIRED_ROW_FIELDS = [
    "ticker", "rank", "sc_momentum", "ptrs", "pipe_rank", "flow", "energy", "structure",
    "elder", "mp", "beta_30d", "atr_14d", "gics_sector", "entry", "bracket",
]

# --- Held rows are the book we actually own, so the bar is higher: these are the fields that make
# a held name risk-manageable. `subcomponents` is NOT here — it is null on 8 of 122 rows in a
# healthy export and nothing in the held path reads it.
#
# DELIBERATELY EXCLUDED, do not "fix" by adding: live_px, held_sl, unreal_usd, trade_date,
# exposure. Those are null on every held row of every export, and that is CORRECT, not a gap.
# They are execution truth, and the AQE export is not the Aegis book of record — the journal is
# (D-21, after the export's held_positions mismatched the live account on 18 Jul, BL-024). AQE
# publishes the same names' live price and exposure under `held_book.positions`, which is where
# the hedge math reads them. Demanding them here would fail every healthy export forever.
REQUIRED_HELD_FIELDS = [
    "ticker", "qty", "entry", "sc_momentum", "ptrs", "flow", "energy", "structure", "elder",
    "mp", "beta_30d", "atr_14d", "gics_sector", "bracket",
]

# --- Sub-blocks that carry their own date. AQE computes these in separate stages, and a stage
# that did not re-run today leaves yesterday's answer sitting inside today's file, where nothing
# about the file's own date reveals it. Maps block -> (path to its date field, severity).
DATED_SUBBLOCKS = [
    ("signal_radar", ("signal_radar", "scan_date"), "degraded"),
    ("intermarket", ("intermarket", "as_of"), "degraded"),
    ("held_book", ("held_book", "as_of"), "degraded"),
    ("sector_map", ("sector_map_version",), "warn"),
]

# --- The count keys in `summary` and the block each one claims to count. A summary that disagrees
# with the thing it summarises means one of the two was written by a stage that did not finish.
SUMMARY_RECONCILE = [
    ("daily_count", "daily_list", None),
    ("longlist_count", "daily_list", "on_longlist"),
    ("elder_count", "daily_list", "on_elder"),
    ("held_count", "held_positions", None),
]


def _get(d, path):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _date_only(v):
    """AQE stamps some fields 'YYYY-MM-DD' and others 'YYYY-MM-DD HH:MM:SS SGT'. Compare dates."""
    if not v:
        return None
    return str(v).strip().split(" ")[0].split("T")[0]


def _days_between(a, b):
    try:
        da = datetime.date.fromisoformat(_date_only(a))
        db = datetime.date.fromisoformat(_date_only(b))
    except (TypeError, ValueError):
        return None
    return (db - da).days


def check(export, journal=None, today=None):
    """Pure function (law 4). Returns a report dict. `today` is an ISO date string supplied by the
    caller — never read from the clock here, so an old export re-checked gives the same answer."""
    incomplete, degraded, warnings = [], [], []
    export_date = _date_only(export.get("date"))

    # ---------------------------------------------------------------- 1. is this today's run?
    # An export older than today is NOT degraded — it is a run that has not happened yet, which
    # time fixes. That distinction is the whole reason INCOMPLETE and DEGRADED are separate exit
    # codes: one says "come back later", the other says "wake the PM".
    if today:
        age = _days_between(export_date, today)
        if age is None:
            degraded.append("export carries no parseable `date` (%r) — cannot establish vintage"
                            % (export.get("date"),))
        elif age > 0:
            incomplete.append("export is dated %s, today is %s (%d day%s behind) — AQE has not "
                              "published today's run yet" % (export_date, today, age,
                                                             "" if age == 1 else "s"))
        elif age < 0:
            degraded.append("export is dated %s, AHEAD of today (%s) — a forward-dated export is "
                            "a clock or pipeline fault, not a fresh run" % (export_date, today))

    # ---------------------------------------------------------------- 2. the blocks exist at all
    dl = export.get("daily_list")
    hp = export.get("held_positions")
    if not dl:
        incomplete.append("daily_list is empty or absent — there is no scored universe to work from")
        dl = []
    if hp is None:
        degraded.append("held_positions block absent — the held book cannot be covered from this export")
        hp = []

    # ---------------------------------------------------------------- 3. summary reconciliation
    summary = export.get("summary") or {}
    for key, block, flag in SUMMARY_RECONCILE:
        claimed = summary.get(key)
        if claimed is None:
            warnings.append("summary.%s absent — nothing to reconcile against" % key)
            continue
        rows = export.get(block) or []
        actual = len(rows) if flag is None else sum(1 for r in rows if r.get(flag))
        if int(claimed) != int(actual):
            degraded.append("summary.%s says %s but %s%s holds %d — one of the two was written by "
                            "a stage that did not finish" % (key, claimed, block,
                                                             "[%s]" % flag if flag else "", actual))

    # ---------------------------------------------------------------- 4. per-row score coverage
    # Reported as a ROLL-UP, not one line per row. A 122-row export with a broken stage produces
    # 122 identical complaints, and a report nobody reads to the end is not a report.
    def _scan(rows, required, label):
        gaps, per_field = {}, {}
        for r in rows:
            t = r.get("ticker") or "<no ticker>"
            miss = [f for f in required
                    if f not in r or r.get(f) is None or r.get(f) == "TBD"]
            if miss:
                gaps[t] = miss
                for f in miss:
                    per_field[f] = per_field.get(f, 0) + 1
        if gaps:
            n = len(rows) or 1
            for f, c in sorted(per_field.items(), key=lambda x: -x[1]):
                pct = 100.0 * c / n
                line = ("%s: `%s` missing/null on %d of %d rows (%.0f%%)"
                        % (label, f, c, len(rows), pct))
                # A field absent from EVERY row is a stage that did not run — structural.
                # A field absent from a few is per-name data thinness — visible, not fatal.
                (degraded if c == len(rows) else warnings).append(
                    line + (" — absent on every row, so the stage that computes it did not run"
                            if c == len(rows) else ""))
        return gaps

    row_gaps = _scan(dl, REQUIRED_ROW_FIELDS, "daily_list")
    held_gaps = _scan(hp, REQUIRED_HELD_FIELDS, "held_positions")

    # ---------------------------------------------------------------- 5. the book we actually own
    # This is the check the PM asked for by name: not just "did AQE score a universe" but "did it
    # score OUR names". A held position with no AQE record is a position being carried with no
    # fresh structure behind its stop.
    held_report = {"journal_names": [], "covered": [], "uncovered": [], "by_source": {}}
    if journal:
        # Both blocks are searched — AQE files a held name under daily_list only if it also made
        # the scored longlist (2 of 12 on 25 Jul); the rest are under held_positions alone.
        # Looking in daily_list only is what made ten of twelve names read as 'absent'.
        index = {}
        for r in dl:
            if r.get("ticker"):
                index[r["ticker"]] = "daily_list"
        for r in hp:
            t = r.get("ticker")
            if t:
                index[t] = "both" if t in index else "held_positions"
        names = [p.get("ticker") for p in (journal.get("open_positions") or [])
                 if p.get("ticker") and p.get("aegis_status") != "pending_review"]
        held_report["journal_names"] = sorted(names)
        for t in sorted(set(names)):
            if t in index:
                held_report["covered"].append(t)
                held_report["by_source"][t] = index[t]
            else:
                held_report["uncovered"].append(t)
        if held_report["uncovered"]:
            degraded.append("held positions with NO record anywhere in today's export: %s — these "
                            "names are being carried on a stop that today's run did not refresh"
                            % ", ".join(held_report["uncovered"]))

    # ---------------------------------------------------------------- 6. sub-block staleness
    stale = {}
    for name, path, sev in DATED_SUBBLOCKS:
        v = _get(export, path) if len(path) > 1 else export.get(path[0])
        d = _date_only(v)
        if d is None:
            warnings.append("%s carries no date field — its vintage cannot be established" % name)
            continue
        lag = _days_between(d, export_date)
        stale[name] = {"date": d, "lag_days": lag}
        if lag and lag > 0:
            msg = ("%s was computed %s, %d day%s BEHIND the export that carries it (%s) — the "
                   "file's own date does not reveal this"
                   % (name, d, lag, "" if lag == 1 else "s", export_date))
            (degraded if sev == "degraded" else warnings).append(msg)

    # ---------------------------------------------------------------- 7. the hedge input sanity
    # The hedge decision is taken off held_book.beta_adj_exposure_usd. If the beta window has
    # produced a book that looks market-neutral, Phase 1 concludes "no hedge needed" and the
    # question never reaches the PM. That is a silent no-hedge decision made by a data artefact,
    # so it is surfaced here rather than left to be noticed.
    hb = export.get("held_book") or {}
    gross = hb.get("total_exposure_usd")
    beta_adj = hb.get("beta_adj_exposure_usd")
    hedge_input = {"gross_exposure_usd": gross, "beta_adj_exposure_usd": beta_adj,
                   "nav_weighted_beta_30d": hb.get("nav_weighted_beta_30d")}
    if gross and beta_adj is not None and abs(float(gross)) > 0:
        ratio = abs(float(beta_adj)) / abs(float(gross))
        hedge_input["beta_adj_to_gross"] = round(ratio, 4)
        if ratio < 0.25:
            degraded.append(
                "beta-adjusted exposure is %.0f on gross %.0f (%.1f%%) — the book reads close to "
                "market-neutral, which is what the hedge assessment sizes against. Verify the "
                "beta window before accepting 'no hedge needed' as a conclusion rather than an "
                "artefact." % (float(beta_adj), float(gross), 100 * ratio))
    negs = [p.get("ticker") for p in (hb.get("positions") or []) if (p.get("beta_30d") or 0) < 0]
    if negs:
        hedge_input["negative_beta_names"] = negs
        warnings.append("negative 30-day beta on long equity: %s — a short-window artefact that "
                        "reduces beta-adjusted exposure and therefore the hedge it implies"
                        % ", ".join(negs))

    # ---------------------------------------------------------------- verdict
    if incomplete:
        verdict, code = "INCOMPLETE", 1
    elif degraded:
        verdict, code = "DEGRADED", 2
    else:
        verdict, code = "COMPLETE", 0

    return {
        "verdict": verdict, "exit_code": code,
        "export_date": export_date, "today": today,
        "counts": {"daily_list": len(dl), "held_positions": len(hp),
                   "rows_with_gaps": len(row_gaps), "held_rows_with_gaps": len(held_gaps)},
        "incomplete": incomplete, "degraded": degraded, "warnings": warnings,
        "held_coverage": held_report, "subblock_dates": stale, "hedge_input": hedge_input,
        "row_gaps": row_gaps, "held_gaps": held_gaps,
    }


def render(rep):
    """Plain text, PM-readable. Numbers always shown; no acronyms."""
    out = ["AQE COVERAGE: %s  (export %s%s)"
           % (rep["verdict"], rep["export_date"],
              ", today %s" % rep["today"] if rep["today"] else "")]
    c = rep["counts"]
    out.append("  %d scored rows, %d held rows" % (c["daily_list"], c["held_positions"]))
    hc = rep["held_coverage"]
    if hc["journal_names"]:
        out.append("  held book: %d of %d journal names covered by today's export"
                   % (len(hc["covered"]), len(set(hc["journal_names"]))))
    for label, items in (("BLOCKING (retry later)", rep["incomplete"]),
                         ("DEGRADED (PM decides)", rep["degraded"]),
                         ("noted", rep["warnings"])):
        if items:
            out.append("  %s:" % label)
            out.extend("    - " + s for s in items)
    return "\n".join(out)


# --------------------------------------------------------------------------- selftest
def _selftest():
    good_row = {f: 1 for f in REQUIRED_ROW_FIELDS}
    good_row.update({"ticker": "AAA", "gics_sector": "XLK", "on_longlist": True, "on_elder": True})
    good_held = {f: 1 for f in REQUIRED_HELD_FIELDS}
    good_held["ticker"] = "HHH"
    good_held["gics_sector"] = "XLK"

    def base(**over):
        e = {"date": "2026-07-28", "daily_list": [dict(good_row)],
             "held_positions": [dict(good_held)],
             "summary": {"daily_count": 1, "longlist_count": 1, "elder_count": 1, "held_count": 1},
             "signal_radar": {"scan_date": "2026-07-28"},
             "intermarket": {"as_of": "2026-07-28"},
             "held_book": {"as_of": "2026-07-28 09:00:00 SGT", "total_exposure_usd": 100000.0,
                           "beta_adj_exposure_usd": 85000.0, "positions": [
                               {"ticker": "HHH", "beta_30d": 0.85}]},
             "sector_map_version": "2026-07-28"}
        e.update(over)
        return e

    # a clean export on its own date is COMPLETE
    r = check(base(), today="2026-07-28")
    assert r["verdict"] == "COMPLETE", (r["verdict"], r["incomplete"], r["degraded"])

    # yesterday's export is INCOMPLETE (time fixes it), never DEGRADED
    r = check(base(), today="2026-07-29")
    assert r["verdict"] == "INCOMPLETE" and r["exit_code"] == 1, r["verdict"]
    assert "has not published today's run" in r["incomplete"][0], r["incomplete"]

    # a forward-dated export is a fault, not freshness
    r = check(base(), today="2026-07-27")
    assert r["verdict"] == "DEGRADED" and any("AHEAD of today" in s for s in r["degraded"]), r

    # a summary that disagrees with its own block is DEGRADED
    e = base(); e["summary"]["daily_count"] = 99
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "DEGRADED" and any("daily_count" in s for s in r["degraded"]), r["degraded"]

    # a field null on EVERY row = a stage that did not run = DEGRADED
    e = base(); e["daily_list"][0]["ptrs"] = None
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "DEGRADED", r
    assert any("absent on every row" in s for s in r["degraded"]), r["degraded"]

    # but a field thin on SOME rows is a warning, not a verdict change
    e = base(); e["daily_list"].append(dict(good_row, ticker="BBB", ptrs=None,
                                            on_longlist=True, on_elder=True))
    e["summary"].update({"daily_count": 2, "longlist_count": 2, "elder_count": 2})
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "COMPLETE", (r["verdict"], r["degraded"])
    assert any("1 of 2 rows" in s for s in r["warnings"]), r["warnings"]

    # "TBD" is a gap, not a value — the AMPL/ptj_sector case
    e = base(); e["held_positions"][0]["gics_sector"] = "TBD"
    r = check(e, today="2026-07-28")
    assert any("gics_sector" in s for s in r["degraded"]), r["degraded"]

    # a sub-block computed a day behind the export that carries it
    e = base(); e["signal_radar"]["scan_date"] = "2026-07-27"
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "DEGRADED" and any("1 day BEHIND" in s for s in r["degraded"]), r["degraded"]

    # held coverage: a journal name in NEITHER block is uncovered and DEGRADED
    j = {"open_positions": [{"ticker": "HHH"}, {"ticker": "AAA"}, {"ticker": "ZZZ"}]}
    r = check(base(), journal=j, today="2026-07-28")
    assert r["held_coverage"]["uncovered"] == ["ZZZ"], r["held_coverage"]
    assert r["held_coverage"]["by_source"] == {"AAA": "daily_list", "HHH": "held_positions"}, \
        r["held_coverage"]["by_source"]
    assert r["verdict"] == "DEGRADED", r["degraded"]

    # a name found only in held_positions IS covered — the ten-of-twelve case that used to read
    # as missing because only daily_list was searched
    j2 = {"open_positions": [{"ticker": "HHH"}]}
    r = check(base(), journal=j2, today="2026-07-28")
    assert r["held_coverage"]["covered"] == ["HHH"] and r["verdict"] == "COMPLETE", r

    # a pending_review fill is not yet ours, so it is not held-coverage's problem
    j3 = {"open_positions": [{"ticker": "HHH"}, {"ticker": "QQQ", "aegis_status": "pending_review"}]}
    r = check(base(), journal=j3, today="2026-07-28")
    assert r["held_coverage"]["uncovered"] == [] and r["verdict"] == "COMPLETE", r

    # the hedge input: a near-neutral beta-adjusted book is surfaced, not silently accepted
    e = base()
    e["held_book"].update({"beta_adj_exposure_usd": 7751.0,
                           "positions": [{"ticker": "HHH", "beta_30d": -0.23}]})
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "DEGRADED", r
    assert any("market-neutral" in s for s in r["degraded"]), r["degraded"]
    assert any("negative 30-day beta" in s for s in r["warnings"]), r["warnings"]
    assert r["hedge_input"]["beta_adj_to_gross"] == 0.0775, r["hedge_input"]

    # an empty daily_list is INCOMPLETE (AQE mid-run), never COMPLETE
    e = base(); e["daily_list"] = []; e["summary"]["daily_count"] = 0
    e["summary"]["longlist_count"] = 0; e["summary"]["elder_count"] = 0
    r = check(e, today="2026-07-28")
    assert r["verdict"] == "INCOMPLETE", r

    # determinism: no wall clock anywhere — same inputs, same verdict, and no `today` means no
    # freshness opinion at all rather than a guess
    r = check(base())
    assert r["verdict"] == "COMPLETE" and r["today"] is None, r

    print("aqe_coverage.py selftest: PASS  (freshness split INCOMPLETE-vs-DEGRADED; summary "
          "reconciliation; every-row vs some-row gaps; TBD counted as a gap; sub-block lag; "
          "held coverage across BOTH export blocks; hedge-input sanity; deterministic)")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Completeness + freshness check on the AQE export (deterministic, law 4). "
                    "Complementary to tripwires.py (anomaly detection) — not a replacement.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--export", required=True)
    c.add_argument("--journal", help="the Aegis journal, for held-book coverage")
    c.add_argument("--today", help="ISO date to judge freshness against; omit for no freshness opinion")
    c.add_argument("--json", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return 0
    with open(a.export) as fh:
        export = json.load(fh)
    journal = None
    if a.journal and os.path.exists(a.journal):
        with open(a.journal) as fh:
            journal = json.load(fh)
    rep = check(export, journal=journal, today=a.today)
    print(json.dumps(rep, indent=1) if a.json else render(rep))
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
