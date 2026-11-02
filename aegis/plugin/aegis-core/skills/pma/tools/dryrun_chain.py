#!/usr/bin/env python3
"""dryrun_chain.py -- the NO-MODEL integration test of the whole PMA chain on REAL published AQE data.

PM 2026-11-01: "complete all process orchestration and integration test. Ensure process and agentic integrity
and interaction contracts are proper." Every seat is replaced by a SYNTHETIC form generator that fills the
house contract from the real packet it would have read (figures copied from the row, never invented); every
hop is validated by registrar.py exactly as a live run validates it; every tool step runs for real. Zero model
spend. What it proves: the data flows end to end, every contract is satisfiable from real data, every validator
fires, the counting tools agree with each other, and the Cards render from the result. What it does NOT prove:
that a seat's judgment is good -- there is no judgment here, by design.

  python3 dryrun_chain.py --output-dir aegis/output --run-dir /tmp/dryrun --date 2026-11-03
R38-R41 (2026-11-02): the open FLOOR is replaced by the two-tier funnel -- MTF -> CLAIMS -> CROSS -> FUNNEL -> PAIR ->
TIER2 -> TIMING -- with seeded outcomes the run asserts (a name that must DROP at tier 1, a REFUTE that must become a
pair, an ACT_NOW/WAIT tie that must be WATCH, a slate verdict that differs from decision.json and must be REJECTED).
Exit 0 = every step passed its barrier. Exit 1 = a FAIL line (named). Writes <run-dir>/dryrun_report.json.
"""
from __future__ import annotations

import argparse, glob, json, os, random, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PMA_DIR = os.path.abspath(os.path.join(HERE, ".."))
CORE = os.path.abspath(os.path.join(PMA_DIR, "..", ".."))
VOICES = os.path.join(os.path.dirname(CORE), "aegis-voices")
T = lambda n: os.path.join(HERE, n)
PIPE, REG, CARDS, COND, LEVELS, PMLENS, PURITY, CHECK = (T("pma_pipeline.py"), T("registrar.py"), T("pma_cards.py"), T("pma_conditions.py"),
                                                           T("pma_levels.py"), T("pm_lens.py"), T("purity_check.py"),
                                                           os.path.join(PMA_DIR, "..", "daily-check", "check.py"))
DECIDERS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]
QA = "steenbarger"
FAMILY = {"oneil": "breakout", "minervini": "breakout", "livermore": "pivotal", "elder-lens": "impulse",
          "seow": "position", "raschke": "swing", "wyckoff": "structure"}
STEPS, FAILS = [], []


def step(name, cmd, cwd, must_exit0=True, env=None):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    ok = (r.returncode == 0) if must_exit0 else True
    log = (r.stdout + r.stderr)[-1200:]
    STEPS.append({"step": name, "cmd": " ".join(os.path.basename(c) if c.endswith(".py") else c for c in cmd[:6]) + (" ..." if len(cmd) > 6 else ""),
                  "rc": r.returncode, "ok": ok, "secs": round(time.time() - t0, 1), "tail": log[-400:]})
    if not ok:
        FAILS.append(f"{name}: rc={r.returncode} :: {log[-300:]}")
    print(("  ok   " if ok else "  FAIL ") + f"{name} ({r.returncode})")
    return r


def validate(path, cwd, *args, expect_reject=False):
    """A seeded-bad form is SUPPOSED to be refused (rc=1); only an unexpected verdict is a failure."""
    r = step(f"registrar validate {os.path.relpath(path, cwd)}" + (" (seeded bad, must REJECT)" if expect_reject else ""),
             [sys.executable, REG, "validate", "--file", path, *args], cwd, must_exit0=not expect_reject)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"result": "REJECT", "errors": ["no JSON from registrar"]}


def read_packet(path):
    rows = [l for l in open(path, encoding="utf-8", errors="replace").read().split("\n") if l and not l.startswith("#")]
    hdr = rows[0].split("\t")
    out = []
    for l in rows[1:]:
        cells = l.split("\t")
        out.append(dict(zip(hdr, cells)))
    return hdr, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output-dir", required=True, help="aegis/output as published (export, candidate_set, packets/, crown, valen)")
    ap.add_argument("--run-dir", required=True); ap.add_argument("--date", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    od, rd = os.path.abspath(a.output_dir), os.path.abspath(a.run_dir)
    if os.path.isdir(rd):
        shutil.rmtree(rd)
    for d in ("forms/r1", "forms/challenge", "forms/r2", "forms/cross", "forms/tier2", "forms/floor2", "forms/ratify", "forms/qa"):
        os.makedirs(os.path.join(rd, d))
    # ---- 0. GATHER: copy the published inputs into the run root under their bare names (data-steward contract) ----
    for n in ("aqe_daily_export.json", "candidate_set.json", "aqe_crown_macro.json", "aqe_valen_dashboard.json", "aqe_last_run.json"):
        src = os.path.join(od, n)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(rd, n))
        else:
            FAILS.append(f"GATHER: {n} missing in {od}")
    shutil.copytree(os.path.join(od, "packets"), os.path.join(rd, "packets"))
    shutil.copy(os.path.join(PMA_DIR, "contracts", "voice_menus.json"), os.path.join(rd, "voice_menus.json"))
    # universe.json = candidate_set (challenge-packets reads --universe with a `universe` key)
    shutil.copy(os.path.join(rd, "candidate_set.json"), os.path.join(rd, "universe.json"))
    step("DATA GATE check.py data", [sys.executable, CHECK, "data", "--output-dir", od], rd)
    step("registrar init", [sys.executable, REG, "init", "--date", a.date], rd)
    step("preflight run (rulings + tests)", [sys.executable, T("preflight_run.py"), "run"], PMA_DIR, must_exit0=False)
    CS = json.load(open(os.path.join(rd, "candidate_set.json"))); uni = {r["ticker"]: r for r in CS["universe"]}
    EX = json.load(open(os.path.join(rd, "aqe_daily_export.json")))
    # ---- 1. NOMINATE: synthetic blind shortlists, <= 6 each, figures copied from the seat's own packet ----
    for v in DECIDERS:
        hdr, rows = read_packet(os.path.join(rd, "packets", f"{v}.tsv"))
        rows = [r for r in rows if r.get("ticker") in uni and not uni[r["ticker"]].get("held")]
        rows.sort(key=lambda r: -float(r.get("sc_momentum") or 0))
        pick = rows[: 4 + (hash(v) % 3)]          # 4..6 names, never padded
        noms = [{"ticker": r["ticker"], "conviction": 3 + (i % 3), "reason": f"synthetic dry run: sc_momentum {r.get('sc_momentum')} read from my packet; no judgment",
                 "checklist_trace": [{"step": 1, "canon_ref": ["C1"], "observed": f"sc_momentum {r.get('sc_momentum')}", "verdict": "pass", "fields": ["sc_momentum"]}],
                 "falsifier": "close below the entry on volume"} for i, r in enumerate(pick)]
        form = {"voice": v, "date": a.date, "round": 1, "nominations": noms,
                "held_review": [{"ticker": h["ticker"], "verdict": "KEEP", "note": "dry run"} for h in (EX.get("held_positions") or [])],
                "declarations": ["DRY RUN -- synthetic form, figures copied from the served packet, no judgment exercised"], "shortfall_reason": None}
        f = os.path.join(rd, "forms", "r1", f"{v}.json"); json.dump(form, open(f, "w"), indent=1)
        res = validate(f, rd, "--round", "1", "--candidates", "candidate_set.json")
        if res.get("result") != "OK":
            FAILS.append(f"NOMINATE {v}: registrar REJECT {res.get('errors')}")
    # cap check (R33): a 7th nomination must be refused -- the cap is 6 per decider
    bad = json.load(open(os.path.join(rd, "forms", "r1", "oneil.json"))); bad["nominations"] = (bad["nominations"] * 3)[:7]
    for i, n in enumerate(bad["nominations"]):
        n["ticker"] = list(uni)[i]
    bf = os.path.join(rd, "forms", "oneil_7.json"); json.dump(bad, open(bf, "w"))
    cap_live = a.date >= "2026-11-01"           # the registrar date-gates the cap on R33's effective date
    res = validate(bf, rd, "--round", "1", "--candidates", "candidate_set.json", expect_reject=cap_live)
    if cap_live and res.get("result") != "REJECT":
        FAILS.append("R33 cap: a 7-nomination ballot was ACCEPTED")
    # ---- 2. RANK. tally reads ONE file holding the list of forms (the conductor stitches forms/r1/*.json) ----
    step("tally", [sys.executable, PIPE, "tally", "--nominations", "forms/r1", "--out", "tally.json"], rd)   # as RUN.yaml
    step("pm-lens", [sys.executable, PMLENS, "--export", "aqe_daily_export.json", "--out", "pm_lens.json"], rd)
    step("rank", [sys.executable, PIPE, "rank", "--tally", "tally.json", "--candidates", "candidate_set.json", "--export", "aqe_daily_export.json",
                  "--cap", "24", "--door-budget", "8", "--pm-lens", "pm_lens.json", "--pm-lens-min", "5", "--out", "phase4.json"], rd)
    step("ledger (phase4)", [sys.executable, PIPE, "ledger", "--ledger", "phase4_ledger.json", "--phase4", "phase4.json", "--date", a.date], rd)
    if not os.path.exists(os.path.join(rd, "phase4.json")):
        FAILS.append("RANK produced no phase4.json -- the chain cannot continue")
        json.dump({"date": a.date, "steps": STEPS, "fails": FAILS, "ok": False}, open(os.path.join(rd, "dryrun_report.json"), "w"), indent=1)
        print("\nDRY RUN FAILED at RANK"); return 1
    P4 = json.load(open(os.path.join(rd, "phase4.json"))); ds = P4["deliberation_set"]
    print(f"  room: {len(ds)} names")
    # ---- 3. CHALLENGE (Steenbarger only) ----
    step("challenge-packets", [sys.executable, PIPE, "challenge-packets", "--menus", "voice_menus.json", "--date", a.date, "--outdir", "seat_packets",
                               "--universe", "universe.json", "--phase4", "phase4.json", "--forms", "forms/r1", "--seats", QA], rd)
    ch = {"voice": QA, "date": a.date, "seat_kind": "challenge", "names_read": len(ds), "obligations": [], "data_gaps": [],
          "findings": [{"scope": ds[0], "ticker": ds[0], "kind": "CROWDING", "claim": "dry run: the most-nominated name is flagged so the floor opens on it",
                        "evidence": f"tally count for {ds[0]}", "addressed_to": "oneil"}]}
    cf = os.path.join(rd, "forms", "challenge", f"{QA}.json"); json.dump(ch, open(cf, "w"), indent=1)
    res = validate(cf, rd, "--kind", "challenge", "--candidates", "candidate_set.json")
    if res.get("result") != "OK":
        FAILS.append(f"CHALLENGE: registrar REJECT {res.get('errors')}")
    # ---- 3b. MTF (R39): the W / D / H1 grid for the room. A dry run has no FMP bars: with tools/mtf.py present it runs on
    # an empty mtf_bars/ (every name declared NOT SERVED); without it a declared STUB is written from the export row. ----
    mtf_tool = T("mtf.py")
    if os.path.exists(mtf_tool):
        os.makedirs(os.path.join(rd, "mtf_bars"), exist_ok=True)
        step("mtf build (no bars in a dry run -> NOT SERVED, declared)", [sys.executable, mtf_tool, "build", "--bars", "mtf_bars", "--phase4", "phase4.json",
                                                                          "--export", "aqe_daily_export.json", "--date", a.date, "--out", "mtf.json"], rd)
    if not os.path.exists(os.path.join(rd, "mtf.json")):
        rowsx = {r["ticker"]: r for r in EX.get("daily_list") or []}
        names = {}
        for j, t in enumerate(ds):
            r = rowsx.get(t) or uni.get(t) or {}
            if j == len(ds) - 2 or not r:
                names[t] = {"served": False, "reason": "dry-run stub: declared unserved"}; continue
            names[t] = {"served": True, "W": {"summary": f"stub: ma_50 {r.get('ma_50')} vs ma_200 {r.get('ma_200')}"},
                        "D": {"summary": f"stub: entry {r.get('entry')} vs ma_20 {r.get('ma_20')}"},
                        "H1": {"summary": "stub: no 1-hour bars in a dry run"}, "summary": "dry-run stub"}
        json.dump({"schema": "mtf.v1", "date": a.date, "names": names, "stub": "dryrun_chain.py: tools/mtf.py absent or wrote nothing"},
                  open(os.path.join(rd, "mtf.json"), "w"), indent=1)
        print("  note mtf.json written as a declared dry-run STUB")
    M_ = json.load(open(os.path.join(rd, "mtf.json")))
    if set(ds) - set(M_.get("names") or {}):
        FAILS.append(f"MTF: room names without a row (served or NOT SERVED): {sorted(set(ds) - set(M_.get('names') or {}))[:6]}")
    # ---- 4. VOTE: identical packet, synthetic case forms with a deliberate split on one name ----
    step("r2digest (vote packet)", [sys.executable, PIPE, "r2digest", "--export", "aqe_daily_export.json", "--phase4", "phase4.json", "--tally", "tally.json",
                                    "--fundamentals", "fundamentals_pack.json", "--steenbarger", cf, "--crown", "aqe_crown_macro.json",
                                    "--valen", "aqe_valen_dashboard.json", "--mtf", "mtf.json", "--run-id", "dryrun", "--out", "VOTE_PACKET.txt"], rd)
    vp = open(os.path.join(rd, "VOTE_PACKET.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(rd, "VOTE_PACKET.txt")) else ""
    if vp.count("\n  MTF: ") != len(ds):
        FAILS.append(f"r2digest --mtf: {vp.count(chr(10) + '  MTF: ')} MTF lines for {len(ds)} room names")
    if "RISK (Valen" in vp or "no-buy" in vp.lower():
        FAILS.append("R41: the vote packet still carries Valen's RISK block / no-buy flags")
    split_name = ds[1] if len(ds) > 1 else ds[0]
    for i, v in enumerate(DECIDERS):
        votes = []
        for t in ds:
            r = uni.get(t) or {}
            oppose = (t == split_name and i >= 4) or (t == ds[-1])
            vote = {"ticker": t, "vote": "OPPOSE" if oppose else "SUPPORT", "conviction": 3,
                    "reason": f"dry run: sc_momentum {r.get('sc_momentum')} structure {r.get('structure')} from the packet",
                    "case": {"for": f"sc_momentum {r.get('sc_momentum')} and structure {r.get('structure')} as served", "against": f"extension {r.get('extension_atr_20')} ATR and day_vol {r.get('day_vol')} as served",
                             "entry_trigger": "h1 close above the pivot high", "wrong_if": "close back under the pivot", "horizon_sessions": 5 + 2 * i,
                             "would_change_my_mind": "a failed test of the pivot on heavy volume", "cannot_see": []}}
            if oppose:
                vote["opposing_case"] = "the base is tight and the group is leading"
            else:
                vote["conditions"] = {"lane": "BREAKOUT", "buy": ["h1_close_above:pivot_high", "vol_x_ge:1.4"], "confirm": ["above_vwap_s"], "wrong": ["close_below:pivot_high"], "tf": "1H"}
            votes.append(vote)
        # R16.1 SPLIT BALLOTS: with the case form a ballot runs ~1.5 KB per name, so a room over ~15 names does
        # not fit the 24 KB form cap. The seat files parts; each part is validated on its own (--part/--of), then
        # `registrar.py merge` proves the parts cover the deliberation set exactly. The dry run exercises exactly that.
        PART = 12
        parts = [votes[i:i + PART] for i in range(0, len(votes), PART)]
        if len(parts) == 1:
            form = {"voice": v, "date": a.date, "round": 2, "votes": votes, "declarations": ["DRY RUN -- synthetic ballot"]}
            f = os.path.join(rd, "forms", "r2", f"{v}.json"); json.dump(form, open(f, "w"))
            res = validate(f, rd, "--round", "2", "--candidates", "candidate_set.json", "--phase4", "phase4.json", "--packet", "VOTE_PACKET.txt")
            if res.get("result") != "OK":
                FAILS.append(f"VOTE {v}: registrar REJECT {res.get('errors')[:3]}")
        else:
            for k, chunk in enumerate(parts, 1):
                form = {"voice": v, "date": a.date, "round": 2, "votes": chunk, "declarations": [f"DRY RUN -- part {k} of {len(parts)}"]}
                f = os.path.join(rd, "forms", "r2", f"{v}.part{k}of{len(parts)}.json"); json.dump(form, open(f, "w"))
                res = validate(f, rd, "--round", "2", "--candidates", "candidate_set.json", "--phase4", "phase4.json", "--packet", "VOTE_PACKET.txt",
                               "--part", str(k), "--of", str(len(parts)))
                if res.get("result") != "OK":
                    FAILS.append(f"VOTE {v} part {k}: registrar REJECT {res.get('errors')[:3]}")
            step(f"registrar merge {v}", [sys.executable, REG, "merge", "--glob", f"forms/r2/{v}.part*.json", "--out", f"forms/r2/{v}.json", "--phase4", "phase4.json"], rd)
            # the parts STAY beside the merged file, exactly as RUN.yaml leaves them -- board/ratify-count skip .partNofM.json
    # ---- 5. CLAIMS (R38 tier 1, code): the blind board for the record, then the claims board + per-seat packets ----
    step("board", [sys.executable, PIPE, "board", "--round2", "forms/r2", "--phase4", "phase4.json", "--challenge", cf, "--date", a.date, "--out", "board.json"], rd)
    step("claims", [sys.executable, PIPE, "claims", "--round2", "forms/r2", "--phase4", "phase4.json", "--challenge", cf, "--mtf", "mtf.json",
                    "--export", "aqe_daily_export.json", "--date", a.date, "--out", "claims_board.json", "--packets-dir", "claims_packets"], rd)
    if not os.path.exists(os.path.join(rd, "claims_board.json")):
        FAILS.append("CLAIMS produced no claims_board.json -- the funnel cannot run")
        json.dump({"date": a.date, "steps": STEPS, "fails": FAILS, "ok": False}, open(os.path.join(rd, "dryrun_report.json"), "w"), indent=1)
        print("\nDRY RUN FAILED at CLAIMS"); return 1
    B = json.load(open(os.path.join(rd, "board.json")))
    CB = json.load(open(os.path.join(rd, "claims_board.json")))
    if ds[-1] not in CB["out"]:
        FAILS.append(f"claims: {ds[-1]} had no SUPPORT vote and must be OUT; out = {CB['out']}")
    for t, n in CB["names"].items():
        for c in n["claims"]:
            if c["author"] in c["reviewers"] or any(FAMILY[r] == FAMILY[c["author"]] for r in c["reviewers"]) or len(c["reviewers"]) != 2:
                FAILS.append(f"claims: {c['claim_id']} routed to {c['reviewers']} -- must be 2 reviewers, never the author or its family")
    # ---- 6. CROSS (tier 1, seats): synthetic rulings copied from the packet each seat was handed ----
    # Seeds: DROP_NAME has every support claim REFUTED (must DROP at tier 1); REFUTE_NAME has one REFUTE beside a CONFIRM
    # (survives, and the refute becomes a PAIR); one reviewer on DROP_NAME changes its mind on the evidence.
    drop_name = ds[2] if len(ds) > 4 else None
    refute_name = ds[0]
    tie_name = ds[3] if len(ds) > 4 else None
    claim_at = {c["claim_id"]: (t, i, c) for t, n in CB["names"].items() for i, c in enumerate(n["claims"])}
    mover = None
    if drop_name and CB["names"][drop_name]["claims"]:
        mover = CB["names"][drop_name]["claims"][0]["reviewers"][0]

    def blind(v, t):
        n = CB["names"][t]
        return "SUPPORT" if v in n["support"] else "OPPOSE" if v in n["oppose"] else "ABSTAIN"
    for v in DECIDERS:
        pk_path = os.path.join(rd, "claims_packets", f"{v}.json")
        if not os.path.exists(pk_path):
            FAILS.append(f"CLAIMS: no claims packet for {v}"); continue
        pk = json.load(open(pk_path))
        if [c["claim_id"] for c in pk["claims"]] != CB["routing"].get(v, []):
            FAILS.append(f"CLAIMS: {v}'s packet does not hold exactly its routed claims")
        rows = []
        for c in pk["claims"]:
            t, i, cc = claim_at[c["claim_id"]]
            ridx = cc["reviewers"].index(v)
            ruling = "CONFIRM"
            if t == drop_name and cc["kind"] == "for":
                ruling = "REFUTE"
            if t == refute_name and i == 0 and ridx == 0:
                ruling = "REFUTE"
            r = c.get("row") or {}
            m = c.get("mtf") or {}
            grid = {fr: (str((m.get(fr) or {}).get("summary") or "not served")[:90]) for fr in ("W", "D", "H1")}
            moved = (v == mover and t == drop_name)
            rows.append({"claim_id": c["claim_id"], "ticker": t, "ruling": ruling,
                         "evidence": f"dry run: sc_momentum {r.get('sc_momentum')} structure {r.get('structure')} from my packet",
                         "tf": grid, "stance_after": "OPPOSE" if moved else c["your_blind_vote"], "changed_mind": moved,
                         "what_moved_me": "dry run: the support claims were refuted on the weekly frame" if moved else None})
        form = {"voice": v, "date": a.date, "rulings": rows}
        f = os.path.join(rd, "forms", "cross", f"{v}.json"); json.dump(form, open(f, "w"), indent=1)
        res = validate(f, rd, "--kind", "cross", "--claims", "claims_board.json")
        if res.get("result") != "OK":
            FAILS.append(f"CROSS {v}: REJECT {res.get('errors')[:3]}")
    # seeded bad: a ruling with no 1-hour frame must be refused (R39)
    bad = json.load(open(os.path.join(rd, "forms", "cross", "wyckoff.json")))
    if bad["rulings"]:
        del bad["rulings"][0]["tf"]["H1"]
        bf = os.path.join(rd, "forms", "cross_bad_noH1.json"); json.dump(bad, open(bf, "w"))
        res = validate(bf, rd, "--kind", "cross", "--claims", "claims_board.json", expect_reject=True)
        if res.get("result") != "REJECT":
            FAILS.append("R39: a cross ruling without tf.H1 was ACCEPTED")
    # ---- 7. FUNNEL + PAIR (code) ----
    step("claims-score", [sys.executable, PIPE, "claims-score", "--claims", "claims_board.json", "--rulings", "forms/cross", "--date", a.date, "--out", "funnel.json"], rd)
    if not os.path.exists(os.path.join(rd, "funnel.json")):
        FAILS.append("FUNNEL produced no funnel.json")
        json.dump({"date": a.date, "steps": STEPS, "fails": FAILS, "ok": False}, open(os.path.join(rd, "dryrun_report.json"), "w"), indent=1)
        print("\nDRY RUN FAILED at FUNNEL"); return 1
    FN = json.load(open(os.path.join(rd, "funnel.json")))
    if drop_name and drop_name not in FN["dropped"]:
        FAILS.append(f"claims-score: {drop_name} had every support claim refuted but is {FN['names'][drop_name]['status']}")
    if refute_name not in FN["survivors"]:
        FAILS.append(f"claims-score: {refute_name} (1 refute beside confirms) should SURVIVE; it is {FN['names'][refute_name]['status']}")
    if mover and not any(x["voice"] == mover and x["ticker"] == drop_name for x in FN["measurement"]["stances_changed"]):
        FAILS.append(f"claims-score: {mover}'s change of mind on {drop_name} is not in the measurement")
    step("pair", [sys.executable, PIPE, "pair", "--claims", "claims_board.json", "--rulings", "forms/cross", "--funnel", "funnel.json", "--mtf", "mtf.json",
                  "--date", a.date, "--out", "pairs.json", "--packets-dir", "tier2_packets"], rd)
    PR = json.load(open(os.path.join(rd, "pairs.json"))) if os.path.exists(os.path.join(rd, "pairs.json")) else {"pairs": []}
    if not any(p["ticker"] == refute_name for p in PR["pairs"]):
        FAILS.append(f"pair: the seeded REFUTE on {refute_name} produced no pair")
    # ---- 8. TIER2 (seats): answer every pair, decide every survivor. TIE_NAME is seeded 3 ACT_NOW / 3 WAIT -> WATCH ----
    for i, v in enumerate(DECIDERS):
        pk = json.load(open(os.path.join(rd, "tier2_packets", f"{v}.json")))
        answers = [{"pair_id": p["pair_id"], "ticker": p["ticker"], "to": p["refuter"], "concede": False,
                    "text": "dry run: 'refuted on my packet' -- my method's test still holds on the daily frame; I hold."} for p in pk["answer_pairs"]]
        decs = []
        for s_ in pk["survivors"]:
            t = s_["ticker"]
            if t == tie_name:
                stance, timing = ("ABSTAIN", None) if v == "wyckoff" else ("SUPPORT", "ACT_NOW" if i < 3 else "WAIT")
            else:
                stance, timing = "SUPPORT", ("ACT_NOW" if i < 4 else "WAIT")
            d_ = {"ticker": t, "stance": stance, "wrong_if": "dry run: close back under the 20-day average",
                  "market_void": ("SPY close_below ma_50" if i < 3 else ("QQQ close_below ma_50" if i == 3 else None)) if stance == "SUPPORT" else None,
                  "reason": "dry run: synthetic decision from the served grid", "timing": timing, "trigger": None}
            if stance == "SUPPORT":
                d_["trigger"] = ({"word": "h1_close_above:bar_high", "tf": "H1", "plain": "dry run: an hourly close over yesterday's high"} if timing == "ACT_NOW"
                                 else {"word": "in_zone:ma_20", "tf": "D", "plain": "dry run: back to the 20-day average, then the hourly trigger"})
            decs.append(d_)
        form = {"voice": v, "date": a.date, "answers": answers, "decisions": decs}
        f = os.path.join(rd, "forms", "tier2", f"{v}.json"); json.dump(form, open(f, "w"), indent=1)
        res = validate(f, rd, "--kind", "tier2", "--pairs", "pairs.json", "--funnel", "funnel.json")
        if res.get("result") != "OK":
            FAILS.append(f"TIER2 {v}: REJECT {res.get('errors')[:3]}")
    bad = json.load(open(os.path.join(rd, "forms", "tier2", "oneil.json")))
    if bad["decisions"] and bad["decisions"][0].get("trigger"):
        bad["decisions"][0]["trigger"]["word"] = "h1_close_above:644.24"
        bf = os.path.join(rd, "forms", "tier2_bad_number.json"); json.dump(bad, open(bf, "w"))
        res = validate(bf, rd, "--kind", "tier2", "--pairs", "pairs.json", "--funnel", "funnel.json", expect_reject=True)
        if res.get("result") != "REJECT":
            FAILS.append("R40/D123: a trigger with a bare number as its level was ACCEPTED")
    # ---- 9. TIMING (code) ----
    step("decide-timing", [sys.executable, PIPE, "decide-timing", "--tier2", "forms/tier2", "--funnel", "funnel.json", "--phase4", "phase4.json",
                           "--export", "aqe_daily_export.json", "--board", "board.json", "--date", a.date, "--out", "decision.json"], rd)
    DEC_ = json.load(open(os.path.join(rd, "decision.json"))) if os.path.exists(os.path.join(rd, "decision.json")) else {"names": {}, "market_kill": None}
    if tie_name in DEC_["names"] and DEC_["names"][tie_name]["proposal"] != "WATCH":
        FAILS.append(f"decide-timing: {tie_name} was seeded ACT_NOW 3 / WAIT 3 -- the tie must be WATCH, got {DEC_['names'][tie_name]['proposal']}")
    if not DEC_.get("market_kill") or DEC_["market_kill"].get("symbol") != "SPY":
        FAILS.append(f"decide-timing: the modal market_void (SPY close_below ma_50) is not the market kill: {DEC_.get('market_kill')}")
    # ---- 10. SLATE (Chair): verdict + ONE trigger COPIED from decision.json; over 15 -> most SUPPORT, ties most ACT_NOW ----
    slated = [(t, n) for t, n in DEC_["names"].items() if n["proposal"] in ("ADVANCE", "WATCH")]
    slated.sort(key=lambda tn: (-tn[1]["counts"]["support"], -tn[1]["counts"]["act_now"], ds.index(tn[0])))
    keep, excl = slated[:15], slated[15:]
    tickets = []
    for t, n in keep:
        bn = B["names"][[x["ticker"] for x in B["names"]].index(t)]
        tg = n["trigger"]
        tickets.append({"ticker": t, "verdict": n["proposal"], "entry_trigger": tg["plain"], "trigger": {"word": tg["word"], "tf": tg["tf"], "plain": tg["plain"]},
                        "wrong_if": "close back under the 20-day average", "horizon_sessions": n["horizon_sessions"] or 7,
                        "why_agreed": "dry run: " + ", ".join(n["seats"]["support"][:3]) + " support on served figures",
                        "dissent": [{"voice": v, "why": "dry run dissent"} for v in n["seats"]["oppose"]],
                        "sources": [f"r2:{v}" for v in DECIDERS], "timing_count": dict(n["counts"])})
    slate = {"date": a.date, "chair": "chair", "tickets": tickets, "market_kill": DEC_.get("market_kill")}
    sf = os.path.join(rd, "slate.json"); json.dump(slate, open(sf, "w"), indent=1)
    json.dump({"date": a.date, "excluded": [{"ticker": t, "support": n["counts"]["support"], "act_now": n["counts"]["act_now"]} for t, n in excl]},
              open(os.path.join(rd, "slate_excluded.json"), "w"), indent=1)
    res = validate(sf, rd, "--kind", "slate", "--phase4", "phase4.json", "--decision", "decision.json")
    if res.get("result") != "OK":
        FAILS.append(f"SLATE: REJECT {res.get('errors')}")
    if tickets:
        bad = json.loads(json.dumps(slate)); bad["tickets"][0]["verdict"] = "WATCH" if tickets[0]["verdict"] == "ADVANCE" else "ADVANCE"
        bf = os.path.join(rd, "slate_bad_verdict.json"); json.dump(bad, open(bf, "w"))
        res = validate(bf, rd, "--kind", "slate", "--phase4", "phase4.json", "--decision", "decision.json", expect_reject=True)
        if res.get("result") != "REJECT":
            FAILS.append("R40: a slate ticket whose verdict differs from decision.json was ACCEPTED")
    # ---- 7. RATIFY: 0 objections on most; 2 on the split name; 4 on the last ticket (DROPPED) ----
    st = [x["ticker"] for x in tickets]
    for i, v in enumerate(DECIDERS):
        rows = []
        for t in st:
            ans = "AGREE"
            if t == split_name and i < 2: ans = "OBJECT"
            if t == st[-1] and i < 4: ans = "OBJECT"
            if t == st[0] and i == 6: ans = "AGREE_WITH_RESERVATION"
            r = {"ticker": t, "answer": ans}
            if ans == "OBJECT": r.update({"objection": "dry run: no test of the break yet", "would_clear": "a hold above the pivot on a down day"})
            if ans == "AGREE_WITH_RESERVATION": r["reservation"] = "dry run: size it small until the test"
            rows.append(r)
        f = os.path.join(rd, "forms", "ratify", f"{v}.json"); json.dump({"voice": v, "date": a.date, "round": 1, "tickets": rows}, open(f, "w"))
        res = validate(f, rd, "--kind", "ratify", "--slate", "slate.json")
        if res.get("result") != "OK":
            FAILS.append(f"RATIFY {v}: REJECT {res.get('errors')}")
    # ---- 8. QA note, one hold, re-ratify the held ticket ----
    qa = {"voice": QA, "date": a.date, "evidence_read": [{"voice": v, "read": True} for v in DECIDERS], "shared_anchors": ["sc_momentum"],
          "unanswered_points": [], "slate_says_what_deciders_said": True, "note": "dry run QA note", "holds": [{"ticker": split_name, "question": "was the break tested?"}] if split_name in st else []}
    qf = os.path.join(rd, "forms", "qa", f"{QA}.json"); json.dump(qa, open(qf, "w"))
    res = validate(qf, rd, "--kind", "qa", "--slate", "slate.json")
    if res.get("result") != "OK":
        FAILS.append(f"QA: REJECT {res.get('errors')}")
    if qa["holds"]:
        # the hold round (RUN.yaml QA): one floor message per decider on the held ticket, then floor-check counts it
        for v in DECIDERS:
            m = {"voice": v, "date": a.date, "ticker": split_name, "msg_id": f"{v}-{split_name}-h1", "to": "room", "in_reply_to": None,
                 "text": "dry run: answering the hold -- the test held three closes on the daily frame.", "stance_now": "SUPPORT", "changed_mind": False}
            f = os.path.join(rd, "forms", "floor2", f"{m['msg_id']}.json"); json.dump(m, open(f, "w"))
            res = validate(f, rd, "--kind", "floor", "--phase4", "phase4.json")
            if res.get("result") != "OK":
                FAILS.append(f"FLOOR2 {m['msg_id']}: REJECT {res.get('errors')}")
        step("floor-check (hold round)", [sys.executable, PIPE, "floor-check", "--messages", "forms/floor2", "--board", "board.json", "--qa", qf, "--out", "floor_check.json"], rd)
        step("slate-cut", [sys.executable, PIPE, "slate-cut", "--slate", "slate.json", "--qa", qf, "--out", "slate_held.json"], rd)
        os.makedirs(os.path.join(rd, "forms", "ratify2"), exist_ok=True)
        for i, v in enumerate(DECIDERS):
            r = {"ticker": split_name, "answer": "OBJECT" if i < 1 else "AGREE"}
            if i < 1: r.update({"objection": "dry run", "would_clear": "x"})
            f = os.path.join(rd, "forms", "ratify2", f"{v}.json"); json.dump({"voice": v, "date": a.date, "round": 2, "tickets": [r]}, open(f, "w"))
            res = validate(f, rd, "--kind", "ratify", "--slate", "slate_held.json")
            if res.get("result") != "OK":
                FAILS.append(f"RATIFY2 {v}: REJECT {res.get('errors')}")
    # ---- 9. DECIDE ----
    cmd = [sys.executable, PIPE, "ratify-count", "--slate", "slate.json", "--ratifications", "forms/ratify", "--board", "board.json",
           "--cross", "forms/cross", "--tier2", "forms/tier2",
           "--qa", qf, "--phase4", "phase4.json", "--date", a.date, "--out", "consensus.json", "--record", "committee_record.json"]
    if qa["holds"]:
        cmd += ["--ratifications2", "forms/ratify2", "--messages2", "forms/floor2"]
    step("ratify-count", cmd, rd)
    C = {c["ticker"]: c for c in json.load(open(os.path.join(rd, "consensus.json")))}
    if st and C[st[-1]]["status"] != "DROPPED":
        FAILS.append(f"ratify-count: {st[-1]} had 4 objections but status {C[st[-1]]['status']}")
    if qa["holds"] and C[split_name]["status"] != "CONTESTED":
        FAILS.append(f"ratify-count: held {split_name} re-ratified with 1 objection but status {C[split_name]['status']}")
    REC = json.load(open(os.path.join(rd, "committee_record.json"))) if os.path.exists(os.path.join(rd, "committee_record.json")) else {"rows": []}
    if mover and not any(r["voice"] == mover and r["ticker"] == drop_name and r.get("changed_mind") and r.get("cross_rulings") for r in REC["rows"]):
        FAILS.append(f"ratify-count: the record does not carry {mover}'s cross rulings and change of mind on {drop_name}")
    if not any(r.get("tier2_trigger") for r in REC["rows"]):
        FAILS.append("ratify-count: no tier-2 trigger reached the record")
    step("record-verdicts", [sys.executable, PIPE, "record-verdicts", "--consensus", "consensus.json", "--candidates", "candidate_set.json", "--phase4", "phase4.json",
                             "--ledger", "verdict_ledger.json", "--date", a.date], rd)
    # ---- 10. CONDITIONS / REPEAT-WATCH / BRACKET / LEVELS / CARDS ----
    step("conditions compile", [sys.executable, COND, "compile", "--consensus", "consensus.json", "--forms", "forms/r2/*.json", "--export", "aqe_daily_export.json",
                                "--candidates", "candidate_set.json", "--date", a.date, "--out", "conditions.json", "--md", "conditions.md", "--html", "conditions.html"], rd)
    json.dump({"schema": "broker_stops.v1", "date": a.date, "positions": [], "note": "dry run: no broker read"}, open(os.path.join(rd, "broker_stops.json"), "w"))
    step("cards triggers", [sys.executable, CARDS, "triggers", "--conditions", "conditions.json", "--export", "aqe_daily_export.json", "--broker-stops", "broker_stops.json", "--out", "cards.json"], rd)
    step("repeat-watch", [sys.executable, PIPE, "repeat-watch", "--ledger", "phase4_ledger.json", "--verdicts", "verdict_ledger.json", "--date", a.date, "--out", "repeat_watch.json"], rd)
    step("purity_check", [sys.executable, PURITY, "--export", "aqe_daily_export.json", "--tally", "tally.json", "--candidates", "candidate_set.json", "--pm-lens", "pm_lens.json", "--out", "purity_check.json"], rd)
    step("brackets", [sys.executable, PIPE, "brackets", "--consensus", "consensus.json", "--phase4", "phase4.json", "--export", "aqe_daily_export.json", "--date", a.date, "--out", "brackets.json"], rd)
    step("repeatmarks", [sys.executable, PIPE, "repeatmarks", "--ledger", "verdict_ledger.json", "--consensus", "consensus.json", "--brackets", "brackets.json", "--date", a.date, "--out", "repeat_marks.json"], rd)
    lv_help = subprocess.run([sys.executable, LEVELS, "emit", "-h"], capture_output=True, text=True).stdout
    lv_slate = ["--slate", "slate.json"] if "--slate" in lv_help else []
    if not lv_slate:
        print("  note pma_levels.py emit has no --slate yet: the market kill is not carried into pma_levels.json (declared)")
    step("levels emit", [sys.executable, LEVELS, "emit", "--date", a.date, "--window", "3", "--conditions", "conditions.json", *lv_slate, "--out", "pma_levels.json"], rd)
    if lv_slate and os.path.exists(os.path.join(rd, "pma_levels.json")):
        LV = json.load(open(os.path.join(rd, "pma_levels.json")))
        if (LV.get("market_kill") or {}).get("plain") != (slate.get("market_kill") or {}).get("plain"):
            FAILS.append(f"LEVELS: market_kill {LV.get('market_kill')} is not the slate's {slate.get('market_kill')}")
        if "no_buy" in json.dumps(LV) or "arabolic" in json.dumps(LV):
            FAILS.append("R41: a Valen no-buy / parabolic flag reached pma_levels.json")
    # words file: the brief-writer's output, synthetic but complete (the renderer refuses gaps)
    adv = [t for t, c in C.items() if c["verdict"] == "ADVANCE"]; hold = [t for t, c in C.items() if c["verdict"] == "HOLD-FOR-CONDITIONS"]; pas = [t for t, c in C.items() if c["verdict"] == "PASS"]
    words = {"session_label": f"DRY RUN {a.date}", "stance_pill": "NEUTRAL", "bottom_line": {"headline": "dry run", "paragraph": "synthetic words; numbers from the run files", "stats": [{"value": "x", "label": "l"}] * 4},
             "market": {"what_happened": [{"lead": "a", "text": "b"}], "weather": [{"lead": "c", "text": "d"}]}, "money": [{"group": "g", "read": "r", "meaning": "m"}],
             "book": [{"ticker": h["ticker"], "read_pill": "HOLD", "tone": "warn", "why": "dry run"} for h in (EX.get("held_positions") or [])], "changed": ["dry run"],
             "cards": {t: {"case": "dry run", "why": "dry run", "readiness": "Ready now", "readiness_tone": "ok"} for t in adv}, "holds": {t: "dry run" for t in hold}, "passes": {t: "dry run" for t in pas},
             "plan": ["dry run"], "caveats": ["DRY RUN -- synthetic seat forms, no judgment"],
             "weather": {k: f"Read: {k} (dry run)." for k in ("stance", "gex", "heartbeat", "positioning", "volatility", "divergence", "call", "cot", "checklist", "turning", "themes", "groups")}}
    json.dump(words, open(os.path.join(rd, "cards_text.json"), "w"))
    step("cards render", [sys.executable, CARDS, "render", "--text", "cards_text.json", "--consensus", "consensus.json", "--export", "aqe_daily_export.json", "--cards", "cards.json",
                          "--brackets", "brackets.json", "--broker-stops", "broker_stops.json", "--phase4", "phase4.json", "--valen", "aqe_valen_dashboard.json",
                          "--crown", "aqe_crown_macro.json", "--scorecard", "nosc.md", "--out", f"pma_cards_{a.date}.html"], rd)
    # ---- 11. the Checker on the result ----
    sys.path.insert(0, HERE)
    import preflight_run
    run_steps = [x["name"] for x in preflight_run.mini_yaml(open(os.path.join(PMA_DIR, "RUN.yaml"), encoding="utf-8").read())["steps"]]
    funnel_steps = ("MTF", "CLAIMS", "CROSS", "FUNNEL", "PAIR", "TIER2", "TIMING")
    for s_ in funnel_steps:       # R38/R39: the new steps' produces[] must be satisfied for real -- no --force-incomplete
        if s_ in run_steps:
            step(f"tick {s_} (produces[] present, not forced)", [sys.executable, REG, "tick", "--step", s_, "--status", "done", "--note", "dry run"], rd)
    for s_ in [x for x in run_steps if x not in funnel_steps]:
        subprocess.run([sys.executable, REG, "tick", "--step", s_, "--status", "done", "--force-incomplete", "--note", "dry run"], cwd=rd, capture_output=True, text=True)
    step("checker chain", [sys.executable, CHECK, "chain", "--run-dir", rd, "--date", a.date, "--levels", os.path.join(rd, "pma_levels.json")], rd)
    rep = {"date": a.date, "output_dir": od, "run_dir": rd, "room": ds, "contested": B["contested"], "slate": st,
           "funnel": {"survivors": FN["survivors"], "dropped": FN["dropped"], "out": FN["out"], "measurement": FN["measurement"]},
           "pairs": len(PR["pairs"]), "decision": {t: n["proposal"] for t, n in DEC_["names"].items()}, "market_kill": DEC_.get("market_kill"),
           "verdicts": {t: (c["verdict"], c["status"]) for t, c in C.items()}, "steps": STEPS, "fails": FAILS, "ok": not FAILS}
    json.dump(rep, open(os.path.join(rd, "dryrun_report.json"), "w"), indent=1)
    print("\nDRY RUN " + ("PASSED -- every hop validated, every tool step ran, the Cards rendered" if not FAILS else f"FAILED ({len(FAILS)}):"))
    for f in FAILS:
        print("  - " + f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
