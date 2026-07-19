#!/usr/bin/env python3
"""Daily Agentic-Flow Audit (D-43) — the day's flight recorder.

Answers "what did the agent hierarchy actually do today?" — distinct from the integrity
auditor (skills/auditor, which checks CORRECTNESS: valid files, sources cited, no fabrication).
This reconstructs the FLOW across the D-26/D-32 hierarchy (PM → Chief → 5 desks → workers +
the spawned voices/committee/gatekeeper) purely from the day's shelf artifacts — deterministic
(law 4), no new per-skill instrumentation (anti-lasagna). Every layer is marked touched/absent
with its key outcomes, so a returning PM sees the whole path at a glance and can spot a layer
that silently didn't fire.

Reads (whatever is present for the date):
  config/aegis_fund.md · data/persistent/dyncap_ledger.json · data/persistent/autopilot_log.jsonl
  data/sod/DATE/{universe.json, committee.json, nominations/*.json, exceptions/*}
  data/intraday/DATE/{staging/*, exceptions/*}
  data/eod/DATE/{audit_*.json, scorecard.json, metrics*.json, morning_summary.json, journal*}
  data/historical/manifest.json (self-heal seeds)

Usage:
  python3 tools/daily_flow_audit.py [DATE]            -> write + print the flow-audit JSON
  python3 tools/daily_flow_audit.py [DATE] --render   -> also write an HTML flight-recorder card
"""
import json, os, sys, glob
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")


def _load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def _jsonl(p):
    try:
        return [json.loads(l) for l in open(p) if l.strip()]
    except Exception:
        return []


def _exceptions(day):
    out = []
    for base in ("sod", "intraday", "eod"):
        for f in glob.glob(os.path.join(D, base, day, "exceptions", "*")):
            out.append(os.path.basename(f))
    return out


VOICES = ["lynch", "oneil", "wyckoff", "raschke", "steenbarger", "thorp", "seow",
          "minervini", "druckenmiller", "detect_lens"]


def audit(day):
    sod = os.path.join(D, "sod", day)
    intr = os.path.join(D, "intraday", day)
    eod = os.path.join(D, "eod", day)
    layers = {}

    # ---- Chief / sessions (from autopilot log + presence of phase artifacts)
    autolog = [r for r in _jsonl(os.path.join(D, "persistent", "autopilot_log.jsonl"))
               if str(r.get("logged_at", "")).startswith(day)]
    layers["chief_orchestrator"] = {
        "touched": bool(autolog) or os.path.isdir(sod) or os.path.isdir(eod),
        "autopilot_events": len(autolog),
        "phases_seen": [p for p, d in (("premarket", sod), ("eod", eod)) if os.path.isdir(d)],
    }

    # ---- Research desk: universe + swarm + tally + event filter
    uni = _load(os.path.join(sod, "universe.json"), {})
    noms = {}
    for f in glob.glob(os.path.join(sod, "nominations", "*.json")):
        v = os.path.basename(f).replace("nomination_", "").replace(".json", "").replace("voice-", "")
        n = _load(f, {})
        noms[v] = len(n.get("nominations", [])) if isinstance(n, dict) else 0
    ran = sorted(noms)
    layers["research_desk"] = {
        "touched": bool(uni) or bool(noms),
        "universe_names": len(uni.get("names", uni.get("universe", []))) if isinstance(uni, dict) else 0,
        "near_misses": len(uni.get("near_misses", [])) if isinstance(uni, dict) else 0,
        "voices_ran": ran, "voices_ran_count": len(ran),
        "voices_missing": [v for v in VOICES if v not in ran],
        "nominations_per_voice": noms,
        "total_nominations": sum(noms.values()),
    }

    # ---- Committee-desk (spawned): verdicts + held_verdicts
    comm = _load(os.path.join(sod, "committee.json"), {})
    verdicts = comm.get("verdicts", []) if isinstance(comm, dict) else []
    held = comm.get("held_verdicts", []) if isinstance(comm, dict) else []
    def _tally(items, key):
        t = {}
        for it in items:
            t[it.get(key)] = t.get(it.get(key), 0) + 1
        return t
    layers["committee_desk"] = {
        "touched": bool(comm),
        "new_idea_verdicts": _tally(verdicts, "verdict") or _tally(verdicts, "position"),
        "held_verdicts": _tally(held, "verdict"),
        "bear_case_on_every_entry": all(bool(v.get("bear_case")) for v in verdicts) if verdicts else None,
        "sector_exposure_note": bool(comm.get("sector_exposure_note")) if isinstance(comm, dict) else False,
    }

    # ---- Risk desk: dynCap mark, VaR, gates
    led = _load(os.path.join(D, "persistent", "dyncap_ledger.json"), {})
    metrics = _load(os.path.join(eod, "metrics.json"), {}) or _load(next(iter(glob.glob(os.path.join(eod, "*metrics*.json"))), ""), {})
    layers["risk_desk"] = {
        "touched": bool(led) or bool(metrics),
        "dyncap_usd": led.get("dyncap_usd"),
        "dyncap_marked_asof": led.get("marked_asof"),
        "dyncap_method": "mark-to-market (D-41)",
        "var_method": "parametric single-factor (D-42)",
        "metrics_written": bool(metrics),
        "gate_flags": metrics.get("gate_flags") if isinstance(metrics, dict) else None,
    }

    # ---- Execution / staging-gatekeeper (spawned per request)
    staging = [_load(f, {}) for f in glob.glob(os.path.join(intr, "staging", "*.json"))]
    layers["execution_gatekeeper"] = {
        "touched": bool(staging),
        "requests": len(staging),
        "previews": sum(1 for s in staging if s.get("outcome") in ("PREVIEW", "CONFIRMED")),
        "refusals": sum(1 for s in staging if s.get("outcome") == "REFUSED"),
        "refusal_reasons": [s.get("first_failed_check") for s in staging if s.get("outcome") == "REFUSED"],
    }

    # ---- Engineering & Change: integrity audit, scorecard, historical self-heal
    intg = _load(next(iter(glob.glob(os.path.join(eod, "audit_*.json"))), ""), {})
    score = _load(os.path.join(eod, "scorecard.json"), {})
    man = _load(os.path.join(D, "historical", "manifest.json"), {})
    layers["engineering_change"] = {
        "touched": bool(intg) or bool(score),
        "integrity_audit_present": bool(intg),
        "integrity_result": intg.get("result") or intg.get("status") if isinstance(intg, dict) else None,
        "scorecard_present": bool(score),
        "historical_self_heal_last": man.get("last_self_heal") if isinstance(man, dict) else None,
        "store_tickers": man.get("n_tickers") if isinstance(man, dict) else None,
    }

    # ---- Operations: journal
    jrnl = glob.glob(os.path.join(eod, "*journal*.json")) or glob.glob(os.path.join(D, "journal", f"*{day}*.json"))
    msum = bool(_load(os.path.join(eod, "morning_summary.json")))
    layers["operations_desk"] = {
        "touched": bool(jrnl) or msum,
        "journal_written": bool(jrnl),
        "morning_summary": msum,
    }

    exc = _exceptions(day)

    # ---- inferred spawn/agent count (D-27 standing spawns)
    spawns = layers["research_desk"]["voices_ran_count"] \
        + (1 if layers["committee_desk"]["touched"] else 0) \
        + layers["execution_gatekeeper"]["requests"]

    touched = [k for k, v in layers.items() if v.get("touched")]
    not_touched = [k for k, v in layers.items() if not v.get("touched")]

    return {
        "date": day,
        "kind": "daily_agentic_flow_audit (D-43)",
        "layers_touched": touched,
        "layers_not_touched": not_touched,
        "inferred_spawns": {"voices": layers["research_desk"]["voices_ran_count"],
                            "committee_desk": 1 if layers["committee_desk"]["touched"] else 0,
                            "gatekeeper_requests": layers["execution_gatekeeper"]["requests"],
                            "total": spawns},
        "exceptions": exc,
        "exception_count": len(exc),
        "flow": layers,
        "headline": _headline(day, layers, exc),
    }


def _headline(day, L, exc):
    r = L["research_desk"]; c = L["committee_desk"]; x = L["execution_gatekeeper"]
    if not any(v.get("touched") for v in L.values()):
        return f"{day}: no agentic flow recorded (no phase ran / empty shelf)."
    parts = []
    if r["touched"]:
        parts.append(f"{r['voices_ran_count']}/10 voices → {r['total_nominations']} noms")
    if c["touched"]:
        adv = c["new_idea_verdicts"].get("ADVANCE", 0)
        parts.append(f"committee {adv} ADVANCE")
    if x["touched"]:
        parts.append(f"gatekeeper {x['previews']} preview / {x['refusals']} refused")
    if exc:
        parts.append(f"{len(exc)} exception(s)")
    return f"{day}: " + " · ".join(parts) if parts else f"{day}: partial flow."


def write(day, obj):
    outdir = os.path.join(D, "eod", day)
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, f"flow_audit_{day}.json")
    json.dump(obj, open(p, "w"), indent=1)
    return p


# ------------------------------------------------------------------ HTML render
def render_html(obj):
    L = obj["flow"]
    ORDER = [("chief_orchestrator", "PM / Chief Orchestrator"),
             ("research_desk", "Research desk — universe + 10-voice swarm"),
             ("committee_desk", "Committee-desk (spawned, judgment tier)"),
             ("risk_desk", "Risk desk — dynCap · VaR · gates"),
             ("execution_gatekeeper", "Execution — staging-gatekeeper (spawned)"),
             ("engineering_change", "Engineering & Change — assurance · self-heal"),
             ("operations_desk", "Operations — journal · metrics")]
    rows = []
    for key, label in ORDER:
        v = L.get(key, {})
        on = v.get("touched")
        dot = "#16a34a" if on else "#9ca3af"
        state = "TOUCHED" if on else "not run"
        detail = {k: val for k, val in v.items() if k != "touched"}
        det = "; ".join(f"{k}: {val}" for k, val in detail.items() if val not in (None, [], {}, 0, False))
        rows.append(f"""<tr>
  <td style="padding:10px 12px;border-bottom:1px solid #1f2937;white-space:nowrap">
    <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{dot};margin-right:8px"></span>
    <b style="color:#e5e7eb">{label}</b></td>
  <td style="padding:10px 12px;border-bottom:1px solid #1f2937;color:{'#16a34a' if on else '#9ca3af'};font-weight:600">{state}</td>
  <td style="padding:10px 12px;border-bottom:1px solid #1f2937;color:#9ca3af;font-size:13px">{det or '—'}</td>
</tr>""")
    sp = obj["inferred_spawns"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Agentic-Flow Audit {obj['date']}</title></head>
<body style="margin:0;background:#0b0f19;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#e5e7eb">
<div style="max-width:760px;margin:0 auto;padding:24px">
  <div style="font-size:12px;letter-spacing:.14em;color:#6b7280;text-transform:uppercase">Aegis · Daily Agentic-Flow Audit (D-43)</div>
  <h1 style="margin:6px 0 2px;font-size:22px">{obj['date']}</h1>
  <div style="color:#93c5fd;font-size:15px;margin-bottom:16px">{obj['headline']}</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px">
    <div style="background:#111827;border:1px solid #1f2937;border-radius:10px;padding:10px 14px">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase">Layers touched</div>
      <div style="font-size:20px;font-weight:700">{len(obj['layers_touched'])}/7</div></div>
    <div style="background:#111827;border:1px solid #1f2937;border-radius:10px;padding:10px 14px">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase">Inferred spawns</div>
      <div style="font-size:20px;font-weight:700">{sp['total']}</div>
      <div style="font-size:11px;color:#6b7280">{sp['voices']} voices · {sp['committee_desk']} committee · {sp['gatekeeper_requests']} gate</div></div>
    <div style="background:#111827;border:1px solid #1f2937;border-radius:10px;padding:10px 14px">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase">Exceptions</div>
      <div style="font-size:20px;font-weight:700;color:{'#ef4444' if obj['exception_count'] else '#16a34a'}">{obj['exception_count']}</div></div>
  </div>
  <table style="width:100%;border-collapse:collapse;background:#0f1420;border:1px solid #1f2937;border-radius:12px;overflow:hidden">
    <thead><tr style="background:#111827">
      <th style="text-align:left;padding:10px 12px;font-size:11px;color:#6b7280;text-transform:uppercase">Hierarchy layer</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;color:#6b7280;text-transform:uppercase">State</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;color:#6b7280;text-transform:uppercase">What it did</th>
    </tr></thead><tbody>{''.join(rows)}</tbody>
  </table>
  <div style="color:#4b5563;font-size:11px;margin-top:14px">Reconstructed deterministically from the day's shelf artifacts (tools/daily_flow_audit.py). A grey "not run" is itself the signal — a layer that should have fired but didn't. Integrity (fabrication/sources) is the separate auditor; this is coverage of the flow.</div>
</div></body></html>"""


if __name__ == "__main__":
    a = sys.argv[1:]
    day = next((x for x in a if not x.startswith("--")), date.today().isoformat())
    obj = audit(day)
    p = write(day, obj)
    if "--render" in a:
        h = os.path.join(D, "eod", day, f"flow_audit_{day}.html")
        open(h, "w").write(render_html(obj))
        print(f"wrote {p}\nwrote {h}")
    else:
        print(json.dumps(obj, indent=1))
