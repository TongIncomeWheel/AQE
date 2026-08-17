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
    "vol_30d_ann","gics_gate","bracket",
    "ma_100","premove_conviction","runner_conviction","sc_m_gate_detail","sc_p_gate_detail",
    "squeeze_breakout_state","was_squeezed","squeeze_breakout_volume_confirmed","squeeze_breakout_date",
    "elder_context","knn_threshold_clear",
    # QS -- the PM's own proprietary regime/signal read. Captured here (2026-08-17, PM request)
    # SOLELY for the S7 card QS line, shown on every card after deliberation closes, whether or
    # not that name was ever nominated. R3 is unchanged and still absolute: this field must never
    # reach a seat packet. Enforced two ways -- (1) no voice_menus.json entry may name it (checked
    # in cmd_packets, fails loudly), (2) it isn't in any menu today, so it never round-trips through
    # _slice. "qs" is undocumented in aegis/contracts/*.schema.json despite being live in the daily
    # export -- schema drift, flagged separately, not blocking.
    "qs", "on_qs"]

# Any menu field naming these is a same-class breach as qs_market in the macro packets below --
# checked once per nominator before packets are written, so a future menu edit fails the build
# instead of shipping a leak that's only caught by grepping a TSV after the fact.
QS_FORBIDDEN = ("qs", "on_qs")

# NO-BLANK-DATA, 2026-08-17 (PM standing rule: "no blank data, all fields available and used").
# Two independent per-ticker checks, both against the RAW export (not the trim), because a gap
# that only shows up after CONSUMED/menu slicing is a gap the pipeline created, not one it found.
#
# CORE_TECHNICAL_FIELDS mirrors the export's own data_quality.flagged definition exactly (verified
# 2026-08-17: the export flags 7 tickers -- AUB, ELS, EQR, FITB, KSS, NNN, OKTA, all source=="qs" --
# on precisely this field set). A ticker null on ALL of these has nothing for any voice to assess
# honestly, so it is held out of every nominator TSV entirely (not served as a wall of "null") and
# written to no_technical_coverage.json instead. It stays in candidate_set.json -- it can still
# carry a QS card line at S7 (PM request, render-only, regardless of deliberation).
CORE_TECHNICAL_FIELDS = ["sc_momentum", "flow", "energy", "structure", "mp", "elder", "entry"]

# PATTERN_FIELDS are NOT covered by the export's own data_quality self-check -- verified 2026-08-17
# against the live export: 14 tickers (all source=="longlist", core fields present and real) come
# back null on every field in this set. That is a real, undeclared upstream gap in the pattern-
# detection engine, not a "no signal" state (contrast: elder_pattern/thematic_basket/thematic_grade/
# ma_200 nulls elsewhere in the export ARE legitimate no-signal/structural states and are NOT
# treated as gaps here). These tickers are NOT excluded -- they have real technical data on
# everything else -- but the gap is reported loudly per run so it doesn't quietly undercount.
PATTERN_FIELDS = ["pin_bar_state", "inside_bar", "choch_state", "div_state", "knn_prob",
                   "squeeze_breakout_state", "was_squeezed"]

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
    """Resolve a menu field against a universe row.

    Dotted names resolve into nested dicts at ANY depth. Before 2026-08-17 this
    special-cased `bracket.` only, so every other dotted field on a menu
    (energy.squeeze_score, bq.bq_base_dur, bq.bq_range_tight, lens.coil,
    lens.structure, lens.resistance) silently resolved to None -- minervini,
    oneil, raschke and wyckoff had been served blank columns for those fields.
    Fixed generically; `missing_menu_fields` in the packets receipt now reports
    any menu field that resolves to None for EVERY row, so a dead field is
    loud instead of silent.
    """
    out = {}
    for f in menu:
        if "." in f:
            cur = row
            for part in f.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
                if cur is None:
                    break
            out[f] = cur
        else:
            out[f] = row.get(f)
    return out

def _cell(x):
    """TSV cell serializer. None must never render as a blank cell -- a blank cell is
    indistinguishable from an empty string or a parsing glitch. Write the literal token
    "null" instead, so a seat can never misread absence as an empty value (2026-08-17,
    PM standing rule: no blank data)."""
    if x is None:
        return "null"
    if isinstance(x, (dict, list)):
        return json.dumps(x)
    return x

def cmd_packets(a):
    CS, menus, D = load(a.candidates), load(a.menus), load(a.export)
    os.makedirs(a.outdir, exist_ok=True)
    rng = random.Random(a.date)  # deterministic per-date shuffle
    # v4.2 architecture: nominators are S4 voices only (excludes S5a/S5b challenge/specialist agents and macro voices)
    nominators = [v for v in menus if v not in ("rogers", "lynch", "druckenmiller", "steenbarger", "detect-lens", "~~CONFIG_NOTE~~")]
    # R3, menu-level: no seat's menu may name qs/on_qs (or any qs.* subfield) -- checked BEFORE any
    # TSV is written, so a future menu edit that adds one fails the build loudly instead of shipping.
    for v in menus:
        if v == "~~CONFIG_NOTE~~":
            continue
        breach = [f for f in menus[v] if f in QS_FORBIDDEN or f.startswith("qs.")]
        assert not breach, f"R3 breach: {v}'s menu names {breach} -- QS is PM-only, never a seat input"

    # NO-BLANK-DATA per-ticker checks (2026-08-17), against the raw export rows directly.
    raw_by_ticker = {r["ticker"]: r for r in D["daily_list"]}
    no_coverage = sorted(t for t, r in raw_by_ticker.items()
                          if all(r.get(f) is None for f in CORE_TECHNICAL_FIELDS))
    pattern_gap = sorted(t for t, r in raw_by_ticker.items()
                          if t not in no_coverage and all(r.get(f) is None for f in PATTERN_FIELDS))
    if no_coverage:
        save(os.path.join(a.outdir, "no_technical_coverage.json"),
             {"excluded_from_nominator_tsvs": no_coverage,
              "reason": f"all of {CORE_TECHNICAL_FIELDS} null -- nothing for any voice to honestly assess",
              "note": "still present in candidate_set.json; may still carry a QS card line at S7"})

    universe = [r for r in CS["universe"] if r["ticker"] not in no_coverage]
    dead = {}
    for v in nominators:
        rows = [_slice(r, menus[v]) for r in universe]
        # a menu field that is None on EVERY row is a dead column -- report, never hide
        d = [f for f in menus[v] if all(r.get(f) is None for r in rows)]
        if d:
            dead[v] = d
        rng.shuffle(rows)
        p = os.path.join(a.outdir, f"{v}.tsv")
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=menus[v], delimiter="\t")
            w.writeheader()
            for r in rows:
                w.writerow({k: _cell(x) for k, x in r.items()})
    # macro packets: crown + druckenmiller read global blocks, NEVER qs_market (R3)
    for name, blocks in (("crown", ["date","market","regime","intermarket","srm","macro_weather","thematic_baskets"]),
                         ("druckenmiller", ["date","market","regime","intermarket","srm","macro_weather","thematic_baskets"])):
        pk = {b: D.get(b) for b in blocks}
        txt = json.dumps(pk)
        assert "qs_market" not in txt and "STAND_DOWN" not in txt.replace(json.dumps(pk.get("regime") or {}), ""), f"R3 breach in {name} packet"
        save(os.path.join(a.outdir, f"{name}.json"), pk)
    print(f"receipt: {len(nominators)} nominator TSVs + 2 macro packets; R3 assertion passed; "
          f"{len(universe)}/{len(CS['universe'])} names served to nominators ({len(no_coverage)} held out, no coverage)")
    if dead:
        print("WARNING missing_menu_fields (null on every row, seat is served a blank column):")
        for v, fs in sorted(dead.items()):
            print(f"  {v}: {', '.join(fs)}")
    else:
        print("receipt: missing_menu_fields none -- every menu field resolved on at least one row")
    if no_coverage:
        print(f"WARNING no_technical_coverage ({len(no_coverage)} tickers, excluded from nominator TSVs, see no_technical_coverage.json): {', '.join(no_coverage)}")
    if pattern_gap:
        print(f"WARNING pattern_field_gap ({len(pattern_gap)} tickers, NOT excluded, upstream pattern-detection engine gap, undeclared by export data_quality): {', '.join(pattern_gap)}")

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
    tickers = load(a.phase4)["deliberation_set"] + [d.split("(")[0] for d in load(a.phase4)["dropped"]]
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
                          ("QS", "QS read (PM-only, render-only, every card)"),
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
