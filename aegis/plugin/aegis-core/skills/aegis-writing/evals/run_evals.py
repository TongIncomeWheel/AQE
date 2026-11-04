#!/usr/bin/env python3
"""Grade text against the aegis-writing eval cases.

  python3 run_evals.py                      prove the harness: every bad text fails, every good text passes
  python3 run_evals.py --case ID --file F   grade a new draft for one case (exit 1 on any failure)

Hard gates: fidelity (the figure/sign/base/date survive) and uncertainty (the hedge survives).
Required/forbidden literals are the style checks. Literal matching is case-insensitive.
"""
import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent


def load():
    return {c["id"]: c for c in json.loads((HERE / "cases.json").read_text())["cases"]}


def grade(case, text):
    t = text.lower()
    miss = lambda lits: [x for x in lits if x.lower() not in t]
    fid = miss(case["gates"]["fidelity"])
    unc = miss(case["gates"]["uncertainty"])
    req = miss(case["required"])
    forb = [x for x in case["forbidden"] if x.lower() in t]
    return {"fidelity_missing": fid, "uncertainty_missing": unc, "required_missing": req,
            "forbidden_present": forb,
            "hard_gates_ok": not fid and not unc, "ok": not (fid or unc or req or forb)}


def selfcheck():
    bad = []
    for cid, c in load().items():
        if not grade(c, c["good"])["ok"]:
            bad.append(f"{cid}: the good rewrite fails: {grade(c, c['good'])}")
        if grade(c, c["bad"])["ok"]:
            bad.append(f"{cid}: the bad text passes (the case cannot tell slop from a fix)")
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case"); ap.add_argument("--file")
    a = ap.parse_args()
    if a.case:
        r = grade(load()[a.case], pathlib.Path(a.file).read_text())
        print(json.dumps(r, indent=1)); sys.exit(0 if r["ok"] else 1)
    problems = selfcheck()
    print("\n".join(problems) or f"aegis-writing evals: {len(load())} cases separate bad from good")
    sys.exit(1 if problems else 0)
