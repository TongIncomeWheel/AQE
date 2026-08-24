#!/usr/bin/env python3
"""
voice_preflight.py — VOICE ACTIVATION CHECK. Runs before the swarm.

Answers TWO questions, separately, and never mixes them:

  1. CAN THIS VOICE RUN?      -> ACTIVATED / NOT ACTIVATED
     Needs: its agent file installed, and its book (canon.lock.yaml) present and readable.
     This is the ONLY thing that can stop a voice speaking.

  2. IS TODAY'S DATA COMPLETE FOR IT?  -> COMPLETE / n numbers missing
     Some numbers a book asks for are not in today's export. That is a data problem,
     not a voice problem. It never blocks the voice. It is reported so the PM can see it.

Mixing those two is what produced "ghost voices": a seat that could speak but was missing
half its numbers still returned ten confident nominations, and nothing said so.

Usage:
  python3 voice_preflight.py --export aqe_daily_export.json \
      --menus contracts/voice_menus.json --canon aegis/canon \
      --agents-dir ~/.claude/plugins/synced/aegis-voices/agents \
      --out activation.json
"""
import argparse, json, os, sys, glob

try:
    import yaml
except ImportError:
    yaml = None

# Seats needing information the AQE export does not carry. The orchestrator fetches and
# verifies it, then inlines it. The seat NEVER fetches its own: on 2026-08-20 and again on
# 2026-08-21 the lynch seat returned a complete 20-name fundamentals memo with tool_uses == 0,
# and both times the figures failed spot-check against live FMP.
EXTERNAL_SOURCE_SEATS = {
    "lynch": "fundamentals (P/E, growth, balance sheet, payout, next-earnings date)",
}

# Nulls that are a real state, not missing data (2026-08-17 no-blank-data audit).
LEGITIMATE_NULLS = {
    "elder_pattern", "thematic_basket", "thematic_grade", "ma_200",
    "bracket.invalid_reason", "lens.extension",
}


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
            else:
                cov[k] = c
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
        return "parse_fail", f"book file will not parse: {str(e).splitlines()[0][:80]}", []
    recs = [r if isinstance(r, dict) else {"id": "?", "if": str(r), "fields": []}
            for r in (d.get("recognisers") or [])]
    if not d.get("pm_signed"):
        return "unsigned", "book present and readable, not yet PM-signed", recs
    return "ok", f"pm_signed={d['pm_signed']}, {len(recs)} rules", recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--menus", required=True)
    ap.add_argument("--canon", required=True)
    ap.add_argument("--agents-dir", default="")
    ap.add_argument("--out", default="activation.json")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--fail-on-not-activated", action="store_true")
    a = ap.parse_args()

    exp = json.load(open(a.export))
    rows = exp.get("daily_list") or []
    if not rows:
        print("STOP: export has no daily_list", file=sys.stderr)
        return 2
    cov, n = export_coverage(rows)
    menus = json.load(open(a.menus))

    installed = set()
    if a.agents_dir and os.path.isdir(os.path.expanduser(a.agents_dir)):
        for f in os.listdir(os.path.expanduser(a.agents_dir)):
            if f.endswith(".md"):
                installed.add(f[:-3].replace("voice-", ""))

    report = {"schema": "voice_activation.v2", "export_rows": n,
              "export_generated_at": exp.get("generated_at") or exp.get("date"),
              "seats": {}}

    for seat, menu in menus.items():
        if seat.startswith("~~") or not isinstance(menu, list):
            continue
        s = {"menu_size": len(menu), "missing_numbers": [], "notes": []}

        agent_ok = (seat in installed) if a.agents_dir else True
        st, detail, recs = load_canon(a.canon, seat)
        s["book"] = detail

        # ---- QUESTION 1: can this voice run? ----
        if not agent_ok:
            s["status"] = "NOT ACTIVATED"
            s["fix"] = (f"install voice-{seat}.md into the aegis-voices plugin agents/ folder")
        elif st in ("missing", "parse_fail", "unsealed"):
            s["status"] = "NOT ACTIVATED"
            s["fix"] = detail
        else:
            s["status"] = "ACTIVATED"
            s["fix"] = ""
            if st == "unsigned":
                s["notes"].append("book not yet PM-signed — runs, but unsealed")

        # rules the book itself marked unexecutable at build time
        dead = [r.get("id", "?") for r in recs
                if not r.get("fields") and "NOT_AVAILABLE" in str(r.get("if", ""))]
        if dead:
            s["rules_that_cannot_fire"] = dead
            s["notes"].append(f"{len(dead)} of {len(recs)} rules in the book need numbers that do "
                              f"not exist anywhere in the export ({','.join(dead)})")

        # ---- QUESTION 2: is today's data complete for it? ----
        for f in menu:
            if f == "ticker":
                continue
            if f not in cov:
                s["missing_numbers"].append({"field": f, "populated": 0.0,
                                             "reason": "not in export at all"})
            elif cov[f] / n < a.min_coverage and f not in LEGITIMATE_NULLS:
                s["missing_numbers"].append({"field": f, "populated": round(cov[f] / n, 3),
                                             "reason": "mostly blank today"})
        k = len(s["missing_numbers"])
        s["data_today"] = "COMPLETE" if k == 0 else (
            f"{k} number{'s' if k != 1 else ''} missing")

        if seat in EXTERNAL_SOURCE_SEATS:
            s["orchestrator_must_serve"] = EXTERNAL_SOURCE_SEATS[seat]
            s["notes"].append(f"orchestrator must fetch, verify and inline "
                              f"{EXTERNAL_SOURCE_SEATS[seat]}; this seat must never fetch its own")

        report["seats"][seat] = s

    NOMINATORS = ["elder-lens", "livermore", "minervini", "oneil", "raschke",
                  "seow", "thorp", "wyckoff", "weis"]
    VOTING = NOMINATORS + ["lynch", "detect-lens"]
    off = [x for x in VOTING if report["seats"].get(x, {}).get("status") == "NOT ACTIVATED"]
    report["roster"] = {
        "voices_total": len(VOTING),
        "voices_activated": len(VOTING) - len(off),
        "not_activated": off,
        "quorum_floor": 8,
        "quorum_ok": (len(VOTING) - len(off)) >= 8,
    }

    md = ["| Voice | Status | Today's data |", "|---|---|---|"]
    for seat in sorted(report["seats"],
                       key=lambda x: (report["seats"][x]["status"] == "ACTIVATED", x)):
        s = report["seats"][seat]
        note = f" — {s['fix']}" if s["fix"] else ""
        md.append(f"| {seat} | **{s['status']}**{note} | {s['data_today']} |")
    report["markdown"] = "\n".join(md)
    json.dump(report, open(a.out, "w"), indent=1)

    print("\n".join(md))
    r = report["roster"]
    print(f"\n{r['voices_activated']} of {r['voices_total']} voices ACTIVATED.")
    for b in off:
        print(f"  NOT ACTIVATED: {b} — {report['seats'][b]['fix']}")

    if a.fail_on_not_activated and off:
        return 1
    if not r["quorum_ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
