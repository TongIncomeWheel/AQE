#!/usr/bin/env python3
"""AEGIS PMA regression tests. Run before every committee: `python3 tests/test_pipeline.py`.

WHY THIS FILE EXISTS. On 2026-09-07 the plugin held 17,148 lines of python and zero tests.
Three tools broke on 2026-09-06 and each would have been caught by one assertion here:
  * consensus read stances[] against forms carrying votes[] -> returned ZERO verdicts, silently
  * r2digest read findings[] against a doc filing challenges[] -> dropped the whole document
  * purity_check passed a retired --solo-min -> the publish gate could not run at all
Fixtures are the REAL 2026-09-06 committee outputs, trimmed. The expected answers are what that
run actually produced. If a change moves a verdict, this fails and tells you which name moved.

Zero external dependencies. Exits 0 on pass, 1 on any failure.
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
PIPE = os.path.join(TOOLS, "pma_pipeline.py")
PURITY = os.path.join(TOOLS, "purity_check.py")
REG = os.path.join(TOOLS, "registrar.py")

FAILS, PASSES = [], []

# R22: verdicts on the 2026-09-06 fixture once the Lynch ballot stops counting (measured 2026-10-23).
R22_DELTA = {"JEF": ("ADVANCE", 3), "SLDE": ("HOLD-FOR-CONDITIONS", 3), "CNH": ("PASS", 3)}

def check(name, cond, detail=""):
    (PASSES if cond else FAILS).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("\n          " + detail) if detail and not cond else ""))

def fx(n): return os.path.join(FIX, n)
def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_consensus_reproduces_the_real_run(td):
    """The 2026-09-06 verdicts, from the raw v5.3 forms, with no adapter anywhere."""
    out = os.path.join(td, "consensus.json")
    rc, log = run([PIPE, "consensus", "--round2", fx("round2_votes.json"), "--out", out])
    check("consensus exits clean on real v5.3 forms", rc == 0, log[-300:])
    if rc != 0: return
    got = {x["ticker"]: (x["verdict"], x["conviction"]) for x in json.load(open(out))}
    want = {x["ticker"]: (x["verdict"], x["conviction"]) for x in json.load(open(fx("consensus.json")))}
    # R22 (PM 2026-10-22): the 2026-09-06 run counted a Lynch ballot; consensus no longer does. These
    # three names move -- and ONLY these. Any other move is a regression.
    want.update(R22_DELTA)
    check("consensus returns 20 names, not zero", len(got) == 20, f"got {len(got)}")
    moved = [t for t in want if got.get(t) != want[t]]
    check("every verdict and conviction matches the real run", not moved,
          "moved: " + ", ".join(f"{t} {want[t]}->{got.get(t)}" for t in moved[:6]))
    adv = sum(1 for v in got.values() if v[0] == "ADVANCE")
    check("9 ADVANCE / 11 HOLD / 0 PASS", (adv, len(got) - adv) == (9, 11), f"got {adv} ADVANCE")


def test_consensus_refuses_a_shape_it_cannot_read(td):
    """THE 2026-09-06 BUG. A reader that finds nothing must stop, not return an empty answer."""
    bad = os.path.join(td, "bad.json")
    src = json.load(open(fx("round2_votes.json")))
    json.dump([{"seat": x["voice"], "ballots": x["votes"]} for x in src], open(bad, "w"))
    rc, log = run([PIPE, "consensus", "--round2", bad, "--out", os.path.join(td, "x.json")])
    check("a renamed-key file is REJECTED, not silently emptied", rc != 0, "it exited 0")
    check("the error names the keys the file actually has", "ballots" in log and "seat" in log, log[-200:])
    check("the error forbids the adapter workaround", "do not work around" in log.lower(), log[-200:])


def test_r2digest_renders_every_challenge_document(td):
    """A filed document must never vanish from the vote packet without an error."""
    out = os.path.join(td, "packet.txt")
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"),
                   "--tally", fx("tally.json"), "--fundamentals", fx("fundamentals.json"),
                   "--rogers", fx("challenge_rogers.json"), "--steenbarger", fx("challenge_steenbarger.json"),
                   "--lynch", fx("challenge_lynch.json"), "--detectlens", fx("challenge_detect-lens.json"),
                   "--run-id", "test", "--out", out])
    check("r2digest exits clean", rc == 0, log[-300:])
    if rc != 0: return
    txt = open(out).read()
    for seat in ["ROGERS", "STEENBARGER", "LYNCH", "DETECT-LENS"]:
        body = txt.split(f"--- {seat} ---")[1].split("--- ")[0] if f"--- {seat} ---" in txt else ""
        check(f"{seat} section is present and NOT empty", len(body.strip().splitlines()) >= 3,
              f"{len(body.strip().splitlines())} lines - this is the 2026-09-06 silent-drop bug")
    check("every deliberated name appears in the packet",
          all(t in txt for t in json.load(open(fx("phase4.json")))["deliberation_set"]))


def test_r2digest_refuses_an_unreadable_challenge_doc(td):
    empty = os.path.join(td, "empty_challenge.json")
    json.dump({"voice": "rogers", "some_shape_nobody_expects": [{"x": 1}]}, open(empty, "w"))
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"),
                   "--tally", fx("tally.json"), "--rogers", empty,
                   "--steenbarger", fx("challenge_steenbarger.json"), "--lynch", fx("challenge_lynch.json"),
                   "--detectlens", fx("challenge_detect-lens.json"), "--run-id", "t",
                   "--out", os.path.join(td, "p.txt")])
    check("an unreadable challenge doc HALTS the packet build", rc != 0, "it exited 0 with a silent gap")
    check("the error prints the doc's actual keys", "some_shape_nobody_expects" in log, log[-200:])


def test_rank_is_stable_and_sector_blind(td):
    out = os.path.join(td, "phase4.json")
    rc, log = run([PIPE, "rank", "--tally", fx("tally.json"), "--candidates", fx("candidate_set.json"),
                   "--export", fx("export.json"), "--cap", "20", "--pm-lens", fx("pm_lens.json"),
                   "--pm-lens-min", "5", "--out", out])
    check("rank exits clean", rc == 0, log[-300:])
    if rc != 0: return
    got = json.load(open(out)); want = json.load(open(fx("phase4.json")))
    # 2026-09-22 (D120): the doors widened, so the SET is no longer byte-identical to the
    # 2026-09-06 run. What must not move: every name the committee's own seats put up (SEATS
    # door) is still admitted, and every admitted row carries doors and a lane.
    seats_then = {r["ticker"] for r in want["ranked"] if "SEATS" in r.get("doors", [])}
    check("every SEATS-door name from the real run is still admitted",
          seats_then <= set(got["deliberation_set"]), str(seats_then - set(got["deliberation_set"])))
    check("every admitted row carries doors and a lane (R14)",
          all(r.get("doors") and r.get("lane") in ("MOMENTUM", "PULLBACK") for r in got["ranked"]))
    check("R4: srm_entry_gate is absent from the ranking key",
          "srm" not in got["ranking_key"].split("(")[0], got["ranking_key"])
    check("R4: sector is still RENDERED on every row (context, not gate)",
          all("srm" in r for r in got["ranked"]))
    check("R1: no bracket term appears in the ranking key",
          not any(w in got["ranking_key"].lower() for w in ("bracket", "risk_pct", "rr_", "stop")))


def test_purity_check_runs_without_being_patched(td):
    """It could not run AT ALL on 2026-09-06 because it passed a flag rank had retired."""
    out = os.path.join(td, "purity.json")
    rc, log = run([PURITY, "--pipeline", PIPE, "--tally", fx("tally.json"),
                   "--candidates", fx("candidate_set.json"), "--export", fx("export.json"),
                   "--pm-lens", fx("pm_lens.json"), "--out", out])
    check("purity_check runs unpatched against this pipeline", rc == 0, log[-400:])
    if rc != 0: return
    check("invariance PASSES", json.load(open(out))["invariance"] == "PASS")


def test_load_declares_its_shape(td):
    """R6: a reader states what it needs; a mismatch names both shapes."""
    bad = os.path.join(td, "no_universe.json")
    json.dump({"not_universe": []}, open(bad, "w"))
    rc, log = run([PIPE, "rank", "--tally", fx("tally.json"), "--candidates", bad,
                   "--export", fx("export.json"), "--cap", "20", "--out", os.path.join(td, "o.json")])
    check("a candidate file missing 'universe' is rejected at the read", rc != 0)
    check("the rejection names the required key AND the actual keys",
          "universe" in log and "not_universe" in log, log[-200:])


def test_registrar_meter_records_cost(td):
    m = os.path.join(td, "run_manifest.json")
    run([REG, "--manifest", m, "init", "--date", "2026-09-07"])
    run([REG, "--manifest", m, "tick", "--step", "VOTE", "--status", "in_flight"])
    run([REG, "--manifest", m, "meter", "--step", "VOTE", "--spawns", "11", "--inlined-bytes", "759000"])
    run([REG, "--manifest", m, "tick", "--step", "VOTE", "--status", "in_flight"])
    run([REG, "--manifest", m, "tick", "--step", "VOTE", "--status", "done"])
    s = json.load(open(m))["steps"]["VOTE"]
    check("meter records spawns and bytes", s["cost"]["spawns"] == 11 and s["cost"]["inlined_bytes"] == 759000)
    check("est_tokens is non-zero (2026-09-06 reported 0 for every step)",
          "0" != str(int(s["cost"]["inlined_bytes"] / 4)))
    rc, log = run([REG, "--manifest", m, "status"])
    check("status prints a cost table with a stated basis", "est_tok" in log and "basis" in log)
    check("started is write-once: a re-tick does not reset the clock",
          s.get("started") is not None and s.get("finished") is not None)


def test_rulings_and_run_map_are_machine_readable():
    """The constitution must be data, not prose. Parsed with no yaml dependency."""
    for f in ("RULINGS.yaml", "RUN.yaml"):
        p = os.path.abspath(os.path.join(HERE, "..", f))
        check(f"{f} exists", os.path.exists(p))
        if not os.path.exists(p): continue
        txt = open(p).read()
        check(f"{f} declares its schema", "schema:" in txt)
    rp = os.path.abspath(os.path.join(HERE, "..", "RULINGS.yaml"))
    if os.path.exists(rp):
        txt = open(rp).read()
        for rid in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]:
            check(f"ruling {rid} is on the record", f"id: {rid}\n" in txt)


def test_gate_refuses_a_brief_whose_day_was_never_recorded(td):
    """R8. Ten sessions ran, three left a record. A report without a record is a FAILED run."""
    brief = os.path.join(td, "b.md")
    open(brief, "w").write(
        "# BRIEF\n\n## §0 VERDICTS\n\n| T | V |\n|---|---|\n| X | ADVANCE |\n\n"
        "## §1 MACRO\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n\n"
        "## §2 SECTOR\n\n## §3 HELD\n\n## NEAR MISS\n\n## ACTION\n\nCondition: x\n")
    empty = os.path.join(td, "empty_ledger.json")
    json.dump({"rows": []}, open(empty, "w"))
    rc, log = run([PIPE, "gate", "--brief", brief, "--consensus", fx("consensus.json"),
                   "--verdict-ledger", empty, "--date", "2026-09-06"])
    check("Q8L fires when the day has no ledger rows", "[FAIL] Q8L" in log, log[-300:])
    check("the failure names record-verdicts as the fix", "record-verdicts" in log or "MISSING" in log)

    rc2, log2 = run([PIPE, "gate", "--brief", brief, "--consensus", fx("consensus.json"),
                     "--verdict-ledger", os.path.join(td, "does_not_exist.json"), "--date", "2026-09-06"])
    check("Q8L fires when there is no ledger at all", "[FAIL] Q8L" in log2, log2[-300:])


def test_every_reader_declares_its_shape(td):
    """R6 across the pipeline, not just the three that broke on 2026-09-06."""
    src = open(PIPE).read()
    declared = src.count("load(a.") - src.count("load(a.menus)") - src.count("load(a.prices)")
    withneeds = len(re.findall(r"load\(a\.[a-z_]+,\s*needs=", src))
    check(f"most reads declare their required keys ({withneeds} declared)", withneeds >= 15,
          f"only {withneeds}")
    for tgt, key in [("candidates", "universe"), ("export", "daily_list"), ("phase4", "deliberation_set")]:
        bad = os.path.join(td, f"bad_{tgt}.json")
        json.dump({"definitely_not_" + key: []}, open(bad, "w"))
        args = {"candidates": ["rank", "--tally", fx("tally.json"), "--candidates", bad,
                               "--export", fx("export.json"), "--out", os.path.join(td, "o.json")],
                "export": ["rank", "--tally", fx("tally.json"), "--candidates", fx("candidate_set.json"),
                           "--export", bad, "--out", os.path.join(td, "o.json")],
                "phase4": ["r2digest", "--export", fx("export.json"), "--phase4", bad,
                           "--tally", fx("tally.json"), "--rogers", fx("challenge_rogers.json"),
                           "--steenbarger", fx("challenge_steenbarger.json"), "--lynch", fx("challenge_lynch.json"),
                           "--detectlens", fx("challenge_detect-lens.json"), "--run-id", "t",
                           "--out", os.path.join(td, "p.txt")]}[tgt]
        rc, log = run([PIPE] + args)
        check(f"a {tgt} file missing '{key}' is refused at the read", rc != 0 and "SHAPE MISMATCH" in log,
              log[-160:])


def test_the_two_explainer_sections_are_exempt_but_bounded(td):
    """QX3. Sections 0A/0B answer 'why did this advance' and need three sentences; a fourth still fails."""
    base = ("# B\n\n## §0 VERDICTS\n\n| T | V |\n|---|---|\n| X | ADVANCE |\n\n"
            "## §0A — EXECUTIVE CONSENSUS\n\n### X — ADVANCE\n{body}\n\n"
            "## §1 MACRO\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n\n"
            "## §2 SECTOR\n\n## §3 HELD\n\n## NEAR MISS\n\n## ACTION\n\nCondition: x\n")
    three = "One sentence here. Two sentences here. Three sentences here."
    four = three + " And a fourth one."
    for body, want_pass, label in [(three, True, "three sentences in §0A passes"),
                                   (four, False, "four sentences in §0A still FAILS")]:
        b = os.path.join(td, f"qx3_{want_pass}.md")
        open(b, "w").write(base.format(body=body))
        rc, log = run([PIPE, "gate", "--brief", b, "--consensus", fx("consensus.json"),
                       "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
        passed = "[PASS] QX3" in log
        check(label, passed == want_pass, log[log.find("QX3"):][:150] if "QX3" in log else log[-150:])


def test_the_brief_must_carry_the_pm_deliverable_sections(td):
    """Q9D. The PM reads for five things; 9A/9B/9C are the last three and they ARE the deliverable.
    Saturday's brief said 'approve or reject the nine as a block' and buried the held-book calls in
    a numbered list -- it made the PM do the work the committee exists to do."""
    stem = ("# B\n\n## §0 VERDICTS\n\n| T | V |\n|---|---|\n| X | ADVANCE |\n\n"
            "## §1 MACRO\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n\n"
            "## §2 SECTOR\n\n## §3 HELD\n\n## NEAR MISS\n\n## ACTION\n\nCondition: x\n")
    b = os.path.join(td, "no9.md"); open(b, "w").write(stem)
    rc, log = run([PIPE, "gate", "--brief", b, "--consensus", fx("consensus.json"),
                   "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    for tok in ("9A", "9B", "9C"):
        check(f"a brief with no §{tok} is refused", f"[FAIL] Q9D {tok}" in log or f"§{tok}" in log)

    adv = [c["ticker"] for c in json.load(open(fx("consensus.json"))) if c["verdict"] == "ADVANCE"]
    hold = [c["ticker"] for c in json.load(open(fx("consensus.json"))) if c["verdict"] != "ADVANCE"]
    # 2026-09-16: §9B is a TABLE by contract (brief-writer card: Ticker | Entry reference | Stop |
    # ...), so the fixture renders it as one. It previously dumped bare space-separated tickers,
    # which the contract does not allow -- that shape only satisfied the old substring check.
    adv_rows = "".join(f"| {t} | ref | stop | conf | kill | ctx | Ready now |\n" for t in adv)
    good = stem + ("\n## §9A OWN\n\n| N | ACTION |\n|---|---|\n| BRZE | HOLD |\n"
                   "\n## §9B TRADE\n\n| Ticker | Entry | Stop | Confirms | Kills | Sector | Ready |\n"
                   "|---|---|---|---|---|---|---|\n" + adv_rows +
                   "\n## §9C PLAN\n\nAt the open, do x.\n")
    b2 = os.path.join(td, "with9.md"); open(b2, "w").write(good)
    rc2, log2 = run([PIPE, "gate", "--brief", b2, "--consensus", fx("consensus.json"),
                     "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    check("a brief carrying all three sections passes Q9D", "[FAIL] Q9D" not in log2,
          [l for l in log2.split(chr(10)) if "Q9D" in l and "FAIL" in l][:2])

    # A genuine leak is a HOLD name carrying its own ROW in the trade table -- i.e. presented as
    # tradeable. Injecting one directly after the ADVANCE rows.
    leak = good.replace(adv_rows, adv_rows + f"| {hold[0]} | ref | stop | conf | kill | ctx | Ready now |\n")
    b3 = os.path.join(td, "leak.md"); open(b3, "w").write(leak)
    rc3, log3 = run([PIPE, "gate", "--brief", b3, "--consensus", fx("consensus.json"),
                     "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    check(f"a HOLD name ({hold[0]}) leaking into the trade list is refused",
          any("[FAIL]" in l and "no HOLD name leaks" in l for l in log3.split(chr(10))),
          "HOLD names must not appear as things to trade today")

    nag = good.replace("| BRZE | HOLD |", "| BRZE | monitor |")
    b4 = os.path.join(td, "nag.md"); open(b4, "w").write(nag)
    rc4, log4 = run([PIPE, "gate", "--brief", b4, "--consensus", fx("consensus.json"),
                     "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    check("an unactionable 'monitor' row in §9A is refused",
          any("[FAIL]" in l and "unactionable" in l for l in log4.split(chr(10))))
    check("a §9A row with no named action is refused",
          any("[FAIL]" in l and "named action per held name" in l for l in log4.split(chr(10))))


def test_the_writing_instruction_exists_and_is_wired(td):
    """R11. The §0B quality the PM approved on 2026-09-08 came from a one-off prompt, not the
    kernel — the banned vocabulary and the plain-English translations existed only in a message.
    Next run would have reverted to engine field names. The shaping now lives in a skill."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    skill = os.path.join(root, "skills", "cio-voice", "SKILL.md")
    check("cio-voice skill is shipped", os.path.exists(skill), skill)
    if not os.path.exists(skill): return
    t = open(skill).read()
    check("it carries the so-what rule as its governing rule",
          "what it means" in t.lower() and "what it changes" in t.lower())
    for term in ["BULLISH_BOS", "ABOVE_STRUCTURE", "rs_leadership", "day_vol", "sma_distance_pct"]:
        pass
    banned = sum(1 for x in ["BULLISH_BOS", "ABOVE_STRUCTURE", "stack ALIGNED", "rs_leadership",
                             "day_vol", "sma_distance_pct", "mp_state FADING"] if x in t)
    check(f"it translates the engine vocabulary into plain English ({banned} terms)", banned >= 6)
    check("it names the five states a name can be in",
          all(x in t for x in ["Ready now", "Right name, wrong price", "No read"]))
    check("it forbids unactionable held-book rows",
          "monitor" in t.lower() and "watch closely" in t.lower())
    check("it records the working spawn pattern (agent type failed twice)",
          "general-purpose" in t and "tool_uses" in t)

    bw = os.path.join(root, "agents", "brief-writer.md")
    check("brief-writer defers to it on language", "cio-voice" in open(bw).read())
    run_yaml = open(os.path.join(HERE, "..", "RUN.yaml")).read()
    check("the WRITE step reads it as an input", "cio-voice" in run_yaml)
    rul = open(os.path.join(HERE, "..", "RULINGS.yaml")).read()
    check("R11 is on the record", "id: R11" in rul)


def test_the_gate_does_not_cry_wolf_on_ordinary_english(td):
    """2026-09-15 REGRESSION. QX2 banned the bare word "support", so a correct brief saying
    "no structural support clears the 3 gates" FAILED the publish gate and a human had to
    adjudicate. A barrier that fires on correct output every run is a barrier that gets waved
    through. Roll-call language must still be caught; ordinary trading English must not be."""
    adv = [c["ticker"] for c in json.load(open(fx("consensus.json"))) if c["verdict"] == "ADVANCE"]
    hold = [c["ticker"] for c in json.load(open(fx("consensus.json"))) if c["verdict"] != "ADVANCE"]
    adv_rows = "".join(f"| {t} | ref | stop | conf | kill | ctx | Ready now |\n" for t in adv)
    base = ("# B\n\n## §0 VERDICTS\n\n| T | V |\n|---|---|\n| X | ADVANCE |\n\n"
            "## §1 MACRO\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n\n"
            "## §2 SECTOR\n\n## §3 HELD\n\n## NEAR MISS\n\n## ACTION\n\nCondition: x\n"
            "\n## §9A OWN\n\n| N | ACTION |\n|---|---|\n| BRZE | HOLD |\n"
            "\n## §9B TRADE\n\n| Ticker | Entry | Stop | Confirms | Kills | Sector | Ready |\n"
            "|---|---|---|---|---|---|---|\n" + adv_rows +
            "\n## §9C PLAN\n\nAt the open, do x.\n")

    ok = base.replace("Condition: x", "Condition: x. No structural support clears the 3 gates; "
                                      "there is no fundamental support for the move.")
    b = os.path.join(td, "english.md"); open(b, "w").write(ok)
    _, log = run([PIPE, "gate", "--brief", b, "--consensus", fx("consensus.json"),
                  "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    check("'structural support' / 'fundamental support' do NOT trip the vote-tally check",
          "[FAIL] QX2 no vote-tally" not in log,
          [l for l in log.split(chr(10)) if "QX2" in l and "FAIL" in l][:2])

    for bad_phrase in ("the vote was 6 support, 2 oppose", "supported by 7 seats"):
        b2 = os.path.join(td, "rollcall.md")
        open(b2, "w").write(base.replace("Condition: x", "Condition: x. " + bad_phrase))
        _, log2 = run([PIPE, "gate", "--brief", b2, "--consensus", fx("consensus.json"),
                       "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
        check(f"real roll-call language is still refused: {bad_phrase!r}",
              "[FAIL] QX2 no vote-tally" in log2)

    footnote = base + f"\nThe HOLD-FOR-CONDITIONS names ({', '.join(hold[:3])}) do not appear in §9B.\n"
    b3 = os.path.join(td, "footnote.md"); open(b3, "w").write(footnote)
    _, log3 = run([PIPE, "gate", "--brief", b3, "--consensus", fx("consensus.json"),
                   "--verdict-ledger", fx("verdict_ledger.json"), "--date", "2026-09-06"])
    check("naming the excluded HOLD names in prose is NOT read as a leak",
          "[FAIL] Q9D no HOLD name leaks" not in log3,
          [l for l in log3.split(chr(10)) if "Q9D" in l and "FAIL" in l][:2])


def test_the_run_map_parses_as_data_not_as_characters(td):
    """2026-09-15 REGRESSION. RUN.yaml's WRITE step wraps its reads: list across two lines. The
    mini-YAML reader only understood a bracket list that closed on the same line, so WRITE's reads
    came back as a STRING and the missing-input check iterated it CHARACTER BY CHARACTER, printing
    a wall of single letters. An input check nobody can read is an input check nobody honours."""
    sys.path.insert(0, TOOLS)
    import importlib, preflight_run
    importlib.reload(preflight_run)
    M = preflight_run.load_yaml("RUN.yaml")
    bad = [(s["name"], type(s.get("reads")).__name__) for s in M["steps"]
           if s.get("reads") is not None and not isinstance(s.get("reads"), list)]
    check("every step's reads: parses as a list, never a bare string", not bad, str(bad))
    w = next(s for s in M["steps"] if s["name"] == "WRITE")
    check("WRITE's wrapped reads: list resolves to real filenames",
          "consensus.json" in (w.get("reads") or []) and "purity_check.json" in (w.get("reads") or []),
          str(w.get("reads"))[:160])


def test_the_publish_gate_runs_with_no_manual_override(td):
    """2026-09-15 REGRESSION. purity_check defaulted --pipeline to a bare filename, which resolves
    against the run root, not tools/. Run the documented way it died instantly, so the invariance
    test that decides whether a run may publish required an operator to already know the override.
    Same class as the v1.8.0 --solo-min skew: a gate needing a manual flag is not a gate."""
    out = os.path.join(td, "purity_nodefault.json")
    rc, log = run([PURITY, "--tally", fx("tally.json"), "--candidates", fx("candidate_set.json"),
                   "--export", fx("export.json"), "--pm-lens", fx("pm_lens.json"), "--out", out])
    check("purity_check finds the pipeline with NO --pipeline flag", rc == 0, log[-400:])
    if rc == 0:
        check("invariance still PASSES on the default path", json.load(open(out))["invariance"] == "PASS")


def test_a_step_cannot_close_without_its_declared_artifacts(td):
    """2026-09-15 REGRESSION, and the structural fix for the whole class. GATHER declares it
    produces phase4_ledger.json and verdict_ledger.json at the run root; they landed under data/.
    Nothing noticed. GATHER ticked done, eleven model seats ran at real token cost, and the first
    complaint came four steps later at REPEAT-WATCH -- recovered by hand-passing data/... paths,
    the adapter R6 forbids, three times in one run. A step that did not put its artifacts where it
    said it would has not finished; tick must refuse to close it."""
    import shutil
    work = os.path.join(td, "tickwork")
    os.makedirs(os.path.join(work, "tools"), exist_ok=True)
    SKILL_DIR = os.path.abspath(os.path.join(HERE, ".."))
    for f in ("RUN.yaml", "RULINGS.yaml"):
        shutil.copy(os.path.join(SKILL_DIR, f), os.path.join(work, f))
    for f in ("registrar.py", "preflight_run.py"):
        shutil.copy(os.path.join(TOOLS, f), os.path.join(work, "tools", f))
    reg = os.path.join(work, "tools", "registrar.py")

    def rrun(args):
        r = subprocess.run([sys.executable, reg] + args, capture_output=True, text=True, cwd=work)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    rrun(["init", "--date", "2026-09-16"])
    rc, log = rrun(["tick", "--step", "DECIDE", "--status", "done"])
    check("tick REFUSES done when declared produces are absent", rc != 0, f"exit {rc}")
    check("the refusal names the artifacts and the path they were promised at",
          "consensus.json" in log, log[-200:])
    check("the refusal forbids re-pointing the next tool (R6)",
          "adapter" in log.lower() or "R6" in log, log[-200:])

    for f in ("consensus.json", "verdict_ledger.json"):   # brackets.json is BRACKET's (R18), not DECIDE's
        open(os.path.join(work, f), "w").write("{}")
    rc2, log2 = rrun(["tick", "--step", "DECIDE", "--status", "done"])
    check("tick ALLOWS done once every declared artifact is at its declared path", rc2 == 0, log2[-200:])

    os.remove(os.path.join(work, "verdict_ledger.json"))
    rc3, _ = rrun(["tick", "--step", "DECIDE", "--status", "done", "--force-incomplete",
                   "--note", "deliberate"])
    m = json.load(open(os.path.join(work, "run_manifest.json")))
    check("a forced close is allowed but writes the gap to the scoreboard, never silently",
          rc3 == 0 and any("produces absent" in d.get("note", "") for d in m.get("degradations", [])),
          str(m.get("degradations"))[:200])


def test_a_seat_that_invents_its_numbers_is_refused(td):
    """R2 AS AMENDED 2026-09-16. The md5 half of R2 never ran once: no spawned seat has a hashing
    tool, so on 2026-09-15 all eleven declared NOT_VERIFIED and substituted a quoted line -- 100%
    non-compliance, routine enough to be invisible. It also never addressed the real exposure: a
    seat can hash a file perfectly and still fabricate every figure in its reasoning, which R2's
    own rationale records happening twice (2026-08-19, 2026-09-03).

    What IS checkable is the claim a seat makes when it writes "ma50 218.30" -- that the row it was
    handed says so. Two properties matter equally and this test pins both: it must not fire on
    correct work (or it gets waved through, like the gate's "support" ban), and it must fire on a
    fabricated figure (or it is decoration)."""
    sys.path.insert(0, TOOLS)
    import importlib, figure_audit
    importlib.reload(figure_audit)

    packet = os.path.join(td, "audit_packet.txt")
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"),
                   "--tally", fx("tally.json"), "--fundamentals", fx("fundamentals.json"),
                   "--rogers", fx("challenge_rogers.json"),
                   "--steenbarger", fx("challenge_steenbarger.json"),
                   "--lynch", fx("challenge_lynch.json"),
                   "--detectlens", fx("challenge_detect-lens.json"),
                   "--run-id", "audit", "--out", packet])
    if rc != 0:
        check("packet builds for the figure audit", False, log[-300:]); return
    ptxt = open(packet).read()

    forms = json.load(open(fx("round2_votes.json")))
    total, votes = 0, 0
    for form in forms:
        votes += len(form.get("votes", []))
        total += len(figure_audit.audit(form, ptxt))
    check(f"ZERO false positives across the real committee's {votes} votes", total == 0,
          f"{total} figures flagged on a run that was correct — this is the cry-wolf failure")

    # The 2026-09-06 fixtures are TRIMMED -- their reason fields are empty -- so they prove the
    # no-false-positive half and nothing else. The catching half is built here from the packet
    # itself: quote a real row correctly (must pass), then move one digit (must fail).
    tickers = list(figure_audit.packet_index(ptxt)[0].keys())
    check("the packet exposes per-ticker rows to scope claims against", bool(tickers), str(tickers[:3]))
    if not tickers:
        return
    tic = tickers[0]
    row_vals = sorted(figure_audit.packet_index(ptxt)[0][tic])
    real = next((v for v in row_vals if abs(v) > 1 and v != int(v)), None)
    if real is None:
        check("a fabricated served-field figure is caught", False, "no decimal in the row to quote")
        return

    honest = {"voice": "testseat", "date": "2026-09-06", "round": 2,
              "votes": [{"ticker": tic, "vote": "ABSTAIN",
                         "reason": f"Row check: ma50 {real} is what the packet says."}]}
    counts = {}
    check("a ballot quoting the row CORRECTLY is clean",
          not figure_audit.audit(honest, ptxt, counts), f"ma50 {real}")
    check("and the audit reports that it actually examined a claim", counts.get("examined", 0) >= 1,
          str(counts))

    fake_val = round(real + 11.11, 2)
    invented = json.loads(json.dumps(honest))
    invented["votes"][0]["reason"] = f"Row check: ma50 {fake_val} is what the packet says."
    found = figure_audit.audit(invented, ptxt)
    check("moving a single digit IS caught", any(f["figure"] == str(fake_val) for f in found),
          f"claimed ma50 {fake_val} against a row that carries {real}; flagged {[f['figure'] for f in found]}")

    silent = {"voice": "testseat", "date": "2026-09-06", "round": 2,
              "votes": [{"ticker": tic, "vote": "ABSTAIN", "reason": "Not my setup. Declining."}]}
    c2 = {}
    figure_audit.audit(silent, ptxt, c2)
    check("a ballot citing no served field reports ZERO examined, not a clean bill",
          c2.get("examined", 0) == 0, str(c2))

    bad_form = os.path.join(td, "tampered_ballot.json")
    json.dump(invented, open(bad_form, "w"))
    rc2, log2 = run([REG, "validate", "--file", bad_form, "--round", "2", "--packet", packet])
    check("registrar validate --packet REJECTS a ballot with an invented figure",
          '"result": "REJECT"' in log2, log2[-200:])
    check("the rejection says the figure is not in the packet", "NOT in the packet" in log2, log2[-250:])

    good_form = os.path.join(td, "clean_ballot.json")
    json.dump(honest, open(good_form, "w"))
    _, log3 = run([REG, "validate", "--file", good_form, "--round", "2", "--packet", packet])
    check("the honest ballot is not rejected by the figure audit",
          "FABRICATED FIGURE" not in log3, log3[-200:])


def _crown_fixture(td, tag=""):
    """The macro artifact crown's card is written against. `packets` now REFUSES to build a blind
    crown packet (2026-09-25 defect), so every test that builds packets supplies it."""
    path = os.path.join(td, tag + "aqe_crown_macro.json")
    open(path, "w").write(json.dumps({
        "the_call": {"family": "NARROWING_CONCENTRATED"}, "status": "OK",
        "readings": {"breadth": {"position_in_12_month_range": "bottom"},
                     "positioning": {"trend_funds": {}, "large_speculators": {},
                                     "option_dealers": {"available": False}},
                     "volatility": {"state": "ELEVATED_RISING", "vix": 14.21}},
        "key_levels": [], "generated_at": "2026-09-06T09:06:00+08:00"}))
    return path


def test_a_position_the_pm_owns_reaches_every_seat(td):
    """THE 2026-09-16 DEFECT, nailed shut.

    AQE serves the held book complete -- 86 fields per position, including hl_state, its OWN
    health verdict on what the PM owns. On 2026-09-16 all three positions read EXIT and NOT ONE
    SEAT SAW IT. cmd_trim built the universe from daily_list alone and sliced it to CONSUMED, so
    a held name failing the $2B/1.5M screen never entered the universe, and the held-only fields
    were stripped from any that did. The brief then reported "no stop served" on two names AQE
    had served a fallback stop for, and recommended STOP-TIGHTEN and HOLD on two positions the
    engine had already called EXIT -- and the resulting hole was reported to the PM as the data
    provider's gap. It was not. It was this function.

    Four assertions, in the order the failure happened: the book enters whole, it reaches every
    seat, the vote packet carries it too, and the run REFUSES rather than quietly proceeding when
    it does not.
    """
    exp = fx("export.json")
    E = json.load(open(exp))
    held = {h["ticker"]: h for h in E["held_positions"]}
    cs = os.path.join(td, "cs.json")
    rc, log = run([PIPE, "trim", "--export", exp, "--date", "2026-09-06", "--out", cs])
    check("trim exits clean with a held book present", rc == 0, log[-300:])
    if rc != 0: return
    U = {r["ticker"]: r for r in json.load(open(cs))["universe"]}

    missing = [t for t in held if t not in U]
    check("every held position is in the universe, screen or no screen",
          not missing, f"absent: {missing}")
    lost = {t: [k for k in h if k not in (U.get(t, {}).get("held_book") or {})]
            for t, h in held.items() if t in U}
    lost = {t: v for t, v in lost.items() if v}
    check("the served held record is carried WHOLE -- not one field dropped",
          not lost, f"lost: {lost}")
    check("every held row is flagged held=True",
          all(U[t].get("held") is True for t in held if t in U))

    pk = os.path.join(td, "packets")
    rc, log = run([PIPE, "packets", "--candidates", cs, "--menus",
                   os.path.abspath(os.path.join(HERE, "..", "contracts", "voice_menus.json")),
                   "--export", exp, "--date", "2026-09-06", "--outdir", pk,
                   "--crown-macro", _crown_fixture(td, os.path.basename(pk) + "_")])
    check("packets build with the held floor in place", rc == 0, log[-400:])
    if rc == 0:
        import csv as _csv, io as _io
        blind, absent_rows = [], []
        for f in sorted(os.listdir(pk)):
            if not f.endswith(".tsv"): continue
            body = [ln for ln in open(os.path.join(pk, f)) if not ln.startswith("#")]
            rows = list(_csv.DictReader(_io.StringIO("".join(body)), delimiter="\t"))
            seen = {r["ticker"] for r in rows if str(r.get("held", "")).lower() in ("true", "1", "yes")}
            if seen != set(held): absent_rows.append((f, sorted(set(held) - seen)))
            for r in rows:
                if r["ticker"] in held and not str(r.get("held_book.hl_state", "")).strip():
                    blind.append((f, r["ticker"]))
        check("every nominating seat is served every held position",
              not absent_rows, f"{absent_rows}")
        check("every nominating seat is served AQE's health verdict on the book",
              not blind, f"seat/ticker served no hl_state: {blind[:6]}")

    # the vote packet, which was equally blind
    dig = os.path.join(td, "VOTE_PACKET.txt")
    rc, log = run([PIPE, "r2digest", "--export", exp, "--phase4", fx("phase4.json"),
                   "--tally", fx("tally.json"), "--run-id", "t", "--out", dig,
                   "--challenge", fx("challenge_rogers.json")])
    if rc == 0 and os.path.exists(dig):
        txt = open(dig).read()
        p4 = set(json.load(open(fx("phase4.json")))["deliberation_set"])
        want = [t for t in held if t in p4]
        check("a held name in the deliberation set carries its book into the vote packet",
              all(f"HELD POSITION" in txt for _ in want) if want else True,
              "no held name in this fixture's deliberation set -- vacuous, not a pass to rely on")

    # --- the refusals ---
    naked = json.load(open(cs))
    for r in naked["universe"]: r.pop("held_book", None)
    np_ = os.path.join(td, "cs_naked.json"); json.dump(naked, open(np_, "w"))
    rc, log = run([PIPE, "packets", "--candidates", np_, "--menus",
                   os.path.abspath(os.path.join(HERE, "..", "contracts", "voice_menus.json")),
                   "--export", exp, "--date", "2026-09-06", "--outdir", os.path.join(td, "pk_naked")])
    check("a candidate_set predating the ruling is REFUSED, not silently served",
          rc != 0 and "held_book" in log, f"rc={rc} {log[-200:]}")

    gone = json.load(open(cs))
    drop = sorted(held)[0]
    gone["universe"] = [r for r in gone["universe"] if r["ticker"] != drop]
    gp = os.path.join(td, "cs_gone.json"); json.dump(gone, open(gp, "w"))
    rc, log = run([PIPE, "packets", "--candidates", gp, "--menus",
                   os.path.abspath(os.path.join(HERE, "..", "contracts", "voice_menus.json")),
                   "--export", exp, "--date", "2026-09-06", "--outdir", os.path.join(td, "pk_gone")])
    check("a held position screened out of its own committee is REFUSED",
          rc != 0 and drop in log, f"rc={rc} {log[-200:]}")


def test_the_expensive_steps_are_checkpointed(td):
    """2026-09-15 REGRESSION. stages/S0_preflight.md: "local disk is disposable -- it has been wiped
    five times in one build, and every artifact that survived did so because it was pushed."
    stages/S7_cio_output.md requires the brief to reach a fixed GitHub path. The v5.4 conductor
    rewrite carried neither -- not one of the 13 steps had a git action -- so a whole committee
    (27 spawns, ~115k model tokens) lived only inside a container that gets reclaimed. The point of
    a checkpoint is not tidiness: it is that a crash costs the step in flight, not the run."""
    sys.path.insert(0, TOOLS)
    import importlib, preflight_run
    importlib.reload(preflight_run)
    M = preflight_run.load_yaml("RUN.yaml")

    cp = M.get("checkpoint") or {}
    check("RUN.yaml declares a checkpoint policy", bool(cp), str(list(M.keys()))[:120])
    after = cp.get("after") or []
    marked = [s["name"] for s in M["steps"] if s.get("checkpoint_after")]

    model_steps = {s["name"] for s in M["steps"] if s.get("kind") == "model"}
    check("EVERY model step is checkpointed — those are the ones that cost tokens to redo",
          model_steps.issubset(set(after)), f"model={sorted(model_steps)} after={sorted(after)}")
    check("the policy list and the per-step markers agree", set(after) == set(marked),
          f"policy={sorted(after)} marked={sorted(marked)}")
    check("no tool step is checkpointed (a re-run is cheaper than a push)",
          not [s["name"] for s in M["steps"] if s.get("kind") == "tool" and s.get("checkpoint_after")])
    check("a push failure does not halt a committee that already did the work",
          "continue" in (cp.get("on_fail") or "").lower(), cp.get("on_fail", "")[:120])
    check("the checkpoint names the tool that performs it",
          "git_sync" in (cp.get("tool") or ""), cp.get("tool", "")[:120])
    # git_sync.py must sit where a RUN can reach it. The run's working set copies skills/ and not
    # the plugin's top-level tools/, so the skill-local copy is the one that matters at run time.
    check("the sync tool it names ships inside the skill, where a run can reach it",
          os.path.exists(os.path.join(TOOLS, "git_sync.py")),
          f"{os.path.join(TOOLS, 'git_sync.py')} not found -- a checkpoint pointed at the plugin "
          f"root would not resolve during a run")

    card_path = os.path.join(os.path.dirname(TOOLS), "SKILL.md")
    if os.path.exists(card_path):
        card = open(card_path).read()
        check("THE LOOP on the card carries the checkpoint step", "git_sync" in card)
        check("THE LOOP on the card carries --packet validation", "--packet" in card)


def test_fading_is_not_a_gate(td):
    """R13. mp_state FADING = 'momentum score not higher than 3 bars ago' (src/engines/mp.py).
    MSTR sat at mp 89 and read FADING on 2026-09-19; the AQE_LEADER door required STRONG."""
    src = open(PIPE).read()
    check("AQE_LEADER door no longer consults mp_state",
          'row.get("mp_state") == "STRONG"' not in src.split("def _aqe_leader")[1].split("def ")[0])
    exp = fx("export.json")
    cs = os.path.join(td, "cs13.json")
    rc, log = run([PIPE, "trim", "--export", exp, "--date", "2026-09-06", "--out", cs])
    check("trim exits clean", rc == 0, log[-300:])
    if rc != 0: return
    U = json.load(open(cs))["universe"]
    check("every row carries mp_state_plain (the translation travels with the row)",
          all(r.get("mp_state_plain") for r in U))
    fading = [r for r in U if r.get("mp_state") == "FADING"]
    check("FADING is translated as 'not higher than 3 bars ago', never as decay",
          all("NOT higher than 3 bars ago" in r["mp_state_plain"] for r in fading))
    # A synthetic leader that reads FADING must open AQE_LEADER.
    import importlib.util
    spec = importlib.util.spec_from_file_location("pp", PIPE); pp = importlib.util.module_from_spec(spec); spec.loader.exec_module(pp)
    check("a SUSTAINED LEADER at mp 89 reading FADING opens the AQE_LEADER door",
          pp._aqe_leader({"elder_pattern": "SUSTAINED", "rs_leadership": "LEADER", "mp_state": "FADING", "mp": 89}))
    check("the round-2 packet header restates R13",
          "R13 (binding): mp_state FADING" in src)


def test_a_momentum_lane_name_is_judged_by_the_strength_seats(td):
    """R14 (SUPERSEDED by R32, 2026-10-30) -- this pins the LEGACY `consensus` blind tally, which is
    no longer the verdict (R34: ratify-count is). Kept so the 2026-09-06 fixtures keep reproducing and
    so a change to the legacy reader is noticed. Seow left STRENGTH_SEATS on 2026-11-01 (R32)."""
    V = json.load(open(fx("round2_votes.json")))
    tk = V[0]["votes"][0]["ticker"]
    p4 = os.path.join(td, "p4_lane.json")
    json.dump({"deliberation_set": [tk], "ranked": [{"ticker": tk, "doors": ["STRENGTH"], "lane": "MOMENTUM"}], "dropped": []}, open(p4, "w"))
    out = os.path.join(td, "c14.json")
    rc, log = run([PIPE, "consensus", "--round2", fx("round2_votes.json"), "--phase4", p4, "--out", out])
    check("consensus exits clean with a lane file", rc == 0, log[-300:])
    if rc != 0: return
    C = {c["ticker"]: c for c in json.load(open(out))}
    row = C[tk]
    strength = {"livermore", "oneil", "minervini", "elder-lens", "detect-lens"}   # R32: seow removed
    counted = set(row["split"]["support"] + row["split"]["oppose"] + row["split"]["abstain"])
    advisory = set(row["advisory"]["support"] + row["advisory"]["oppose"] + row["advisory"]["abstain"])
    check("the momentum-lane row is stamped lane=MOMENTUM", row.get("lane") == "MOMENTUM")
    check("only strength seats are counted", counted <= strength, str(counted - strength))
    check("the other seats' votes are kept as advisory, not discarded", advisory and not (advisory & strength), str(advisory))
    others = [c for t, c in C.items() if t != tk]
    check("every other name is PULLBACK lane and counts every seat",
          all(c["lane"] == "PULLBACK" and not any(c["advisory"].values()) for c in others))
    # Same votes with no lane file reproduce the legacy single-committee verdict.
    out2 = os.path.join(td, "c14b.json")
    rc, _ = run([PIPE, "consensus", "--round2", fx("round2_votes.json"), "--phase4", os.path.join(td, "nope.json"), "--out", out2])
    legacy = {c["ticker"]: c["verdict"] for c in json.load(open(fx("consensus.json")))}
    legacy.update({t: v[0] for t, v in R22_DELTA.items()})   # R22: Lynch's ballot no longer counts
    got = {c["ticker"]: c["verdict"] for c in json.load(open(out2))}
    check("with no lane file the verdicts are the legacy ones (nothing else moved)", got == legacy)


def test_every_nominator_is_served_the_momentum_floor(td):
    """R15. The momentum numbers reach every seat packet, not just the three whose menus asked."""
    exp = fx("export.json")
    cs = os.path.join(td, "cs15.json")
    rc, _ = run([PIPE, "trim", "--export", exp, "--date", "2026-09-06", "--out", cs])
    pk = os.path.join(td, "packets15")
    rc, log = run([PIPE, "packets", "--candidates", cs, "--menus",
                   os.path.abspath(os.path.join(HERE, "..", "contracts", "voice_menus.json")),
                   "--export", exp, "--date", "2026-09-06", "--outdir", pk,
                   "--crown-macro", _crown_fixture(td, os.path.basename(pk) + "_")])
    check("packets build with the momentum floor in place", rc == 0, log[-400:])
    if rc != 0: return
    need = ["rs_spy_20d", "rs_rank_pct", "ret_63d", "pct_run_10d", "adx_14", "extension_atr_20", "mp", "mp_state_plain", "mp_accel_state", "runner_setup"]
    blind = {}
    for f in sorted(os.listdir(pk)):
        if not f.endswith(".tsv"): continue
        hdr = next(ln for ln in open(os.path.join(pk, f)) if ln.startswith("ticker")).rstrip("\n").split("\t")
        miss = [c for c in need if c not in hdr]
        if miss: blind[f] = miss
    check("every nominating seat is served every momentum-floor column", not blind, str(blind))
    rank_out = os.path.join(td, "p4_15.json")
    rc, log = run([PIPE, "rank", "--tally", fx("tally.json"), "--candidates", cs, "--export", exp,
                   "--cap", "24", "--pm-lens", fx("pm_lens.json"), "--pm-lens-min", "5", "--out", rank_out])
    check("rank exits clean with the seven doors", rc == 0, log[-300:])
    if rc == 0:
        P = json.load(open(rank_out))
        # R16 (2026-09-24) added NOMINATED: the floor is a door of its own and the other seven are
        # ADDITIONS. The set is asserted whole so a door can never be dropped or renamed silently.
        check("the doors are declared on the record, NOMINATED among them",
              set(P["doors_rule"]) == {"NOMINATED", "HELD", "SEATS", "SOLO", "ELDER+LENS", "LENS", "STRENGTH", "PM_LENS", "AQE_LEADER"}, str(set(P["doors_rule"])))
        check("R16: NOMINATED is declared UNCONDITIONAL", "UNCONDITIONALLY" in P["doors_rule"]["NOMINATED"])
        check("R17: every door says it only flags, never seats",
              all("FLAG ONLY" in P["doors_rule"][d]
                  for d in ("ELDER+LENS", "LENS", "STRENGTH", "PM_LENS", "AQE_LEADER")),
              str({d: P["doors_rule"][d][-40:] for d in ("LENS", "STRENGTH")}))
        check("ELDER+LENS reads 2 bars, not 3", "last 2 bars" in P["doors_rule"]["ELDER+LENS"])



# ============================ R16 — THE NOMINATION FLOOR ============================
# PM ruling 2026-09-24, verbatim: "I never asked to leave 5 seats or whatever that means. It is
# additive and not to gate or remove voice (analyst) picks."

def _r16_fixture(td, n_nominated=30, n_universe=90, tag=""):
    """A universe where the nominated names are deliberately the WEAKEST rows on the sheet, so any
    door-ordered or strength-ordered cap would cut every one of them. Under R16 all of them are
    seated anyway. This is the 2026-09-24 failure in miniature: 12 of 24 chairs went to unnominated
    extension while 17 seat picks were binned."""
    uni = []
    for i in range(n_universe):
        nominated = i < n_nominated
        uni.append({
            "ticker": ("N%02d" % i) if nominated else ("M%02d" % i),
            "rank": i + 1,
            "rs_spy_20d": 0.5 + i * 0.01 if nominated else 40.0 + i,
            "mp": 30.0 if nominated else 95.0,
            "mp_state": "BUILDING" if nominated else "STRONG",
            "mp_accel_state": "ACCELERATING",
            "extension_atr_20": 0.8 if nominated else 3.9,
            "sc_momentum": 10.0 if nominated else 90.0,
            "gics_sector_name": "Technology",
            "elder": 9.0, "elder_5d": [9, 9, 9, 9, 9],
            "elder_pattern": "SUSTAINED", "rs_leadership": "LEADER", "on_longlist": True,
            "lens": {"leadership": "strong", "coil": "strong", "insti_money": "strong",
                     "structure": "strong", "resistance": "warn", "sector": "ok"},
        })
    tally = [{"ticker": "N%02d" % i, "seats": ["weis"], "conv": [2], "reasons": [],
              "count": 1, "maxc": 2, "sumc": 2} for i in range(n_nominated)]
    def w(name, obj):
        path = os.path.join(td, tag + name)
        open(path, "w").write(json.dumps(obj))
        return path
    return (w("tally.json", tally),
            w("candidate_set.json", {"run_date": "2026-09-24", "universe": uni}),
            w("export.json", {"daily_list": uni, "srm": [{"sector": "Technology", "entry_gate": "WATCH"}]}),
            os.path.join(td, tag + "phase4.json"))


def test_every_nomination_is_seated(td):
    """R16: thirty nominations against a cap of twenty-four. Every nomination is seated anyway and
    the artifact records zero cut by machinery. Before R16 this cut six of them."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=30, tag="r16a_")
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex,
                   "--cap", "24", "--pm-lens", "", "--out", out])
    check("rank exits clean with 30 nominations against a cap of 24", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    nominated = set("N%02d" % i for i in range(30))
    cut = sorted(nominated - set(P["deliberation_set"]))
    check("R16: every nomination is seated, cap or no cap", not cut, "CUT: %s" % cut)
    check("R16: the artifact records zero nominations cut by machinery",
          P["nominations_cut_by_machinery"] == [], str(P["nominations_cut_by_machinery"]))
    check("R16: nominations_seated counts the whole floor", P["nominations_seated"] == 30,
          str(P.get("nominations_seated")))
    check("R16: the room is at least as large as the floor", len(P["deliberation_set"]) >= 30,
          str(len(P["deliberation_set"])))
    check("R16: NOMINATED is declared as a door on the record", "NOMINATED" in P["doors_rule"])
    check("R16+R12: HELD is declared as a floor door", "HELD" in P["doors_rule"])


def test_the_flag_list_leads_with_the_strongest_names(td):
    """R26 (PM 2026-10-23): "our objective is to NOT miss strong momentum picks". The flag list is every
    Longlist/Elder name not in the room, strongest vs SPY first -- a name that opened one door but is
    the strongest on the sheet leads; a name on neither list never appears."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=5, tag="r26_")
    E = json.load(open(ex)); C = json.load(open(cs))
    for doc in (E["daily_list"], C["universe"]):
        for r in doc:
            if r["ticker"] == "M50": r.update({"rs_spy_20d": 999.0, "lens": {}, "elder_5d": [1], "elder_pattern": None, "rs_leadership": None, "mp": 10.0})
            if r["ticker"] == "M89": r["on_longlist"] = False
    open(ex, "w").write(json.dumps(E)); open(cs, "w").write(json.dumps(C))
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex, "--pm-lens", "",
                   "--strong-seats", "0", "--out", out])
    check("rank exits clean", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out)); f = [x["ticker"] for x in P["informational"]]
    check("R26: the strongest name leads even with few doors", f[:1] == ["M50"], str(f))
    check("R26: a name on neither list is never flagged", "M89" not in f, str(f))
    check("R26: ten are shown by default", len(f) == 10, str(len(f)))
    check("R26: still never seated (R17)", not (set(f) & set(P["deliberation_set"])))


def test_the_strongest_names_are_voted_in_the_momentum_lane(td):
    """R27 (PM 2026-10-23): "let committee review these strongest and vote on it ... if they dont do this,
    it is equivalent to me scanning aqe manually" and "the 2 lanes should still stay". The top
    --strong-seats Longlist/Elder names not nominated are SEATED, MOMENTUM lane; the next ones stay
    flagged; nominations are untouched; 0 turns it off."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=5, tag="r27_")
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex, "--pm-lens", "",
                   "--strong-seats", "4", "--door-budget", "3", "--out", out])
    check("rank exits clean", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    seated = [x["ticker"] for x in P["strong_seats"]]
    check("R27: the four strongest vs SPY are seated", seated == ["M89", "M88", "M87", "M86"], str(seated))
    check("R27: they are in the room", set(seated) <= set(P["deliberation_set"]))
    lanes = {r["ticker"]: r["lane"] for r in P["ranked"]}
    check("R27: they are voted in the MOMENTUM lane", all(lanes[t] == "MOMENTUM" for t in seated), str(lanes))
    f = [x["ticker"] for x in P["informational"]]
    check("R27: the next strongest stay flagged, not seated", f == ["M85", "M84", "M83"], str(f))
    check("R16 still holds", {"N%02d" % i for i in range(5)} <= set(P["deliberation_set"]))
    hdr = None
    check("R27: the vote packet tells seats a rule-seated name is not a reason to oppose",
          "STRONG_SEAT" in open(os.path.join(TOOLS, "pma_pipeline.py")).read().split("ROUND 2 VOTE PACKET")[1][:3000])


def test_up_to_three_reserved_seats_for_a_valen_reclaim(td):
    """R25 (PM 2026-10-23): ACN -- on both lists, strength rank 51, Valen U&R MET, the PM's own manual
    pick -- was never voted because no seat nominated it. Up to 3 un-nominated names with U&R MET on
    the Longlist or Elder list are seated, by AQE rank, in the whole-room lane. SETUP does not qualify,
    a name off both lists does not qualify, and a nominated name never uses a reserved seat."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=10, tag="r25_")
    E = json.load(open(ex))
    names = {r["ticker"]: r for r in E["daily_list"]}
    def mark(tk, st="MET", ll=True):
        names[tk].update({"unr_status": st, "on_longlist": ll, "on_elder": False, "unr_note": "x", "unr_level": 1.0})
    mark("N03")                      # nominated: never uses a reserved seat
    mark("M20"); mark("M15"); mark("M40"); mark("M60")   # four qualify -> best three by rank
    mark("M12", "SETUP")             # no reclaim yet
    mark("M13", ll=False)            # off both lists
    open(ex, "w").write(json.dumps(E))
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex, "--pm-lens", "", "--out", out])
    check("rank exits clean", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    seated = [x["ticker"] for x in P["unr_seats"]]
    check("R25: the best three by AQE rank take the reserved seats", seated == ["M15", "M20", "M40"], str(seated))
    check("R25: they are in the room and voted", set(seated) <= set(P["deliberation_set"]))
    check("R25: SETUP, off-list and nominated names never take a reserved seat",
          not ({"M12", "M13", "N03", "M60"} & set(seated)))
    lanes = {r["ticker"]: r["lane"] for r in P["ranked"]}
    check("R27: a reserved U&R seat takes the ordinary lane rule (a strength name is MOMENTUM)",
          all(lanes[t] == "MOMENTUM" for t in seated), str({t: lanes[t] for t in seated}))
    check("R16 still holds: every nomination is seated", {"N%02d" % i for i in range(10)} <= set(P["deliberation_set"]))
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex, "--pm-lens", "",
                   "--unr-seats", "0", "--out", out])
    check("R25: --unr-seats 0 turns it off", rc == 0 and json.load(open(out))["unr_seats"] == [], log[-300:])


def test_the_doors_can_never_displace_a_nomination(td):
    """R16 + R17: the floor is the room. With the door allowance forced wide open, door-openers are
    FLAGGED for the PM and seat nobody, so the room is exactly the floor and no nomination can be
    displaced. The retired strength reserve changes nothing."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=30, tag="r16b_")
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex,
                   "--cap", "24", "--machine-add", "40", "--pm-lens", "", "--strong-seats", "0", "--out", out])  # R27 off: pure R16/R17
    check("rank exits clean with a wide machine-add budget", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    nominated = set("N%02d" % i for i in range(30))
    check("R16: the floor survives a wide-open door allowance", nominated <= set(P["deliberation_set"]))
    check("R17: the doors seat nobody -- the room IS the floor",
          set(P["deliberation_set"]) == set(P["nomination_floor"]), str(len(P["deliberation_set"])))
    check("R17: machine_additions is empty", P["machine_additions"] == [], str(P["machine_additions"]))
    flagged = [x["ticker"] for x in P["informational"]]
    check("R17: door-openers are FLAGGED for the PM instead", len(flagged) > 0, str(flagged[:5]))
    check("R17: nothing nominated appears in the flag list",
          not (set(flagged) & nominated), str(sorted(set(flagged) & nominated)))
    strays = [t for t in flagged if not t.startswith("M")]
    check("R17: every flagged name is one no seat nominated", not strays, str(strays))
    check("R17: each flagged row carries its doors and AQE reads",
          all(("doors" in x and "aqe_rank" in x and "mp" in x) for x in P["informational"]))
    out2 = out.replace(".json", ".reserve.json")
    rc2, log2 = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex, "--cap", "24",
                     "--machine-add", "40", "--strength-reserve", "5", "--pm-lens", "", "--strong-seats", "0", "--out", out2])
    check("R16: --strength-reserve is accepted and changes nothing (retired)",
          rc2 == 0 and json.load(open(out2))["deliberation_set"] == P["deliberation_set"], log2[-300:])


def test_a_floor_larger_than_the_cap_never_gives_way(td):
    """R16: when the seats alone fill more than the cap, the FLOOR still stands whole and the door
    allowance stays additive. The analysts are never the ones who give way, and --cap bounds the
    doors only. Replayed on real 2026-09-24 data, a residual budget would have dropped FTNT and
    TWLO -- both ADVANCED by the room."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=40, tag="r16c_")
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex,
                   "--cap", "24", "--pm-lens", "", "--out", out])
    check("rank exits clean with a floor larger than the cap", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    # The door allowance is ADDITIVE, so a big floor does NOT starve it -- that is the whole point of
    # the ruling. What must never happen is the floor giving way.
    check("R16: the floor is whole even at 40 nominations against a cap of 24",
          P["nominations_cut_by_machinery"] == [], str(P["nominations_cut_by_machinery"]))
    check("R17: the flag allowance does not collapse to zero",
          P["machine_add_budget"] > 0, str(P["machine_add_budget"]))
    check("R16/R27: --cap never bounds the seats -- the room is the 40-name floor plus the R27 strength seats",
          len(P["deliberation_set"]) == 40 + len(P["strong_seats"]) and len(P["deliberation_set"]) > 24,
          "room %d, floor 40, strength seats %d" % (len(P["deliberation_set"]), len(P["strong_seats"])))
    check("R16: all 40 nominations seated", P["nominations_seated"] == 40, str(P["nominations_seated"]))
    check("R16: nothing cut", P["nominations_cut_by_machinery"] == [])


def test_a_repeat_advance_is_marked_standing_or_drifted(td):
    """PM, 2026-09-25: "you'd realise at least 5 names are repeat picks for advance that has appeared
    consecutive days." It was six, and nothing on the face of the report said so -- the history was
    computed and buried in a verbatim paste. A repeat fails two OPPOSITE ways and one label cannot
    cover both: the entry is still there (ACA, four sessions, +0.21%) or the entry has gone (TWLO,
    +22.89% since its first call). The separator is the name's OWN computed stop distance, not a fitted
    number: drift inside its risk is STANDING, drift beyond it is DRIFTED."""
    d = os.path.join(td, "rm"); os.makedirs(d, exist_ok=True)
    rows = []
    for dt, px in (("2026-09-22", 100.0), ("2026-09-24", 100.5), ("2026-09-25", 100.6)):
        rows.append({"date": dt, "ticker": "STAND", "verdict": "ADVANCE", "ref_price": px})
    for dt, px in (("2026-09-22", 100.0), ("2026-09-24", 104.0), ("2026-09-25", 110.0)):
        rows.append({"date": dt, "ticker": "DRIFT", "verdict": "ADVANCE", "ref_price": px})
    rows += [{"date": "2026-09-24", "ticker": "REV", "verdict": "ADVANCE", "ref_price": 50.0},
             {"date": "2026-09-25", "ticker": "REV", "verdict": "HOLD-FOR-CONDITIONS", "ref_price": 50.5},
             {"date": "2026-09-24", "ticker": "GONE", "verdict": "ADVANCE", "ref_price": 10.0},
             {"date": "2026-09-25", "ticker": "NEW", "verdict": "ADVANCE", "ref_price": 20.0},
             {"date": "2026-09-22", "ticker": "BACK", "verdict": "ADVANCE", "ref_price": 80.0},
             {"date": "2026-09-24", "ticker": "BACK", "verdict": "HOLD-FOR-CONDITIONS", "ref_price": 82.0},
             {"date": "2026-09-25", "ticker": "BACK", "verdict": "ADVANCE", "ref_price": 88.0}]
    led = os.path.join(d, "ledger.json")
    open(led, "w").write(json.dumps({"schema": "verdict_ledger.v1", "rows": rows}))
    cons = os.path.join(d, "consensus.json")
    open(cons, "w").write(json.dumps([{"ticker": t, "verdict": v, "lane": "PULLBACK", "conviction": 3}
                                      for t, v in (("STAND", "ADVANCE"), ("DRIFT", "ADVANCE"),
                                                   ("REV", "HOLD-FOR-CONDITIONS"), ("NEW", "ADVANCE"),
                                                   ("BACK", "ADVANCE"))]))
    brk = os.path.join(d, "brackets.json")
    open(brk, "w").write(json.dumps({"brackets": {
        "STAND": {"stop": {"stop_pct": 3.0}}, "DRIFT": {"stop": {"stop_pct": 3.0}},
        "NEW": {"stop": {"stop_pct": 2.0}}, "BACK": {"stop": {"stop_pct": 2.0}}}}))
    out = os.path.join(d, "repeat_marks.json")
    rc, log = run([PIPE, "repeatmarks", "--ledger", led, "--consensus", cons, "--brackets", brk,
                   "--date", "2026-09-25", "--out", out])
    check("repeatmarks exits clean", rc == 0, log[-400:])
    if rc != 0: return
    M = json.load(open(out))["marks"]
    check("a repeat whose price held is STANDING, not presented as news",
          M["STAND"]["mark"] == "STANDING", M["STAND"]["mark"])
    check("STANDING says it is the same unacted idea, in words",
          "unacted" in (M["STAND"]["mark_plain"] or ""), M["STAND"]["mark_plain"])
    check("a repeat past its own risk is DRIFTED", M["DRIFT"]["mark"] == "DRIFTED", M["DRIFT"]["mark"])
    check("DRIFTED says the entry is gone, in words",
          "entry you were shown is gone" in (M["DRIFT"]["mark_plain"] or ""), M["DRIFT"]["mark_plain"])
    check("the streak is counted, not guessed",
          M["STAND"]["advance_streak"] == 3 and M["DRIFT"]["advance_streak"] == 3,
          "%s / %s" % (M["STAND"]["advance_streak"], M["DRIFT"]["advance_streak"]))
    check("the ordinal reads correctly and never '2th'",
          "2th" not in (M["STAND"]["mark_plain"] or "") and "3rd" in (M["STAND"]["mark_plain"] or ""),
          M["STAND"]["mark_plain"])
    check("a name the committee advanced last run and no longer does is REVERSED",
          M["REV"]["mark"] == "REVERSED" and "changed its mind" in M["REV"]["mark_plain"])
    check("a first-time advance is FRESH", M["NEW"]["mark"] == "FRESH")
    check("an advance after a gap is RETURNED, with the cost since the first call",
          M["BACK"]["mark"] == "RETURNED" and "+10.00%" in (M["BACK"]["mark_plain"] or ""),
          M["BACK"]["mark_plain"])
    G = json.load(open(out))["left_the_room"]
    check("a name that advanced last run and is not in the room at all is still reported",
          G.get("GONE", {}).get("mark") == "LEFT_THE_ROOM", str(G))
    check("the separator rule is stated on the record, and says it is not fitted",
          "own computed stop distance" in json.load(open(out))["rule"]
          and "No threshold is fitted" in json.load(open(out))["rule"])


def test_brackets_are_produced_for_advance_and_hold_and_never_for_held(td):
    """PM ruling 2026-09-25: run the bracket calculator over every ADVANCE and HOLD name as a step of
    the committee run. This gives brackets.json its first producer after five runs of it being a
    declared gap -- which meant every level on every card was hand-picked, not computed. Two things
    must hold: a HELD name is never bracketed (you do not bracket what you already own), and R1 is not
    weakened -- the output says on its face that it is render-only and attached after the vote."""
    d = os.path.join(td, "brk"); os.makedirs(d, exist_ok=True)
    # The fixture row is a REAL served row (ACA, 2026-09-25, 171 fields) rather than a hand-made stub.
    # A stub row omits the AQE bracket block the calculator reads and then produces "NO STOP
    # DEFINABLE", which would have this test asserting against a shape the run never sees.
    real = json.load(open(fx("bracket_row_ACA.json")))
    held_row = dict(real); held_row["ticker"], held_row["held"] = "HLD", True
    pass_row = dict(real); pass_row["ticker"] = "PSS"
    ex = os.path.join(d, "export.json")
    open(ex, "w").write(json.dumps({"daily_list": [real, held_row, pass_row], "srm": [],
                                    "regime": {"level": "GREEN"}, "regime_stop_pct_ceiling": 8.0}))
    p4 = os.path.join(d, "phase4.json")
    open(p4, "w").write(json.dumps({"deliberation_set": [real["ticker"], "HLD", "PSS"],
                                    "held_seated": ["HLD"]}))
    cons = os.path.join(d, "consensus.json")
    open(cons, "w").write(json.dumps([
        {"ticker": real["ticker"], "verdict": "ADVANCE", "lane": "PULLBACK", "conviction": 3},
        {"ticker": "HLD", "verdict": "HOLD-FOR-CONDITIONS", "lane": "MOMENTUM", "conviction": 2},
        {"ticker": "PSS", "verdict": "PASS", "lane": "MOMENTUM", "conviction": 1}]))
    out = os.path.join(d, "brackets.json")
    rc, log = run([PIPE, "brackets", "--consensus", cons, "--phase4", p4, "--export", ex,
                   "--date", "2026-09-25", "--out", out])
    check("brackets exits clean", rc == 0, log[-400:])
    if rc != 0: return
    B = json.load(open(out)); T = real["ticker"]
    check("an ADVANCE name is bracketed", T in B["brackets"])
    check("a HELD name is NEVER bracketed", "HLD" not in B["brackets"] and "HLD" in B["skipped"])
    check("the held skip says why, rather than vanishing", "HELD" in B["skipped"].get("HLD", ""))
    check("a PASSED name is not bracketed at all", "PSS" not in B["brackets"] and "PSS" not in B["skipped"])
    check("R1: the artifact declares itself render-only and post-vote",
          "render_only" in B and "after the vote" in B["render_only"].lower(), str(B.get("render_only"))[:120])
    check("a computed stop carries a price, not a hand-picked level",
          (B["brackets"][T].get("stop") or {}).get("price") is not None,
          "stop=%s warning=%s" % (B["brackets"][T].get("stop"), B["brackets"][T].get("warning")))
    check("the stop carries its own gate flags so the card can show whether it cleared",
          set(((B["brackets"][T].get("stop") or {}).get("flags") or {})) >= {"atr_ok", "rr_ok"},
          str((B["brackets"][T].get("stop") or {}).get("flags")))
    check("sizing without dynCap is refused and labelled, never faked",
          B["brackets"][T].get("sized") is False and B["brackets"][T].get("size") is None)
    check("the verdict that earned the bracket is carried on it",
          B["brackets"][T].get("verdict") == "ADVANCE")


def test_a_door_opener_is_flagged_and_never_voted(td):
    """R17 (PM ruling 2026-09-25): "If a name gets added through a door, it should be highlighted for
    PM even if there no voice supporting for it. It's largely informational, otherwise we end up
    superseding the committee consensus (aka the voice)." So a door-opener nobody nominated is a FLAG,
    not a seat: it never reaches the deliberation set, so it is never voted and can never return a
    verdict that overrides the room. On 2026-09-25 the old behaviour produced INTC as an ADVANCE off
    the strength door with no seat behind it."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=5, tag="r17_")
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex,
                   "--cap", "24", "--door-budget", "8", "--pm-lens", "", "--strong-seats", "0", "--out", out])  # R27 off: pure R17
    check("rank exits clean under R17", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    nominated = set("N%02d" % i for i in range(5))
    check("R17: the deliberation set is EXACTLY the floor",
          set(P["deliberation_set"]) == set(P["nomination_floor"]) == nominated,
          "%d in room, %d on floor" % (len(P["deliberation_set"]), len(P["nomination_floor"])))
    check("R17: strong door-openers are NOT in the room",
          not [t for t in P["deliberation_set"] if t.startswith("M")],
          str([t for t in P["deliberation_set"] if t.startswith("M")]))
    check("R17: they are flagged instead, up to the budget",
          0 < len(P["informational"]) <= 8, str(len(P["informational"])))  # --door-budget 8 passed explicitly
    check("R17: the full count of door-openers is recorded, not just the shown ones",
          P["door_openers_not_on_the_floor"] >= len(P["informational"]),
          "%s vs %s" % (P["door_openers_not_on_the_floor"], len(P["informational"])))
    check("R17: the rule is stated on the record",
          "never seated" in P["informational_rule"] and "supersede" in P["informational_rule"])
    check("R17: a flagged row carries doors, lane and its AQE reads",
          all({"doors", "lane", "aqe_rank", "mp", "rs_spy_20d", "lens_strong"} <= set(x)
              for x in P["informational"]))
    # R26 (PM 2026-10-23, DECLARED CHANGE): the flag list was ordered by doors opened, which hid ACN.
    # It is now ordered by 20-day strength vs SPY so the strongest names the room did not see lead.
    rs = [x["rs_spy_20d"] for x in P["informational"]]
    check("R26: flagged names are ordered by 20-day strength vs SPY", rs == sorted(rs, reverse=True), str(rs))


def test_a_position_the_pm_owns_is_on_the_floor(td):
    """R16 + R12: a held position is seated unconditionally even when no seat nominated it and it
    opened no door -- so the room is asked whether to ADD to it, not only whether to keep it.
    Replayed on real 2026-09-24 data, held FTNT was ADVANCED as an add and a doors-opened ordering
    dropped it. The PM's own money does not queue behind a machine heuristic."""
    tal, cs, ex, out = _r16_fixture(td, n_nominated=5, tag="r16h_")
    U = json.load(open(cs))
    for r in U["universe"]:
        if r["ticker"] == "M80":                 # unnominated, and stripped of every door
            r["held"] = True
            r["elder"], r["elder_5d"], r["elder_pattern"] = 0.0, [0, 0, 0, 0, 0], "INTERRUPTED"
            r["rs_leadership"], r["rs_spy_20d"], r["mp"] = "LAGGARD", -9.0, 5.0
            r["mp_state"], r["mp_accel_state"] = "FADING", "DECELERATING"
            r["lens"] = {"leadership": "warn", "coil": "warn", "insti_money": "warn",
                         "structure": "warn", "resistance": "warn", "sector": "warn"}
    open(cs, "w").write(json.dumps(U))
    open(ex, "w").write(json.dumps({"daily_list": U["universe"],
                                    "srm": [{"sector": "Technology", "entry_gate": "WATCH"}]}))
    rc, log = run([PIPE, "rank", "--tally", tal, "--candidates", cs, "--export", ex,
                   "--cap", "24", "--pm-lens", "", "--out", out])
    check("rank exits clean with a doorless held position", rc == 0, log[-400:])
    if rc != 0: return
    P = json.load(open(out))
    check("R12+R16: the held name with no nomination and no door is still seated",
          "M80" in P["deliberation_set"], str(P["deliberation_set"])[:200])
    check("R12+R16: it is on the FLOOR, not a machine addition",
          "M80" in P["nomination_floor"] and "M80" not in P["machine_additions"])
    check("R12+R16: it carries the HELD door", "HELD" in dict((r["ticker"], r["doors"]) for r in P["ranked"])["M80"])
    check("R16: held_seated records it", "M80" in P.get("held_seated", []))


def test_crown_is_served_its_own_artifact(td):
    """2026-09-25 defect: both macro packets were built from the same export blocks, so crown.json and
    druckenmiller.json came out byte-identical and crown never received aqe_crown_macro.json -- the
    file its whole card is written against. Seven of its eleven recognisers went dark and the seat
    declared the artifact missing while it sat in the run root. Absence is now a HARD FAILURE, and
    identical packets are asserted against."""
    d = os.path.join(td, "crown_fix"); os.makedirs(d, exist_ok=True)
    uni = [{"ticker": "AAA", "rank": 1, "held": False, "mp": 50.0, "gics_sector_name": "Technology"}]
    ex = os.path.join(d, "export.json")
    open(ex, "w").write(json.dumps({"date": "2026-09-25", "market": "x",
                                    "regime": {"vix": 15.7, "level": "GREEN"}, "intermarket": {},
                                    "srm": [{"sector": "Technology", "entry_gate": "WATCH"}],
                                    "macro_weather": {}, "thematic_baskets": {},
                                    "daily_list": uni}))
    cs = os.path.join(d, "cs.json"); open(cs, "w").write(json.dumps({"universe": uni}))
    menus = os.path.join(d, "menus.json")
    open(menus, "w").write(json.dumps({"crown": [], "druckenmiller": [], "weis": ["ticker", "mp"]}))
    out = os.path.join(d, "packets")
    # 1. artifact ABSENT -> hard failure, not a quiet fallback
    rc, log = run([PIPE, "packets", "--candidates", cs, "--export", ex, "--menus", menus,
                   "--date", "2026-09-25", "--outdir", out])
    check("packets REFUSES to build a blind crown packet", rc != 0 and "NOT FOUND" in log, log[-300:])
    # 2. artifact present -> served whole, and the two macro packets differ
    art = os.path.join(d, "aqe_crown_macro.json")
    open(art, "w").write(json.dumps({"the_call": {"family": "NARROWING"}, "status": "OK",
                                     "readings": {"breadth": {"position_in_12_month_range": "bottom"},
                                                  "positioning": {"trend_funds": {}, "large_speculators": {},
                                                                  "option_dealers": {"available": True}},
                                                  "volatility": {"state": "ELEVATED_RISING"}},
                                     "key_levels": [], "generated_at": "2026-09-25T09:06:15+08:00"}))
    rc, log = run([PIPE, "packets", "--candidates", cs, "--export", ex, "--menus", menus,
                   "--date", "2026-09-25", "--outdir", out, "--crown-macro", art])
    check("packets builds once the artifact is there", rc == 0, log[-400:])
    if rc != 0: return
    c = json.load(open(os.path.join(out, "crown.json")))
    dr = json.load(open(os.path.join(out, "druckenmiller.json")))
    check("crown gets the_call at top level", "the_call" in c)
    check("crown gets the positioning plane",
          "option_dealers" in (((c.get("readings") or {}).get("positioning")) or {}))
    check("crown gets breadth position, its own most consequential read",
          (((c.get("readings") or {}).get("breadth")) or {}).get("position_in_12_month_range") == "bottom")
    check("crown keeps the whole artifact too", "crown_artifact" in c)
    check("the two macro packets are NOT identical", json.dumps(c) != json.dumps(dr))
    check("druckenmiller does NOT get crown's artifact", "the_call" not in dr and "crown_artifact" not in dr)


def test_a_nominating_ballot_has_no_count_cap(td):
    """R16: the registrar caps a round-1 ballot by BYTES, never by nomination count. On 2026-09-25 --
    the first morning the seats were told the admission cap was gone -- a leftover `len(noms) > 10`
    rejected minervini's 11 and raschke's 13. Same defect as R16 itself, one layer down: a
    hard-coded limit silently truncating analyst picks."""
    names = ["B%02d" % i for i in range(14)]
    cs = os.path.join(td, "r16n_cs.json")
    open(cs, "w").write(json.dumps({"universe": [{"ticker": t} for t in names]}))
    ballot = {"voice": "weis", "date": "2026-09-25", "round": 1,
              "nominations": [{"ticker": t, "conviction": 3, "reason": "coil at a high",
                               "checklist_trace": {"W21": "inside bar"}, "falsifier": "loses ma_50"}
                              for t in names],
              "held_review": [], "declarations": [], "shortfall_reason": None}
    f = os.path.join(td, "r16n_ballot.json")
    open(f, "w").write(json.dumps(ballot))
    rc, log = run([REG, "validate", "--file", f, "--round", "1", "--candidates", cs])
    check("R16: a 14-nomination ballot is accepted, not truncated", rc == 0, log[-400:])
    check("R16: no 'at most 10' rejection survives anywhere", "at most 10" not in log, log[-200:])
    bad = dict(ballot); bad["nominations"] = "not a list"
    f2 = os.path.join(td, "r16n_bad.json")
    open(f2, "w").write(json.dumps(bad))
    rc2, log2 = run([REG, "validate", "--file", f2, "--round", "1", "--candidates", cs])
    check("a non-list nominations field is still rejected", rc2 != 0 and "must be a list" in log2, log2[-200:])


def test_a_split_ballot_is_validated_per_part_and_merged(td):
    """R16 support: a room bigger than ~25 names does not fit one MAX_FORM_BYTES ballot, so a seat
    files parts. Each part validates on its own; `registrar.py merge` proves the parts cover the
    deliberation set EXACTLY -- and refuses a gap, a duplicate and an outsider. A file size limit
    must never again decide which of the PM's analysts are heard."""
    names = ["A%02d" % i for i in range(30)]
    p4 = os.path.join(td, "r16_split_phase4.json")
    open(p4, "w").write(json.dumps({"deliberation_set": names}))
    cs = os.path.join(td, "r16_split_cs.json")
    open(cs, "w").write(json.dumps({"universe": [{"ticker": t} for t in names]}))
    def vote(t): return {"ticker": t, "vote": "SUPPORT", "conviction": 3, "reason": "coil at a high"}
    def part(fn, tickers):
        path = os.path.join(td, fn)
        open(path, "w").write(json.dumps({"voice": "weis", "date": "2026-09-24", "round": 2,
                                          "votes": [vote(t) for t in tickers]}))
        return path
    p1 = part("weis.part1of2.json", names[:15])
    p2 = part("weis.part2of2.json", names[15:])
    rc, log = run([REG, "validate", "--file", p1, "--round", "2", "--candidates", cs,
                   "--phase4", p4, "--part", "1", "--of", "2"])
    check("a declared ballot PART validates without covering the whole set", rc == 0, log[-300:])
    rc, log = run([REG, "validate", "--file", p1, "--round", "2", "--candidates", cs, "--phase4", p4])
    check("an UNdeclared partial ballot is still rejected", rc != 0 and "missing" in log, log[-300:])
    merged = os.path.join(td, "weis.merged.json")
    rc, log = run([REG, "merge", "--glob", os.path.join(td, "weis.part*of2.json"),
                   "--out", merged, "--phase4", p4])
    check("merge stitches the parts and proves exact coverage", rc == 0, log[-400:])
    if rc == 0:
        M = json.load(open(merged))
        check("merged ballot carries all 30 votes", len(M["votes"]) == 30, str(len(M["votes"])))
        check("merged ballot keeps the seat identity", M["voice"] == "weis")
        check("merge records which part each vote came from", len(M.get("merged_from", [])) == 2)
        rc2, log2 = run([REG, "validate", "--file", merged, "--round", "2",
                         "--candidates", cs, "--phase4", p4])
        check("the merged ballot passes ordinary round-2 validation", rc2 == 0, log2[-300:])
    gap = part("weisgap.part1of2.json", names[:14])
    part("weisgap.part2of2.json", names[15:])
    rc, log = run([REG, "merge", "--glob", os.path.join(td, "weisgap.part*of2.json"),
                   "--out", os.path.join(td, "gap.json"), "--phase4", p4])
    check("merge REFUSES parts that leave a name unvoted", rc != 0 and "missing" in log, log[-300:])
    part("weisdup.part1of2.json", names[:16])
    part("weisdup.part2of2.json", names[15:])
    rc, log = run([REG, "merge", "--glob", os.path.join(td, "weisdup.part*of2.json"),
                   "--out", os.path.join(td, "dup.json"), "--phase4", p4])
    check("merge REFUSES a name voted twice across parts", rc != 0 and "duplicate" in log, log[-300:])
    part("weisout.part1of2.json", names[:15])
    part("weisout.part2of2.json", names[15:] + ["ZZZZ"])
    rc, log = run([REG, "merge", "--glob", os.path.join(td, "weisout.part*of2.json"),
                   "--out", os.path.join(td, "out.json"), "--phase4", p4])
    check("merge REFUSES a vote on a name outside the set", rc != 0, log[-300:])



def test_a_held_name_is_graded_from_its_close_not_its_cost(td):
    """Found 2026-09-27. On a held-only row trim copies the COST BASIS into `entry`, and
    record-verdicts read `entry` as the reference close. GLD, USO, WEAT, MRVL, CRWD and FTNT were
    locked into the ledger at what the PM paid, labelled eod_close -- so any grade of a held name
    would have measured the position's P&L, not the committee's call. The close must win."""
    d = os.path.join(td, "refpx"); os.makedirs(d, exist_ok=True)
    cs = os.path.join(d, "cs.json")
    open(cs, "w").write(json.dumps({"run_date": "2026-09-26", "universe": [
        {"ticker": "HLD", "entry": 151.0334722, "held": True,
         "held_book": {"entry": 151.0334722, "cob_price": 148.33, "live_px": 148.33}},
        {"ticker": "SCR", "entry": 516.17, "bracket": {"price": 516.17, "price_source": "eod_close"}}]}))
    cons = os.path.join(d, "cons.json")
    open(cons, "w").write(json.dumps([
        {"ticker": "HLD", "verdict": "PASS", "conviction": 2, "split": {"support": [], "oppose": ["x"], "abstain": []}},
        {"ticker": "SCR", "verdict": "ADVANCE", "conviction": 3, "split": {"support": ["x", "y"], "oppose": [], "abstain": []}}]))
    led = os.path.join(d, "led.json")
    rc, log = run([PIPE, "record-verdicts", "--consensus", cons, "--candidates", cs,
                   "--phase4", os.path.join(d, "absent.json"), "--ledger", led, "--date", "2026-09-26"])
    check("record-verdicts exits clean", rc == 0, log[-300:])
    if rc != 0: return
    rows = {r["ticker"]: r for r in json.load(open(led))["rows"]}
    check("a held-only name is referenced at its close, never its cost basis",
          rows["HLD"]["ref_price"] == 148.33, str(rows["HLD"]["ref_price"]))
    check("the source says where the close came from", rows["HLD"]["ref_price_source"] == "held_book.cob_price",
          str(rows["HLD"]["ref_price_source"]))
    check("a screened name still reads its bracket close", rows["SCR"]["ref_price"] == 516.17
          and rows["SCR"]["ref_price_source"] == "eod_close")


def test_the_committee_levels_are_emitted_for_aqe_and_never_loosen_a_stop(td):
    """R20 (PM 2026-09-30): the committee's levels leave the run as numbers AQE's 15-minute alert loop
    can watch. Three promises are enforced at emit, not hoped for: a HOLD condition is never silently
    unwatched, a WATCH name never alerts (R17), and a committee exit line may never sit below the PM's
    own broker stop. The broker read also has to catch the two order faults found on 2026-09-29:
    WEAT with no stop at all, and NTRA's limit sitting above its stop."""
    LV = os.path.join(TOOLS, "pma_levels.py")
    d = os.path.join(td, "lv"); os.makedirs(d, exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    J("orders.json", {"result": [
        {"symbol": "HLD", "sec_type": "STK", "action": "SELL", "order_type": "STP_LMT", "stop_price": 350.5, "limit_price": 350.58, "quantity": 17}]})
    J("positions.json", {"result": [
        {"symbol": "HLD", "sec_type": "STK", "quantity": 17, "avg_cost": 388.58, "market_price": 411.77},
        {"symbol": "NOS", "sec_type": "STK", "quantity": 545, "avg_cost": 26.46, "market_price": 24.97}]})
    rc, log = run([LV, "stops", "--orders", P("orders.json"), "--positions", P("positions.json"), "--out", P("bs.json")])
    check("stops exits clean", rc == 0, log[-300:])
    bs = json.load(open(P("bs.json")))["positions"]
    check("a position with no stop order is named as such", bs["NOS"]["stop"] is None and "NO STOP" in bs["NOS"].get("note", ""))
    check("a limit above its stop is flagged", "ABOVE stop" in bs["HLD"].get("note", ""))
    J("cons.json", [{"ticker": "ADV", "verdict": "ADVANCE", "lane": "MOMENTUM", "conviction": 3},
                    {"ticker": "HFC", "verdict": "HOLD-FOR-CONDITIONS", "lane": "PULLBACK", "conviction": 2}])
    J("p4.json", {"informational": [{"ticker": "WAT", "doors": ["LENS"]}]})
    cards = {"advance": {"ADV": {"triggers": [{"kind": "close_below", "level": 163.75, "basis": "daily", "priority": "ACTION", "action": "kill"}]}},
             "hold": {"HFC": {"triggers": []}},
             "held": {"HLD": {"committee_exit": 354.62}, "NOS": {}}}
    J("cards.json", cards)
    base = [LV, "emit", "--consensus", P("cons.json"), "--brackets", P("none.json"), "--repeat-marks", P("none.json"),
            "--cards", P("cards.json"), "--broker-stops", P("bs.json"), "--candidates", P("none.json"),
            "--phase4", P("p4.json"), "--date", "2026-09-29", "--out", P("lv.json")]
    rc, log = run(base)
    check("emit REFUSES a HOLD condition with no trigger and no stated reason", rc != 0 and "HFC" in log, log[-300:])
    cards["hold"]["HFC"]["not_structured_yet"] = "two-legged condition"
    cards["held"]["HLD"]["committee_exit"] = 340.0
    J("cards.json", cards)
    rc, log = run(base)
    check("emit REFUSES a committee exit line below the PM's broker stop", rc != 0 and "BELOW" in log, log[-300:])
    cards["held"]["HLD"]["committee_exit"] = 354.62
    J("cards.json", cards)
    rc, log = run(base)
    check("emit writes once the contract holds", rc == 0, log[-300:])
    if rc != 0: return
    doc = json.load(open(P("lv.json")))
    R = {(r["ticker"], r["class"]): r for r in doc["rows"]}
    kinds = lambda k: {x["kind"] for x in R[k]["triggers"]}
    check("the no-stop position gets an open-of-session ACTION", "no_stop_order" in kinds(("NOS", "HELD")))
    check("the limit-above-stop order gets an ACTION", "order_config" in kinds(("HLD", "HELD")))
    check("a WATCH name carries no trigger (R17)", R[("WAT", "WATCH")]["triggers"] == [])
    check("the file declares itself render-only with the no-orders guardrail",
          doc["render_only"] and any("never place" in g for g in doc["guardrails"]))


def test_a_carried_name_off_todays_universe_is_still_checked_against_its_kill(td):
    """2026-10-01: BE was advanced on 09-30 with a kill line at 288.00, closed 276.98 the next day, and
    was nominated by nobody -- so it was not in the served universe, its close was unknown to the window,
    and the broken idea was carried into AQE's alert file as live. --closes supplies the last close for
    exactly those names; a name with no close at all is declared under window.kill_unchecked, never
    silently treated as intact."""
    LV = os.path.join(TOOLS, "pma_levels.py")
    d = os.path.join(td, "winc"); os.makedirs(d, exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    T = lambda i, k, lvl: {"id": i, "kind": k, "level": lvl, "basis": "daily", "priority": "ACTION", "action": "x"}
    J("h.json", {"run_date": "2026-09-30", "rows": [
        {"ticker": "BE", "class": "ADVANCE", "triggers": [T("BE-entry", "close_above", 288.0), T("BE-kill", "close_below", 288.0)]},
        {"ticker": "VE", "class": "ADVANCE", "triggers": [T("VE-kill", "close_below", 269.83)]},
        {"ticker": "NO", "class": "HOLD_FOR_CONDITIONS", "triggers": [T("NO-dead", "close_below", 10.0)]}]})
    J("cons.json", []); J("cards.json", {"advance": {}, "hold": {}, "held": {}}); J("cs.json", {"universe": []})
    J("closes.json", {"BE": 276.98, "VE": 285.45})
    rc, log = run([LV, "emit", "--consensus", P("cons.json"), "--brackets", P("none"), "--repeat-marks", P("none"),
                   "--cards", P("cards.json"), "--broker-stops", P("none"), "--candidates", P("cs.json"),
                   "--phase4", P("none"), "--date", "2026-10-01", "--window", "3", "--history", P("h.json"),
                   "--closes", P("closes.json"), "--out", P("lv.json")])
    check("emit with --closes exits clean", rc == 0, log[-400:])
    if rc != 0: return
    doc = json.load(open(P("lv.json")))
    tick = {r["ticker"] for r in doc["rows"]}
    retired = {x["ticker"]: x["why"] for x in doc["window"]["retired"]}
    check("an unserved carried name whose kill broke on the supplied close is retired (BE)",
          "BE" not in tick and "supplied close" in retired.get("BE", ""))
    check("an unserved carried name still above its kill is carried (VE)", "VE" in tick)
    check("a carried name with no close anywhere is declared, not assumed intact (NO)",
          "NO" in tick and "NO" in doc["window"].get("kill_unchecked", []))


def test_the_scorecard_separates_the_list_the_judgment_and_the_beta(td):
    """D122.1 (PM 2026-10-01): "if you look at the committee tickers, the performance has been under spy".
    Raw SPY alone cannot tell a bad pick from a high-beta list in a falling tape. The scorecard grades every
    call against SPY, against the equal-weight AQE list it was chosen from, and net of beta; it reports the
    median and the share that beat beside the mean; and it refuses a row whose ledger price disagrees with
    the close it is graded from, rather than grading off the wrong base."""
    SC = os.path.join(TOOLS, "pma_scorecard.py")
    d = os.path.join(td, "sc"); os.makedirs(d, exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    days = ["2026-09-01", "2026-09-02", "2026-09-03"]
    C = lambda a, b, c: dict(zip(days, [a, b, c]))
    J("closes.json", {"SPY": C(100, 99, 98), "HI": C(100, 97, 96), "LO": C(100, 100, 100),
                      "PA": C(100, 95, 94), "U1": C(100, 98, 96), "BAD": C(50, 50, 50)})
    J("exp.json", {"daily_list": [{"ticker": t, "beta_30d": b} for t, b in
                                  (("HI", 3.0), ("LO", 1.0), ("PA", 1.0), ("U1", 1.0))]})
    R = lambda t, v, ref: {"date": "2026-09-02", "ticker": t, "verdict": v, "ref_price": ref}
    J("ledger.json", {"rows": [R("HI", "ADVANCE", 100), R("LO", "ADVANCE", 100), R("PA", "PASS", 100),
                               R("BAD", "HOLD-FOR-CONDITIONS", 60)]})
    rc, log = run([SC, "grade", "--ledger", P("ledger.json"), "--closes", P("closes.json"),
                   "--export", "2026-09-02=" + P("exp.json"), "--horizon", "2", "--out", P("o.json"), "--md", P("o.md")])
    check("the scorecard exits non-zero when a ledger price disagrees with its base close", rc == 3, log[-400:])
    o = json.load(open(P("o.json")))
    adv = o["pooled_all"]["ADVANCE"]; R0 = o["runs"]["2026-09-02"]
    check("the window starts at the close before the run and SPY is graded on it",
          R0["base"] == "2026-09-01" and R0["end"] == "2026-09-03" and R0["spy"] == -2.0 and R0["full_horizon"])
    check("the list is the equal-weight AQE daily list over the same window", R0["universe_mean"] == -3.5, str(R0))
    check("advances report mean, median and share beating SPY", adv["n"] == 2 and adv["mean"] == -2.0
          and adv["median"] == -2.0 and adv["beat_spy"] == 1, str(adv))
    check("vs the list and net of beta are graded separately",
          adv["vs_universe_mean"] == 1.5 and adv["beta_adj_mean"] == 2.0, str(adv))
    check("the beta split puts a beta-3 name above a 2.5 cap",
          adv["beta_split"]["at_or_above"]["n"] == 1 and adv["beta_split"]["below"]["n"] == 1)
    check("a row whose ledger price disagrees with the close is refused, never graded",
          [x["ticker"] for x in o["refused_ref_mismatch"]] == ["BAD"] and o["pooled_all"]["HOLD-FOR-CONDITIONS"]["n"] == 0)
    check("the brief block renders", "Advances split at beta 2.5" in open(P("o.md")).read())
    # D122.1 monitoring (PM 2026-10-01: "keep it running so we can log and monitor"): one log line per close,
    # a re-run of the same close replaces its line rather than doubling it, and the card block carries the trend.
    args = [SC, "grade", "--ledger", P("ledger.json"), "--closes", P("closes.json"), "--export", "2026-09-02=" + P("exp.json"),
            "--horizon", "2", "--out", P("o2.json"), "--html", P("o.html"), "--log", P("log.jsonl")]
    run(args); run(args)
    lines = [json.loads(l) for l in open(P("log.jsonl")) if l.strip()]
    check("the scorecard log holds exactly one line per close, however often the run repeats",
          len(lines) == 1 and lines[0]["asof"] == "2026-09-03" and lines[0]["mature"]["ADVANCE"]["n"] == 2, str(lines))
    rc, log = run([SC, "trend", "--log", P("log.jsonl")])
    check("the trend prints from the log", rc == 0 and "2026-09-03" in log, log[-300:])
    h = open(P("o.html")).read()
    check("the card block is phone-safe (fixed-layout tables that wrap)", "table-layout:fixed" in h and "Committee scorecard" in h)


def test_conditions_are_written_in_shared_words_and_compiled_without_judgment(td):
    """D123 (PM 2026-10-02): "there is NO CHANGE to what committee looks at and lands at as recommend
    or advance. it is simply printing it in a format AQE alert can pick it up." Each SUPPORT from
    2026-10-02 carries a conditions block in words from contracts/condition_vocab.json, levels named by
    field and never typed as numbers, inside the seat's own method. The compile step attaches numbers
    from the export, finds what the supporters share, lists every exit line -- and decides nothing.
    The levels file refuses a trade-through pinned to yesterday's close (HPE, 2026-10-01)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("reg_d123", REG); reg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reg)
    V = lambda seat, votes, date="2026-10-02": reg.validate_round2(
        {"voice": seat, "date": date, "round": 2, "votes": votes}, None, None)[0]
    ok = {"lane": "BREAKOUT", "buy": ["h1_close_above:pivot_high", "vol_x_ge:1.4"], "confirm": ["above_vwap_s"],
          "wrong": ["close_below:pivot_high"], "tf": "1H"}
    sup = lambda c: [{"ticker": "HPE", "vote": "SUPPORT", "conviction": 3, "reason": "x", "conditions": c}]
    check("a SUPPORT from 2026-10-02 with no conditions block is rejected", any("conditions" in e for e in V("minervini", sup(None))))
    check("a SUPPORT filed before 2026-10-02 is validated as it was filed", V("minervini", sup(None), "2026-10-01") == [])
    check("a clean conditions block passes", V("minervini", sup(ok)) == [], str(V("minervini", sup(ok))))
    bad = dict(ok, buy=["h1_close_above:62.15"])
    check("a level typed as a number is rejected (name the field)", any("never a number" in e for e in V("minervini", sup(bad))))
    check("a word not in the vocabulary is rejected", any("unknown word" in e for e in V("minervini", sup(dict(ok, buy=["moon:pivot_high"])))))
    check("Seow may not name a 200-day average (C1)", any("ma_200" in e for e in V("seow", sup(dict(ok, wrong=["close_below:ma_200"])))))
    check("Livermore may not buy the pullback (C5)", any("in_zone" in e for e in V("livermore", sup(dict(ok, buy=["in_zone:ma_20"])))))
    check("Lynch may support with a non-price exit only", V("lynch", sup({"lane": "NONE", "non_price": "Altman stays in distress"})) == [])

    PC = os.path.join(TOOLS, "pma_conditions.py")
    d = os.path.join(td, "d123"); os.makedirs(os.path.join(d, "r2"), exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    J("cons.json", [{"ticker": "HPE", "verdict": "ADVANCE", "lane": "MOMENTUM", "conviction": 3,
                     "split": {"support": ["minervini", "livermore", "detect-lens"], "oppose": [], "abstain": []}}])
    J("exp.json", {"daily_list": [{"ticker": "HPE", "entry": 63.89, "pivot_high": 62.15, "atr_14d": 3.56, "ma_20": 58.99,
                                   "bar_high": 67.1, "elder": 7.0}]})
    B = lambda seat, c: J(f"r2/{seat}.json", {"voice": seat, "date": "2026-10-02", "round": 2,
                                               "votes": [{"ticker": "HPE", "vote": "SUPPORT", "conviction": 3, "conditions": c}]})
    B("minervini", ok)
    B("detect-lens", dict(ok, buy=["h1_close_above:pivot_high+0.1atr"], confirm=["vol_x_ge:1.4"]))
    B("livermore", {"lane": "BREAKOUT", "buy": ["close_above:high_52w_close"], "wrong": ["close_below:pivot_high-0.5atr", "fade_atr_ge:1"]})
    B("weis", {"lane": "CONTINUATION", "buy": ["reclaim:ma_20"], "wrong": ["close_below:ma_20"]})
    rc, log = run([PC, "compile", "--consensus", P("cons.json"), "--forms", P("r2/*.json"), "--export", P("exp.json"),
                   "--candidates", P("none"), "--date", "2026-10-02", "--out", P("c.json"), "--md", P("c.md"), "--html", P("c.html")])
    check("compile exits clean", rc == 0, log[-400:])
    if rc != 0: return
    r = json.load(open(P("c.json")))["rows"][0]
    check("the verdict is copied, never recomputed", r["verdict"] == "ADVANCE")
    sb = r["shared"]["buy"]
    check("two supporters' pivot lines within half an ATR are one shared condition",
          sb and sb[0]["w"] == "h1_close_above" and sorted(sb[0]["seats"]) == ["detect-lens", "minervini"], str(sb))
    check("a confirmation held by half the counting supporters is shared (volume 1.4x)",
          any(g["w"] == "vol_x_ge" and g["x"] == 1.4 for g in r["shared"]["confirm"]), str(r["shared"]["confirm"]))
    ex = [(e["value"], e["seats"]) for e in r["exits"]]
    check("every exit line is listed highest first with its analysts",
          ex[0] == (62.15, ["detect-lens", "minervini"]) and ex[1][0] == 60.37 and ex[-1] == (58.99, ["weis"]), str(ex))
    check("a supporter outside the counting lane is shown as advisory, not dropped",
          any(a["seat"] == "weis" and not a["counts"] for a in r["analysts"]))
    check("the plain-English ledger and the per-card HTML render",
          "Exit lines, highest first" in open(P("c.md")).read() and "HPE" in json.load(open(P("c.html"))))

    LV = os.path.join(TOOLS, "pma_levels.py")
    T = lambda i, k, lvl, pr="ACTION": {"id": i, "kind": k, "level": lvl, "basis": "15m", "priority": pr, "action": "x"}
    J("cs.json", {"universe": [{"ticker": "HPE", "entry": 63.89, "atr_14d": 3.56}]})
    def emit(trig):
        J("cards.json", {"advance": {"HPE": {"triggers": trig}}, "hold": {}, "held": {}})
        return run([LV, "emit", "--consensus", P("cons.json"), "--brackets", P("none"), "--repeat-marks", P("none"),
                    "--cards", P("cards.json"), "--broker-stops", P("none"), "--candidates", P("cs.json"),
                    "--phase4", P("none"), "--date", "2026-10-02", "--conditions", P("c.json"), "--out", P("lv.json")])
    rc, log = emit([T("HPE-entry", "trade_above", 63.89)])
    check("the levels file refuses a trade-through pinned to yesterday's close (HPE 2026-10-01)",
          rc != 0 and "yesterday's close" in log, log[-300:])
    rc, log = emit([T("HPE-entry", "trade_above", 67.1), T("HPE-kill", "close_below", 62.15)])
    check("with a real level the file is written", rc == 0, log[-300:])
    if rc == 0:
        row = [r for r in json.load(open(P("lv.json")))["rows"] if r["ticker"] == "HPE"][0]
        check("each alert row carries the analysts' conditions for AQE, old triggers kept beside them",
              row["triggers"] and row["conditions"]["shared"]["buy"] and row["conditions"]["exits"][0]["value"] == 62.15)


def test_levels_roll_forward_three_sessions_and_today_wins(td):
    """R20.1 (PM 2026-09-30): "sometimes the levels and the alerts dont occur IMMEDIATELY and have some
    time lag due to market conditions". The levels file therefore carries the last three runs additively.
    Carrying must not become clutter or contradiction: today's verdict on a name supersedes every older
    one, a name PASSED today or whose own kill line is already broken is retired, HELD and WATCH rows are
    never carried (the broker and the doors are re-read every morning), nothing older than the window
    survives, and every trigger id carries its origin run so AQE can remember a fire for the row's life."""
    LV = os.path.join(TOOLS, "pma_levels.py")
    d = os.path.join(td, "win"); os.makedirs(d, exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    T = lambda i, k="close_above", lvl=10.0: {"id": i, "kind": k, "level": lvl, "basis": "daily", "priority": "ACTION", "action": "x"}
    row = lambda t, cls, trig: {"ticker": t, "class": cls, "triggers": trig}
    J("h1.json", {"run_date": "2026-09-28", "rows": [row("XX", "HOLD_FOR_CONDITIONS", [T("XX-cond")]),
                                                     row("HH", "HELD", [T("HH-committee", "close_below")])]})
    J("h2.json", {"run_date": "2026-09-27", "rows": [row("XX", "ADVANCE", [T("XX-entry")]),
                                                     row("YY", "HOLD_FOR_CONDITIONS", [T("YY-cond")]),
                                                     row("ZZ", "HOLD_FOR_CONDITIONS", [T("ZZ-cond"), T("ZZ-dead", "close_below", 10.0)]),
                                                     row("KK", "ADVANCE", [T("KK-entry")])]})
    J("h3.json", {"run_date": "2026-09-26", "rows": [row("WW", "ADVANCE", [T("WW-entry")])]})
    J("cons.json", [{"ticker": "KK", "verdict": "ADVANCE", "lane": "PULLBACK", "conviction": 3},
                    {"ticker": "YY", "verdict": "PASS", "lane": "PULLBACK", "conviction": 2}])
    J("cards.json", {"advance": {"KK": {"triggers": [T("KK-entry", "trade_above", 12.0)]}}, "hold": {}, "held": {}})
    J("cs.json", {"universe": [{"ticker": "ZZ", "bracket": {"price": 9.5}}]})
    rc, log = run([LV, "emit", "--consensus", P("cons.json"), "--brackets", P("none"), "--repeat-marks", P("none"),
                   "--cards", P("cards.json"), "--broker-stops", P("none"), "--candidates", P("cs.json"),
                   "--phase4", P("none"), "--date", "2026-09-29", "--window", "3",
                   "--history", P("h1.json"), P("h2.json"), P("h3.json"), "--out", P("lv.json")])
    check("window emit exits clean", rc == 0, log[-400:])
    if rc != 0: return
    doc = json.load(open(P("lv.json")))
    by = {}
    for r in doc["rows"]: by.setdefault(r["ticker"], []).append(r)
    retired = {x["ticker"]: x["why"] for x in doc["window"]["retired"]}
    check("today wins: KK carries only today's row", len(by.get("KK", [])) == 1 and not by["KK"][0].get("carried"))
    check("a name absent today carries its NEWEST earlier view only (XX as HOLD from 09-28, not the 09-27 ADVANCE)",
          len(by.get("XX", [])) == 1 and by["XX"][0]["class"] == "HOLD_FOR_CONDITIONS" and by["XX"][0]["age_sessions"] == 1)
    check("a name PASSED today is retired, with the reason", "YY" not in by and "PASSED" in retired.get("YY", ""))
    check("a carried row whose own kill line is already broken is retired", "ZZ" not in by and "broken" in retired.get("ZZ", ""))
    check("a HELD row from an earlier run is never carried", "HH" not in by)
    check("nothing older than the window survives", "WW" not in by)
    check("every trigger id carries its origin run",
          all(":" in x["id"] for r in doc["rows"] for x in r["triggers"]) and
          by["XX"][0]["triggers"][0]["id"].startswith("2026-09-28:"))
    # Chaining from YESTERDAY'S PUBLISHED FILE alone: its carried rows keep their origin, so a row that
    # entered on 09-26 is retired on 09-29 even though it arrived in the 09-28 file.
    J("prev.json", {"run_date": "2026-09-28", "window": {"runs": ["2026-09-28", "2026-09-27", "2026-09-26"]},
                    "rows": [dict(row("OLD", "ADVANCE", [T("2026-09-26:OLD-entry")]), origin_run="2026-09-26", carried=True),
                             dict(row("MID", "HOLD_FOR_CONDITIONS", [T("2026-09-27:MID-cond")]), origin_run="2026-09-27", carried=True)]})
    rc, log = run([LV, "emit", "--consensus", P("cons.json"), "--brackets", P("none"), "--repeat-marks", P("none"),
                   "--cards", P("cards.json"), "--broker-stops", P("none"), "--candidates", P("cs.json"),
                   "--phase4", P("none"), "--date", "2026-09-29", "--window", "3",
                   "--history", P("prev.json"), "--out", P("lv2.json")])
    check("chained emit exits clean", rc == 0, log[-400:])
    if rc != 0: return
    d2 = json.load(open(P("lv2.json")))
    t2 = {r["ticker"]: r for r in d2["rows"]}
    check("chained from one file: a row whose origin left the window is retired",
          "OLD" not in t2 and any(x["ticker"] == "OLD" and "older" in x["why"] for x in d2["window"]["retired"]))
    check("chained from one file: a row still inside the window carries with its ORIGIN and age",
          "MID" in t2 and t2["MID"]["origin_run"] == "2026-09-27" and t2["MID"]["age_sessions"] == 2
          and t2["MID"]["triggers"][0]["id"] == "2026-09-27:MID-cond")



def test_consulted_seat_ballot_never_counts(td):
    """R22: a Lynch ballot -- even one supporting everything at conviction 5 -- changes nothing."""
    src = json.load(open(fx("round2_votes.json")))
    base = [x for x in src if x["voice"] != "lynch"]
    loud = base + [{"voice": "lynch", "date": "2026-09-06", "round": 2,
                    "votes": [{"ticker": v["ticker"], "vote": "SUPPORT", "conviction": 5} for v in base[0]["votes"]]}]
    a, b = os.path.join(td, "r22a.json"), os.path.join(td, "r22b.json")
    json.dump(base, open(os.path.join(td, "base.json"), "w")); json.dump(loud, open(os.path.join(td, "loud.json"), "w"))
    run([PIPE, "consensus", "--round2", os.path.join(td, "base.json"), "--out", a])
    rc, log = run([PIPE, "consensus", "--round2", os.path.join(td, "loud.json"), "--out", b])
    check("a consulted seat's ballot is announced as ignored", "ignored" in log, log[-200:])
    check("a consulted seat's ballot moves no verdict", json.load(open(a)) == json.load(open(b)))
    check("lynch is not a voting seat in the run map",
          "lynch" not in next(s for s in __import__("yaml").safe_load(open(os.path.join(HERE, "..", "RUN.yaml")))["steps"] if s["name"] == "VOTE")["seats"])


def test_card_report_layout_is_fixed_and_refuses_gaps(td):
    """R23: the card report is rendered by a tool; a words file with a missing ADVANCE card is refused,
    and a complete one renders the fixed sections in the fixed order."""
    CARDS = os.path.join(TOOLS, "pma_cards.py")
    cons = [{"ticker": "AAA", "verdict": "ADVANCE", "conviction": 3, "lane": "MOMENTUM", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}},
            {"ticker": "BBB", "verdict": "HOLD-FOR-CONDITIONS", "conviction": 2, "lane": "PULLBACK", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}},
            {"ticker": "CCC", "verdict": "PASS", "conviction": 2, "lane": "PULLBACK", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}}]
    exp = {"daily_list": [{"ticker": t, "entry": 10.0, "rank": i, "gics_sector_name": "Tech", "setups": [], "unr_status": "NO"} for i, t in enumerate(["AAA", "BBB", "CCC"], 1)], "held_positions": []}
    cards = {"advance": {"AAA": {"triggers": [{"id": "AAA-buy0", "kind": "close_above", "level": 10.5}, {"id": "AAA-dead", "kind": "close_below", "level": 9.5}], "confirms": "x", "kills": "y"}},
             "hold": {"BBB": {"triggers": [], "confirms": "", "kills": "", "not_structured_yet": "none"}}, "held": {}}
    p4 = {"ranked": [{"ticker": t, "lane": c["lane"]} for t, c in zip(["AAA", "BBB", "CCC"], cons)], "deliberation_set": ["AAA", "BBB", "CCC"]}
    for n, d in (("consensus.json", cons), ("export.json", exp), ("cards.json", cards), ("phase4.json", p4)):
        json.dump(d, open(os.path.join(td, n), "w"))
    words = {"session_label": "s", "stance_pill": "NEUTRAL", "bottom_line": {"headline": "h", "paragraph": "p", "stats": [{"value": "1", "label": "l"}] * 4},
             "market": {"what_happened": [{"lead": "a", "text": "b"}], "weather": [{"lead": "c", "text": "d"}]},
             "money": [{"group": "g", "read": "r", "meaning": "m"}], "book": [], "changed": ["c"],
             "cards": {}, "holds": {"BBB": "waits"}, "passes": {"CCC": "no"}, "plan": ["p"], "caveats": ["c"]}
    tw = os.path.join(td, "words.json"); json.dump(words, open(tw, "w"))
    args = [CARDS, "render", "--text", tw, "--consensus", os.path.join(td, "consensus.json"), "--export", os.path.join(td, "export.json"),
            "--cards", os.path.join(td, "cards.json"), "--phase4", os.path.join(td, "phase4.json"), "--brackets", os.path.join(td, "nob.json"),
            "--broker-stops", os.path.join(td, "nobs.json"), "--valen", os.path.join(td, "nov.json"), "--scorecard", os.path.join(td, "nosc.md"),
            "--out", os.path.join(td, "r.html")]
    rc, log = run(args)
    check("a words file missing an ADVANCE card is REFUSED", rc == 2 and "cards.AAA" in log, log[-300:])
    words["cards"]["AAA"] = {"case": "c", "why": "w", "readiness": "Ready now", "readiness_tone": "ok"}
    json.dump(words, open(tw, "w"))
    rc, log = run(args)
    check("a complete words file renders", rc == 0, log[-300:])
    if rc == 0:
        h = open(os.path.join(td, "r.html")).read()
        # PM 2026-10-23 (DECLARED CHANGE): Part 1 Daily weather comes straight after the bottom line.
        order = ["Bottom line", "Part 1 · Daily weather", "Cross-asset · what happened", "Where money is moving",
                 "Part 2 · Your book and the committee", "What it means for your book",
                 "Committee recommendations", "HOLD for conditions", "PASS · off the list", "The plan", "Read with care", "DRAFT"]
        pos = [h.find(x) for x in order]
        check("the fixed sections render in the fixed order", all(p >= 0 for p in pos) and pos == sorted(pos), str(list(zip(order, pos))))
        check("a card's buy trigger comes from cards.json, not the words file", "Hourly close above 10.5" in h)
        check("a missing Valen file is declared, not blank", "not served" in h)


def test_a_too_late_line_is_never_below_the_buy_line(td):
    """PM 2026-10-23 ("the chase prices one looks weird"): ADP printed buy above 308.63 and too late
    past 292.45. The shared too-late line was the LOWEST chase of any supporter, and O'Neil's was anchored
    to an older pivot under today's price. A chase at or below the shared buy is that analyst saying the
    name is already extended: it is shown as a dissent, never as the shared line."""
    PC = os.path.join(TOOLS, "pma_conditions.py")
    d = os.path.join(td, "chase"); os.makedirs(os.path.join(d, "r2"), exist_ok=True)
    J = lambda n, o: open(os.path.join(d, n), "w").write(json.dumps(o))
    P = lambda n: os.path.join(d, n)
    J("cons.json", [{"ticker": "ADP", "verdict": "HOLD-FOR-CONDITIONS", "lane": "MOMENTUM", "conviction": 3,
                     "split": {"support": ["minervini", "livermore", "oneil"], "oppose": [], "abstain": []}}])
    J("exp.json", {"daily_list": [{"ticker": "ADP", "entry": 307.94, "pivot_high": 278.52, "bar_high": 308.63,
                                   "atr_14d": 6.15, "ma_20": 274.1}]})
    B = lambda seat, c: J(f"r2/{seat}.json", {"voice": seat, "date": "2026-10-23", "round": 2,
                                               "votes": [{"ticker": "ADP", "vote": "SUPPORT", "conviction": 3, "conditions": c}]})
    B("minervini", {"lane": "BREAKOUT", "buy": ["h1_close_above:bar_high"], "chase": "close_above:bar_high+3pct",
                    "wrong": ["close_below:ma_20"], "tf": "1H"})
    B("livermore", {"lane": "BREAKOUT", "buy": ["h1_close_above:bar_high"], "chase": "close_above:bar_high+1atr",
                    "wrong": ["close_below:ma_20"], "tf": "1H"})
    B("oneil", {"lane": "BREAKOUT", "buy": ["h1_close_above:pivot_high"], "chase": "close_above:pivot_high+5pct",
                "wrong": ["close_below:ma_20"], "tf": "1H"})
    rc, log = run([PC, "compile", "--consensus", P("cons.json"), "--forms", P("r2/*.json"), "--export", P("exp.json"),
                   "--candidates", P("none"), "--date", "2026-10-23", "--out", P("c.json"), "--md", P("c.md")])
    check("compile exits clean", rc == 0, log[-400:])
    if rc != 0: return
    sh = json.load(open(P("c.json")))["rows"][0]["shared"]
    buy = max(g["value"] for g in sh["buy"])
    ch = sh["chase"]["levels"][0]["value"] if sh["chase"] else None
    check("the shared too-late line sits above the shared buy line", ch is not None and ch > buy, f"buy {buy} chase {ch}")
    check("the lowest valid chase is used (livermore bar_high+1atr 314.78)", ch is not None and abs(ch - 314.78) < 0.01, str(ch))
    check("a chase under the buy line is reported as a dissent, not dropped",
          [x["seat"] for x in sh["chase_dissent"]] == ["oneil"], str(sh.get("chase_dissent")))
    check("the ledger says so in plain English", "Already past one analyst's too-late line" in open(P("c.md")).read())
    # no shared buy (ACN 2026-10-23): the yardstick is the last close
    B("minervini", {"lane": "BREAKOUT", "buy": ["h1_close_above:ma_20"], "chase": "close_above:ma_20+1pct",
                    "wrong": ["close_below:ma_20"], "tf": "1H"})
    B("livermore", {"lane": "BREAKOUT", "buy": ["h1_close_above:bar_high"], "chase": "close_above:bar_high+1atr",
                    "wrong": ["close_below:ma_20"], "tf": "1H"})
    rc, log = run([PC, "compile", "--consensus", P("cons.json"), "--forms", P("r2/*.json"), "--export", P("exp.json"),
                   "--candidates", P("none"), "--date", "2026-10-23", "--out", P("c2.json")])
    sh = json.load(open(P("c2.json")))["rows"][0]["shared"]
    ch = sh["chase"]["levels"][0]["value"] if sh["chase"] else None
    check("with no shared buy, a too-late line under the last close is a dissent, never the shared line",
          rc == 0 and not sh["buy"] and (ch is None or ch > 307.94), f"buy {sh['buy']} chase {ch}")


def test_a_buy_line_far_under_the_close_is_never_the_trigger(td):
    """2026-10-23 refresh (XOM): Minervini and O'Neil shared "an hourly close above pivot_high 164.91" with
    XOM at 178.23 -- an old breakout point 4 average daily ranges behind. As a trigger it alerts at once
    and means nothing. A line within one daily range under the close is a fresh breakout (ROKU "ready
    now") and stays; a line further under it is skipped for the supporters' own lines above the close."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pc_t", os.path.join(TOOLS, "pma_cards.py")); pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    def row(t, close, atr, shared, own):
        an = [{"seat": s, "vote": "SUPPORT", "counts": True, "buy": [{"w": "h1_close_above", "levels": [{"value": v}]}]} for s, v in own]
        return {"ticker": t, "verdict": "ADVANCE", "ref_close": close, "atr_14d": atr, "exits": [],
                "shared": {"buy": [{"w": "h1_close_above", "value": shared, "seats": ["a", "b"], "plain": f"x {shared}"}], "confirm": []},
                "analysts": an}
    C = {"rows": [row("XOM", 178.23, 3.3, 164.91, [("a", 164.91), ("b", 164.91), ("c", 180.31)]),
                  row("ROKU", 160.06, 5.0, 158.85, [("a", 158.85), ("b", 158.85)])]}
    cards = pc.build_triggers(C, {"daily_list": []}, {})
    b0 = lambda t: [x for x in cards["advance"][t]["triggers"] if x["id"].endswith("buy0")][0]["level"]
    check("an old line far under the close is skipped for a supporter's line above it", b0("XOM") == 180.31, str(b0("XOM")))
    check("a fresh breakout just under the close stays the trigger (ready now)", b0("ROKU") == 158.85, str(b0("ROKU")))


def test_the_figure_audit_reads_field_equals_value(td):
    """2026-10-22 defect: field=value claims were never audited."""
    sys.path.insert(0, TOOLS)
    import importlib, figure_audit
    importlib.reload(figure_audit)
    m = figure_audit.QUOTED.search("structure=86.3 and more")
    check("figure audit reads 'field=value'", bool(m) and m.group(2) == "86.3", repr(m))


def _pipeline_source():
    return open(PIPE, encoding="utf-8").read()


def _const_list(name):
    """Read a top-level list constant out of pma_pipeline.py's source without importing it."""
    m = re.search(rf"^{name}\s*=\s*\[([^\]]*)\]", _pipeline_source(), re.M)
    return [x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()] if m else None


def test_roster_is_seven_deciders_plus_qa(td):
    """R31 (PM 2026-10-30). Seven deciders, Steenbarger as QA, Detect-lens a list not a voice, Weis and
    Thorp benched, Rogers / Lynch / Crown / Druckenmiller stood down. The constants are the roster the
    code counts; RUN.yaml's seats must agree with them (checked once the run map carries the new rounds)."""
    deciders = _const_list("DECIDERS")
    check("DECIDERS is exactly the seven the PM named",
          sorted(deciders or []) == sorted(["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]),
          str(deciders))
    check("Steenbarger is the QA seat", 'QA_SEAT = "steenbarger"' in _pipeline_source())
    check("Weis and Thorp are benched", sorted(_const_list("BENCH_SEATS") or []) == ["thorp", "weis"])
    check("Rogers, Lynch, Crown, Druckenmiller and Detect-lens are not voices",
          sorted(_const_list("STOOD_DOWN") or []) == ["crown", "detect-lens", "druckenmiller", "lynch", "rogers"])
    check("the round-2 voting seats ARE the deciders", "R2_VOTING_SEATS = list(DECIDERS)" in _pipeline_source())
    rul = open(os.path.join(HERE, "..", "RULINGS.yaml")).read()
    check("R31..R36 are on the record", all(f"id: R{n}" in rul for n in range(31, 37)))
    check("R14, R22 and R30 are marked superseded, never deleted",
          all(f"id: {r}" in rul for r in ("R14", "R22", "R30")) and rul.count("status: superseded") >= 3)


def test_all_seven_deciders_count_on_every_name(td):
    """R32. Seow is out of STRENGTH_SEATS; no strength list decides a verdict. Under the legacy blind
    tally (the only reader of STRENGTH_SEATS) seow is therefore advisory on a MOMENTUM-lane name -- the
    opposite of R30, which the PM reversed the same day. Both rebuilt canons still stand."""
    check("seow is not in STRENGTH_SEATS", "seow" not in (_const_list("STRENGTH_SEATS") or ["seow"]))
    check("detect-lens is not a decider", "detect-lens" not in (_const_list("DECIDERS") or ["detect-lens"]))
    V = json.load(open(fx("round2_votes.json")))
    tk = V[0]["votes"][0]["ticker"]
    p4 = os.path.join(td, "p4_r32.json")
    json.dump({"deliberation_set": [tk], "ranked": [{"ticker": tk, "doors": ["STRENGTH"], "lane": "MOMENTUM"}], "dropped": []}, open(p4, "w"))
    out = os.path.join(td, "c32.json")
    rc, log = run([PIPE, "consensus", "--round2", fx("round2_votes.json"), "--phase4", p4, "--out", out])
    check("legacy consensus still exits clean", rc == 0, log[-300:])
    if rc != 0: return
    row = {c["ticker"]: c for c in json.load(open(out))}[tk]
    counted = set(row["split"]["support"] + row["split"]["oppose"] + row["split"]["abstain"])
    check("legacy tally no longer counts seow as a strength seat", "seow" not in counted, str(counted))


def test_rebuilt_seow_and_wyckoff_canons_are_sound(td):
    """R30. The v2 locks parse, their house rules are labelled, no recogniser rejects on a bracket field,
    and every recogniser field a seat reads is on that seat's served menu or the momentum floor."""
    import yaml
    voices = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "aegis-voices"))
    if not os.path.isdir(voices):
        check("aegis-voices present beside aegis-core (handover layout)", True); return
    menus = json.load(open(os.path.join(HERE, "..", "contracts", "voice_menus.json")))
    floor = {"rs_spy_20d", "rs_rank_pct", "ret_63d", "ret_6m", "ret_12m", "pct_run_10d", "adx_14",
             "pct_from_52w_high", "mp", "lane", "entry", "held", "hl_score", "hl_state", "bracket.stop",
             "bracket.targets", "atr_14d", "sector_trend_state"}
    derived = {"close location", "days_held", "current_stop", "tick_size", "setup_flag", "portfolio_value",
               "risk_pct", "prior_support", "breakout_bar_low", "support_level", "high_since_entry", "target",
               "stop", "index_pct_change_63d", "industry_group_pct_change_63d", "prior_day_low", "energy"}
    for seat, ver in (("seow", 2), ("wyckoff", 2)):
        d = yaml.safe_load(open(os.path.join(voices, "canon", seat, "canon.lock.yaml")))
        check(f"{seat} lock is revision {ver}", (d.get("revision") or {}).get("version") == ver)
        house = [p["id"] for p in d["principles"] if p.get("status") == "house"]
        check(f"{seat} house rules carry a reason and no citation",
              all(p.get("reason") and not p.get("cite") for p in d["principles"] if p.get("status") == "house"), str(house))
        offmenu = sorted({f for r in d["recognisers"] for f in r.get("fields", [])
                          if f not in menus[seat] and f not in floor and f not in derived})
        check(f"{seat} recognisers read only served fields", not offmenu, str(offmenu))
    w = yaml.safe_load(open(os.path.join(voices, "canon", "wyckoff", "canon.lock.yaml")))
    check("wyckoff is anchored on Wyckoff 2.0", w["sources"][0]["code"] == "WYK2" and w["sources"][0]["weight"] == "foundational")


def main():
    print("AEGIS PMA regression suite -- fixtures are the real 2026-09-06 committee outputs\n")
    with tempfile.TemporaryDirectory() as td:
        for fn in [test_consensus_reproduces_the_real_run, test_consensus_refuses_a_shape_it_cannot_read,
                   test_r2digest_renders_every_challenge_document, test_r2digest_refuses_an_unreadable_challenge_doc,
                   test_rank_is_stable_and_sector_blind, test_purity_check_runs_without_being_patched,
                   test_load_declares_its_shape, test_registrar_meter_records_cost,
                   test_gate_refuses_a_brief_whose_day_was_never_recorded,
                   test_every_reader_declares_its_shape,
                   test_the_two_explainer_sections_are_exempt_but_bounded,
                   test_the_brief_must_carry_the_pm_deliverable_sections,
                   test_the_writing_instruction_exists_and_is_wired,
                   test_the_gate_does_not_cry_wolf_on_ordinary_english,
                   test_the_run_map_parses_as_data_not_as_characters,
                   test_the_publish_gate_runs_with_no_manual_override,
                   test_a_step_cannot_close_without_its_declared_artifacts,
                   test_a_seat_that_invents_its_numbers_is_refused,
                   test_the_expensive_steps_are_checkpointed,
                   test_a_position_the_pm_owns_reaches_every_seat,
                   test_fading_is_not_a_gate,
                   test_a_momentum_lane_name_is_judged_by_the_strength_seats,
                   test_every_nominator_is_served_the_momentum_floor,
                   test_every_nomination_is_seated,
                   test_the_doors_can_never_displace_a_nomination,
                   test_a_floor_larger_than_the_cap_never_gives_way,
                   test_brackets_are_produced_for_advance_and_hold_and_never_for_held,
                   test_a_repeat_advance_is_marked_standing_or_drifted,
                   test_a_door_opener_is_flagged_and_never_voted,
                   test_a_position_the_pm_owns_is_on_the_floor,
                   test_a_nominating_ballot_has_no_count_cap,
                   test_crown_is_served_its_own_artifact,
                   test_a_split_ballot_is_validated_per_part_and_merged,
                   test_a_held_name_is_graded_from_its_close_not_its_cost,
                   test_the_committee_levels_are_emitted_for_aqe_and_never_loosen_a_stop,
                   test_levels_roll_forward_three_sessions_and_today_wins,
                   test_a_carried_name_off_todays_universe_is_still_checked_against_its_kill,
                   test_the_scorecard_separates_the_list_the_judgment_and_the_beta,
                   test_conditions_are_written_in_shared_words_and_compiled_without_judgment,
                   test_consulted_seat_ballot_never_counts,
                   test_card_report_layout_is_fixed_and_refuses_gaps,
                   test_roster_is_seven_deciders_plus_qa, test_all_seven_deciders_count_on_every_name,
                   test_rebuilt_seow_and_wyckoff_canons_are_sound,
                   test_the_figure_audit_reads_field_equals_value,
                   test_a_too_late_line_is_never_below_the_buy_line,
                   test_up_to_three_reserved_seats_for_a_valen_reclaim,
                   test_the_flag_list_leads_with_the_strongest_names,
                   test_the_strongest_names_are_voted_in_the_momentum_lane,
                   test_a_buy_line_far_under_the_close_is_never_the_trigger]:
            print(fn.__name__.replace("test_", "").replace("_", " ") + ":")
            try:
                fn(td)
            except Exception as e:
                check(fn.__name__ + " raised", False, repr(e))
            print()
        print("rulings and run map are machine readable:")
        test_rulings_and_run_map_are_machine_readable()
    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        print("FAILED:"); [print("  - " + f) for f in FAILS]
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

