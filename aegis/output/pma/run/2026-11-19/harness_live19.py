#!/usr/bin/env python3
"""Replay harness: run the committee again on the frozen r2 inputs, through TIMING, local only.
usage: replay.py <tag> prep | prompts <STEP> | collect <STEP> | summary
STEPS: NOMINATE CHALLENGE VOTE CROSS TIER2
"""
import json, os, shutil, subprocess, sys, glob, math

DATE = "2026-11-19"
SRC = "/home/user/pma_run/2026-11-19"
T = "/home/user/AQE/aegis/plugin/aegis-core/skills/pma/tools"
PLUG = "/home/user/AQE/aegis/plugin"
SEATS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]
CORE = PLUG + "/aegis-core"
VOICES = PLUG + "/aegis-voices"
CONTRACTS = CORE + "/skills/pma/contracts"


def run(R, *args, quiet=True):
    p = subprocess.run(["python3"] + list(args), cwd=R, capture_output=True, text=True)
    out = (p.stdout + p.stderr)
    out = "\n".join(l for l in out.splitlines() if "Deprecat" not in l and "utcnow" not in l)
    return p.returncode, out


def reg(R, *a):
    return run(R, T + "/registrar.py", "--manifest", "run_manifest.json", *a)


def prep(R, tag):
    os.makedirs(R, exist_ok=True)
    for f in ["aqe_daily_export_wu.json", "aqe_crown_macro.json", "aqe_valen_dashboard.json", "candidate_set.json",
              "fundamentals_pack.json", "voice_menus.json"]:
        shutil.copy(f"{SRC}/{f}", f"{R}/{f}")
    if os.path.exists(f"{R}/packets"):
        shutil.rmtree(f"{R}/packets")
    shutil.copytree(f"{SRC}/packets", f"{R}/packets")
    for d in ["forms/r1", "forms/challenge", "forms/r2", "forms/cross", "forms/tier2", "prompts"]:
        os.makedirs(f"{R}/{d}", exist_ok=True)
    print(reg(R, "init", "--date", DATE, "--rerun", tag)[1])
    print(run(R, T + "/pm_lens.py", "--export", "aqe_daily_export_wu.json", "--out", "pm_lens.json")[1][-200:])


HEAD = ("You are the {SEAT} seat (voice \"{seat}\") on the Aegis investment committee. Session: Thursday 2026-11-19 SGT "
        "(the US session of Thu 19 Nov), data: the Wednesday 2026-11-18 US close.\n\n")


def card(seat):
    return f"{VOICES}/agents/voice-{seat}.md", f"{VOICES}/canon/{seat}/canon.lock.yaml"


def p_nominate(R, seat):
    c, canon = card(seat)
    return HEAD.format(SEAT=seat.upper(), seat=seat) + f"""ROUND 1 — NOMINATE, blind and isolated.

READ ONLY THESE FILES (nothing else — no other seat's packet, no other run files, no forms directory, no git history, no web):
1. Your card: {c}
2. Shared engine: {VOICES}/skills/voice-common/SKILL.md
3. Your canon: {canon}
4. Form schema: {CORE}/contracts/nomination.schema.json
5. Your packet (tab-separated, one row per candidate): {R}/packets/{seat}.tsv — read the rows themselves in full.

THE ROUND: Apply your card's checklist in order to the packet and shortlist the names your method most wants. AT MOST SIX nominations (R33); fewer is valid and must never be padded (give shortfall_reason if fewer). Each nomination: ticker, reason (<=300 chars), fields_cited, conviction 1-5, checklist_trace (one entry per checklist step on your card, in order; canon_ref C-ids; verdict pass/fail/partial/no_data), falsifier. Review EVERY held name (the Aegis book today is FLAT: no position is held; SPCX was closed on 18 Nov and RBRK on 17 Nov, so held_review is [] unless the packet shows a held name) in held_review with KEEP / TIGHTEN / EXIT-CASE and one line. Declare any menu field you needed that is absent in data_gaps [{{field, impact}}]. R1: a bracket field is never a reason to not nominate or to cap conviction. Write any figure as "field value" exactly as the packet gives it.

OUTPUT: write {R}/forms/r1/{seat}.json = {{"voice":"{seat}","date":"{DATE}","round":1,"nominations":[...],"held_review":[...],"data_gaps":[...],"declarations":[...],"shortfall_reason":null or text}}.
Validate: `cd {R} && python3 {T}/registrar.py validate --file forms/r1/{seat}.json --round 1 --candidates candidate_set.json --packet packets/{seat}.tsv`. If REJECT fix only what the error names (never change a judgment to pass), max 3 attempts. Run no other command; write no other file. Return ONLY the final validator line."""


def p_challenge(R, seat):
    return f"""You are the STEENBARGER seat (voice "steenbarger") on the Aegis investment committee — the quality-assurance seat. ROUND 1b — CHALLENGE, filed BEFORE anyone votes. Session: Thursday 2026-11-19 SGT, data: the Wednesday 2026-11-18 US close.

READ ONLY THESE FILES (nothing else):
1. Your card: {VOICES}/agents/voice-steenbarger.md
2. Shared engine: {VOICES}/skills/voice-common/SKILL.md
3. Your canon: {VOICES}/canon/steenbarger/canon.lock.yaml
4. Form schema: {CONTRACTS}/challenge.schema.json
5. Your packet (the room, with the anonymised nomination pattern): {R}/seat_packets/challenge_steenbarger.json

THE ROUND: Read the room as a whole and file crowding, extension and overlap findings (scope, ticker where it applies, kind, claim, evidence, addressed_to). You NEVER nominate and NEVER vote. A name you flag becomes CONTESTED on the board, so flag only what your evidence supports. Address each finding to the decider seat(s) whose method it most tests (oneil, minervini, livermore, elder-lens, seow, raschke, wyckoff). Set names_read to the number of room names you read. Declare every gap in data_gaps. Write figures as "field value" exactly as the packet gives. R1: a bracket field is never a reason in itself.
OUTPUT: write {R}/forms/challenge/steenbarger.json with {{"voice":"steenbarger","date":"{DATE}","seat_kind":"challenge", ...}} per the schema.
Validate: `cd {R} && python3 {T}/registrar.py validate --file forms/challenge/steenbarger.json --kind challenge --candidates candidate_set.json`. If REJECT fix only what the error names, max 3 attempts. Run no other command; write no other file. Return ONLY the final validator line."""


def parts_of(names, n=16):
    k = math.ceil(len(names) / n)
    size = math.ceil(len(names) / k)
    return [names[i:i + size] for i in range(0, len(names), size)]


def room(R):
    p = json.load(open(f"{R}/phase4.json"))
    return [x if isinstance(x, str) else x.get("ticker") for x in p["deliberation_set"]]


def p_vote(R, seat):
    c, canon = card(seat)
    names = room(R)
    parts = parts_of(names)
    n = len(parts)
    lines = "\n".join(f"- Part {i+1} of {n} → {R}/forms/r2/{seat}.part{i+1}of{n}.json, exactly these {len(pt)}: {' '.join(pt)}"
                      for i, pt in enumerate(parts))
    return HEAD.format(SEAT=seat.upper(), seat=seat) + f"""ROUND 2 — VOTE, blind (you cannot see any other seat's vote).

READ ONLY THESE FILES (nothing else — no forms directory except your own round-1 ballot, no other packet, no other run files, no git history, no web):
1. Your card: {c}
2. Shared engine: {VOICES}/skills/voice-common/SKILL.md
3. Your canon: {canon}
4. Vote schema: {CONTRACTS}/vote_round2.schema.json and case form: {CONTRACTS}/case_form.schema.json
5. Conditions block (MANDATORY on every SUPPORT): {CONTRACTS}/conditions_block.md, vocabulary {CONTRACTS}/condition_vocab.json, your method limits {CONTRACTS}/voice_primitives.json
6. THE VOTE PACKET (identical for every seat): {R}/VOTE_PACKET.txt
7. Your own round-1 ballot (for conviction_change only): {R}/forms/r1/{seat}.json

THE ROUND: vote on EVERY one of the {len(names)} deliberation-set names — SUPPORT, OPPOSE or ABSTAIN — judged exactly as your card says. Every vote carries: reason (<=500), conviction (1-5; null only on ABSTAIN), the `case` block (for, against, entry_trigger, wrong_if, horizon_sessions = YOUR own horizon, would_change_my_mind, cannot_see) — reasons BOTH ways on every name; opposing_case on every OPPOSE; self_counter on SUPPORT at conviction >=4; conditions block on every SUPPORT (levels named by FIELD, never by number; stay inside your method); conviction_change where it differs from your round-1 position. R1: a bracket field is never the basis of an OPPOSE. Each name's packet entry carries an MTF line (weekly / daily / 1-hour). Read Steenbarger's findings in the packet and answer any addressed to you inside the relevant cases. Write figures as "field value" exactly as the packet gives them.

SPLIT BALLOT: file {n} parts.
{lines}
Each file: {{"voice":"{seat}","date":"{DATE}","round":2,"votes":[...],"declarations":[...]}}. Keep each part under 24,576 bytes (aim at most ~650 bytes per vote).
VALIDATE each part: `cd {R} && python3 {T}/registrar.py validate --file forms/r2/{seat}.partNof{n}.json --round 2 --candidates candidate_set.json --phase4 phase4.json --packet VOTE_PACKET.txt --part N --of {n}`. If REJECT fix only what the error names (never change a judgment to pass), max 3 attempts per part. Run no other command, write no other file. Return ONLY the final validator lines."""


def p_cross(R, seat):
    c, canon = card(seat)
    cp = json.load(open(f"{R}/cross_parts/{seat}.json"))
    return HEAD.format(SEAT=seat.upper(), seat=seat) + f"""ROUND — TIER 1 CROSS-EXAMINATION. Your blind vote is on the record; nobody sees any ruling until the funnel is posted.

READ ONLY THESE FILES (nothing else — no other seat's ballot or ruling, no other run files, no git history, no web):
1. Your card: {c}
2. The deliberation procedure: {VOICES}/skills/voice-deliberate/SKILL.md (read TIER 1 and NEVER carefully)
3. Your canon: {canon}
4. Form schema: {CONTRACTS}/cross_ruling.schema.json
5. Your claims packet — exactly the claims routed to you: {R}/claims_packets/{seat}.json
6. Your own blind vote (to compare your stance_after / changed_mind): {R}/forms/r2/{seat}.json
7. Your part lists: {R}/cross_parts/{seat}.json

THE ROUND: rule on EVERY claim routed to you — CONFIRM, REFUTE or CANNOT_SEE — through YOUR OWN method, on the weekly / daily / 1-hour grid (fill tf.W, tf.D, tf.H1 for each claim, <=90 chars each, or 'not served'). Never restate your own case; concede only on evidence your method cares about; state stance_after on the name and set changed_mind true (with what_moved_me by field name) only if it differs from your blind vote. R1 and R41. Write figures as "field value" exactly as your packet gives them.

SPLIT FORM (~{len(cp['part1of2'])+len(cp['part2of2'])} claims): file TWO parts.
- Part 1 of 2 → {R}/forms/cross/{seat}.part1of2.json — exactly the claim_ids in "part1of2" of your part-lists file
- Part 2 of 2 → {R}/forms/cross/{seat}.part2of2.json — exactly the claim_ids in "part2of2"
Each file: {{"voice":"{seat}","date":"{DATE}","rulings":[...],"declarations":[...]}}. Under 24,576 bytes (aim <= ~600 bytes per ruling).
VALIDATE each part: `cd {R} && python3 {T}/registrar.py validate --file forms/cross/{seat}.partNof2.json --kind cross --claims claims_board.json --part N --of 2`. If REJECT fix only what the error names, max 3 attempts per part. Run no other command, write no other file. Return ONLY the two final validator lines."""


def survivors(R):
    f = json.load(open(f"{R}/funnel.json"))
    s = f["survivors"]
    return [x if isinstance(x, str) else (x.get("ticker") or x.get("name")) for x in s]


def p_tier2(R, seat):
    c, canon = card(seat)
    sv = survivors(R)
    h = math.ceil(len(sv) / 2)
    a, b = sv[:h], sv[h:]
    return HEAD.format(SEAT=seat.upper(), seat=seat) + f"""ROUND — TIER 2 DECISION (the second funnel). The first funnel is posted: {len(sv)} names survived tier-1 cross-examination.

READ ONLY THESE FILES (nothing else — no other seat's ruling or decision, no other run files, no git history, no web):
1. Your card: {c}
2. The deliberation procedure: {VOICES}/skills/voice-deliberate/SKILL.md (read TIER 2 and NEVER carefully)
3. Your canon: {canon}
4. Form schema: {CONTRACTS}/tier2.schema.json
5. Trigger vocabulary and your method's limits: {CONTRACTS}/condition_vocab.json and {CONTRACTS}/voice_primitives.json (a trigger word must be in the vocabulary, carry a FIELD level written word:field_level, and stay inside your own method's primitives)
6. Your tier-2 packet — the refutations of YOUR claims (answer each) and the survivors with their W/D/H1 grids and tier-1 tallies (decide each): {R}/tier2_packets/{seat}.json
7. Your own blind vote (for reference): {R}/forms/r2/{seat}.json

THE ROUND: (a) answer every refutation of your own claims — quote the refuter's point in ten words or fewer, answer with your method's test on the grid, concede only when the evidence is evidence your method cares about; (b) decide EVERY survivor exactly once: stance (SUPPORT / OPPOSE / ABSTAIN); on SUPPORT the timing (ACT_NOW or WAIT), ONE trigger {{word, tf (W/D/H1), plain}}, wrong_if, optional market_void (null if your method has none), reason. Judge on your own method; do not follow the room; no bracket as a reason (R1); no Valen flags (R41). Write figures as "field value" exactly as the packet gives them.

SPLIT FORM: file TWO parts.
- Part 1 of 2 → {R}/forms/tier2/{seat}.part1of2.json = ALL your answers + decisions on exactly these {len(a)} survivors: {' '.join(a)}
- Part 2 of 2 → {R}/forms/tier2/{seat}.part2of2.json = "answers": [] + decisions on exactly these {len(b)} survivors: {' '.join(b)}
Each file: {{"voice":"{seat}","date":"{DATE}","answers":[...],"decisions":[...],"declarations":[...]}}, under 24,576 bytes (aim <= ~1,000 bytes per decision).
VALIDATE each part: `cd {R} && python3 {T}/registrar.py validate --file forms/tier2/{seat}.partNof2.json --kind tier2 --pairs pairs.json --funnel funnel.json --part N --of 2`. If REJECT fix only what the error names, max 3 attempts per part. Run no other command, write no other file. Return ONLY the two final validator lines."""


def p_ratify(R, seat):
    c, canon = card(seat)
    return HEAD.format(SEAT=seat.upper(), seat=seat) + f"""ROUND — RATIFY (R34/R35). The Chair has drafted the slate from what the deciders themselves filed; you now say whether you stand behind each ticket.

READ ONLY THESE FILES (nothing else — no other seat's ratification, no other run files, no git history, no web):
1. Your card: {c}
2. The deliberation procedure: {VOICES}/skills/voice-deliberate/SKILL.md (read the RATIFY section and NEVER carefully)
3. Your canon: {canon}
4. Form schema: {CONTRACTS}/ratification.schema.json
5. The slate (every ticket, its verdict, its ONE trigger, wrong-if, horizon, why agreed and the dissents): {R}/slate.json
6. Your own tier-2 decisions, for reference: {R}/forms/tier2/{seat}.json

THE ROUND: answer EVERY ticket on the slate — AGREE, AGREE_WITH_RESERVATION (say the reservation) or OBJECT (say the one thing that would clear it). Judge each ticket on your own method: do you stand behind this verdict AND this trigger? A seat that disagrees with a ticket's trigger must OBJECT, not reserve (R40). Also give, per ticket, your committee conviction 1-5 (the form schema says where; the median of the deciders is taken by code). THE SIGNED ANCHORS (PM): 5 = textbook for my method; 4 = strong, one thing missing; 3 = yes once one named condition (X) prints; 2 = marginal; 1 = fails my method as written. R1 and R41 as everywhere. Write figures as "field value" exactly as the slate gives them. You may not edit the slate or see anyone's answer.

OUTPUT: write {R}/forms/ratify/{seat}.json per the schema (voice "{seat}", date "{DATE}"). Validate: `cd {R} && python3 {T}/registrar.py validate --file forms/ratify/{seat}.json --kind ratify --slate slate.json`. If REJECT fix only what the error names (never change a judgment to pass), max 3 attempts. Run no other command; write no other file. Return ONLY the final validator line."""


GEN = {"NOMINATE": p_nominate, "CHALLENGE": p_challenge, "VOTE": p_vote, "CROSS": p_cross, "TIER2": p_tier2, "RATIFY": p_ratify}


def prompts(R, step):
    d = f"{R}/prompts/{step}"
    os.makedirs(d, exist_ok=True)
    seats = ["steenbarger"] if step == "CHALLENGE" else SEATS
    for s in seats:
        open(f"{d}/{s}.txt", "w").write(GEN[step](R, s))
        print(f"{d}/{s}.txt")


def commit(R, step, f, seat):
    print(reg(R, "commit", "--step", step, "--file", f, "--seat", seat)[1].splitlines()[-1:])


def collect(R, step):
    if step == "NOMINATE":
        have = [s for s in SEATS if os.path.exists(f"{R}/forms/r1/{s}.json")]
        for s in have:
            rc, out = reg(R, "validate", "--file", f"forms/r1/{s}.json", "--round", "1", "--candidates", "candidate_set.json", "--packet", f"packets/{s}.tsv")
            print(s, out.strip()[:90]); commit(R, "NOMINATE", f"forms/r1/{s}.json", s)
        print(run(R, T + "/pma_pipeline.py", "tally", "--nominations", "forms/r1", "--out", "tally.json")[1][-200:])
        print(run(R, T + "/pma_pipeline.py", "rank", "--tally", "tally.json", "--candidates", "candidate_set.json", "--export", "aqe_daily_export_wu.json", "--cap", "24", "--strong-seats", "0", "--swing-seats", "0", "--unr-seats", "0", "--door-budget", "0", "--machine-add", "0", "--pm-lens", "pm_lens.json", "--pm-lens-min", "5", "--out", "phase4.json")[1][-400:])
        print(run(R, T + "/mtf.py", "build", "--grid", "/home/user/AQE/aegis/output/committee_data/mtf_grid.json", "--phase4", "phase4.json", "--date", DATE, "--out", "mtf.json")[1][-200:])
        print(run(R, T + "/pma_pipeline.py", "challenge-packets", "--menus", "voice_menus.json", "--universe", "candidate_set.json", "--phase4", "phase4.json", "--forms", "forms/r1", "--date", DATE, "--outdir", "seat_packets", "--seats", "steenbarger")[1][-200:])
    elif step == "CHALLENGE":
        rc, out = reg(R, "validate", "--file", "forms/challenge/steenbarger.json", "--kind", "challenge", "--candidates", "candidate_set.json")
        print(out.strip()[:90]); commit(R, "CHALLENGE", "forms/challenge/steenbarger.json", "steenbarger")
        print(run(R, T + "/pma_pipeline.py", "r2digest", "--export", "aqe_daily_export_wu.json", "--fundamentals", "fundamentals_pack.json", "--steenbarger", "forms/challenge/steenbarger.json", "--crown", "aqe_crown_macro.json", "--valen", "aqe_valen_dashboard.json", "--mtf", "mtf.json", "--out", "VOTE_PACKET.txt")[1][-200:])
    elif step == "VOTE":
        for s in SEATS:
            rc, out = reg(R, "merge", "--glob", f"forms/r2/{s}.part*.json", "--out", f"forms/r2/{s}.json", "--phase4", "phase4.json")
            print(s, out.strip()[:80]);
            if os.path.exists(f"{R}/forms/r2/{s}.json"): commit(R, "VOTE", f"forms/r2/{s}.json", s)
        print(run(R, T + "/pma_pipeline.py", "board", "--round2", "forms/r2", "--phase4", "phase4.json", "--challenge", "forms/challenge/steenbarger.json", "--date", DATE, "--out", "board.json")[1][-300:])
        print(run(R, T + "/pma_pipeline.py", "claims", "--round2", "forms/r2", "--phase4", "phase4.json", "--challenge", "forms/challenge/steenbarger.json", "--mtf", "mtf.json", "--date", DATE, "--out", "claims_board.json", "--packets-dir", "claims_packets")[1][-300:])
        os.makedirs(f"{R}/cross_parts", exist_ok=True)
        for s in SEATS:
            cl = json.load(open(f"{R}/claims_packets/{s}.json"))["claims"]
            ids = [c["claim_id"] for c in cl]; h = (len(ids) + 1) // 2
            json.dump({"voice": s, "part1of2": ids[:h], "part2of2": ids[h:]}, open(f"{R}/cross_parts/{s}.json", "w"))
    elif step == "CROSS":
        for s in SEATS:
            rc, out = reg(R, "merge", "--kind", "cross", "--glob", f"forms/cross/{s}.part*.json", "--claims", "claims_board.json", "--out", f"forms/cross/{s}.json")
            print(s, out.strip()[:80])
            if os.path.exists(f"{R}/forms/cross/{s}.json"): commit(R, "CROSS", f"forms/cross/{s}.json", s)
        print(run(R, T + "/pma_pipeline.py", "claims-score", "--claims", "claims_board.json", "--rulings", "forms/cross", "--date", DATE, "--out", "funnel.json")[1][-500:])
        print(run(R, T + "/pma_pipeline.py", "pair", "--claims", "claims_board.json", "--rulings", "forms/cross", "--funnel", "funnel.json", "--mtf", "mtf.json", "--date", DATE, "--out", "pairs.json", "--packets-dir", "tier2_packets")[1][-300:])
    elif step == "TIER2":
        for s in SEATS:
            rc, out = reg(R, "merge", "--kind", "tier2", "--glob", f"forms/tier2/{s}.part*.json", "--pairs", "pairs.json", "--funnel", "funnel.json", "--out", f"forms/tier2/{s}.json")
            print(s, out.strip()[:80])
            if os.path.exists(f"{R}/forms/tier2/{s}.json"): commit(R, "TIER2", f"forms/tier2/{s}.json", s)
        print(run(R, T + "/pma_pipeline.py", "decide-timing", "--tier2", "forms/tier2", "--funnel", "funnel.json", "--phase4", "phase4.json", "--date", DATE, "--out", "decision.json")[1][-1200:])


def summary(R):
    d = json.load(open(f"{R}/decision.json"))
    rows = d.get("survivors") or d.get("tickets") or d.get("names") or []
    out = {}
    for r in (rows if isinstance(rows, list) else rows.values()):
        out[r.get("ticker")] = (r.get("verdict") or r.get("proposal"), r.get("support"), r.get("act_now"), r.get("wait"))
    print(json.dumps(out))


if __name__ == "__main__":
    tag = sys.argv[1]
    R = f"/home/user/pma_run/{DATE}"
    cmd = sys.argv[2]
    if cmd == "prep": prep(R, tag)
    elif cmd == "prompts": prompts(R, sys.argv[3])
    elif cmd == "collect": collect(R, sys.argv[3])
    elif cmd == "summary": summary(R)
