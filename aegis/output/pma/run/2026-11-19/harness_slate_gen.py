#!/usr/bin/env python3
"""slate_gen.py <run_dir> : the Chair's slate from decision.json + the seats' own tier-2 forms. Uses ONLY the seats' words (R34/R40)."""
import json, sys, os, hashlib, glob
R = sys.argv[1]
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None
dec = json.load(open(f"{R}/decision.json"))
forms = {}
for f in glob.glob(f"{R}/forms/tier2/*.json"):
    if ".part" in f: continue
    d = json.load(open(f)); forms[d["voice"]] = {x["ticker"]: x for x in d.get("decisions", [])}
plan_path = f"{R}/slate_plan.json"
keep = None
if os.path.exists(plan_path):
    pl = json.load(open(plan_path)); keep = {(x["ticker"] if isinstance(x, dict) else x) for x in (pl.get("keep") or [])}
tickets = []
for t, n in dec["names"].items():
    if n.get("proposal") not in ("ADVANCE", "WATCH"): continue
    if keep is not None and t not in keep: continue
    sup = n["seats"]["support"]; opp = n["seats"]["oppose"]
    trig = n["trigger"]
    def q(seat, txt, k=90):
        txt = " ".join((txt or "").split())
        return f'{seat}: "{txt[:k]}"'
    why = " | ".join(q(s, (forms.get(s, {}).get(t) or {}).get("reason", ""), 95) for s in sup[:3] if forms.get(s, {}).get(t))
    why = (why or f"{len(sup)} SUPPORT of {len(sup)+len(opp)+len(n['seats']['abstain'])}")[:400]
    wi = ""
    for s in (trig.get("seats") or []) + sup:
        w = (forms.get(s, {}).get(t) or {}).get("wrong_if")
        if w:
            w = " ".join(w.split()); wi = f'{s}: "{w[:150]}"'[:200]; break
    if not wi: wi = "see the seats' own wrong-if lines in the tier-2 forms"
    dis = []
    for s in opp:
        r = (forms.get(s, {}).get(t) or {}).get("reason")
        if r: dis.append({"voice": s, "why": " ".join(r.split())[:300]})
    tickets.append({"ticker": t, "verdict": n["proposal"], "entry_trigger": trig["plain"][:200],
        "trigger": {"word": trig["word"], "tf": trig["tf"], "plain": trig["plain"][:120]},
        "timing_count": {"support": n["counts"]["support"], "act_now": n["counts"]["act_now"], "wait": n["counts"]["wait"], "oppose": n["counts"]["oppose"], "abstain": n["counts"]["abstain"]},
        "wrong_if": wi, "horizon_sessions": n["horizon_sessions"], "why_agreed": why, "dissent": dis, "sources": [f"tier2:{s}" for s in sup[:4]]})
mk = dec.get("market_kill")
slate = {"date": dec["date"], "chair": "chair", "board_sha256": sha(f"{R}/board.json"), "decision_sha256": sha(f"{R}/decision.json"), "tickets": tickets, "market_kill": mk}
json.dump(slate, open(f"{R}/slate.json", "w"), indent=1)
print(len(tickets), [(x["ticker"], x["verdict"]) for x in tickets])
