#!/usr/bin/env python3
"""
Stop reconciliation for long-only cash equities: Tiger working stops vs committee stop levels.

  reconcile : compare + classify  -> <out>/reconcile.json, reconcile.md, approvals_template.json
  ticket    : PM-approved levels  -> <out>/amend_requests.json, amend_checklist.md
  verify    : fresh Tiger pull    -> compares the book against the amend requests

THIS TOOL NEVER SENDS, CANCELS OR AMENDS AN ORDER. It is read + compute only (constitution law 1).
Amend requests are specs for the staging-gatekeeper, or a checklist for manual entry at Tiger.

Rules enforced here, not left to prose:
  * ratchet: a stop is only ever RAISED; lowering needs "allow_lower": true set by the PM
  * a long sell-stop is never proposed at or above the live mark
  * committee levels older than --stale-days block tickets unless --allow-stale
  * approval qty must equal held qty
  * Tiger has no amend call: every amend is CANCEL then PLACE, never place-then-cancel (oversell risk)
"""
import argparse
import datetime as dt
import json
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text())


def classify(sym, pos, order, com, tol):
    mark = pos["mark"]
    tl, kind = None, None
    if order:
        if order.get("stop_price") is not None:
            tl, kind = order["stop_price"], "trigger"
        elif order.get("limit_price") is not None:
            tl, kind = order["limit_price"], "limit-only"
        else:
            kind = "hidden"
    cl = com.get("level") if com else None
    r = dict(symbol=sym, qty=pos["qty"], mark=mark,
             order_id=order["id"] if order else None,
             order_type=order["type"] if order else None,
             order_qty=order["qty"] if order else None,
             tiger_level=tl, tiger_kind=kind, committee_level=cl,
             committee_action=(com or {}).get("action"), basis=(com or {}).get("basis"),
             status=None, proposal=None, note="")
    if order and order["qty"] != pos["qty"]:
        r["note"] += f"QTY MISMATCH order {order['qty']} vs held {pos['qty']}. "
    if not order:
        r["status"] = "NO_TIGER_STOP"
        if com and com.get("action") == "EXIT":
            r["note"] += "Committee says EXIT and nothing protects the position. PM: exit or place a protective stop."
        elif cl is not None and cl < mark:
            r["proposal"] = {"action": "PLACE", "level": cl}
            r["note"] += "Unprotected; committee level available."
        else:
            r["note"] += "Unprotected and no usable committee level."
    elif com is None:
        r["status"] = "NO_COMMITTEE_LEVEL"
        r["note"] += "Not in the committee's held book; cannot reconcile."
    elif cl is None:
        r["status"] = "COMMITTEE_EXIT"
        r["note"] += "Committee EXIT with no stop level; PM decision."
    elif mark <= cl:
        r["status"] = "BREACHED"
        r["note"] += "Mark is through the committee line; no stop proposed above price. PM: exit or override."
    elif tl is None:
        r["status"] = "TIGER_TRIGGER_HIDDEN"
        r["note"] += "Plain STP order: Tiger MCP returns no price. Cannot reconcile."
    else:
        diff = tl - cl
        pct = diff / cl * 100
        r["diff"], r["diff_pct"] = round(diff, 2), round(pct, 2)
        if abs(pct) <= tol:
            r["status"] = "ALIGNED"
        elif diff > 0:
            r["status"] = "TIGER_TIGHTER"
            r["note"] += "Ratchet: no change proposed. "
        else:
            r["status"] = "TIGER_LOOSER"
            r["proposal"] = {"action": "RAISE", "level": cl}
        if kind == "limit-only":
            r["note"] += "Tiger trigger hidden; limit shown, true trigger is at or above it."
    if r["proposal"]:
        lvl = r["proposal"]["level"]
        r["proposal"]["dist_to_mark_pct"] = round((mark - lvl) / mark * 100, 2)
    return r


def cmd_reconcile(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pos = {p["symbol"]: p for p in load(a.positions)["positions"]}
    orders = {}
    for o in load(a.orders)["orders"]:
        if o.get("side", "SELL") == "SELL" and o["type"] in ("STP", "STP_LMT"):
            orders[o["symbol"]] = o
    cm = load(a.committee)
    age = (dt.date.fromisoformat(a.today) - dt.date.fromisoformat(cm["as_of"])).days
    rows = [classify(s, pos[s], orders.get(s), cm["stops"].get(s), a.tol) for s in sorted(pos)]
    (out / "reconcile.json").write_text(json.dumps(
        {"today": a.today, "committee_as_of": cm["as_of"], "committee_source": cm.get("source"),
         "committee_age_days": age, "rows": rows}, indent=2))
    props = [r for r in rows if r["proposal"]]
    tmpl = {"instruction": "PM: set approved=true and approved_level per row you accept. Anything else is ignored.",
            "committee_as_of": cm["as_of"],
            "rows": [{"symbol": r["symbol"], "order_id": r["order_id"], "qty": r["qty"],
                      "current_tiger_level": r["tiger_level"], "proposed_level": r["proposal"]["level"],
                      "action": r["proposal"]["action"], "approved": False, "approved_level": None,
                      "allow_lower": False} for r in props]}
    (out / "approvals_template.json").write_text(json.dumps(tmpl, indent=2))
    stale = age > a.stale_days
    L = [f"# Stop reconciliation, {a.today}",
         f"Committee levels as of {cm['as_of']} ({age} days old)"
         + ("  **STALE: tickets blocked until refreshed or overridden**" if stale else ""), "",
         "| Symbol | Qty | Mark | Tiger stop | Committee | Delta | Status | Proposal | Note |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tl = "-" if r["tiger_level"] is None else f"{r['tiger_level']:.2f}" + ("*" if r["tiger_kind"] == "limit-only" else "")
        cl = "-" if r["committee_level"] is None else f"{r['committee_level']:.2f}"
        dl = "-" if "diff" not in r else f"{r['diff']:+.2f} ({r['diff_pct']:+.1f}%)"
        pr = "-" if not r["proposal"] else (f"{r['proposal']['action']} to {r['proposal']['level']:.2f} "
                                            f"({r['proposal']['dist_to_mark_pct']:.1f}% under mark)")
        L.append(f"| {r['symbol']} | {r['qty']} | {r['mark']:.2f} | {tl} | {cl} | {dl} | {r['status']} | {pr} | {r['note'].strip()} |")
    L += ["", "\\* limit price of a stop-limit; Tiger MCP does not return the trigger."]
    (out / "reconcile.md").write_text("\n".join(L))
    print("\n".join(L))


def cmd_ticket(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rec = load(a.recon or out / "reconcile.json")
    appr = load(a.approvals)
    if rec["committee_age_days"] > a.stale_days and not a.allow_stale:
        raise SystemExit(f"REFUSED: committee levels are {rec['committee_age_days']} days old "
                         f"(limit {a.stale_days}). Refresh them or pass --allow-stale.")
    byname = {r["symbol"]: r for r in rec["rows"]}
    tickets, refused = [], []
    for ap in appr["rows"]:
        if not ap.get("approved") or ap.get("approved_level") is None:
            continue
        s, lvl = ap["symbol"], float(ap["approved_level"])
        r = byname.get(s)
        why = None
        if r is None:
            why = "symbol not in the reconcile"
        elif lvl >= r["mark"]:
            why = f"level {lvl} is at or above mark {r['mark']}"
        elif r["tiger_level"] is not None and lvl < r["tiger_level"] and not ap.get("allow_lower"):
            why = f"would LOWER the stop ({r['tiger_level']} to {lvl}); ratchet blocks it unless allow_lower"
        elif ap.get("qty") != r["qty"]:
            why = f"approval qty {ap.get('qty')} differs from held {r['qty']}"
        if why:
            refused.append({"symbol": s, "reason": why})
            continue
        lim = round(lvl * (1 - a.limit_buffer_pct / 100), 2)
        steps = []
        if r["order_id"]:
            steps.append({"n": 1, "do": "re-pull open orders", "check": f"order {r['order_id']} still working, qty {r['qty']}"})
            steps.append({"n": 2, "do": "cancel", "order_id": r["order_id"]})
        steps.append({"n": len(steps) + 1, "do": "place",
                      "args": {"symbol": s, "side": "SELL", "quantity": r["qty"], "order_type": "STP_LMT",
                               "stop_price": round(lvl, 2), "limit_price": lim,
                               "time_in_force": "GTC", "outside_rth": False}})
        steps.append({"n": len(steps) + 1, "do": "verify",
                      "check": f"new SELL STP_LMT {r['qty']} {s} limit {lim} working; old order gone; position qty unchanged"})
        tickets.append({"symbol": s, "action": "PLACE" if not r["order_id"] else "RAISE",
                        "old_order_id": r["order_id"], "from": r["tiger_level"], "to": round(lvl, 2),
                        "limit": lim, "qty": r["qty"], "committee_basis": r["basis"], "steps": steps})
    doc = {"status": "REQUEST ONLY, NOT SENT", "committee_as_of": rec["committee_as_of"],
           "sequence_rule": "CANCEL then PLACE. Never place first: both could trigger and oversell.",
           "tickets": tickets, "refused": refused}
    (out / "amend_requests.json").write_text(json.dumps(doc, indent=2))
    C = ["# Amend checklist (request only, nothing sent)", ""]
    for t in tickets:
        C.append(f"## {t['symbol']}: {t['action']} stop {t['from']} to {t['to']} (limit {t['limit']}) x{t['qty']}")
        for s in t["steps"]:
            detail = s.get("args") or s.get("order_id") or s.get("check")
            C.append(f"- [ ] {s['n']}. {s['do']}: {json.dumps(detail)}")
        if t["committee_basis"] == "close":
            C.append("- note: the committee rule is close-basis; an intraday stop fires on a wick.")
        C.append("")
    for f in refused:
        C.append(f"REFUSED {f['symbol']}: {f['reason']}")
    (out / "amend_checklist.md").write_text("\n".join(C))
    print("\n".join(C))


def cmd_verify(a):
    out = Path(a.out_dir)
    req = load(a.requests or out / "amend_requests.json")
    pos = {p["symbol"]: p for p in load(a.positions)["positions"]}
    orders = [o for o in load(a.orders)["orders"]
              if o.get("side", "SELL") == "SELL" and o["type"] in ("STP", "STP_LMT")]
    res = []
    for t in req["tickets"]:
        s = t["symbol"]
        mine = [o for o in orders if o["symbol"] == s]
        old_live = any(o["id"] == t["old_order_id"] for o in mine) if t["old_order_id"] else False
        new = [o for o in mine if o["type"] == "STP_LMT" and o["qty"] == t["qty"]
               and o.get("limit_price") is not None and abs(o["limit_price"] - t["limit"]) < 0.005
               and o["id"] != t["old_order_id"]]
        qty_ok = s in pos and pos[s]["qty"] == t["qty"]
        if not mine:
            st = "UNPROTECTED"
        elif new and old_live:
            st = "DOUBLE_SELL_RISK"
        elif new and not old_live and qty_ok:
            st = "OK"
        elif old_live and not new:
            st = "NOT_REPLACED"
        else:
            st = "MISMATCH"
        res.append({"symbol": s, "status": st, "expected_limit": t["limit"], "new_order_ids": [o["id"] for o in new],
                    "position_qty_ok": qty_ok,
                    "note": "Trigger price is not returned by Tiger; verified on limit, qty and order identity."})
    (out / "verify.json").write_text(json.dumps(res, indent=2))
    for r in res:
        print(f"{r['symbol']:<6} {r['status']:<18} expected limit {r['expected_limit']}  qty_ok={r['position_qty_ok']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("reconcile")
    p.add_argument("--positions", required=True)
    p.add_argument("--orders", required=True)
    p.add_argument("--committee", required=True)
    p.add_argument("--today", default=dt.date.today().isoformat())
    p.add_argument("--tol", type=float, default=0.5, help="aligned tolerance, percent")
    p.add_argument("--stale-days", type=int, default=3)
    p.add_argument("--out-dir", default="stop_out")
    p.set_defaults(fn=cmd_reconcile)

    p = sp.add_parser("ticket")
    p.add_argument("--approvals", required=True)
    p.add_argument("--recon")
    p.add_argument("--allow-stale", action="store_true")
    p.add_argument("--stale-days", type=int, default=3)
    p.add_argument("--limit-buffer-pct", type=float, default=0.5)
    p.add_argument("--out-dir", default="stop_out")
    p.set_defaults(fn=cmd_ticket)

    p = sp.add_parser("verify")
    p.add_argument("--positions", required=True)
    p.add_argument("--orders", required=True)
    p.add_argument("--requests")
    p.add_argument("--out-dir", default="stop_out")
    p.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
