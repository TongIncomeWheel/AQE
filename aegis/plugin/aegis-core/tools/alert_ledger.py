#!/usr/bin/env python3
"""
alert_ledger.py — read + route the AQE intraday alert ledger.

THE ONE READER. Replaces tools/alert_inbox.py (retired 2026-08-06): AQE never
emitted the inbox.jsonl shape and never will. The real artifact is a single
JSON object, aqe_alert_ledger.json, written by the AQE alert engine to the
Drive "AQE" folder and mirrored to data/alerts/DATE/aqe_alert_ledger.json.
Contract: contracts/alert_ledger.schema.json.

Three properties of the real file that collapse work Aegis used to plan for:

  1. PRE-ENRICHED AT SOURCE. Every entry already carries scores, levels, qs,
     and intraday context. There is NO join back to the daily export.
  2. SELF-SCOPING. `lists` (on_longlist / on_elder / on_qs / held) is stamped
     at source. Membership is a flag read, NOT a re-derivation from
     alert_list.json.
  3. SELF-DOCUMENTING. The file carries its own `events` map. That map is
     authoritative; this tool validates against it rather than inventing a
     vocabulary.

Dedupe is on (ticker, event, time_et) — no cursor file, no state file. The
ledger is a rolling 30-day window sorted newest first, so a sweep re-reads it
whole every cycle and is idempotent by construction.

Deterministic (law 4). No models, no network, no judgment. It sorts alerts
into routes; the pod and the PM do the deciding.

Usage
-----
  python3 tools/alert_ledger.py summary  --file <ledger.json> [--date DATE]
  python3 tools/alert_ledger.py sweep    --file <ledger.json> [--date DATE]
                                         [--since HH:MM] [--json]
  python3 tools/alert_ledger.py stamp    --file <ledger.json>
                                         --ticker T --event E --time HH:MM
                                         --outcome '{"route":"podded",...}'

Exit codes: 0 ok · 2 file/parse problem · 3 nothing for the requested date.
"""

import argparse
import json
import os
import sys
from collections import Counter, OrderedDict

# ---------------------------------------------------------------------------
# The six real events. Kept here ONLY as a cross-check against the file's own
# `events` map — the file wins, this list is the tripwire that tells us AQE
# changed its vocabulary without telling us.
# ---------------------------------------------------------------------------
KNOWN_EVENTS = {
    "BOS",            # closed above last confirmed pivot high
    "NEAR_BREAKOUT",  # climbing into that level from below
    "NEAR_TARGET",    # approaching TP1 from below
    "NEAR_STOP",      # within 5% above the stop / live SL
    "MOVE",           # +/-2% vs last close — REFERENCE ONLY, no entry claim
    "VETO_HELD",      # a QS veto struck a name in the held book
}

# Routes, in page-first order.
PAGE = "page"            # held-book risk — page the PM now, no committee
MANAGE = "manage"        # held-book target — trim-or-run management question
POD = "pod"              # opportunity — wake the Intraday Review Pod
LOG = "log"              # visible, not actioned
DROP = "drop"            # reference only, carries no entry claim

ROUTE_ORDER = [PAGE, MANAGE, POD, LOG, DROP]


def load(path):
    if not os.path.exists(path):
        sys.stderr.write("alert_ledger: no file at %s\n" % path)
        sys.exit(2)
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("alert_ledger: cannot parse %s (%s)\n" % (path, exc))
        sys.exit(2)
    if not isinstance(doc, dict) or "entries" not in doc:
        sys.stderr.write("alert_ledger: %s is not an alert ledger "
                         "(no `entries`)\n" % path)
        sys.exit(2)
    return doc


def vocabulary_check(doc):
    """The file defines its own events. Report drift, never silently adapt."""
    declared = set((doc.get("events") or {}).keys())
    seen = set(e.get("event") for e in doc.get("entries") or [])
    seen.discard(None)
    return {
        "declared": sorted(declared),
        "unknown_to_aegis": sorted((declared | seen) - KNOWN_EVENTS),
        "used_but_undeclared": sorted(seen - declared) if declared else [],
    }


def entries_for(doc, date=None, since=None):
    rows = [e for e in (doc.get("entries") or []) if isinstance(e, dict)]
    if date:
        rows = [e for e in rows if e.get("date") == date]
    if since:
        rows = [e for e in rows if (e.get("time_et") or "") >= since]
    return rows


def dedupe(rows):
    """Key = (ticker, event, time_et). Newest first, so first wins."""
    seen = set()
    out = []
    for e in rows:
        key = (e.get("ticker"), e.get("event"), e.get("time_et"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def on_a_list(entry):
    """Membership is READ, never re-derived."""
    lists = entry.get("lists") or {}
    return bool(lists.get("on_longlist") or lists.get("on_elder")
                or lists.get("on_qs"))


def route(entry):
    """
    The routing table, against the six real events.

    MOVE                        -> drop. The file itself says "no entry claim".
    NEAR_STOP / VETO_HELD, held -> page immediately, no committee.
    NEAR_TARGET, held           -> trim-or-run management question.
    BOS / NEAR_BREAKOUT,
      on a list, bracket valid  -> wake the Intraday Review Pod.
    everything else             -> logged, not podded (kept visible).
    """
    ev = entry.get("event")
    held = bool(entry.get("is_held") or (entry.get("lists") or {}).get("held"))
    bracket_valid = bool((entry.get("levels") or {}).get("bracket_valid"))

    if ev == "MOVE":
        return DROP, "reference only — the ledger states no entry claim"

    if ev in ("NEAR_STOP", "VETO_HELD"):
        if held:
            return PAGE, ("held book at risk (%s) — page the PM, no committee"
                          % ev)
        return LOG, "%s on a name we do not hold" % ev

    if ev == "NEAR_TARGET":
        if held:
            return MANAGE, "held name approaching TP1 — trim or run"
        return LOG, "NEAR_TARGET on a name we do not hold"

    if ev in ("BOS", "NEAR_BREAKOUT"):
        if not on_a_list(entry):
            return LOG, "off every list — visible, not podded"
        if not bracket_valid:
            return LOG, "no valid bracket — cannot size, so cannot pod"
        return POD, "%s on a listed name with a workable bracket" % ev

    return LOG, "event %r not in the routing table" % ev


def sweep(doc, date=None, since=None):
    rows = dedupe(entries_for(doc, date=date, since=since))
    routed = OrderedDict((r, []) for r in ROUTE_ORDER)
    for e in rows:
        r, why = route(e)
        routed[r].append({
            "ticker": e.get("ticker"),
            "event": e.get("event"),
            "time_et": e.get("time_et"),
            "date": e.get("date"),
            "live_px": e.get("live_px"),
            "level_price": e.get("level_price"),
            "is_held": bool(e.get("is_held")),
            "lists": e.get("lists") or {},
            "bracket_stop": (e.get("levels") or {}).get("bracket_stop"),
            "tp1": (e.get("levels") or {}).get("tp1"),
            "bracket_valid": bool((e.get("levels") or {}).get("bracket_valid")),
            "sc_momentum": (e.get("scores") or {}).get("sc_momentum"),
            "mp_state": (e.get("scores") or {}).get("mp_state"),
            "structure_shift": e.get("structure_shift"),
            "qs": e.get("qs"),
            "label": e.get("label"),
            "note": e.get("note"),
            "why": why,
        })
    return rows, routed


def cmd_summary(args):
    doc = load(args.file)
    rows = entries_for(doc, date=args.date)
    if not rows:
        sys.stderr.write("alert_ledger: no entries for %s\n"
                         % (args.date or "any date"))
        sys.exit(3)
    out = {
        "updated": doc.get("updated"),
        "retention_days": doc.get("retention_days"),
        "entries_total": len(doc.get("entries") or []),
        "entries_scoped": len(rows),
        "dates": sorted(set(e.get("date") for e in rows)),
        "write_times_et": sorted(set(e.get("time_et") for e in rows)),
        "events": dict(Counter(e.get("event") for e in rows)),
        "sessions": dict(Counter(e.get("session") for e in rows)),
        "held": sum(1 for e in rows if e.get("is_held")),
        "on_longlist": sum(1 for e in rows
                           if (e.get("lists") or {}).get("on_longlist")),
        "on_elder": sum(1 for e in rows
                        if (e.get("lists") or {}).get("on_elder")),
        "on_qs": sum(1 for e in rows if (e.get("lists") or {}).get("on_qs")),
        "bracket_valid": sum(1 for e in rows
                             if (e.get("levels") or {}).get("bracket_valid")),
        "outcome_stamped": sum(1 for e in rows
                               if e.get("outcome") is not None),
        "vocabulary": vocabulary_check(doc),
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_sweep(args):
    doc = load(args.file)
    rows, routed = sweep(doc, date=args.date, since=args.since)
    if not rows:
        sys.stderr.write("alert_ledger: no entries for %s\n"
                         % (args.date or "any date"))
        sys.exit(3)

    payload = {
        "updated": doc.get("updated"),
        "scoped_date": args.date,
        "since_et": args.since,
        "read": len(rows),
        "counts": {r: len(v) for r, v in routed.items()},
        "routes": routed,
        "vocabulary": vocabulary_check(doc),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print("AQE alert ledger — updated %s" % doc.get("updated"))
    print("read %d alert(s)%s%s"
          % (len(rows),
             " for %s" % args.date if args.date else "",
             " from %s ET" % args.since if args.since else ""))
    drift = payload["vocabulary"]["unknown_to_aegis"]
    if drift:
        print("!! vocabulary drift — AQE emits events Aegis does not know: %s"
              % ", ".join(drift))
    print("")
    for r in ROUTE_ORDER:
        items = routed[r]
        print("%-7s %d" % (r.upper(), len(items)))
        for it in items:
            print("    %-6s %-14s %s  %s"
                  % (it["ticker"], it["event"], it["time_et"], it["why"]))
    return 0


def cmd_stamp(args):
    """
    Close the loop. Every entry ships with outcome=null; Aegis stamps what the
    alert actually became so the day is auditable. AQE never writes this field,
    so stamping it can never collide with the source.
    """
    doc = load(args.file)
    try:
        outcome = json.loads(args.outcome)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("alert_ledger: --outcome must be JSON (%s)\n" % exc)
        sys.exit(2)

    hits = 0
    for e in doc.get("entries") or []:
        if (e.get("ticker") == args.ticker
                and e.get("event") == args.event
                and e.get("time_et") == args.time):
            e["outcome"] = outcome
            hits += 1
    if not hits:
        sys.stderr.write("alert_ledger: no entry matches %s/%s/%s\n"
                         % (args.ticker, args.event, args.time))
        sys.exit(3)

    tmp = args.file + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=1)
    os.replace(tmp, args.file)
    print("stamped %d entr%s" % (hits, "y" if hits == 1 else "ies"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summary", help="profile the ledger")
    s.add_argument("--file", required=True)
    s.add_argument("--date")
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser("sweep", help="route the ledger's alerts")
    s.add_argument("--file", required=True)
    s.add_argument("--date")
    s.add_argument("--since", help="ET HH:MM — only alerts at/after this time")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_sweep)

    s = sub.add_parser("stamp", help="write back what an alert became")
    s.add_argument("--file", required=True)
    s.add_argument("--ticker", required=True)
    s.add_argument("--event", required=True)
    s.add_argument("--time", required=True, help="time_et HH:MM")
    s.add_argument("--outcome", required=True, help="JSON object")
    s.set_defaults(func=cmd_stamp)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
