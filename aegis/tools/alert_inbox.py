#!/usr/bin/env python3
"""
alert_inbox.py — capture + gate-prefilter the AQE alert stream (D-62).

THE CORRECT PATTERN (replaces the old email channel):
  AQE engine  --15min-->  aegis/data/alerts/DATE/inbox.jsonl   (writes, does NOT email)
  Aegis market-watch session  --sweep-->  reads NEW inbox lines since last cursor
  THIS TOOL (deterministic, no models):  dedupe + enrich from today's AQE export
    + a CHEAP gate PRE-FILTER (event-clear · on today's strong-momentum universe ·
    coarse quality) so only real candidates survive.
  The market_hours SKILL then runs the 3-lens POD only on the survivors, and PAGES
  the PM only on a pod CONFIRM that is also gate-actionable ("flash if worth taking").

Doctrine: order-blind; NEVER a gate that removes a name silently — a filtered alert
is LOGGED with its reason (use all the data, D-55/D-61). The pod, not this tool,
makes the judgment; this tool just keeps the pod cheap by not podding rank-158 noise.

CLI:
  alert_inbox.py --date 2026-07-21          # sweep today's inbox, print pod-worthy + skipped
  alert_inbox.py --date DATE --export path --inbox path --cursor path --json
"""
import json, os, argparse, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# coarse pod-worthiness pre-filter (the POD does the real judgment; this is just triage)
SC_MOM_FLOOR = 70.0     # high-composite names go to the pod
LENS_FLOOR = 2          # or 2+ detect sub-lenses strong
STRONG_UNIVERSE_FLOOR = 65.0   # "today's strong-momentum universe" cut when AQE doesn't assert on_strong_universe


def _load_export(export):
    d = json.load(open(export))
    dl = {r["ticker"]: r for r in d.get("daily_list", [])}
    lens = {x["ticker"]: x for x in d.get("lens_ranking", {}).get("ranked", [])}
    radar = {r["ticker"] for r in d.get("_radar_pool", [])}
    runners = {x["ticker"] for x in d.get("signal_radar", {}).get("runner_setup", [])}
    return d.get("date"), dl, lens, radar, runners


def _read_inbox(inbox):
    if not os.path.exists(inbox):
        return []
    out = []
    for line in open(inbox):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def sweep(date, export, inbox, cursor_path):
    export_date, dl, lens, radar, runners = _load_export(export)
    alerts = _read_inbox(inbox)

    # dedupe by (ticker, alert_type) keeping the latest ts; skip already-processed
    processed = set()
    if cursor_path and os.path.exists(cursor_path):
        try:
            processed = set(tuple(x) for x in json.load(open(cursor_path)))
        except Exception:
            pass
    latest = {}
    for a in alerts:
        k = (a.get("ticker"), a.get("alert_type"))
        if k[0] is None:
            continue
        if k not in latest or a.get("ts", "") > latest[k].get("ts", ""):
            latest[k] = a

    pod_worthy, skipped = [], []
    for k, a in latest.items():
        t, atype = k
        if k in processed:
            continue
        r = dl.get(t, {})
        L = lens.get(t, {})
        lp = L.get("positive", 0)
        scm = r.get("sc_momentum")
        # staleness: alert must be scoped to today's universe (matches the export date)
        stale = a.get("universe_date") not in (None, export_date)
        # event-clear: AQE may tag; default clear unless flagged
        event_clear = not a.get("event_driven", False)
        enriched = {
            "ticker": t, "alert_type": atype, "price": a.get("price"),
            "sc_momentum": scm, "sector": r.get("gics_sector"), "rank": r.get("rank"),
            "lens_positive": lp, "elder_5d": r.get("elder_5d"), "mp_state": r.get("mp_state"),
            "knn_prob": r.get("knn_prob"), "bracket_valid": (r.get("bracket", {}) or {}).get("valid"),
            "on_strong_universe": (a.get("on_strong_universe")
                                   if a.get("on_strong_universe") is not None
                                   else (t in dl and (scm or 0) >= STRONG_UNIVERSE_FLOOR)),
            "is_runner": (t in runners),
            "trigger_detail": a.get("trigger_detail"),
        }
        # HELD-BOOK alerts (stop/approaching on a position) ALWAYS surface — risk stream, not opportunity
        risk_stream = atype in ("stop_hit", "stop_approaching")
        # QUALITY GATE (D-62/D-57) — the anti-noise filter. A breakout is "worth podding" only if it
        # is a FRESH quality pivot, not an extended chase. Deterministic; protects the voices from noise.
        e5 = r.get("elder_5d") or [0]
        sd = r.get("sma_distance_pct")
        checks = {
            "strong_univ": (scm or 0) >= STRONG_UNIVERSE_FLOOR,
            "detect_ok": lp >= 3,                                   # >=3/6 detect sub-lenses
            "edge_ok": (r.get("knn_prob") or 0) >= 0.5,             # empirical edge, not a coin flip
            "not_extended": (sd is not None and sd < 12),           # NOT a ~20%-over-SMA late chase
            "force_sustained": (sum(e5[-3:]) / 3) >= 8,             # elder force still up
        }
        enriched["gate"] = {"passed": sum(checks.values()), "checks": checks}
        quality_ok = sum(checks.values()) >= 4                      # 4 of 5 -> worth a pod
        if risk_stream:
            enriched["route"] = "HELD-RISK -> page immediately"; pod_worthy.append(enriched)
        elif stale:
            enriched["skip_reason"] = f"stale universe ({a.get('universe_date')} != today {export_date})"; skipped.append(enriched)
        elif not enriched["on_strong_universe"]:
            enriched["skip_reason"] = "not on today's strong-momentum universe"; skipped.append(enriched)
        elif not event_clear:
            enriched["skip_reason"] = "event-driven (earnings) — cannot advance"; skipped.append(enriched)
        elif not quality_ok:
            enriched["skip_reason"] = f"quality gate {enriched['gate']['passed']}/5 (<4) — extended/unconfirmed breakout"; skipped.append(enriched)
        else:
            enriched["route"] = "POD (Detect+Elder+fitting voice) -> page if CONFIRM & gate-actionable"; pod_worthy.append(enriched)

    return {"date": date, "export_date": export_date, "n_alerts": len(latest),
            "pod_worthy": pod_worthy, "skipped": skipped,
            "cursor_write": list(latest.keys())}


def render(res):
    L = [f"AQE ALERT SWEEP — {res['date']} · {res['n_alerts']} unique alerts (export {res['export_date']})"]
    L.append(f"\nPOD-WORTHY ({len(res['pod_worthy'])}) — go to the 3-lens pod, page if it confirms:")
    for a in res["pod_worthy"]:
        L.append(f"  {a['ticker']:5} {a['alert_type']:16} rank={a.get('rank')} sc={a.get('sc_momentum')} lens={a.get('lens_positive')}/6 knn={a.get('knn_prob')} {a.get('sector')} -> {a.get('route')}")
    L.append(f"\nFILTERED ({len(res['skipped'])}) — logged, NOT podded (kept visible, D-61):")
    for a in res["skipped"]:
        L.append(f"  {a['ticker']:5} {a['alert_type']:16} sc={a.get('sc_momentum')} rank={a.get('rank')} — {a['skip_reason']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="AQE alert inbox sweep + gate pre-filter (D-62, deterministic)")
    ap.add_argument("--date")
    ap.add_argument("--export", default=os.path.join(ROOT, "output", "aqe_daily_export.json"))
    ap.add_argument("--inbox")
    ap.add_argument("--cursor")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    date = a.date or "TODAY"
    inbox = a.inbox or os.path.join(ROOT, "data", "alerts", date, "inbox.jsonl")
    res = sweep(date, a.export, inbox, a.cursor)
    print(json.dumps(res, indent=1) if a.json else render(res))


if __name__ == "__main__":
    main()
