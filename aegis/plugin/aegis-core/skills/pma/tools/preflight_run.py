#!/usr/bin/env python3
"""preflight_run.py — the gate the conductor passes through before every step.

WHY. Rulings used to live as paragraphs in cards. Prose cannot be checked and does not survive an
operator whose context is compacted mid-run: on 2026-09-06 three rulings held and three did not,
and the difference was never authority, only whether the rule had been compiled into something
that could fail. This reads RULINGS.yaml and RUN.yaml -- the constitution as data -- and either
asserts a ruling mechanically or PRINTS it to the conductor at the step it binds, so it cannot be
silently lost.

    python3 tools/preflight_run.py run                 # once, before GATHER: full check + tests
    python3 tools/preflight_run.py step NOMINATE       # before each step: inputs + binding rulings

No external dependencies -- the YAML here is read by a tiny purpose-built parser, so this runs on
any box, exactly like registrar.py.
"""
import re, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
TOOLS = HERE


def mini_yaml(text):
    """Enough YAML for RULINGS/RUN: nested maps, '- ' lists, '>' folded scalars, [a, b] inline."""
    def val(v):
        # FIX 2026-11-02: a trailing YAML comment ('spawns: 1   # one courier') was read INTO the value, so the MTF
        # step's spawns became the string "1   # ..." and the spawn budget sum raised TypeError. Strip a comment
        # that follows an unquoted scalar, or that follows the closing quote of a quoted one.
        v = v.strip()
        if v[:1] in ("\"", "'"):
            j = v.find(v[0], 1)
            if j > 0 and v[j + 1:].strip().startswith("#"):
                v = v[:j + 1]
        elif v.startswith("["):
            j = v.find("]")
            if j > 0 and v[j + 1:].strip().startswith("#"):
                v = v[:j + 1]
        else:
            m = re.search(r"\s#", v)
            if m:
                v = v[:m.start()].rstrip()
        if v.startswith("[") and v.endswith("]"):
            return [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
        if v in ("null", "~", ""): return None
        if v in ("true", "false"): return v == "true"
        if v.startswith('"') and v.endswith('"'): return v[1:-1]
        if v.startswith("'") and v.endswith("'"): return v[1:-1]
        try: return int(v)
        except ValueError: return v

    lines = [l.rstrip() for l in text.split("\n")]
    i, root = 0, {}

    def join_flow(v):
        """FIX 2026-09-16: an inline [a, b] list may WRAP across lines -- RUN.yaml's WRITE step
        wraps its reads: list. val() only recognised a bracket list that opened and closed on one
        line, so a wrapped list fell through as a raw STRING. cmd_step then iterated that string
        character by character and reported every character as a missing input, which made the
        missing-input report for that step unreadable and easy to dismiss. Consume continuation
        lines until the bracket balances; leave i on the last line consumed for the caller's i+=1."""
        nonlocal i
        s = v.strip()
        if not s.startswith("[") or s.endswith("]"):
            return v
        parts, j = [s], i + 1
        while j < len(lines) and "]" not in parts[-1]:
            parts.append(lines[j].strip()); j += 1
        if "]" not in parts[-1]:
            return v                      # unbalanced to EOF -- leave it alone, don't eat the file
        i = j - 1
        return " ".join(parts)

    def parse(indent):
        nonlocal i
        out = None
        while i < len(lines):
            raw = lines[i]
            if not raw.strip() or raw.lstrip().startswith("#"):
                i += 1; continue
            ind = len(raw) - len(raw.lstrip())
            if ind < indent: break
            s = raw.strip()
            if s.startswith("- "):
                if out is None: out = []
                if not isinstance(out, list): break
                body = s[2:]
                item = {}
                if ":" in body:
                    k, _, v = body.partition(":")
                    if v.strip() in (">", "|"):
                        i += 1; item[k.strip()] = fold(ind + 2)
                    else:
                        item[k.strip()] = val(join_flow(v)); i += 1
                    sub = parse(ind + 2)
                    if isinstance(sub, dict): item.update(sub)
                else:
                    i += 1; item = val(body)
                out.append(item); continue
            if ":" in s:
                if out is None: out = {}
                if not isinstance(out, dict): break
                k, _, v = s.partition(":")
                if v.strip() in (">", "|"):
                    i += 1; out[k.strip()] = fold(ind + 2)
                elif v.strip() == "":
                    i += 1; out[k.strip()] = parse(ind + 2)
                else:
                    out[k.strip()] = val(join_flow(v)); i += 1
                continue
            i += 1
        return out if out is not None else {}

    def fold(indent):
        nonlocal i
        parts = []
        while i < len(lines):
            raw = lines[i]
            if raw.strip() and (len(raw) - len(raw.lstrip())) < indent: break
            parts.append(raw.strip()); i += 1
        return " ".join(p for p in parts if p).strip()

    return parse(0)


def load_yaml(name):
    p = os.path.join(SKILL, name)
    if not os.path.exists(p):
        sys.exit(f"PREFLIGHT FAIL: {name} is missing. The constitution must be present as data.")
    return mini_yaml(open(p).read())


FAILS = []
def assert_(name, cond, detail=""):
    print(("  ok    " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond: FAILS.append(name)


# ---------------------------------------------------------------- ruling checks
def check_ranking_key_has_no_srm():
    """R4 -- sector is not a gate."""
    src = open(os.path.join(TOOLS, "pma_pipeline.py")).read()
    key = src.split('"ranking_key": "')[1].split('"')[0] if '"ranking_key": "' in src else ""
    head = key.split("(")[0]
    assert_("R4 srm_entry_gate absent from the ranking key", "srm" not in head, key[:80])
    assert_("R4 sector still rendered on rows (context, not gate)", '"srm": srm.get(' in src)


def check_no_local_filter():
    """R5 -- candidate_set is consumed as published."""
    src = open(os.path.join(TOOLS, "pma_pipeline.py")).read()
    banned = ["momentum_floor", "MOMENTUM_FLOOR", "sc_momentum >= FLOOR"]
    hit = [b for b in banned if b in src]
    assert_("R5 no local momentum floor in the pipeline", not hit, str(hit))
    assert_("R5 momentum_floor.py is not invoked by any step",
            "momentum_floor" not in open(os.path.join(SKILL, "RUN.yaml")).read())


def check_tool_hashes_recorded(manifest="run_manifest.json"):
    """R7 -- the run verifies the tools it executes."""
    if not os.path.exists(manifest):
        assert_("R7 tool hashes recorded on the scoreboard", False, "no run_manifest.json yet (run `registrar.py init`)")
        return
    m = json.load(open(manifest))
    rec = (m.get("steps", {}).get("GATHER", {}) or {}).get("tool_hashes")
    assert_("R7 tool hashes recorded on the scoreboard", bool(rec), "GATHER.tool_hashes is empty")
    if rec:
        bad = []
        for f, h in rec.items():
            p = os.path.join(TOOLS, f)
            if os.path.exists(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() != h:
                bad.append(f)
        assert_("R7 no tool changed mid-run", not bad, str(bad))


def stamp_tool_hashes(manifest="run_manifest.json"):
    """Called at GATHER. Records what this run will execute."""
    if not os.path.exists(manifest):
        sys.exit("stamp: no run_manifest.json — run `registrar.py init --date <date>` first")
    m = json.load(open(manifest))
    h = {}
    for f in sorted(os.listdir(TOOLS)):
        if f.endswith(".py"):
            h[f] = hashlib.sha256(open(os.path.join(TOOLS, f), "rb").read()).hexdigest()
    m.setdefault("steps", {}).setdefault("GATHER", {})["tool_hashes"] = h
    json.dump(m, open(manifest, "w"), indent=1, sort_keys=True)
    print(f"stamped {len(h)} tool hashes onto the scoreboard (R7)")
    for f, v in h.items(): print(f"  {f:22} {v[:16]}")


_TESTS_RAN = set()


def run_tests():
    """The regression suite, once per preflight (every ruling below maps here). tests/test_pipeline.py is required;
    tests/test_cards_levels_mtf.py (R39/R40 cards, levels and mtf.py, 2026-11-02) runs too when it ships."""
    for name, required in (("test_pipeline.py", True), ("test_cards_levels_mtf.py", False)):
        if name in _TESTS_RAN:
            continue
        _TESTS_RAN.add(name)
        t = os.path.join(SKILL, "tests", name)
        if not os.path.exists(t):
            if required:
                assert_("regression suite present", False, f"tests/{name} missing")
            continue
        # cwd = the skill dir, never the run dir: a test whose tool reads a default path (consensus --phase4 phase4.json)
        # would otherwise read the RUN's file and fail on a fixture mismatch that is not a regression.
        r = subprocess.run([sys.executable, t], capture_output=True, text=True, cwd=SKILL)
        tail = (r.stdout or "").strip().split("\n")
        summary = next((l for l in reversed(tail) if "passed" in l), "no summary")
        assert_(f"regression suite {name}: {summary.strip()}", r.returncode == 0,
                "\n".join(tail[-8:]))


CHECKS = {
    "preflight.ranking_key_has_no_srm": check_ranking_key_has_no_srm,
    "preflight.no_local_filter_between_gather_and_rank": check_no_local_filter,
    "preflight.tool_hashes_recorded": check_tool_hashes_recorded,
    "tests.test_shape_contracts": run_tests,
    "tests.test_a_position_the_pm_owns_reaches_every_seat": run_tests,
    "tests.test_fading_is_not_a_gate": run_tests,
    "tests.test_a_momentum_lane_name_is_judged_by_the_strength_seats": run_tests,
    "tests.test_every_nominator_is_served_the_momentum_floor": run_tests,
    # R16 (PM ruling 2026-09-24): the nomination floor. Mechanically checked, never advisory --
    # this is the ruling that stops a file size limit deciding which analysts are heard.
    "tests.test_every_nomination_is_seated": run_tests,
    "tests.test_a_split_ballot_is_validated_per_part_and_merged": run_tests,
    # R17/R18 (PM rulings 2026-09-25): a door flags and never seats; brackets are produced by the run.
    "tests.test_a_door_opener_is_flagged_and_never_voted": run_tests,
    "tests.test_brackets_are_produced_for_advance_and_hold_and_never_for_held": run_tests,
    "tests.test_a_repeat_advance_is_marked_standing_or_drifted": run_tests,
    # R22/R23 (PM 2026-10-22/23): Lynch consulted only; one fixed card-report format.
    "tests.test_consulted_seat_ballot_never_counts": run_tests,
    "tests.test_card_report_layout_is_fixed_and_refuses_gaps": run_tests,
    # R31/R32 (PM 2026-10-30, the redesign): seven deciders + QA; all seven count on every name.
    "tests.test_roster_is_seven_deciders_plus_qa": run_tests,
    "tests.test_all_seven_deciders_count_on_every_name": run_tests,
    "tests.test_shortlist_cap_is_six": run_tests,                      # R33
    "tests.test_objection_rule_counts_the_final_ratification": run_tests,   # R34
    "tests.test_the_record_is_written_per_voice_per_ticket": run_tests,     # R35
    "tests.test_floor_caps_are_counted_by_code": run_tests,                 # R36
    # R37 is superseded by R41 (2026-11-02); its test is replaced by R41's.
    "tests.test_two_tier_funnel_is_counted_by_code": run_tests,             # R38
    "tests.test_multi_timeframe_grid_is_required": run_tests,               # R39
    "tests.test_one_trigger_per_ticket_and_market_kill": run_tests,         # R40
    "tests.test_valen_flags_leave_ticket_selection": run_tests,             # R41
}


def cmd_run():
    R = load_yaml("RULINGS.yaml"); M = load_yaml("RUN.yaml")
    print(f"PREFLIGHT — {len(R['rulings'])} rulings, {len(M['steps'])} steps\n")
    print("Rulings checked mechanically:")
    done = set()
    for r in R["rulings"]:
        c = r.get("check")
        if c in CHECKS and c not in done:
            done.add(c); CHECKS[c]()
    print("\nRulings enforced elsewhere (registrar / gate), listed so they are not forgotten:")
    for r in R["rulings"]:
        c = r.get("check")
        if c and c not in CHECKS: print(f"  ..    {r['id']}  {r['title']}  -> {c}")
    print("\nAdvisory rulings — the conductor must hold these itself:")
    for r in R["rulings"]:
        if not r.get("check") and not str(r.get("status", "")).startswith("superseded"):
            print(f"  !!    {r['id']}  {r['title']}")
    sup = [f"{r['id']} ({r.get('status')})" for r in R["rulings"] if str(r.get("status", "")).startswith("superseded")]
    if sup:
        print(f"\nSuperseded rulings (on the record, no longer bind): {', '.join(sup)}")
    print(f"\nBudget: {sum(s.get('spawns', 0) for s in M['steps'])} model spawns across "
          f"{sum(1 for s in M['steps'] if s['kind'] == 'model')} spawn steps.")
    print(f"\n{'PREFLIGHT PASS' if not FAILS else 'PREFLIGHT FAIL: ' + str(FAILS)}")
    return 1 if FAILS else 0


def cmd_step(name):
    R = load_yaml("RULINGS.yaml"); M = load_yaml("RUN.yaml")
    step = next((s for s in M["steps"] if s["name"] == name.upper()), None)
    if not step: sys.exit(f"unknown step '{name}'. Steps: {[s['name'] for s in M['steps']]}")
    print(f"STEP {step['name']}  [{step['kind']}]"
          + (f"  spawns={step['spawns']}" if step.get("spawns") else ""))
    if step.get("command"): print(f"  command : {step['command']}")
    if step.get("then"):    print(f"  then    : {step['then']}")
    if step.get("barrier"): print(f"  barrier : {step['barrier']}")
    if step.get("on_fail"): print(f"  on fail : {step['on_fail']}")
    if step.get("meter"):   print(f"  meter   : registrar.py meter --step {step['name']} {step['meter']}")
    missing = [f for f in (step.get("reads") or []) if "*" not in f and "<" not in f and not os.path.exists(f)]
    if missing: print(f"  MISSING INPUTS: {missing}")
    binding = [r for r in R["rulings"]
               if step["name"] in (r.get("binds_at") or []) or "ALL" in (r.get("binds_at") or [])]
    if binding:
        print("  RULINGS BINDING HERE — read them, they are not optional:")
        for r in binding:
            print(f"    {r['id']}  {r['title']}")
            print(f"        {r['rule'][:300]}")
    if step.get("must_also"): print(f"  ALSO    : {step['must_also'][:400]}")
    return 1 if missing else 0


if __name__ == "__main__":
    a = sys.argv[1:] or ["run"]
    if a[0] == "run": sys.exit(cmd_run())
    if a[0] == "step": sys.exit(cmd_step(a[1]))
    if a[0] == "stamp": sys.exit(stamp_tool_hashes(*(a[1:] or [])) or 0)
    sys.exit("usage: preflight_run.py run | step <NAME> | stamp")
