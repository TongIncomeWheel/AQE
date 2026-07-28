#!/usr/bin/env python3
"""
pipeline_ledger.py — the Pipeline Ledger (D-83): ideas that have NOT fired yet.

WHY THIS EXISTS
  A name the committee liked but did not advance used to vanish into the watch
  table and be re-discovered from scratch (or not at all) the next morning. This
  store keeps it alive with its ORIGINAL reasoning attached, so re-surfacing it
  costs a file read instead of a re-nomination.

WHAT IT IS NOT
  Not the Nomination Ledger (tools/nomination_ledger.py, data/persistent/ledger.jsonl).
  That one tracks the d1..d15 OUTCOME of names already nominated — a scoring store.
  This one is a LIFECYCLE store for ideas still waiting on something.

WHO DECIDES WHAT GOES IN
  The committee, once, at deliberation time, via `ledger_proposal` on its verdict
  (contracts/committee.schema.json). Post-market FILES what was proposed — it makes
  no judgement of its own and never sweeps in everything that failed to advance.
  That narrowing is the whole point: the store stays small enough to be read.

DETERMINISTIC (law 4). No model, no network. Sole writer of
data/persistent/pipeline_ledger.json (contracts/pipeline_ledger.schema.json).

COMMANDS
  persist --committee data/sod/DATE/committee.json [--date D]
        File this session's proposals. Idempotent — re-running the same committee
        file the same day changes nothing.
  sweep --date D [--export data/sod/DATE/aqe_daily_export.json]
        Expire rows past their TTL; with --export, evaluate every trigger_silent
        row's trigger against today's record and mark the ones that fired.
  active [--classification daily_reconsider|trigger_silent] [--json]
        Read-out. What premarket re-feeds into the tally, and what the market-hours
        sweep adds to its watch membership.
  close --ticker T --reason "..." [--date D]
        Resolve a row deliberately (it advanced into the plan; the PM dropped it).
  render [--date D]
        The plain-text card for the PM's glance.
  selftest
"""
import argparse
import json
import os
import sys
import datetime as _dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.environ.get(
    "AEGIS_PIPELINE_LEDGER",
    os.path.join(ROOT, "data", "persistent", "pipeline_ledger.json"),
)
_PARAMS_PATH = os.path.join(ROOT, "charter", "parameters.yaml")

X_VERSION = "1.0.0"

DEFAULTS = {
    "ttl_days": 30,          # bounded TTL — an idea dies stale unless re-proposed
    "max_rows": 60,          # hard ceiling: a ledger you cannot read is not a ledger
}

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


# --------------------------------------------------------------------------- params
def load_params():
    """parameters.yaml `pipeline_ledger:` block overlaid on DEFAULTS (same pattern
    as lanes.load_params — the PM tunes the yaml and it actually takes effect)."""
    p = dict(DEFAULTS)
    try:
        import yaml
        with open(_PARAMS_PATH) as fh:
            doc = yaml.safe_load(fh) or {}
        block = doc.get("pipeline_ledger", {}) or {}
        for k in p:
            v = block.get(k)
            if isinstance(v, (int, float)):
                p[k] = int(v)
    except Exception:
        pass
    return p


def _today(explicit=None):
    return explicit or _dt.date.today().isoformat()


def _plus_days(datestr, days):
    d = _dt.date.fromisoformat(datestr)
    return (d + _dt.timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------- store
def load():
    if not os.path.exists(STORE):
        return {"x_version": X_VERSION, "updated": _today(), "rows": []}
    with open(STORE) as fh:
        doc = json.load(fh)
    doc.setdefault("rows", [])
    doc.setdefault("x_version", X_VERSION)
    return doc


def save(doc, date=None):
    doc["x_version"] = X_VERSION
    doc["updated"] = _today(date)
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")


def _row(doc, ticker):
    for r in doc["rows"]:
        if r["ticker"] == ticker:
            return r
    return None


def _log(row, date, event, note=None):
    row.setdefault("history", []).append({"date": date, "event": event, "note": note})


def _dotted(rec, path):
    """Look up a dotted field path in an AQE record. Returns None if any hop misses —
    a missing field is NEVER treated as a satisfied trigger."""
    cur = rec
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# --------------------------------------------------------------------------- persist
def _validate_proposal(prop, ticker):
    """Return (ok, reason). The one place a bad proposal is caught."""
    if not isinstance(prop, dict):
        return False, "ledger_proposal is not an object"
    if prop.get("propose") is not True:
        return False, "propose is not true"
    cls = prop.get("classification")
    if cls not in ("daily_reconsider", "trigger_silent"):
        return False, "classification must be daily_reconsider or trigger_silent (got %r)" % (cls,)
    reason = (prop.get("reason") or "").strip()
    if not reason:
        return False, "reason is empty — a row with no case snapshot cannot be re-surfaced"
    trig = prop.get("trigger")
    if cls == "trigger_silent":
        # A parked name with no stated condition would be parked forever. Reject it
        # loudly rather than filing an idea that can never come back.
        if not isinstance(trig, dict):
            return False, "trigger_silent requires a trigger {field, op, value}"
        if not trig.get("field") or trig.get("op") not in _OPS:
            return False, "trigger needs a field and an op in %s" % (list(_OPS),)
        if not isinstance(trig.get("value"), (int, float)):
            return False, "trigger value must be a number"
    return True, ""


def persist(args):
    p = load_params()
    date = _today(args.date)
    with open(args.committee) as fh:
        cm = json.load(fh)
    origin_date = cm.get("date") or date

    doc = load()
    filed, extended, rejected, skipped = [], [], [], []

    for v in cm.get("verdicts", []) or []:
        ticker = str(v.get("ticker", "")).upper()
        if not ticker:
            continue
        prop = v.get("ledger_proposal")
        if prop is None:
            continue                                   # the default: not proposed, dropped
        ok, why = _validate_proposal(prop, ticker)
        if not ok:
            if prop.get("propose") is True:
                rejected.append({"ticker": ticker, "reason": why})
            else:
                skipped.append(ticker)
            continue
        if v.get("verdict") == "ADVANCE":
            # An advanced name is in the plan, not the pipeline. Filing it here would
            # double-track it and re-surface a name already live.
            rejected.append({"ticker": ticker, "reason": "verdict is ADVANCE — it belongs in the plan, not the pipeline"})
            continue

        cls = prop["classification"]
        trig = prop.get("trigger") if cls == "trigger_silent" else None
        existing = _row(doc, ticker)
        if existing and existing.get("status") == "active":
            # Re-proposed by a later committee: refresh the case and push the TTL out
            # rather than creating a second row for the same name.
            existing["case_snapshot"] = prop["reason"]
            existing["classification"] = cls
            existing["trigger"] = trig
            existing["conviction"] = v.get("conviction")
            existing["origin_verdict"] = v.get("verdict")
            existing["expiry_date"] = _plus_days(date, p["ttl_days"])
            existing["proposed_count"] = int(existing.get("proposed_count", 1)) + 1
            existing["last_seen"] = date
            _log(existing, date, "re-proposed", "TTL extended to %s (proposal #%d)"
                 % (existing["expiry_date"], existing["proposed_count"]))
            extended.append(ticker)
            continue

        row = {
            "ticker": ticker,
            "origin_date": origin_date,
            "origin_session": args.session,
            "origin_verdict": v.get("verdict"),
            "case_snapshot": prop["reason"],
            "conviction": v.get("conviction"),
            "classification": cls,
            "trigger": trig,
            "status": "active",
            "expiry_date": _plus_days(date, p["ttl_days"]),
            "last_seen": date,
            "fired_on": None,
            "fired_note": None,
            "closed_on": None,
            "closed_reason": None,
            "proposed_count": 1,
            "history": [],
        }
        _log(row, date, "filed", "%s from %s (%s)" % (cls, args.session, v.get("verdict")))
        # Re-filing a name whose old row is fired/expired/closed: replace it, keeping
        # the history so the repeat shows up.
        if existing:
            row["history"] = existing.get("history", []) + row["history"]
            row["proposed_count"] = int(existing.get("proposed_count", 0)) + 1
            doc["rows"] = [r for r in doc["rows"] if r["ticker"] != ticker]
        doc["rows"].append(row)
        filed.append(ticker)

    # Ceiling: if active rows exceed max_rows, the OLDEST actives are expired out.
    # Stated loudly (no silent truncation) — a ledger nobody can read is dead weight.
    actives = [r for r in doc["rows"] if r.get("status") == "active"]
    overflow = []
    if len(actives) > p["max_rows"]:
        actives.sort(key=lambda r: (r.get("origin_date", ""), r["ticker"]))
        for r in actives[: len(actives) - p["max_rows"]]:
            r["status"] = "expired"
            r["last_seen"] = date
            _log(r, date, "expired", "ledger over max_rows=%d — oldest rows retired" % p["max_rows"])
            overflow.append(r["ticker"])

    save(doc, date)
    out = {
        "date": date, "committee": args.committee, "session": args.session,
        "filed": filed, "extended": extended, "rejected": rejected,
        "not_proposed": skipped, "overflow_expired": overflow,
        "active_rows": len([r for r in doc["rows"] if r.get("status") == "active"]),
    }
    print(json.dumps(out, indent=1))
    return 0


# --------------------------------------------------------------------------- sweep
def sweep(args):
    date = _today(args.date)
    doc = load()
    export = {}
    if args.export and os.path.exists(args.export):
        with open(args.export) as fh:
            ex = json.load(fh)
        for rec in ex.get("daily_list", []) or []:
            t = str(rec.get("ticker", "")).upper()
            if t:
                export[t] = rec

    expired, fired, checked, unseen = [], [], 0, []
    for r in doc["rows"]:
        if r.get("status") != "active":
            continue
        r["last_seen"] = date
        if r.get("expiry_date") and date >= r["expiry_date"]:
            r["status"] = "expired"
            _log(r, date, "expired", "TTL reached (%s) with no trigger" % r["expiry_date"])
            expired.append(r["ticker"])
            continue
        if r.get("classification") != "trigger_silent" or not r.get("trigger"):
            continue
        rec = export.get(r["ticker"])
        if rec is None:
            # Not in today's export = not evaluable. Say so; never treat a missing
            # field as a satisfied condition.
            unseen.append(r["ticker"])
            continue
        trig = r["trigger"]
        val = _dotted(rec, trig["field"])
        checked += 1
        if not isinstance(val, (int, float)):
            unseen.append(r["ticker"])
            continue
        if _OPS[trig["op"]](val, trig["value"]):
            r["status"] = "fired"
            r["fired_on"] = date
            r["fired_note"] = "%s = %s (trigger %s %s %s)" % (
                trig["field"], val, trig["field"], trig["op"], trig["value"])
            _log(r, date, "fired", r["fired_note"])
            fired.append({"ticker": r["ticker"], "why": r["fired_note"],
                          "case": r["case_snapshot"]})

    save(doc, date)
    out = {"date": date, "expired": expired, "fired": fired,
           "triggers_evaluated": checked, "not_evaluable": unseen,
           "active_rows": len([r for r in doc["rows"] if r.get("status") == "active"])}
    print(json.dumps(out, indent=1))
    return 0


# --------------------------------------------------------------------------- reads
def active(args):
    doc = load()
    rows = [r for r in doc["rows"] if r.get("status") == "active"]
    if args.classification:
        rows = [r for r in rows if r.get("classification") == args.classification]
    rows.sort(key=lambda r: (-int(r.get("conviction") or 0), r["ticker"]))
    if args.json:
        print(json.dumps({"date": doc.get("updated"), "count": len(rows), "rows": rows}, indent=1))
    else:
        for r in rows:
            print("%-6s %-17s %s" % (r["ticker"], r["classification"], r["case_snapshot"][:80]))
    return 0


def close(args):
    date = _today(args.date)
    doc = load()
    r = _row(doc, args.ticker.upper())
    if r is None:
        print(json.dumps({"error": "no row for %s" % args.ticker}))
        return 1
    r["status"] = "closed"
    r["closed_on"] = date
    r["closed_reason"] = args.reason
    _log(r, date, "closed", args.reason)
    save(doc, date)
    print(json.dumps({"ticker": r["ticker"], "status": "closed", "reason": args.reason}))
    return 0


def render(args):
    doc = load()
    rows = doc.get("rows", [])
    act = [r for r in rows if r.get("status") == "active"]
    fired = [r for r in rows if r.get("status") == "fired"]
    recon = [r for r in act if r["classification"] == "daily_reconsider"]
    silent = [r for r in act if r["classification"] == "trigger_silent"]
    L = ["PIPELINE LEDGER — %s" % doc.get("updated", "?"),
         "%d active (%d re-considered daily, %d parked on a trigger)" % (len(act), len(recon), len(silent))]
    if fired:
        L.append("")
        L.append("FIRED — needs a look:")
        for r in fired:
            L.append("  %-6s %s" % (r["ticker"], r.get("fired_note") or ""))
            L.append("         %s" % r["case_snapshot"][:100])
    if recon:
        L.append("")
        L.append("RE-CONSIDERED EVERY MORNING:")
        for r in recon:
            L.append("  %-6s (conv %s, since %s) %s" % (
                r["ticker"], r.get("conviction"), r["origin_date"], r["case_snapshot"][:80]))
    if silent:
        L.append("")
        L.append("PARKED — silent until:")
        for r in silent:
            t = r.get("trigger") or {}
            L.append("  %-6s %s %s %s — %s" % (
                r["ticker"], t.get("field"), t.get("op"), t.get("value"), r["case_snapshot"][:70]))
    print("\n".join(L))
    return 0


# --------------------------------------------------------------------------- selftest
def selftest(args):
    import tempfile
    global STORE
    tmp = tempfile.mkdtemp()
    STORE = os.path.join(tmp, "pipeline_ledger.json")

    committee = {
        "date": "2026-07-27",
        "deliberation_set": ["AAA", "BBB", "CCC", "DDD", "EEE"],
        "verdicts": [
            {"ticker": "AAA", "verdict": "PASS", "conviction": 3, "nominators": ["oneil"],
             "bear_case": "x", "dissent": [],
             "ledger_proposal": {"propose": True, "classification": "daily_reconsider",
                                 "reason": "base intact, needs one more day of volume"}},
            {"ticker": "BBB", "verdict": "HOLD-FOR-CONDITIONS", "conviction": 4, "nominators": ["wyckoff"],
             "bear_case": "x", "dissent": [], "conditions": "needs momentum >= 75",
             "ledger_proposal": {"propose": True, "classification": "trigger_silent",
                                 "trigger": {"field": "sc_momentum", "op": ">=", "value": 75},
                                 "reason": "spring held; wants momentum confirmation"}},
            {"ticker": "CCC", "verdict": "PASS", "conviction": 1, "nominators": ["lynch"],
             "bear_case": "x", "dissent": []},                                   # not proposed
            {"ticker": "DDD", "verdict": "PASS", "conviction": 2, "nominators": ["thorp"],
             "bear_case": "x", "dissent": [],
             "ledger_proposal": {"propose": True, "classification": "trigger_silent",
                                 "reason": "no trigger stated"}},                # must be rejected
            {"ticker": "EEE", "verdict": "ADVANCE", "conviction": 5, "nominators": ["oneil"],
             "bear_case": "x", "dissent": [],
             "ledger_proposal": {"propose": True, "classification": "daily_reconsider",
                                 "reason": "already advancing"}},                # must be rejected
        ],
    }
    cpath = os.path.join(tmp, "committee.json")
    with open(cpath, "w") as fh:
        json.dump(committee, fh)

    class A:
        pass

    a = A(); a.committee = cpath; a.date = "2026-07-27"; a.session = "premarket_committee"
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        persist(a)
    res = json.loads(buf.getvalue())
    assert res["filed"] == ["AAA", "BBB"], "only valid non-ADVANCE proposals file: %s" % res["filed"]
    assert "CCC" not in res["filed"], "an unproposed name must NOT be filed (no blanket sweep)"
    rej = {r["ticker"] for r in res["rejected"]}
    assert rej == {"DDD", "EEE"}, "trigger_silent-without-trigger and ADVANCE must be rejected: %s" % rej

    # idempotence: same committee, same day -> extends, never duplicates
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        persist(a)
    res2 = json.loads(buf.getvalue())
    assert res2["filed"] == [] and set(res2["extended"]) == {"AAA", "BBB"}, "re-persist must extend, not duplicate"
    doc = load()
    assert len([r for r in doc["rows"] if r["ticker"] == "AAA"]) == 1, "no duplicate rows"

    # sweep: BBB's trigger fires at 78, AAA (daily_reconsider) is untouched
    export = {"date": "2026-07-28", "daily_list": [
        {"ticker": "BBB", "sc_momentum": 78}, {"ticker": "AAA", "sc_momentum": 40}]}
    epath = os.path.join(tmp, "export.json")
    with open(epath, "w") as fh:
        json.dump(export, fh)
    b = A(); b.date = "2026-07-28"; b.export = epath
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sweep(b)
    sres = json.loads(buf.getvalue())
    assert [f["ticker"] for f in sres["fired"]] == ["BBB"], "BBB must fire at 78 >= 75: %s" % sres["fired"]
    assert _row(load(), "AAA")["status"] == "active", "daily_reconsider is never fired by the sweep"

    # a missing field must NOT fire
    doc = load()
    r = _row(doc, "AAA")
    r["classification"] = "trigger_silent"
    r["trigger"] = {"field": "not_a_field", "op": ">=", "value": 1}
    save(doc, "2026-07-28")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sweep(b)
    sres2 = json.loads(buf.getvalue())
    assert sres2["fired"] == [] and "AAA" in sres2["not_evaluable"], "a missing field must never satisfy a trigger"

    # TTL expiry
    c = A(); c.date = "2026-09-30"; c.export = None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sweep(c)
    sres3 = json.loads(buf.getvalue())
    assert "AAA" in sres3["expired"], "TTL must expire a stale row: %s" % sres3

    print("pipeline_ledger selftest OK — proposals filed only when the committee asked, "
          "trigger_silent without a trigger rejected, ADVANCE rejected, re-persist idempotent, "
          "missing fields never fire, TTL expires.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Pipeline Ledger (D-83) — ideas that haven't fired yet")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("persist", help="file this session's committee ledger_proposals")
    p1.add_argument("--committee", required=True)
    p1.add_argument("--date")
    p1.add_argument("--session", default="premarket_committee")
    p1.set_defaults(fn=persist)

    p2 = sub.add_parser("sweep", help="expire stale rows; fire triggers against today's export")
    p2.add_argument("--date")
    p2.add_argument("--export")
    p2.set_defaults(fn=sweep)

    p3 = sub.add_parser("active", help="what is being watched right now")
    p3.add_argument("--classification", choices=["daily_reconsider", "trigger_silent"])
    p3.add_argument("--json", action="store_true")
    p3.set_defaults(fn=active)

    p4 = sub.add_parser("close", help="resolve a row (advanced into the plan / PM dropped it)")
    p4.add_argument("--ticker", required=True)
    p4.add_argument("--reason", required=True)
    p4.add_argument("--date")
    p4.set_defaults(fn=close)

    p5 = sub.add_parser("render", help="plain-text card for the PM")
    p5.add_argument("--date")
    p5.set_defaults(fn=render)

    p6 = sub.add_parser("selftest")
    p6.set_defaults(fn=selftest)

    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
