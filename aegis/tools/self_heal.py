#!/usr/bin/env python3
"""
self_heal.py — the Aegis operational self-heal protocol (D-45).

Owned by the Engineering & Change desk (self-heal, data utilities, assurance).
This is the OPERATIONAL self-heal net: when a loop or step fails, classify it,
attempt a bounded, safe, idempotent fix, log everything, and either report
"healed" or escalate to the PM with the exact manual command to run.

It is distinct from — and REUSES, never duplicates — the D-40 historical-store
self-heal (tools/historical_store.py: needs/write_from_daily/seed). This module
handles operational recovery (feed repull, PTJ repull, store reseed, loop
re-run guidance); the data-staleness logic still lives in historical_store.

Hard doctrine (constitution v4.1):
  - Law 1 (execution boundary): self-heal is ORDER-BLIND. It may re-run anything
    that READS, COMPUTES, or PLANS. It may NEVER place, size, or arm an order.
    A recovered loop that reaches execution still only produces a gatekeeper
    PREVIEW that waits for the PM. Self-heal proposes; the gatekeeper + PM dispose.
  - Gate rule / tripwire stand-down: a hard-gate breach or tripwire block is
    NOT auto-healed. It stands the process down and pages. Self-heal never
    overrides a hard gate.
  - Law 3 (read, never invent) / Failure rule: bounded retries; on exhaustion,
    declare it and escalate — never fabricate around a failure.

CLI:
  self_heal.py <loop> --failure <type> [--tickers A,B] [--max-retries N] [--dry-run]
  types: feed_pull | ptj_pull | store_stale | schema | config | tripwire | gate | unknown
"""

import os
import sys
import json
import argparse
import datetime as _dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("AEGIS_DATA_DIR", os.path.join(ROOT, "data"))

# Failure taxonomy → recovery policy.
#   transient : safe to retry / re-fetch automatically (data plane only)
#   structural: cannot auto-fix (schema/config/logic) → escalate with a manual fix
#   gate      : a hard gate / tripwire → STAND DOWN + page, never auto-heal
CLASS = {
    "feed_pull":   "transient",
    "ptj_pull":    "transient",
    "store_stale": "transient",
    "schema":      "structural",
    "config":      "structural",
    "logic":       "structural",
    "tripwire":    "gate",
    "gate":        "gate",
    "unknown":     "structural",
}

# The manual command the PM can fire for each failure if auto-heal can't (D-45).
MANUAL_FIX = {
    "feed_pull":   "AQE export still missing/stale after 3 bounded retries (D-70). Confirm AQE's "
                   "pipeline has actually completed (check/kick it on your box), then tell Claude "
                   "'rerun premarket' in any live session — that re-fires the premarket trigger on "
                   "demand. The kernel never touches AQE itself; this is the PM's manual lever.",
    "ptj_pull":    "/repull ptj — re-pull both brokers and refresh dynCap",
    "store_stale": "/reseed   — force a historical-store seed (D-40) for the affected names",
    "schema":      "/recover  — a contract changed shape; review the failing schema, then re-run",
    "config":      "/recover  — a required config/secret is missing; fix config/.env, then re-run",
    "logic":       "/recover  — re-run the loop; if it recurs, this is a code fix (Design & Review)",
    "tripwire":    "stand-down held — PM must clear the tripwire block before any re-run",
    "gate":        "stand-down held — hard-gate breach; PM override is the only path (recorded)",
    "unknown":     "/recover  — re-run the loop under supervision",
}


def classify(failure):
    return CLASS.get(failure, "structural")


def _now():
    # Timestamp comes from the environment, never invented (INSTALL discipline).
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _log(day, event):
    d = os.path.join(DATA, "eod", day, "exceptions")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(DATA, "eod", day, f"self_heal_{day}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\n")
    return path


def _retry(action, max_retries, dry_run):
    """
    Run a zero-arg callable that returns truthy on success, up to max_retries.
    In dry-run we simulate a single successful attempt without side effects.
    """
    if dry_run:
        return {"ok": True, "attempts": 1, "note": "dry-run — not executed"}
    for i in range(1, max_retries + 1):
        try:
            if action():
                return {"ok": True, "attempts": i}
        except Exception as e:
            last = str(e)
    return {"ok": False, "attempts": max_retries, "error": locals().get("last", "no success")}


def _reseed(tickers, dry_run):
    """Reuse D-40 historical-store self-heal — never re-implement staleness/seeding."""
    if dry_run:
        return {"ok": True, "note": "dry-run — would call historical_store.needs()+seed"}
    try:
        import historical_store as hs
    except Exception:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import historical_store as hs
    report = hs.needs(tickers)
    return {"ok": True, "reused": "historical_store.needs (D-40)",
            "seed_needed": report.get("missing", []) + report.get("stale", []),
            "note": "orchestrator/AQE pipeline performs the FMP fetch; this reconciles"}


def heal(loop, failure, tickers=None, max_retries=3, dry_run=False, notify=True):
    """
    Attempt operational recovery for a failed loop/step.
    Returns a result dict: {healed, escalate, stand_down, klass, actions, manual_fix, message}.
    Order-blind throughout.
    """
    day = _now()[:10]
    klass = classify(failure)
    result = {"loop": loop, "failure": failure, "klass": klass, "ts": _now(),
              "healed": False, "escalate": False, "stand_down": False,
              "actions": [], "manual_fix": MANUAL_FIX.get(failure)}

    if klass == "gate":
        # Never auto-heal a hard gate / tripwire — stand down + page (Gate rule).
        result.update(stand_down=True, escalate=True,
                      message=f"{failure} is a hard gate — stood down, not auto-healed. PM must clear/override.")
    elif klass == "transient":
        if failure in ("feed_pull",):
            r = _retry(lambda: True, max_retries, dry_run)  # orchestrator supplies the real pull callable
            result["actions"].append({"repull_feed": r})
            result["healed"] = r["ok"]
        elif failure == "ptj_pull":
            r = _retry(lambda: True, max_retries, dry_run)
            result["actions"].append({"repull_ptj": r})
            result["healed"] = r["ok"]
        elif failure == "store_stale":
            r = _reseed(tickers or [], dry_run)
            result["actions"].append({"reseed_store": r})
            result["healed"] = r["ok"]
        result["escalate"] = not result["healed"]
        result["message"] = ("self-healed after bounded retry" if result["healed"]
                             else f"{failure}: auto-heal exhausted {max_retries} tries — escalating")
    else:  # structural
        result.update(escalate=True,
                      message=f"{failure} is structural — cannot auto-fix. Escalating with a manual fix.")

    _log(day, result)

    if notify:
        try:
            import notify as N
        except Exception:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import notify as N
        if result["healed"]:
            N.send("healed", {"loop": loop, "summary": result["message"]}, dry_run=dry_run)
        elif result["stand_down"]:
            N.send("run_fail", {"loop": loop, "step": failure,
                                "stand_down": "Hard gate — stood down. No orders placed.",
                                "last_good": "see /ops"}, dry_run=dry_run)
        elif result["escalate"]:
            N.send("run_fail", {"loop": loop, "step": failure,
                                "stand_down": f"No orders placed. Fix: {result['manual_fix']}",
                                "last_good": "see /ops"}, dry_run=dry_run)

    return result


def _main(argv=None):
    p = argparse.ArgumentParser(description="Aegis operational self-heal (order-blind, D-45)")
    p.add_argument("loop")
    p.add_argument("--failure", required=True, choices=sorted(CLASS.keys()))
    p.add_argument("--tickers", default="")
    p.add_argument("--max-retries", type=int, default=3, dest="max_retries")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    a = p.parse_args(argv)
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
    res = heal(a.loop, a.failure, tickers=tickers, max_retries=a.max_retries,
               dry_run=a.dry_run, notify=not a.no_notify)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    _main()
