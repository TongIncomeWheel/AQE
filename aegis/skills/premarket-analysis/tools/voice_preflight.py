#!/usr/bin/env python3
"""
voice_preflight.py — VOICE + DATA ACTIVATION CHECK. Runs before the swarm.

Rule: a voice and its data must BOTH work, or the run is wasting time.

Answers two questions per seat and never mixes them:

  1. CAN THIS VOICE RUN?  -> ACTIVATED / NOT ACTIVATED
     Needs its agent file installed and its book (canon.lock.yaml) readable. Nothing else.

  2. CAN IT RUN ITS METHOD ON TODAY'S DATA?  -> READY / SERVED / BLOCKED
     Every number the seat's menu asks for that is missing today gets classified into
     exactly one of four, and each one carries an action:

       DERIVED          the value is fully determined by fields that ARE populated — it is a
                        missing LABEL, not missing information.
                        Action: --apply fills it here and tags it "<field>_source": "derived".
                        Not a blocker.

       SUBSTITUTE_LIVE  a named fallback field is populated and IS ON THIS SEAT'S MENU.
                        Action: packet serves the fallback under a labelled column and the
                        seat declares the substitution. Method runs. Not a blocker.

       MENU_BUG         a populated fallback exists but is NOT on this seat's menu, so the
                        seat is blind to data that is sitting right there.
                        Action: add the field to voice_menus.json. One-line fix. BLOCKS.

       ENGINE_TICKET    no substitute exists anywhere in the export.
                        Action: the engine must emit it. BLOCKS until ruled on.

     Nulls that are a real state (no thematic basket, no pattern detected) are not gaps
     and are never counted.

Exit: 0 all good · 1 a voice is NOT ACTIVATED · 2 quorum failed · 3 a voice is BLOCKED on data.

Usage:
  python3 voice_preflight.py --export aqe_daily_export.json \
      --menus contracts/voice_menus.json --canon aegis/canon \
      --agents-dir ~/.claude/plugins/synced/aegis-voices/agents \
      --out activation.json --apply --strict

--apply writes the DERIVED fields back into the export in place, so the same command that
finds the gap is the one that closes it. Without it the tool only reports.
"""
import argparse, json, os, sys, glob

try:
    import yaml
except ImportError:
    yaml = None

# Seats needing information the AQE export does not carry. The orchestrator fetches, verifies
# and inlines it. The seat NEVER fetches its own: on 2026-08-20 and again on 2026-08-21 the
# lynch seat returned a complete 20-name fundamentals memo with tool_uses == 0, and both times
# the figures failed spot-check against live FMP.
EXTERNAL_SOURCE_SEATS = {
    "lynch": "fundamentals (P/E, growth, balance sheet, payout, next-earnings date)",
}

# Nulls that are a real state, not missing data (2026-08-17 no-blank-data audit).
REAL_STATE_NULLS = {
    "elder_pattern": "no pattern currently detected",
    "thematic_basket": "ticker belongs to no tracked basket",
    "thematic_grade": "ticker belongs to no tracked basket",
    "ma_200": "young listing, insufficient history for a 200-day average",
    "bracket.invalid_reason": "null when the bracket IS valid",
    "lens.extension": "no extension reading for this name",
}

# field -> ordered list of fallbacks that carry the same information in a usable form.
# Verified 2026-08-24 against the live export: bracket.atr_fallback_stop is populated on
# 100% of rows, so a seat is NEVER actually blind on stop data — it just has to be served
# the fallback under a labelled column instead of the strict structural one.
SUBSTITUTES = {
    "bracket.stop":          ["bracket.atr_fallback_stop"],
    "bracket.stop_type":     ["bracket.invalid_reason"],
    "bracket.risk_pct":      ["bracket.atr_fallback_stop", "entry"],
    "bracket.rr":            ["bracket.atr_fallback_stop"],
    "bracket.rr_tp1":        ["bracket.atr_fallback_stop"],
    "bracket.rr_tp2":        ["bracket.atr_fallback_stop"],
    "bracket.stop_atr_dist": ["atr_14d"],
}
SUB_MIN_COVERAGE = 0.95   # a fallback only counts if it is essentially always there
NON_BLOCKING = {"SUBSTITUTE_LIVE", "DERIVED"}

# Fields the orchestrator can compute deterministically at packet build. See field_derive.py.
try:
    from field_derive import DERIVATIONS, derive_all
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from field_derive import DERIVATIONS, derive_all


def flatten(d, prefix=""):
    """Dotted keys, keeping dict containers as present in their own right."""
    out = {}
    for k, v in d.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict):
            out[name] = v
            out.update(flatten(v, name + "."))
        else:
            out[name] = v
    return out


def export_coverage(rows):
    n = len(rows)
    cov = {}
    for r in rows:
        for k, v in flatten(r).items():
            c = cov.setdefault(k, 0)
            if v is not None and v != "":
                cov[k] = c + 1
    return cov, n


def load_canon(canon_dir, seat):
    """(status, detail, recognisers). status: ok|unsigned|unsealed|missing|parse_fail"""
    path = os.path.join(canon_dir, seat, "canon.lock.yaml")
    if not os.path.exists(path):
        alt = glob.glob(os.path.join(canon_dir, seat, "*.md"))
        if alt:
            return "unsealed", f"no canon.lock.yaml; only {os.path.basename(alt[0])}", []
        return "missing", "no book file for this voice", []
    if yaml is None:
        return "ok", "pyyaml unavailable — parse skipped", []
    try:
        d = yaml.safe_load(open(path))
    except Exception as e:
        return "parse_fail", f"book file will not parse: {str(e).splitlines()[0][:70]}", []
    recs = [r if isinstance(r, dict) else {"id": "?", "if": str(r), "fields": []}
            for r in (d.get("recognisers") or [])]
    if not d.get("pm_signed"):
        return "unsigned", "book readable, not yet PM-signed", recs
    return "ok", f"pm_signed={d['pm_signed']}, {len(recs)} rules", recs


def classify_gap(field, menu, cov, n):
    """Return (verdict, action, substitute_used)."""
    # 1. can the orchestrator compute it deterministically from fields that ARE populated?
    if field in DERIVATIONS:
        req, _fn, why = DERIVATIONS[field]
        if all(cov.get(r, 0) / n >= SUB_MIN_COVERAGE for r in req):
            return ("DERIVED",
                    f"orchestrator fills this at packet build (field_derive.py): {why}",
                    "+".join(req))
    # 2. is there a populated fallback field carrying the same information?
    for sub in SUBSTITUTES.get(field, []):
        if cov.get(sub, 0) / n >= SUB_MIN_COVERAGE:
            if sub in menu:
                return ("SUBSTITUTE_LIVE",
                        f"serve {sub} in place of {field}, labelled; seat declares the substitution",
                        sub)
            return ("MENU_BUG",
                    f"{sub} is populated {cov[sub]/n:.0%} but is NOT on this seat's menu — "
                    f"add \"{sub}\" to voice_menus.json[\"{{seat}}\"]",
                    sub)
    return ("ENGINE_TICKET",
            f"no populated substitute for {field} anywhere in the export — engine must emit it",
            None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--menus", required=True)
    ap.add_argument("--canon", required=True)
    ap.add_argument("--agents-dir", default="")
    ap.add_argument("--out", default="activation.json")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any voice is NOT ACTIVATED or BLOCKED on data")
    ap.add_argument("--apply", action="store_true",
                    help="write the DERIVED fields back into --export in place, so the gate "
                         "that finds the gap is also the step that closes it")
    a = ap.parse_args()

    exp = json.load(open(a.export))
    rows = exp.get("daily_list") or []
    if not rows:
        print("STOP: export has no daily_list", file=sys.stderr)
        return 2
    if a.apply:
        filled = derive_all(rows)
        json.dump(exp, open(a.export, "w"), indent=1)
        for f, c in sorted(filled.items()):
            print(f"AUTO-FILLED {f}: {c}/{len(rows)} rows ({c/len(rows):.0%}), "
                  f"tagged {f}_source=derived")
    cov, n = export_coverage(rows)
    menus = json.load(open(a.menus))

    installed = set()
    if a.agents_dir and os.path.isdir(os.path.expanduser(a.agents_dir)):
        for f in os.listdir(os.path.expanduser(a.agents_dir)):
            if f.endswith(".md"):
                installed.add(f[:-3].replace("voice-", ""))

    report = {"schema": "voice_activation.v3", "export_rows": n,
              "export_generated_at": exp.get("generated_at") or exp.get("date"),
              "seats": {}, "actions": []}

    for seat, menu in menus.items():
        if seat.startswith("~~") or not isinstance(menu, list):
            continue
        s = {"menu_size": len(menu), "gaps": [], "notes": []}

        agent_ok = (seat in installed) if a.agents_dir else True
        st, detail, recs = load_canon(a.canon, seat)
        s["book"] = detail

        # ---- 1. can this voice run? ----
        if not agent_ok:
            s["status"] = "NOT ACTIVATED"
            s["fix"] = f"install voice-{seat}.md into the aegis-voices plugin agents/ folder"
        elif st in ("missing", "parse_fail", "unsealed"):
            s["status"] = "NOT ACTIVATED"
            s["fix"] = detail
        else:
            s["status"] = "ACTIVATED"
            s["fix"] = ""
            if st == "unsigned":
                s["notes"].append("book not yet PM-signed — runs, but unsealed")

        dead = [r.get("id", "?") for r in recs
                if not r.get("fields") and "NOT_AVAILABLE" in str(r.get("if", ""))]
        if dead:
            s["rules_that_cannot_fire"] = dead
            s["notes"].append(f"{len(dead)} of {len(recs)} rules in the book need numbers that do "
                              f"not exist anywhere in the export ({','.join(dead)})")

        # ---- 2. can it run its method on today's data? ----
        for f in menu:
            if f == "ticker" or f in REAL_STATE_NULLS:
                continue
            present = cov.get(f, 0) / n if f in cov else 0.0
            if present >= a.min_coverage:
                continue
            verdict, action, sub = classify_gap(f, menu, cov, n)
            action = action.replace("{seat}", seat)
            s["gaps"].append({"field": f, "populated": round(present, 3),
                              "verdict": verdict, "action": action, "substitute": sub})
            if verdict not in NON_BLOCKING:
                report["actions"].append({"seat": seat, "field": f,
                                          "verdict": verdict, "action": action})

        blockers = [g for g in s["gaps"] if g["verdict"] not in NON_BLOCKING]
        subs = [g for g in s["gaps"] if g["verdict"] == "SUBSTITUTE_LIVE"]
        derv = [g for g in s["gaps"] if g["verdict"] == "DERIVED"]
        if blockers:
            s["data"] = (f"BLOCKED — {len(blockers)} number"
                         f"{'s' if len(blockers)!=1 else ''} with no substitute")
        elif subs or derv:
            bits = []
            if subs:
                bits.append(f"{len(subs)} fallback{'s' if len(subs)!=1 else ''}")
            if derv:
                bits.append(f"{len(derv)} auto-filled")
            s["data"] = "SERVED — " + " + ".join(bits)
        else:
            s["data"] = "READY"

        if seat in EXTERNAL_SOURCE_SEATS:
            s["orchestrator_must_serve"] = EXTERNAL_SOURCE_SEATS[seat]
            s["notes"].append(f"orchestrator must fetch, verify and inline "
                              f"{EXTERNAL_SOURCE_SEATS[seat]}; this seat never fetches its own")

        report["seats"][seat] = s

    NOMINATORS = ["elder-lens", "livermore", "minervini", "oneil", "raschke",
                  "seow", "thorp", "wyckoff", "weis"]
    VOTING = NOMINATORS + ["lynch", "detect-lens"]
    off = [x for x in VOTING if report["seats"].get(x, {}).get("status") == "NOT ACTIVATED"]
    blocked = [x for x in VOTING
               if report["seats"].get(x, {}).get("data", "").startswith("BLOCKED")]
    report["roster"] = {
        "voices_total": len(VOTING),
        "voices_activated": len(VOTING) - len(off),
        "not_activated": off,
        "blocked_on_data": blocked,
        "quorum_floor": 8,
        "quorum_ok": (len(VOTING) - len(off)) >= 8,
        "ready_to_run": not off and not blocked,
    }

    report["derived_fields"] = sorted({g["field"] for seat in report["seats"].values()
                                       for g in seat["gaps"] if g["verdict"] == "DERIVED"})

    md = ["| Voice | Status | Data |", "|---|---|---|"]
    for seat in sorted(report["seats"],
                       key=lambda x: (report["seats"][x]["status"] == "ACTIVATED",
                                      report["seats"][x]["data"].startswith("READY"), x)):
        s = report["seats"][seat]
        note = f" — {s['fix']}" if s["fix"] else ""
        md.append(f"| {seat} | **{s['status']}**{note} | {s['data']} |")
    report["markdown"] = "\n".join(md)
    json.dump(report, open(a.out, "w"), indent=1)

    print("\n".join(md))
    r = report["roster"]
    print(f"\n{r['voices_activated']} of {r['voices_total']} voices ACTIVATED.")
    for b in off:
        print(f"  NOT ACTIVATED: {b} — {report['seats'][b]['fix']}")

    if report["actions"]:
        print("\nACTIONS REQUIRED (each one blocks a voice's method):")
        seen = set()
        for act in report["actions"]:
            key = (act["field"], act["verdict"])
            if key in seen:
                continue
            seen.add(key)
            who = [x["seat"] for x in report["actions"] if x["field"] == act["field"]]
            print(f"  [{act['verdict']}] {act['field']}  (hits: {', '.join(who)})")
            print(f"      -> {act['action']}")
    else:
        print("\nNo blocking data actions. Every missing number is either already on the "
              "seat's menu as a live fallback, or auto-filled by the orchestrator.")
    if report["derived_fields"]:
        print("\nAUTO-FILLED AT PACKET BUILD (field_derive.py, deterministic, no engine change):")
        for f in report["derived_fields"]:
            print(f"  {f}  ->  {DERIVATIONS[f][2]}")

    print(f"\nREADY TO RUN: {'YES' if r['ready_to_run'] else 'NO'}")

    if a.strict and not r["ready_to_run"]:
        return 3 if blocked else 1
    if not r["quorum_ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
