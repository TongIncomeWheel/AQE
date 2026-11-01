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

v5 §6b bracket-basis lint (flag): a vote/nomination whose stated basis is
bracket validity ALONE is flagged so the pattern is visible on the scoreboard
instead of covert. The crowding audit itself lives in purity_check.py.

R1 ENFORCEMENT (reject) — PM ruling 2026-08-14, restated 2026-09-05, made
mechanical 2026-09-06 after the same card regression surfaced a third time:
"a bracket, its validity, its risk%, its stop type and its R:R are NEVER a
reason to reject a name. The committee chooses on momentum and structure; the
bracket is the PM's last step to narrow a chosen idea." A card can say the
wrong thing; the registrar cannot let it through. Therefore:
  * Round 2: an OPPOSE whose `reason` / `opposing_case` uses a bracket term as a
    disqualifier (bracket + reject-verb in the same text) => REJECT the form.
  * Round 1: a `shortfall_reason` that cites a bracket term => REJECT the form
    (a seat may not nominate fewer names because brackets were invalid).
  * Any other bracket mention (SUPPORT/ABSTAIN reason, conviction_change) is
    still flagged BRACKET_BASIS / BRACKET_MENTION for the scoreboard, never
    rejected — stating the invalidation level is exactly what R1 asks for.
The rejection text tells the seat what to re-file: judge on signals, state the
level as information. One re-spawn, then absent — same ladder as any REJECT.
"""
import argparse, datetime, glob, hashlib, json, os, re, sys

MAX_FORM_BYTES = 24 * 1024
R1_REASON_MAX = 300
# ---- THE REDESIGN (PM 2026-10-30; RULINGS R31-R36). Duplicated from pma_pipeline.py on purpose: the
# registrar is copied on its own into run dirs (the tick tests do exactly that) and must not import
# the pipeline. tests.test_roster_is_seven_deciders_plus_qa asserts the two copies agree.
DECIDERS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]
QA_SEAT = "steenbarger"
R33_EFFECTIVE = "2026-11-01"   # forms dated from here: shortlist cap, decider-only ballots, the case form
SHORTLIST_CAP = 6              # R33
SLATE_CAP = 15                 # R34
FLOOR_MSG_CAP = 2              # R36 (counted across files by `pma_pipeline.py floor-check`)
CASE_LIMITS = {"for": 400, "against": 400, "entry_trigger": 200, "wrong_if": 200,
               "would_change_my_mind": 250}
CASE_REQUIRED = ("for", "against", "entry_trigger", "wrong_if", "horizon_sessions",
                 "would_change_my_mind", "cannot_see")
RATIFY_ANSWERS = ("AGREE", "AGREE_WITH_RESERVATION", "OBJECT")


def _new_regime(form):
    """True when the form is dated on/after R33_EFFECTIVE: the 30 Oct redesign binds. Earlier forms
    (the 2026-09-06 fixtures, the Oct runs) are validated exactly as they were filed."""
    return str(form.get("date", "")) >= R33_EFFECTIVE
R2_LIMITS = {"reason": 500, "conviction_change": 250, "opposing_case": 300,
             "self_counter": 300, "falsifier": 250, "challenge_reply": 400,
             "o_a_note": 250, "o_b_stop_honored": 150, "o_c_invalidation": 250}
BRACKET_ONLY = re.compile(r"bracket[._ ]?(valid|invalid)", re.I)
SIGNAL_WORDS = re.compile(r"(structure|momentum|volume|rs_|elder|mp_|div_|squeeze|vwap|flow|energy|sector|leader|conviction|base|coil|stack|ma_\d)", re.I)
# R1 enforcement vocabulary. BRACKET_TERM = any way a seat can point at the engine bracket;
# REJECT_VERB = any way a seat can turn it into a disqualifier. Both in one OPPOSE text (or a
# BRACKET_TERM anywhere in a shortfall_reason) is an R1 violation => REJECT.
BRACKET_TERM = re.compile(
    r"(bracket[._ ]?(valid|invalid|rr|risk|stop|price|atr)"
    r"|malformed[_ ]bracket"
    r"|atr[_ ]fallback"
    r"|risk[_ ]?pct"
    r"|\brr[_ ]?tp\d?\b|\brr\s*[<>=]|\bR:R\b|reward[- ]to[- ]risk|risk[- ]?reward"
    r"|no (valid|usable|tradeable|tradable|structural) (bracket|stop)"
    r"|bracket (is|was) (invalid|false|missing|unusable|absent)"
    r"|stop (is |sits )?(too )?wide"
    r"|(invalid|missing|unusable|no) bracket)", re.I)
REJECT_VERB = re.compile(
    r"(reject|disqualif|cannot (be )?(take|taken|own|hold|enter|buy)|can't (take|own|enter|buy)"
    r"|not (a|my) (setup|position|trade)|no setup|untradeable|untradable|not tradeable|not tradable"
    r"|rules? (it |this |the name )?out|throws? (it |this )?out|excluded?|fails?\b|fatal"
    r"|hard (pass|no)|at any (size|conviction)|no (entry|nomination)|do not nominate|cannot nominate"
    r"|oppose[sd]? (because|on|for)|too (wide|thin|large|big|risky))", re.I)


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


def _bracket_as_reject(texts):
    """R1 enforcement: True when a bracket term is used as a disqualifier.
    Returns the matched bracket term + verb so the rejection names them."""
    joined = " ".join(t for t in texts if t)
    bt = BRACKET_TERM.search(joined)
    if not bt:
        return None
    rv = REJECT_VERB.search(joined)
    if not rv:
        return None
    return (bt.group(0), rv.group(0))


R1_TEXT = ("R1 VIOLATION — bracket is never a reject (PM ruling 2026-08-14 / 2026-09-06). "
           "The committee chooses on momentum and structure; the bracket is the PM's last step. "
           "Re-file judging on signals; state the bracket/invalidation level as information only.")


def validate_round1(form, universe):
    errs, flags = [], []
    for req in ("voice", "date", "nominations", "held_review"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    noms = form.get("nominations", [])
    # R16 (PM ruling 2026-09-24, enforced from 2026-09-25): there is NO per-ballot nomination cap.
    # This line read `len(noms) > 10` until the 2026-09-25 run, where it REJECTED minervini (11) and
    # raschke (13) on the first morning the seats were told the admission cap was gone -- the same
    # defect R16 exists to kill, one layer down. A seat files what its method supports; the room is
    # as large as the seats made it. Padding is still wrong, but it is a judgment matter for the
    # seat's own card and for the challenge seats to attack, never a silent truncation by the
    # registrar. A ballot is still bounded by MAX_FORM_BYTES, and a seat whose honest ballot does not
    # fit trims its checklist_trace, never a nomination.
    if not isinstance(noms, list):
        errs.append("nominations: must be a list")
        noms = noms if isinstance(noms, list) else []
    # R31 + R33 (PM 2026-10-30), binding on ballots dated from 2026-11-01. The R16 floor stands: every
    # nomination that IS filed is seated. The cap is on how many one decider may put forward.
    if _new_regime(form):
        if form.get("voice") not in DECIDERS:
            errs.append(f"voice {form.get('voice')!r} is not a decider seat (R31: {', '.join(DECIDERS)}); "
                        f"the QA seat and benched or stood-down voices do not nominate")
        if len(noms) > SHORTLIST_CAP:
            errs.append(f"nominations: {len(noms)} > {SHORTLIST_CAP} -- R33 (PM 2026-10-30): a decider shortlists at "
                        f"most {SHORTLIST_CAP}; fewer is valid and is never padded. Re-file the {SHORTLIST_CAP} your "
                        f"method ranks highest; the rest are not lost -- say in `declarations` which names you cut and why.")
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
        elif BRACKET_TERM.search(n.get("reason", "") or ""):
            flags.append(f"BRACKET_MENTION:{t}")
    sf = form.get("shortfall_reason")
    if isinstance(sf, str) and BRACKET_TERM.search(sf):
        errs.append(f"shortfall_reason cites a bracket term ({BRACKET_TERM.search(sf).group(0)!r}) — "
                    f"a seat may not nominate fewer names because engine brackets were invalid. {R1_TEXT}")
    return errs, flags


def _cond():
    """conditions.py lives beside this file; imported lazily so the registrar's other commands run
    even where only registrar.py was copied (the tick tests do exactly that)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import conditions
    return conditions
# Ballots dated on or after this carry a `conditions` block on every SUPPORT (D123). Earlier ballots
# (and the 2026-09-06 regression fixtures) are validated as they were filed.
D123_EFFECTIVE = "2026-10-02"

def _validate_case(case, where):
    """R36 (PM 2026-10-30): the CASE FORM on every name -- reasons both ways. Stance and the vote's own
    reason live on the vote row; this block carries what a seat must also say so the floor, the slate
    and the scorecard can read it: the case FOR, the case AGAINST, the entry trigger it would use,
    where it is wrong, its horizon in sessions, what would change its mind, what it cannot see."""
    errs = []
    if not isinstance(case, dict):
        return [f"{where}.case: required on every vote from 2026-11-01 (R36 case form) -- "
                f"{{for, against, entry_trigger, wrong_if, horizon_sessions, would_change_my_mind, cannot_see}}"]
    for k in CASE_REQUIRED:
        if k not in case:
            errs.append(f"{where}.case: missing {k}")
    for k, cap in CASE_LIMITS.items():
        v = case.get(k)
        if k in case and (not isinstance(v, str) or not v.strip()):
            errs.append(f"{where}.case.{k}: must be a non-empty string (reasons both ways -- never blank)")
        elif isinstance(v, str) and len(v) > cap:
            errs.append(f"{where}.case.{k}: {len(v)} chars > cap {cap} (essay leak)")
    h = case.get("horizon_sessions")
    if "horizon_sessions" in case and (not isinstance(h, int) or isinstance(h, bool) or not (1 <= h <= 120)):
        errs.append(f"{where}.case.horizon_sessions: integer 1-120 trading sessions (R35: each voice is graded on its own horizon)")
    cs = case.get("cannot_see")
    if "cannot_see" in case:
        if not isinstance(cs, list) or any(not isinstance(x, str) or len(x) > 80 for x in cs):
            errs.append(f"{where}.case.cannot_see: list of short strings (<=80 chars; [] when nothing is missing)")
    return errs


def validate_round2(form, universe, deliberation_set, partial=False):
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
    new_regime = _new_regime(form)
    if new_regime and form.get("voice") not in DECIDERS:
        errs.append(f"voice {form.get('voice')!r} is not a decider seat (R31: {', '.join(DECIDERS)}); only deciders vote")
    seen = set()
    for i, v in enumerate(votes):
        w = f"votes[{i}]"
        t = v.get("ticker")
        if not t:
            errs.append(f"{w}: missing ticker")
            continue
        if new_regime:
            errs.extend(_validate_case(v.get("case"), w + f" {t}"))
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
        texts = [v.get("reason", ""), v.get("opposing_case") or "", v.get("conviction_change") or ""]
        if stance == "OPPOSE":
            hit = _bracket_as_reject(texts)
            if hit:
                errs.append(f"{w}: OPPOSE on {t} uses a bracket as the disqualifier "
                            f"({hit[0]!r} + {hit[1]!r}). {R1_TEXT}")
        if _bracket_lint(texts):
            flags.append(f"BRACKET_BASIS:{t}")
        elif BRACKET_TERM.search(" ".join(x for x in texts if x)):
            flags.append(f"BRACKET_MENTION:{t}")
        # D123 (PM 2026-10-02): the vote itself is unchanged; the analyst ALSO writes when they act and
        # when they are wrong, in words from contracts/condition_vocab.json, so AQE can watch exactly that.
        if str(form.get("date", "")) >= D123_EFFECTIVE:
            errs.extend(_cond().validate_block(form.get("voice"), stance, v.get("conditions"), w + f" {t}"))
        elif v.get("conditions") is not None:
            errs.extend(_cond().validate_block(form.get("voice"), stance, v.get("conditions"), w + f" {t}"))
    if deliberation_set is not None:
        ds = set(deliberation_set)
        missing, extra = ds - seen, seen - ds
        # SPLIT BALLOTS (R16 support, PM ruling 2026-09-24). Under R16 the room is as large as the
        # seats made it, so a seat's votes no longer fit in one MAX_FORM_BYTES file (~953B per name
        # measured over 11 real ballots on 2026-09-24 => ~25 names is the single-file ceiling). A
        # seat may file part 1 of N, part 2 of N ... and each PART is validated on its own: it must
        # stay inside the deliberation set, but it is NOT required to cover it. `registrar.py merge`
        # then proves the parts together cover the set exactly, before DECIDE runs. A FILE SIZE LIMIT
        # MUST NEVER AGAIN DECIDE WHICH OF THE PM'S ANALYSTS ARE HEARD.
        if extra:
            errs.append(f"votes filed on names OUTSIDE the deliberation set: {sorted(extra)}")
        if missing and not partial:
            errs.append(f"votes missing for deliberation-set names: {sorted(missing)} "
                        f"(a seat splitting its ballot passes --part N --of M, and `registrar.py merge` "
                        f"proves the parts cover the set)")
    return errs, flags



# ---------------------------------------------------------------------------
# THE DELIBERATION FORMS (R34-R36, PM 2026-10-30). Shapes documented in contracts/*.schema.json;
# validated here in pure python like every other form. The registrar checks ONE file's shape and
# membership; cross-file counting (floor caps, objection totals, hold-once) is pma_pipeline.py's
# `floor-check` and `ratify-count`. Nothing here judges a reason -- only that the form is complete.
# ---------------------------------------------------------------------------
def _str(errs, obj, field, cap, where, required=True):
    v = obj.get(field)
    if v is None:
        if required:
            errs.append(f"{where}: missing {field}")
        return
    if not isinstance(v, str) or (required and not v.strip()):
        errs.append(f"{where}.{field}: must be a non-empty string")
    elif len(v) > cap:
        errs.append(f"{where}.{field}: {len(v)} chars > cap {cap} (essay leak)")


def validate_challenge(form, universe):
    """Steenbarger's challenge document (R36 round 1b): crowding, extension and overlap reads on the
    room BEFORE anyone votes. The shape the seat has filed since 2026-09-06, now written down."""
    errs, flags = [], []
    for req in ("voice", "date", "seat_kind", "findings", "names_read"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    if form.get("seat_kind") != "challenge":
        errs.append("seat_kind: must be 'challenge'")
    if _new_regime(form) and form.get("voice") != QA_SEAT:
        errs.append(f"voice {form.get('voice')!r}: from 2026-11-01 the challenge document is filed by {QA_SEAT} only (R31)")
    fnd = form.get("findings")
    if not isinstance(fnd, list):
        errs.append("findings: must be a list"); fnd = []
    for i, f in enumerate(fnd):
        w = f"findings[{i}]"
        if not isinstance(f, dict):
            errs.append(f"{w}: must be an object"); continue
        for req in ("scope", "kind", "claim", "evidence"):
            if not f.get(req):
                errs.append(f"{w}: missing {req}")
        _str(errs, f, "claim", 500, w); _str(errs, f, "evidence", 400, w)
        _str(errs, f, "addressed_to", 120, w, required=False)
        tk = f.get("ticker")
        if tk and universe is not None and tk not in universe:
            errs.append(f"{w}: ticker {tk} NOT IN UNIVERSE")
        if _bracket_as_reject([f.get("claim", ""), f.get("evidence", "")]):
            errs.append(f"{w}: uses a bracket as a disqualifier. {R1_TEXT}")
    for i, ob in enumerate(form.get("obligations") or []):
        w = f"obligations[{i}]"
        for req in ("seat", "ticker", "what_is_owed"):
            if not ob.get(req):
                errs.append(f"{w}: missing {req}")
        _str(errs, ob, "what_is_owed", 300, w)
    nr = form.get("names_read")
    if "names_read" in form and (not isinstance(nr, int) or nr < 0):
        errs.append("names_read: integer >= 0 (how many room names the seat actually read)")
    if "names_read" in form and nr == 0 and fnd:
        errs.append("names_read is 0 but findings were filed -- a challenge on names not read is not evidence")
    return errs, flags


def validate_floor_message(form, deliberation_set, contested=None):
    """One floor message (R36 round 3). Addressed to a seat by name or to the room; answers a point,
    concedes or holds; says what moved it when it changed its mind."""
    errs, flags = [], []
    for req in ("voice", "date", "ticker", "msg_id", "to", "text", "stance_now", "changed_mind"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    v = form.get("voice")
    if v not in DECIDERS and v != QA_SEAT:
        errs.append(f"voice {v!r}: only a decider, or {QA_SEAT} when called on by name, speaks on the floor (R31)")
    t = form.get("ticker")
    if deliberation_set is not None and t not in set(deliberation_set):
        errs.append(f"ticker {t} is not in the deliberation set")
    if contested is not None and t not in set(contested):
        errs.append(f"ticker {t} is not a CONTESTED name on the board -- the floor opens on contested names only (R36)")
    to = form.get("to")
    if to != "room" and to not in DECIDERS and to != QA_SEAT:
        errs.append(f"to: must be a decider by name, '{QA_SEAT}', or 'room'")
    if to == v:
        errs.append("to: a seat does not address itself")
    _str(errs, form, "text", 600, "message")
    _str(errs, form, "msg_id", 64, "message")
    irt = form.get("in_reply_to")
    if irt is not None and not isinstance(irt, str):
        errs.append("in_reply_to: msg_id string or null")
    if form.get("stance_now") not in ("SUPPORT", "OPPOSE", "ABSTAIN", "NO_VOTE"):
        errs.append("stance_now: SUPPORT/OPPOSE/ABSTAIN (a decider) or NO_VOTE (the QA seat)")
    if v == QA_SEAT and form.get("stance_now") != "NO_VOTE":
        errs.append(f"{QA_SEAT} carries stance_now NO_VOTE -- the QA seat never votes (R31)")
    cm = form.get("changed_mind")
    if "changed_mind" in form and not isinstance(cm, bool):
        errs.append("changed_mind: true/false")
    if cm is True:
        _str(errs, form, "what_moved_me", 300, "message")
    if _bracket_as_reject([form.get("text", "")]):
        errs.append(f"text uses a bracket as a disqualifier. {R1_TEXT}")
    return errs, flags


def validate_slate(form, deliberation_set):
    """The Chair's slate (R34/R36 round 4): at most 15 tickets across ADVANCE and WATCH, each with its
    trigger, wrong-if, horizon, why the room agrees and who dissents. The Chair uses only what the
    seats said; the registrar checks completeness and membership, never the reasoning."""
    errs, flags = [], []
    for req in ("date", "chair", "tickets"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    if form.get("chair") != "chair":
        errs.append("chair: must be 'chair' -- the Chair is not a voice (R36)")
    tk = form.get("tickets")
    if not isinstance(tk, list):
        errs.append("tickets: must be a list"); tk = []
    if len(tk) > SLATE_CAP:
        errs.append(f"tickets: {len(tk)} > {SLATE_CAP} -- R34 (PM 2026-10-30): the slate is at most {SLATE_CAP} across "
                    f"ADVANCE and WATCH. A ceiling, not a target; nothing is padded to reach it either.")
    seen = set()
    ds = set(deliberation_set) if deliberation_set is not None else None
    for i, x in enumerate(tk):
        w = f"tickets[{i}]"
        if not isinstance(x, dict):
            errs.append(f"{w}: must be an object"); continue
        t = x.get("ticker")
        if not t:
            errs.append(f"{w}: missing ticker"); continue
        if t in seen:
            errs.append(f"{w}: duplicate ticker {t}")
        seen.add(t)
        if ds is not None and t not in ds:
            errs.append(f"{w}: {t} is not in the deliberation set -- the Chair may not add a name the room never voted")
        if x.get("verdict") not in ("ADVANCE", "WATCH"):
            errs.append(f"{w}: verdict must be ADVANCE or WATCH")
        for f_, cap in (("entry_trigger", 200), ("wrong_if", 200), ("why_agreed", 400)):
            _str(errs, x, f_, cap, w)
        h = x.get("horizon_sessions")
        if not isinstance(h, int) or isinstance(h, bool) or not (1 <= h <= 120):
            errs.append(f"{w}: horizon_sessions integer 1-120")
        dis = x.get("dissent")
        if not isinstance(dis, list):
            errs.append(f"{w}: dissent must be a list ([] when nobody dissents)")
        else:
            for j, d in enumerate(dis):
                if not isinstance(d, dict) or d.get("voice") not in DECIDERS or not d.get("why"):
                    errs.append(f"{w}.dissent[{j}]: {{voice: a decider, why: text}}")
                elif len(str(d.get("why"))) > 300:
                    errs.append(f"{w}.dissent[{j}].why: > 300 chars")
        if _bracket_as_reject([x.get("why_agreed", ""), x.get("wrong_if", "")]):
            errs.append(f"{w}: uses a bracket as a disqualifier. {R1_TEXT}")
    return errs, flags


def validate_ratification(form, slate):
    """A decider's ratification (R34/R36 round 5): one answer per slate ticket -- AGREE,
    AGREE_WITH_RESERVATION (say the reservation) or OBJECT (say the objection and the ONE thing that
    would clear it). Covers the slate exactly."""
    errs, flags = [], []
    for req in ("voice", "date", "tickets"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    if form.get("voice") not in DECIDERS:
        errs.append(f"voice {form.get('voice')!r} is not a decider (R31); only deciders ratify")
    rows = form.get("tickets")
    if not isinstance(rows, list):
        errs.append("tickets: must be a list"); rows = []
    seen = set()
    for i, r in enumerate(rows):
        w = f"tickets[{i}]"
        t = r.get("ticker") if isinstance(r, dict) else None
        if not t:
            errs.append(f"{w}: missing ticker"); continue
        if t in seen:
            errs.append(f"{w}: duplicate ticker {t}")
        seen.add(t)
        ans = r.get("answer")
        if ans not in RATIFY_ANSWERS:
            errs.append(f"{w} {t}: answer must be one of {list(RATIFY_ANSWERS)}")
        if ans == "AGREE_WITH_RESERVATION":
            _str(errs, r, "reservation", 300, f"{w} {t}")
        if ans == "OBJECT":
            _str(errs, r, "objection", 300, f"{w} {t}")
            _str(errs, r, "would_clear", 200, f"{w} {t}")
            if _bracket_as_reject([r.get("objection", "")]):
                errs.append(f"{w} {t}: OBJECT uses a bracket as the disqualifier. {R1_TEXT}")
    if slate is not None:
        st = {x["ticker"] for x in slate.get("tickets", []) if isinstance(x, dict) and x.get("ticker")}
        missing, extra = st - seen, seen - st
        if missing:
            errs.append(f"no answer for slate tickets {sorted(missing)} -- every decider answers every ticket (R34)")
        if extra:
            errs.append(f"answers on names not on the slate: {sorted(extra)}")
    return errs, flags


def validate_qa_note(form, slate):
    """Steenbarger's QA note (R36 round 6): did every decider read evidence; are reasons leaning on the
    same anchors; did a point go unanswered; does the slate say what the deciders said. May HOLD a
    ticket -- once per ticket -- which reopens the floor and the ratification for that ticket only."""
    errs, flags = [], []
    for req in ("voice", "date", "evidence_read", "shared_anchors", "unanswered_points",
                "slate_says_what_deciders_said", "note", "holds"):
        if req not in form:
            errs.append(f"missing required field: {req}")
    if form.get("voice") != QA_SEAT:
        errs.append(f"voice: the QA note is {QA_SEAT}'s (R31)")
    er = form.get("evidence_read")
    if not isinstance(er, list):
        errs.append("evidence_read: list of {voice, read: bool, note}")
    else:
        for j, e in enumerate(er):
            if not isinstance(e, dict) or e.get("voice") not in DECIDERS or not isinstance(e.get("read"), bool):
                errs.append(f"evidence_read[{j}]: {{voice: a decider, read: true/false, note}}")
        covered = {e.get("voice") for e in er if isinstance(e, dict)}
        if isinstance(er, list) and covered != set(DECIDERS):
            errs.append(f"evidence_read must cover every decider once; missing {sorted(set(DECIDERS) - covered)}, "
                        f"extra {sorted(covered - set(DECIDERS))}")
    sa = form.get("shared_anchors")
    if not isinstance(sa, list) or any(not isinstance(x, str) or len(x) > 200 for x in sa):
        errs.append("shared_anchors: list of short strings ([] when none)")
    up = form.get("unanswered_points")
    if not isinstance(up, list):
        errs.append("unanswered_points: list of {voice, ticker, point}")
    else:
        for j, u in enumerate(up):
            if not isinstance(u, dict) or not u.get("voice") or not u.get("ticker") or not u.get("point"):
                errs.append(f"unanswered_points[{j}]: {{voice, ticker, point}}")
    if not isinstance(form.get("slate_says_what_deciders_said"), bool):
        errs.append("slate_says_what_deciders_said: true/false")
    _str(errs, form, "note", 800, "qa")
    holds = form.get("holds")
    if not isinstance(holds, list):
        errs.append("holds: list of {ticker, question} ([] for no hold)"); holds = []
    st = ({x["ticker"] for x in slate.get("tickets", []) if isinstance(x, dict) and x.get("ticker")}
          if slate is not None else None)
    held = set()
    for j, h in enumerate(holds):
        w = f"holds[{j}]"
        if not isinstance(h, dict) or not h.get("ticker") or not h.get("question"):
            errs.append(f"{w}: {{ticker, question}}"); continue
        if h["ticker"] in held:
            errs.append(f"{w}: {h['ticker']} held twice -- ONE hold per ticket, then the result stands (R36)")
        held.add(h["ticker"])
        if st is not None and h["ticker"] not in st:
            errs.append(f"{w}: {h['ticker']} is not on the slate; a hold reopens a slate ticket only")
        _str(errs, h, "question", 300, w)
    return errs, flags


def cmd_merge(a):
    """R16 (PM ruling 2026-09-24): stitch a seat's split round-2 ballot parts into one form and PROVE
    the parts together cover the deliberation set exactly -- no name missing, no name twice, no name
    from outside. This is the check that makes split ballots safe: the per-part validation is
    deliberately permissive about coverage, so coverage has to be proved exactly once, here, before
    DECIDE computes a verdict on it.

    Why this exists: before R16 the room was capped at 24 names because a seat's votes had to fit in
    one MAX_FORM_BYTES file. That is a file size limit, and it was silently binning the PM's analysts'
    picks -- 64 of 107 nominations over three runs. The room size is now set by how many names the
    seats nominated. Ballots split; nobody is cut."""
    parts = sorted(glob.glob(a.glob))
    if not parts:
        print(json.dumps({"result": "REJECT", "errors": [f"no ballot parts matched {a.glob!r}"]})); return 1
    merged, errs, seen, meta = None, [], {}, []
    for f in parts:
        raw = open(f, "rb").read()
        if len(raw) > MAX_FORM_BYTES:
            errs.append(f"{os.path.basename(f)} is {len(raw)}B > {MAX_FORM_BYTES}B — split it further"); continue
        try:
            form = json.loads(raw)
        except json.JSONDecodeError as e:
            errs.append(f"{os.path.basename(f)}: not valid JSON: {e}"); continue
        meta.append({"file": os.path.basename(f), "bytes": len(raw), "votes": len(form.get("votes", [])),
                     "sha256": hashlib.sha256(raw).hexdigest()[:12]})
        if merged is None:
            merged = {k: v for k, v in form.items() if k != "votes"}; merged["votes"] = []
        else:
            for k in ("voice", "date", "round"):
                if form.get(k) != merged.get(k):
                    errs.append(f"{os.path.basename(f)}: {k}={form.get(k)!r} does not match part 1's {merged.get(k)!r}")
            for k in ("declarations", "data_gaps"):
                if form.get(k): merged.setdefault(k, []).extend(x for x in form[k] if x not in merged.get(k, []))
        for v in form.get("votes", []):
            t = v.get("ticker")
            if t in seen:
                errs.append(f"duplicate vote on {t} ({seen[t]} and {os.path.basename(f)})"); continue
            seen[t] = os.path.basename(f); merged["votes"].append(v)
    if merged is None:
        print(json.dumps({"result": "REJECT", "errors": errs or ["no readable part"]})); return 1
    if a.phase4:
        p4, err = load_json(a.phase4, "phase4")
        if err: errs.append(err)
        else:
            ds = set(p4.get("deliberation_set") or [])
            missing, extra = ds - set(seen), set(seen) - ds
            if missing: errs.append(f"parts do not cover the deliberation set — missing {sorted(missing)}")
            if extra:   errs.append(f"parts vote on names outside the deliberation set — {sorted(extra)}")
    if errs:
        print(json.dumps({"result": "REJECT", "errors": errs, "parts": meta})); return 1
    merged["votes"].sort(key=lambda v: (p4.get("deliberation_set") or []).index(v["ticker"]) if a.phase4 else v["ticker"])
    merged["merged_from"] = meta
    with open(a.out, "w") as fh: json.dump(merged, fh, indent=1)
    print(json.dumps({"result": "OK", "voice": merged.get("voice"), "out": a.out,
                      "votes": len(merged["votes"]), "parts": meta,
                      "bytes": os.path.getsize(a.out)}))
    return 0


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
    kind = getattr(a, "kind", None)
    if (a.round is None) == (kind is None):
        print(json.dumps({"result": "REJECT", "errors": ["pass exactly one of --round 1|2 or --kind challenge|floor|slate|ratify|qa"]}))
        return 1
    dset = None
    if (a.round == 2 or kind in ("floor", "slate")) and a.phase4:
        p4, err = load_json(a.phase4, "phase4")
        if err:
            print(json.dumps({"result": "REJECT", "errors": [err]}))
            return 1
        dset = p4.get("deliberation_set")
    slate = None
    if kind in ("ratify", "qa"):
        if not getattr(a, "slate", None):
            print(json.dumps({"result": "REJECT", "errors": [f"--slate slate.json is required to validate a {kind} form"]}))
            return 1
        slate, err = load_json(a.slate, "slate")
        if err:
            print(json.dumps({"result": "REJECT", "errors": [err]}))
            return 1
    contested = None
    if kind == "floor" and getattr(a, "board", None):
        board, err = load_json(a.board, "board")
        if err:
            print(json.dumps({"result": "REJECT", "errors": [err]}))
            return 1
        contested = board.get("contested")
    if a.round == 1:
        errs, flags = validate_round1(form, universe)
    elif a.round == 2:
        errs, flags = validate_round2(form, universe, dset, partial=bool(getattr(a, "of", None) and a.of > 1))
    elif kind == "challenge":
        errs, flags = validate_challenge(form, universe)
    elif kind == "floor":
        errs, flags = validate_floor_message(form, dset, contested)
    elif kind == "slate":
        errs, flags = validate_slate(form, dset)
    elif kind == "ratify":
        errs, flags = validate_ratification(form, slate)
    else:
        errs, flags = validate_qa_note(form, slate)

    # --- did this seat read the packet, or invent the numbers? (PM ruling 2026-09-16) ------------
    # R2 asks a seat to prove it read the packet by returning its md5. No seat has a hashing tool,
    # so on 2026-09-15 all eleven declared NOT_VERIFIED. The PM ruled the tamper check overkill --
    # AQE writes the file, the voices read it, nobody is attacking it -- and named the exposure that
    # actually matters: a seat that does not read the packet and writes plausible numbers instead.
    # A md5 could never catch that; a seat can hash a file perfectly and still fabricate every
    # figure. figure_audit checks the claim a seat is actually making when it writes "ma50 218.30":
    # that the row it was handed says so. Measured before being given teeth -- zero findings across
    # all 231 real votes of 2026-09-15, and it catches a single altered digit.
    if a.packet:
        if not os.path.exists(a.packet):
            errs.append(f"--packet {a.packet} does not exist; cannot audit cited figures")
        else:
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import figure_audit
                bad = figure_audit.audit(form, open(a.packet, encoding="utf-8",
                                                    errors="replace").read())
                for b in bad:
                    errs.append(
                        f"votes[{b['ticker']}].{b['field']}: cites {b['claimed']}={b['figure']}, "
                        f"which is NOT in the packet row this seat was given — FABRICATED FIGURE, "
                        f"the whole return is untrusted")
            except Exception as e:                       # never invent a rejection on a tool fault
                flags.append(f"FIGURE_AUDIT_UNAVAILABLE:{e.__class__.__name__}")
    result = "REJECT" if errs else "OK"
    print(json.dumps({"result": result, "errors": errs, "flags": flags,
                      "voice": form.get("voice"), "sha256": hashlib.sha256(raw).hexdigest()}))
    return 1 if errs else 0


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
    step = m["steps"].setdefault(a.step, _blank_step())
    step.setdefault("started", _now())
    # FIX 2026-09-16: preflight_run.py stamp creates steps["GATHER"] carrying ONLY tool_hashes, so
    # the entry exists but has no "files" key and every commit to GATHER after a stamp died on
    # KeyError: 'files'. Order-dependent crash in the one step that must record the run's inputs.
    step.setdefault("files", {})
    if a.file not in step["files"]:
        _cost(step)["returned_bytes"] += os.path.getsize(a.file)   # every committed artifact is a return
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


# ---------------------------------------------------------------- produces verification (2026-09-16)
_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.abspath(os.path.join(_HERE, ".."))


def _declared_produces(step_name):
    """Read this step's declared produces[] from RUN.yaml -- the run map is the contract.

    WHY THIS EXISTS. RUN.yaml's GATHER declares it produces phase4_ledger.json and
    verdict_ledger.json at the run root, and every downstream tool default resolves them there.
    On 2026-09-15 they landed under data/ instead. Nothing noticed at GATHER. The run ticked
    GATHER 'done', ran eleven model seats costing real tokens, and only at REPEAT-WATCH -- four
    steps and ~115k tokens later -- did anything complain, at which point the operator recovered
    by hand-passing data/... paths: the adapter R6 forbids, applied three times in one run.

    A step that did not put its artifacts where it said it would has not finished. Catching that
    at the step that caused it is the difference between re-running one tool step and re-running
    a committee. Returns [] when the map cannot be read -- this check never invents a failure.
    """
    try:
        sys.path.insert(0, _HERE)
        import preflight_run
        M = preflight_run.load_yaml("RUN.yaml")
    except Exception:
        return []
    step = next((s for s in (M.get("steps") or []) if s.get("name") == step_name), None)
    if not step:
        return []
    out = step.get("produces") or []
    # review finding 7 (2026-11-01): globs used to be dropped, so a model round with ZERO forms ticked done.
    # A glob now stays in the list and must match at least one file; a <placeholder> or remote: path is declared
    # on the scoreboard but not checked here (the tool that writes it verifies its own read-back).
    return [f for f in out if isinstance(f, str) and "<" not in f and not f.startswith("remote:")]


def _missing_produces(step_name):
    """Declared artifacts that are not at their declared path. A trailing / means a directory."""
    missing = []
    for f in _declared_produces(step_name):
        target = f.rstrip("/")
        if any(ch in target for ch in "*?["):
            if not glob.glob(target, recursive=True):
                missing.append(f + " (glob matched nothing)")
        elif not os.path.exists(target):
            missing.append(f)
    return missing


def cmd_tick(a):
    m = load_manifest(a.manifest)
    if m is None:
        print("ERROR: scoreboard missing", file=sys.stderr)
        return 1
    step = m["steps"].setdefault(a.step, _blank_step())
    step.setdefault("started", _now())
    if a.status == "done" and not a.force_incomplete:
        gap = _missing_produces(a.step)
        if gap:
            print(f"REFUSED: {a.step} declares it produces {gap} and they are not at those paths.",
                  file=sys.stderr)
            print("  RUN.yaml's produces[] is the contract. A step that did not put its artifacts",
                  file=sys.stderr)
            print("  where it said it would has NOT finished -- do not tick it done and do not",
                  file=sys.stderr)
            print("  re-point the next tool at wherever they actually landed: that adapter is",
                  file=sys.stderr)
            print("  forbidden (R6). Fix the step so it writes to the declared path.", file=sys.stderr)
            print("  A genuinely degraded run records it: --status degraded, or --force-incomplete",
                  file=sys.stderr)
            print("  --note '<why>' which writes the gap to the scoreboard as a declared degradation.",
                  file=sys.stderr)
            return 2
    if a.status:
        step["status"] = a.status
        if a.status == "in_flight":
            step.setdefault("started", _now())   # write-once: a re-tick must never reset the clock
        if a.status in ("done", "degraded", "failed"):
            step["finished"] = _now()
        if a.status == "done" and a.force_incomplete:
            gap = _missing_produces(a.step)
            if gap:
                step.setdefault("notes", []).append(f"FORCED done with missing produces: {gap}")
                m["degradations"].append({"step": a.step, "note": f"declared produces absent: {gap}",
                                          "at": _now()})
        if a.status == "degraded":
            gap = _missing_produces(a.step)
            if gap:
                m["degradations"].append({"step": a.step, "note": f"declared produces absent: {gap}",
                                          "at": _now()})
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
    total_spawns = 0
    print(f"  {'step':14s} {'status':9s} {'files':>5s} {'spawns':>6s} {'est_tok':>9s} {'mins':>6s}  where")
    for name, s in m["steps"].items():
        est = _est_tokens(s); total_tokens += est
        c = _cost(s); total_spawns += c["spawns"]
        mn = _mins(s)
        print(f"  {name:14s} {s.get('status','?'):9s} {len(s.get('files', {})):5d} "
              f"{c['spawns']:6d} {est:9,d} {(str(mn) if mn is not None else '-'):>6s}  "
              f"{'tool' if c.get('tool_only') else 'model'}")
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
    print(f"  TOTAL  spawns {total_spawns}  est_tokens {total_tokens:,}  "
          f"(basis: {BYTES_PER_TOKEN} bytes/token over inlined+returned bytes; "
          f"conductor overhead NOT included)")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default="run_manifest.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--date", required=True)
    s = sub.add_parser("validate")
    s.add_argument("--file", required=True); s.add_argument("--round", type=int, choices=(1, 2), default=None,
                   help="1 = nomination ballot, 2 = vote ballot (carries the case form from 2026-11-01)")
    s.add_argument("--kind", choices=("challenge", "floor", "slate", "ratify", "qa"), default=None,
                   help="R34-R36 deliberation forms: Steenbarger's challenge document, one floor message, "
                        "the Chair's slate, a decider's ratification, the QA note. Exactly one of --round/--kind.")
    s.add_argument("--slate", default=None, help="slate.json (required for --kind ratify|qa)")
    s.add_argument("--board", default=None, help="board.json (optional for --kind floor: proves the name is contested)")
    s.add_argument("--candidates", default=None); s.add_argument("--phase4", default=None)
    s.add_argument("--part", type=int, default=None, help="R16 split ballot: which part of a seat's round-2 ballot this file is.")
    s.add_argument("--of", type=int, default=None, help="R16 split ballot: how many parts the seat filed. With --of >1 this part is validated on its own and need not cover the whole deliberation set; `merge` proves the coverage.")
    s.add_argument("--packet", default=None,
                   help="the packet this seat was given; every quoted-field figure in the ballot is "
                        "checked against it. A ballot citing data the packet does not carry is "
                        "REJECTED on arrival -- one respawn, then absent, same ladder as any REJECT.")
    s = sub.add_parser("merge", help="R16: stitch a seat's split round-2 ballot parts and prove they cover the deliberation set exactly.")
    s.add_argument("--glob", required=True, help="e.g. 'forms/r2/livermore.part*.json'")
    s.add_argument("--out", required=True); s.add_argument("--phase4", default="phase4.json")
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
    s.add_argument("--force-incomplete", dest="force_incomplete", action="store_true",
                   help="tick done even though declared produces[] are missing; the gap is written "
                        "to the scoreboard as a declared degradation, never silently")
    s = sub.add_parser("meter", help="record spawns and bytes moved for a step (the PM's token meter)")
    s.add_argument("--step", required=True)
    s.add_argument("--spawns", type=int, default=0)
    s.add_argument("--inlined", action="append", default=None,
                   help="path whose bytes were pasted into a spawn prompt; repeatable")
    s.add_argument("--inlined-bytes", dest="inlined_bytes", type=int, default=0)
    s.add_argument("--returned-bytes", dest="returned_bytes", type=int, default=0)
    s.add_argument("--tokens", type=int, default=0, help="exact count, when the caller knows it")
    s.add_argument("--tool-only", dest="tool_only", action="store_true",
                   help="this step moved bytes between files only -- nothing entered a model context")
    sub.add_parser("status")
    a = p.parse_args()
    return {"init": cmd_init, "validate": cmd_validate, "merge": cmd_merge, "commit": cmd_commit,
            "tick": cmd_tick, "meter": cmd_meter, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
