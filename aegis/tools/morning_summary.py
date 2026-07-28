#!/usr/bin/env python3
"""Morning-summary assembler (BL-005 / G6).

Stitches the overnight artifacts into ONE 10:00 summary the PM reads on the phone:
journal state, scorecard, ledger deltas, open backlog asks, and the steer file's
DECIDE items. Fail-visible: any missing piece is marked PARTIAL, never silently omitted.

Usage: python3 tools/morning_summary.py <data_dir> [YYYY-MM-DD]
Writes <data_dir>/eod/<date>/morning_summary.json and prints the plain-text render.
"""
import json, os, sys, datetime

def _load(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default

def assemble(data_dir, date):
    parts, missing = {}, []
    def grab(key, path, summarise):
        v = _load(path)
        if v is None:
            missing.append(key); parts[key] = None
        else:
            parts[key] = summarise(v)
    eod = os.path.join(data_dir, "eod", date)
    persistent = os.path.join(data_dir, "persistent")
    grab("journal", os.path.join(eod, f"aegis_journal_{date}.json"),
         lambda j: {"valid": j.get("valid", True), "closed_trades": len(j.get("closed_trades", [])), "open": len(j.get("open_positions", []))})
    grab("scorecard", os.path.join(eod, "scorecard.json"),
         lambda s: {"verdict": s.get("verdict"), "failing": s.get("failing_windows")})
    grab("dyncap", os.path.join(persistent, "dyncap_ledger.json"),
         lambda d: {"dyncap_usd": d.get("dyncap_usd"), "realised_pnl_usd": d.get("realised_pnl_usd")})
    # backlog open asks + steer DECIDEs
    bl = _load(os.path.join(persistent, "backlog.jsonl").replace(".jsonl", ".jsonl"))
    try:
        rows = [json.loads(l) for l in open(os.path.join(persistent, "backlog.jsonl"))]
        parts["backlog_open"] = sum(1 for r in rows if r.get("status") != "SHIPPED")
        parts["pm_actions"] = [r["id"] for r in rows if r.get("status") != "SHIPPED" and r.get("owner") == "pm_action"]
    except Exception:
        missing.append("backlog"); parts["backlog_open"] = None; parts["pm_actions"] = []
    grab("steer", os.path.join(persistent, "steer.json"),
         lambda s: {"decide": s.get("decide", []), "fyi": len(s.get("fyi", []))})
    # Pipeline Ledger (D-83) — ideas the committee parked, and anything whose trigger
    # fired overnight. NOT via grab(): an absent store is an empty ledger (a normal
    # state before the first proposal), not a missing overnight artifact.
    pl = _load(os.path.join(persistent, "pipeline_ledger.json"), {"rows": []}) or {"rows": []}
    plrows = pl.get("rows", [])
    parts["pipeline_ledger"] = {
        "active": len([r for r in plrows if r.get("status") == "active"]),
        "daily_reconsider": len([r for r in plrows if r.get("status") == "active" and r.get("classification") == "daily_reconsider"]),
        "trigger_silent": len([r for r in plrows if r.get("status") == "active" and r.get("classification") == "trigger_silent"]),
        # fired rows are the only part that asks anything of the PM — surfaced by name
        "fired": [{"ticker": r["ticker"], "why": r.get("fired_note"), "case": r.get("case_snapshot")}
                  for r in plrows if r.get("status") == "fired"],
    }
    status = "PARTIAL" if missing else "COMPLETE"
    return {"date": date, "status": status, "missing": missing, **parts}

def render(s):
    L = [f"AEGIS morning summary — {s['date']}  [{s['status']}]"]
    if s.get("missing"): L.append("  ⚠ missing: " + ", ".join(s["missing"]))
    j = s.get("journal");  L.append(f"  Journal: {'valid' if (j and j['valid']) else 'CHECK'} · {j['closed_trades'] if j else '?'} closed, {j['open'] if j else '?'} open")
    sc = s.get("scorecard"); L.append(f"  Scorecard: {sc['verdict'] if sc else '—'}")
    dc = s.get("dyncap");   L.append(f"  dynCap: {dc['dyncap_usd'] if dc else 'awaiting allocation'}")
    L.append(f"  Backlog open: {s.get('backlog_open')} · PM actions: {', '.join(s.get('pm_actions') or []) or 'none'}")
    st = s.get("steer");    L.append(f"  DECIDE items: {len((st or {}).get('decide', []))} (re-surface until answered)")
    pl = s.get("pipeline_ledger") or {}
    L.append(f"  Pipeline Ledger: {pl.get('active', 0)} active ({pl.get('daily_reconsider', 0)} re-considered daily, {pl.get('trigger_silent', 0)} parked on a trigger)")
    for f in pl.get("fired", []):
        L.append(f"    ▲ {f['ticker']} FIRED — {f.get('why') or ''}")
        if f.get("case"): L.append(f"       {f['case'][:110]}")
    return "\n".join(L)

if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    date = sys.argv[2] if len(sys.argv) > 2 else (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")
    s = assemble(data_dir, date)
    out_dir = os.path.join(data_dir, "eod", date); os.makedirs(out_dir, exist_ok=True)
    json.dump(s, open(os.path.join(out_dir, "morning_summary.json"), "w"), indent=1)
    print(render(s))
