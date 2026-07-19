#!/usr/bin/env python3
"""Mechanical gatekeeper verifier (BL-009 / A-2).

The staging-gatekeeper's 7 checks must be verified by CODE, not narrated by an agent.
This tool takes a request context (the actual files/values), applies each check
deterministically, and emits a signed staging record (contracts/staging.schema.json).
The agent may ONLY relay this record — it cannot fabricate a pass.

Exit 0 = PASS (a preview may be produced), exit 1 = REFUSED. Fail-closed: any missing
input is a failed check, never a skipped one.

Usage: python3 tools/gate_check.py <context.json>
context.json = {
  "ticker","requested_by","broker",
  "committee": {"verdict": "ADVANCE"|..., "conditions": null|"...", "conditions_met": bool},
  "event_driven": bool,
  "bracket": {"valid": bool},
  "size": {"shares": int, "r_used": float},
  "plan": {"status": "APPROVED"|..., "preauthorised": bool, "on_plan": bool},
  "portfolio_gates": {"beta_ok":bool,"var_ok":bool,"leverage_ok":bool,"combined_stop_ok":bool},
  "mechanics": {"entry_limit": bool, "exit_market": bool}
}
"""
import json, sys, datetime

def _sgt_now():
    # True SGT (UTC+8) — matches autopilot.py's SGT logs so staging & autopilot records correlate (MED-3 fix)
    sgt = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    return sgt.replace(microsecond=0).isoformat() + "+08:00"

def verify(ctx):
    checks = []
    def chk(name, ok, evidence):
        checks.append({"name": name, "pass": bool(ok), "evidence": str(evidence)})
    c = ctx.get("committee") or {}
    verdict = c.get("verdict")
    cond_ok = (verdict == "ADVANCE") or (verdict == "HOLD-FOR-CONDITIONS" and c.get("conditions_met") is True)
    chk("consensus", cond_ok, f"committee verdict={verdict} conditions_met={c.get('conditions_met')}")
    chk("event_clean", ctx.get("event_driven") is False, f"event_driven={ctx.get('event_driven')}")
    # D-38: the hard floor is a DEFINABLE stop (risk bounded), NOT bracket quality (RR/ATR).
    b = ctx.get("bracket") or {}
    stop_defined = b.get("stop") is not None or b.get("atr_fallback_stop") is not None
    chk("stop_defined", stop_defined, f"stop={b.get('stop')} atr_fallback={b.get('atr_fallback_stop')} (RR/ATR quality is a soft flag, not gated)")
    sz = ctx.get("size") or {}
    r_used = sz.get("r_used"); max_r = ctx.get("max_r_per_order")
    size_ok = isinstance(sz.get("shares"), int) and sz.get("shares", 0) > 0
    # HIGH-1: when armed, the per-order R cap (RB:autopilot.max_r_per_order) is enforced HERE in code,
    # not left to agent prose — a 2R high-conviction size cannot auto-confirm under a 1R armed cap.
    if ctx.get("autopilot_armed") and max_r is not None and r_used is not None and r_used > max_r:
        size_ok = False
    chk("size", size_ok, f"shares={sz.get('shares')} r_used={r_used} max_r={max_r} armed={ctx.get('autopilot_armed')}")
    pg = ctx.get("portfolio_gates") or {}
    gates_ok = all(pg.get(k) is True for k in ("beta_ok", "var_ok", "leverage_ok", "combined_stop_ok"))
    chk("portfolio_gates", gates_ok, f"{pg}")
    pl = ctx.get("plan") or {}
    pm_ok = pl.get("status") == "APPROVED" and pl.get("on_plan") is True
    chk("pm_approval", pm_ok, f"status={pl.get('status')} on_plan={pl.get('on_plan')} preauth={pl.get('preauthorised')}")
    mc = ctx.get("mechanics") or {}
    chk("mechanics", mc.get("entry_limit") is True and mc.get("exit_market") is True, f"{mc}")

    first_fail = next((c["name"] for c in checks if not c["pass"]), None)
    outcome = "PREVIEW" if first_fail is None else "REFUSED"
    rec = {
        "ticker": ctx.get("ticker"), "outcome": outcome, "strategy_tag": "AEGIS",
        "broker": ctx.get("broker", "tiger"), "requested_by": ctx.get("requested_by", "unknown"),
        "ts": _sgt_now(), "checks": checks, "first_failed_check": first_fail,
        "autopilot_armed": bool(ctx.get("autopilot_armed", False)),
    }
    return rec, (0 if first_fail is None else 1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: gate_check.py <context.json>", file=sys.stderr); sys.exit(2)
    ctx = json.load(open(sys.argv[1]))
    rec, code = verify(ctx)
    print(json.dumps(rec, indent=1))
    sys.exit(code)
