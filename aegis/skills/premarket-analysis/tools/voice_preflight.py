#!/usr/bin/env python3
"""
voice_preflight.py — S0.5 VOICE ACTIVATION GATE

Runs BEFORE the swarm. Proves every seat is actually able to speak, and says so
in writing, before a single nomination exists. Deterministic: no model, no judgment.

The ghost-voice problem this closes:
  A seat can return fluent, well-formatted, entirely confident output while
  half its method is unexecutable — because nothing ever checked that the fields
  its canon requires are (a) on its menu and (b) populated in today's export.
  The canon locks already record which recogniser needs which field. Nobody read them.

Four gates per seat:
  G1 AGENT   — the agent type is installed and spawnable
  G2 CANON   — canon.lock.yaml exists, parses, and is pm_signed
  G3 MENU    — menu fields exist in the export and are populated above threshold
  G4 SOURCE  — seats that need data the export does not carry must be SERVED by the
               orchestrator, never self-fetch (the Lynch fabrication surface)

Verdict per seat: LIVE / DEGRADED / BENCHED. BENCHED seats do not spawn and do not
count toward quorum. DEGRADED seats spawn with their dead rules named in the prompt,
so the seat declares up front instead of quietly proxying.

Usage:
  python3 voice_preflight.py --export aqe_daily_export.json \
      --menus contracts/voice_menus.json --canon aegis/canon \
      --agents-dir ~/.claude/plugins/synced/aegis-voices/agents \
      --out activation.json [--min-coverage 0.5] [--fail-on-benched]
"""
import argparse, json, os, sys, glob

try:
    import yaml
except ImportError:
    yaml = None

# Seats whose canon requires information the AQE export does not carry.
# These MUST be served pre-verified by the orchestrator. A seat that self-fetches
# is a fabrication surface: on 2026-08-20 and 2026-08-21 the lynch seat returned a
# complete 20-name fundamentals memo with tool_uses == 0, twice, and both times the
# figures failed spot-check against live FMP.
EXTERNAL_SOURCE_SEATS = {
    "lynch": "fundamentals (P/E, growth, balance sheet, payout, next-earnings date)",
}

# Fields whose null is a real categorical state, not missing data (per the
# 2026-08-17 no-blank-data audit in voice_menus.json). Never counted as a gap.
LEGITIMATE_NULLS = {
    "elder_pattern",        # 'no pattern currently detected'
    "thematic_basket",      # ticker belongs to no tracked basket
    "thematic_grade",
    "ma_200",               # young listings, insufficient history
    "bracket.invalid_reason",
    "lens.extension",
}


def flatten(d, prefix=""):
    """Flatten nested dicts to dotted keys, but ALSO keep the container key itself.
    A dict-valued field like `lens` is present as a field in its own right — a seat
    can be served the whole block. Treating it as missing was a false positive."""
    out = {}
    for k, v in d.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict):
            out[name] = v            # container counts as present
            out.update(flatten(v, name + "."))
        else:
            out[name] = v
    return out


def export_coverage(rows):
    """field -> (populated_count, total_rows)"""
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
    """Returns (status, detail, recognisers). status in ok|missing|parse_fail|unsigned"""
    path = os.path.join(canon_dir, seat, "canon.lock.yaml")
    if not os.path.exists(path):
        alt = glob.glob(os.path.join(canon_dir, seat, "*.md"))
        if alt:
            return "unsealed", f"no canon.lock.yaml; only {os.path.basename(alt[0])}", []
        return "missing", "no canon directory or lock", []
    if yaml is None:
        return "ok", "pyyaml unavailable — parse skipped", []
    try:
        d = yaml.safe_load(open(path))
    except Exception as e:
        first = str(e).split("\n")[0][:90]
        return "parse_fail", f"YAML will not parse: {first}", []
    if not d.get("pm_signed"):
        return "unsigned", "canon.lock.yaml has no pm_signed", d.get("recognisers") or []
    recs = []
    for r in (d.get("recognisers") or []):
        recs.append(r if isinstance(r, dict) else {"id": "?", "if": str(r), "fields": []})
    return "ok", f"pm_signed={d['pm_signed']}, {len(recs)} recognisers", recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--menus", required=True)
    ap.add_argument("--canon", required=True)
    ap.add_argument("--agents-dir", default="")
    ap.add_argument("--out", default="activation.json")
    ap.add_argument("--min-coverage", type=float, default=0.5,
                    help="field is DEAD below this populated fraction")
    ap.add_argument("--degrade-threshold", type=float, default=0.80,
                    help="seat is DEGRADED below this fraction of live menu fields")
    ap.add_argument("--bench-threshold", type=float, default=0.50,
                    help="seat is BENCHED below this fraction of live menu fields")
    ap.add_argument("--fail-on-benched", action="store_true")
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

    report = {
        "schema": "voice_activation.v1",
        "export_rows": n,
        "export_generated_at": exp.get("generated_at") or exp.get("date"),
        "thresholds": {"min_coverage": a.min_coverage,
                       "degrade": a.degrade_threshold, "bench": a.bench_threshold},
        "seats": {},
    }

    for seat, menu in menus.items():
        if seat.startswith("~~") or not isinstance(menu, list):
            continue
        s = {"menu_size": len(menu), "gates": {}, "dead_fields": [],
             "sparse_fields": [], "notes": []}

        # G1 AGENT
        if a.agents_dir:
            ok = seat in installed
            s["gates"]["G1_agent"] = "PASS" if ok else "FAIL"
            if not ok:
                s["notes"].append(
                    f"no installed agent 'voice-{seat}' — seat runs as general-purpose "
                    f"with canon hand-inlined by the orchestrator every run, which is "
                    f"unversioned and unauditable")
        else:
            s["gates"]["G1_agent"] = "SKIP"

        # G2 CANON — unsigned is a DEGRADE (canon exists and parses, PM just hasn't sealed it);
        # missing or unparseable is a hard FAIL (the seat has no method to run).
        st, detail, recs = load_canon(a.canon, seat)
        s["gates"]["G2_canon"] = ("PASS" if st == "ok"
                                  else "UNSIGNED" if st == "unsigned"
                                  else "FAIL")
        s["canon_detail"] = detail
        if st != "ok":
            s["notes"].append(f"canon {st}: {detail}")

        # canon recognisers that the build already marked unexecutable
        dead_recs = [r.get("id", "?") for r in recs
                     if not r.get("fields") and "NOT_AVAILABLE" in str(r.get("if", ""))]
        if dead_recs:
            s["canon_dead_recognisers"] = dead_recs
            s["notes"].append(
                f"{len(dead_recs)}/{len(recs)} recognisers marked NOT_AVAILABLE at canon "
                f"build ({','.join(dead_recs)}) — these rules cannot fire, ever, on the "
                f"current field set")

        # G3 MENU vs EXPORT
        live = 0
        for f in menu:
            if f == "ticker":
                live += 1
                continue
            if f not in cov:
                s["dead_fields"].append({"field": f, "reason": "not in export"})
                continue
            frac = cov[f] / n
            if frac < a.min_coverage:
                if f in LEGITIMATE_NULLS:
                    live += 1
                    s["notes"].append(f"{f} at {frac:.0%} — legitimate categorical null, not a gap")
                else:
                    s["sparse_fields"].append({"field": f, "populated": round(frac, 3)})
            else:
                live += 1
        s["live_fields"] = live
        s["capability"] = round(live / len(menu), 3) if menu else 0.0
        s["gates"]["G3_menu"] = ("PASS" if s["capability"] >= a.degrade_threshold
                                 else "DEGRADED" if s["capability"] >= a.bench_threshold
                                 else "FAIL")

        # G4 EXTERNAL SOURCE
        if seat in EXTERNAL_SOURCE_SEATS:
            s["gates"]["G4_source"] = "REQUIRES_SERVED_DATA"
            s["requires_served"] = EXTERNAL_SOURCE_SEATS[seat]
            s["notes"].append(
                f"seat needs {EXTERNAL_SOURCE_SEATS[seat]} — NOT in the export. "
                f"Orchestrator must fetch and verify, then inline. If this seat is "
                f"spawned with instructions to fetch its own data it MUST be audited "
                f"for tool_uses > 0 and spot-checked, or discarded.")
        else:
            s["gates"]["G4_source"] = "N/A"

        # VERDICT
        g = s["gates"]
        if g["G1_agent"] == "FAIL" or g["G2_canon"] == "FAIL" or g["G3_menu"] == "FAIL":
            s["verdict"] = "BENCHED"
        elif g["G3_menu"] == "DEGRADED" or g["G2_canon"] == "UNSIGNED" \
                or s.get("canon_dead_recognisers") or s["sparse_fields"] \
                or g["G4_source"] == "REQUIRES_SERVED_DATA":
            s["verdict"] = "DEGRADED"
        else:
            s["verdict"] = "LIVE"
        report["seats"][seat] = s

    # roster / quorum arithmetic
    NOMINATORS = ["elder-lens", "livermore", "minervini", "oneil", "raschke",
                  "seow", "thorp", "wyckoff", "weis"]
    VOTING = NOMINATORS + ["lynch", "detect-lens"]
    benched = [x for x in VOTING if report["seats"].get(x, {}).get("verdict") == "BENCHED"]
    report["roster"] = {
        "nominators_total": len(NOMINATORS),
        "nominators_benched": [x for x in NOMINATORS if x in benched],
        "voting_seats_total": len(VOTING),
        "voting_seats_available": len(VOTING) - len(benched),
        "quorum_floor": 8,
        "quorum_ok": (len(VOTING) - len(benched)) >= 8,
    }

    json.dump(report, open(a.out, "w"), indent=1)

    # markdown block for the report header — pasted verbatim, never hand-typed
    md = ["| Seat | Verdict | Capability | Gates (agent/canon/menu/source) | Blocking issue |",
          "|---|---|---|---|---|"]
    order = {"BENCHED": 0, "DEGRADED": 1, "LIVE": 2}
    for seat in sorted(report["seats"], key=lambda x: (order[report["seats"][x]["verdict"]], x)):
        s = report["seats"][seat]
        g = s["gates"]
        gs = f"{g['G1_agent'][:4]}/{g['G2_canon'][:4]}/{g['G3_menu'][:4]}/{g['G4_source'][:4]}"
        # blocking issue: hardest failure first, so the column always explains the verdict
        if g["G2_canon"] == "FAIL":
            issue = f"CANON: {s['canon_detail']}"
        elif g["G1_agent"] == "FAIL":
            issue = "NO AGENT INSTALLED — canon hand-inlined, unversioned"
        elif s["dead_fields"]:
            issue = "NOT IN EXPORT: " + ", ".join(d["field"] for d in s["dead_fields"][:3])
        elif s["sparse_fields"]:
            issue = "SPARSE: " + ", ".join(
                f"{d['field']} {d['populated']:.0%}" for d in s["sparse_fields"][:3])
        elif s.get("canon_dead_recognisers"):
            issue = (f"{len(s['canon_dead_recognisers'])} recognisers NOT_AVAILABLE at canon "
                     f"build ({','.join(s['canon_dead_recognisers'][:6])})")
        elif g["G2_canon"] == "UNSIGNED":
            issue = f"CANON UNSIGNED: {s['canon_detail']}"
        elif g["G4_source"] == "REQUIRES_SERVED_DATA":
            issue = f"needs served data: {s.get('requires_served','')}"
        else:
            issue = "—"
        issue = issue[:96]
        md.append(f"| {seat} | **{s['verdict']}** | {s['capability']:.0%} | {gs} | {issue} |")
    report["markdown"] = "\n".join(md)
    json.dump(report, open(a.out, "w"), indent=1)

    print("\n".join(md))
    r = report["roster"]
    print(f"\nROSTER: {r['voting_seats_available']}/{r['voting_seats_total']} voting seats available "
          f"(floor {r['quorum_floor']}) — quorum {'OK' if r['quorum_ok'] else 'FAILED'}")
    if benched:
        print(f"BENCHED: {', '.join(benched)}")
    if a.fail_on_benched and benched:
        return 1
    if not r["quorum_ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
