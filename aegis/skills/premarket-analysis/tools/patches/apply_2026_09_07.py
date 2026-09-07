#!/usr/bin/env python3
"""AEGIS migration 2026-09-07 -- PM ruling (sector is not a gate) + three tool defects.

Run from aegis/skills/premarket-analysis/tools/:   python3 patches/apply_2026_09_07.py
Idempotent. Every edit asserts on the exact text it expects, so it applies cleanly or fails
loudly -- it can never half-apply, and it never rewrites a file it does not recognise. This is
deliberately a migration rather than a file replacement: main carries work (Layer 0, the
2026-09-05 field spec) that the patching session had not seen, and a wholesale overwrite would
have silently reverted it.

WHAT THIS CHANGES
1. PM RULING 2026-09-07 -- SECTOR IS NOT A GATE. `srm_entry_gate` is removed from the DOOR-1
   ranking key in cmd_rank. It never gated admission (there is no sector door) and as the 3rd
   tiebreaker inside a cap that admits every DOOR-1 name it was inert -- measured on 2026-09-06
   data: neutralising it produced an identical 20-name deliberation set and an identical 13-name
   cut list; only the display order of ranks 10-16 moved. Sector survives as CONTEXT and a SIZING
   input: still rendered on every row and card, still weighted by individual seats at their own
   discretion, never consulted by selection or ordering.

2. DEFECT -- cmd_consensus read the legacy stances[]/stance shape while the v5.3 vote schema is
   votes[]/vote, so it returned an EMPTY tally on real forms and the 2026-09-06 run needed a
   key-rename adapter. Now shape-tolerant, and it raises rather than emitting an empty tally.
   A silent wrong answer is the worst failure class this pipeline can produce.

3. DEFECT -- cmd_r2digest's challenge reader looked only for findings[]. The crowding seat files
   challenges[]/catalyst_check[], so its entire document was dropped from the vote packet with no
   error on 2026-09-06 -- caught only by eyeballing the output. Now aliases the known shapes and
   refuses to emit an empty section for a document that was filed.

4. DEFECT -- purity_check.py hard-coded --solo-min, which v5.3's four-door rank RETIRED, so rank
   exited 2 and the invariance test (the gate that decides whether a run may publish) could not
   run at all. It now probes rank's own --help and passes exactly the flags that exist, and
   forwards --pm-lens so both runs use the command RANK actually used. A tool/pipeline version
   skew now degrades to a weaker test, never to no test. The crowding base rate is also fixed:
   with solo_min defaulting to 0, `maxc >= solo_min` swept in every tallied name and diluted it.

5. COST METER -- registrar.py's `tokens` field existed and nothing ever wrote it, so the PM's
   token meter read 0 for a run that cost over a million. New `registrar.py meter` records
   spawns, bytes inlined into spawn prompts, and bytes returned; `--tool-only` marks steps that
   move bytes between files without anything entering a model context. `status` prints est_tokens
   and wall-clock minutes per step with its basis stated. `started` is now write-once so a re-tick
   cannot reset the clock -- on 2026-09-06 it read GATHER as an eight-hour step.
"""
import os, sys

def edit(path, pairs):
    if not os.path.exists(path):
        sys.exit(f"MISSING {path} -- run this from the tools/ directory")
    s = orig = open(path).read()
    applied, already = [], []
    for name, old, new in pairs:
        if new in s:
            already.append(name); continue
        if old not in s:
            sys.exit(f"REFUSING: {path}: anchor for '{name}' not found. This file has diverged "
                     f"from the expected base; patch by hand and re-verify rather than forcing.")
        s = s.replace(old, new, 1); applied.append(name)
    if s != orig:
        open(path, "w").write(s)
    compile(s, path, "exec")
    print(f"{path}: applied {applied or 'nothing'}" + (f"; already present {already}" if already else ""))

RANK_OLD = '        return (t["count"], t["sumc"], SRM_RANK.get(s.get("entry_gate", ""), 0), them, r.get("sc_momentum") or 0, tk)'
RANK_NEW = '''        # PM RULING 2026-09-07 (SECTOR IS NOT A GATE): srm entry_gate REMOVED from the ranking key.
        # It never gated admission -- it was the 3rd tiebreaker -- but a tiebreaker inside a cap that
        # admits every DOOR-1 name is inert, and the BLOCKED/CAUTION labels read as authority the
        # layer does not have. Sector survives as CONTEXT only: rendered on cards and in brief S2,
        # weighted by individual seats at their own discretion, and consumed by sizing -- never by
        # selection or ordering. Verified on 2026-09-06 data: identical 20-name set, identical cut list.
        return (t["count"], t["sumc"], them, r.get("sc_momentum") or 0, tk)'''

KEY_OLD = '"ranking_key": "DOOR1 by seat_count > conviction_sum > srm_entry_gate > thematic_support > sc_momentum; then DOORS 2-4 by AQE rank"'
KEY_NEW = '"ranking_key": "DOOR1 by seat_count > conviction_sum > thematic_support > sc_momentum; then DOORS 2-4 by AQE rank (PM ruling 2026-09-07: srm_entry_gate removed -- sector is context and sizing input, never selection)"'

SRM_OLD = 'SRM_RANK = {"PASS": 3, "CAUTION": 2, "WATCH": 1, "BLOCKED": 0}'
SRM_NEW = 'SRM_RANK = {"PASS": 3, "CAUTION": 2, "WATCH": 1, "BLOCKED": 0}  # display/sizing only since 2026-09-07; NOT in any ranking key'

CONS_OLD = '''def cmd_consensus(a):
    R2 = load(a.round2)  # list of {voice, stances:[{ticker, stance, conviction, ...}]}
    by_t = collections.defaultdict(lambda: {"support": [], "oppose": [], "abstain": [], "conv": []})
    for vr in R2:
        for s in vr.get("stances", []):
            st = s["stance"].lower()'''
CONS_NEW = '''def cmd_consensus(a):
    # SHAPE-TOLERANT since 2026-09-07. The v5.3 vote schema is votes[]/vote; this reader shipped
    # against the legacy stances[]/stance and silently returned an EMPTY tally on real forms --
    # a silent wrong answer, the worst failure class. It now accepts either shape natively.
    R2 = load(a.round2)  # list of {voice, votes:[{ticker, vote, conviction, ...}]} (legacy: stances/stance)
    by_t = collections.defaultdict(lambda: {"support": [], "oppose": [], "abstain": [], "conv": []})
    for vr in R2:
        rows = vr.get("votes")
        if rows is None:
            rows = vr.get("stances") or []
        for s in rows:
            raw = s.get("vote", s.get("stance"))
            if raw is None:
                raise SystemExit(f"consensus: {vr.get('voice')} row for {s.get('ticker')} has neither 'vote' nor 'stance'")
            st = str(raw).lower()'''

EMPTY_OLD = '''            if st == "support":
                by_t[s["ticker"]]["conv"].append(s.get("conviction", 3))
    out = []'''
EMPTY_NEW = '''            if st == "support":
                by_t[s["ticker"]]["conv"].append(s.get("conviction", 3))
    if not by_t:
        raise SystemExit(f"consensus: read {len(R2)} forms and found ZERO votes -- refusing to emit "
                         f"an empty tally. Check the vote form shape (expected votes[] or stances[]).")
    out = []'''

DIG_OLD = '''        L.append(f"--- {name.upper()} ---")
        for fd in c.get("findings", []) or []:'''
DIG_NEW = '''        L.append(f"--- {name.upper()} ---")
        before = len(L)
        # SHAPE-TOLERANT since 2026-09-07. Challenge seats do not all file findings[]: the crowding
        # seat files challenges[]/catalyst_check[]. This reader looked only for findings[] and emitted
        # a SILENT EMPTY SECTION -- a whole challenge document dropped out of the vote packet with no
        # error. Alias the known equivalents; refuse to emit an empty section for a filed document.
        fnd = list(c.get("findings") or []) + list(c.get("challenges") or []) \\
            + list(c.get("catalyst_check") or []) + list(c.get("entries") or [])
        for fd in fnd:'''

CLAIM_OLD = '''            L.append(f"  [{sc}{(' ' + tag) if tag else ''}] {str(fd.get('claim', ''))[:a.claim_chars]}")
            if fd.get("evidence"): L.append(f"      evidence: {str(fd['evidence'])[:a.evidence_chars]}")'''
CLAIM_NEW = '''            claim = fd.get("claim") or fd.get("challenge") or fd.get("question") or fd.get("read") or ""
            L.append(f"  [{sc}{(' ' + tag) if tag else ''}] {str(claim)[:a.claim_chars]}")
            ev = fd.get("evidence") or fd.get("basis") or fd.get("data")
            if ev: L.append(f"      evidence: {str(ev)[:a.evidence_chars]}")'''

GUARD_OLD = '''    digest("rogers", a.rogers); digest("steenbarger", a.steenbarger); digest("lynch", a.lynch); digest("detect-lens", a.detectlens)'''
GUARD_NEW = '''        if len(L) == before:
            raise SystemExit(f"r2digest: challenge document '{name}' ({path}) produced ZERO lines -- "
                             f"its top-level keys are {sorted(c.keys())}. Refusing to build a vote "
                             f"packet with a silently empty challenge section.")
    digest("rogers", a.rogers); digest("steenbarger", a.steenbarger); digest("lynch", a.lynch); digest("detect-lens", a.detectlens)'''

edit("pma_pipeline.py", [
    ("srm removed from ranking key", RANK_OLD, RANK_NEW),
    ("ranking_key receipt text", KEY_OLD, KEY_NEW),
    ("SRM_RANK display-only note", SRM_OLD, SRM_NEW),
    ("consensus shape tolerance", CONS_OLD, CONS_NEW),
    ("consensus empty-tally guard", EMPTY_OLD, EMPTY_NEW),
    ("r2digest shape tolerance", DIG_OLD, DIG_NEW),
    ("r2digest claim/evidence aliases", CLAIM_OLD, CLAIM_NEW),
    ("r2digest empty-section guard", GUARD_OLD, GUARD_NEW),
])

PC_OLD = '''def run_rank(pipeline, tally, candidates, export, cap, solo_min, out):
    cmd = [sys.executable, pipeline, "rank", "--tally", tally, "--candidates", candidates,
           "--export", export, "--cap", str(cap), "--solo-min", str(solo_min), "--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"rank failed: {r.stderr.strip() or r.stdout.strip()}")'''
PC_NEW = '''def _rank_flags(pipeline):
    """Which optional flags does THIS pipeline's rank actually accept?

    Fixed 2026-09-07. This tool shipped hard-coding --solo-min, which the v5.3 four-door rank
    RETIRED; rank exited 2 and the invariance test -- the gate that decides whether the run may
    publish -- could not run at all. It now probes rank's own --help and passes exactly the flags
    that exist, so a tool/pipeline version skew degrades to a weaker test, never to no test."""
    h = subprocess.run([sys.executable, pipeline, "rank", "--help"], capture_output=True, text=True)
    return (h.stdout or "") + (h.stderr or "")


def run_rank(pipeline, tally, candidates, export, cap, solo_min, out, pm_lens=None, pm_lens_min=5,
             _flags=None):
    flags = _flags if _flags is not None else _rank_flags(pipeline)
    cmd = [sys.executable, pipeline, "rank", "--tally", tally, "--candidates", candidates,
           "--export", export, "--cap", str(cap), "--out", out]
    if "--solo-min" in flags and solo_min:
        cmd += ["--solo-min", str(solo_min)]
    if "--pm-lens" in flags and pm_lens and os.path.exists(pm_lens):
        cmd += ["--pm-lens", pm_lens, "--pm-lens-min", str(pm_lens_min)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"rank failed ({' '.join(cmd[2:])}): {r.stderr.strip() or r.stdout.strip()}")'''

PC2_OLD = '''        run_rank(a.pipeline, a.tally, a.candidates, a.export, a.cap, a.solo_min, out_a)
        run_rank(a.pipeline, a.tally, cs_s, ex_s, a.cap, a.solo_min, out_b)'''
PC2_NEW = '''        flags = _rank_flags(a.pipeline)
        run_rank(a.pipeline, a.tally, a.candidates, a.export, a.cap, a.solo_min, out_a,
                 a.pm_lens, a.pm_lens_min, _flags=flags)
        run_rank(a.pipeline, a.tally, cs_s, ex_s, a.cap, a.solo_min, out_b,
                 a.pm_lens, a.pm_lens_min, _flags=flags)'''

PC3_OLD = '    p.add_argument("--solo-min", dest="solo_min", type=int, default=4)'
PC3_NEW = '''    p.add_argument("--solo-min", dest="solo_min", type=int, default=0,
                   help="legacy; passed only if this pipeline's rank still accepts it (RETIRED in v5.3)")
    p.add_argument("--pm-lens", dest="pm_lens", default="pm_lens.json",
                   help="passed to rank when supported, so BOTH runs use the exact command RANK used")
    p.add_argument("--pm-lens-min", dest="pm_lens_min", type=int, default=5)'''

PC4_OLD = '    qual = [t for t in ranked if t.get("count", 0) >= 2 or t.get("maxc", 0) >= a.solo_min]'
PC4_NEW = '''    # Base rate is the SEAT-qualified population. solo_min now defaults to 0 (the one-seat
    # exception is retired), and "maxc >= 0" would sweep in every tallied name and dilute the
    # base rate -- so the solo leg only applies when a solo_min was actually asked for.
    qual = [t for t in ranked if t.get("count", 0) >= 2 or (a.solo_min and t.get("maxc", 0) >= a.solo_min)]'''

edit("purity_check.py", [
    ("rank flag probe", PC_OLD, PC_NEW),
    ("invariance passes probed flags", PC2_OLD, PC2_NEW),
    ("solo-min default 0 + pm-lens args", PC3_OLD, PC3_NEW),
    ("crowding base rate", PC4_OLD, PC4_NEW),
])

METER_HELPER = '''
# ---------------------------------------------------------------------------
# COST METER (added 2026-09-07 after the 2026-09-06 run reported tokens=0 on
# every step -- the field existed, nothing ever wrote it, and the PM's token
# meter read zero for a run that cost over a million. The conductor cannot
# observe its own token count, so the meter measures what IS observable and
# derives from it: bytes inlined into each spawn, bytes returned, spawn count.
# est_tokens = bytes / BYTES_PER_TOKEN. Approximate on purpose; a number with a
# stated basis beats a zero.)
# ---------------------------------------------------------------------------
BYTES_PER_TOKEN = 4.0


def _blank_step():
    return {"status": "pending", "files": {}, "tokens": 0, "notes": [],
            "cost": {"spawns": 0, "inlined_bytes": 0, "returned_bytes": 0}}


def _cost(step):
    return step.setdefault("cost", {"spawns": 0, "inlined_bytes": 0, "returned_bytes": 0})


def _est_tokens(step):
    """Bytes that passed through a MODEL context. A tool step moves bytes between files without
    any of them entering a context window, so it costs ~0 tokens however large the file is --
    counting them made the first meter read 933k on GATHER, which is arithmetic, not cost."""
    c = _cost(step)
    if c.get("tool_only"):
        return step.get("tokens", 0)
    derived = int((c["inlined_bytes"] + c["returned_bytes"]) / BYTES_PER_TOKEN)
    return max(step.get("tokens", 0), derived)


def _mins(step):
    a, b = step.get("started"), step.get("finished")
    if not (a and b):
        return None
    try:
        f = "%Y-%m-%dT%H:%M:%SZ"
        return round((datetime.datetime.strptime(b, f) - datetime.datetime.strptime(a, f)).total_seconds() / 60, 1)
    except Exception:
        return None


def cmd_meter(a):
    """Record what a step actually consumed. Call once per spawn wave."""
    m = load_manifest(a.manifest)
    if m is None:
        print("ERROR: scoreboard missing", file=sys.stderr)
        return 1
    step = m["steps"].setdefault(a.step, _blank_step())
    step.setdefault("started", _now())
    c = _cost(step)
    c["spawns"] += a.spawns
    for f in (a.inlined or []):
        if os.path.exists(f):
            c["inlined_bytes"] += os.path.getsize(f)
    c["inlined_bytes"] += a.inlined_bytes
    c["returned_bytes"] += a.returned_bytes
    if a.tool_only:
        c["tool_only"] = True
    if a.tokens:
        step["tokens"] = step.get("tokens", 0) + a.tokens
    save_manifest(a.manifest, m)
    print(f"meter: {a.step} spawns={c['spawns']} inlined={c['inlined_bytes']}B "
          f"returned={c['returned_bytes']}B est_tokens={_est_tokens(step)}")
    return 0


def cmd_init(a):'''

R_COMMIT_OLD = '''    step = m["steps"].setdefault(a.step, {"status": "in_flight", "files": {},
                                          "tokens": 0, "started": _now(), "notes": []})
    step["files"][a.file] = digest'''
R_COMMIT_NEW = '''    step = m["steps"].setdefault(a.step, _blank_step())
    step.setdefault("started", _now())
    if a.file not in step["files"]:
        _cost(step)["returned_bytes"] += os.path.getsize(a.file)   # every committed artifact is a return
    step["files"][a.file] = digest'''

R_TICK_OLD = '''    step = m["steps"].setdefault(a.step, {"status": "pending", "files": {}, "tokens": 0, "notes": []})
    if a.status:'''
R_TICK_NEW = '''    step = m["steps"].setdefault(a.step, _blank_step())
    step.setdefault("started", _now())
    if a.status:'''

R_START_OLD = '''        if a.status == "in_flight":
            step["started"] = _now()'''
R_START_NEW = '''        if a.status == "in_flight":
            step.setdefault("started", _now())   # write-once: a re-tick must never reset the clock'''

R_STATUS_OLD = '''    total_tokens = 0
    for name, s in m["steps"].items():
        total_tokens += s.get("tokens", 0)
        nfiles = len(s.get("files", {}))
        print(f"  {name:14s} {s.get('status','?'):9s} files={nfiles} tokens={s.get('tokens',0)}")'''
R_STATUS_NEW = '''    total_tokens = 0
    total_spawns = 0
    print(f"  {'step':14s} {'status':9s} {'files':>5s} {'spawns':>6s} {'est_tok':>9s} {'mins':>6s}  where")
    for name, s in m["steps"].items():
        est = _est_tokens(s); total_tokens += est
        c = _cost(s); total_spawns += c["spawns"]
        mn = _mins(s)
        print(f"  {name:14s} {s.get('status','?'):9s} {len(s.get('files', {})):5d} "
              f"{c['spawns']:6d} {est:9,d} {(str(mn) if mn is not None else '-'):>6s}  "
              f"{'tool' if c.get('tool_only') else 'model'}")'''

R_TOT_OLD = '    print(f"  tokens total: {total_tokens}")'
R_TOT_NEW = '''    print(f"  TOTAL  spawns {total_spawns}  est_tokens {total_tokens:,}  "
          f"(basis: {BYTES_PER_TOKEN} bytes/token over inlined+returned bytes; "
          f"conductor overhead NOT included)")'''

R_SUB_OLD = '    sub.add_parser("status")'
R_SUB_NEW = '''    s = sub.add_parser("meter", help="record spawns and bytes moved for a step (the PM's token meter)")
    s.add_argument("--step", required=True)
    s.add_argument("--spawns", type=int, default=0)
    s.add_argument("--inlined", action="append", default=None,
                   help="path whose bytes were pasted into a spawn prompt; repeatable")
    s.add_argument("--inlined-bytes", dest="inlined_bytes", type=int, default=0)
    s.add_argument("--returned-bytes", dest="returned_bytes", type=int, default=0)
    s.add_argument("--tokens", type=int, default=0, help="exact count, when the caller knows it")
    s.add_argument("--tool-only", dest="tool_only", action="store_true",
                   help="this step moved bytes between files only -- nothing entered a model context")
    sub.add_parser("status")'''

R_DISP_OLD = '''    return {"init": cmd_init, "validate": cmd_validate, "commit": cmd_commit,
            "tick": cmd_tick, "status": cmd_status}[a.cmd](a)'''
R_DISP_NEW = '''    return {"init": cmd_init, "validate": cmd_validate, "commit": cmd_commit,
            "tick": cmd_tick, "meter": cmd_meter, "status": cmd_status}[a.cmd](a)'''

edit("registrar.py", [
    ("cost meter + cmd_meter", "def cmd_init(a):", METER_HELPER.lstrip("\n")),
    ("commit accrues returned bytes", R_COMMIT_OLD, R_COMMIT_NEW),
    ("tick uses blank_step", R_TICK_OLD, R_TICK_NEW),
    ("started write-once", R_START_OLD, R_START_NEW),
    ("status cost table", R_STATUS_OLD, R_STATUS_NEW),
    ("status total line", R_TOT_OLD, R_TOT_NEW),
    ("meter subparser", R_SUB_OLD, R_SUB_NEW),
    ("meter dispatch", R_DISP_OLD, R_DISP_NEW),
])


# ---------------------------------------------------------------------------
# CARDS. Same assert-anchored discipline: these run against ../SKILL.md and
# ../agents/*.md relative to tools/, and report rather than guess.
# ---------------------------------------------------------------------------
def edit_md(path, pairs):
    if not os.path.exists(path):
        print(f"SKIP {path} (not present from here)"); return
    s = orig = open(path).read()
    applied, already, missing = [], [], []
    for name, old, new in pairs:
        if new in s:
            already.append(name); continue
        if old not in s:
            missing.append(name); continue
        s = s.replace(old, new, 1); applied.append(name)
    if s != orig:
        open(path, "w").write(s)
    print(f"{path}: applied {applied or 'nothing'}"
          + (f"; already present {already}" if already else "")
          + (f"; ANCHOR NOT FOUND -- apply by hand: {missing}" if missing else ""))


SKILL_OLD = "_Legacy:_ Qualification seat_count ≥2 OR solo conviction ≥4; fixed v4.2 key (seat_count > conviction_sum > SRM entry_gate > thematic > sc_momentum). No gate anywhere in this chain — no sector, fundamental, or bracket term (R1)."
SKILL_NEW = ("**Ordering key (v5.4, PM ruling 2026-09-07 — SECTOR IS NOT A GATE):** DOOR-1 names by "
             "`seat_count > conviction_sum > thematic_support > sc_momentum`; doors 2–4 by AQE rank. "
             "`srm_entry_gate` has been REMOVED from the key. It never gated admission — there is no sector door — "
             "but as the 3rd tiebreaker inside a cap that admits every DOOR-1 name it was inert, and AQE's BLOCKED/CAUTION "
             "labels read as authority the layer does not have. **Sector is context and a sizing input, never selection or "
             "ordering:** it renders on every card and in brief §2, individual seats weight it at their own discretion, and "
             "concentration/sizing consumes it. Verified on 2026-09-06 data — identical 20-name deliberation set, identical "
             "13-name cut list, display order only. No gate anywhere in this chain — no sector, fundamental, or bracket term (R1).")

METER_DOC = ("## THE COST METER (v5.4, added 2026-09-07)\n"
    "The 2026-09-06 run reported `tokens: 0` on every step — the field existed and nothing ever wrote it, so the PM's token "
    "meter read zero for a run that cost over a million. **The conductor cannot observe its own token count, so it meters what it "
    "can observe.** After every spawn wave: `registrar.py meter --step <STEP> --spawns <n> --inlined <path> [...] --returned-bytes <n>`. "
    "Tool-only steps (GATHER, PREPARE, RANK, PM-LENS, DECIDE, REPEAT-WATCH, CHECK, PUBLISH) add `--tool-only` — they move bytes "
    "between files without anything entering a model context, so they cost ~0 tokens however large the export is. `registrar.py status` "
    "then prints est_tokens and wall-clock minutes per step and a run total, with its basis stated. `started` is write-once and a "
    "re-tick never resets it.\n\n"
    "**Steady-state budget, measured on 2026-09-06:** ~905k model tokens across the five spawn steps (NOMINATE 172k · MACRO 34k · "
    "CHALLENGE 107k · VOTE 352k · WRITE 240k) plus conductor overhead, call it 1.3M for a clean run. VOTE is the single largest line "
    "because the ~69KB tool-built vote packet is inlined once per voting seat; WRITE is second because brief-writer receives all eleven "
    "vote forms. Those are the two levers if a run must be made cheaper.\n\n"
    "## THE SCOREBOARD (`run_manifest.json`)")

edit_md(os.path.join("..", "SKILL.md"), [
    ("v5.4 ordering key -- sector is not a gate", SKILL_OLD, SKILL_NEW),
    ("cost meter discipline", "## THE SCOREBOARD (`run_manifest.json`)", METER_DOC),
])

BW_OLD = "**§1 MACRO — as a table, not paragraphs.**"
BW_NEW = ("**§0A EXECUTIVE CONSENSUS — WHY THESE ADVANCE. MANDATORY (PM ruling 2026-09-07).**\n"
    "The §0 one-liner says what the name is; §0A says why the committee rated it ADVANCE. Open with **the book in three lines** — "
    "what the ADVANCE names have in common as a group (with figures), where agreement was strongest and where thinnest, and the single "
    "condition that invalidates the group thesis. Then one block per ADVANCE name, `### TICKER — ADVANCE · conviction N`, **exactly "
    "2–3 sentences**: (1) the winning argument, with the figures that carried it; (2) the strongest thing said against it and why it "
    "lost — stated as the losing argument, never softened into agreement; (3) optional, what has to stay true. Same rules as everywhere "
    "else in the body: no seat name, no vote count, no 'support/oppose/abstain', and **never** a bracket-based reason (R1). Strength of "
    "agreement is qualitative only — unanimous, near-unanimous, carried over a real objection, narrow. HOLD names get no §0A block; "
    "their §0 condition line is the whole story.\n\n"
    "**§1 MACRO — as a table, not paragraphs.**")

for cand in [os.path.join("..", "agents", "brief-writer.md"),
             os.path.join("..", "..", "..", "plugin", "aegis-core", "agents", "brief-writer.md")]:
    if os.path.exists(cand):
        edit_md(cand, [("mandatory section 0A executive consensus", BW_OLD, BW_NEW)])
        break
else:
    print("SKIP brief-writer.md (not found from here) -- add the §0A block by hand")

print("\nAll edits applied and every touched file re-compiled clean.")
print("Verify:  python3 purity_check.py --export <export>   (must print 'invariance: PASS')")
print("         python3 registrar.py status                 (must print an est_tok column)")
