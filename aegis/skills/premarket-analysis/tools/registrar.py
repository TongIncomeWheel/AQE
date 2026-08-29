#!/usr/bin/env python3
"""registrar.py — the CHECKER (v5, PM-approved design 2026-08-28).

The one deterministic doorway every artifact passes through. Pure python, zero
external deps (no jsonschema import — validation is hand-rolled so this runs on
any box). It does four things, identically every time:

  validate   a seat form (round1 nomination / round2 vote) against the house
             contract + the universe + the deliberation set. Malformed => REJECT
             with reasons; the conductor gives the seat ONE re-spawn, then marks
             it absent. Never at the end of the run — the moment it arrives.
  commit     save a validated artifact, fingerprint it (sha256), tick the
             scoreboard (run_manifest.json). Committing IS the checkpoint.
  tick       update a step's status/tokens/degradations on the scoreboard.
  status     print the scoreboard — this IS the progress report and the resume
             point. `registrar.py status` answers: which run, what's done (with
             fingerprints), what's in flight, tokens per step, degradations.

Scoreboard shape (run_manifest.json):
{
  "run_id": "pma-2026-08-28", "date": "2026-08-28",
  "steps": { "<STEP>": {"status": "pending|in_flight|done|degraded|failed",
                        "files": {"<path>": "<sha256>"},
                        "tokens": 0, "started": "...", "finished": "...",
                        "notes": []} },
  "seats": { "<STEP>/<seat>": {"status": "committed|rejected|absent",
                               "file": "...", "sha256": "...",
                               "flags": ["BRACKET_BASIS", ...]} },
  "degradations": [], "flags": []
}

v5 §6b bracket-basis lint: a vote/nomination whose stated basis is bracket
validity ALONE is flagged (never rejected) so the pattern is visible on the
scoreboard instead of covert. The crowding audit itself lives in purity_check.py.
"""
import argparse, datetime, hashlib, json, os, re, sys

MAX_FORM_BYTES = 24 * 1024
R1_REASON_MAX = 300
R2_LIMITS = {"reason": 500, "conviction_change": 250, "opposing_case": 300,
             "self_counter": 300, "falsifier": 250, "challenge_reply": 400,
             "o_a_note": 250, "o_b_stop_honored": 150, "o_c_invalidation": 250}
BRACKET_ONLY = re.compile(r"bracket[._ ]?(valid|invalid)", re.I)
SIGNAL_WORDS = re.compile(r"(structure|momentum|volume|rs_|elder|mp_|div_|squeeze|vwap|flow|energy|sector|leader|conviction|base|coil|stack|ma_\d)", re.I)


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path, what):
    try:
        with open(path) as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"{what} not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"{what} is not valid JSON ({e})"


def load_manifest(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_manifest(path, m):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _bounded(errs, obj, field, maxlen, where):
    v = obj.get(field)
    if v is not None and not isinstance(v, str):
        errs.append(f"{where}.{field}: must be string or null")
    elif isinstance(v, str) and len(v) > maxlen:
        errs.append(f"{where}.{field}: {len(v)} chars > cap {maxlen} (essay leak)")


def _bracket_lint(texts):
    """Flag when bracket validity is the ONLY stated basis (v5 §6b lint)."""
    joined = " ".join(t for t in texts if t)
    if BRACKET_ONLY.search(joined) and not SIGNAL_WORDS.search(joined):
        return True
    return False


def validate_round1(form, universe):
    errs, flags = [], []
    for req in ("voice", "date", "nominations", "held_review"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    noms = form.get("nominations", [])
    if not isinstance(noms, list) or len(noms) > 10:
        errs.append("nominations: must be a list of at most 10")
        noms = noms if isinstance(noms, list) else []
    for i, n in enumerate(noms):
        w = f"nominations[{i}]"
        for req in ("ticker", "reason", "conviction", "checklist_trace"):
            if req not in n:
                errs.append(f"{w}: missing {req}")
        t = n.get("ticker")
        if universe is not None and t and t not in universe:
            errs.append(f"{w}: ticker {t} NOT IN UNIVERSE — F1: whole return untrusted")
        c = n.get("conviction")
        if not isinstance(c, int) or not (1 <= c <= 5):
            errs.append(f"{w}: conviction must be integer 1-5")
        _bounded(errs, n, "reason", R1_REASON_MAX, w)
        for step in (n.get("checklist_trace") or []):
            if isinstance(step, dict):
                _bounded(errs, step, "observed", 200, f"{w}.trace")
        if _bracket_lint([n.get("reason", "")]):
            flags.append(f"BRACKET_BASIS:{t}")
    return errs, flags


def validate_round2(form, universe, deliberation_set):
    errs, flags = [], []
    for req in ("voice", "date", "round", "votes"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    if form.get("round") != 2:
        errs.append("round: must be 2")
    votes = form.get("votes", [])
    if not isinstance(votes, list):
        errs.append("votes: must be a list")
        votes = []
    seen = set()
    for i, v in enumerate(votes):
        w = f"votes[{i}]"
        t = v.get("ticker")
        if not t:
            errs.append(f"{w}: missing ticker")
            continue
        if t in seen:
            errs.append(f"{w}: duplicate ticker {t}")
        seen.add(t)
        if universe is not None and t not in universe:
            errs.append(f"{w}: ticker {t} NOT IN UNIVERSE — F1: whole return untrusted")
        stance = v.get("vote")
        if stance not in ("SUPPORT", "OPPOSE", "ABSTAIN"):
            errs.append(f"{w}: vote must be SUPPORT/OPPOSE/ABSTAIN")
        c = v.get("conviction")
        if stance in ("SUPPORT", "OPPOSE"):
            if not isinstance(c, int) or not (1 <= c <= 5):
                errs.append(f"{w}: {stance} requires conviction 1-5")
        if stance == "OPPOSE" and not v.get("opposing_case"):
            errs.append(f"{w}: OPPOSE requires opposing_case (O1)")
        if stance == "SUPPORT" and isinstance(c, int) and c >= 4 and not v.get("self_counter"):
            errs.append(f"{w}: SUPPORT@{c} requires self_counter (O2)")
        for field, cap in R2_LIMITS.items():
            src = v.get("obligations") if field.startswith("o_") else v
            if isinstance(src, dict):
                _bounded(errs, src, field, cap, w)
        if _bracket_lint([v.get("reason", ""), v.get("opposing_case") or ""]):
            flags.append(f"BRACKET_BASIS:{t}")
    if deliberation_set is not None:
        ds = set(deliberation_set)
        missing, extra = ds - seen, seen - ds
        if missing:
            errs.append(f"votes missing for deliberation-set names: {sorted(missing)}")
        if extra:
            errs.append(f"votes filed on names OUTSIDE the deliberation set: {sorted(extra)}")
    return errs, flags


def cmd_validate(a):
    raw = open(a.file, "rb").read()
    if len(raw) > MAX_FORM_BYTES:
        print(json.dumps({"result": "REJECT", "errors":
              [f"form is {len(raw)}B > {MAX_FORM_BYTES}B cap — essay leak; forms not essays"]}))
        return 1
    try:
        form = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"result": "REJECT", "errors": [f"not a single valid JSON object: {e}"]}))
        return 1
    universe = None
    if a.candidates:
        cs, err = load_json(a.candidates, "candidate_set")
        if err:
            print(json.dumps({"result": "REJECT", "errors": [err]}))
            return 1
        universe = {r["ticker"] for r in cs.get("universe", [])}
    dset = None
    if a.round == 2 and a.phase4:
        p4, err = load_json(a.phase4, "phase4")
        if err:
            print(json.dumps({"result": "REJECT", "errors": [err]}))
            return 1
        dset = p4.get("deliberation_set")
    if a.round == 1:
        errs, flags = validate_round1(form, universe)
    else:
        errs, flags = validate_round2(form, universe, dset)
    result = "REJECT" if errs else "OK"
    print(json.dumps({"result": result, "errors": errs, "flags": flags,
                      "voice": form.get("voice"), "sha256": hashlib.sha256(raw).hexdigest()}))
    return 1 if errs else 0


def cmd_init(a):
    m = {"run_id": f"pma-{a.date}", "date": a.date, "created": _now(),
         "steps": {}, "seats": {}, "degradations": [], "flags": []}
    save_manifest(a.manifest, m)
    print(f"scoreboard initialised: {a.manifest} run_id=pma-{a.date}")
    return 0


def cmd_commit(a):
    m = load_manifest(a.manifest)
    if m is None:
        print("ERROR: scoreboard missing — run `registrar.py init` first", file=sys.stderr)
        return 1
    digest = sha256_file(a.file)
    step = m["steps"].setdefault(a.step, {"status": "in_flight", "files": {},
                                          "tokens": 0, "started": _now(), "notes": []})
    step["files"][a.file] = digest
    if a.seat:
        key = f"{a.step}/{a.seat}"
        m["seats"][key] = {"status": "committed", "file": a.file, "sha256": digest,
                           "flags": a.flag or []}
    if a.tokens:
        step["tokens"] = step.get("tokens", 0) + a.tokens
    save_manifest(a.manifest, m)
    print(f"committed {a.file} sha256={digest[:12]}… -> {a.step}" + (f"/{a.seat}" if a.seat else ""))
    return 0


def cmd_tick(a):
    m = load_manifest(a.manifest)
    if m is None:
        print("ERROR: scoreboard missing", file=sys.stderr)
        return 1
    step = m["steps"].setdefault(a.step, {"status": "pending", "files": {}, "tokens": 0, "notes": []})
    if a.status:
        step["status"] = a.status
        if a.status == "in_flight":
            step["started"] = _now()
        if a.status in ("done", "degraded", "failed"):
            step["finished"] = _now()
    if a.tokens:
        step["tokens"] = step.get("tokens", 0) + a.tokens
    if a.note:
        step.setdefault("notes", []).append(a.note)
    if a.degradation:
        m["degradations"].append({"step": a.step, "note": a.degradation, "at": _now()})
    if a.seat_absent:
        m["seats"][f"{a.step}/{a.seat_absent}"] = {"status": "absent"}
    save_manifest(a.manifest, m)
    print(f"tick: {a.step} -> {step['status']}")
    return 0


def cmd_status(a):
    m = load_manifest(a.manifest)
    if m is None:
        print("no scoreboard — run not started (registrar.py init)")
        return 1
    print(f"RUN {m['run_id']}  (created {m.get('created')})")
    total_tokens = 0
    for name, s in m["steps"].items():
        total_tokens += s.get("tokens", 0)
        nfiles = len(s.get("files", {}))
        print(f"  {name:14s} {s.get('status','?'):9s} files={nfiles} tokens={s.get('tokens',0)}")
    committed = [k for k, v in m["seats"].items() if v.get("status") == "committed"]
    absent = [k for k, v in m["seats"].items() if v.get("status") == "absent"]
    flags = [f"{k}:{','.join(v['flags'])}" for k, v in m["seats"].items() if v.get("flags")]
    print(f"  seats committed: {len(committed)}  absent: {absent or 'none'}")
    if flags:
        print(f"  lint flags: {flags}")
    if m["degradations"]:
        print("  degradations:")
        for d in m["degradations"]:
            print(f"    - [{d['step']}] {d['note']}")
    print(f"  tokens total: {total_tokens}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default="run_manifest.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--date", required=True)
    s = sub.add_parser("validate")
    s.add_argument("--file", required=True); s.add_argument("--round", type=int, choices=(1, 2), required=True)
    s.add_argument("--candidates", default=None); s.add_argument("--phase4", default=None)
    s = sub.add_parser("commit")
    s.add_argument("--step", required=True); s.add_argument("--file", required=True)
    s.add_argument("--seat", default=None); s.add_argument("--tokens", type=int, default=0)
    s.add_argument("--flag", action="append", default=None)
    s = sub.add_parser("tick")
    s.add_argument("--step", required=True); s.add_argument("--status", default=None,
        choices=(None, "pending", "in_flight", "done", "degraded", "failed"))
    s.add_argument("--tokens", type=int, default=0); s.add_argument("--note", default=None)
    s.add_argument("--degradation", default=None); s.add_argument("--seat-absent", dest="seat_absent", default=None)
    s.add_argument("--seat", default=None)
    sub.add_parser("status")
    a = p.parse_args()
    return {"init": cmd_init, "validate": cmd_validate, "commit": cmd_commit,
            "tick": cmd_tick, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
