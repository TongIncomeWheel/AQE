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

WHICH PROCESS ARE YOU GATING? (`--for`, D-91)
  Premarket is TWO processes with DIFFERENT prerequisites, so one gate answer for
  both was wrong in a way that mattered:
    --for premarket_data   the cheap data half. Needs post-market only. It is the
                           process that FETCHES the export, so gating it on the
                           export was a deadlock — nothing could ever fetch it.
    --for premarket_build  the expensive judgement half. Needs post-market, today's
                           export on disk, AND an ok premarket_data stamp for today.
  The data half stamps itself with `stamp --phase premarket_data` exactly as
  post-market does, and a `fail` stamp there BLOCKS the swarm rather than looping it.

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
  python3 tools/phase_gate.py check --for premarket_data  [--date 2026-07-28] [--json]
  python3 tools/phase_gate.py check --for premarket_build [--date 2026-07-28] [--json]
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


# Which gates apply to which downstream phase (D-91). Premarket is two processes now — a cheap
# data half and an expensive judgement half — and they do NOT have the same prerequisites.
GATES_FOR = {
    # The CHEAP half is the process that fetches the export. Requiring the export to already be
    # on disk before firing it was a deadlock: the only session that downloads it is the one this
    # gate refused to start. Nothing had ever fired it, so nothing had ever been noticed.
    # Prerequisite is post-market alone.
    "premarket_data": {"post_market": True, "export": False, "requires_stamp": None},
    # The EXPENSIVE half runs only after the cheap half stamped ok. By then the export is on disk
    # AND pushed, so checking it here is a real check rather than a circular one — and it is worth
    # checking twice, because the expensive half runs in its OWN fresh checkout and a missing
    # push would otherwise be discovered twelve agent spawns too late.
    "premarket_build": {"post_market": True, "export": True, "requires_stamp": "premarket_data"},
}


def check(args):
    date = _today(args.date)
    export_path = args.export or EXPORT_PATH
    target = getattr(args, "for_phase", None) or "premarket_data"
    if target not in GATES_FOR:
        raise SystemExit("unknown --for phase %r; expected one of %s"
                         % (target, ", ".join(sorted(GATES_FOR))))
    gates = GATES_FOR[target]
    doc = _load()
    pm = doc["phases"].get("post_market")

    reasons = []
    verdict = READY

    # --- gate 1: post-market ran, and ran clean -------------------------------
    journal = (False, "not checked")
    if not gates["post_market"]:
        journal = (False, "not required for %s" % target)
    elif pm is None:
        verdict = NOT_READY
        reasons.append("no post_market stamp on record — post-market has not run yet")
        journal = (False, "no stamp")
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

    # --- gate 2b: the upstream half of premarket has stamped ------------------
    # Only the expensive half has an upstream half. Same grammar as post-market:
    # absent-or-yesterday is transient (the cheap half is still to run today), an
    # explicit failure is not (the cheap half tried and could not produce the data,
    # so spinning up the swarm would be spending the expensive session on nothing).
    need = gates["requires_stamp"]
    upstream = doc["phases"].get(need) if need else None
    if need:
        if upstream is None:
            verdict = max(verdict, NOT_READY)
            reasons.append("no %s stamp on record — the cheap data half has not run yet" % need)
        elif upstream.get("status") != "ok":
            verdict = BLOCKED
            reasons.append("%s stamped %s on %s: %s"
                           % (need, upstream.get("status"), upstream.get("run_date"),
                              upstream.get("note") or "no note"))
        elif upstream.get("run_date") != date:
            verdict = max(verdict, NOT_READY)
            reasons.append("last %s run was %s, expected %s"
                           % (need, upstream.get("run_date"), date))

    # --- gate 3: today's AQE export is published ------------------------------
    # Applied ONLY where it is a real check. For the cheap half it was a deadlock:
    # that process is the one that FETCHES the export, so gating its start on the
    # export already being on disk meant it could never start on a normal morning.
    if gates["export"]:
        eok, edate, enote = _export_ok(date, export_path)
        if not eok:
            # AQE is an external box on its own schedule; a late export is the normal
            # transient case, never a hard block.
            verdict = max(verdict, NOT_READY)
            reasons.append(enote)
    else:
        eok, edate = None, None
        enote = "not gated for %s — this is the process that fetches it" % target

    label = {READY: "READY", NOT_READY: "NOT_READY", BLOCKED: "BLOCKED"}[verdict]
    out = {
        "date": date,
        "for": target,
        "verdict": label,
        "exit_code": verdict,
        "post_market": pm,
        "upstream_phase": need,
        "upstream": upstream,
        "journal_ok": journal[0],
        "journal": journal[1],
        "export_ok": eok,
        "export_date": edate,
        "export": enote,
        "reasons": reasons,
        "action": {
            "READY": "fire %s" % target,
            "NOT_READY": "retry later within the self-heal budget; page only when it is spent",
            "BLOCKED": "page the PM now — do not fire %s" % target,
        }[label],
    }
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print("PHASE GATE %s (for %s) — %s" % (date, target, label))
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

    def run_check(date, for_phase="premarket_build"):
        a = A(); a.date = date; a.json = True; a.export = export_path; a.for_phase = for_phase
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = check(a)
        return code, json.loads(buf.getvalue())

    def stamp_data(date, status="ok"):
        s = A(); s.phase = "premarket_data"; s.status = status; s.date = date
        s.journal_date = None; s.note = None; s.run_at = None
        with contextlib.redirect_stdout(io.StringIO()):
            stamp(s)

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
    code, r = run_check("2026-07-28", "premarket_data")
    assert code == BLOCKED, "a failed post-market must block the cheap half too: %s" % r

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

    # 4b. THE DEADLOCK, broken (D-91). Same disk state, same moment — but the process being
    # gated is the one that DOWNLOADS the export, so its own gate must not demand it first.
    # Before this, every real morning sat at NOT_READY forever: nothing ever fetched the export
    # because the only session that fetches it was refused a start for not having fetched it.
    assert not os.path.exists(export_path), "precondition: no export on disk yet"
    code, r = run_check("2026-07-28", "premarket_data")
    assert code == READY, ("the cheap half must start with NO export on disk — it is the "
                           "process that fetches it: %s" % r)
    assert r["export_ok"] is None and "fetches it" in r["export"], r

    # 4c. ...and the expensive half must NOT start there, on the same state.
    code, r = run_check("2026-07-28")
    assert code == NOT_READY, "the expensive half must still wait for the data: %s" % r

    # 5. export dated yesterday -> still NOT_READY (staleness is not freshness)
    with open(export_path, "w") as fh:
        json.dump({"date": "2026-07-27", "daily_list": [{"ticker": "AAA"}]}, fh)
    code, r = run_check("2026-07-28")
    assert code == NOT_READY and not r["export_ok"], "a stale export must not pass: %s" % r

    # 6. export current — but the cheap half has not stamped, so the expensive half still waits.
    # This is the second, independent gate: the two halves run in SEPARATE fresh checkouts, so an
    # export sitting on this disk is not proof the data half finished and pushed.
    with open(export_path, "w") as fh:
        json.dump({"date": "2026-07-28", "daily_list": [{"ticker": "AAA"}]}, fh)
    code, r = run_check("2026-07-28")
    assert code == NOT_READY, "no premarket_data stamp must hold the swarm back: %s" % r
    assert any("cheap data half has not run" in x for x in r["reasons"]), r["reasons"]

    # 6b. cheap half stamped ok, today -> READY
    stamp_data("2026-07-28")
    code, r = run_check("2026-07-28")
    assert code == READY and r["verdict"] == "READY", r

    # 6c. cheap half stamped FAIL -> BLOCKED. It tried and could not produce the data; the
    # expensive session would be spent on nothing.
    stamp_data("2026-07-28", status="fail")
    code, r = run_check("2026-07-28")
    assert code == BLOCKED, "a failed data half must page, not retry the swarm: %s" % r
    stamp_data("2026-07-28")

    # 7. yesterday's stamp against today -> NOT_READY (today's run is still pending)
    code, r = run_check("2026-07-29")
    assert code == NOT_READY, "a stamp from a previous day must not green-light today: %s" % r

    # 7b. an unknown --for is a hard stop, never a silent default to the permissive gate
    try:
        run_check("2026-07-28", "premarket_everything")
        raise AssertionError("an unknown phase must not be accepted")
    except SystemExit:
        pass

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
          "all current = READY; and the two premarket halves gate DIFFERENTLY — the cheap data "
          "half starts with no export on disk (deadlock broken), the expensive half waits for "
          "both the export and the data half's ok stamp.")
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

    p2 = sub.add_parser("check", help="Phase 0's gate: is it safe to fire the next process?")
    p2.add_argument("--date")
    p2.add_argument("--export")
    p2.add_argument("--for", dest="for_phase", default="premarket_data",
                    choices=sorted(GATES_FOR),
                    help="which downstream process you are about to fire — the gates differ "
                         "(premarket_data fetches the export, so it is NOT gated on it; "
                         "premarket_build is gated on both the export and a premarket_data stamp)")
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
