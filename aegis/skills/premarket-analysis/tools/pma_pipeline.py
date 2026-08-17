#!/usr/bin/env python3
"""PMA deterministic pipeline tool — v4.2 (PM-ratified 2026-08-17).
All arithmetic between the model stages lives HERE: same inputs, same outputs, no model in the path.
Subcommands:
  trim       raw export -> candidate_set.json (CONSUMED trim; keeps source/on_longlist/in_ledger/elder*)
  packets    candidate_set + voice_menus -> per-voice shuffled TSVs + crown/druck JSON packets (QS byte-stripped)
  tally      nominations dir/file -> tally.json (seat_count, conviction_sum per ticker)
  rank       tally + candidate_set + export srm -> qualify -> 5-key rank -> cap -> deliberation_set.json
  consensus  round2 stances -> verdicts (support>oppose AND support>=2 AND median>=3)
  ledger     append today's phase-4 list to phase4_ledger.json; emit REPEAT flags (>=2 of trailing 5)
  gate       S7Q mechanical checks (quality/completeness families that are greppable)
Run from a working dir holding the day's artifacts. Every subcommand prints its output path + a one-line receipt.
"""
import json, sys, os, csv, random, statistics, argparse, collections

SRM_RANK = {"PASS": 3, "CAUTION": 2, "WATCH": 1, "BLOCKED": 0}
CONSUMED = ["ticker","rank","sc_momentum","flow","energy","structure","mp","mp_state","mp_accel_state",
    "elder","elder_5d","elder_pattern","entry","beta_30d","day_vol","rs_spy_20d","rs_leadership",
    "rs_down_day_20d","sma_distance_pct","ma_20","ma_50","ma_200","atr_14d","gics_sector","gics_sector_name",
    "sector_trend_state","sector_rrg_quadrant","sector_rrg_direction","structure_shift","choch_state",
    "div_state","div_bear_count","knn_prob","atr_caution","runner_setup","runner_conviction_label",
    "premove_setup","mover_subtype","pin_bar_state","inside_bar","lens","lens_positive","lens_warnings",
    "source","held","in_ledger","on_longlist","thematic_basket","thematic_grade","thematic_rrg_quadrant",
    "vol_30d_ann","gics_gate","bracket"]

def load(p): return json.load(open(p))
def save(p, o):
    json.dump(o, open(p, "w"), indent=1)
    print(f"wrote {p}")

def cmd_trim(a):
    D = load(a.export)
    rows = []
    for r in D["daily_list"]:
        row = {k: r.get(k) for k in CONSUMED}
        row["on_longlist"] = (r.get("source") == "longlist")
        row["in_ledger"] = bool(r.get("in_ledger"))
        rows.append(row)
    save(a.out, {"run_date": a.date, "universe": rows})
    print(f"receipt: {len(rows)} names trimmed; sources={dict(collections.Counter(r['source'] for r in rows))}")

def _slice(row, menu):
    out = {}
    for f in menu:
        if f.startswith("bracket."):
            out[f] = (row.get("bracket") or {}).get(f.split(".", 1)[1])
        else:
            out[f] = row.get(f)
    return out

def cmd_packets(a):
    CS, menus = load(a.candidates), load(a.menus)
    os.makedirs(a.outdir, exist_ok=True)
    rng = random.Random(a.date)  # deterministic per-date shuffle
    nominators = [v for v in menus if v not in ("rogers", "lynch", "druckenmiller")]
    for v in nominators:
        rows = [_slice(r, menus[v]) for r in CS["universe"]]
        rng.shuffle(rows)
        p = os.path.join(a.outdir, f"{v}.tsv")
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=menus[v], delimiter="\t")
            w.writeheader()
            for r in rows:
                w.writerow({k: json.dumps(x) if isinstance(x, (dict, list)) else x for k, x in r.items()})
    D = load(a.export)
    for name in ("crown", "druckenmiller"):
        blocks = ["date","market","regime","intermarket","srm","macro_weather","thematic_baskets"]
        pk = {b: D.get(b) for b in blocks}
        txt = json.dumps(pk)
        assert "qs_market" not in txt, f"R3 breach in {name} packet"
        save(os.path.join(a.outdir, f"{name}.json"), pk)
    print(f"receipt: {len(nominators)} nominator TSVs + 2 macro packets; R3 assertion passed")

def cmd_tally(a):
    noms = load(a.nominations)  # list of {voice, nominations:[{ticker, conviction, reason, fields}]}
    T = {}
    for vr in noms:
        for n in vr.get("nominations", []):
            t = T.setdefault(n["ticker"], {"ticker": n["ticker"], "seats": [], "conv": [], "reasons": []})
            t["seats"].append(vr["voice"]); t["conv"].append(n["conviction"])
            t["reasons"].append({"voice": vr["voice"], "reason": n.get("reason"), "conviction": n["conviction"], "fields": n.get("fields", [])})
    out = []
    for t in T.values():
        t["count"], t["maxc"], t["sumc"] = len(t["seats"]), max(t["conv"]), sum(t["conv"])
        out.append(t)
    save(a.out, sorted(out, key=lambda x: (-x["count"], -x["sumc"])))
    print(f"receipt: {len(out)} tickers nominated across {len(noms)} seats")

def cmd_rank(a):
    tally, CS, D = load(a.tally), load(a.candidates), load(a.export)
    uni = {r["ticker"]: r for r in CS["universe"]}
    srm = {s["sector"]: s for s in D["srm"]}
    qual = [t for t in tally if t["count"] >= 2 or t["maxc"] >= a.solo_min]
    def key(t):
        r = uni.get(t["ticker"], {})
        s = srm.get(r.get("gics_sector_name"), {})
        srm_rank = SRM_RANK.get(s.get("entry_gate", ""), 0)
        them = 1 if (r.get("thematic_grade") == "DEPLOY" or r.get("thematic_rrg_quadrant") in ("LEADING", "IMPROVING")) else 0
        return (t["count"], t["sumc"], srm_rank, them, r.get("sc_momentum") or 0, t["ticker"])
    ranked = sorted(qual, key=key, reverse=True)
    cut = ranked[:a.cap]
    dropped = [f"{t['ticker']}({t['count']}s/c{t['maxc']})" for t in ranked[a.cap:]]
    save(a.out, {"cap": a.cap, "qualifying": len(qual),
                 "ranking_key": "seat_count > conviction_sum > srm_entry_gate > thematic_support > sc_momentum",
                 "deliberation_set": [t["ticker"] for t in cut],
                 "ranked": [{"ticker": t["ticker"], "seats": t["count"], "sumc": t["sumc"], "srm": srm.get(uni.get(t["ticker"], {}).get("gics_sector_name"), {}).get("entry_gate"), "sc_m": uni.get(t["ticker"], {}).get("sc_momentum")} for t in ranked],
                 "dropped": dropped})
    print(f"receipt: {len(qual)} qualified, top {min(a.cap, len(qual))} to deliberation, {len(dropped)} cut by cap")

def cmd_consensus(a):
    R2 = load(a.round2)  # list of {voice, stances:[{ticker, stance, conviction, ...}]}
    by_t = collections.defaultdict(lambda: {"support": [], "oppose": [], "abstain": [], "conv": []})
    for vr in R2:
        for s in vr.get("stances", []):
            st = s["stance"].lower()
            by_t[s["ticker"]][st if st in ("support", "oppose", "abstain") else "abstain"].append(vr["voice"])
            if st == "support":
                by_t[s["ticker"]]["conv"].append(s.get("conviction", 3))
    out = []
    for t, d in by_t.items():
        sup, opp = len(d["support"]), len(d["oppose"])
        med = statistics.median(d["conv"]) if d["conv"] else 0
        if sup > opp and sup >= 2 and med >= 3:
            verdict = "ADVANCE"
        elif sup >= 2:
            verdict = "HOLD-FOR-CONDITIONS"
        else:
            verdict = "PASS"
        conviction = min(int(med) if med else 2, 4 if sup < 3 else 5, 3 if verdict != "ADVANCE" else 5)
        out.append({"ticker": t, "verdict": verdict, "conviction": conviction,
                    "split": {"support": d["support"], "oppose": d["oppose"], "abstain": d["abstain"]}})
    save(a.out, out)
    print("receipt: " + ", ".join(f"{c['ticker']}:{c['verdict']}" for c in sorted(out, key=lambda x: x['ticker'])))

def cmd_ledger(a):
    led = load(a.ledger) if os.path.exists(a.ledger) else {"window_sessions": 5, "retention_sessions": 20, "repeat_threshold": 2, "entries": []}
    P4 = load(a.phase4)
    tickers = P4["deliberation_set"] + [d.split("(")[0] for d in P4["dropped"]]
    led["entries"] = [e for e in led["entries"] if e["date"] != a.date] + [{"date": a.date, "tickers": tickers}]
    led["entries"] = sorted(led["entries"], key=lambda e: e["date"])[-led["retention_sessions"]:]
    window = led["entries"][-led["window_sessions"]:]
    counts = collections.Counter(t for e in window for t in set(e["tickers"]))
    repeats = sorted([(t, c) for t, c in counts.items() if c >= led["repeat_threshold"]], key=lambda x: -x[1])
    led["repeat_flags"] = [{"ticker": t, "appearances": c, "window": len(window)} for t, c in repeats]
    save(a.ledger, led)
    print(f"receipt: {len(tickers)} logged for {a.date}; REPEAT flags: " + (", ".join(f"{t} {c}x/{len(window)}" for t, c in repeats) or "none (window has " + str(len(window)) + " sessions)"))

def cmd_gate(a):
    brief = open(a.brief).read()
    cons = load(a.consensus)
    fails = []
    def chk(ok, code, msg):
        print(f"[{'PASS' if ok else 'FAIL'}] {code} {msg}")
        if not ok: fails.append(code)
    for c in cons:
        if c["verdict"] == "ADVANCE":
            chk(len(c["split"]["support"]) > len(c["split"]["oppose"]), "Q2r", f"{c['ticker']}: ADVANCE has support>oppose")
        if c["verdict"] == "HOLD-FOR-CONDITIONS":
            chk(("Condition" in brief and c["ticker"] in brief), "Q2h", f"{c['ticker']}: HOLD carries a Condition line in brief")
    for token, label in [("MACRO", "S1 macro"), ("SECTOR", "S2 sector"), ("HELD", "S3 held book"),
                          ("NEAR MISS", "S5 near misses"), ("ACTION", "S6 action plan"),
                          ("List", "list membership"), ("Elder", "elder field"),
                          ("DRAFT", "draft footer")]:
        chk(token.lower() in brief.lower(), "Q4", f"brief carries {label}")
    chk("persuad" not in brief.lower(), "Q4n", "zero persuasion narration")
    print(f"RESULT: {len(fails)} FAIL")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("trim"); s.add_argument("--export", required=True); s.add_argument("--date", required=True); s.add_argument("--out", default="candidate_set.json")
    s = sub.add_parser("packets"); s.add_argument("--candidates", default="candidate_set.json"); s.add_argument("--export", required=True); s.add_argument("--menus", required=True); s.add_argument("--date", required=True); s.add_argument("--outdir", default="packets")
    s = sub.add_parser("tally"); s.add_argument("--nominations", required=True); s.add_argument("--out", default="tally.json")
    s = sub.add_parser("rank"); s.add_argument("--tally", default="tally.json"); s.add_argument("--candidates", default="candidate_set.json"); s.add_argument("--export", required=True); s.add_argument("--cap", type=int, default=20); s.add_argument("--solo-min", type=int, default=4); s.add_argument("--out", default="phase4.json")
    s = sub.add_parser("consensus"); s.add_argument("--round2", required=True); s.add_argument("--out", default="consensus.json")
    s = sub.add_parser("ledger"); s.add_argument("--ledger", default="phase4_ledger.json"); s.add_argument("--phase4", default="phase4.json"); s.add_argument("--date", required=True)
    s = sub.add_parser("gate"); s.add_argument("--brief", required=True); s.add_argument("--consensus", default="consensus.json")
    a = p.parse_args()
    {"trim": cmd_trim, "packets": cmd_packets, "tally": cmd_tally, "rank": cmd_rank,
     "consensus": cmd_consensus, "ledger": cmd_ledger, "gate": cmd_gate}[a.cmd](a)
