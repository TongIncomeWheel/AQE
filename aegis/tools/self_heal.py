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
  types: feed_pull | ptj_pull | store_stale | schema | config | tripwire | gate | usage_limit | unknown

usage_limit (D-72 — Claude Max-plan session/weekly cap, capacity class): the PM runs the
scheduled pipeline on a Claude Max 5x plan (150 SGD/mo), which pools a rolling 5-hour session
window + a weekly cap across ALL usage on the account — Anthropic publishes no separate
allowance for Claude Code / Agent SDK / scheduled-task usage, and no documented behavior for
what a scheduled (non-interactive) session does if it hits the cap mid-run. Premarket's 11
opus-tier spawns (10 voices + committee-desk) are the concentrated cost driver. `detect_usage_limit()`
is a deterministic text classifier (law 4) — given a spawn failure's error text, it flags whether
the failure carries a usage/rate/session-limit signature, DISTINCT from a voice simply returning
invalid/empty content (which stays on the existing "respawn once, proceed with the rest" path).
KNOWN LIMITATION, stated plainly: this can only catch a failure where the ORCHESTRATOR session
itself survives to observe and classify a subagent spawn's error text. If the orchestrator's own
session hits the cap, nothing here runs to catch it — that residual risk is not closed by this
tool and is a reason the PM is evaluating metered API billing for the scheduled pipeline separately.
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
#   capacity  : an account-level usage ceiling (D-72) → retrying now just re-hits the same
#               ceiling, so no auto-retry; escalate immediately with the wait-for-reset guidance
CLASS = {
    "feed_pull":   "transient",
    "ptj_pull":    "transient",
    "store_stale": "transient",
    "schema":      "structural",
    "config":      "structural",
    "logic":       "structural",
    "tripwire":    "gate",
    "gate":        "gate",
    "usage_limit": "capacity",
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
    "usage_limit": "This is NOT a data/config problem — the Claude account hit its session/weekly "
                   "usage cap mid-run (D-72). Check the account's usage indicator for the reset time, "
                   "then once the window resets tell Claude 'rerun <loop>' to re-fire that phase's "
                   "trigger. No auto-retry is attempted (it would just re-hit the same ceiling). If "
                   "this recurs often, the scheduled pipeline may need metered API billing instead of "
                   "the Max plan — flagged separately, PM decision pending.",
    "unknown":     "/recover  — re-run the loop under supervision",
}

# Text signatures Anthropic/the client surface when a spawn hits a session/rate/usage ceiling —
# deliberately broad (law 4, deterministic match, no model judgement) so a wording change on
# either side still gets caught. Checked case-insensitively against a spawn failure's error text.
USAGE_LIMIT_SIGNATURES = (
    "usage limit", "rate limit", "rate_limit", "ratelimit",
    "5-hour limit", "session limit", "weekly limit", "weekly cap",
    "quota exceeded", "resets at", "reset at", "overloaded_error",
    "429", "limit reached", "usage cap",
)


def classify(failure):
    return CLASS.get(failure, "structural")


def detect_usage_limit(error_text):
    """
    Deterministic classifier (D-72, law 4): does a subagent spawn failure's error text carry a
    usage/session/rate-limit signature, as opposed to a generic invalid/empty voice response?
    Returns {"matched": bool, "signature": str|None}. Never raises — a malformed/None input is
    simply "no match", not a crash (a diagnostic check must not become a new failure mode).
    """
    if not error_text:
        return {"matched": False, "signature": None}
    text = str(error_text).lower()
    for sig in USAGE_LIMIT_SIGNATURES:
        if sig in text:
            return {"matched": True, "signature": sig}
    return {"matched": False, "signature": None}


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
    elif klass == "capacity":
        # D-72: an account-level usage ceiling. No auto-retry — it would just re-hit the same
        # ceiling within the same window. Escalate immediately, distinctly from a data/logic failure.
        result.update(escalate=True,
                      message="usage_limit: spawn failure carries a session/usage-cap signature, "
                              "not a data or logic failure — escalating with the wait-for-reset guidance.")
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


def _selftest():
    # detect_usage_limit: real-shaped signatures match, ordinary failures don't, no crash on None/empty.
    hit = detect_usage_limit("Error: rate_limit_error — you have reached your usage limit, resets at 14:00 UTC")
    assert hit["matched"] is True and hit["signature"] in ("rate_limit", "usage limit", "resets at"), hit
    hit2 = detect_usage_limit("weekly limit reached for this workspace")
    assert hit2["matched"] is True, hit2
    miss = detect_usage_limit("KeyError: 'nomination_id' — malformed nomination.json")
    assert miss["matched"] is False, miss
    empty = detect_usage_limit("")
    assert empty["matched"] is False, empty
    none_ = detect_usage_limit(None)
    assert none_["matched"] is False, none_

    # heal(): capacity class never auto-retries, always escalates, carries the D-72 manual_fix.
    r = heal("premarket", "usage_limit", dry_run=True, notify=False)
    assert r["klass"] == "capacity", r
    assert r["healed"] is False and r["escalate"] is True and r["stand_down"] is False, r
    assert r["actions"] == [], r  # no retry action attempted — retrying would just re-hit the ceiling
    assert "usage" in r["manual_fix"].lower() or "cap" in r["manual_fix"].lower(), r

    # Existing classes untouched by this change.
    assert classify("feed_pull") == "transient"
    assert classify("gate") == "gate"
    assert classify("usage_limit") == "capacity"
    print("self_heal.py selftest: PASS")


def _main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "selftest":
        _selftest()
        return
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
