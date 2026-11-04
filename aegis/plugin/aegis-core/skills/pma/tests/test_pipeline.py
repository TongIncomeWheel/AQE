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
import json, os, re, shutil, subprocess, sys, tempfile

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
    run([REG, "--manifest", m, "tick", "--step", "VOTE", "--status", "done", "--force-incomplete"])   # no forms here; tick now refuses an empty glob (review finding 7)
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

    for f in ("consensus.json", "committee_record.json", "verdict_ledger.json"):   # brackets.json is BRACKET's (R18), not DECIDE's; committee_record.json is R35's
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
    # Contract audit 2026-11-02: two tool steps ARE checkpointed, for reasons other than token cost.
    # GATHER's push is the RUN LOCK (run_manifest.json on main before any seat is spawned, read by the
    # READY watcher and the pma-auto backstop so two committees never start the same day); PUBLISH's
    # push is the LAST write, so the manifest the 18:00 gate reads from origin/main shows CHECK /
    # LEVELS / REPORT / PUBLISH done (before this, the last push was after WRITE and `check.py chain`
    # would have FAILed every clean run). Every other tool step stays un-checkpointed: a re-run is
    # cheaper than a push.
    tool_cp = sorted(s["name"] for s in M["steps"] if s.get("kind") == "tool" and s.get("checkpoint_after"))
    check("the only checkpointed tool steps are the run lock (GATHER) and the final manifest push (PUBLISH)",
          tool_cp == ["GATHER", "PUBLISH"], f"tool steps checkpointed: {tool_cp}")
    check("PUBLISH's checkpoint pushes the receipt the tick checks", "publish_receipt.json" in (cp.get("tool") or ""))
    check("the policy says why the first and last pushes exist", "lock" in (cp.get("first_and_last") or "").lower()
          and "18:00" in (cp.get("first_and_last") or ""))
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


def test_the_conductor_tells_the_desk_when_done_and_ships_what_the_desk_shows(td):
    """PM 2026-11-02: "the report appears on the desk automatically each day; the conductor needs a done message
    to the desk." The desk renders FROM MAIN (it never trusts the relay and never reads the conductor's disk), so
    the Cards HTML, the brief and the run notes must be in the checkpoint's paths, the desk session must be a
    declared parameter, and PUBLISH must carry the instruction to send DONE (and STUCK) after the final push."""
    sys.path.insert(0, TOOLS)
    import importlib, preflight_run
    importlib.reload(preflight_run)
    M = preflight_run.load_yaml("RUN.yaml")
    ds = str((M.get("parameters") or {}).get("desk_session") or "")
    check("RUN.yaml declares the desk session", ds.startswith("session_"), ds)
    tool = (M.get("checkpoint") or {}).get("tool") or ""
    for name in ("pma_cards_<date>.html", "pma_brief_<date>.md", "run_notes.md"):
        check(f"the checkpoint ships {name} so the desk can render from main", name in tool, tool[-160:])
    pub = [s for s in M["steps"] if s["name"] == "PUBLISH"][0]
    msg = str(pub.get("desk_done_message") or "")
    check("PUBLISH tells the conductor to message the desk after the final checkpoint",
          "send_message" in msg and "PMA DONE" in msg and "AFTER the FINAL checkpoint" in msg, msg[:120])
    check("a STUCK run tells the desk too", "PMA STUCK" in msg)
    check("the desk re-reads main instead of trusting the relay", "does NOT trust the message" in msg)


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
    # R31 (2026-11-01): the macro packets are RETIRED by default -- a plain build makes none and needs no artifact.
    rc0, log0 = run([PIPE, "packets", "--candidates", cs, "--export", ex, "--menus", menus,
                     "--date", "2026-09-25", "--outdir", out + "_default"])
    check("by default no macro packet is built and the Crown artifact is not required (R31)",
          rc0 == 0 and not os.path.exists(os.path.join(out + "_default", "crown.json")), log0[-300:])
    # The artifact logic stays testable behind --macro-seats, for a re-seat.
    rc, log = run([PIPE, "packets", "--candidates", cs, "--export", ex, "--menus", menus,
                   "--date", "2026-09-25", "--outdir", out, "--macro-seats", "crown", "druckenmiller"])
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
                   "--date", "2026-09-25", "--outdir", out, "--crown-macro", art, "--macro-seats", "crown", "druckenmiller"])
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
    words["cards"]["AAA"] = {"case": "c", "why": "w", "reason": {"agree": "A leader in a strong group breaking out on heavy buying.", "wrong_if": "It closes back under the breakout.", "wait_for": "An hourly close above the buy line."}, "readiness": "Ready now", "readiness_tone": "ok"}
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


def _r1_ballot(voice, date, names):
    return {"voice": voice, "date": date, "round": 1,
            "nominations": [{"ticker": t, "conviction": 3, "reason": "coil at a high on rising volume",
                             "checklist_trace": [{"step": 1, "canon_ref": ["C1"], "observed": "x", "verdict": "pass"}],
                             "falsifier": "loses ma_50"} for t in names],
            "held_review": [], "declarations": [], "shortfall_reason": None}


def _case(**over):
    c = {"for": "break above the base high on volume", "against": "extended 2 ATR from the 20-day",
         "entry_trigger": "h1 close above 61.20", "wrong_if": "close back under 58.90",
         "horizon_sessions": 10, "would_change_my_mind": "a failed test of 61.20 on heavy volume",
         "cannot_see": []}
    c.update(over)
    return c


def _r2_ballot(voice, date, tickers, case=True, **vote_over):
    votes = []
    for t in tickers:
        v = {"ticker": t, "vote": "SUPPORT", "conviction": 3, "reason": "structure and momentum aligned",
             "conditions": {"lane": "BREAKOUT", "buy": ["h1_close_above:pivot_high", "vol_x_ge:1.4"],
                            "confirm": ["above_vwap_s"], "wrong": ["close_below:pivot_high"], "tf": "1H"}}
        v.update(vote_over)
        if case:
            v["case"] = _case()
        votes.append(v)
    return {"voice": voice, "date": date, "round": 2, "votes": votes}


def test_shortlist_cap_is_six(td):
    """R33 (PM 2026-10-30). A decider shortlists at most six on a ballot dated from 2026-11-01; a seventh
    is REJECTED on arrival. History validates as filed (the 2026-09-25 14-name ballot above still passes).
    A ballot from a non-decider is rejected under the new regime (R31)."""
    names = ["S%02d" % i for i in range(8)]
    cs = os.path.join(td, "r33_cs.json"); open(cs, "w").write(json.dumps({"universe": [{"ticker": t} for t in names]}))
    def val(ballot, tag):
        f = os.path.join(td, f"r33_{tag}.json"); open(f, "w").write(json.dumps(ballot))
        return run([REG, "validate", "--file", f, "--round", "1", "--candidates", cs])
    rc, log = val(_r1_ballot("oneil", "2026-11-01", names[:7]), "seven")
    check("7 nominations from a decider on 2026-11-01 are REJECTED", rc != 0 and "R33" in log, log[-300:])
    rc, log = val(_r1_ballot("oneil", "2026-11-01", names[:6]), "six")
    check("6 nominations are accepted", rc == 0, log[-300:])
    rc, log = val(_r1_ballot("oneil", "2026-11-01", names[:2]), "two")
    check("fewer is valid, never padded", rc == 0, log[-300:])
    rc, log = val(_r1_ballot("weis", "2026-11-01", names[:3]), "bench")
    check("a benched seat's ballot is rejected (R31)", rc != 0 and "not a decider" in log, log[-300:])
    rc, log = val(_r1_ballot("weis", "2026-10-29", names[:7]), "history")
    check("a 2026-10-29 ballot validates as it was filed (no cap, any seat)", rc == 0, log[-300:])


def test_case_form_is_required_both_ways(td):
    """R36. From 2026-11-01 every vote carries the case form: for, against, entry trigger, wrong-if,
    horizon in sessions, what would change my mind, what I cannot see. The 2026-09-06 fixtures still
    validate without it."""
    names = ["GNW", "BBY"]
    cs = os.path.join(td, "r36_cs.json"); open(cs, "w").write(json.dumps({"universe": [{"ticker": t} for t in names]}))
    p4 = os.path.join(td, "r36_p4.json"); json.dump({"deliberation_set": names, "ranked": [{"ticker": t, "lane": "MOMENTUM", "doors": ["STRENGTH"]} for t in names], "dropped": []}, open(p4, "w"))
    def val(ballot, tag):
        f = os.path.join(td, f"r36_{tag}.json"); open(f, "w").write(json.dumps(ballot))
        return run([REG, "validate", "--file", f, "--round", "2", "--candidates", cs, "--phase4", p4])
    rc, log = val(_r2_ballot("minervini", "2026-11-01", names, case=False), "nocase")
    check("a vote without the case form is REJECTED", rc != 0 and "case" in log, log[-300:])
    rc, log = val(_r2_ballot("minervini", "2026-11-01", names), "case")
    check("a vote with the case form is accepted", rc == 0, log[-400:])
    b = _r2_ballot("minervini", "2026-11-01", names); b["votes"][0]["case"]["against"] = ""
    rc, log = val(b, "blank")
    check("a blank case AGAINST is rejected -- reasons both ways, never blank", rc != 0 and "against" in log, log[-300:])
    b = _r2_ballot("minervini", "2026-11-01", names); b["votes"][0]["case"]["horizon_sessions"] = "two weeks"
    rc, log = val(b, "horizon")
    check("horizon must be an integer number of sessions (R35)", rc != 0 and "horizon_sessions" in log, log[-300:])
    rc, log = val(_r2_ballot("thorp", "2026-11-01", names), "bench")
    check("a benched seat's vote is rejected (R31)", rc != 0 and "not a decider" in log, log[-300:])
    one = json.load(open(fx("round2_votes.json")))[0]          # a real 2026-09-06 ballot, no case form
    f = os.path.join(td, "r36_hist.json"); open(f, "w").write(json.dumps(one))
    rc, log = run([REG, "validate", "--file", f, "--round", "2"])
    check("a 2026-09-06 ballot is never asked for the case form", "R36 case form" not in log and ".case" not in log, log[-300:])


def test_deliberation_forms_are_validated_on_arrival(td):
    """R34/R36. The challenge document, a floor message, the slate, a ratification and the QA note each
    have a contract and are REJECTED when incomplete -- membership and completeness only, never the
    reasoning. Cross-file counting is floor-check / ratify-count (tested separately)."""
    room = ["GNW", "BBY", "VRNS", "MFG"]
    cs = os.path.join(td, "df_cs.json"); open(cs, "w").write(json.dumps({"universe": [{"ticker": t} for t in room]}))
    p4 = os.path.join(td, "df_p4.json"); json.dump({"deliberation_set": room, "ranked": [{"ticker": t, "lane": "PULLBACK", "doors": ["SEATS"]} for t in room], "dropped": []}, open(p4, "w"))
    def val(form, tag, *extra):
        f = os.path.join(td, f"df_{tag}.json"); open(f, "w").write(json.dumps(form))
        return run([REG, "validate", "--file", f, *extra])
    # challenge
    ch = {"voice": "steenbarger", "date": "2026-11-01", "seat_kind": "challenge", "names_read": 4,
          "findings": [{"scope": "committee", "kind": "CROWDING", "claim": "three cases lean on rs_rank_pct alone",
                        "evidence": "rs_rank_pct cited by oneil, minervini, livermore on GNW", "addressed_to": "oneil"}],
          "obligations": [], "data_gaps": []}
    rc, log = val(ch, "ch_ok", "--kind", "challenge", "--candidates", cs)
    check("a complete challenge document is accepted", rc == 0, log[-300:])
    rc, log = val(dict(ch, voice="rogers"), "ch_rogers", "--kind", "challenge", "--candidates", cs)
    check("from 2026-11-01 only steenbarger files the challenge (R31)", rc != 0 and "steenbarger" in log, log[-300:])
    rc, log = val(dict(ch, names_read=0), "ch_zero", "--kind", "challenge", "--candidates", cs)
    check("findings with names_read 0 are rejected", rc != 0 and "names_read" in log, log[-300:])
    # floor message
    board = os.path.join(td, "df_board.json"); json.dump({"contested": ["BBY"]}, open(board, "w"))
    fm = {"voice": "oneil", "date": "2026-11-01", "ticker": "BBY", "msg_id": "oneil-BBY-1", "to": "wyckoff",
          "in_reply_to": None, "text": "Where is the test? The break held three closes above 61.20 on rising volume.",
          "stance_now": "SUPPORT", "changed_mind": False}
    rc, log = val(fm, "fm_ok", "--kind", "floor", "--phase4", p4, "--board", board)
    check("a floor message on a contested name is accepted", rc == 0, log[-300:])
    rc, log = val(dict(fm, ticker="GNW", msg_id="oneil-GNW-1"), "fm_uncontested", "--kind", "floor", "--phase4", p4, "--board", board)
    check("a message on an uncontested name is rejected", rc != 0 and "CONTESTED" in log, log[-300:])
    rc, log = val(dict(fm, changed_mind=True), "fm_moved", "--kind", "floor", "--phase4", p4, "--board", board)
    check("changed_mind without what_moved_me is rejected (R35)", rc != 0 and "what_moved_me" in log, log[-300:])
    rc, log = val(dict(fm, to="oneil"), "fm_self", "--kind", "floor", "--phase4", p4, "--board", board)
    check("a seat does not address itself", rc != 0, log[-300:])
    rc, log = val(dict(fm, voice="steenbarger", msg_id="sb-BBY-1", stance_now="NO_VOTE"), "fm_qa", "--kind", "floor", "--phase4", p4, "--board", board)
    check("steenbarger may answer when called on, with NO_VOTE", rc == 0, log[-300:])
    # slate
    def ticket(t, v="ADVANCE"):
        return {"ticker": t, "verdict": v, "entry_trigger": "h1 close above 61.20", "wrong_if": "close under 58.90",
                "horizon_sessions": 10, "why_agreed": "oneil, minervini: base break on volume", "dissent": []}
    sl = {"date": "2026-11-01", "chair": "chair", "tickets": [ticket("GNW"), ticket("BBY", "WATCH")]}
    rc, log = val(sl, "sl_ok", "--kind", "slate", "--phase4", p4)
    check("a two-ticket slate is accepted", rc == 0, log[-300:])
    big = dict(sl, tickets=[dict(ticket("GNW"), ticker=f"T{i:02d}") for i in range(26)])
    p4big = os.path.join(td, "df_p4big.json"); json.dump({"deliberation_set": [f"T{i:02d}" for i in range(30)], "ranked": [], "dropped": []}, open(p4big, "w"))
    rc, log = val(big, "sl_16", "--kind", "slate", "--phase4", p4big)
    check("a 26-ticket slate is REJECTED (R34 cap 25, PM 2026-11-04)", rc != 0 and "25" in log, log[-300:])
    rc, log = val(dict(big, tickets=big["tickets"][:15]), "sl_15", "--kind", "slate", "--phase4", p4big)
    check("a 15-ticket slate is accepted", rc == 0, log[-300:])
    rc, log = val(dict(sl, tickets=[ticket("ZZZZ")]), "sl_out", "--kind", "slate", "--phase4", p4)
    check("a slate ticket outside the room is rejected", rc != 0 and "deliberation set" in log, log[-300:])
    rc, log = val(dict(sl, chair="oneil"), "sl_voice", "--kind", "slate", "--phase4", p4)
    check("the Chair is not a voice", rc != 0, log[-300:])
    slate_path = os.path.join(td, "df_sl_ok.json")
    # ratification
    rt = {"voice": "raschke", "date": "2026-11-01", "tickets": [
        {"ticker": "GNW", "answer": "AGREE"},
        {"ticker": "BBY", "answer": "OBJECT", "objection": "no test of the break yet", "would_clear": "a hold above 61.20 on a down day"}]}
    rc, log = val(rt, "rt_ok", "--kind", "ratify", "--slate", slate_path)
    check("a complete ratification is accepted", rc == 0, log[-300:])
    rc, log = val(dict(rt, tickets=rt["tickets"][:1]), "rt_missing", "--kind", "ratify", "--slate", slate_path)
    check("a ratification missing a slate ticket is rejected", rc != 0 and "no answer" in log, log[-300:])
    bad = dict(rt); bad["tickets"] = [rt["tickets"][0], {"ticker": "BBY", "answer": "OBJECT", "objection": "too extended"}]
    rc, log = val(bad, "rt_noclear", "--kind", "ratify", "--slate", slate_path)
    check("OBJECT without would_clear is rejected", rc != 0 and "would_clear" in log, log[-300:])
    rc, log = val(dict(rt, voice="lynch"), "rt_lynch", "--kind", "ratify", "--slate", slate_path)
    check("a stood-down voice cannot ratify", rc != 0 and "not a decider" in log, log[-300:])
    # qa note
    qa = {"voice": "steenbarger", "date": "2026-11-01",
          "evidence_read": [{"voice": v, "read": True} for v in ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]],
          "shared_anchors": ["rs_rank_pct"], "unanswered_points": [], "slate_says_what_deciders_said": True,
          "note": "Every decider cited served fields. Three cases lean on rs_rank_pct.", "holds": [{"ticker": "BBY", "question": "Has the break been tested?"}]}
    rc, log = val(qa, "qa_ok", "--kind", "qa", "--slate", slate_path)
    check("a complete QA note with one hold is accepted", rc == 0, log[-300:])
    rc, log = val(dict(qa, holds=qa["holds"] * 2), "qa_twice", "--kind", "qa", "--slate", slate_path)
    check("the same ticket held twice is rejected (one hold per ticket)", rc != 0 and "twice" in log, log[-300:])
    rc, log = val(dict(qa, evidence_read=qa["evidence_read"][:6]), "qa_cover", "--kind", "qa", "--slate", slate_path)
    check("evidence_read must cover every decider", rc != 0 and "every decider" in log, log[-300:])
    rc, log = val(dict(qa, holds=[{"ticker": "VRNS", "question": "?"}]), "qa_offslate", "--kind", "qa", "--slate", slate_path)
    check("a hold on a name not on the slate is rejected", rc != 0 and "not on the slate" in log, log[-300:])
    rc, log = val(qa, "qa_both", "--kind", "qa", "--round", "2", "--slate", slate_path)
    check("exactly one of --round / --kind", rc != 0, log[-300:])


ROOM = ["GNW", "BBY", "VRNS", "MFG", "LNG"]          # real tickers from the 2026-09-06 fixtures
DEC = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]


def _committee_fixture(td, tag):
    """Seven blind ballots on five room names, Steenbarger's challenge naming LNG, and phase4.
       GNW: 7 support (unanimous)      -> not contested
       BBY: 4 support / 3 oppose       -> contested (split)
       VRNS: 7 oppose                  -> not contested
       MFG: 5 support / 2 abstain      -> not contested (no OPPOSE)
       LNG: 7 support, but challenged  -> contested (challenge)"""
    d = os.path.join(td, tag); os.makedirs(os.path.join(d, "forms", "r2"), exist_ok=True)
    os.makedirs(os.path.join(d, "forms", "challenge"), exist_ok=True)
    p4 = os.path.join(d, "phase4.json")
    json.dump({"deliberation_set": ROOM, "ranked": [{"ticker": t, "lane": ("MOMENTUM" if t in ("GNW", "LNG") else "PULLBACK"), "doors": ["SEATS"]} for t in ROOM], "dropped": []}, open(p4, "w"))
    for i, v in enumerate(DEC):
        b = _r2_ballot(v, "2026-11-01", ROOM)
        for row in b["votes"]:
            t = row["ticker"]
            if t == "VRNS" or (t == "BBY" and i >= 4):
                row.update({"vote": "OPPOSE", "opposing_case": "the base is tight and volume is rising", "conditions": None})
            if t == "MFG" and i >= 5:
                row.update({"vote": "ABSTAIN", "conviction": None, "conditions": None})
            row["case"]["horizon_sessions"] = 5 + 3 * i      # each voice its own horizon (R35)
        json.dump(b, open(os.path.join(d, "forms", "r2", f"{v}.json"), "w"))
    # a benched seat's stray ballot: must be IGNORED loudly, never counted
    json.dump(_r2_ballot("thorp", "2026-11-01", ROOM), open(os.path.join(d, "forms", "r2", "thorp.json"), "w"))
    ch = {"voice": "steenbarger", "date": "2026-11-01", "seat_kind": "challenge", "names_read": 5, "obligations": [], "data_gaps": [],
          "findings": [{"scope": "LNG", "ticker": "LNG", "kind": "CROWDING", "claim": "all seven lean on rs_rank_pct", "evidence": "rs_rank_pct cited 7 times"}]}
    json.dump(ch, open(os.path.join(d, "forms", "challenge", "steenbarger.json"), "w"))
    return d, p4


def _ticket(t, v="ADVANCE"):
    return {"ticker": t, "verdict": v, "entry_trigger": "h1 close above the base high", "wrong_if": "close back inside the base",
            "horizon_sessions": 10, "why_agreed": "oneil, minervini, livermore: base break on volume", "dissent": []}


def _ratify(d, sub, voice, answers):
    os.makedirs(os.path.join(d, "forms", sub), exist_ok=True)
    rows = []
    for t, ans in answers.items():
        r = {"ticker": t, "answer": ans}
        if ans == "OBJECT": r.update({"objection": "no test of the break yet", "would_clear": "a hold above the pivot on a down day"})
        if ans == "AGREE_WITH_RESERVATION": r["reservation"] = "size it small until the test"
        rows.append(r)
    json.dump({"voice": voice, "date": "2026-11-01", "tickets": rows}, open(os.path.join(d, "forms", sub, f"{voice}.json"), "w"))


def test_board_marks_contested_names_and_never_a_verdict(td):
    """R36 round 3. The board is what the seats said, laid out: blind split, every case, CONTESTED where
    SUPPORT and OPPOSE both appear or Steenbarger named the name. It computes no verdict."""
    d, p4 = _committee_fixture(td, "board")
    out = os.path.join(d, "board.json")
    rc, log = run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4,
                   "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", out])
    check("board exits clean", rc == 0, log[-400:])
    if rc != 0: return
    B = json.load(open(out))
    check("contested = the split name and the challenged name, in room order", B["contested"] == ["BBY", "LNG"], str(B["contested"]))
    check("a unanimous-oppose name is not contested (nothing to argue)", "VRNS" in B["uncontested_oppose"])
    check("support + abstain is not contested", "MFG" not in B["contested"])
    check("the benched seat's ballot is ignored LOUDLY", B["ignored_ballots"] == ["thorp"] and "IGNORED" in log, log[-300:])
    check("all seven deciders present", B["deciders_present"] == sorted(DEC) and B["deciders_absent"] == [])
    bby = next(n for n in B["names"] if n["ticker"] == "BBY")
    check("the blind split is recorded per name", (len(bby["split"]["support"]), len(bby["split"]["oppose"])) == (4, 3))
    check("every decider's case (for/against/trigger/wrong-if/horizon) is on the board",
          all(set(("for", "against", "entry_trigger", "wrong_if", "horizon_sessions")) <= set(bby["cases"][v]) for v in DEC))
    check("the board carries NO verdict", "verdict" not in json.dumps(B))


def test_floor_caps_are_counted_by_code(td):
    """R36. Two messages per seat per name, on open names only, replies to real messages -- counted across
    files by floor-check, which exits 1 and names every breach."""
    d, p4 = _committee_fixture(td, "floor")
    board = os.path.join(d, "board.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", board])
    fl = os.path.join(d, "forms", "floor"); os.makedirs(fl, exist_ok=True)
    def msg(voice, t, n, to="room", reply=None, changed=False):
        m = {"voice": voice, "date": "2026-11-01", "ticker": t, "msg_id": f"{voice}-{t}-{n}", "to": to, "in_reply_to": reply,
             "text": "Where is the test? Three closes above the pivot on rising volume.", "stance_now": "SUPPORT", "changed_mind": changed}
        if changed: m["what_moved_me"] = "the hold above the pivot on a down day"
        json.dump(m, open(os.path.join(fl, m["msg_id"] + ".json"), "w")); return m["msg_id"]
    a1 = msg("oneil", "BBY", 1, to="wyckoff"); msg("wyckoff", "BBY", 1, to="oneil", reply=a1, changed=True); msg("oneil", "BBY", 2, to="wyckoff")
    out = os.path.join(d, "floor_check.json")
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", out])
    check("two messages each on a contested name pass", rc == 0, log[-400:])
    F = json.load(open(out)) if os.path.exists(out) else {}
    check("the record shows who changed their mind and what moved them",
          F.get("per_name", {}).get("BBY", {}).get("changed_mind", [{}])[0].get("voice") == "wyckoff", str(F.get("per_name")))
    msg("oneil", "BBY", 3, to="room")
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", out])
    check("a THIRD message by the same seat on the same name is a breach (exit 1, named)", rc != 0 and "oneil sent 3" in log, log[-300:])
    os.remove(os.path.join(fl, "oneil-BBY-3.json"))
    msg("seow", "GNW", 1)
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", out])
    check("a message on an uncontested name is a breach", rc != 0 and "not open on the floor" in log, log[-300:])
    os.remove(os.path.join(fl, "seow-GNW-1.json"))
    msg("raschke", "LNG", 1, reply="ghost-LNG-9")
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", out])
    check("a reply to a message that does not exist is a breach", rc != 0 and "ghost-LNG-9" in log, log[-300:])
    os.remove(os.path.join(fl, "raschke-LNG-1.json"))
    # hold round: only the held ticket is open
    qa = os.path.join(d, "qa.json"); json.dump({"voice": "steenbarger", "holds": [{"ticker": "GNW", "question": "tested?"}]}, open(qa, "w"))
    fl2 = os.path.join(d, "forms", "floor2"); os.makedirs(fl2, exist_ok=True)
    json.dump({"voice": "seow", "date": "2026-11-01", "ticker": "GNW", "msg_id": "seow-GNW-h1", "to": "room", "in_reply_to": None,
               "text": "Answering Steenbarger: the test came on day 3.", "stance_now": "SUPPORT", "changed_mind": False}, open(os.path.join(fl2, "a.json"), "w"))
    rc, log = run([PIPE, "floor-check", "--messages", fl2, "--board", board, "--qa", qa, "--out", os.path.join(d, "fc2.json")])
    check("after a hold the floor is open on the HELD ticket only, contested or not", rc == 0, log[-300:])
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--qa", qa, "--out", os.path.join(d, "fc3.json")])
    check("the first round's BBY messages are not valid on the hold round", rc != 0, log[-300:])


def test_objection_rule_counts_the_final_ratification(td):
    """R34 (PM 2026-10-30). 0 objections AGREED; 1-3 CONTESTED; 4+ of 7 DROPPED. Machine verdicts keep
    every downstream reader working: ADVANCE / HOLD-FOR-CONDITIONS / PASS, split, conviction, lane.
    A non-decider's ratification is ignored loudly. A hold's re-ratification replaces the first for the
    held ticket only. record-verdicts consumes the result unchanged."""
    d, p4 = _committee_fixture(td, "ratify")
    board = os.path.join(d, "board.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", board])
    slate = os.path.join(d, "slate.json")
    json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY", "WATCH"), _ticket("LNG"), _ticket("MFG")]}, open(slate, "w"))
    # GNW 0 objections; BBY 2; LNG 4; MFG 3 (with reservations on GNW from two seats)
    for i, v in enumerate(DEC):
        _ratify(d, "ratify", v, {"GNW": "AGREE_WITH_RESERVATION" if i < 2 else "AGREE",
                                 "BBY": "OBJECT" if i < 2 else "AGREE",
                                 "LNG": "OBJECT" if i < 4 else "AGREE",
                                 "MFG": "OBJECT" if i < 3 else "AGREE"})
    _ratify(d, "ratify", "lynch", {"GNW": "OBJECT", "BBY": "OBJECT", "LNG": "OBJECT", "MFG": "OBJECT"})   # stood down: ignored
    out = os.path.join(d, "consensus.json"); rec = os.path.join(d, "committee_record.json")
    args = [PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratify"), "--board", board,
            "--phase4", p4, "--date", "2026-11-01", "--out", out, "--record", rec]
    rc, log = run(args)
    check("ratify-count exits clean", rc == 0, log[-400:])
    if rc != 0: return
    C = {c["ticker"]: c for c in json.load(open(out))}
    check("0 objections = AGREED -> ADVANCE", (C["GNW"]["status"], C["GNW"]["verdict"]) == ("AGREED", "ADVANCE"), str(C["GNW"]))
    check("AGREED with reservations orders at 4, not 5", C["GNW"]["conviction"] == 4 and len(C["GNW"]["reservations"]) == 2)
    check("2 objections = CONTESTED; slate WATCH -> HOLD-FOR-CONDITIONS", (C["BBY"]["status"], C["BBY"]["verdict"]) == ("CONTESTED", "HOLD-FOR-CONDITIONS"), str(C["BBY"]))
    check("3 objections = CONTESTED (stays listed)", C["MFG"]["status"] == "CONTESTED" and C["MFG"]["verdict"] == "ADVANCE")
    check("4 of 7 = DROPPED -> PASS, still recorded", (C["LNG"]["status"], C["LNG"]["verdict"]) == ("DROPPED", "PASS"), str(C["LNG"]))
    check("the objections and what would clear them are on the row",
          C["BBY"]["objections"][0]["would_clear"] and sorted(o["voice"] for o in C["BBY"]["objections"]) == ["minervini", "oneil"])
    check("a never-slated room name is PASS / NOT_SLATED with its blind split", C["VRNS"]["status"] == "NOT_SLATED" and len(C["VRNS"]["split"]["oppose"]) == 7)
    check("the stood-down voice's ratification was ignored LOUDLY", "lynch" in log and "IGNORED" in log and all("lynch" not in c["split"]["oppose"] for c in C.values()))
    check("every ADVANCE row has support > oppose (the publish gate's Q2r holds by construction)",
          all(len(c["split"]["support"]) > len(c["split"]["oppose"]) for c in C.values() if c["verdict"] == "ADVANCE"))
    check("the lane rides along as a label", C["GNW"]["lane"] == "MOMENTUM" and C["BBY"]["lane"] == "PULLBACK")
    check("n deciders and the drop threshold are stated on every row", all(c["n_deciders"] == 7 and c["drop_threshold"] == 4 for c in C.values()))
    # downstream smoke: the ledger writer reads this consensus.json as-is
    led = os.path.join(d, "verdict_ledger.json")
    rc, log = run([PIPE, "record-verdicts", "--consensus", out, "--candidates", fx("candidate_set.json"), "--phase4", p4, "--ledger", led, "--date", "2026-11-01"])
    check("record-verdicts consumes the new consensus.json unchanged", rc == 0 and os.path.exists(led), log[-300:])
    if rc == 0:
        rows = {r["ticker"]: r for r in json.load(open(led))["rows"] if r["date"] == "2026-11-01"}
        check("the ledger locks ADVANCE / HOLD / PASS for every room name", {rows[t]["verdict"] for t in ROOM} == {"ADVANCE", "HOLD-FOR-CONDITIONS", "PASS"})
        check("a slated ticket is graded at the horizon the room stated (R35); a never-slated name keeps the run default",
              rows["GNW"]["fixed_horizon"]["horizon_sessions"] == 10 and rows["GNW"]["fixed_horizon"]["horizon_source"] == "slate"
              and rows["VRNS"]["fixed_horizon"]["horizon_sessions"] == 5 and rows["VRNS"]["fixed_horizon"]["horizon_source"] == "run_default",
              str({t: rows[t]["fixed_horizon"] for t in ("GNW", "VRNS")}))
    # hold round: Steenbarger holds LNG; after discussion only 2 object -> CONTESTED, back on the list
    qa = os.path.join(d, "forms", "qa", "steenbarger.json"); os.makedirs(os.path.dirname(qa), exist_ok=True)
    json.dump({"voice": "steenbarger", "date": "2026-11-01", "evidence_read": [{"voice": v, "read": True} for v in DEC], "shared_anchors": [],
               "unanswered_points": [], "slate_says_what_deciders_said": True, "note": "ok", "holds": [{"ticker": "LNG", "question": "crowded?"}]}, open(qa, "w"))
    for i, v in enumerate(DEC):
        _ratify(d, "ratify2", v, {"LNG": "OBJECT" if i < 2 else "AGREE"})
    rc, log = run(args + ["--ratifications2", os.path.join(d, "forms", "ratify2"), "--qa", qa])
    C2 = {c["ticker"]: c for c in json.load(open(out))}
    check("after the hold, LNG's re-ratification replaces the first: 2 objections -> CONTESTED", rc == 0 and C2["LNG"]["status"] == "CONTESTED" and C2["LNG"]["held"], log[-300:])
    check("the other tickets are unchanged by the hold round", C2["GNW"]["status"] == "AGREED" and C2["MFG"]["status"] == "CONTESTED")
    _ratify(d, "ratify2", "oneil", {"LNG": "AGREE", "GNW": "OBJECT"})
    rc, log = run(args + ["--ratifications2", os.path.join(d, "forms", "ratify2"), "--qa", qa])
    check("re-ratifying a ticket that was NOT held is refused", rc != 0 and "NOT held" in log, log[-300:])
    # a slate over the cap (25) is refused even if the registrar were bypassed
    big = os.path.join(d, "slate16.json"); json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket(t) for t in ROOM] * 9}, open(big, "w"))
    rc, log = run([PIPE, "ratify-count", "--slate", big, "--ratifications", os.path.join(d, "forms", "ratify"), "--phase4", p4, "--date", "2026-11-01", "--out", os.path.join(d, "x.json"), "--record", os.path.join(d, "y.json")])
    check("a slate over 25 is refused by the counter too (R34, defence in depth)", rc != 0 and "25" in log, log[-300:])
    # fewer than 4 deciders ratifying is no committee
    few = os.path.join(d, "forms", "few"); os.makedirs(few, exist_ok=True)
    for v in DEC[:3]:
        json.dump(json.load(open(os.path.join(d, "forms", "ratify", f"{v}.json"))), open(os.path.join(few, f"{v}.json"), "w"))
    rc, log = run([PIPE, "ratify-count", "--slate", slate, "--ratifications", few, "--phase4", p4, "--date", "2026-11-01", "--out", os.path.join(d, "x.json"), "--record", os.path.join(d, "y.json")])
    check("3 ratifications is no committee -- halt", rc != 0 and "no committee" in log, log[-300:])


def test_the_record_is_written_per_voice_per_ticket(td):
    """R35. committee_record.json: for every decider and every room name -- blind vote, horizon, floor
    messages, change of mind and what moved it, ratification and objection, final status."""
    d, p4 = _committee_fixture(td, "record")
    board = os.path.join(d, "board.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", board])
    slate = os.path.join(d, "slate.json"); json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY", "WATCH")]}, open(slate, "w"))
    fl = os.path.join(d, "forms", "floor"); os.makedirs(fl, exist_ok=True)
    json.dump({"voice": "wyckoff", "date": "2026-11-01", "ticker": "BBY", "msg_id": "wyckoff-BBY-1", "to": "oneil", "in_reply_to": None,
               "text": "Conceding: the test held.", "stance_now": "SUPPORT", "changed_mind": True, "what_moved_me": "the hold above the pivot"}, open(os.path.join(fl, "w1.json"), "w"))
    for i, v in enumerate(DEC):
        _ratify(d, "ratify", v, {"GNW": "AGREE", "BBY": "OBJECT" if i == 0 else "AGREE"})
    out = os.path.join(d, "consensus.json"); rec = os.path.join(d, "committee_record.json")
    rc, log = run([PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratify"), "--board", board, "--messages", fl,
                   "--phase4", p4, "--date", "2026-11-01", "--out", out, "--record", rec])
    check("ratify-count writes the record", rc == 0 and os.path.exists(rec), log[-300:])
    if not os.path.exists(rec): return
    R = json.load(open(rec)); rows = {(r["voice"], r["ticker"]): r for r in R["rows"]}
    check("one row per decider per room name (7 x 5)", len(R["rows"]) == 35 and set(r["voice"] for r in R["rows"]) == set(DEC))
    w = rows[("wyckoff", "BBY")]
    check("the blind vote and the seat's OWN horizon are recorded", w["blind_vote"] == "OPPOSE" and w["horizon_sessions"] == 5 + 3 * DEC.index("wyckoff"))
    check("the floor message, the change of mind and what moved it are recorded",
          w["floor_messages"] == ["wyckoff-BBY-1"] and w["changed_mind"] and w["what_moved_me"] == ["the hold above the pivot"] and w["stance_after_floor"] == "SUPPORT")
    check("the ratification and the final status sit on the same row", w["ratification"] == "AGREE" and w["final_status"] == "CONTESTED")
    o = rows[("oneil", "BBY")]
    check("an objector's objection and what would clear it are recorded", o["ratification"] == "OBJECT" and o["would_clear"])
    check("horizons differ per voice -- no single 5-session clock", len({r["horizon_sessions"] for r in R["rows"] if r["ticker"] == "GNW"}) == 7)


def test_r2digest_reads_the_crown_file_and_marks_retired_seats(td):
    """R31. The weather comes from AQE's Crown file (what_would_change_it lives under read_me_first);
    Rogers, Lynch and Detect-lens render as retired seats, never as a silent 'NOT FILED' gap."""
    crown = os.path.join(td, "crown.json")
    json.dump({"generated_at": "2026-10-30T08:54:02+08:00", "status": "OK",
               "the_call": {"expression_family": "HIDDEN_STRESS_DOWNSIDE", "match_quality": "exact", "size_multiplier": 0.5},
               "scenario": {"leading": "REFLATION", "runner_up": "GROWTH_SCARE", "contested": False},
               "read_me_first": {"headline": "Breadth is narrowing under a rising tape.", "what_would_change_it": ["RSP/SPY reclaims its 20-day average"]}}, open(crown, "w"))
    out = os.path.join(td, "vp_crown.txt")
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--crown", crown, "--run-id", "t", "--out", out])
    check("r2digest runs with only Steenbarger's document and the Crown file", rc == 0, log[-300:])
    if rc != 0: return
    txt = open(out).read()
    check("the Crown call, scenario and headline are in the packet", "HIDDEN_STRESS_DOWNSIDE" in txt and "REFLATION" in txt and "Breadth is narrowing" in txt)
    check("what would change it is read from read_me_first", "RSP/SPY reclaims" in txt)
    check("retired seats are marked retired, not 'NOT FILED'", "ROGERS: retired seat" in txt and "LYNCH: retired seat" in txt and "DETECT-LENS: retired seat" in txt and "NOT FILED" not in txt)
    check("the lane header says all seven count (R32)", "ALL seven deciders vote on ALL names" in txt)


def test_run_map_carries_the_seven_deciders_and_the_new_rounds(td):
    """R31/R34/R36/R38 in RUN.yaml: rosters, the two-tier funnel (CLAIMS/CROSS/FUNNEL/PAIR/TIER2/TIMING) in place of the
    retired FLOOR, SLATE/RATIFY/QA, DECIDE on ratify-count, no MACRO."""
    import yaml
    M = yaml.safe_load(open(os.path.join(HERE, "..", "RUN.yaml")))
    S = {s["name"]: s for s in M["steps"]}
    check("no MACRO step", "MACRO" not in S)
    check("NOMINATE, VOTE and RATIFY seat exactly the seven deciders",
          all(sorted(S[n]["seats"]) == sorted(DEC) for n in ("NOMINATE", "VOTE", "RATIFY")), str({n: S[n]["seats"] for n in ("NOMINATE", "VOTE", "RATIFY")}))
    check("CHALLENGE and QA seat steenbarger alone", S["CHALLENGE"]["seats"] == ["steenbarger"] and S["QA"]["seats"] == ["steenbarger"])
    order = ["NOMINATE", "RANK", "MTF", "CHALLENGE", "VOTE", "CLAIMS", "CROSS", "FUNNEL", "PAIR", "TIER2", "TIMING", "SLATE", "RATIFY", "QA", "DECIDE"]
    check("the rounds run in order (R38: the two-tier funnel sits between VOTE and SLATE)", [n for n in S if n in order] == order, str([n for n in S if n in order]))
    check("R38: the open FLOOR is retired from the run map", "FLOOR" not in S)
    check("DECIDE counts with ratify-count, not consensus", "ratify-count" in S["DECIDE"]["command"] and not any(
          str(s.get("command", "")).startswith("pma_pipeline.py consensus") for s in M["steps"]))
    check("CLAIMS builds the board then the claims board", "board" in S["CLAIMS"]["first"] and "pma_pipeline.py claims " in S["CLAIMS"]["command"])
    check("CROSS and TIER2 seat the seven deciders and validate on arrival", all(sorted(S[n]["seats"]) == sorted(DEC) for n in ("CROSS", "TIER2"))
          and "--kind cross --claims claims_board.json" in S["CROSS"]["validate_with"] and "--kind tier2 --pairs pairs.json --funnel funnel.json" in S["TIER2"]["validate_with"])
    check("FUNNEL / PAIR / TIMING are tool steps counted by code", (S["FUNNEL"]["kind"], S["PAIR"]["kind"], S["TIMING"]["kind"]) == ("tool", "tool", "tool")
          and "claims-score" in S["FUNNEL"]["command"] and "pma_pipeline.py pair " in S["PAIR"]["command"] and "decide-timing" in S["TIMING"]["command"])
    check("the slate validates against decision.json (R40)", "--decision decision.json" in S["SLATE"]["barrier"])
    check("DECIDE puts the cross and tier-2 forms on the record", "--cross forms/cross" in S["DECIDE"]["command"] and "--tier2 forms/tier2" in S["DECIDE"]["command"])
    check("the funnel parameters are stated", (M["parameters"]["claims_per_camp"], M["parameters"]["claim_reviewers"], M["parameters"]["slate_min_support"], M["parameters"]["tie_rule"]) == (2, 2, 4, "WATCH"))
    src = _pipeline_source()
    check("the code's funnel constants agree with RUN.yaml", "CLAIMS_PER_CAMP = 2" in src and "CLAIM_REVIEWERS = 2" in src
          and "SLATE_MIN_SUPPORT = 4" in src and 'TIMING_TIE = "WATCH"' in src)
    check("the vote packet reads the Crown file and only Steenbarger's challenge", "--crown" in S["VOTE"]["packet"] and "--rogers" not in S["VOTE"]["packet"] and "--lynch" not in S["VOTE"]["packet"])
    check("every model round is checkpointed", all(S[n].get("checkpoint_after") for n in ("NOMINATE", "CHALLENGE", "VOTE", "CROSS", "TIER2", "SLATE", "RATIFY", "QA")))
    check("parameters carry the caps", M["parameters"]["shortlist_cap"] == 6 and M["parameters"]["slate_cap"] == 25 and M["parameters"]["floor_messages_per_seat_per_name"] == 2)
    reg = open(REG).read()
    check("registrar and pipeline agree on the deciders", all(v in reg for v in DEC) and 'QA_SEAT = "steenbarger"' in reg)


def test_the_seat_cards_carry_the_floor_and_the_roster_is_archived_not_deleted(td):
    """R31/R36 on the cards. Each decider's agent AND skill card carries its 'ON THE FLOOR' block; Steenbarger
    carries the QA block; Seow's R10 picks his system from the name's own picture; the Chair, pma-deliberate
    and voice-deliberate exist; the stood-down and benched cards sit under archive/, not under agents/."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))            # aegis-core
    voices = os.path.join(os.path.dirname(root), "aegis-voices")
    if not os.path.isdir(voices):
        check("aegis-voices sits beside aegis-core (one code tree)", False, voices); return
    for v in DEC:
        for p in (os.path.join(voices, "agents", f"voice-{v}.md"), os.path.join(voices, "skills", f"voice-{v}", "SKILL.md")):
            t = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
            check(f"{os.path.relpath(p, voices)} carries ON THE FLOOR (R36)", "ON THE FLOOR (R36" in t and "I press others on" in t)
    for p in (os.path.join(voices, "agents", "voice-steenbarger.md"), os.path.join(voices, "skills", "voice-steenbarger", "SKILL.md")):
        t = open(p, encoding="utf-8").read()
        check(f"{os.path.relpath(p, voices)} carries the QA block", "QUALITY ASSURANCE (R31" in t and "I may HOLD a ticket" in t)
    for p in (os.path.join(voices, "agents", "voice-seow.md"), os.path.join(voices, "skills", "voice-seow", "SKILL.md")):
        t = open(p, encoding="utf-8").read()
        check(f"{os.path.relpath(p, voices)}: R10 picks the system from the name's own picture, not the lane",
              "I count toward momentum-lane verdicts" not in t and "NAME'S OWN PICTURE" in t)
    for v in ("weis", "thorp", "rogers", "lynch", "crown", "druckenmiller", "detect-lens"):
        check(f"{v} is archived, not an agent", not os.path.exists(os.path.join(voices, "agents", f"voice-{v}.md"))
              and os.path.exists(os.path.join(voices, "archive", "agents", f"voice-{v}.md")))
        check(f"{v}'s canon is untouched", os.path.exists(os.path.join(voices, "canon", v, "canon.lock.yaml")))
    check("voice-deliberate skill exists", os.path.exists(os.path.join(voices, "skills", "voice-deliberate", "SKILL.md")))
    check("the Chair agent exists and is not a voice", os.path.exists(os.path.join(root, "agents", "chair.md"))
          and "I am not a voice" in open(os.path.join(root, "agents", "chair.md")).read())
    check("pma-deliberate skill exists", os.path.exists(os.path.join(root, "skills", "pma-deliberate", "SKILL.md")))
    check("the aqe-engineer agent exists", os.path.exists(os.path.join(root, "agents", "aqe-engineer.md")))
    vp = open(os.path.join(TOOLS, "voice_preflight.py")).read()
    check("voice_preflight's roster is the seven deciders", "DECIDERS" in vp and '"thorp"' not in vp.split("DECIDERS")[-1][:400])


def test_checkpoints_land_under_aegis_output_and_never_rebuild_the_space(td):
    """BUILD_PLAN Phase 1 (PM 2026-10-30): the checkpoint path. deploy-hf.yml rebuilds the HF Space on any push
    to main outside aegis/output/**. git_sync.plan() puts run files under --dest and refuses anything outside."""
    sys.path.insert(0, TOOLS)
    import importlib, git_sync
    importlib.reload(git_sync)
    P = git_sync.plan(["run_manifest.json", "forms/", "board.json"], dest="aegis/output/pma/run/2026-11-03", cwd="/run")
    check("every working file is planned under aegis/output/pma/run/<date>/",
          [r for _, r in P["copies"]] == ["aegis/output/pma/run/2026-11-03/run_manifest.json",
                                         "aegis/output/pma/run/2026-11-03/forms", "aegis/output/pma/run/2026-11-03/board.json"], str(P["copies"]))
    check("only the dest directory is staged", P["stage"] == ["aegis/output/pma/run/2026-11-03"])
    check("nothing is outside the safe prefix", P["outside"] == [])
    legacy = git_sync.plan(["run_manifest.json", "forms/", "*.json"])
    check("the OLD bare-name checkpoint is flagged as outside aegis/output (it would have hit the repo root)",
          sorted(legacy["outside"]) == ["*.json", "forms", "run_manifest.json"], str(legacy))
    dflt = git_sync.plan(git_sync.DEFAULT_PATHS)
    check("the legacy DEFAULT_PATHS are flagged outside too (aegis/data, decisions_log)",
          "aegis/data" in dflt["outside"] and "aegis/output/aqe_daily_export.json" not in dflt["outside"])
    r = git_sync.sync("t", ["run_manifest.json"], dry_run=True)
    check("sync REFUSES an outside push by default, fail-visible", r["ok"] is False and "REFUSED" in r["reason"], str(r)[:200])
    run_yaml = open(os.path.join(HERE, "..", "RUN.yaml")).read()
    check("RUN.yaml's checkpoint tool passes --dest aegis/output/pma/run/<date>", "--dest aegis/output/pma/run/<date>" in run_yaml)
    root_copy = os.path.join(HERE, "..", "..", "..", "tools", "git_sync.py")
    check("the plugin-root copy of git_sync.py is identical (RUN.yaml: keep the two copies identical)",
          not os.path.exists(root_copy) or open(root_copy).read() == open(os.path.join(TOOLS, "git_sync.py")).read())


def test_one_risk_figure(td):
    """BUILD_PLAN Phase 1: one risk-per-trade figure. PM 2026-10-27: 1R = $620 fixed. It lives in
    config/aegis_fund.md and every sizing path reads it from there; parameters.yaml's percent is not used while set."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    sys.path.insert(0, os.path.join(root, "tools"))
    import importlib, fund_config
    importlib.reload(fund_config)
    check("one_r_usd is 620 in the fund config", fund_config.one_r_usd() == 620.0)
    pct = fund_config.one_r_pct_equivalent(66699)
    check("the percent equivalent reproduces $620 exactly on the current dynCap", pct is not None and abs(66699 * pct / 100.0 - 620.0) < 1e-6, str(pct))
    try:
        import bracket_calc
        importlib.reload(bracket_calc)
        prm = bracket_calc.load_params(dyncap=66699)
        check("bracket_calc sizes from the fixed $620, and says so", prm["one_r_usd"] == 620.0 and "aegis_fund.md" in prm["one_r_source"]
              and abs(66699 * prm["one_r_pct"] / 100.0 - 620.0) < 1e-6, str(prm))
    except ImportError as e:                      # numpy may be absent in a bare harness; the fund-config half still proves the figure
        check(f"bracket_calc importable (skipped: {e.__class__.__name__})", True)
    live = open(os.path.join(os.path.dirname(root), "aegis-live", "skills", "live-review", "SKILL.md")).read()
    check("the live review quotes the same $620", "$620" in live)


def test_the_checker_catches_a_seeded_failure(td):
    """Operating model E1 / BUILD_PLAN Phase 1 gate: 'Checker catches a seeded failure'. A healthy fixture reads
    Healthy; a stale AQE marker, a pending step, a 16-ticket slate and an over-ceiling spend are each named."""
    CHK = os.path.abspath(os.path.join(HERE, "..", "..", "daily-check", "check.py"))
    check("daily-check/check.py ships", os.path.exists(CHK), CHK)
    if not os.path.exists(CHK): return
    d = os.path.join(td, "chk"); os.makedirs(d, exist_ok=True)
    sys.path.insert(0, TOOLS)
    import importlib, preflight_run
    importlib.reload(preflight_run)
    steps = [x["name"] for x in preflight_run.load_yaml("RUN.yaml")["steps"]]       # the checker reads RUN.yaml's list
    check("the checker's fallback step list is RUN.yaml's", "KNOWN_STEPS = " in open(CHK).read()
          and all(f'"{x}"' in open(CHK).read().split("KNOWN_STEPS = ")[1].split("]")[0] for x in steps))
    check("the checker's spend ceiling is 2,500,000 (DECISIONS_2026-11-02)", "DEFAULT_CEILING = 2_500_000" in open(CHK).read())
    def write(name, obj): json.dump(obj, open(os.path.join(d, name), "w"))
    healthy_manifest = {"date": "2026-11-03", "steps": {s: {"status": "done", "cost": {"est_tokens": 20000}} for s in steps}}
    write("run_manifest.json", healthy_manifest)
    write("consensus.json", [{"ticker": "GNW", "verdict": "ADVANCE", "status": "AGREED"}, {"ticker": "BBY", "verdict": "PASS", "status": "DROPPED"}])
    write("committee_record.json", {"deciders_present": DEC, "rows": [{"voice": v, "ticker": t} for v in DEC for t in ("GNW", "BBY")]})
    write("slate.json", {"tickets": [{"ticker": "GNW", "verdict": "ADVANCE"}]})
    write("funnel.json", {"survivors": ["GNW"], "dropped": ["BBY"], "out": [], "names": {"GNW": {}, "BBY": {}}, "measurement": {"claims_issued": 4, "stances_changed_n": 1}})
    write("decision.json", {"names": {"GNW": {"proposal": "ADVANCE"}}})
    write("pma_levels.json", {"run_date": "2026-11-03"})
    write("aqe_last_run.json", {"date_sgt": "2026-11-03", "status": "success", "packets_status": "Voice packets published: 8/8"})
    base = [CHK, "all", "--last-run", os.path.join(d, "aqe_last_run.json"), "--today", "2026-11-03",
            "--run-dir", d, "--date", "2026-11-03", "--levels", os.path.join(d, "pma_levels.json")]
    rc, log = run(base)
    check("a healthy chain reads Healthy on both checks", rc == 0 and log.count("Healthy") == 2, log[-400:])
    # seeded failures, one at a time
    write("aqe_last_run.json", {"date_sgt": "2026-11-02", "status": "success"})
    rc, log = run(base); check("a stale AQE marker is NOT READY", rc != 0 and "stale" in log, log[-300:])
    write("aqe_last_run.json", {"date_sgt": "2026-11-03", "status": "partial"})
    rc, log = run(base); check("status partial is named (export current, tail step failed)", rc != 0 and "partial" in log, log[-300:])
    write("aqe_last_run.json", {"date_sgt": "2026-11-03", "status": "success"})
    m = json.loads(json.dumps(healthy_manifest)); m["steps"]["VOTE"]["status"] = "pending"; write("run_manifest.json", m)
    rc, log = run(base); check("a step still pending is named", rc != 0 and "step VOTE: pending" in log, log[-300:])
    m = json.loads(json.dumps(healthy_manifest)); m["steps"]["VOTE"]["cost"]["est_tokens"] = 2_600_000; write("run_manifest.json", m)
    rc, log = run(base); check("spend over the ceiling is named for the PM", rc != 0 and "SPEND OVER CEILING" in log, log[-300:])
    write("run_manifest.json", healthy_manifest)
    write("slate.json", {"tickets": [{"ticker": f"T{i}"} for i in range(26)]})
    rc, log = run(base); check("a 26-ticket slate is named (R34, cap 25)", rc != 0 and "26 tickets > 25" in log, log[-300:])
    write("slate.json", {"tickets": [{"ticker": "GNW", "verdict": "ADVANCE"}]})
    write("consensus.json", [{"ticker": "GNW", "verdict": "ADVANCE"}])
    rc, log = run(base); check("a consensus without `status` (the retired rule) is named", rc != 0 and "retired rule" in log, log[-300:])
    write("consensus.json", [{"ticker": "GNW", "verdict": "ADVANCE", "status": "AGREED"}])
    os.remove(os.path.join(d, "funnel.json"))
    rc, log = run(base); check("a missing file is a FAIL, never 'probably fine'", rc != 0 and "funnel.json: MISSING" in log, log[-300:])
    write("funnel.json", {"survivors": ["GNW"], "dropped": [], "out": [], "names": {"GNW": {}}, "measurement": {}})
    write("decision.json", {"names": {"GNW": {"proposal": "WATCH"}}})
    rc, log = run(base); check("a slate verdict that differs from decision.json is named (R40)", rc != 0 and "!= decision.json" in log, log[-300:])
    write("decision.json", {"names": {"GNW": {"proposal": "ADVANCE"}}})
    write("floor_check.json", {"ok": False, "errors": ["oneil sent 3 messages"]})
    rc, log = run(base); check("a QA-hold floor_check.json that is not ok is named", rc != 0 and "floor_check.json not ok" in log, log[-300:])
    os.remove(os.path.join(d, "floor_check.json"))
    rc, log = run(base); check("without a hold round there is no floor_check.json, and that is healthy (R38: FLOOR retired)", rc == 0, log[-300:])
    write("pma_levels.json", {"run_date": "2026-11-02"})
    rc, log = run(base); check("yesterday's levels file is named -- today's levels are not being watched", rc != 0 and "NOT being watched" in log, log[-300:])


def test_the_cards_show_the_slate_status_objections_and_the_detect_lens_top_10(td):
    """R34/R31 on the PM's own read. A CONTESTED ticket prints its objections and what would clear them;
    a DROPPED name says so on the PASS row; the Detect-lens top 10 renders from lens_ranking.ranked with a
    marker where a name is also in the room; the fixed section order (R23) still holds. Rows WITHOUT
    `status` (pre-redesign runs) render exactly as before."""
    CARDS = os.path.join(TOOLS, "pma_cards.py")
    d = os.path.join(td, "cards_r34"); os.makedirs(d, exist_ok=True)
    cons = [{"ticker": "AAA", "verdict": "ADVANCE", "status": "CONTESTED", "conviction": 3, "lane": "MOMENTUM", "n_deciders": 7,
             "split": {"support": DEC[1:], "oppose": DEC[:1], "abstain": []}, "advisory": {},
             "objections": [{"voice": "oneil", "objection": "no test of the break yet", "would_clear": "a hold above the pivot on a down day"}], "reservations": []},
            {"ticker": "BBB", "verdict": "HOLD-FOR-CONDITIONS", "status": "AGREED", "conviction": 4, "lane": "PULLBACK", "n_deciders": 7,
             "split": {"support": DEC, "oppose": [], "abstain": []}, "advisory": {}, "objections": [], "reservations": [{"voice": "seow", "reservation": "size it small"}]},
            {"ticker": "CCC", "verdict": "PASS", "status": "DROPPED", "conviction": 2, "lane": "PULLBACK", "n_deciders": 7,
             "split": {"support": DEC[4:], "oppose": DEC[:4], "abstain": []}, "advisory": {},
             "objections": [{"voice": v, "objection": "x", "would_clear": "y"} for v in DEC[:4]], "reservations": []}]
    exp = {"daily_list": [{"ticker": t, "entry": 10.0, "rank": i, "gics_sector_name": "Tech", "setups": [], "unr_status": "NO"} for i, t in enumerate(["AAA", "BBB", "CCC"], 1)],
           "held_positions": [],
           "lens_ranking": {"ranked": [{"rank": 1, "ticker": "ZZZ", "positive": 5, "warnings": 0}, {"rank": 2, "ticker": "AAA", "positive": 4, "warnings": 1}]}}
    cards = {"advance": {"AAA": {"triggers": [{"id": "AAA-buy0", "kind": "close_above", "level": 10.5}, {"id": "AAA-dead", "kind": "close_below", "level": 9.5}], "confirms": "x", "kills": "y"}},
             "hold": {"BBB": {"triggers": [], "confirms": "", "kills": "", "not_structured_yet": "none"}}, "held": {}}
    p4 = {"ranked": [{"ticker": t, "lane": c["lane"]} for t, c in zip(["AAA", "BBB", "CCC"], cons)], "deliberation_set": ["AAA", "BBB", "CCC"]}
    for n, x in (("consensus.json", cons), ("export.json", exp), ("cards.json", cards), ("phase4.json", p4)):
        json.dump(x, open(os.path.join(d, n), "w"))
    words = {"session_label": "s", "stance_pill": "NEUTRAL", "bottom_line": {"headline": "h", "paragraph": "p", "stats": [{"value": "1", "label": "l"}] * 4},
             "market": {"what_happened": [{"lead": "a", "text": "b"}], "weather": [{"lead": "c", "text": "d"}]},
             "money": [{"group": "g", "read": "r", "meaning": "m"}], "book": [], "changed": ["c"],
             "cards": {"AAA": {"case": "c", "why": "w", "reason": {"agree": "A leader in a strong group breaking out on heavy buying.", "wrong_if": "It closes back under the breakout.", "wait_for": "An hourly close above the buy line."}, "readiness": "Ready now", "readiness_tone": "ok"}}, "holds": {"BBB": "waits"}, "passes": {"CCC": "no"}, "plan": ["p"], "caveats": ["c"]}
    tw = os.path.join(d, "words.json"); json.dump(words, open(tw, "w"))
    out = os.path.join(d, "r.html")
    rc, log = run([CARDS, "render", "--text", tw, "--consensus", os.path.join(d, "consensus.json"), "--export", os.path.join(d, "export.json"),
                   "--cards", os.path.join(d, "cards.json"), "--phase4", os.path.join(d, "phase4.json"), "--brackets", os.path.join(d, "nob.json"),
                   "--broker-stops", os.path.join(d, "nobs.json"), "--valen", os.path.join(d, "nov.json"), "--scorecard", os.path.join(d, "nosc.md"), "--out", out])
    check("the card report renders with status rows", rc == 0, log[-300:])
    if rc != 0: return
    h = open(out).read()
    check("the head pills count AGREED / CONTESTED / DROPPED", "1 AGREED" in h and "1 CONTESTED" in h and "1 DROPPED" in h)
    check("HOLD is labelled WATCH for the PM", "HOLD &middot; WATCH" in h)
    check("a CONTESTED ticket prints the objection and what would clear it",
          "Contested &middot; 1 of 7 object" in h and "no test of the break yet" in h and "a hold above the pivot on a down day" in h)
    check("an AGREED ticket prints its reservations", "Agreed, with 1 reservation" in h and "size it small" in h)
    check("a DROPPED name says so on the PASS row", "DROPPED</b> by 4 of 7 objections" in h)
    check("the Detect-lens top 10 renders from lens_ranking.ranked", "Detect-lens top 10" in h and "ZZZ" in h)
    check("a lens name that is also in the room carries the marker", "ADVANCE &middot; CONTESTED (in the room)" in h)
    order = ["Bottom line", "Part 1 · Daily weather", "Cross-asset · what happened", "Where money is moving",
             "Part 2 · Your book and the committee", "What it means for your book",
             "Committee recommendations", "HOLD for conditions", "PASS · off the list", "Detect-lens top 10", "The plan", "Read with care", "Top 20 AQE names", "DRAFT"]
    pos = [h.find(x) for x in order]
    check("the fixed section order still holds, with the lens panel before the plan and the Top-20 table at the very bottom", all(p >= 0 for p in pos) and pos == sorted(pos), str(list(zip(order, pos))))
    # weather-spec item 6 (PM 2026-11-01): Valen's management switch + trim/trail facts render under the book table
    vfile = os.path.join(d, "valen_mgmt.json")
    json.dump({"read_me_first": {"as_of": "2026-11-01", "headline": "h", "so_what": "half size", "because": [], "watch_for": []}, "stance": {"word": "NEUTRAL", "status": "OK"},
               "regime": "CHOP", "trend": [], "extension": [], "breadth": [], "gex": {}, "history": [], "neighbourhood": [], "theme_leaders": [], "rotation": [],
               "selection": {"no_buy_list": [], "relative_strength": [], "funnel": []}, "house": {"setups": []},
               "management": {"manage_note": {"status": "OK", "state": "ABOVE", "note": "Net new highs: the 8-day average (12.5) is above the 20-day (8.0) -- breakouts are being rewarded.", "doctrine": "quoted doctrine"},
                              "trim_trail": [{"ticker": "AAA", "r_multiple": 2.1, "r_multiple_2r_or_more": True, "tp1_printed": True, "pct_vs_ma_20": 5.2, "dist_from_stop_pct": 9.1, "days_held": 12, "gaps": []}]}}, open(vfile, "w"))
    words["weather"] = {k: f"Read: {k}." for k in ("stance", "gex", "heartbeat", "positioning", "volatility", "divergence", "call", "cot", "checklist", "turning", "themes", "groups")}
    json.dump(words, open(tw, "w"))        # R28: with a Valen file served, all 12 weather paragraphs must exist
    exp2 = json.load(open(os.path.join(d, "export.json"))); exp2["held_positions"] = [{"ticker": "AAA", "qty": 100, "entry": 9.0, "live_px": 10.0, "unreal_usd": 100.0}]
    json.dump(exp2, open(os.path.join(d, "export.json"), "w"))
    rc, log = run([CARDS, "render", "--text", tw, "--consensus", os.path.join(d, "consensus.json"), "--export", os.path.join(d, "export.json"),
                   "--cards", os.path.join(d, "cards.json"), "--phase4", os.path.join(d, "phase4.json"), "--brackets", os.path.join(d, "nob.json"),
                   "--broker-stops", os.path.join(d, "nobs.json"), "--valen", vfile, "--scorecard", os.path.join(d, "nosc.md"), "--out", out])
    hv = open(out).read() if rc == 0 else ""
    check("the Valen management switch renders under the book table", rc == 0 and "Valen management switch" in hv and "breakouts are being rewarded" in hv, log[-300:])
    check("the held name's trim/trail facts render (R, 2R+, first target, 20-day line) with the doctrine quoted",
          "First target printed" in hv and "+2.10" in hv and "pieces 17" in hv and "The call is yours" in hv)
    # pre-redesign rows (no status) render with none of the new text
    for c in cons:
        for k in ("status", "objections", "reservations", "n_deciders"):
            c.pop(k, None)
    exp.pop("lens_ranking")
    json.dump(cons, open(os.path.join(d, "consensus.json"), "w")); json.dump(exp, open(os.path.join(d, "export.json"), "w"))
    rc, log = run([CARDS, "render", "--text", tw, "--consensus", os.path.join(d, "consensus.json"), "--export", os.path.join(d, "export.json"),
                   "--cards", os.path.join(d, "cards.json"), "--phase4", os.path.join(d, "phase4.json"), "--brackets", os.path.join(d, "nob.json"),
                   "--broker-stops", os.path.join(d, "nobs.json"), "--valen", os.path.join(d, "nov.json"), "--scorecard", os.path.join(d, "nosc.md"), "--out", out])
    h2 = open(out).read() if rc == 0 else ""
    check("rows without status render as before (no contest text) and a missing lens_ranking is a declared gap",
          rc == 0 and "Contested" not in h2 and "DROPPED</b>" not in h2 and "declared gap" in h2, log[-300:])


def test_the_weather_cards_exist_and_are_wired(td):
    """PM 2026-11-01: Crown and Valen are READING SOURCES, not voices (R31). Their rules lived in the PM's
    memory; they now live in two persistent cards beside the voices, and the brief-writer / WRITE step read them."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    voices = os.path.join(os.path.dirname(root), "aegis-voices")
    for v in ("weather-crown", "weather-valen"):
        p = os.path.join(voices, "skills", v, "SKILL.md")
        t = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        check(f"{v} card exists and says it is not a voice", "not a voice" in t and "declared gap" in t)
    spec = os.path.join(voices, "skills", "weather_spec_2026-11-01.md")
    check("the full weather spec ships beside the cards", os.path.exists(spec))
    cr = open(os.path.join(voices, "skills", "weather-crown", "SKILL.md")).read()
    check("Crown card carries the gate, the percentile trap and 'never sizes'", "Stop." in cr and "Percentile trap" in cr and "Never sizes" in cr)
    va = open(os.path.join(voices, "skills", "weather-valen", "SKILL.md")).read()
    check("Valen card: stance is a reading, no levels to the voices, silence on U&R NO",
          "never a size" in va and "no levels to the voices" in va and "say nothing on NO or NA" in va)
    bw = open(os.path.join(root, "agents", "brief-writer.md")).read()
    check("brief-writer reads both cards before the weather paragraphs", "weather-crown" in bw and "weather-valen" in bw)
    run_yaml = open(os.path.join(HERE, "..", "RUN.yaml")).read()
    check("the WRITE step lists both cards as inputs", "weather-crown/SKILL.md" in run_yaml and "weather-valen/SKILL.md" in run_yaml)


def test_the_data_handoff_gate_catches_bad_data_before_a_committee(td):
    """PM 2026-11-01: 'before we run PMA we need the data agent to check data delivery and integrity from AQE
    to voices handoff. Else we run with shit data and not aware.' check.py data proves the published files
    agree with each other and with the run; each seeded defect is named."""
    CHK = os.path.abspath(os.path.join(HERE, "..", "..", "daily-check", "check.py"))
    od = os.path.join(td, "aegis", "output"); os.makedirs(os.path.join(od, "packets"), exist_ok=True)
    os.makedirs(os.path.join(td, "aegis", "skills", "premarket-analysis"), exist_ok=True)
    D = "2026-11-03"
    def row(t): return {"ticker": t, "on_longlist": True, "on_elder": t != "CCC", "entry": 10.0}
    def write_all(**over):
        last = {"date_sgt": D, "status": "success", "started_at": f"{D} 06:31 SGT", "exported_at": f"{D} 06:58 SGT", "finished_at": f"{D} 07:12 SGT", "packets_status": "Voice packets published: 8/8"}
        exp = {"date": D, "daily_list": [row("AAA"), row("BBB"), row("CCC")], "held_positions_status": "live",
               "held_positions": [{"ticker": "HLD", "qty": 1, "held_sl": 9.0, "held_stop_source": "journal 2026-11-02", "held_stop_status": "LIVE"}],
               "held_stops": {"status": "OK", "journal_date": "2026-11-02", "second_read_at": "2026-11-02T22:20:00Z", "differs": {}},
               "data_quality": {"flagged_count": 0, "flagged": []}, "lens_ranking": {"ranked": [{"rank": 1, "ticker": "AAA"}]}}
        jdir = os.path.join(td, "aegis", "data", "journal"); os.makedirs(jdir, exist_ok=True)
        json.dump({"date": "2026-11-02", "broker_sync": {"open_orders_pull_ran": True},
                   "open_positions": [{"ticker": "HLD", "qty": 1, "stop_live_broker": 9.0}], "review_flags": []},
                  open(os.path.join(jdir, "aegis_journal_2026-11-02.json"), "w"))
        cs = {"run_date": D, "universe": [row("AAA"), row("BBB"), row("CCC"), {"ticker": "HLD", "held": True}]}
        crown = {"generated_at": f"{D}T06:55:00+08:00", "status": "OK", "the_call": {"expression_family": "X"}, "read_me_first": {"headline": "h"}}
        valen = {"read_me_first": {"as_of": f"{D[:4]}-{D[5:7]}-{int(D[8:])-1:02d}T23:05:00Z"}, "stance": {"word": "NEUTRAL"},
                 "data_freshness": {"legs_table": [{"leg": "breadth_whole_market", "as_of": D, "expected": D, "reason": "CURRENT", "detail": ""}]}}   # UTC evening = the run date in SGT
        pk = {v: "# DICT x: 1=a\nticker\tsc_momentum\nAAA\t70\nBBB\t60\nCCC\t55\nHLD\t50\n" for v in DEC}
        for k, v in over.items():
            if k == "pk": pk.update(v)
            else: locals()[k].update(v) if isinstance(v, dict) else None
        if "exp" in over: exp.update(over["exp"])
        if "cs" in over: cs.update(over["cs"])
        if "crown" in over: crown.update(over["crown"])
        if "last" in over: last.update(over["last"])
        for name, obj in (("aqe_last_run.json", last), ("aqe_daily_export.json", exp), ("candidate_set.json", cs), ("aqe_crown_macro.json", crown), ("aqe_valen_dashboard.json", valen)):
            json.dump(obj, open(os.path.join(od, name), "w"))
        for f in os.listdir(os.path.join(od, "packets")):
            os.remove(os.path.join(od, "packets", f))
        for v, txt in pk.items():
            open(os.path.join(od, "packets", f"{v}.tsv"), "w").write(txt)
        write_committee_data()
    def write_committee_data(run_date=D, spy_last="2026-11-02", mutate=None):
        """The files src/pipeline/committee_data.py publishes, built by hand (plugin tests are stdlib only)."""
        import hashlib
        cdd = os.path.join(od, "committee_data"); os.makedirs(cdd, exist_ok=True)
        names = ["AAA", "BBB", "CCC", "HLD"]
        def dumps(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        fr = {"served": True, "summary": "above EMA9, 9>21, HH/HL, 1.0% under 20-day high"}
        grid_names = {t: {"served": True, "complete": True, "gaps": [], "reason": None, "W": fr, "D": fr, "H1": fr, "summary": "W: x | D: y | H1: z",
                          "fetch": {"daily": {"source": "panel", "rows": 300}, "hourly": {"source": "1hour", "rows": 70}}} for t in names}
        sha_names = hashlib.sha256(dumps(grid_names)).hexdigest()
        grid = {"schema": "mtf_grid.v1", "run_date": run_date, "generated_at": "x", "frames": ["W", "D", "H1"], "names": grid_names, "sha256_of_names": sha_names,
                "coverage": {"requested": 4, "served": 4, "complete": 4, "not_served": 0, "not_served_names": [], "hourly_native": 4, "hourly_rolled_up": 0, "hourly_none": 0}}
        fund = {"schema": "fundamentals_pack.v1", "run_date": run_date, "as_of": run_date, "source": "t",
                "coverage": {"requested": 4, "served": 4, "carried": 0, "partial": 0, "unserved": 0, "partial_names": [], "unserved_names": []},
                "tickers": {t: {"unserved": False, "status": "served", "pulled_on": run_date} for t in names}}
        closes = {"SPY": {"2026-11-02": 500.0}, "AAA": {"2026-11-02": 10.0}, "_missing": []}
        closes["SPY"] = {spy_last: 500.0}
        if mutate: mutate(grid, fund, closes)
        bodies = {"fundamentals_pack.json": dumps(fund), "mtf_grid.json": dumps(grid), "closes_scorecard.json": dumps(closes)}
        sch = {"fundamentals_pack.json": "fundamentals_pack.v1", "mtf_grid.json": "mtf_grid.v1", "closes_scorecard.json": "closes_scorecard.v1"}
        files = {n: {"schema": sch[n], "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "rows": 4, "served": 4, "unserved": 0, "as_of": run_date} for n, b in bodies.items()}
        files["closes_scorecard.json"].update({"served": 2, "rows": 2})
        man = {"schema": "committee_data_manifest.v1", "run_date": run_date, "status": "OK", "generated_at": "x", "scope": {"requested": 4},
               "files": files, "fmp_calls": 10, "elapsed_s": 1.0, "errors": []}
        for n, b in bodies.items(): open(os.path.join(cdd, n), "wb").write(b)
        open(os.path.join(cdd, "manifest.json"), "wb").write(dumps(man))
    def gate():
        # the per-voice coverage check has its own tests on REAL packets (tests/test_voice_coverage.py); these
        # minimal fixture packets carry two columns, so it is switched off - loudly, and the test asserts the note.
        return run([CHK, "data", "--output-dir", od, "--voice-contract", "none"])
    write_all()
    rc, log = gate(); check("a clean handoff reads Healthy", rc == 0 and "DATA HANDOFF: Healthy" in log, log[-400:])
    check("switching the per-voice coverage check off is never silent", "voice coverage check DISABLED" in log, log[-400:])
    write_all(pk={"seow": "# DICT\nticker\tsc_momentum\n"}); rc, log = gate(); check("an EMPTY decider packet is named", rc != 0 and "seow.tsv has a header but NO rows" in log, log[-300:])
    write_all(pk={"raschke": "ticker\tsc_momentum\nAAA\t70\nBBB\t60\nCCC\t55\nHLD\t50\nZZZ\t1\n"}); rc, log = gate(); check("a packet serving a name outside the candidate set is named", rc != 0 and "not in the candidate set" in log, log[-300:])
    write_all(pk={"raschke": "ticker\tsc_momentum\nAAA\t70\n"}); rc, log = gate(); check("a packet blind to most of the candidate set is named (yesterday's packet?)", rc != 0 and "blind to" in log, log[-300:])
    write_all(pk={"raschke": "ticker\tsc_momentum\tstructure\nAAA\t\t\nBBB\t\t\nCCC\t\t\nHLD\t\t\n"}); rc, log = gate(); check("a packet of blank cells is named", rc != 0 and "blank cells" in log, log[-300:])
    write_all(pk={"oneil": "ticker\tqs_market\nAAA\t1\n"}); rc, log = gate(); check("a PM-only field in a packet is named (R3)", rc != 0 and "qs_market" in log, log[-300:])
    write_all(pk={"weis": "ticker\tsc_momentum\nAAA\t70\n"}); rc, log = gate(); check("a stray packet for a non-decider is named (R31)", rc != 0 and "NON-decider" in log, log[-300:])
    write_all(); os.remove(os.path.join(od, "packets", "wyckoff.tsv")); rc, log = gate(); check("a missing decider packet is named", rc != 0 and "packet MISSING for decider wyckoff" in log, log[-300:])
    write_all(exp={"data_quality": {"flagged_count": 2, "flagged": [{"ticker": "AAA"}, {"ticker": "BBB"}]}}); rc, log = gate(); check("null core fields are named", rc != 0 and "flagged 2" in log, log[-300:])
    write_all(exp={"held_positions_status": "cache_fallback"}); rc, log = gate(); check("a non-live held book is named (the real-money incident class)", rc != 0 and "not live" in log, log[-300:])
    write_all(crown={"generated_at": "2026-11-02T06:55:00+08:00"}); rc, log = gate(); check("a stale Crown file is named", rc != 0 and "not the run date" in log, log[-300:])
    write_all(exp={"date": "2026-11-02"}); rc, log = gate(); check("an export dated differently from the run is named", rc != 0 and "export date" in log, log[-300:])
    write_all(cs={"universe": [row("AAA"), row("BBB"), row("CCC")]}); rc, log = gate(); check("a held position missing from the candidate set is named (R12)", rc != 0 and "held position(s) missing" in log, log[-300:])
    write_all(last={"status": "partial"}); rc, log = gate(); check("a partial run is named", rc != 0 and "did not finish clean" in log, log[-300:])
    # PM 2026-11-03: the committee's FMP inputs are fetched by the daily run; absent / stale / torn = FAIL, thin = WARN
    write_all(); shutil_cd = os.path.join(od, "committee_data", "manifest.json"); os.remove(shutil_cd)
    rc, log = gate(); check("missing committee data is named, with the courier fallback cost", rc != 0 and "committee_data/manifest.json" in log and "courier fallback" in log, log[-300:])
    write_all(); write_committee_data(run_date="2026-11-02")
    rc, log = gate(); check("committee data for another day is named STALE", rc != 0 and "STALE" in log, log[-300:])
    write_all(); write_committee_data(spy_last="2026-10-28")
    rc, log = gate(); check("closes that stop before the last US close are named", rc != 0 and "stale closes" in log, log[-300:])
    write_all(); p_ = os.path.join(od, "committee_data", "mtf_grid.json"); open(p_, "ab").write(b" ")
    rc, log = gate(); check("a committee data file changed after its manifest is named", rc != 0 and "mtf_grid.json: sha256/bytes differ" in log, log[-300:])
    def _thin(g, f, c):
        g["coverage"]["not_served_names"] = ["CCC"]; f["coverage"]["unserved_names"] = ["BBB"]
    write_all(); write_committee_data(mutate=_thin)
    rc, log = gate(); check("declared gaps in committee data are a WARN naming the names, not a block", rc == 0 and "WARN" in log and "'CCC'" in log and "'BBB'" in log, log[-400:])


def test_the_book_and_its_stops_are_one_checked_source(td):
    """PM 2026-11-02: 'Stop from Tiger is correct. That's the dependency ... ask for the stops then, both
    from the trade report and also during the AQE run.' The close's dated journal is the book of record;
    check.py data FAILS when it is missing, stale, did not read the orders, or disagrees with the export or a
    live broker read. A name with no stop order is a WARN. pma_levels stops builds from the journal."""
    CHK = os.path.abspath(os.path.join(HERE, "..", "..", "daily-check", "check.py"))
    sys.path.insert(0, os.path.dirname(CHK))
    import importlib; C = importlib.import_module("check")
    check("a Tuesday SGT run reads Monday's close", C.last_us_close("2026-11-03") == "2026-11-02")
    check("a Monday SGT run reads Friday's close", C.last_us_close("2026-11-02") == "2026-10-30")
    check("the Friday after Thanksgiving SGT reads the Wednesday close", C.last_us_close("2026-11-27") == "2026-11-25")
    jd = os.path.join(td, "book", "journal"); os.makedirs(jd, exist_ok=True)
    def journal(date="2026-11-02", pulled=True, stops=(("MP", 300, 36.66), ("V", 38, 391.8)), flags=()):
        for f in os.listdir(jd): os.remove(os.path.join(jd, f))
        json.dump({"date": date, "broker_sync": {"open_orders_pull_ran": pulled}, "review_flags": list(flags),
                   "open_positions": [{"ticker": t, "qty": q, "stop_live_broker": st, "entry": 1.0,
                                       "stop_order": ({"type": "STP_LMT", "stop": st, "limit": st, "qty": q, "time_in_force": "GTC"} if st else None)}
                                      for t, q, st in stops]}, open(os.path.join(jd, f"aegis_journal_{date}.json"), "w"))
    def export(sl=None, differs=None, held=("MP", "V"), jdate="2026-11-02", second="2026-11-02T22:20:00Z"):
        sl = sl or {"MP": 36.66, "V": 391.8}
        return {"held_positions": [{"ticker": t, "held_sl": sl.get(t), "held_stop_source": f"journal {jdate}"} for t in held],
                "held_stops": {"journal_date": jdate, "differs": differs or {}, "second_read_at": second, "second_read_reason": None if second else "not found"}}
    journal(); f, n = C.check_book(jd, "2026-11-03", export())
    check("a fresh journal with read stops that the export agrees with is clean", not f, f)
    for d in os.listdir(jd): os.remove(os.path.join(jd, d))
    f, n = C.check_book(jd, "2026-11-03", export()); check("a MISSING journal fails", f and "MISSING" in f[0], f)
    journal(date="2026-10-30"); f, n = C.check_book(jd, "2026-11-03", export(jdate="2026-10-30"))
    check("a STALE journal fails (yesterday's close did not file)", any("STALE" in x for x in f), f)
    journal(pulled=None); f, n = C.check_book(jd, "2026-11-03", export())
    check("a journal whose close did not read the orders fails", any("NOT read at the close" in x for x in f), f)
    journal(); f, n = C.check_book(jd, "2026-11-03", export(sl={"MP": 36.0, "V": 391.8}))
    check("an export stop that differs from the journal fails", any("MP: export held_sl 36.0" in x for x in f), f)
    journal(); f, n = C.check_book(jd, "2026-11-03", export(held=("V",)))
    check("an export held book that differs from the journal fails", any("!= journal" in x for x in f), f)
    journal(); f, n = C.check_book(jd, "2026-11-03", export(differs={"MP": "DIFFERS: stop moved, journal 36.66 -> Tiger 36.0"}))
    check("the two Tiger reads disagreeing fails, with what moved", any("stop moved" in x for x in f), f)
    journal(); f, n = C.check_book(jd, "2026-11-03", {"held_positions": [{"ticker": "MP"}, {"ticker": "V"}]})
    check("an export with no held_stops block fails", any("no held_stops block" in x for x in f), f)
    journal(stops=(("MP", 300, 36.66), ("V", 38, None), ("COIN", 100, None)),
            flags=[{"ticker": "COIN", "type": "auto_included_unrecognized", "detail": "auto-included"}])
    f, n = C.check_book(jd, "2026-11-03", None)
    check("a held name with NO stop is a WARN, not a FAIL", not f and any(x.startswith("WARN V") for x in n), (f, n))
    check("a new name auto-included at the close is surfaced for the PM's review", any("COIN: auto_included_unrecognized" in x for x in n), n)
    journal(); bs = os.path.join(td, "book", "broker_stops.json")
    json.dump({"journal_date": "2026-11-02", "disagreements": ["MP: stop moved, journal 36.66 -> broker 36.0"], "positions": {}}, open(bs, "w"))
    f, n = C.check_book(jd, "2026-11-03", None, bs)
    check("a live broker read at GATHER that disagrees with the journal fails", any("live broker read vs journal" in x for x in f), f)
    # pma_levels stops: from the journal alone (no Tiger connector needed), and cross-checked when live
    LV = os.path.join(TOOLS, "pma_levels.py"); jpath = os.path.join(jd, "aegis_journal_2026-11-02.json")
    out = os.path.join(td, "book", "bs_j.json")
    rc, log = run([LV, "stops", "--journal", jpath, "--out", out])
    B = json.load(open(out)) if rc == 0 else {}
    check("GATHER builds broker_stops.json from the journal alone", rc == 0 and B["positions"]["V"]["stop"] == 391.8 and B["journal_date"] == "2026-11-02", log[-300:])
    o = os.path.join(td, "book", "o.json"); p = os.path.join(td, "book", "p.json")
    json.dump({"result": [{"action": "SELL", "order_type": "STP_LMT", "sec_type": "STK", "symbol": "V", "quantity": 38, "stop_price": 391.8, "limit_price": 390.8},
                          {"action": "SELL", "order_type": "STP_LMT", "sec_type": "STK", "symbol": "MP", "quantity": 300, "stop_price": 36.0, "limit_price": 36.0}]}, open(o, "w"))
    json.dump({"result": [{"symbol": s_, "sec_type": "STK", "quantity": q} for s_, q in (("MARA", 17000), ("MP", 300), ("V", 38))]}, open(p, "w"))
    rc, log = run([LV, "stops", "--journal", jpath, "--orders", o, "--positions", p, "--out", out])
    B = json.load(open(out)) if rc == 0 else {}
    check("a live read is restricted to the journal's book (no MARA) and its disagreement is named",
          rc == 0 and set(B["positions"]) == {"MP", "V"} and B["disagreements"] == ["MP: stop moved, journal 36.66 -> broker 36.0"], str(B.get("disagreements")) + log[-200:])


def test_one_r_is_one_percent_of_the_journals_capital(td):
    """PM 2026-11-03 (final, relayed by the conductor; the repo's own CLAUDE.md records the 27 Oct ruling as 1% of
    the portfolio): the journal's 1R is 1% of its dynamic capital. aegis_fund.md one_r_usd (620) stays the single
    figure the committee sizes from; this pins the PERCENT that still drives the journal's own dyncap.one_r."""
    core = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    live = os.path.abspath(os.path.join(core, "..", "..", "charter", "parameters.yaml"))
    for label, path in (("plugin", os.path.join(core, "charter", "parameters.yaml")), ("live", live)):
        txt = open(path).read()
        check(f"{label} parameters.yaml: one_r_pct_of_dyncap is 1.0", "one_r_pct_of_dyncap: 1.0" in txt and "one_r_pct_of_dyncap: 1.5" not in txt, path)
    for path in (os.path.join(core, "tools", "journal_build.py"), os.path.abspath(os.path.join(core, "..", "..", "tools", "journal_build.py"))):
        txt = open(path).read()
        check(f"{os.path.relpath(path, core)}: the fallback default is 1.0", "one_r_pct = 1.0" in txt and "one_r_pct = 1.5" not in txt, path)
    fund = open(os.path.join(core, "config", "aegis_fund.md")).read()
    check("aegis_fund.md still carries the single committee figure, one_r_usd 620", "one_r_usd: 620" in fund)


def test_review_fixes_count_only_validated_forms_and_never_double_count(td):
    """Independent review 2026-11-01, findings 1, 2, 3, 7, 8, 9: the counter refuses an unvalidated or partial
    ratification; split-ballot parts beside the merged file are not double-counted; a silent open floor fails;
    tick requires a glob to match; the plugin-root tool copies are identical to the live ones; slate-cut exists."""
    d, p4 = _committee_fixture(td, "review")
    # finding 2: leave parts beside the merged ballot -> board must count each voice once
    r2 = os.path.join(d, "forms", "r2"); src = json.load(open(os.path.join(r2, "oneil.json")))
    json.dump(dict(src, votes=src["votes"][:2]), open(os.path.join(r2, "oneil.part1of2.json"), "w"))
    json.dump(dict(src, votes=src["votes"][2:]), open(os.path.join(r2, "oneil.part2of2.json"), "w"))
    board = os.path.join(d, "board.json")
    rc, log = run([PIPE, "board", "--round2", r2, "--phase4", p4, "--date", "2026-11-01", "--out", board])
    B = json.load(open(board)) if rc == 0 else {"names": []}
    gnw = next((n for n in B["names"] if n["ticker"] == "GNW"), {"split": {"support": []}})
    check("split-ballot parts beside the merged file are NOT double-counted", rc == 0 and gnw["split"]["support"].count("oneil") == 1, str(gnw["split"]))
    # finding 1: a bad answer and a partial ratification are refused by the counter
    slate = os.path.join(d, "slate.json"); json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY", "WATCH")]}, open(slate, "w"))
    for v in DEC:
        _ratify(d, "ratify", v, {"GNW": "AGREE", "BBY": "AGREE"})
    json.dump({"voice": "seow", "date": "2026-11-01", "tickets": [{"ticker": "GNW", "answer": "Object"}, {"ticker": "BBY", "answer": "AGREE"}]}, open(os.path.join(d, "forms", "ratify", "seow.json"), "w"))
    args = [PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratify"), "--board", board, "--phase4", p4, "--date", "2026-11-01",
            "--out", os.path.join(d, "c.json"), "--record", os.path.join(d, "r.json")]
    rc, log = run(args); check("a misspelled answer is REFUSED by the counter, never a silent non-objection", rc != 0 and "not a valid answer" in log, log[-300:])
    json.dump({"voice": "seow", "date": "2026-11-01", "tickets": [{"ticker": "GNW", "answer": "AGREE"}]}, open(os.path.join(d, "forms", "ratify", "seow.json"), "w"))
    rc, log = run(args); check("a ratification that does not cover the slate is REFUSED", rc != 0 and "must cover exactly" in log, log[-300:])
    _ratify(d, "ratify", "seow", {"GNW": "AGREE", "BBY": "AGREE"})
    rc, log = run(args); check("a clean set counts", rc == 0, log[-300:])
    # finding 9: slate-cut
    qa = os.path.join(d, "qa.json"); json.dump({"voice": "steenbarger", "holds": [{"ticker": "BBY", "question": "q"}]}, open(qa, "w"))
    rc, log = run([PIPE, "slate-cut", "--slate", slate, "--qa", qa, "--out", os.path.join(d, "slate_held.json")])
    check("slate-cut writes the held-tickets slate", rc == 0 and [x["ticker"] for x in json.load(open(os.path.join(d, "slate_held.json")))["tickets"]] == ["BBY"], log[-200:])
    # finding 3: a silent open floor fails unless allowed
    fl = os.path.join(d, "forms", "floor"); os.makedirs(fl, exist_ok=True)
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", os.path.join(d, "fc.json")])
    check("zero messages on an open floor is a FAIL", rc != 0 and "silent floor" in log, log[-300:])
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--allow-silent", "--out", os.path.join(d, "fc.json")])
    check("--allow-silent accepts it explicitly", rc == 0, log[-200:])
    # nested layout forms/floor/<ticker>/<msg>.json is read
    os.makedirs(os.path.join(fl, "BBY"), exist_ok=True)
    json.dump({"voice": "oneil", "date": "2026-11-01", "ticker": "BBY", "msg_id": "oneil-BBY-1", "to": "room", "in_reply_to": None, "text": "x", "stance_now": "SUPPORT", "changed_mind": False}, open(os.path.join(fl, "BBY", "oneil-BBY-1.json"), "w"))
    rc, log = run([PIPE, "floor-check", "--messages", fl, "--board", board, "--out", os.path.join(d, "fc.json")])
    check("a nested forms/floor/<ticker>/ message is counted", rc == 0 and json.load(open(os.path.join(d, "fc.json")))["messages"] == 1, log[-200:])
    # finding 7: tick requires a glob to match
    import shutil
    work = os.path.join(d, "tick"); os.makedirs(os.path.join(work, "tools"), exist_ok=True)
    for f in ("RUN.yaml", "RULINGS.yaml"): shutil.copy(os.path.join(HERE, "..", f), os.path.join(work, f))
    for f in ("registrar.py", "preflight_run.py"): shutil.copy(os.path.join(TOOLS, f), os.path.join(work, "tools", f))
    reg = os.path.join(work, "tools", "registrar.py")
    subprocess.run([sys.executable, reg, "init", "--date", "2026-11-01"], cwd=work, capture_output=True, text=True)
    r = subprocess.run([sys.executable, reg, "tick", "--step", "NOMINATE", "--status", "done"], cwd=work, capture_output=True, text=True)
    check("tick REFUSES a NOMINATE with zero forms (the glob matched nothing)", r.returncode != 0 and "matched nothing" in r.stdout + r.stderr, (r.stdout + r.stderr)[-200:])
    os.makedirs(os.path.join(work, "forms", "r1")); open(os.path.join(work, "forms", "r1", "oneil.json"), "w").write("{}")
    r = subprocess.run([sys.executable, reg, "tick", "--step", "NOMINATE", "--status", "done"], cwd=work, capture_output=True, text=True)
    check("tick allows it once a form exists", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    # finding 8: root copies identical
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    for f in ("registrar.py", "pma_pipeline.py", "pma_cards.py", "preflight_run.py", "git_sync.py"):
        rp = os.path.join(root, "tools", f)
        check(f"plugin-root tools/{f} is identical to the live copy", not os.path.exists(rp) or open(rp).read() == open(os.path.join(TOOLS, f)).read())
    # finding 4/6/10/11: the run map's commands name real flags
    run_yaml = open(os.path.join(HERE, "..", "RUN.yaml")).read()
    check("VOTE validates room and universe", "--round 2 --candidates candidate_set.json --phase4 phase4.json --packet" in run_yaml)
    check("record-verdicts / repeat-watch / gate carry their required flags", "record-verdicts --consensus" in run_yaml and "repeat-watch --ledger" in run_yaml and "gate --brief" in run_yaml)
    check("PM-LENS runs before RANK and RANK reads it", run_yaml.index("name: PM-LENS") < run_yaml.index("name: RANK"))
    check("CHALLENGE reads the candidate set as its universe", "--universe candidate_set.json" in run_yaml)


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


# ============================ R38-R41 -- THE TWO-TIER FUNNEL (PM 2026-11-02) ============================
FAMILY = {"oneil": "breakout", "minervini": "breakout", "livermore": "pivotal", "elder-lens": "impulse",
          "seow": "position", "raschke": "swing", "wyckoff": "structure"}
GRID = {"W": "above the rising 21-week EMA", "D": "close above EMA9 > EMA21", "H1": "upper fifth of the day's range"}


def _validate(td, obj, tag, *args):
    p = os.path.join(td, f"{tag}.json"); json.dump(obj, open(p, "w"))
    return run([REG, "validate", "--file", p, *args])


def _cross_plan(t, idx, ridx, kind):
    """The seeded tier-1 outcome. GNW all CONFIRM -> SURVIVES. BBY support claims all REFUTED -> DROPPED.
    MFG claim 0: CONFIRM + REFUTE, claim 1: CANNOT_SEE -> 1 >= 1, SURVIVES (and one pair). LNG: 1 CONFIRM vs 3
    REFUTE on support -> DROPPED. VRNS has no SUPPORT -> OUT, no claims."""
    if t == "GNW":
        return "CONFIRM"
    if t == "BBY":
        return "REFUTE" if kind == "for" else "CONFIRM"
    if t == "MFG":
        return ("CONFIRM", "REFUTE")[ridx] if idx == 0 else "CANNOT_SEE"
    if t == "LNG":
        return "CONFIRM" if (idx == 0 and ridx == 0) else "REFUTE"
    return "CANNOT_SEE"


def _blind(B, v, t):
    n = B["names"][t]
    return "SUPPORT" if v in n["support"] else "OPPOSE" if v in n["oppose"] else "ABSTAIN" if v in n["abstain"] else None


def _cross_form(B, v, mover=None):
    """mover = (voice, ticker, new_stance): that seat moves on that name and says what moved it."""
    rows = []
    claims = {c["claim_id"]: (t, i, c) for t, n in B["names"].items() for i, c in enumerate(n["claims"])}
    for cid in B["routing"][v]:
        t, i, c = claims[cid]
        ridx = c["reviewers"].index(v)
        st = _blind(B, v, t)
        moved = mover is not None and mover[:2] == (v, t)
        if moved:
            st = mover[2]
        rows.append({"claim_id": cid, "ticker": t, "ruling": _cross_plan(t, i, ridx, c["kind"]),
                     "evidence": f"structure 86.3 and elder 7 on {t}, read by my own method", "tf": dict(GRID),
                     "stance_after": st, "changed_mind": moved, "what_moved_me": "the weekly base holds above EMA21" if moved else None})
    return {"voice": v, "date": "2026-11-02", "rulings": rows}


def _dec(t, stance, timing=None, word=None, tf=None, plain=None, wrong="close back under the 20-day average", void=None):
    d = {"ticker": t, "stance": stance, "wrong_if": wrong, "market_void": void, "reason": "my method's read on the grid"}
    if stance == "SUPPORT":
        d.update({"timing": timing, "trigger": {"word": word, "tf": tf, "plain": plain}})
    else:
        d.update({"timing": None, "trigger": None})
    return d


SPY_VOID = "SPY close_below put wall 750"
# GNW: 7 SUPPORT, ACT_NOW 4 vs WAIT 3 -> ADVANCE. The ACT_NOW camp splits 2-2 between h1_close_above:bar_high/H1
# (oneil, minervini at conviction 3) and close_above:pivot_high/D (raschke 4, wyckoff 5): the modal tie is broken by
# the higher blind conviction -> close_above:pivot_high/D. Three SUPPORT decisions name the SPY void, one names QQQ.
# MFG: 4 SUPPORT, ACT_NOW 2 vs WAIT 2 -> a TIE -> WATCH; the WAIT camp's trigger is in_zone:ma_20/D.
T2_PLAN = {
    "oneil": [_dec("GNW", "SUPPORT", "ACT_NOW", "h1_close_above:bar_high", "H1", "an hourly close over yesterday's high", void=SPY_VOID),
              _dec("MFG", "SUPPORT", "ACT_NOW", "h1_close_above:bar_high", "H1", "hourly close over yesterday's high")],
    "minervini": [_dec("GNW", "SUPPORT", "ACT_NOW", "h1_close_above:bar_high", "H1", "hourly close over the prior high", void=SPY_VOID),
                  _dec("MFG", "SUPPORT", "ACT_NOW", "h1_close_above:bar_high", "H1", "hourly close over yesterday's high")],
    "livermore": [_dec("GNW", "SUPPORT", "WAIT", "close_above:pivot_high", "D", "a daily close through the pivot after a pause", void=SPY_VOID),
                  _dec("MFG", "OPPOSE")],
    "elder-lens": [_dec("GNW", "SUPPORT", "WAIT", "in_zone:ma_20", "D", "a pull back to the 20-day"),
                   _dec("MFG", "SUPPORT", "WAIT", "in_zone:ma_20", "D", "back to the 20-day average", wrong="loses the 20-day on a close")],
    "seow": [_dec("GNW", "SUPPORT", "WAIT", "in_zone:ma_20", "D", "back to the 20-day", void="QQQ close_below ma_50"),
             _dec("MFG", "SUPPORT", "WAIT", "in_zone:ma_20", "D", "a test of the 20-day average and a hold of it on the close")],
    "raschke": [_dec("GNW", "SUPPORT", "ACT_NOW", "close_above:pivot_high", "D", "close over the pivot"),
                _dec("MFG", "ABSTAIN")],
    "wyckoff": [_dec("GNW", "SUPPORT", "ACT_NOW", "close_above:pivot_high", "D", "a daily close through the creek on volume"),
                _dec("MFG", "OPPOSE")],
}


def _funnel_chain(td, tag, mover=("raschke", "MFG", "SUPPORT")):
    """The tier-1 + tier-2 chain on the committee fixture, every hop through the real tool and the real registrar.
    Returns (dir, phase4, paths). GNW is given convictions wyckoff 5 / raschke 4 so 'highest conviction' is tested."""
    d, p4 = _committee_fixture(td, tag)
    for v in DEC:
        f = os.path.join(d, "forms", "r2", f"{v}.json"); b = json.load(open(f))
        for row in b["votes"]:
            if row["ticker"] == "GNW" and v in ("wyckoff", "raschke"):
                row["conviction"] = 5 if v == "wyckoff" else 4
                row["self_counter"] = "a failed retest of the creek would undo it"
                row["case"]["for"] = f"{v}: the creek was crossed on rising volume"
        json.dump(b, open(f, "w"))
    P = {k: os.path.join(d, n) for k, n in (("board", "board.json"), ("claims", "claims_board.json"), ("funnel", "funnel.json"),
                                             ("pairs", "pairs.json"), ("decision", "decision.json"), ("cp", "claims_packets"),
                                             ("t2p", "tier2_packets"), ("cross", os.path.join("forms", "cross")),
                                             ("tier2", os.path.join("forms", "tier2")))}
    ch = os.path.join(d, "forms", "challenge", "steenbarger.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", ch, "--date", "2026-11-02", "--out", P["board"]])
    rc, log = run([PIPE, "claims", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", ch, "--mtf", fx("mtf.json"),
                   "--export", fx("export.json"), "--date", "2026-11-02", "--out", P["claims"], "--packets-dir", P["cp"]])
    P["claims_log"] = (rc, log)
    if rc != 0:
        return d, p4, P
    B = json.load(open(P["claims"]))
    os.makedirs(P["cross"], exist_ok=True)
    P["cross_rc"] = {}
    for v in DEC:
        if not B["routing"].get(v):
            continue
        f = os.path.join(P["cross"], f"{v}.json"); json.dump(_cross_form(B, v, mover), open(f, "w"))
        P["cross_rc"][v] = run([REG, "validate", "--file", f, "--kind", "cross", "--claims", P["claims"]])
    P["score_log"] = run([PIPE, "claims-score", "--claims", P["claims"], "--rulings", P["cross"], "--date", "2026-11-02", "--out", P["funnel"]])
    P["pair_log"] = run([PIPE, "pair", "--claims", P["claims"], "--rulings", P["cross"], "--funnel", P["funnel"], "--mtf", fx("mtf.json"),
                         "--date", "2026-11-02", "--out", P["pairs"], "--packets-dir", P["t2p"]])
    if not os.path.exists(P["pairs"]):
        return d, p4, P
    pairs = json.load(open(P["pairs"]))["pairs"]
    os.makedirs(P["tier2"], exist_ok=True)
    P["tier2_rc"] = {}
    for v in DEC:
        form = {"voice": v, "date": "2026-11-02", "decisions": json.loads(json.dumps(T2_PLAN[v])),
                "answers": [{"pair_id": p["pair_id"], "ticker": p["ticker"], "to": p["refuter"], "concede": False,
                             "text": "'no weekly base' -- the weekly holds above EMA21 three bars running; I hold."} for p in pairs if p["author"] == v]}
        f = os.path.join(P["tier2"], f"{v}.json"); json.dump(form, open(f, "w"))
        P["tier2_rc"][v] = run([REG, "validate", "--file", f, "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"]])
    P["timing_log"] = run([PIPE, "decide-timing", "--tier2", P["tier2"], "--funnel", P["funnel"], "--phase4", p4,
                           "--board", P["board"], "--date", "2026-11-02", "--out", P["decision"]])
    return d, p4, P


def test_two_tier_funnel_is_counted_by_code(td):
    """R38 (PM 2026-11-02). Tier 1: code builds the claims board (the two highest-conviction SUPPORT cases and OPPOSE
    cases per name; no SUPPORT = OUT), routes each claim to two reviewers of ANOTHER method family -- never the author,
    the opposite camp first, load-balanced -- and applies the survival rule. Tier 2: every refute of a surviving claim
    is paired with its author; decide-timing counts: <4 SUPPORT not slated, ACT_NOW > WAIT ADVANCE, a tie WATCH, ONE
    modal trigger. Every count is code; decide-timing refuses a form that does not decide every survivor."""
    d, p4, P = _funnel_chain(td, "funnel")
    rc, log = P["claims_log"]
    check("claims exits clean", rc == 0, log[-400:])
    if rc != 0: return
    B = json.load(open(P["claims"]))
    N = B["names"]
    check("a name with no SUPPORT vote is OUT and carries no claims", B["out"] == ["VRNS"] and N["VRNS"]["claims"] == [], str(B["out"]))
    check("claims are the two highest-conviction SUPPORT seats' case.for (ties by seat order)",
          [c["claim_id"] for c in N["GNW"]["claims"]] == ["GNW-wyckoff-for", "GNW-raschke-for"], str([c["claim_id"] for c in N["GNW"]["claims"]]))
    check("... and the two highest-conviction OPPOSE seats' case.against",
          [c["claim_id"] for c in N["BBY"]["claims"]] == ["BBY-oneil-for", "BBY-minervini-for", "BBY-seow-against", "BBY-raschke-against"],
          str([c["claim_id"] for c in N["BBY"]["claims"]]))
    check("the claim text is the seat's own case, verbatim", N["GNW"]["claims"][0]["text"] == "wyckoff: the creek was crossed on rising volume")
    allc = [(t, c) for t, n in N.items() for c in n["claims"]]
    check("every claim is routed to exactly two reviewers", all(len(c["reviewers"]) == 2 for _, c in allc), str([(c["claim_id"], c["reviewers"]) for _, c in allc if len(c["reviewers"]) != 2]))
    check("a claim is NEVER routed to its author", all(c["author"] not in c["reviewers"] for _, c in allc))
    check("a claim is NEVER routed to a seat of the author's method family (oneil and minervini are one family)",
          all(FAMILY[r] != FAMILY[c["author"]] for _, c in allc for r in c["reviewers"]),
          str([(c["claim_id"], c["reviewers"]) for _, c in allc if any(FAMILY[r] == FAMILY[c["author"]] for r in c["reviewers"])]))
    bby = {c["claim_id"]: c["reviewers"] for c in N["BBY"]["claims"]}
    check("a SUPPORT claim goes to the opposite camp first (BBY's opposers)",
          set(bby["BBY-oneil-for"]) <= {"seow", "raschke", "wyckoff"} and set(bby["BBY-minervini-for"]) <= {"seow", "raschke", "wyckoff"}, str(bby))
    check("an AGAINST claim goes to the supporters first", set(bby["BBY-seow-against"]) <= {"oneil", "minervini", "livermore", "elder-lens"}, str(bby))
    check("with no opposite camp, the abstainers come next (MFG's raschke and wyckoff)",
          set(N["MFG"]["claims"][0]["reviewers"]) == {"raschke", "wyckoff"}, str(N["MFG"]["claims"][0]["reviewers"]))
    check("load balance: GNW's second claim goes to the two least-loaded eligible seats, not the first claim's reviewers",
          N["GNW"]["claims"][0]["reviewers"] == ["oneil", "minervini"] and N["GNW"]["claims"][1]["reviewers"] == ["livermore", "elder-lens"],
          str([c["reviewers"] for c in N["GNW"]["claims"]]))
    check("routing per seat == the claims that name it", all(sorted(B["routing"][v]) == sorted(c["claim_id"] for _, c in allc if v in c["reviewers"]) for v in DEC))
    check("the board carries the measurement and NO verdict", B["measurement"]["claims_issued"] == len(allc) and "verdict" not in json.dumps(B))
    pk = json.load(open(os.path.join(P["cp"], "wyckoff.json")))
    check("a reviewer's packet holds exactly its routed claims", [c["claim_id"] for c in pk["claims"]] == B["routing"]["wyckoff"])
    keys = {k for c in pk["claims"] for k in c}
    check("the packet carries the claim, its author, the grid and the row -- never the stance counts or the other reviewer",
          keys == {"claim_id", "ticker", "kind", "author", "text", "your_blind_vote", "mtf", "row"} and all("sc_momentum" in c["row"] for c in pk["claims"]), str(keys))
    check("the packet has no other seat's ruling or vote", not any(w in json.dumps(pk) for w in ('"support"', '"oppose"', '"reviewers"', '"ruling"')))
    # ---- tier 1 rulings: registrar on arrival ----
    check("every synthetic cross form validates", all(r[0] == 0 for r in P["cross_rc"].values()), str({v: r[1][-200:] for v, r in P["cross_rc"].items() if r[0]}))
    own = _cross_form(B, "wyckoff"); own["rulings"][0]["claim_id"] = "GNW-wyckoff-for"; own["rulings"][0]["ticker"] = "GNW"
    rc, log = _validate(d, own, "cross_own", "--kind", "cross", "--claims", P["claims"])
    check("a voice ruling on its OWN claim is REJECTED", rc != 0 and "AUTHOR" in log, log[-300:])
    gap = _cross_form(B, "wyckoff"); gap["rulings"] = gap["rulings"][1:]
    rc, log = _validate(d, gap, "cross_gap", "--kind", "cross", "--claims", P["claims"])
    check("a cross form missing a routed claim is REJECTED", rc != 0 and "no ruling on routed claim" in log, log[-300:])
    lie = _cross_form(B, "seow"); lie["rulings"][0]["changed_mind"] = True; lie["rulings"][0]["what_moved_me"] = "x"
    rc, log = _validate(d, lie, "cross_lie", "--kind", "cross", "--claims", P["claims"])
    check("changed_mind must agree with stance_after vs the blind vote", rc != 0 and "changed_mind" in log, log[-300:])
    # R16.1 for the funnel: a reviewer whose form will not fit one 24 KB file files parts; merge proves coverage
    full = json.load(open(os.path.join(P["cross"], "seow.json"))); half = len(full["rulings"]) // 2
    sp = os.path.join(d, "forms", "cross_split"); os.makedirs(sp, exist_ok=True)
    for k, chunk in ((1, full["rulings"][:half]), (2, full["rulings"][half:])):
        json.dump(dict(full, rulings=chunk), open(os.path.join(sp, f"seow.part{k}of2.json"), "w"))
    rc1, l1 = run([REG, "validate", "--file", os.path.join(sp, "seow.part1of2.json"), "--kind", "cross", "--claims", P["claims"], "--part", "1", "--of", "2"])
    rc0, l0 = run([REG, "validate", "--file", os.path.join(sp, "seow.part1of2.json"), "--kind", "cross", "--claims", P["claims"]])
    check("a declared cross PART is validated on its own; the same file undeclared is refused for coverage", rc1 == 0 and rc0 != 0, l1[-200:] + l0[-200:])
    mo = os.path.join(sp, "seow.json")
    rc, log = run([REG, "merge", "--kind", "cross", "--glob", os.path.join(sp, "seow.part*.json"), "--claims", P["claims"], "--out", mo])
    check("merge --kind cross stitches the parts and proves the routing is covered", rc == 0 and json.load(open(mo))["rulings"] == full["rulings"], log[-300:])
    os.remove(os.path.join(sp, "seow.part2of2.json"))
    rc, log = run([REG, "merge", "--kind", "cross", "--glob", os.path.join(sp, "seow.part*.json"), "--claims", P["claims"], "--out", os.path.join(sp, "x.json")])
    check("merge refuses parts that do not cover the routing", rc != 0 and "no ruling on routed claim" in log, log[-300:])
    t2full = json.load(open(os.path.join(P["tier2"], "oneil.json")))
    sp2 = os.path.join(d, "forms", "tier2_split"); os.makedirs(sp2, exist_ok=True)
    json.dump(dict(t2full, decisions=t2full["decisions"][:1]), open(os.path.join(sp2, "oneil.part1of2.json"), "w"))
    json.dump(dict(t2full, decisions=t2full["decisions"][1:], answers=[]), open(os.path.join(sp2, "oneil.part2of2.json"), "w"))
    rc, log = run([REG, "merge", "--kind", "tier2", "--glob", os.path.join(sp2, "oneil.part*.json"), "--pairs", P["pairs"], "--funnel", P["funnel"],
                   "--out", os.path.join(sp2, "oneil.json")])
    check("merge --kind tier2 proves every pair and every survivor is covered", rc == 0, log[-300:])
    # ---- the first funnel ----
    rc, log = P["score_log"]
    check("claims-score exits clean", rc == 0, log[-400:])
    if rc != 0: return
    F = json.load(open(P["funnel"]))
    st = {t: F["names"][t]["status"] for t in ROOM}
    check("survival rule: GNW all confirmed SURVIVES; MFG 1 confirm vs 1 refute SURVIVES (confirms >= refutes)",
          st["GNW"] == "SURVIVES" and st["MFG"] == "SURVIVES", str(st))
    check("survival rule: BBY's support claims all refuted -> DROPPED; LNG 1 confirm vs 3 refutes -> DROPPED; VRNS OUT",
          (st["BBY"], st["LNG"], st["VRNS"]) == ("DROPPED", "DROPPED", "OUT"), str(st))
    check("survivors / dropped / out lists in room order", (F["survivors"], F["dropped"], F["out"]) == (["GNW", "MFG"], ["BBY", "LNG"], ["VRNS"]))
    tl = F["names"]["MFG"]["tallies"]
    check("tallies are counted per side", (tl["support_confirm"], tl["support_refute"], tl["support_cannot_see"]) == (1, 1, 2), str(tl))
    check("a DROPPED name carries the refuting evidence on the record",
          len(F["names"]["BBY"]["refuted_by"]) == 4 and all(x["evidence"] and x["tf"]["H1"] for x in F["names"]["BBY"]["refuted_by"]))
    M = F["measurement"]
    check("measurement: claims issued and rulings by kind add up", M["claims_issued"] == len(allc)
          and M["rulings_total"] == 2 * len(allc) and set(M["rulings"]) == {"CONFIRM", "REFUTE", "CANNOT_SEE"}, str(M))
    check("measurement: the seat whose stance moved on a peer's evidence is recorded, with what moved it",
          M["stances_changed"] == [{"voice": "raschke", "ticker": "MFG", "from": "ABSTAIN", "to": "SUPPORT", "what_moved_me": "the weekly base holds above EMA21"}], str(M["stances_changed"]))
    check("funnel.json carries no verdict", "verdict" not in json.dumps(F))
    e = os.path.join(d, "forms", "empty_cross"); os.makedirs(e, exist_ok=True)
    rc, log = run([PIPE, "claims-score", "--claims", P["claims"], "--rulings", e, "--date", "2026-11-02", "--out", os.path.join(d, "x.json")])
    check("claims-score refuses to count an empty forms dir", rc != 0 and "refusing to count an empty room" in log, log[-200:])
    bad = os.path.join(d, "forms", "cross_bad"); shutil.copytree(P["cross"], bad)
    g = json.load(open(os.path.join(bad, "wyckoff.json"))); g["rulings"] = g["rulings"][1:]; json.dump(g, open(os.path.join(bad, "wyckoff.json"), "w"))
    rc, log = run([PIPE, "claims-score", "--claims", P["claims"], "--rulings", bad, "--date", "2026-11-02", "--out", os.path.join(d, "x.json")])
    check("claims-score refuses a form that does not cover its routing (defence in depth)", rc != 0 and "must cover exactly" in log, log[-200:])
    # ---- the pairing ----
    rc, log = P["pair_log"]
    check("pair exits clean", rc == 0, log[-300:])
    PR = json.load(open(P["pairs"]))
    mfg0 = N["MFG"]["claims"][0]
    check("every REFUTE on a SURVIVING name is one pair, in front of the claim's author (DROPPED names pair nothing)",
          [(p["ticker"], p["author"], p["refuter"]) for p in PR["pairs"]] == [("MFG", mfg0["author"], mfg0["reviewers"][1])], str(PR["pairs"]))
    check("pair_id = <claim_id>~<refuter>", PR["pairs"][0]["pair_id"] == f"{mfg0['claim_id']}~{mfg0['reviewers'][1]}")
    t2 = {v: json.load(open(os.path.join(P["t2p"], f"{v}.json"))) for v in DEC if os.path.exists(os.path.join(P["t2p"], f"{v}.json"))}
    check("every decider present gets a tier-2 packet, even with nothing to answer", sorted(t2) == sorted(DEC))
    check("the author's packet carries its pair; nobody else's does",
          [p["pair_id"] for p in t2[mfg0["author"]]["answer_pairs"]] == [PR["pairs"][0]["pair_id"]]
          and all(not t2[v]["answer_pairs"] for v in DEC if v != mfg0["author"]))
    sv = t2["wyckoff"]["survivors"]
    check("survivors carry tallies as COUNTS only, never who ruled", [s["ticker"] for s in sv] == ["GNW", "MFG"]
          and set(sv[1]["tallies"]) == {"support_confirm", "support_refute", "against_confirm", "against_refute"}
          and not any(v in json.dumps(sv) for v in DEC if v != "wyckoff"), json.dumps(sv)[:300])
    check("the condition vocabulary rides in every tier-2 packet", "h1_close_above" in t2["oneil"]["vocab"]["words"])
    # ---- the second funnel ----
    check("every synthetic tier-2 form validates", all(r[0] == 0 for r in P["tier2_rc"].values()), str({v: r[1][-300:] for v, r in P["tier2_rc"].items() if r[0]}))
    rc, log = P["timing_log"]
    check("decide-timing exits clean", rc == 0, log[-400:])
    if rc != 0: return
    D = json.load(open(P["decision"]))
    g, m = D["names"]["GNW"], D["names"]["MFG"]
    check("7 SUPPORT, ACT_NOW 4 > WAIT 3 -> ADVANCE", g["proposal"] == "ADVANCE" and g["counts"] == {"support": 7, "oppose": 0, "abstain": 0, "act_now": 4, "wait": 3}, str(g["counts"]))
    check("a 2-2 modal split inside the winning camp is broken by the higher blind conviction (wyckoff 5)",
          (g["trigger"]["word"], g["trigger"]["tf"]) == ("close_above:pivot_high", "D"), str(g["trigger"]))
    check("the trigger's plain words are the most complete of its holders", g["trigger"]["plain"] == "a daily close through the creek on volume")
    check("ACT_NOW 2 == WAIT 2 -> WATCH (a tie is WATCH)", m["proposal"] == "WATCH" and (m["counts"]["act_now"], m["counts"]["wait"]) == (2, 2), str(m))
    check("WATCH takes the WAIT camp's trigger", (m["trigger"]["word"], m["trigger"]["tf"]) == ("in_zone:ma_20", "D"), str(m["trigger"]))
    check("the market kill is the modal market_void across all SUPPORT decisions, parsed",
          D["market_kill"] and D["market_kill"]["plain"] == SPY_VOID and (D["market_kill"]["symbol"], D["market_kill"]["word"], D["market_kill"]["level"]) == ("SPY", "close_below", 750.0)
          and D["market_kill"]["seats"] == ["oneil", "minervini", "livermore"], str(D["market_kill"]))
    check("horizon = median of the supporters' stated horizons", isinstance(g["horizon_sessions"], int) and g["horizon_sessions"] == 14, str(g["horizon_sessions"]))
    check("the measurement carries the ACT_NOW vs WAIT split per name", D["measurement"]["act_now_vs_wait"] == {"GNW": {"act_now": 4, "wait": 3}, "MFG": {"act_now": 2, "wait": 2}})
    # variant: GNW falls to 3 SUPPORT -> NOT_SLATED; MFG gains raschke's ACT_NOW -> 3 vs 2 ADVANCE, modal by majority
    v2 = os.path.join(d, "forms", "tier2_v2"); os.makedirs(v2, exist_ok=True)
    for v in DEC:
        f = json.load(open(os.path.join(P["tier2"], f"{v}.json")))
        for x in f["decisions"]:
            if x["ticker"] == "GNW" and v not in ("oneil", "minervini", "raschke"):
                x.update({"stance": "OPPOSE", "timing": None, "trigger": None})
            if x["ticker"] == "MFG" and v == "raschke":
                x.update({"stance": "SUPPORT", "timing": "ACT_NOW", "trigger": {"word": "h1_close_above:bar_high", "tf": "H1", "plain": "hourly close over the high"}})
        json.dump(f, open(os.path.join(v2, f"{v}.json"), "w"))
    exp = json.load(open(fx("export.json")))
    for r in exp["daily_list"]:
        if r["ticker"] == "MFG": r["held"] = True
    ex2 = os.path.join(d, "export_mfg_held.json"); json.dump(exp, open(ex2, "w"))
    out2 = os.path.join(d, "decision_v2.json")
    rc, log = run([PIPE, "decide-timing", "--tier2", v2, "--funnel", P["funnel"], "--phase4", p4, "--export", ex2, "--date", "2026-11-02", "--out", out2])
    check("decide-timing (variant) exits clean", rc == 0, log[-300:])
    if rc == 0:
        D2 = json.load(open(out2))
        check("fewer than 4 SUPPORT -> NOT_SLATED, no trigger", D2["names"]["GNW"]["proposal"] == "NOT_SLATED" and D2["names"]["GNW"]["trigger"] is None, str(D2["names"]["GNW"]))
        check("ACT_NOW 3 > WAIT 2 -> ADVANCE on the majority trigger", D2["names"]["MFG"]["proposal"] == "ADVANCE"
              and (D2["names"]["MFG"]["trigger"]["word"], D2["names"]["MFG"]["trigger"]["seats"]) == ("h1_close_above:bar_high", ["oneil", "minervini", "raschke"]), str(D2["names"]["MFG"]))
        check("a held name is counted on the ADD question and carries the hold line (modal wrong_if of its supporters)",
              D2["names"]["MFG"]["held"] and D2["names"]["MFG"]["question"] == "ADD"
              and D2["names"]["MFG"]["hold_line"]["plain"] == "close back under the 20-day average", str(D2["names"]["MFG"].get("hold_line")))
    # a hand-edited funnel.json (BBY slipped into the survivors) is refused: the tier-2 forms never decided it
    hf = json.load(open(P["funnel"])); hf["survivors"].append("BBY"); hfp = os.path.join(d, "funnel_edited.json"); json.dump(hf, open(hfp, "w"))
    rc, log = run([PIPE, "decide-timing", "--tier2", P["tier2"], "--funnel", hfp, "--phase4", p4, "--date", "2026-11-02", "--out", os.path.join(d, "x.json")])
    check("decide-timing refuses a funnel survivor no tier-2 form decided (a hand-edited funnel.json)", rc != 0 and "must decide exactly the survivors" in log, log[-300:])
    miss = os.path.join(d, "forms", "tier2_miss"); shutil.copytree(P["tier2"], miss)
    g = json.load(open(os.path.join(miss, "seow.json"))); g["decisions"] = g["decisions"][:1]; json.dump(g, open(os.path.join(miss, "seow.json"), "w"))
    rc, log = run([PIPE, "decide-timing", "--tier2", miss, "--funnel", P["funnel"], "--phase4", p4, "--date", "2026-11-02", "--out", os.path.join(d, "x.json")])
    check("decide-timing refuses a tier-2 form that misses a survivor", rc != 0 and "seow" in log and "MFG" in log, log[-300:])
    # --reroute: an absent reviewer's claims move to the next eligible seats; nobody else's routing changes
    rr = os.path.join(d, "claims_rr.json"); shutil.copy(P["claims"], rr)
    rc, log = run([PIPE, "claims", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--date", "2026-11-02", "--out", rr,
                   "--packets-dir", os.path.join(d, "cp_rr"), "--reroute", "wyckoff"])
    check("claims --reroute exits clean", rc == 0, log[-300:])
    if rc == 0:
        R = json.load(open(rr)); rc_ = [c for n in R["names"].values() for c in n["claims"]]
        before = {c["claim_id"]: c["reviewers"] for _, c in allc}
        check("the absent seat is off every claim and still two reviewers each, never the author or its family",
              all("wyckoff" not in c["reviewers"] and len(c["reviewers"]) == 2 and c["author"] not in c["reviewers"]
                  and all(FAMILY[r] != FAMILY[c["author"]] for r in c["reviewers"]) for c in rc_ if c["author"] != "wyckoff"), str([(c["claim_id"], c["reviewers"]) for c in rc_]))
        check("claims the absent seat did not review keep their reviewers", all(c["reviewers"] == before[c["claim_id"]] for c in rc_ if "wyckoff" not in before[c["claim_id"]]))
        check("the absent seat is declared and has no packet", R["reviewers_absent"] == ["wyckoff"] and not os.path.exists(os.path.join(d, "cp_rr", "wyckoff.json")))


def test_multi_timeframe_grid_is_required(td):
    """R39 (PM 2026-11-02). The weekly / daily / 1-hour grid is required on every tier-1 ruling and every tier-2
    trigger; the vote packet, the claims board and the tier-2 packets carry it; a name the bars do not serve says
    MTF NOT SERVED (declared), never a neutral reading."""
    d, p4, P = _funnel_chain(td, "mtf")
    if P["claims_log"][0] != 0:
        check("claims exits clean", False, P["claims_log"][1][-300:]); return
    B = json.load(open(P["claims"]))
    check("the claims board carries each name's grid", B["names"]["GNW"]["mtf"]["served"] is True and "W" in B["names"]["GNW"]["mtf"])
    check("a name the bars do not serve is declared NOT served, with the reason",
          B["names"]["VRNS"]["mtf"] == {"served": False, "reason": "FMP returned no 1-hour bars"}, str(B["names"]["VRNS"]["mtf"]))
    t2 = json.load(open(os.path.join(P["t2p"], "seow.json")))
    check("every tier-2 survivor carries its grid", all(s["mtf"].get("served") for s in t2["survivors"]))
    f = _cross_form(B, "seow"); del f["rulings"][0]["tf"]["H1"]
    rc, log = _validate(d, f, "cross_noh1", "--kind", "cross", "--claims", P["claims"])
    check("a cross ruling missing tf.H1 is REJECTED", rc != 0 and "missing H1" in log, log[-300:])
    f = _cross_form(B, "seow"); f["rulings"][0]["tf"] = "daily looks fine"
    rc, log = _validate(d, f, "cross_tfstr", "--kind", "cross", "--claims", P["claims"])
    check("a cross ruling whose tf is not the grid is REJECTED", rc != 0 and "W / D / H1 grid" in log, log[-300:])
    t2f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); del t2f["decisions"][0]["trigger"]["tf"]
    rc, log = _validate(d, t2f, "t2_notf", "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    check("a tier-2 SUPPORT trigger without its timeframe is REJECTED", rc != 0 and "trigger.tf" in log, log[-300:])
    t2f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); t2f["decisions"][0]["trigger"]["tf"] = "1H"
    rc, log = _validate(d, t2f, "t2_badtf", "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    check("a timeframe outside W / D / H1 is REJECTED", rc != 0 and "trigger.tf" in log, log[-300:])
    # the vote packet
    out = os.path.join(td, "vp_mtf.txt")
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--mtf", fx("mtf.json"),
                   "--run-id", "t", "--out", out])
    check("r2digest runs with --mtf", rc == 0, log[-300:])
    if rc != 0: return
    L = open(out).read().splitlines()
    def after_elder(t):
        i = next(i for i, l in enumerate(L) if l.startswith(f"### {t} "))
        j = next(j for j in range(i, len(L)) if L[j].startswith("  elder "))
        return L[j + 1]
    check("a served name prints its W / D / H1 line right after the elder line",
          after_elder("VLO") == "  MTF: W above rising EMA21 | D inside bar under the pivot | H1 holding the morning low", after_elder("VLO"))
    check("a name mtf.json declares unserved prints MTF NOT SERVED (declared)", after_elder("MPC") == "  MTF: NOT SERVED (declared)", after_elder("MPC"))
    check("a name absent from mtf.json prints MTF NOT SERVED too -- never a neutral reading", after_elder("SLDE") == "  MTF: NOT SERVED (declared)", after_elder("SLDE"))
    check("every room name carries exactly one MTF line", sum(1 for l in L if l.startswith("  MTF: ")) == len(json.load(open(fx("phase4.json")))["deliberation_set"]))
    out0 = os.path.join(td, "vp_nomtf.txt")
    run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
         "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--run-id", "t", "--out", out0])
    check("without --mtf the packet is unchanged (no MTF line)", os.path.exists(out0) and "MTF:" not in open(out0).read())
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--mtf", os.path.join(td, "nope.json"),
                   "--run-id", "t", "--out", os.path.join(td, "vp_gone.txt")])
    check("a missing mtf.json declares every name NOT SERVED", rc == 0 and open(os.path.join(td, "vp_gone.txt")).read().count("MTF: NOT SERVED (declared)") == 20)
    run_yaml = open(os.path.join(HERE, "..", "RUN.yaml")).read()
    check("the VOTE packet in RUN.yaml passes --mtf", "--mtf mtf.json --out VOTE_PACKET.txt" in run_yaml)


def test_mtf_build_from_real_bars_prints_the_grid_in_the_packet(td):
    """3 Nov 2026 defect (conductor): mtf.py build wrote only a name-level `summary`, but r2digest / claims / pair
    read the summary of each FRAME, so with real bars every name printed 'MTF: W not served | D not served | H1 not
    served'. The old test read a hand-written fixture that already had per-frame summaries, and the dry run had no
    bars at all. This builds mtf.json from SYNTHETIC BARS through the real tool, then runs the real r2digest."""
    import datetime as _dt
    run_date = "2026-11-02"
    def sessions(n, end=run_date):
        d, out = _dt.date.fromisoformat(end), []
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d.isoformat())
            d -= _dt.timedelta(days=1)
        return sorted(out)
    def bar(date, i, vol=1000):
        c = 100 + i * 0.3 + (i % 5) * 0.1
        return {"date": date, "open": round(c - 0.1, 4), "high": round(c + 0.5, 4), "low": round(c - 0.5, 4),
                "close": round(c, 4), "volume": vol}
    daily = [bar(d, i) for i, d in enumerate(sessions(300))]
    h1, m15, k = [], [], 0
    for day in sessions(10):
        for hh in range(7):
            mins = 9 * 60 + 30 + hh * 60
            h1.append(bar(f"{day} {mins // 60:02d}:{mins % 60:02d}:00", k)); k += 1
        for q in range(26):                                   # 09:30 ... 15:45 in 15-minute bars
            mins = 9 * 60 + 30 + q * 15
            m15.append(bar(f"{day} {mins // 60:02d}:{mins % 60:02d}:00", k, vol=100 + q)); k += 1
    bars = os.path.join(td, "mtf_bars_real"); os.makedirs(bars, exist_ok=True)
    json.dump({"daily": daily, "h1": h1}, open(os.path.join(bars, "VLO.json"), "w"))
    json.dump({"daily": daily, "m15": m15}, open(os.path.join(bars, "GNW.json"), "w"))     # no h1: rolled up by code
    json.dump({"daily": daily}, open(os.path.join(bars, "BBY.json"), "w"))                 # no hourly bars at all: H1 is a gap
    old_daily = [bar(d, i) for i, d in enumerate(sessions(300, end="2026-10-01"))]         # stale daily, fresh hourly
    json.dump({"daily": old_daily, "h1": h1}, open(os.path.join(bars, "MFG.json"), "w"))
    out = os.path.join(td, "mtf_real.json")
    rc, log = run([os.path.join(TOOLS, "mtf.py"), "build", "--bars", bars, "--phase4", fx("phase4.json"),
                   "--export", fx("export.json"), "--date", run_date, "--out", out])
    check("mtf.py build runs on synthetic bars", rc == 0, log[-300:])
    if rc != 0: return
    M = json.load(open(out))["names"]
    for t in ("VLO", "GNW"):
        check(f"{t}: all three frames are served", M[t]["served"] is True and M[t]["frames_served"] == ["W", "D", "H1"], str(M[t].get("reason")))
        for tf in ("W", "D", "H1"):
            sm = M[t][tf].get("summary")
            check(f"{t} {tf}: the frame carries its own summary, without the label", bool(sm) and not sm.startswith(f"{tf}:"), str(sm))
    check("the joined name-level summary keeps the labels", M["VLO"]["summary"].startswith("W: ") and " | D: " in M["VLO"]["summary"] and " | H1: " in M["VLO"]["summary"], M["VLO"]["summary"])
    check("a name with no bars file is declared NOT SERVED, with a summary on every frame", M["MPC"]["served"] is False and all(M["MPC"][tf].get("summary") for tf in ("W", "D", "H1")))
    # PM 2026-11-03: a name missing one timeframe SHOWS the others, the gap labelled -- never wholly hidden, never invented
    check("BBY (no hourly bars): served with a gap, not complete", M["BBY"]["served"] is True and M["BBY"]["complete"] is False and M["BBY"]["gaps"] == ["H1"], str(M["BBY"].get("gaps")))
    check("MFG (stale daily): W and D are gaps, H1 is served", M["MFG"]["gaps"] == ["W", "D"] and M["MFG"]["frames_served"] == ["H1"], str(M["MFG"].get("gaps")))
    check("the build counts complete / partial / not served", json.load(open(out))["measurement"]["partial_names"] == ["BBY", "MFG"], str(json.load(open(out))["measurement"]))
    # the 15-minute roll-up: exact, :30-anchored, the last bucket is the 30-minute close
    sess = sessions(10)[-1]
    sys.path.insert(0, TOOLS)
    import importlib; mtf = importlib.import_module("mtf")
    day15 = [b for b in m15 if b["date"].startswith(sess)]
    hb, dropped = mtf.rollup_hourly(mtf._clean(day15))
    check("26 fifteen-minute bars roll to 7 :30-anchored hourly bars", [b["date"][11:] for b in hb] == ["09:30:00", "10:30:00", "11:30:00", "12:30:00", "13:30:00", "14:30:00", "15:30:00"] and dropped == 0, str([b["date"] for b in hb]))
    first = day15[:4]
    check("a rolled hour is open-first / high-max / low-min / close-last / volume-sum",
          hb[0]["open"] == first[0]["open"] and hb[0]["close"] == first[-1]["close"] and hb[0]["high"] == max(x["high"] for x in first)
          and hb[0]["low"] == min(x["low"] for x in first) and hb[0]["volume"] == sum(x["volume"] for x in first), str(hb[0]))
    check("the 15:30 bucket is the 30-minute close (2 bars)", hb[-1]["volume"] == day15[-1]["volume"] + day15[-2]["volume"])
    thin, d2 = mtf.rollup_hourly(mtf._clean(day15[:5] + [dict(day15[8], date=f"{sess} 17:00:00"), dict(day15[9], date=f"{sess} 08:00:00")]))
    check("a one-bar bucket and out-of-session bars are dropped and counted, never passed off as an hour", len(thin) == 1 and d2 == 3, f"{len(thin)} bars, {d2} dropped")
    # the real packet, from the real file
    vp = os.path.join(td, "vp_real.txt")
    rc, log = run([PIPE, "r2digest", "--export", fx("export.json"), "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--mtf", out,
                   "--run-id", "t", "--out", vp])
    check("r2digest runs on the built mtf.json", rc == 0, log[-300:])
    if rc != 0: return
    L = open(vp).read().splitlines()
    def mtf_line(t):
        i = next(i for i, l in enumerate(L) if l.startswith(f"### {t} "))
        return next(l for l in L[i:] if l.startswith("  MTF: "))
    for t in ("VLO", "GNW"):
        ln = mtf_line(t)
        check(f"{t}: the packet prints the grid -- W, D and H1 each with a reading", ln.startswith("  MTF: W ") and " | D " in ln and " | H1 " in ln and "not served" not in ln.lower(), ln)
        check(f"{t}: the labels are not doubled", not any(x in ln for x in ("W W:", "D D:", "H1 H1:", "W: ", "D: ", "H1: ")), ln)
    check("a name with no bars still prints NOT SERVED (declared)", mtf_line("MPC") == "  MTF: NOT SERVED (declared)", mtf_line("MPC"))
    ln = mtf_line("BBY")
    check("BBY: W and D print their readings, H1 is labelled a GAP with its reason",
          ln.startswith("  MTF: W ") and " | D " in ln and ln.endswith("| H1 GAP (no 1-hour bars)") and "NOT SERVED" not in ln, ln)
    ln = mtf_line("MFG")
    check("MFG: W and D are labelled GAPs (stale), H1 prints its reading", ln.startswith("  MTF: W GAP (") and " | D GAP (" in ln and " | H1 " in ln and "H1 GAP" not in ln, ln)


def _slate_from(decision, tickers=None):
    D = json.load(open(decision))
    tk = []
    for t, n in D["names"].items():
        if n["proposal"] == "NOT_SLATED" or (tickers and t not in tickers):
            continue
        tg = n["trigger"]
        tk.append({"ticker": t, "verdict": n["proposal"], "entry_trigger": tg["plain"],
                   "trigger": {"word": tg["word"], "tf": tg["tf"], "plain": tg["plain"]}, "wrong_if": "close back inside the base",
                   "horizon_sessions": n["horizon_sessions"] or 10, "why_agreed": "oneil, wyckoff: the creek was crossed on volume",
                   "dissent": [], "timing_count": dict(n["counts"])})
    return {"date": "2026-11-02", "chair": "chair", "tickets": tk, "market_kill": D["market_kill"]}


def test_one_trigger_per_ticket_and_market_kill(td):
    """R40 (PM 2026-11-02). A ticket carries ONE trigger -- the one decide-timing fixed -- and the slate carries ONE
    market kill line. The registrar REJECTS a ticket whose verdict or trigger differs from decision.json, a ticket
    for a name code did not slate, and a market_kill that is not decision.json's. A trigger names a FIELD level."""
    d, p4, P = _funnel_chain(td, "r40")
    if not os.path.exists(P.get("decision", "")):
        check("the funnel chain reaches decision.json", False, str(P.get("timing_log"))[-300:]); return
    S = _slate_from(P["decision"])
    sv = lambda s, tag, *x: _validate(d, s, tag, "--kind", "slate", "--phase4", p4, "--decision", P["decision"], *x)
    rc, log = sv(S, "slate_ok")
    check("a slate copied from decision.json validates", rc == 0, log[-400:])
    b = json.loads(json.dumps(S)); b["tickets"][0]["trigger"]["word"] = "h1_close_above:bar_high"; b["tickets"][0]["trigger"]["tf"] = "H1"
    rc, log = sv(b, "slate_trig")
    check("a ticket whose trigger differs from decision.json is REJECTED", rc != 0 and "differs from decision.json" in log, log[-300:])
    b = json.loads(json.dumps(S)); b["tickets"][1]["verdict"] = "ADVANCE"
    rc, log = sv(b, "slate_verdict")
    check("a ticket whose verdict differs from decision.json is REJECTED (MFG is a WATCH by the tie rule)", rc != 0 and "verdict ADVANCE differs" in log, log[-300:])
    b = json.loads(json.dumps(S)); b["market_kill"] = dict(S["market_kill"], plain="QQQ close_below ma_50", symbol="QQQ", level=None)
    rc, log = sv(b, "slate_mk")
    check("a market_kill that is not decision.json's is REJECTED", rc != 0 and "market_kill" in log, log[-300:])
    b = json.loads(json.dumps(S)); b["market_kill"] = None
    rc, log = sv(b, "slate_mk_null")
    check("dropping the market_kill decision.json carries is REJECTED", rc != 0 and "market_kill" in log, log[-300:])
    b = json.loads(json.dumps(S)); b["tickets"].append(dict(b["tickets"][0], ticker="BBY"))
    rc, log = sv(b, "slate_dropped")
    check("a ticket for a name tier 1 DROPPED is REJECTED", rc != 0 and "not a tier-1 survivor" in log, log[-300:])
    b = json.loads(json.dumps(S)); b["tickets"] = b["tickets"][:1]
    rc, log = sv(b, "slate_missing")
    check("a slated name left off a slate under the 15 cap is REJECTED", rc != 0 and "missing from the slate" in log, log[-300:])
    # a NOT_SLATED name (variant decision: GNW at 3 SUPPORT)
    D = json.load(open(P["decision"])); D["names"]["GNW"].update({"proposal": "NOT_SLATED", "trigger": None, "why": "3 SUPPORT < 4 of 7"})
    dn = os.path.join(d, "decision_ns.json"); json.dump(D, open(dn, "w"))
    rc, log = _validate(d, S, "slate_ns", "--kind", "slate", "--phase4", p4, "--decision", dn)
    check("a ticket for a name decision.json did NOT slate is REJECTED", rc != 0 and "did NOT slate" in log, log[-300:])
    # no --decision: a slate dated from 2026-11-02 still needs the trigger and the market_kill; history validates as filed
    b = json.loads(json.dumps(S)); del b["tickets"][0]["trigger"]
    rc, log = _validate(d, b, "slate_notrig", "--kind", "slate", "--phase4", p4)
    check("a 2026-11-02 ticket without its trigger is REJECTED even without --decision", rc != 0 and "missing trigger" in log, log[-300:])
    old = {"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY", "WATCH")]}
    rc, log = _validate(d, old, "slate_old", "--kind", "slate", "--phase4", p4)
    check("a slate dated before 2026-11-02 validates as filed (no trigger, no market_kill)", rc == 0, log[-300:])
    # the trigger word names a FIELD level, never a number (D123 grammar, reused)
    def t2(word):
        f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); f["decisions"][0]["trigger"]["word"] = word
        return _validate(d, f, "t2_" + re.sub(r"\W", "_", word), "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    rc, log = t2("h1_close_above:644.24")
    check("a trigger with a bare number as its level is REJECTED at tier 2", rc != 0 and "never a number" in log, log[-300:])
    check("h1_close_above:bar_high is accepted", t2("h1_close_above:bar_high")[0] == 0)
    check("in_zone:ma_20 is accepted", t2("in_zone:ma_20")[0] == 0)
    rc, log = t2("rs_today_gt_spy")
    check("a word with no price level is not a trigger", rc != 0 and "names no price level" in log, log[-300:])
    rc, log = t2("reclaim:ma_20")
    check("a seat's own method limits apply to its trigger (oneil may not buy a reclaim)", rc != 0 and "outside this seat's own method" in log, log[-300:])
    f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); f["decisions"][0]["timing"] = None
    rc, log = _validate(d, f, "t2_notiming", "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    check("SUPPORT without ACT_NOW / WAIT is REJECTED", rc != 0 and "timing" in log, log[-300:])
    f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); f["answers"] = []
    rc, log = _validate(d, f, "t2_noanswer", "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    check("an author who does not answer its refuter is REJECTED", rc != 0 and "no answer to pair" in log, log[-300:])
    f = json.load(open(os.path.join(P["tier2"], "oneil.json"))); f["decisions"][0]["wrong_if"] = "the bracket is invalid so reject it"
    rc, log = _validate(d, f, "t2_bracket", "--kind", "tier2", "--pairs", P["pairs"], "--funnel", P["funnel"])
    check("a bracket used as the disqualifier in wrong_if is REJECTED (R1)", rc != 0 and "R1 VIOLATION" in log, log[-300:])
    # the record: ratify-count reads the cross and tier-2 forms beside the ratifications
    sp = os.path.join(d, "slate.json"); json.dump(S, open(sp, "w"))
    for v in DEC:
        _ratify(d, "ratify", v, {"GNW": "AGREE", "MFG": "AGREE"})
    rec = os.path.join(d, "committee_record.json")
    rc, log = run([PIPE, "ratify-count", "--slate", sp, "--ratifications", os.path.join(d, "forms", "ratify"), "--board", P["board"],
                   "--cross", P["cross"], "--tier2", P["tier2"], "--phase4", p4, "--date", "2026-11-02", "--out", os.path.join(d, "consensus.json"), "--record", rec])
    check("ratify-count runs with --cross and --tier2", rc == 0, log[-300:])
    if rc == 0:
        R = {(r["voice"], r["ticker"]): r for r in json.load(open(rec))["rows"]}
        r = R[("raschke", "MFG")]
        check("the record carries the seat's cross rulings and its changed mind from them",
              r["cross_rulings"] and all(set(x) == {"claim_id", "ruling"} for x in r["cross_rulings"]) and r["changed_mind"]
              and "the weekly base holds above EMA21" in r["what_moved_me"] and r["stance_after_cross"] == "SUPPORT", str(r))
        o = R[("oneil", "GNW")]
        check("the record carries the tier-2 stance, timing and trigger", (o["tier2_stance"], o["tier2_timing"], o["tier2_trigger"]["word"]) == ("SUPPORT", "ACT_NOW", "h1_close_above:bar_high"), str(o))
        p0 = json.load(open(P["pairs"]))["pairs"][0]
        a = R[(p0["author"], "MFG")]
        check("the record carries the pair answers a seat gave", a["answers_given"] == [p0["pair_id"]], str(a["answers_given"]))
        C = {c["ticker"]: c for c in json.load(open(os.path.join(d, "consensus.json")))}
        check("the ONE trigger rides into consensus.json", C["GNW"]["trigger"]["word"] == "close_above:pivot_high")


def test_valen_flags_leave_ticket_selection(td):
    """R41 (PM 2026-11-02): 'Valen risk do not need to appear at ticket selection level.' The vote packet carries no
    RISK (Valen) block and no no-buy / parabolic text; the cards carry no no-buy flag. Valen stays as the weather."""
    ex = json.load(open(fx("export.json"))); p4 = json.load(open(fx("phase4.json")))
    t0 = p4["deliberation_set"][0]
    for row in ex["daily_list"]:
        if row["ticker"] == t0:
            row["setups"] = [{"setup": "Parabolic", "status": "WATCH", "checks": [{"result": "PASS"}]},
                             {"setup": "VCP", "status": "READY", "checks": [{"result": "PASS"}, {"result": "FAIL"}]}]
    exp = os.path.join(td, "r41_export.json"); json.dump(ex, open(exp, "w"))
    val = os.path.join(td, "r41_valen.json")
    json.dump({"read_me_first": {"as_of": "2026-11-02", "so_what": "half size"}, "stance": {"word": "NEUTRAL"}, "regime": "CHOP",
               "selection": {"no_buy_list": [{"ticker": t0, "flags": [{"label": "4.2 ATR extended"}]}]}}, open(val, "w"))
    out = os.path.join(td, "r41_packet.txt")
    rc, log = run([PIPE, "r2digest", "--export", exp, "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"), "--valen", val, "--run-id", "t", "--out", out])
    check("r2digest runs with a Valen file carrying a no-buy list", rc == 0, log[-300:])
    if rc != 0: return
    txt = open(out).read()
    check("no RISK (Valen block in the vote packet", "RISK (Valen" not in txt)
    check("no no-buy / NO-BUY / parabolic text anywhere in the vote packet",
          not any(w in txt for w in ("no-buy", "NO-BUY", "arabolic", "4.2 ATR extended")), [l for l in txt.splitlines() if "arabolic" in l or "no-buy" in l.lower()][:3])
    check("Valen stays as the weather", "stance NEUTRAL" in txt and "VCP READY (1/2)" in txt)
    # the CODE of the cards (comments stripped: a comment saying the list is no longer read is not a flag)
    code = [l.split("#", 1)[0] for l in open(os.path.join(TOOLS, "pma_cards.py"), encoding="utf-8").read().splitlines()]
    hits = [l.strip() for l in code if any(w in l for w in ("no-buy", "NO-BUY", "no_buy"))]
    check("pma_cards.py carries no no-buy card flag (no code reads no_buy_list or prints a no-buy line)", not hits, str(hits[:3]))
    check("R41 is on the record and R37 is superseded", "id: R41" in open(os.path.join(HERE, "..", "RULINGS.yaml")).read()
          and "superseded_by_R41" in open(os.path.join(HERE, "..", "RULINGS.yaml")).read())


def test_committee_position_counts_the_median_and_never_invents_a_rationale(td):
    """R42 (PM 2026-11-03): conviction = median_low of the deciders' 1-5; fewer than 4 scores = no conviction;
    no rationale filed = a declared gap; the Cards block prints exactly that."""
    d = os.path.join(td, "r42"); os.makedirs(os.path.join(d, "ratify"))
    json.dump([{"ticker": "AAA", "status": "AGREED", "verdict": "ADVANCE"}, {"ticker": "BBB", "status": "AGREED", "verdict": "ADVANCE"}],
              open(os.path.join(d, "consensus.json"), "w"))
    voices = ["oneil", "minervini", "livermore", "elder-lens", "seow"]
    scores = {"AAA": [5, 4, 4, 2, 1], "BBB": [3, 3, 4]}            # AAA median 4; BBB only 3 scores -> none
    for i, v in enumerate(voices):
        tk = [{"ticker": t, "conviction": sc[i]} for t, sc in scores.items() if i < len(sc)]
        json.dump({"voice": v, "tickets": tk}, open(os.path.join(d, "ratify", v + ".json"), "w"))
    out = os.path.join(d, "committee_position.json")
    rc, o = run([PIPE, "committee-position", "--consensus", os.path.join(d, "consensus.json"), "--ratifications", os.path.join(d, "ratify"),
                 "--draft", os.path.join(d, "none1.json"), "--final", os.path.join(d, "none2.json"), "--adopts", os.path.join(d, "none3"),
                 "--run-dir", d, "--record", os.path.join(d, "none4.json"), "--date", "2026-11-04", "--out", out])
    check("committee-position runs", rc == 0, o)
    P = json.load(open(out))["tickets"] if os.path.exists(out) else {}
    check("conviction is the median of the five scores", P.get("AAA", {}).get("committee_conviction") == 4, str(P.get("AAA")))
    check("fewer than 4 scores gives no conviction, with the reason", P.get("BBB", {}).get("committee_conviction") is None
          and any("fewer than 4" in g for g in P["BBB"]["gaps"]), str(P.get("BBB")))
    check("no rationale filed is a declared gap, not invented text", P["AAA"]["why"] == [] and any("no committee rationale" in g for g in P["AAA"]["gaps"]))
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards
    importlib.reload(pma_cards)
    on = pma_cards._committee_block(P["AAA"], True)
    check("the Cards block shows 'Conviction 4 of 5'", "Conviction 4 of 5" in on, on)
    check("no final rationale is declared in the file and in the log", any("DRAFT" in x or "NOT FILED" in x for x in json.load(open(out)).get("declared", [])) and "R42 DECLARED" in o, o)
    banner = pma_cards._rationale_banner(json.load(open(out)), True)
    check("the Cards declare a missing final at the top ('NOT FILED' / 'DRAFT, not adopted')", "NOT FILED" in banner or "DRAFT, not adopted" in banner, banner)
    check("a draft-stage rationale is labelled 'DRAFT, not adopted' on the ticket", "DRAFT, not adopted" in pma_cards._committee_block({"committee_conviction": 3, "rationale_stage": "draft", "why": [{"text": "x"}]}, True))
    check("a final rationale carries no banner", pma_cards._rationale_banner({"tickets": {"A": {"rationale_stage": "final"}}}, True) == "")
    ry = open(os.path.join(HERE, "..", "RUN.yaml"), encoding="utf-8").read()
    check("RUN.yaml carries the one R42 switch and the retry cap", "committee_position: on" in ry and "r42_respawns: 1" in ry)
    check("the Cards render is handed the committee position file", "pma_cards.py render --text cards_text.json --position committee_position.json" in ry)
    check("a run with no position file prints no block", pma_cards._committee_block(None, False) == "")
    check("a missing ticket on a post-R42 run is a declared gap", "declared gap" in pma_cards._committee_block(None, True))


def test_a_rerun_has_its_own_identity_and_cannot_publish_live(td):
    """PM 2026-11-03: a RERUN of the same date has its own run id and dir, git_sync refuses any other destination, and
    check.py chain FAILs a rerun whose publish receipt names a path outside its own dir."""
    d = os.path.join(td, "rr"); os.makedirs(d)
    m = os.path.join(d, "run_manifest.json")
    rc, o = run([REG, "--manifest", m, "init", "--date", "2026-11-03", "--rerun", "r2"])
    M = json.load(open(m)) if os.path.exists(m) else {}
    check("init --rerun r2 writes pma-2026-11-03-r2 and the r2 run dir", rc == 0 and M.get("run_id") == "pma-2026-11-03-r2"
          and M["rerun"]["run_dir"] == "aegis/output/pma/run/2026-11-03-r2" and M["rerun"]["publishes_live"] is False, o + str(M))
    rc, _ = run([REG, "--manifest", os.path.join(d, "bad.json"), "init", "--date", "2026-11-03", "--rerun", "x"])
    check("a malformed rerun suffix is refused", rc == 2)
    rc, _ = run([REG, "--manifest", os.path.join(d, "live.json"), "init", "--date", "2026-11-03"])
    check("a normal init is unchanged: pma-<date>, no rerun key", json.load(open(os.path.join(d, "live.json"))).get("run_id") == "pma-2026-11-03"
          and "rerun" not in json.load(open(os.path.join(d, "live.json"))))
    # git_sync guard, run in the dir holding the rerun manifest
    gs = os.path.join(TOOLS, "git_sync.py")
    for dest in ("aegis/output/pma", "aegis/output/pma/run/2026-11-03", None):
        args = [gs, "-m", "x", "--paths", "run_manifest.json", "--dry-run"] + (["--dest", dest] if dest else [])
        r = subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=d)
        check(f"git_sync refuses a rerun pushing to {dest}", r.returncode != 0 and "RERUN" in r.stdout and "REFUSED" in r.stdout, r.stdout[-300:] + r.stderr[-200:])
    r = subprocess.run([sys.executable, gs, "-m", "x", "--paths", "run_manifest.json", "--dest", "aegis/output/pma/run/2026-11-03-r2", "--dry-run"],
                       capture_output=True, text=True, cwd=d)
    check("git_sync lets the rerun push to its own dir (the guard does not refuse it)", "REFUSED: this is a RERUN" not in r.stdout, r.stdout[-300:])
    # the chain check
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_rr", os.path.join(HERE, "..", "..", "daily-check", "check.py"))
    C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
    rd = os.path.join(d, "aegis", "output", "pma", "run", "2026-11-03-r2"); os.makedirs(rd)
    shutil.copy(m, os.path.join(rd, "run_manifest.json"))
    json.dump({"pushed": ["aegis/output/pma/pma_levels.json"]}, open(os.path.join(rd, "publish_receipt.json"), "w"))
    f, n = C.check_chain(rd, "2026-11-03")
    check("a rerun receipt naming the LIVE levels file FAILs the chain", any("OUTSIDE" in x and "never publish live" in x for x in f), str(f)[:300])
    json.dump({"pushed": ["aegis/output/pma/run/2026-11-03-r2/pma_levels.json"]}, open(os.path.join(rd, "publish_receipt.json"), "w"))
    f, n = C.check_chain(rd, "2026-11-03")
    check("a rerun receipt inside its own dir is not flagged, and the note says NOT LIVE", not any("OUTSIDE" in x for x in f) and any("NOT LIVE" in x for x in n), str(f)[:200] + str(n)[:200])
    ry = open(os.path.join(HERE, "..", "RUN.yaml"), encoding="utf-8").read()
    check("RUN.yaml states the rerun rules (no live levels, scorecard log, inbox skipped)", "RERUN MODE" in ry and "INBOX-CLEAN is skipped" in ry and "scorecard_log.jsonl or scorecard/<date>.md" in ry)


def test_the_handoff_gate_fails_a_stale_breadth_we_caused_and_a_missing_legs_table(td):
    """PM 2026-11-04: the data handoff gate must FAIL on OUR_BUDGET / SOURCE_DOWN legs and on a Valen file with no legs table."""
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("chk_legs", os.path.join(HERE, "..", "..", "daily-check", "check.py")); ck = _iu.module_from_spec(sp); sp.loader.exec_module(ck)
    f, n = ck.check_macro_legs({"data_freshness": {"legs_table": [{"leg": "breadth_whole_market", "as_of": "x", "expected": "y", "reason": "OUR_BUDGET", "detail": "37%"}]}}, None)
    check("the gate FAILs breadth that is behind because of our own budget", len(f) == 1 and "OUR_BUDGET" in f[0], str(f))
    f, n = ck.check_macro_legs({"stance": {}}, None)
    check("the gate FAILs a Valen file with no legs table", len(f) == 1 and "cannot be audited" in f[0], str(f))


def test_p2_cap_25_code_made_cut_verbatim_slate_quotes_and_amend_also(td):
    """P2 (conductor 2026-11-04): slate cap 25 with a code-made cut; why_agreed / wrong_if quotes must be a SUPPORT seat's
    verbatim words; cross and tier2 words are quotable; AMEND texts are attached verbatim by CODE (no MERGED ladder);
    market_kill never carries a stray number."""
    sys.path.insert(0, TOOLS)
    import importlib, registrar, pma_pipeline
    importlib.reload(registrar); importlib.reload(pma_pipeline)
    check("SLATE_CAP is 25", registrar.SLATE_CAP == 25)
    import re as _re, importlib.util as _iu
    cap_yaml = int(_re.search(r"^\s*slate_cap:\s*(\d+)", open(os.path.join(HERE, "..", "RUN.yaml"), encoding="utf-8").read(), _re.M).group(1))
    _sp = _iu.spec_from_file_location("chk_cap", os.path.join(HERE, "..", "..", "daily-check", "check.py")); _ck = _iu.module_from_spec(_sp); _sp.loader.exec_module(_ck)
    check("registrar, pma_pipeline and check.py all read the cap from RUN.yaml, so they cannot drift (4 Nov: ratify-count still said 15)",
          registrar.SLATE_CAP == pma_pipeline.SLATE_CAP == _ck.SLATE_CAP == cap_yaml == 25, f"{registrar.SLATE_CAP} {pma_pipeline.SLATE_CAP} {_ck.SLATE_CAP} {cap_yaml}")
    sch = json.load(open(os.path.join(HERE, "..", "contracts", "slate.schema.json")))
    check("slate.schema maxItems is 25", sch["properties"]["tickets"]["maxItems"] == 25)
    ry = open(os.path.join(HERE, "..", "RUN.yaml"), encoding="utf-8").read()
    check("RUN.yaml slate_cap is 25 and the SLATE step runs the code cut", "slate_cap: 25" in ry and "pma_pipeline.py slate-plan --decision decision.json --cap 25" in ry)
    # --- market_kill parse
    check("a range like '4-5 weeks' is never a level or a symbol", pma_pipeline._parse_void("Index distribution days reach 4-5 inside 4-5 weeks (C2): market gate fails, no buys (C1).") == (None, None, None))
    sym, wd, lv = pma_pipeline._parse_void("SPY close_below 750")
    check("a real market void still parses to symbol / word / level", (sym, wd, lv) == ("SPY", "close_below", 750.0), str((sym, wd, lv)))
    # --- slate-plan
    d = os.path.join(td, "p2"); os.makedirs(d)
    def nm(t, prop, sup, act): return {"ticker": t, "proposal": prop, "counts": {"support": sup, "act_now": act}}
    names = {"AAA": nm("AAA", "WATCH", 5, 2), "BBB": nm("BBB", "ADVANCE", 5, 3), "CCC": nm("CCC", "WATCH", 7, 1), "DDD": nm("DDD", "ADVANCE", 5, 3),
             "EEE": nm("EEE", "NOT_SLATED", 2, 0), "FFF": nm("FFF", "WATCH", 4, 0)}
    json.dump({"date": "2026-11-04", "names": names}, open(os.path.join(d, "decision.json"), "w"))
    rc, o = run([PIPE, "slate-plan", "--decision", os.path.join(d, "decision.json"), "--cap", "3", "--out", os.path.join(d, "slate_plan.json"), "--excluded", os.path.join(d, "slate_excluded.json")])
    P = json.load(open(os.path.join(d, "slate_plan.json"))); X = json.load(open(os.path.join(d, "slate_excluded.json")))
    check("the cut keeps the most SUPPORT, then ACT_NOW, then ADVANCE first, then A-Z", [r["ticker"] for r in P["keep"]] == ["CCC", "BBB", "DDD"], o + str(P["keep"]))
    check("the rest are excluded with a reason and a rank; NOT_SLATED is never a candidate", [r["ticker"] for r in X["excluded"]] == ["AAA", "FFF"] and all("over the cap of 3" in r["reason"] for r in X["excluded"]))
    errs = []
    form = {"tickets": [{"ticker": t} for t in ("CCC", "BBB", "AAA")]}
    registrar.validate_slate(form, None, None, None, P)  # must not raise
    e2, _ = registrar.validate_slate({"date": "2026-11-04", "chair": "chair", "tickets": [{"ticker": t} for t in ("CCC", "BBB", "AAA")]}, None, None, None, P)
    check("a slate that differs from the code-made plan is refused, naming both sides", any("differ from slate_plan.json" in x and "'DDD'" in x and "'AAA'" in x for x in e2), str(e2)[:300])
    # --- verbatim slate quotes
    rd = os.path.join(d, "run"); 
    for sub in ("forms/r2", "forms/cross", "forms/tier2", "forms/adopt", "forms/ratify"): os.makedirs(os.path.join(rd, sub))
    json.dump({"voice": "oneil", "votes": [{"ticker": "ZZZ", "stance": "OPPOSE", "reason": "Market gate fails so I stay OPPOSE on this name"}]}, open(os.path.join(rd, "forms/r2/oneil.json"), "w"))
    json.dump({"voice": "seow", "votes": [{"ticker": "ZZZ", "stance": "SUPPORT", "reason": "structure_shift ABOVE_STRUCTURE at the high, cmf 0.34"}]}, open(os.path.join(rd, "forms/r2/seow.json"), "w"))
    json.dump({"voice": "livermore", "rulings": [{"ticker": "ZZZ", "claim_id": "c1", "ruling": "CONFIRM", "stance_after": "SUPPORT", "evidence": "C5 met: W 9>21 HH/HL under the 20-wk high"}]}, open(os.path.join(rd, "forms/cross/livermore.json"), "w"))
    dec = {"names": {"ZZZ": {"seats": {"support": ["seow", "livermore"]}}}}
    def q(wa, wi="seow: \"cmf 0.34\""):
        e = []; registrar._slate_quotes({"tickets": [{"ticker": "ZZZ", "why_agreed": wa, "wrong_if": wi}]}, dec, rd, e); return e
    check("a verbatim supporter quote (with a '(confirm)' tag) passes", q('seow: "structure_shift ABOVE_STRUCTURE at the high" | livermore (confirm): "C5 met: W 9>21 HH/HL"') == [], str(q('seow: "structure_shift ABOVE_STRUCTURE at the high" | livermore (confirm): "C5 met: W 9>21 HH/HL"')))
    check("a quote from a seat that is NOT a SUPPORT seat is refused", any("not a SUPPORT seat" in x for x in q('oneil: "Market gate fails so I stay OPPOSE"')))
    check("a paraphrase is refused as not verbatim", any("NOT verbatim" in x for x in q('seow: "the structure looks great"')))
    check("a piece that is not  voice: \"quote\"  is refused", any("must read" in x for x in q("seow says it is strong")))
    dec["names"]["ZZZ"]["seats"]["support"].append("oneil")
    check("an opposer's line is refused even if the seat later counted as SUPPORT", any("not SUPPORT" in x and "OPPOSE" in x for x in q('oneil: "Market gate fails so I stay OPPOSE"')), str(q('oneil: "Market gate fails so I stay OPPOSE"')))
    # --- rationale: cross + tier2 sources; AMEND attached by code
    json.dump({"voice": "wyckoff", "decisions": [{"ticker": "ZZZ", "stance": "SUPPORT", "reason": "Spring held on rising volume"}]}, open(os.path.join(rd, "forms/tier2/wyckoff.json"), "w"))
    clause = lambda txt, v, f, fld: {"text": txt, "source": {"voice": v, "form": f, "field": fld}}
    draft = {"voice": "chair", "date": "2026-11-04", "stage": "draft", "tickets": [{"ticker": "ZZZ", "why": [
        clause("C5 met: W 9>21 HH/HL", "livermore", "cross", "evidence"), clause("Spring held on rising volume", "wyckoff", "tier2", "reason"),
        clause("structure_shift ABOVE_STRUCTURE at the high", "seow", "vote", "reason")], "would_change": []}]}
    e, _ = registrar.validate_rationale(draft, "draft", ["ZZZ"], rd)
    check("a rationale may quote cross and tier2 words", e == [], str(e))
    bad = json.loads(json.dumps(draft)); bad["tickets"][0]["why"][0]["text"] = "an invented claim"
    e, _ = registrar.validate_rationale(bad, "draft", ["ZZZ"], rd)
    check("a cross quote that is not verbatim is refused", any("NOT a verbatim quote" in x for x in e))
    amend = lambda v, t: {"voice": v, "date": "2026-11-04", "tickets": [{"ticker": "ZZZ", "answer": "AMEND", "text": t}]}
    json.dump(amend("seow", "Add that cmf is above 0.3"), open(os.path.join(rd, "forms/adopt/seow.json"), "w"))
    json.dump(amend("raschke", "x" * 880), open(os.path.join(rd, "forms/adopt/raschke.json"), "w"))
    json.dump(draft, open(os.path.join(rd, "rationale_draft.json"), "w"))
    rc, o = run([PIPE, "rationale-final", "--draft", os.path.join(rd, "rationale_draft.json"), "--run-dir", rd, "--out", os.path.join(rd, "rationale_final.json")])
    F = json.load(open(os.path.join(rd, "rationale_final.json")))
    t0 = F["tickets"][0]
    check("rationale-final attaches the AMEND text verbatim as `also` and sends what does not fit to the overflow", rc == 0 and t0["also"] == [{"voice": "seow", "text": "Add that cmf is above 0.3"}] and [x["voice"] for x in t0["also_overflow"]] == ["raschke"], o + str(t0)[:300])
    e, _ = registrar.validate_rationale(F, "final", ["ZZZ"], rd)
    check("the code-written final validates; a hand-edited `also` does not", e == [], str(e))
    F["tickets"][0]["also"] = [{"voice": "seow", "text": "something else"}]
    e, _ = registrar.validate_rationale(F, "final", ["ZZZ"], rd)
    check("a final whose `also` is not the code-attached AMEND texts is refused", any("code-attached" in x for x in e))
    import importlib as _il, pma_cards
    _il.reload(pma_cards)
    blk = pma_cards._committee_block({"committee_conviction": 4, "rationale_stage": "final", "why": [{"text": "x", "voice": "seow"}], "also": [{"voice": "seow", "text": "Add that cmf is above 0.3"}], "what_would_change_it": [], "minority_notes": []}, True)
    check("the Cards print 'Also (voice): ...'", "Also (seow):" in blk and "Add that cmf is above 0.3" in blk, blk)


def test_form_cap_scales_with_tickets_and_trigger_ties_are_stated(td):
    """P2 (conductor 2026-11-04): a 12-ticket rationale_final was 28KB and hit the 24KB essay-leak cap; with a 25-ticket slate every
    ticket-keyed form would. The cap scales per kind with the ticket count (per-field caps remain the real essay guard), and a
    trigger tie in decision.json carries the competing groups and the stated rule."""
    sys.path.insert(0, TOOLS)
    import importlib, registrar, pma_pipeline
    importlib.reload(registrar); importlib.reload(pma_pipeline)
    raw12 = json.dumps({"tickets": [{"ticker": f"T{i}"} for i in range(12)]}).encode()
    raw25 = json.dumps({"tickets": [{"ticker": f"T{i}"} for i in range(25)]}).encode()
    check("a 12-ticket rationale may be 100KB, a 25-ticket slate 69KB, but a vote form stays at 24KB",
          registrar.form_byte_cap("rationale", raw12) == 8000 * 12 + 4096 and registrar.form_byte_cap("slate", raw25) == 2600 * 25 + 4096
          and registrar.form_byte_cap("vote", raw25) == registrar.MAX_FORM_BYTES)
    check("the floor is the old 24KB for a tiny form", registrar.form_byte_cap("ratify", b'{"tickets": []}') == registrar.MAX_FORM_BYTES)
    d = os.path.join(td, "capform"); os.makedirs(d)
    big = {"voice": "chair", "date": "2026-11-04", "stage": "draft", "tickets": [{"ticker": f"T{i}", "why": [], "would_change": [], "pad": "x" * 2400} for i in range(12)]}
    json.dump(big, open(os.path.join(d, "r.json"), "w"))
    rc, o = run([REG, "validate", "--file", os.path.join(d, "r.json"), "--kind", "rationale", "--stage", "draft", "--run-dir", d])
    check("a 29KB 12-ticket rationale is no longer refused for size (it may be refused for content)", "essay leak; forms not essays" not in o, o[-300:])
    check("a trigger tie names the competing groups and the rule", "TRIGGER_TIE_RULE" in open(PIPE).read() and "tie_broken" in open(PIPE).read())
    groups = collections_ordered = {("h1_close_above:bar_high", "H1"): ["oneil", "seow"], ("close_above:ma_20", "D"): ["minervini", "wyckoff"]}
    win = pma_pipeline._modal(groups, {"oneil": 5, "seow": 3, "minervini": 4, "wyckoff": 2})
    check("the tie is broken by the higher blind conviction in the group, then decider order", win[0] == ("h1_close_above:bar_high", "H1"), str(win))


def test_rationale_final_drops_clauses_sourced_from_a_dissenting_seat(td):
    """4 Nov rerun: the draft legitimately quoted an objector's would_clear for 'what would change it'; that seat then answered
    DISSENT at ADOPT, and the final-stage validator refused 25 clauses. rationale-final (code) now drops every why / would_change
    clause sourced from a seat that DISSENTed on that ticket, lists what it dropped, says so when nothing is left, and the final
    then validates. The dissenter's words ride as the minority note."""
    sys.path.insert(0, TOOLS)
    import importlib, registrar, pma_pipeline
    importlib.reload(registrar); importlib.reload(pma_pipeline)
    rd = os.path.join(td, "dissent"); 
    for sub in ("forms/r2", "forms/ratify", "forms/adopt"): os.makedirs(os.path.join(rd, sub))
    json.dump({"voice": "seow", "votes": [{"ticker": "QQQ1", "stance": "SUPPORT", "reason": "cmf 0.34 confirms the high"}]}, open(os.path.join(rd, "forms/r2/seow.json"), "w"))
    json.dump({"voice": "oneil", "date": "2026-11-04", "tickets": [{"ticker": "QQQ1", "answer": "OBJECT", "objection": "Market gate", "would_clear": "A follow-through day on the index"}]}, open(os.path.join(rd, "forms/ratify/oneil.json"), "w"))
    json.dump({"voice": "oneil", "date": "2026-11-04", "tickets": [{"ticker": "QQQ1", "answer": "DISSENT", "text": "I still oppose: the market gate fails"}]}, open(os.path.join(rd, "forms/adopt/oneil.json"), "w"))
    cl = lambda txt, v, f, fld: {"text": txt, "source": {"voice": v, "form": f, "field": fld}}
    draft = {"voice": "chair", "date": "2026-11-04", "stage": "draft", "tickets": [{"ticker": "QQQ1", "why": [cl("cmf 0.34 confirms the high", "seow", "vote", "reason")],
             "would_change": [cl("A follow-through day on the index", "oneil", "ratify", "would_clear")]}]}
    json.dump(draft, open(os.path.join(rd, "rationale_draft.json"), "w"))
    e, _ = registrar.validate_rationale(draft, "draft", ["QQQ1"], rd)
    check("the draft may quote an objector's would_clear only until they dissent: with the dissent on file the draft is refused too", any("DISSENTED" in x for x in e), str(e))
    # the draft as the Chair filed it BEFORE the dissent existed
    os.remove(os.path.join(rd, "forms/adopt/oneil.json"))
    e, _ = registrar.validate_rationale(draft, "draft", ["QQQ1"], rd)
    check("before the dissent the draft validates", e == [], str(e))
    json.dump({"voice": "oneil", "date": "2026-11-04", "tickets": [{"ticker": "QQQ1", "answer": "DISSENT", "text": "I still oppose: the market gate fails"}]}, open(os.path.join(rd, "forms/adopt/oneil.json"), "w"))
    rc, o = run([PIPE, "rationale-final", "--draft", os.path.join(rd, "rationale_draft.json"), "--run-dir", rd, "--out", os.path.join(rd, "rationale_final.json")])
    F = json.load(open(os.path.join(rd, "rationale_final.json")))["tickets"][0]
    check("rationale-final drops the dissenter's clause and lists it", rc == 0 and F["would_change"] == [] and F["dropped_dissent_clauses"] == [{"field": "would_change", "voice": "oneil", "text": "A follow-through day on the index"}], o + str(F)[:300])
    check("the seat that did not dissent keeps its clause", len(F["why"]) == 1 and F["why"][0]["source"]["voice"] == "seow")
    e, _ = registrar.validate_rationale({"voice": "chair", "date": "2026-11-04", "stage": "final", "tickets": [F]}, "final", ["QQQ1"], rd)
    check("the dropped-clause final validates", e == [], str(e))
    F2 = dict(F); F2["would_change"] = [cl("A follow-through day on the index", "oneil", "ratify", "would_clear")]
    e, _ = registrar.validate_rationale({"voice": "chair", "date": "2026-11-04", "stage": "final", "tickets": [F2]}, "final", ["QQQ1"], rd)
    check("a final that still quotes the dissenter is refused", any("DISSENTED" in x for x in e))
    check("the position step declares what was removed and that no 'what would change it' is left",
          "removed from the rationale" in open(PIPE).read() and "no 'what would change it' is left" in open(PIPE).read())


def test_cards_bracket_first_target_rule_and_plain_reason(td):
    """PM 2026-11-04 ("the first target is ultra stupid once you consider RR"): every ADVANCE card carries a code-rendered bracket;
    only levels at 1R or more are targets, closer ones are listed as nearby resistance; the reason block is one plain voice."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards
    importlib.reload(pma_cards)
    # ROKU, 3 Nov: stop 157.90, levels 161.26 / 164.31 / 168.20
    b = pma_cards.bracket_view(160.36, "last close", 157.90, "aqe_atr_fallback", [161.26, 164.31, 168.20], 620)
    check("a level at 0.37R is NOT a target: it is nearby resistance", [x["price"] for x in b["nearby"]] == [161.26] and b["nearby"][0]["r"] == 0.37, str(b))
    check("TP1/TP2 are the levels at or above 1R, each with its own R", [(x["n"], x["price"], x["r"]) for x in b["targets"]] == [(1, 164.31, 1.61), (2, 168.2, 3.19)], str(b["targets"]))
    check("RR to TP2 is TP2's own R, risk is entry - stop, 1R in dollars gives shares", b["rr_tp2"] == 3.19 and b["risk"] == 2.46 and b["shares"] == 252, str(b))
    b = pma_cards.bracket_view(161.26, "buy line", 157.90, "aqe_atr_fallback", [161.26, 164.31, 168.20], 620)
    check("entered at the buy line only ONE level reaches 1R, and the card says so instead of inventing a ladder", len(b["targets"]) == 1 and b["rr_tp2"] is None and "Only one level reaches 1R" in (b["note"] or ""), str(b))
    check("no valid stop is said plainly, not rendered as numbers", "no valid stop" in pma_cards.bracket_view(100, "last close", None, None, [110], 620)["note"])
    html = pma_cards._bracket_html(pma_cards.bracket_view(160.36, "last close", 157.90, "aqe_atr_fallback", [161.26, 164.31, 168.20], 620))
    check("the bracket HTML shows entry, stop, risk, TP in R, RR to TP2, 1R and the nearby line", all(x in html for x in ("Entry", "Stop", "Risk", "TP1", "(1.6R)", "RR to TP2", "1R $620", "Nearby resistance, not targets")), html[:400])
    ok = {"agree": "A leader in a strong group is breaking out on heavy buying.", "wrong_if": "It closes back under 158.99.", "wait_for": "An hourly close above 161.26."}
    check("a plain three-part reason passes", pma_cards.validate_reason(ok) == [])
    bad = dict(ok, agree="4 of 7 analysts SUPPORT; bar_high 161.26, high_52w_close 160.36, ATR 2.4 and EMA21 vwap 5 6 7 8.")
    errs = pma_cards.validate_reason(bad)
    check("raw field names, vote tallies, jargon and a number pile-up are each refused", all(any(k in e for e in errs) for k in ("raw field", "vote tally", "jargon", "numbers")), str(errs))
    check("a missing part or a two-sentence part is refused", pma_cards.validate_reason({"agree": "x."}) != [] and any("more than one sentence" in e for e in pma_cards.validate_reason(dict(ok, agree="It breaks out. It leads the group."))))
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("chk_cards", os.path.join(HERE, "..", "..", "daily-check", "check.py")); ck = _iu.module_from_spec(sp); sp.loader.exec_module(ck)
    f = os.path.join(td, "ct.json"); json.dump({"cards": {"AAA": {"reason": bad}, "BBB": {"reason": ok}, "CCC": {"why": "old wall"}}}, open(f, "w"))
    fails, notes = ck.check_cards_text(f)
    check("check.py cards FAILs the bad reason and the missing one, passes the good one", any("cards.AAA" in x for x in fails) and any("cards.CCC: no `reason`" in x for x in fails) and not any("cards.BBB" in x for x in fails), str(fails)[:300])


def test_freshness_line_and_withheld_stance_print_on_the_cards(td):
    """PM 2026-11-04: the one-line FRESHNESS header (expected session, each leg's date with its reason code, COT 'latest published')
    prints on the card page, and a withheld Valen stance says WITHHELD with the reason, never blank."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards
    importlib.reload(pma_cards)
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..", "..")))
    from src.macro import legs as L
    from datetime import date
    rows = L.build_legs("2026-11-03", date(2026, 11, 4), breadth={"freshness": {"as_of": "2026-11-03", "stale": True, "reason": "1600/4314", "current": 1600, "total": 4314}},
                        vol_series={"vix": "2026-11-03", "vixeq": "2026-11-02", "dspx": "2026-11-02", "vix3m": "2026-11-03", "vix9d": "2026-11-03", "cor1m": "2026-11-03"},
                        cot_as_of="2026-10-27", heartbeat_asof="2026-11-03")
    line = L.freshness_line("2026-11-03", rows)
    check("the FRESHNESS line carries expected, breadth OUR_BUDGET, dispersion PUBLISHER_LAG and COT latest published with the next release",
          line.startswith("FRESHNESS | expected 2026-11-03") and "breadth 2026-11-03 [OUR_BUDGET]" in line and "dispersion 2026-11-02 [PUBLISHER_LAG]" in line
          and "COT 2026-10-27 [PUBLISHER_CADENCE] (latest published; next release 2026-11-06)" in line, line)
    html = pma_cards._freshness_html({"data_freshness": {"line": line}})
    check("it renders as a flag line on the page", "expected 2026-11-03" in html and "FRESHNESS" in html and 'class="flag freshness"' in html)
    check("a missing Valen file or legs table is a declared gap, not silence", "no Valen file and no run marker" in pma_cards._freshness_html({}) and "cannot be dated" in pma_cards._freshness_html({"x": 1}))
    check("a withheld stance says WITHHELD with the reason", pma_cards._stance_word({"stance": {"stance": None, "reason": "breadth STALE"}}).startswith("WITHHELD - breadth STALE")
          and pma_cards._stance_word({"stance": {"word": "NEUTRAL"}}) == "NEUTRAL")


def test_plain_words_in_the_rendered_page_and_the_html_gate(td):
    """PM 2026-11-04: no raw field name anywhere on the page. One table translates them in every text node; check.py cards --html FAILs any left."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards
    importlib.reload(pma_cards)
    t = pma_cards.plain_words("an hourly candle closes above bar_high 161.26; closes above high_52w_close 160.36")
    check("Confirms reads in plain words", t == "an hourly candle closes above yesterday's high 161.26; closes above the 52-week closing high 160.36", t)
    page = ('<html><head><style>.a_b{color:red}</style></head><body><div class="x_y" title="bar_high"><p>day_vol is 2 and ABOVE_STRUCTURE with mystery_field</p></div>'
            '<script>var a_b=1;</script></body></html>')
    out = pma_cards.plainify_html(page)
    check("only TEXT is translated (style, script, attributes untouched)", ".a_b{color:red}" in out and 'class="x_y" title="bar_high"' in out and "var a_b=1;" in out, out)
    check("table entries and caps states are translated; an unknown token falls back to words and is reported",
          "today's volume against its average is 2 and above structure with mystery field" in out and "mystery_field" in pma_cards._PLAIN_FALLBACK, out)
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("chk_html", os.path.join(HERE, "..", "..", "daily-check", "check.py")); ck = _iu.module_from_spec(sp); sp.loader.exec_module(ck)
    f1 = os.path.join(td, "raw.html"); open(f1, "w").write(page)
    f2 = os.path.join(td, "clean.html"); open(f2, "w").write(out)
    fails, _ = ck.check_cards_html(f1)
    check("the gate FAILs a page that shows raw field names (naming them)", len(fails) == 1 and "day_vol" in fails[0] and "mystery_field" in fails[0], str(fails))
    check("the gate passes the translated page (class names and CSS are not text)", ck.check_cards_html(f2)[0] == [])
    b0 = pma_cards.bracket_view(161.26, "buy line", 157.90, "x", [161.26, 164.31], 620)
    h0 = pma_cards._bracket_html(b0)
    check("no target reaching 1R says 'Reward does not justify the risk' and 'No level reaches 1R'", "Reward does not justify the risk at this entry" in h0 and "No level reaches 1R above the entry" in h0, h0)
    h1 = pma_cards._bracket_html(pma_cards.bracket_view(161.26, "buy line", 157.90, "x", [161.26, 164.31, 168.20], 620))
    check("the first line of the bracket is 'Reward/risk to the first real target: 2.1R'", "Reward/risk to the first real target: <b>2.1R</b>" in h1, h1)


def test_committee_words_fold_into_the_audit_trail_and_freshness_falls_back_to_the_marker(td):
    """PM 2026-11-04: the card shows 'Conviction 4 of 5' only; the committee's verbatim rationale and the objections are kept whole
    but folded in <details>, and the gate FAILs C-codes / W/D/H1 / ADX / %K/%D outside a <details>. FRESHNESS falls back to the run
    marker's 'Macro legs:' line instead of a silent 'declared gap'."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards
    importlib.reload(pma_cards)
    pos = {"committee_conviction": 4, "rationale_stage": "final", "why": [{"text": "Trend Template passes: C5 fits, ADX 31, W/D/H1 aligned", "voice": "minervini"}],
           "also": [], "what_would_change_it": [{"text": "C16 breaks", "voice": "oneil"}], "minority_notes": [{"voice": "seow", "kind": "DISSENT", "text": "no"}], "gaps": []}
    blk = pma_cards._committee_block(pos, True)
    visible = re.sub(r"<details.*?</details>", "", blk, flags=re.S)
    check("the visible committee line is plain: 'Conviction 4 of 5' and a dissent count", "Conviction 4 of 5" in visible and "1 reviewer dissents" in visible and "C5" not in visible and "ADX" not in visible, visible)
    check("the verbatim rationale is kept whole inside a closed <details> audit trail", "<details" in blk and "open" not in blk.split(">")[1] and "Audit trail: what each reviewer filed (verbatim)" in blk and "Trend Template passes: C5 fits, ADX 31, W/D/H1 aligned" in blk, blk)
    c = pma_cards._contest_html({"status": "CONTESTED", "n_deciders": 7, "objections": [{"voice": "oneil", "objection": "C2 distribution days fail the gate"}]})
    check("contested objections are folded too, with the count visible", "Contested &middot; 1 of 7 object" in re.sub(r"<details.*?</details>", "", c, flags=re.S) and "C2 distribution days" in c and "<details" in c, c)
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("chk_fold", os.path.join(HERE, "..", "..", "daily-check", "check.py")); ck = _iu.module_from_spec(sp); sp.loader.exec_module(ck)
    bad = os.path.join(td, "bad.html"); open(bad, "w").write("<body><p>Trend fits C5 and W/D/H1 with ADX 31 and %K/%D up</p><details><summary>x</summary><p>C16 ADX</p></details></body>")
    ok = os.path.join(td, "ok.html"); open(ok, "w").write("<body><p>Trend fits and the move is clean</p><details><summary>x</summary><p>C16 ADX W/D/H1</p></details></body>")
    f, _ = ck.check_cards_html(bad)
    check("the gate FAILs C-codes, W/D/H1, ADX and %K/%D outside a <details>, and ignores the audit trail", len(f) == 1 and all(x in f[0] for x in ("C5", "W/D/H1", "ADX", "%K/%D")) and "C16" not in f[0], str(f))
    check("the gate passes a page whose jargon is only inside the audit trail", ck.check_cards_html(ok)[0] == [])
    line = pma_cards._freshness_html({}, {"macro_legs": "Macro legs: expected session 2026-11-03 | breadth 2026-11-03 STALE | volatility 2026-11-02"}, None)
    check("with no legs table the FRESHNESS line comes from the run marker, never a silent gap", "expected session 2026-11-03" in line and "from the run marker" in line and "declared gap" not in line and "NOW (" not in line, line)
    line2 = pma_cards._freshness_html({"data_freshness": {"line": "FRESHNESS | old"}}, None, {"exported_at": "2026-11-04 13:11 SGT", "data_freshness": {"line": "FRESHNESS | new", "expected_session": "2026-11-03", "legs_table": [{"leg": "vix_level", "as_of": "2026-11-03", "reason": "CURRENT"}]}})
    check("with refreshed weather the ONE line carries both halves: AT RUN TIME and NOW (refreshed, after the committee)",
          "AT RUN TIME:" in line2 and "NOW (refreshed" in line2 and "after the committee" in line2, line2)
    line3 = pma_cards._freshness_html({}, {"macro_legs": "Macro legs: expected session 2026-11-03 | breadth 2026-11-03 STALE"},
                                      {"exported_at": "2026-11-04 13:11 SGT", "data_freshness": {"expected_session": "2026-11-03", "legs_table": [
                                          {"leg": "positioning_cot", "as_of": "2026-10-27", "reason": "PUBLISHER_CADENCE", "detail": "x; next release 2026-11-06"},
                                          {"leg": "vix_level", "as_of": "2026-11-03", "reason": "CURRENT"}]}})
    check("the NOW half names what is still not current, with COT as latest published and its next release",
          "all current except positioning_cot 2026-10-27 [PUBLISHER_CADENCE] (latest published; next release 2026-11-06)" in line3 and "breadth 2026-11-03 STALE" in line3, line3)
    mk = {"plain": "Index under distribution: 4+ distribution days in 5 weeks, or no confirmed uptrend (C1, C2).", "seats": ["oneil"]}
    check("the visible Void-if has no canon codes and no seat names; the verbatim line is in the audit trail",
          pma_cards._plain_void(mk) == "Index under distribution: 4+ distribution days in 5 weeks, or no confirmed uptrend."
          and "(C1, C2)" in pma_cards._void_cell(mk) and "(oneil)" in pma_cards._void_cell(mk) and "<details" in pma_cards._void_cell(mk)
          and "C1" not in re.sub(r"<details.*?</details>", "", pma_cards._void_cell(mk), flags=re.S), pma_cards._void_cell(mk))
    check("the leg names read as plain words", pma_cards.plain_words("crown_oldest_leg and positioning_cot") == "the oldest macro input and positioning (COT report)")
    check("indicator names in prose become plain words; a bare ticker cell is left alone", pma_cards.plain_prose("momentum (RSI) is not confirming; 5-day VWAP rising; 2.4 ATR above") == "momentum is not confirming; 5-day volume-weighted price rising; 2.4 daily ranges above"
          and pma_cards.plain_prose("RSI") == "RSI")


def test_a_missing_or_stale_net_highs_read_never_prints_a_direction(td):
    """PM 2026-11-04: stale breadth rendered 'Worsening' (null read as false). Missing/stale must read 'Not read'."""
    sys.path.insert(0, TOOLS)
    import pma_cards as PC
    def row(**k):
        return {"breadth": [dict({"label": "Net High/Net Low (8d vs 20d)"}, **k)]}
    for name, r in (("stale", row(status="STALE", value=None, display=None, reason="OUR_BUDGET")),
                    ("unavailable", row(status="UNAVAILABLE", value=None)),
                    ("null value", row(status="OK", value=None))):
        h = PC._wind_gauges(r)
        check(f"a {name} net-highs read says Not read, no direction", "Not read" in h and "Worsening" not in h and "Improving" not in h, h[:300])
    ok = PC._wind_gauges(row(status="OK", value=False, display="-3 vs -5"))
    check("a real False still reads Worsening", "Worsening" in ok)
    ok2 = PC._wind_gauges(row(status="OK", value=True, display="2 vs 1"))
    check("a real True still reads Improving", "Improving" in ok2)


def test_seat_reported_tokens_and_step_budgets_count_in_the_spend_check(td):
    """P3 (2026-11-04): real seat-reported usage beats the byte estimate; a step over its RUN.yaml budget_tokens FAILs."""
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("chk_p3", os.path.join(HERE, "..", "..", "daily-check", "check.py")); ck = _iu.module_from_spec(sp); sp.loader.exec_module(ck)
    d = os.path.join(td, "p3"); os.makedirs(d, exist_ok=True)
    ry = os.path.join(d, "RUN.yaml")
    open(ry, "w").write("steps:\n  - name: VOTE\n    kind: spawn\n    budget_tokens: 100000\n  - name: GATHER\n    kind: tool\n")
    check("budgets are read per step", ck._step_budgets(ry) == {"VOTE": 100000}, str(ck._step_budgets(ry)))
    json.dump({"date": "2026-11-03", "steps": {"VOTE": {"status": "done", "tokens": 3_000_000, "cost": {"inlined_bytes": 400, "returned_bytes": 400}}}},
              open(os.path.join(d, "run_manifest.json"), "w"))
    f, n = ck.check_chain(d, "2026-11-03", run_yaml=ry)
    check("seat-reported tokens beat a tiny byte estimate and trip the ceiling", any("SPEND OVER CEILING" in x for x in f), str(f)[:300])
    check("a step over its own budget is named", any("STEP OVER BUDGET: VOTE" in x for x in f), str(f)[:300])


def test_lanes_v1_assigns_by_code_and_leads_decide(td):
    """R43 (PROPOSED, behind lanes_v1: off): lane by code, lead seats decide, advisor objections are shown and never counted."""
    sys.path.insert(0, TOOLS)
    import lanes_v1 as L
    base = {"entry": 100.0, "hi_20d": 101.0, "ma_20": 95.0, "ma_20_slope_5d_pct": 1.0, "ma_50": 90.0}
    assert L.assign_lane(dict(base, pct_from_pivot=12.0, continuation_pivot=99.0, continuation_state="BUY_ZONE"))[0] == L.CONTINUATION
    assert L.assign_lane(dict(base, pct_from_pivot=12.0))[0] == L.UNLANED                      # extended, no pause high: every seat counts
    assert L.assign_lane(dict(base, pct_from_pivot=2.0))[0] == L.BREAKOUT
    assert L.assign_lane(dict(base, pct_from_pivot=-1.0, nr7_flag=True))[0] == L.BREAKOUT       # coiling under the pivot
    assert L.assign_lane(dict(base, pct_from_pivot=-6.0, hi_20d=120.0))[0] == L.PULLBACK        # holds a rising 20-day, not coiling
    assert L.assign_lane(dict(base, pct_from_pivot=-6.0, hi_20d=120.0, ma_20=105.0, ma_50=104.0, unr_status="NO"))[0] == L.UNLANED
    # lead sets are inside the seven deciders; the continuation leads are the PM's signed set
    assert all(set(v) <= set(L.DECIDERS) for v in L.LEADS.values())
    assert set(L.LEADS[L.CONTINUATION]) == {"livermore", "seow", "elder-lens", "raschke"} and L.PM_SIGNED[L.CONTINUATION] is True
    assert set(L.advisors(L.CONTINUATION)) == {"oneil", "minervini", "wyckoff"}
    # advisors object: shown, never counted
    r = L.lane_status(L.CONTINUATION, ["oneil", "minervini", "wyckoff"], 7, list(L.DECIDERS), 4)
    assert r["status"] == "AGREED" and r["counted_objectors"] == [] and r["advisor_objectors"] == ["minervini", "oneil", "wyckoff"]
    # leads object: proportional drops at 2 of 4, absolute needs the room's 4
    r = L.lane_status(L.CONTINUATION, ["livermore", "seow"], 7, list(L.DECIDERS), 4)
    assert r["status"] == "DROPPED" and r["threshold"] == 2
    assert L.lane_status(L.CONTINUATION, ["livermore", "seow"], 7, list(L.DECIDERS), 4, "absolute")["status"] == "CONTESTED"
    # UNLANED is exactly today's rule
    assert L.lane_status(L.UNLANED, ["oneil", "minervini", "wyckoff", "seow"], 7, list(L.DECIDERS), 4)["status"] == "DROPPED"
    # the switch ships OFF and the ruling is recorded as proposed
    ry = open(os.path.join(HERE, "..", "RUN.yaml"), encoding="utf-8").read()
    rl = open(os.path.join(HERE, "..", "RULINGS.yaml"), encoding="utf-8").read()
    check("lanes_v1 ships off", "lanes_v1: off" in ry and "id: R43" in rl and "status: approved" in rl.split("id: R43")[1])


def test_ratify_count_with_lanes_v1_on_counts_leads_only_and_off_is_unchanged(td):
    """R43 (PM-approved 2026-11-04, switch lanes_v1): ON -> lead seats' objections decide, advisors' are printed with counted=false;
    the threshold is half of the leads (proportional). OFF (default) -> exactly the R34 count. UNLANED -> R34."""
    d, p4 = _committee_fixture(td, "ratifyv1")
    board = os.path.join(d, "board.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", board])
    P = json.load(open(p4))
    laned = {"GNW": "MOMENTUM_CONTINUATION", "BBY": "MOMENTUM_BREAKOUT", "LNG": "MOMENTUM_CONTINUATION", "MFG": "UNLANED"}
    for r in P["ranked"]:
        if r["ticker"] in laned: r["lane"] = laned[r["ticker"]]
    p4v = os.path.join(d, "phase4_v1.json"); json.dump(P, open(p4v, "w"))
    slate = os.path.join(d, "slate_v1.json")
    json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY"), _ticket("LNG"), _ticket("MFG")]}, open(slate, "w"))
    obj = {"GNW": {"oneil", "minervini", "wyckoff"},                 # all three ADVISORS on a continuation ticket
           "BBY": {"elder-lens", "seow", "raschke"},                 # all three ADVISORS on a breakout ticket
           "LNG": {"livermore", "seow"},                             # two of the four continuation LEADS
           "MFG": {"oneil", "minervini", "wyckoff", "seow"}}         # UNLANED: today's rule, 4 of 7
    for v in DEC:
        _ratify(d, "ratifyv1", v, {t: ("OBJECT" if v in obj[t] else "AGREE") for t in obj})
    def count(on):
        out = os.path.join(d, f"cons_{on}.json")
        if on: os.environ["AEGIS_LANES_V1"] = "on"
        else: os.environ["AEGIS_LANES_V1"] = "off"
        try:
            rc, log = run([PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratifyv1"), "--board", board,
                           "--phase4", p4v, "--date", "2026-11-01", "--out", out, "--record", os.path.join(d, f"rec_{on}.json")])
        finally:
            os.environ.pop("AEGIS_LANES_V1", None)
        check(f"ratify-count lanes_v1={'on' if on else 'off'} exits clean", rc == 0, log[-300:])
        return {c["ticker"]: c for c in json.load(open(out))} if rc == 0 else {}
    off = count(False); on = count(True)
    if not off or not on: return
    check("OFF: three objections on GNW is CONTESTED, four on MFG DROPPED, two on LNG CONTESTED (R34 as before)",
          (off["GNW"]["status"], off["MFG"]["status"], off["LNG"]["status"]) == ("CONTESTED", "DROPPED", "CONTESTED") and "lanes_v1" not in off["GNW"], str({k: v["status"] for k, v in off.items()}))
    check("ON: advisors-only objections leave GNW and BBY AGREED and print them uncounted",
          on["GNW"]["status"] == "AGREED" and on["BBY"]["status"] == "AGREED"
          and all(o["counted"] is False for o in on["GNW"]["objections"]) and sorted(on["GNW"]["lanes_v1"]["advisor_objectors"]) == ["minervini", "oneil", "wyckoff"], str(on["GNW"]))
    check("ON: two of four continuation leads DROP LNG (threshold 2)", on["LNG"]["status"] == "DROPPED" and on["LNG"]["drop_threshold"] == 2 and on["LNG"]["verdict"] == "PASS", str(on["LNG"]))
    check("ON: an UNLANED ticket is counted exactly as before", on["MFG"]["status"] == "DROPPED" and on["MFG"]["drop_threshold"] == 4 and "lanes_v1" not in on["MFG"] or on["MFG"].get("lanes_v1", {}).get("lane") == "UNLANED")


def test_lanes_v1_switch_prompt_and_rank_lane(td):
    """R43: the switch defaults OFF (door-based label); ON the rank lane is the code-assigned lane and the vote prompt names the leads and each yardstick."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_pipeline as PP
    importlib.reload(PP)
    os.environ.pop("AEGIS_LANES_V1", None)
    check("lanes_v1 is OFF by default and the lane is the door label", PP.lanes_v1_on() is False and PP._lane_for({"pct_from_pivot": 2.0}, ["STRENGTH"])[0] == "MOMENTUM")
    os.environ["AEGIS_LANES_V1"] = "on"
    try:
        check("ON: the lane comes from the AQE row", PP._lane_for({"pct_from_pivot": 12.0, "continuation_pivot": 99.0}, [])[0] == "MOMENTUM_CONTINUATION"
              and PP._lane_for({"pct_from_pivot": 2.0}, ["STRENGTH"])[0] == "MOMENTUM_BREAKOUT")
        txt = "\n".join(PP._lanes_mod().prompt_lines())
        check("ON: the prompt names the leads, the advisors and the continuation yardstick",
              "MOMENTUM_CONTINUATION: leads livermore, seow, elder-lens, raschke; advisors oneil, minervini, wyckoff" in txt
              and "CONTINUATION PIVOT" in txt and "WARNING you state, not a veto" in txt, txt[:400])
    finally:
        os.environ.pop("AEGIS_LANES_V1", None)


def test_cards_theme_basket_table_and_extension_bracket_line(td):
    """PM 2026-11-04: theme baskets in the sector-strength section (grade, week, month, rotation, strongest members) and the labelled
    extension bracket on each ADVANCE card; both from the export alone, nothing invented when it is absent."""
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards as PC
    importlib.reload(PC)
    D = {"thematic_baskets": {"Semis": {"grade": "DEPLOY", "roc5": 3.2, "roc20": 9.1, "rrg_quadrant": "LEADING", "rrg_direction": "HOLDING",
                                         "constituents_used": ["AAA", "BBB", "CCC", "DDD"]},
                              "Travel_Leisure": {"grade": "AVOID", "roc5": -2.0, "roc20": -6.0, "rrg_quadrant": "LAGGING", "rrg_direction": "EXITING",
                                                 "constituents_used": ["EEE"]}},
         "daily_list": [{"ticker": "AAA", "rs_spy_20d": 20.0}, {"ticker": "BBB", "rs_spy_20d": 35.0}, {"ticker": "CCC", "rs_spy_20d": 5.0},
                        {"ticker": "DDD", "rs_spy_20d": 50.0}]}
    h = PC._theme_basket_table(D)
    check("the basket table lists grade, week, month and rotation, best grade first",
          "Semis" in h and "+3.2%" in h and "+9.1%" in h and "Leading" in h and h.index("Semis") < h.index("Travel Leisure"), h[:300])
    check("strongest members are the top three by 20-day strength, best first, and a basket with none on today's list says so",
          h.index("DDD") < h.index("BBB") < h.index("AAA") and "CCC" not in h.split("Semis")[1].split("Travel")[0] and "none on today" in h)
    check("no baskets in the export is a declared gap, not a blank", "declared gap" in PC._theme_basket_table({}))
    eb = {"available": True, "passed": True, "stop": 108.0, "targets": [{"tp": "TP1", "price": 118.0, "r": 2.0}, {"tp": "TP2", "price": 126.5, "r": 3.4}]}
    x = PC._ext_bracket_html(eb)
    check("the extension line is plain, labelled, and names both targets", "runs into open air" in x and "118" in x and "126.5" in x and "1.272" in x and "1.618" in x and "ignores nearby resistance" in x, x)
    check("an older export (no extension_bracket) adds nothing; an unavailable one says why",
          PC._ext_bracket_html(None) == "" and "no continuation window" in PC._ext_bracket_html({"available": False, "reason": "no continuation window"}))


def test_ratify_count_excludes_a_pending_takeover_target_from_advance(td):
    """R44 (PM 2026-11-04): ma_status PENDING_TARGET in the export -> status DEAL_PINNED, verdict PASS, never ADVANCE/WATCH; no ma_status in the
    export = not applied, said loudly; the Cards print the name in its own section from the export, not as a buy card."""
    d, p4 = _committee_fixture(td, "ratifyma")
    board = os.path.join(d, "board.json")
    run([PIPE, "board", "--round2", os.path.join(d, "forms", "r2"), "--phase4", p4, "--challenge", os.path.join(d, "forms", "challenge", "steenbarger.json"), "--date", "2026-11-01", "--out", board])
    slate = os.path.join(d, "slate_ma.json")
    json.dump({"date": "2026-11-01", "chair": "chair", "tickets": [_ticket("GNW"), _ticket("BBY", "WATCH")]}, open(slate, "w"))
    for v in DEC:
        _ratify(d, "ratifyma", v, {"GNW": "AGREE", "BBY": "AGREE"})
    exp = os.path.join(d, "export_ma.json")
    json.dump({"daily_list": [{"ticker": "GNW", "ma_status": "PENDING_TARGET", "ma_note": "Acme will acquire Gnw (2026-06-15)", "gics_sector_name": "Tech", "entry": 10.0},
                              {"ticker": "BBY", "ma_status": "PENDING_TARGET", "ma_note": "x", "entry": 20.0}]}, open(exp, "w"))
    out = os.path.join(d, "cons_ma.json")
    rc, log = run([PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratifyma"), "--board", board, "--phase4", p4,
                   "--date", "2026-11-01", "--export", exp, "--out", out, "--record", os.path.join(d, "rec_ma.json")])
    check("ratify-count with an export exits clean", rc == 0, log[-300:])
    if rc != 0: return
    C = {c["ticker"]: c for c in json.load(open(out))}
    check("a pending-takeover target slated ADVANCE or WATCH becomes DEAL_PINNED / PASS and carries its M&A line",
          all((C[t]["status"], C[t]["verdict"]) == ("DEAL_PINNED", "PASS") for t in ("GNW", "BBY")) and C["GNW"]["deal_pinned"]["ma_note"].startswith("Acme will acquire"), str(C["GNW"])[:300])
    json.dump({"daily_list": [{"ticker": "GNW", "entry": 10.0}]}, open(exp, "w"))                 # an older export with no ma_status
    rc, log = run([PIPE, "ratify-count", "--slate", slate, "--ratifications", os.path.join(d, "forms", "ratifyma"), "--board", board, "--phase4", p4,
                   "--date", "2026-11-01", "--export", exp, "--out", out, "--record", os.path.join(d, "rec_ma.json")])
    C2 = {c["ticker"]: c for c in json.load(open(out))}
    check("no ma_status in the export: the rule is NOT applied and the run says so", rc == 0 and C2["GNW"]["status"] == "AGREED" and "R44) NOT applied" in log, log[-300:])
    sys.path.insert(0, TOOLS)
    import importlib, pma_cards as PC
    importlib.reload(PC)
    pinned = [C["GNW"]]
    h = PC._deal_pinned_section(pinned, {"GNW": {"ticker": "GNW", "ma_status": "PENDING_TARGET", "ma_note": "Acme will acquire Gnw (2026-06-15)", "gics_sector_name": "Tech", "entry": 10.0}})
    check("the Cards print a Deal-pinned section with the M&A line and no buy card", "Deal-pinned, not a momentum pick" in h and "Acme will acquire" in h and "never a buy card" in h and PC._deal_pinned_section([], {}) == "", h[:200])
    gaps = PC._validate_text({"cards": {}, "holds": {}, "passes": {}}, [C["GNW"]])
    check("a deal-pinned name needs no entry in the words file", not any("GNW" in g for g in gaps), str(gaps)[:300])


def main():
    print("AEGIS PMA regression suite -- fixtures are the real 2026-09-06 committee outputs\n")
    with tempfile.TemporaryDirectory() as td:
        for fn in [test_ratify_count_excludes_a_pending_takeover_target_from_advance, test_cards_theme_basket_table_and_extension_bracket_line, test_lanes_v1_switch_prompt_and_rank_lane, test_ratify_count_with_lanes_v1_on_counts_leads_only_and_off_is_unchanged, test_lanes_v1_assigns_by_code_and_leads_decide, test_seat_reported_tokens_and_step_budgets_count_in_the_spend_check, test_a_missing_or_stale_net_highs_read_never_prints_a_direction, test_consensus_reproduces_the_real_run, test_consensus_refuses_a_shape_it_cannot_read,
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
                   test_the_conductor_tells_the_desk_when_done_and_ships_what_the_desk_shows,
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
                   test_shortlist_cap_is_six, test_case_form_is_required_both_ways,
                   test_deliberation_forms_are_validated_on_arrival,
                   test_board_marks_contested_names_and_never_a_verdict, test_floor_caps_are_counted_by_code,
                   test_objection_rule_counts_the_final_ratification, test_the_record_is_written_per_voice_per_ticket,
                   test_r2digest_reads_the_crown_file_and_marks_retired_seats,
                   test_run_map_carries_the_seven_deciders_and_the_new_rounds,
                   test_the_seat_cards_carry_the_floor_and_the_roster_is_archived_not_deleted,
                   test_checkpoints_land_under_aegis_output_and_never_rebuild_the_space, test_one_risk_figure,
                   test_the_checker_catches_a_seeded_failure,
                   test_the_cards_show_the_slate_status_objections_and_the_detect_lens_top_10,
                   test_the_weather_cards_exist_and_are_wired,
                   test_two_tier_funnel_is_counted_by_code, test_multi_timeframe_grid_is_required,
                   test_mtf_build_from_real_bars_prints_the_grid_in_the_packet,
                   test_one_trigger_per_ticket_and_market_kill, test_valen_flags_leave_ticket_selection,
                   test_the_data_handoff_gate_catches_bad_data_before_a_committee,
                   test_the_book_and_its_stops_are_one_checked_source,
                   test_one_r_is_one_percent_of_the_journals_capital,
                   test_review_fixes_count_only_validated_forms_and_never_double_count,
                   test_rebuilt_seow_and_wyckoff_canons_are_sound,
                   test_the_figure_audit_reads_field_equals_value,
                   test_a_too_late_line_is_never_below_the_buy_line,
                   test_up_to_three_reserved_seats_for_a_valen_reclaim,
                   test_the_flag_list_leads_with_the_strongest_names,
                   test_the_strongest_names_are_voted_in_the_momentum_lane,
                   test_a_buy_line_far_under_the_close_is_never_the_trigger,
                   test_committee_position_counts_the_median_and_never_invents_a_rationale,
                   test_a_rerun_has_its_own_identity_and_cannot_publish_live,
                   test_p2_cap_25_code_made_cut_verbatim_slate_quotes_and_amend_also,
                   test_form_cap_scales_with_tickets_and_trigger_ties_are_stated,
                   test_rationale_final_drops_clauses_sourced_from_a_dissenting_seat,
                   test_the_handoff_gate_fails_a_stale_breadth_we_caused_and_a_missing_legs_table,
                   test_cards_bracket_first_target_rule_and_plain_reason,
                   test_freshness_line_and_withheld_stance_print_on_the_cards,
                   test_plain_words_in_the_rendered_page_and_the_html_gate,
                   test_committee_words_fold_into_the_audit_trail_and_freshness_falls_back_to_the_marker]:
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

