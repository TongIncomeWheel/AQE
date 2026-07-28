#!/usr/bin/env python3
"""artefact_check.py — are the day's files ACTUALLY on disk, and are they the day's? (D-92)

WHAT THIS ANSWERS, IN ONE SENTENCE:
  every step of the data half claimed it wrote a file — did the files land, do they parse, do
  they carry today's date, and is there anything real inside them?

WHY IT IS A SEPARATE TOOL AND NOT A BRANCH INSIDE aqe_coverage.py.
  aqe_coverage.py interrogates ONE file's contents: is the AQE export complete and fresh. This
  asks a question one level up — the SET of artefacts the data half is contracted to produce.
  A run can pass coverage on a perfect export and still hand the expensive half nothing, because
  the universe build silently wrote to yesterday's date folder, or the held-book refresh errored
  after the export was already validated, or the whole session's work never left local disk.
  Those are not export defects; no amount of reading the export finds them.

  The three checks in the data half now read, in order:
    tripwires.py      — is what is here BELIEVABLE?     (anomaly)
    aqe_coverage.py   — is all of the EXPORT here?      (completeness + freshness of one file)
    artefact_check.py — are all of the FILES here?      (the run's whole output set)

THE POINT OF THE `report` SUBCOMMAND.
  The data half's deliverable to the PM is not a chat paragraph he has to trust — it is a file he
  can open. `report` renders the same verdict as a self-contained markdown document written to
  data/sod/DATE/premarket_data_report.md. The skill delivers THAT file. Every number in it is
  read off disk at render time, so the document cannot claim something the files do not say.

DETERMINISTIC (law 4). No model, no network. `--date` is passed in by the caller and never read
from the wall clock, so re-checking an old day reproduces that day's verdict exactly.

EXIT CODES (the house three-way grammar, same as phase_gate.py and aqe_coverage.py):
  0 = COMPLETE  — every contracted artefact is present, parses, and is today's.
  1 = MISSING   — one or more artefacts are simply not there. The step that writes them has not
                  run (or has not run yet). Re-run that step; this is not a page.
  2 = INVALID   — the artefacts are present but wrong: unparseable, stale-dated, or empty of the
                  content that makes them useful. Time does not fix this. Page.

Usage:
  python3 tools/artefact_check.py check  --date YYYY-MM-DD [--root .] [--json]
  python3 tools/artefact_check.py report --date YYYY-MM-DD [--root .] [--out PATH]
  python3 tools/artefact_check.py selftest
"""
import json
import argparse
import datetime
import glob
import os
import sys

# --- The D-53 voice menu. universe.json must carry these PER NAME or the voices read half-blind
# and the eleven judgment-tier spawns are wasted. Checked as coverage across names, not as a
# per-name assertion: AQE legitimately omits a field on a thin name, but a field present on ZERO
# names means the stage that computes it did not run.
MENU_FIELDS = [
    "sc_momentum", "flow", "energy", "structure", "mp", "mp_state", "mp_accel_state",
    "elder", "elder_5d", "elder_pattern", "structure_shift", "sma_distance_pct", "rvol",
    "rs_spy_20d", "rs_leadership", "ma_20", "ma_50", "ma_100", "ma_200", "atr_14d",
    "bracket", "lens", "lens_positive", "sector_trend_state", "beta_30d",
]

# --- A journal older than this is not "yesterday's, fine" — it is a post-market that has not run
# for days, and every held number computed off it is that old. 4 calendar days clears a normal
# weekend plus one public holiday and nothing more.
MAX_JOURNAL_LAG_DAYS = 4


def _date_only(v):
    if not v:
        return None
    return str(v).strip().split(" ")[0].split("T")[0]


def _lag_days(older, newer):
    try:
        a = datetime.date.fromisoformat(_date_only(older))
        b = datetime.date.fromisoformat(_date_only(newer))
    except (TypeError, ValueError):
        return None
    return (b - a).days


def _load(path):
    """Returns (doc, error). Never raises — a corrupt file is a finding, not a crash."""
    if not os.path.exists(path):
        return None, "not on disk"
    if os.path.getsize(path) == 0:
        return None, "zero bytes"
    try:
        with open(path) as fh:
            return json.load(fh), None
    except (ValueError, OSError) as exc:
        return None, "unreadable/unparseable: %s" % exc


def _journal_path(root, date):
    """Today's journal if it exists, else the most recent one, so a lagging post-market is
    REPORTED with its real date rather than read as an absent file."""
    exact = os.path.join(root, "data", "journal", "aegis_journal_%s.json" % date)
    if os.path.exists(exact):
        return exact
    found = sorted(glob.glob(os.path.join(root, "data", "journal", "aegis_journal_*.json")))
    return found[-1] if found else exact


# --------------------------------------------------------------------------- the four artefacts
def check(root, date):
    """Pure-ish (reads disk only, law 4). Returns a report dict."""
    missing, invalid, notes = [], [], []
    rows = []

    def row(label, path, produced_by, status, detail):
        rows.append({"artefact": label, "path": os.path.relpath(path, root),
                     "produced_by": produced_by, "status": status, "detail": detail})

    # ---------------------------------------------------------------- 1. the AQE export
    p = os.path.join(root, "output", "aqe_daily_export.json")
    export, err = _load(p)
    if err:
        missing.append("AQE export (%s) — %s. Without it there is no universe and no held-book "
                       "refresh; nothing downstream in this half can run." % (os.path.relpath(p, root), err))
        row("AQE export", p, "step 4 (Drive pull)", "MISSING", err)
    else:
        ed = _date_only(export.get("date"))
        n_rows = len(export.get("daily_list") or [])
        n_held = len(export.get("held_positions") or [])
        detail = "%d scored rows, %d held rows, dated %s" % (n_rows, n_held, ed)
        if ed != date:
            lag = _lag_days(ed, date)
            invalid.append("AQE export is dated %s but the run is for %s (%s) — the pull returned "
                           "a file that is not today's." % (ed, date,
                                                            "%d days behind" % lag if lag else "date mismatch"))
            row("AQE export", p, "step 4 (Drive pull)", "STALE", detail)
        elif n_rows == 0:
            invalid.append("AQE export is dated today but carries an empty daily_list — a "
                           "well-formed file with no run inside it.")
            row("AQE export", p, "step 4 (Drive pull)", "EMPTY", detail)
        else:
            row("AQE export", p, "step 4 (Drive pull)", "OK", detail)

    # ---------------------------------------------------------------- 2. the universe
    p = os.path.join(root, "data", "sod", date, "universe.json")
    uni, err = _load(p)
    if err:
        missing.append("universe file (%s) — %s. This is the ONLY file the voices nominate from; "
                       "the judgement half has nothing to read." % (os.path.relpath(p, root), err))
        row("universe", p, "step 6 (universe build)", "MISSING", err)
    else:
        names = uni.get("names") or []
        ud = _date_only(uni.get("date"))
        detail = "%d names, dated %s" % (len(names), ud)
        if not names:
            invalid.append("universe file is present but carries zero names — the builder ran and "
                           "produced nothing.")
            row("universe", p, "step 6 (universe build)", "EMPTY", detail)
        elif ud != date:
            invalid.append("universe file is dated %s inside a %s folder — the builder read an "
                           "export that was not today's." % (ud, date))
            row("universe", p, "step 6 (universe build)", "STALE", detail)
        else:
            # The thin-universe check (D-53). A menu field on ZERO names is a dead stage.
            dead, thin = [], []
            for f in MENU_FIELDS:
                c = sum(1 for n in names if n.get(f) is not None)
                if c == 0:
                    dead.append(f)
                elif c < 0.5 * len(names):
                    thin.append("%s on %d of %d" % (f, c, len(names)))
            if dead:
                invalid.append("universe carries NO value for %s on any of its %d names — the "
                               "voice menu is incomplete, so those seats would nominate half-blind. "
                               "Fields: %s" % (len(dead), len(names), ", ".join(dead)))
                row("universe", p, "step 6 (universe build)", "THIN", detail + "; %d dead menu fields" % len(dead))
            else:
                if thin:
                    notes.append("universe menu fields present on under half the names: %s — thin "
                                 "data, not a dead stage; the voices see it and say so."
                                 % "; ".join(thin))
                row("universe", p, "step 6 (universe build)", "OK",
                    detail + ", full voice menu present")

    # ---------------------------------------------------------------- 3. the journal
    p = _journal_path(root, date)
    jrn, err = _load(p)
    if err:
        missing.append("journal (%s) — %s. The journal is the Aegis book of record; without it "
                       "there is no held book to refresh and no dynCap to size against."
                       % (os.path.relpath(p, root), err))
        row("journal", p, "post-market, refreshed at step 7", "MISSING", err)
    else:
        jd = _date_only(jrn.get("date")) or _date_only(
            os.path.basename(p).replace("aegis_journal_", "").replace(".json", ""))
        opens = [o for o in (jrn.get("open_positions") or [])
                 if o.get("aegis_status") != "pending_review"]
        fresh = sum(1 for o in opens if _date_only(o.get("aqe_snapshot_as_of")) == date)
        stopped = sum(1 for o in opens if o.get("stop_reference") is not None)
        metrics = jrn.get("metrics") or {}
        conc = metrics.get("sector_concentration_pct")
        detail = ("%d open positions, %d with today's AQE snapshot, %d with a stop reference; "
                  "dated %s" % (len(opens), fresh, stopped, jd))
        lag = _lag_days(jd, date)
        if lag is not None and lag > MAX_JOURNAL_LAG_DAYS:
            invalid.append("journal is dated %s, %d days before this run (%s) — post-market has "
                           "not written for days, so every held number here is that old."
                           % (jd, lag, date))
            row("journal", p, "post-market, refreshed at step 7", "STALE", detail)
        elif opens and fresh == 0:
            invalid.append("not one of the %d open positions carries an AQE snapshot dated %s — "
                           "the held-book refresh did not land, so the trailing stops were "
                           "recomputed off a snapshot that never moved." % (len(opens), date))
            row("journal", p, "post-market, refreshed at step 7", "NOT REFRESHED", detail)
        else:
            if opens and fresh < len(opens):
                notes.append("%d of %d open positions did not get a snapshot dated %s — those "
                             "names are genuinely absent from both export blocks and are flagged "
                             "not_in_todays_export, carrying a stale structural stop."
                             % (len(opens) - fresh, len(opens), date))
            if opens and stopped < len(opens):
                notes.append("%d of %d open positions carry no stop_reference — the stop-update "
                             "step wrote fewer floors than there are positions."
                             % (len(opens) - stopped, len(opens)))
            if not metrics:
                notes.append("journal carries no `metrics` block — portfolio_metrics has not been "
                             "computed against this journal.")
            elif conc is not None and isinstance(conc, dict) and set(conc) == {"UNKNOWN"}:
                invalid.append("sector concentration reads 100%% UNKNOWN — the sector key is not "
                               "resolving off the held snapshot, so the concentration gate is "
                               "measuring nothing. This is a regression, not a book state.")
            row("journal", p, "post-market, refreshed at step 7", "OK", detail)

    # ---------------------------------------------------------------- 4. the dynCap ledger
    p = os.path.join(root, "data", "persistent", "dyncap_ledger.json")
    led, err = _load(p)
    if err:
        missing.append("dynCap ledger (%s) — %s. Every size tomorrow is computed against dynCap; "
                       "absent, sizing fails closed." % (os.path.relpath(p, root), err))
        row("dynCap ledger", p, "step 8 (dynCap update)", "MISSING", err)
    else:
        # The key names are read off the ledger dyncap_ledger.py actually writes — `dyncap_usd`,
        # `one_r_usd`, `marked_asof`. Asking for a plausible-sounding key nothing carries is the
        # exact defect that made sector concentration read 100% UNKNOWN for weeks; do not "tidy"
        # these into shorter names without changing the writer first.
        val = led.get("dyncap_usd")
        one_r = led.get("one_r_usd")
        as_of = _date_only(led.get("marked_asof"))
        detail = "dynCap %s, 1R %s, marked %s" % (
            ("{:,.0f}".format(float(val)) if isinstance(val, (int, float)) else val),
            ("{:,.0f}".format(float(one_r)) if isinstance(one_r, (int, float)) else one_r), as_of)
        if not isinstance(val, (int, float)) or val == 0:
            invalid.append("dynCap ledger is present but carries no usable value — sizing has "
                           "nothing to compute against.")
            row("dynCap ledger", p, "step 8 (dynCap update)", "EMPTY", detail)
        else:
            if as_of and as_of != date:
                notes.append("dynCap ledger is stamped %s, not %s — it was not refreshed on this "
                             "run's mark." % (as_of, date))
            row("dynCap ledger", p, "step 8 (dynCap update)", "OK", detail)

    # ---------------------------------------------------------------- verdict
    # MISSING outranks INVALID deliberately: a step that has not run is re-runnable, and telling
    # the PM "your universe is thin" is noise when the real answer is "the builder never ran".
    if missing:
        verdict, code = "MISSING", 1
    elif invalid:
        verdict, code = "INVALID", 2
    else:
        verdict, code = "COMPLETE", 0

    return {"verdict": verdict, "exit_code": code, "date": date, "root": os.path.abspath(root),
            "artefacts": rows, "missing": missing, "invalid": invalid, "notes": notes}


# --------------------------------------------------------------------------- rendering
def render(rep):
    """Terminal-readable. The `report` subcommand renders the same facts as markdown."""
    out = ["ARTEFACT CHECK: %s  (run date %s)" % (rep["verdict"], rep["date"])]
    for r in rep["artefacts"]:
        out.append("  [%-13s] %-14s %s" % (r["status"], r["artefact"], r["detail"]))
    for label, items in (("MISSING (re-run the step)", rep["missing"]),
                         ("INVALID (page — time does not fix these)", rep["invalid"]),
                         ("noted", rep["notes"])):
        if items:
            out.append("  %s:" % label)
            out.extend("    - " + s for s in items)
    return "\n".join(out)


VERDICT_LINE = {
    "COMPLETE": "**Every file the data half is contracted to produce is on disk, parses, and is "
                "dated for this run.** The judgement half has what it needs.",
    "MISSING": "**At least one contracted file is not on disk.** The step that writes it has not "
               "run. Re-run that step — this is not a fault, and it is not a page.",
    "INVALID": "**The files are there but at least one of them is wrong** — stale-dated, empty, or "
               "missing the content that makes it usable. Time does not fix this.",
}


def render_markdown(rep, coverage=None):
    """The document the PM opens. Every number here was read off disk by check() at render time —
    this file cannot claim something the artefacts do not say."""
    L = ["# Premarket data — %s" % rep["date"],
         "",
         "Verdict: **%s**" % rep["verdict"],
         "",
         VERDICT_LINE.get(rep["verdict"], ""),
         "",
         "## The files",
         "",
         "| Artefact | Status | What is in it | File | Written by |",
         "|---|---|---|---|---|"]
    for r in rep["artefacts"]:
        L.append("| %s | %s | %s | `%s` | %s |"
                 % (r["artefact"], r["status"], r["detail"], r["path"], r["produced_by"]))
    if coverage:
        L += ["", "## Did AQE finish the job",
              "",
              "| Question | Answer |", "|---|---|",
              "| Verdict on today's export | **%s** |" % coverage.get("verdict"),
              "| Scored rows | %s |" % (coverage.get("counts", {}).get("daily_list")),
              "| Held rows in the export | %s |" % (coverage.get("counts", {}).get("held_positions")),
              "| Held names in the journal covered by the export | %s of %s |"
              % (len(coverage.get("held_coverage", {}).get("covered", [])),
                 len(set(coverage.get("held_coverage", {}).get("journal_names", []))))]
        unc = coverage.get("held_coverage", {}).get("uncovered") or []
        if unc:
            L.append("| Held names with NO record in today's export | %s |" % ", ".join(unc))
    for title, items in (("## Blocking — a file is not there", rep["missing"]),
                         ("## Blocking — a file is wrong", rep["invalid"]),
                         ("## Noted — visible, not blocking", rep["notes"])):
        if items:
            L += ["", title, ""] + ["- " + s for s in items]
    if coverage:
        for title, key in (("## Export gaps the PM decides on", "degraded"),
                           ("## Export — noted", "warnings")):
            items = coverage.get(key) or []
            if items:
                L += ["", title, ""] + ["- " + s for s in items]
    L += ["", "---", "",
          "Generated by `tools/artefact_check.py` from the files on disk. Nothing in this run is "
          "scheduled — the data half is started by hand, and this document is the record of what "
          "that run produced.", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- selftest
def _selftest():
    import tempfile
    import shutil

    def build(root, date, **over):
        os.makedirs(os.path.join(root, "output"), exist_ok=True)
        os.makedirs(os.path.join(root, "data", "sod", date), exist_ok=True)
        os.makedirs(os.path.join(root, "data", "journal"), exist_ok=True)
        os.makedirs(os.path.join(root, "data", "persistent"), exist_ok=True)
        export = over.get("export", {"date": date,
                                     "daily_list": [{"ticker": "AAA"}],
                                     "held_positions": [{"ticker": "HHH"}]})
        name = {f: 1 for f in MENU_FIELDS}
        name["ticker"] = "AAA"
        uni = over.get("universe", {"date": date, "count": 1, "names": [name]})
        jrn = over.get("journal", {
            "date": date,
            "open_positions": [{"ticker": "HHH", "aqe_snapshot_as_of": date,
                                "stop_reference": 10.0, "aegis_status": "confirmed"}],
            "metrics": {"sector_concentration_pct": {"XLK": 100.0}}})
        led = over.get("ledger", {"dyncap_usd": 100000.0, "one_r_usd": 1000.0,
                                  "marked_asof": date + " 21:22 UTC"})
        json.dump(export, open(os.path.join(root, "output", "aqe_daily_export.json"), "w"))
        json.dump(uni, open(os.path.join(root, "data", "sod", date, "universe.json"), "w"))
        json.dump(jrn, open(os.path.join(root, "data", "journal",
                                         "aegis_journal_%s.json" % date), "w"))
        json.dump(led, open(os.path.join(root, "data", "persistent", "dyncap_ledger.json"), "w"))

    D = "2026-07-28"
    root = tempfile.mkdtemp()
    try:
        # a complete day is COMPLETE
        build(root, D)
        r = check(root, D)
        assert r["verdict"] == "COMPLETE" and r["exit_code"] == 0, (r["missing"], r["invalid"])
        assert len(r["artefacts"]) == 4, r["artefacts"]

        # markdown renders every artefact as a table row and never crashes on a missing coverage arg
        md = render_markdown(r)
        assert md.startswith("# Premarket data — %s" % D)
        assert md.count("\n| ") >= 4, md

        # a deleted universe is MISSING (exit 1), not INVALID — re-run the builder, do not page
        os.remove(os.path.join(root, "data", "sod", D, "universe.json"))
        r = check(root, D)
        assert r["verdict"] == "MISSING" and r["exit_code"] == 1, r
        assert any("universe file" in s for s in r["missing"]), r["missing"]

        # yesterday's export sitting in today's run is INVALID (exit 2), not MISSING
        shutil.rmtree(root); root = tempfile.mkdtemp(); build(root, D)
        json.dump({"date": "2026-07-27", "daily_list": [{"ticker": "AAA"}], "held_positions": []},
                  open(os.path.join(root, "output", "aqe_daily_export.json"), "w"))
        r = check(root, D)
        assert r["verdict"] == "INVALID" and r["exit_code"] == 2, r
        assert any("dated 2026-07-27" in s for s in r["invalid"]), r["invalid"]

        # MISSING outranks INVALID: a stale export AND an absent universe reports the absent file
        os.remove(os.path.join(root, "data", "sod", D, "universe.json"))
        r = check(root, D)
        assert r["verdict"] == "MISSING", r

        # a universe with a dead menu field is INVALID — this is the thin-universe catch (D-53)
        shutil.rmtree(root); root = tempfile.mkdtemp()
        thin = {f: 1 for f in MENU_FIELDS}
        thin["elder_5d"] = None
        build(root, D, universe={"date": D, "count": 1, "names": [dict(thin, ticker="AAA")]})
        r = check(root, D)
        assert r["verdict"] == "INVALID", r
        assert any("elder_5d" in s for s in r["invalid"]), r["invalid"]

        # a held book that got NO fresh snapshot is INVALID — the refresh silently not landing is
        # exactly the failure that risk-managed ten of twelve names off a stop that never moved
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, D, journal={"date": D, "open_positions": [
            {"ticker": "HHH", "aqe_snapshot_as_of": "2026-07-20", "stop_reference": 10.0}]})
        r = check(root, D)
        assert r["verdict"] == "INVALID", r
        assert any("did not land" in s for s in r["invalid"]), r["invalid"]

        # but SOME names unrefreshed is a note, not a verdict change — genuinely absent names exist
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, D, journal={"date": D, "open_positions": [
            {"ticker": "HHH", "aqe_snapshot_as_of": D, "stop_reference": 10.0},
            {"ticker": "III", "aqe_snapshot_as_of": "2026-07-20", "stop_reference": 9.0}]})
        r = check(root, D)
        assert r["verdict"] == "COMPLETE", (r["invalid"], r["notes"])
        assert any("1 of 2 open positions did not get" in s for s in r["notes"]), r["notes"]

        # a journal days behind is INVALID — post-market has not run, every held number is that old
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, "2026-07-10")
        os.makedirs(os.path.join(root, "data", "sod", D), exist_ok=True)
        shutil.copy(os.path.join(root, "data", "sod", "2026-07-10", "universe.json"),
                    os.path.join(root, "data", "sod", D, "universe.json"))
        json.dump({"date": D, "count": 1, "names": [dict({f: 1 for f in MENU_FIELDS}, ticker="AAA")]},
                  open(os.path.join(root, "data", "sod", D, "universe.json"), "w"))
        json.dump({"date": D, "daily_list": [{"ticker": "AAA"}], "held_positions": []},
                  open(os.path.join(root, "output", "aqe_daily_export.json"), "w"))
        r = check(root, D)
        assert r["verdict"] == "INVALID" and any("post-market has not written" in s
                                                 for s in r["invalid"]), r["invalid"]

        # sector concentration stuck at 100% UNKNOWN is called a regression, not a book state
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, D, journal={"date": D, "open_positions": [
            {"ticker": "HHH", "aqe_snapshot_as_of": D, "stop_reference": 10.0}],
            "metrics": {"sector_concentration_pct": {"UNKNOWN": 100.0}}})
        r = check(root, D)
        assert r["verdict"] == "INVALID" and any("UNKNOWN" in s for s in r["invalid"]), r["invalid"]

        # a corrupt file is a finding, never a crash
        shutil.rmtree(root); root = tempfile.mkdtemp(); build(root, D)
        open(os.path.join(root, "output", "aqe_daily_export.json"), "w").write("{not json")
        r = check(root, D)
        assert r["verdict"] == "MISSING" and any("unparseable" in s for s in r["missing"]), r

        # the ledger is read by the key the writer actually writes; a plausible wrong key must NOT
        # silently pass as "present" (the 100%-UNKNOWN failure mode, one level up)
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, D, ledger={"dyncap": 100000.0, "as_of": D})   # the WRONG key names
        r = check(root, D)
        assert r["verdict"] == "INVALID" and any("no usable value" in s for s in r["invalid"]), r
        # ...and a ledger marked on an older day is a note, not a blocker
        shutil.rmtree(root); root = tempfile.mkdtemp()
        build(root, D, ledger={"dyncap_usd": 65761.65, "one_r_usd": 986.42,
                               "marked_asof": "2026-07-21 21:22 UTC"})
        r = check(root, D)
        assert r["verdict"] == "COMPLETE" and any("stamped 2026-07-21" in s for s in r["notes"]), r

        # determinism: same disk, same date, same verdict — no wall clock anywhere
        shutil.rmtree(root); root = tempfile.mkdtemp(); build(root, D)
        assert check(root, D) == check(root, D)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("artefact_check.py selftest: PASS  (four artefacts; MISSING outranks INVALID; stale "
          "export; dead voice-menu field; held refresh that did not land vs some names absent; "
          "journal lag; UNKNOWN-sector regression; corrupt file is a finding; deterministic)")


# --------------------------------------------------------------------------- CLI
def _coverage_for(root, date):
    """Best-effort: fold the export's own coverage verdict into the PM document so he opens ONE
    file, not two. Absent or unrunnable, the document is still rendered without that section."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import aqe_coverage
        ex = os.path.join(root, "output", "aqe_daily_export.json")
        if not os.path.exists(ex):
            return None
        jp = _journal_path(root, date)
        journal = json.load(open(jp)) if os.path.exists(jp) else None
        return aqe_coverage.check(json.load(open(ex)), journal=journal, today=date)
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Does the day's artefact SET exist on disk and is it the day's? "
                    "(deterministic, law 4). Complementary to aqe_coverage.py, which "
                    "interrogates one file's contents.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--date", required=True, help="ISO run date; never read from the clock")
        c.add_argument("--root", default=".", help="repo root (default: cwd)")
        if name == "check":
            c.add_argument("--json", action="store_true")
        else:
            c.add_argument("--out", help="default: data/sod/<date>/premarket_data_report.md")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        _selftest()
        return 0

    rep = check(a.root, a.date)
    if a.cmd == "check":
        print(json.dumps(rep, indent=1) if a.json else render(rep))
        return rep["exit_code"]

    out = a.out or os.path.join(a.root, "data", "sod", a.date, "premarket_data_report.md")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as fh:
        fh.write(render_markdown(rep, coverage=_coverage_for(a.root, a.date)))
    print(out)
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
