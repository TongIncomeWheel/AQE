#!/usr/bin/env python3
"""
phase_gate.py — the pre-requisite gate between phases (D-83).

THE PROBLEM IT SOLVES
  Premarket's expensive half (universe -> 11 voices -> committee) depends on
  post-market having finished: the journal has to be current or every size, every
  dynCap number and every held-book read is computed off stale truth. Today that
  dependency is a CLOCK GUESS — premarket is scheduled a few hours after
  post-market and its step-1 freshness check runs INSIDE the same session that
  goes on to do the full build. So a stale-data morning still pays to spin up the
  big session before halting.

  This tool splits the check out so it can run FIRST, on its own, for almost
  nothing: two deterministic file reads, no models, no network, no swarm.

TWO COMMANDS, TWO OWNERS
  post-market calls `stamp`  — "I finished, here is the session I journaled."
  Phase 0    calls `check`   — "is it safe to fire the expensive build yet?"

EXIT CODES (this is the whole interface — the Phase 0 scheduled task branches on it)
  0  READY      -> fire the premarket build
  1  NOT_READY  -> a thing that fixes itself with time (post-market hasn't run yet,
                   AQE export not published yet). Retry later; page only after the
                   retry budget is spent.
  2  BLOCKED    -> post-market ran and FAILED, or the journal it claims is missing.
                   Time will not fix this. Page now; do not fire the build.

Deterministic (law 4). Reads only; writes only its own stamp file. Places nothing
(constitution law 1).

Usage:
  python3 tools/phase_gate.py stamp --phase post_market --status ok \\
        --journal-date 2026-07-27 [--note "..."]
  python3 tools/phase_gate.py check [--date 2026-07-28] [--json]
  python3 tools/phase_gate.py show
  python3 tools/phase_gate.py selftest
"""
import argparse
import json
import os
import sys
import datetime as _dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.environ.get(
    "AEGIS_PHASE_STATE",
    os.path.join(ROOT, "data", "persistent", "phase_state.json"),
)
JOURNAL_DIR = os.path.join(ROOT, "data", "journal")
EXPORT_PATH = os.environ.get("AEGIS_AQE_EXPORT", os.path.join(ROOT, "output", "aqe_daily_export.json"))

X_VERSION = "1.0.0"

READY, NOT_READY, BLOCKED = 0, 1, 2


def _today(explicit=None):
    return explicit or _dt.date.today().isoformat()


def _load():
    if not os.path.exists(STATE):
        return {"x_version": X_VERSION, "phases": {}}
    try:
        with open(STATE) as fh:
            doc = json.load(fh)
    except Exception:
        return {"x_version": X_VERSION, "phases": {}}
    doc.setdefault("phases", {})
    return doc


def _save(doc):
    doc["x_version"] = X_VERSION
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")


# --------------------------------------------------------------------------- stamp
def stamp(args):
    """Called by post-market as its LAST act. Records what actually happened —
    including a failure. A stamp is a fact, not a claim of success: status=fail is
    a legitimate, useful stamp and is exactly what turns Phase 0's answer from
    'keep waiting' into 'page the PM now'."""
    doc = _load()
    run_at = args.run_at or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
    doc["phases"][args.phase] = {
        "status": args.status,
        "run_date": _today(args.date),
        "run_at_utc": run_at,
        "journal_date": args.journal_date,
        "note": args.note,
    }
    _save(doc)
    print(json.dumps(doc["phases"][args.phase], indent=1))
    return 0


# --------------------------------------------------------------------------- check
def _journal_ok(journal_date):
    """Does the journal post-market claims to have written actually exist and parse?
    Trusting the stamp alone would repeat the D-69 mistake — auditing the kernel's
    belief about the world instead of the world."""
    if not journal_date:
        return False, "stamp carries no journal_date"
    path = os.path.join(JOURNAL_DIR, "aegis_journal_%s.json" % journal_date)
    if not os.path.exists(path):
        return False, "journal file missing: %s" % os.path.relpath(path, ROOT)
    try:
        with open(path) as fh:
            j = json.load(fh)
    except Exception as e:
        return False, "journal unreadable (%s): %s" % (os.path.relpath(path, ROOT), e)
    if not j:
        return False, "journal is empty: %s" % os.path.relpath(path, ROOT)
    return True, os.path.relpath(path, ROOT)


def _export_ok(date, path):
    if not os.path.exists(path):
        return False, None, "AQE export not found at %s" % os.path.relpath(path, ROOT)
    try:
        with open(path) as fh:
            ex = json.load(fh)
    except Exception as e:
        return False, None, "AQE export unreadable: %s" % e
    edate = ex.get("date")
    n = len(ex.get("daily_list", []) or [])
    if edate != date:
        return False, edate, "AQE export is dated %s, expected %s" % (edate, date)
    if n == 0:
        return False, edate, "AQE export for %s carries an empty daily_list" % edate
    return True, edate, "%d names" % n


def check(args):
    date = _today(args.date)
    export_path = args.export or EXPORT_PATH
    doc = _load()
    pm = doc["phases"].get("post_market")

    reasons = []
    verdict = READY

    # --- gate 1: post-market ran, and ran clean -------------------------------
    if pm is None:
        verdict = NOT_READY
        reasons.append("no post_market stamp on record — post-market has not run yet")
        journal = (False, "not checked")
    else:
        if pm.get("status") != "ok":
            verdict = BLOCKED
            reasons.append("post_market stamped %s on %s: %s"
                           % (pm.get("status"), pm.get("run_date"), pm.get("note") or "no note"))
        elif pm.get("run_date") != date:
            # Ran, but not for today. Time can still fix this (today's run is pending).
            verdict = max(verdict, NOT_READY)
            reasons.append("last post_market run was %s, expected %s" % (pm.get("run_date"), date))
        # --- gate 2: the journal it claims actually exists ---------------------
        jok, jnote = _journal_ok(pm.get("journal_date"))
        journal = (jok, jnote)
        if not jok:
            # post-market said ok but the artifact is not there — no amount of
            # waiting fixes that.
            verdict = BLOCKED
            reasons.append(jnote)
    if pm is None:
        journal = (False, "no stamp")

    # --- gate 3: today's AQE export is published ------------------------------
    eok, edate, enote = _export_ok(date, export_path)
    if not eok:
        # AQE is an external box on its own schedule; a late export is the normal
        # transient case, never a hard block.
        verdict = max(verdict, NOT_READY)
        reasons.append(enote)

    label = {READY: "READY", NOT_READY: "NOT_READY", BLOCKED: "BLOCKED"}[verdict]
    out = {
        "date": date,
        "verdict": label,
        "exit_code": verdict,
        "post_market": pm,
        "journal_ok": journal[0],
        "journal": journal[1],
        "export_ok": eok,
        "export_date": edate,
        "export": enote,
        "reasons": reasons,
        "action": {
            "READY": "fire the premarket build",
            "NOT_READY": "retry later within the self-heal budget; page only when it is spent",
            "BLOCKED": "page the PM now — do not fire the build",
        }[label],
    }
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print("PHASE GATE %s — %s" % (date, label))
        for r in reasons:
            print("  - %s" % r)
        if not reasons:
            print("  journal %s | export %s" % (journal[1], enote))
        print("  -> %s" % out["action"])
    return verdict


def claim(args):
    """Exactly-once latch, so Phase 0 can be scheduled to fire REPEATEDLY (every N
    minutes across a morning window) without ever firing the expensive build twice.

    The first claim on a given date wins (exit 0); every later claim that day loses
    (exit 1). Repeat-firing is what makes the retry behaviour work without the task
    having to reschedule itself — a fresh scheduled session has no memory, so the
    latch has to live on disk, not in the session.

    `--release` clears the claim (for /recover: a deliberate manual re-run)."""
    date = _today(args.date)
    doc = _load()
    claims = doc.setdefault("claims", {})
    held = claims.get(args.phase)
    if args.release:
        claims.pop(args.phase, None)
        _save(doc)
        print(json.dumps({"phase": args.phase, "claim": "released", "was": held}))
        return 0
    if held and held.get("date") == date:
        print(json.dumps({"phase": args.phase, "claim": "lost",
                          "already_claimed_at": held.get("at_utc"),
                          "note": "already fired today — do nothing"}))
        return 1
    claims[args.phase] = {"date": date,
                          "at_utc": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()}
    _save(doc)
    print(json.dumps({"phase": args.phase, "claim": "won", "date": date,
                      "note": "you own today's run — proceed"}))
    return 0


def show(args):
    print(json.dumps(_load(), indent=1))
    return 0


# --------------------------------------------------------------------------- selftest
def selftest(args):
    import tempfile, io, contextlib
    global STATE, JOURNAL_DIR
    tmp = tempfile.mkdtemp()
    STATE = os.path.join(tmp, "phase_state.json")
    JOURNAL_DIR = os.path.join(tmp, "journal")
    os.makedirs(JOURNAL_DIR)
    export_path = os.path.join(tmp, "export.json")

    class A:
        pass

    def run_check(date):
        a = A(); a.date = date; a.json = True; a.export = export_path
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = check(a)
        return code, json.loads(buf.getvalue())

    # 1. nothing at all -> NOT_READY (post-market simply hasn't run)
    code, r = run_check("2026-07-28")
    assert code == NOT_READY and r["verdict"] == "NOT_READY", r
    assert any("has not run" in x for x in r["reasons"]), r["reasons"]

    # 2. post-market FAILED -> BLOCKED, not "wait longer"
    s = A(); s.phase = "post_market"; s.status = "fail"; s.date = "2026-07-28"
    s.journal_date = "2026-07-27"; s.note = "both broker pulls down"; s.run_at = None
    with contextlib.redirect_stdout(io.StringIO()):
        stamp(s)
    code, r = run_check("2026-07-28")
    assert code == BLOCKED, "a failed post-market must BLOCK, not retry: %s" % r

    # 3. post-market ok but the journal it claims is missing -> BLOCKED
    s.status = "ok"; s.note = None
    with contextlib.redirect_stdout(io.StringIO()):
        stamp(s)
    code, r = run_check("2026-07-28")
    assert code == BLOCKED and not r["journal_ok"], "a claimed-but-absent journal must BLOCK: %s" % r

    # 4. journal present, export missing -> NOT_READY (AQE is external and often late)
    with open(os.path.join(JOURNAL_DIR, "aegis_journal_2026-07-27.json"), "w") as fh:
        json.dump({"date": "2026-07-27", "dyncap_usd": 1}, fh)
    code, r = run_check("2026-07-28")
    assert code == NOT_READY and r["journal_ok"], "missing export is transient: %s" % r

    # 5. export dated yesterday -> still NOT_READY (staleness is not freshness)
    with open(export_path, "w") as fh:
        json.dump({"date": "2026-07-27", "daily_list": [{"ticker": "AAA"}]}, fh)
    code, r = run_check("2026-07-28")
    assert code == NOT_READY and not r["export_ok"], "a stale export must not pass: %s" % r

    # 6. everything current -> READY
    with open(export_path, "w") as fh:
        json.dump({"date": "2026-07-28", "daily_list": [{"ticker": "AAA"}]}, fh)
    code, r = run_check("2026-07-28")
    assert code == READY and r["verdict"] == "READY", r

    # 7. yesterday's stamp against today -> NOT_READY (today's run is still pending)
    code, r = run_check("2026-07-29")
    assert code == NOT_READY, "a stamp from a previous day must not green-light today: %s" % r

    # 8. the claim latch: first firing of the day wins, every later one loses
    def run_claim(date, release=False):
        c = A(); c.phase = "premarket_build"; c.date = date; c.release = release
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = claim(c)
        return code, json.loads(buf.getvalue())

    code, r = run_claim("2026-07-28")
    assert code == 0 and r["claim"] == "won", r
    code, r = run_claim("2026-07-28")
    assert code == 1 and r["claim"] == "lost", "a repeating Phase 0 must never double-fire the build: %s" % r
    code, r = run_claim("2026-07-29")
    assert code == 0 and r["claim"] == "won", "a new day is a new claim: %s" % r
    run_claim("2026-07-29", release=True)
    code, r = run_claim("2026-07-29")
    assert code == 0 and r["claim"] == "won", "release must allow a deliberate manual re-run: %s" % r

    print("phase_gate selftest OK — no stamp/stale stamp = NOT_READY (retry), "
          "failed post-market or missing journal = BLOCKED (page), late or stale export = NOT_READY, "
          "all current = READY.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Phase pre-requisite gate (D-83)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("stamp", help="record that a phase finished (post-market's last act)")
    p1.add_argument("--phase", default="post_market")
    p1.add_argument("--status", required=True, choices=["ok", "fail", "partial"])
    p1.add_argument("--journal-date", dest="journal_date", help="the session date the journal covers")
    p1.add_argument("--date", help="the calendar day the phase RAN (default today)")
    p1.add_argument("--note")
    p1.add_argument("--run-at", dest="run_at")
    p1.set_defaults(fn=stamp)

    p2 = sub.add_parser("check", help="Phase 0's gate: is it safe to fire the premarket build?")
    p2.add_argument("--date")
    p2.add_argument("--export")
    p2.add_argument("--json", action="store_true")
    p2.set_defaults(fn=check)

    p3 = sub.add_parser("claim", help="exactly-once latch so a repeating Phase 0 never double-fires the build")
    p3.add_argument("--phase", default="premarket_build")
    p3.add_argument("--date")
    p3.add_argument("--release", action="store_true", help="clear the claim (deliberate manual re-run)")
    p3.set_defaults(fn=claim)

    p3b = sub.add_parser("show", help="dump the raw state file")
    p3b.set_defaults(fn=show)

    p4 = sub.add_parser("selftest")
    p4.set_defaults(fn=selftest)

    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
