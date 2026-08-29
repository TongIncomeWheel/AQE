#!/usr/bin/env python3
"""purity_check.py — SIGNAL-STRENGTH PURITY enforcement (v5 §6b, PM-approved 2026-08-28).

Standing rule R1: a name advances or dies on the strength of its signals — seat
count, conviction, momentum — never on whether the bracket engine could compute
a stop, and never on a fundamentals field. This tool ENFORCES that rule instead
of restating it, in two parts:

INVARIANCE (the proof):
  Runs `pma_pipeline.py rank` twice — once on the real inputs, once on copies
  with every bracket.* and fundamentals field STRIPPED from candidate_set and
  export rows — and requires the two phase4 outputs to be IDENTICAL. If they
  ever differ, the strength chain has been contaminated and the run FAILS at
  CHECK. Deliberately NOT stripped: SRM entry_gate and thematic fields — those
  are ratified tiebreakers in the fixed v4.2 ranking key (seat_count >
  conviction_sum > srm_entry_gate > thematic > sc_momentum), part of the key,
  not a gate. Stripping them would flag the ratified key as contamination.

CROWDING AUDIT (the daylight):
  What Rogers found by hand on 2026-08-27 — the committee's most-supported
  names tracked WHICH names had computable brackets (PM/WELL/CSX were the top 3
  by seats and 3 of only 6 bracket-valid names) — becomes a computed line on
  every run's scoreboard: bracket-valid rate among the top-supported names vs
  the base rate in the qualifier pool. A large gap doesn't fail anything (seats
  whose canon uses structural stops are legitimate); it prints ONE line in the
  brief so consensus tracking data-availability is visible the same day, not
  found by a challenge seat a week later.

Exit codes: 0 = pass · 1 = INVARIANCE BROKEN (fail the gate) · 2 = tool error.
"""
import argparse, copy, json, os, shutil, subprocess, sys, tempfile

BRACKET_KEYS = {"bracket"}
BRACKET_PREFIXES = ("bracket.", "bracket_")
FUNDAMENTAL_KEYS = {"fundamentals", "pe", "pe_ratio", "eps", "eps_growth", "revenue_growth",
                    "dividend_yield", "book_value", "roe", "debt_equity", "fcf_yield",
                    "market_cap", "net_margin"}


def strip_row(row):
    out = {}
    for k, v in row.items():
        lk = k.lower()
        if lk in BRACKET_KEYS or lk in FUNDAMENTAL_KEYS or lk.startswith(BRACKET_PREFIXES):
            continue
        out[k] = v
    return out


def strip_file(src, dst, list_keys):
    with open(src) as f:
        data = json.load(f)
    for key in list_keys:
        if key in data and isinstance(data[key], list):
            data[key] = [strip_row(r) if isinstance(r, dict) else r for r in data[key]]
    with open(dst, "w") as f:
        json.dump(data, f, sort_keys=True)


def run_rank(pipeline, tally, candidates, export, cap, solo_min, out):
    cmd = [sys.executable, pipeline, "rank", "--tally", tally, "--candidates", candidates,
           "--export", export, "--cap", str(cap), "--solo-min", str(solo_min), "--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"rank failed: {r.stderr.strip() or r.stdout.strip()}")


def canon(path):
    with open(path) as f:
        return json.dumps(json.load(f), sort_keys=True)


def invariance(a):
    with tempfile.TemporaryDirectory() as td:
        cs_s = os.path.join(td, "cs_stripped.json")
        ex_s = os.path.join(td, "ex_stripped.json")
        out_a = os.path.join(td, "phase4_real.json")
        out_b = os.path.join(td, "phase4_stripped.json")
        strip_file(a.candidates, cs_s, ["universe"])
        strip_file(a.export, ex_s, ["daily_list"])
        run_rank(a.pipeline, a.tally, a.candidates, a.export, a.cap, a.solo_min, out_a)
        run_rank(a.pipeline, a.tally, cs_s, ex_s, a.cap, a.solo_min, out_b)
        same = canon(out_a) == canon(out_b)
        detail = {}
        if not same:
            ra, rb = json.load(open(out_a)), json.load(open(out_b))
            detail = {"real_set": ra.get("deliberation_set"),
                      "stripped_set": rb.get("deliberation_set")}
        return same, detail


def crowding(a, top_n=5):
    with open(a.tally) as f:
        tally = json.load(f)
    with open(a.candidates) as f:
        cs = json.load(f)
    valid = {}
    for r in cs.get("universe", []):
        b = r.get("bracket") or {}
        valid[r.get("ticker")] = bool(b.get("valid"))
    ranked = sorted(tally, key=lambda t: (t.get("count", 0), t.get("sumc", 0)), reverse=True)
    qual = [t for t in ranked if t.get("count", 0) >= 2 or t.get("maxc", 0) >= a.solo_min]
    top = qual[:top_n]
    if not qual:
        return {"line": "crowding audit: no qualifiers today — nothing to audit", "gap": 0.0}
    top_rate = sum(1 for t in top if valid.get(t["ticker"])) / max(1, len(top))
    base_rate = sum(1 for t in qual if valid.get(t["ticker"])) / len(qual)
    gap = top_rate - base_rate
    names = ", ".join(f"{t['ticker']}({'V' if valid.get(t['ticker']) else '-'})" for t in top)
    line = (f"crowding audit: top-{len(top)} by seats [{names}] are {top_rate:.0%} bracket-valid "
            f"vs {base_rate:.0%} across all {len(qual)} qualifiers (gap {gap:+.0%}). ")
    if gap >= a.crowding_warn:
        line += ("WARNING: consensus is tracking bracket availability, not just signal strength — "
                 "read the crowded names' actual signal case before trusting the seat count.")
    else:
        line += "No sign that consensus is tracking bracket availability today."
    return {"line": line, "gap": round(gap, 3), "top_rate": round(top_rate, 3),
            "base_rate": round(base_rate, 3), "warn": gap >= a.crowding_warn}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pipeline", default="pma_pipeline.py")
    p.add_argument("--tally", default="tally.json")
    p.add_argument("--candidates", default="candidate_set.json")
    p.add_argument("--export", required=True)
    p.add_argument("--cap", type=int, default=20)
    p.add_argument("--solo-min", dest="solo_min", type=int, default=4)
    p.add_argument("--crowding-warn", dest="crowding_warn", type=float, default=0.30,
                   help="gap (top rate minus base rate) at which the audit line carries a WARNING")
    p.add_argument("--out", default="purity_check.json")
    a = p.parse_args()
    try:
        same, detail = invariance(a)
        audit = crowding(a)
    except Exception as e:
        print(f"PURITY TOOL ERROR: {e}", file=sys.stderr)
        return 2
    result = {"invariance": "PASS" if same else "FAIL", "invariance_detail": detail,
              "crowding_audit": audit}
    with open(a.out, "w") as f:
        json.dump(result, f, indent=1)
    print(f"invariance: {result['invariance']}")
    print(audit["line"])
    if not same:
        print("R1 CONTAMINATION: ranking changed when bracket/fundamental fields were stripped. "
              "FAIL THE GATE — do not publish on this ranking.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
