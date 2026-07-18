#!/usr/bin/env python3
"""The PM's autopilot switch. Default is OFF (preview-only) — always.
  /arm     -> arm(reason)      arms until 05:30 SGT (fixed, definitive — PM ruling: no timezone math)
  /disarm  -> disarm(reason)
  /ap      -> status()
State: data/persistent/autopilot.json — dated, reasoned, auto-expiring. The Staging Gatekeeper
reads status before ANY confirm call; missing/expired/disarmed state == OFF. Every arm/disarm is
appended to data/persistent/autopilot_log.jsonl. Expiry is FIXED at the next 05:30 SGT — past US close
in both summer (04:00) and winter (05:00), definitive, no DST logic to get wrong (PM ruling, D-7a).
"""
import argparse, json, os
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
SGT = ZoneInfo("Asia/Singapore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "persistent", "autopilot.json")
LOG = os.path.join(ROOT, "data", "persistent", "autopilot_log.jsonl")

def _now(): return datetime.now(SGT).replace(tzinfo=None)  # D1: pinned to SGT regardless of host tz

def _write(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), indent=1)
    with open(LOG, "a") as f: f.write(json.dumps({**state, "logged_at": _now().isoformat(timespec="seconds")}) + "\n")

ARM_EXPIRY = time(5, 30)   # fixed 05:30 SGT — RB:autopilot.expiry

def _next_expiry(dt):
    d = dt.date() if dt.time() < ARM_EXPIRY else dt.date() + timedelta(days=1)
    return datetime.combine(d, ARM_EXPIRY)

def status():
    """ANY read problem == OFF (QA-F5): corrupt json, missing keys, bad dates all fail safe."""
    try:
        if not os.path.exists(STATE): return {"armed": False, "why": "no state — default OFF"}
        s = json.load(open(STATE))
        if not s.get("armed"): return {"armed": False, "why": "disarmed"}
        if _now() > datetime.fromisoformat(s["expires_at"]): return {"armed": False, "why": f"expired {s['expires_at']}"}
        s.setdefault("orders_used", 0)
        return s
    except Exception as e:
        return {"armed": False, "why": f"state unreadable ({type(e).__name__}) — fail-safe OFF"}

def count_order(max_orders: int):
    """A1 fix: durable per-arming order counter. Gatekeeper calls `autopilot.py count` BEFORE each confirm;
    exit 0 = allowed (counter incremented atomically), exit 1 = cap reached or not armed."""
    s = status()
    if not s.get("armed"):
        print(json.dumps({"allowed": False, "why": s.get("why", "not armed")})); raise SystemExit(1)
    used = int(s.get("orders_used", 0))
    if used >= max_orders:
        print(json.dumps({"allowed": False, "why": f"cap reached {used}/{max_orders}"})); raise SystemExit(1)
    s["orders_used"] = used + 1
    _write(s)
    print(json.dumps({"allowed": True, "orders_used": s["orders_used"], "max": max_orders})); raise SystemExit(0)

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("arm"); a1.add_argument("--reason", default="PM /arm")
    a2 = sub.add_parser("disarm"); a2.add_argument("--reason", required=True)
    sub.add_parser("status")
    c = sub.add_parser("count"); c.add_argument("--max", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "count":
        count_order(a.max); return
    if a.cmd == "status":
        print(json.dumps(status(), indent=1)); return
    if a.cmd == "disarm":
        _write({"armed": False, "reason": a.reason, "at": _now().isoformat(timespec="seconds")}); print("DISARMED"); return
    exp = _next_expiry(_now())
    _write({"armed": True, "armed_at": _now().isoformat(timespec="seconds"), "expires_at": exp.isoformat(timespec="seconds"), "reason": a.reason, "armed_by": "PM", "orders_used": 0})
    print(f"ARMED until {exp} — gatekeeper may confirm within caps; auto-off on any kill condition")

if __name__ == "__main__":
    main()
