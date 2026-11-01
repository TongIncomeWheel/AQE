#!/usr/bin/env python3
"""canon_validate.py — RUNTIME half of voice grounding.

canon_build.py answers "is the canon real?". This answers the other, harder question:
"was it actually walked?" A voice can silently apply one of five checklist steps and still
return schema-valid output. That is the failure this file exists to make impossible.

MODES
    nominations <DATE>   every voice's checklist_trace, per §7.2 — six checks:
                           1 every card step present, in order
                           2 canon_ref resolves against the voice's lock
                           3 fields on the voice's own menu
                           4 'no_data' declared in data_gaps
                           5 conviction 5 does not contradict a failing walk
                           6 DEMOTED FIELDS (2026-08-06) — a card may rule some of its
                             own served fields "Advisory only, never a vote" or "Not mine
                             at all"; a passing walk built only on advisory fields, or any
                             step reading a not-mine field, is blocked
    desk <DATE>          the committee desk's canon_refs — CIO neutrality, per §8b
    drift [--days N]     the four AI-behaviour audits (§4d):
                           coverage      — a principle uncited in N days is dead weight
                                           or is being ignored; both are findings
                           concentration — a voice collapsing onto 3 of 20 principles has
                                           stopped reading its canon and started pattern-matching
                           completeness  — every checklist step present, in order, machine-checked
                           rerun         — emits the blind re-run manifest (a past universe file
                                           re-put to the voice; if it cannot reproduce itself
                                           it is not stable)
    all <DATE>           nominations + desk

Exit code 1 on any BLOCK. Warnings do not block.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "contracts", "canon_index.json")

COVERAGE_WINDOW_DAYS = 60
CONCENTRATION_MAX_SHARE = 0.60   # top-3 principles may not exceed this share of a voice's citations
CONCENTRATION_MIN_DISTINCT = 6   # ...and it must touch at least this many distinct principles

_problems = []


def block(where, msg):
    _problems.append(("BLOCK", where, msg))


def warn(where, msg):
    _problems.append(("WARN", where, msg))


def load_index():
    if not os.path.isfile(INDEX):
        sys.exit("no contracts/canon_index.json — run `python3 tools/canon_build.py index`")
    return json.load(open(INDEX))


_CARD_MARKUP = "#*_-> \t"
_STEP_TOKEN = re.compile(r"(?:^|\s)(\d+)[).]")

# A checklist HEADER, not the word 'checklist' occurring in running prose. After the
# markup is stripped the line must be 'checklist' followed by punctuation that opens a
# header — ':', '(', a dash, or nothing at all. elder-lens wraps the sentence "...the
# checklist below implements." onto its own line; that line began with the word and was
# being read as the header, so the real '## Checklist (in order)' 29 lines below was
# never reached.
_CHECKLIST_HEADER = re.compile(r"^checklist\s*(?:[:(\-—]|$)")


def _is_checklist_header(line):
    return bool(_CHECKLIST_HEADER.match(line.strip().lstrip(_CARD_MARKUP).lower()))


def card_steps(vkey):
    """The voice card states its checklist: 'Checklist: 1) ... 2) ... 3) ...', either
    inline on one line or as a heading followed by numbered lines. The number of steps
    is not a config value — it is whatever the card says, so the validator can never
    drift from the card it is validating.

    HARDENED 2026-08-06. The old version required the raw line to LITERALLY start with
    'checklist', so a card writing '**Checklist (in order):**' or '## Checklist' returned
    None — and None SILENTLY DISABLED the step-completeness check at both call sites
    (`if nsteps and ...`). thorp and seow were unguarded for weeks and nobody could see
    it. Markdown markup is now stripped before the test, and a heading-style checklist
    has its numbered lines counted. A card whose steps cannot be found is a hard error,
    never a silent pass — see require_card_steps()."""
    p = os.path.join(ROOT, "skills", f"voice-{vkey}", "SKILL.md")
    if not os.path.isfile(p):
        return None
    lines = open(p, encoding="utf-8").read().split("\n")
    for i, line in enumerate(lines):
        if not _is_checklist_header(line):
            continue
        # form A — inline: 'Checklist: 1) ... 2) ...' all on the header line
        n = len(_STEP_TOKEN.findall(line))
        if n:
            return n
        # form B — heading: the numbered lines that follow, to the end of the section.
        # The SECTION is the boundary (the next markdown heading), not a blank line —
        # cards space their steps apart and elder-lens read as 1 step when blanks ended
        # the scan.
        seen = set()
        for nxt in lines[i + 1:]:
            s = nxt.strip()
            if s.startswith("#"):
                break
            if _is_checklist_header(s):
                break
            m = re.match(r"^(?:[-*+]\s*)?\**(\d+)[).]\s", s)
            if m:
                seen.add(int(m.group(1)))
        if seen:
            return len(seen)
    return None


def require_card_steps(vkey, grounded):
    """card_steps() returning None used to mean 'skip the check'. It now means the card
    is unreadable, and that is reported — never swallowed.

    A GROUNDED voice is blocked: its card is canon-backed, so an unenforceable checklist
    is a live hole in the only mechanism that proves the canon was walked. An UNGROUNDED
    voice is warned: its card is still a stub and blocking it would stand down the whole
    validator over work that has not been done yet."""
    n = card_steps(vkey)
    if not n:
        msg = ("voice card states no parseable checklist ('Checklist: 1) ... 2) ...' inline, "
               "or a 'Checklist' heading followed by numbered lines). Step completeness "
               "cannot be enforced against a card that will not say how many steps it has.")
        (block if grounded else warn)(f"card/{vkey}", msg)
    return n


def menu_fields(vkey):
    try:
        sys.path.insert(0, os.path.join(ROOT, "packaging"))
        import build_claude
        return set(build_claude.VOICE_MENUS.get(vkey, []))
    except Exception:
        return set()


# terminate on a sentence-ending period (one followed by space/markup/EOL), never on the
# dot inside a dotted field name like `bracket.stop`
_SENT_END = r"(?:\.(?=[\s*_]|$)|$)"
ADVISORY_LINE = re.compile(r"Advisory only, never a vote:(.+?)" + _SENT_END, re.I | re.S)
FORBIDDEN_LINE = re.compile(r"Not mine at all:(.+?)" + _SENT_END, re.I | re.S)
BACKTICKED = re.compile(r"`([A-Za-z0-9_.]+)`")


def field_standings(vkey):
    """Fields a voice's OWN card demotes, parsed from the card — same
    card-is-the-source-of-truth rule as card_steps().

    Two sentences, anywhere in the card, both optional:
        Advisory only, never a vote: `a`, `b`.     -> may inform, may never carry a pass
        Not mine at all: `c`.                      -> may not be read as a checklist field

    Returns (advisory, forbidden) as sets. A voice that demotes nothing gets two
    empty sets and is unaffected."""
    p = os.path.join(ROOT, "skills", f"voice-{vkey}", "SKILL.md")
    if not os.path.isfile(p):
        return set(), set()
    txt = open(p).read()
    adv = ADVISORY_LINE.search(txt)
    forb = FORBIDDEN_LINE.search(txt)
    return (set(BACKTICKED.findall(adv.group(1))) if adv else set(),
            set(BACKTICKED.findall(forb.group(1))) if forb else set())


# ---------------------------------------------------------------- nominations

def validate_nominations(date, idx):
    d = os.path.join(ROOT, "data", "sod", date, "nominations")
    if not os.path.isdir(d):
        sys.exit(f"no nominations for {date}")
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    for f in files:
        doc = json.load(open(f))
        vkey = doc.get("voice") or os.path.basename(f)[:-5]
        vi = (idx.get("voices") or {}).get(vkey, {})
        valid_ids = set(vi.get("principles") or [])
        grounded = vi.get("grounded")
        nsteps = require_card_steps(vkey, grounded)
        menu = menu_fields(vkey)
        advisory, forbidden = field_standings(vkey)
        gaps = {g.get("field") for g in (doc.get("data_gaps") or [])}

        for n in doc.get("nominations") or []:
            tag = f"{date}/{vkey}/{n.get('ticker','?')}"
            tr = n.get("checklist_trace")
            if not tr:
                block(tag, "no checklist_trace — a nomination with no walked checklist is an "
                           "assertion, not an analysis")
                continue

            # (1) every step present, IN ORDER, none omitted
            steps = [t.get("step") for t in tr]
            if steps != sorted(steps):
                block(tag, f"checklist_trace steps out of order: {steps}")
            if nsteps and len(set(steps)) != nsteps:
                block(tag, f"card has {nsteps} checklist steps, trace covers {len(set(steps))} "
                           f"({sorted(set(steps))}). A step that could not be evaluated is recorded "
                           "'no_data' — it is never dropped.")

            for t in tr:
                st = t.get("step")
                # (2) canon_ref must resolve
                refs = t.get("canon_ref") or []
                if not refs:
                    block(tag, f"step {st} cites no canon principle")
                if grounded:
                    for r in refs:
                        if r not in valid_ids:
                            block(tag, f"step {st} cites '{r}' which is not a principle in this "
                                       f"voice's lock ({len(valid_ids)} exist). Either the voice "
                                       "invented it or the lock changed under it.")
                elif refs and refs != ["UNGROUNDED"]:
                    warn(tag, f"step {st} cites {refs} but {vkey} has no canon lock — "
                              "these ids are unverifiable")

                # (3) fields must be on the voice's own menu
                for fl in (t.get("fields") or []):
                    if menu and fl not in menu and fl.split(".")[0] not in {m.split(".")[0] for m in menu}:
                        block(tag, f"step {st} reads '{fl}' — off this voice's data menu")

                # (4) no_data must be declared as a gap, not quietly swallowed
                if t.get("verdict") == "no_data":
                    if not (set(t.get("fields") or []) & gaps):
                        block(tag, f"step {st} is 'no_data' but none of its fields appear in "
                                   "data_gaps. A voice that hits a hole declares it (D-55).")

            # (5) conviction must not contradict the walk
            bad = [t.get("step") for t in tr if t.get("verdict") in ("fail", "partial")]
            if bad and n.get("conviction") == 5:
                block(tag, f"conviction 5 with failing/partial steps {bad} — the trace and the "
                           "number disagree; the number is the one that is wrong")

            # (6) THE DEMOTED-FIELD CHECK (2026-08-06). A card may rule some of its own
            # menu fields advisory (informative, never decisive) or not-mine (outside its
            # canon). Both standings are declared on the card itself; this enforces them.
            # Origin: 22 Jul, all ten thorp nominations led with a 5-analogue knn hit rate
            # and tiebroke on beta_30d — schema-valid, canon-void.
            if forbidden:
                for t in tr:
                    hit = sorted(set(t.get("fields") or []) & forbidden)
                    if hit:
                        block(tag, f"step {t.get('step')} reads {hit} — this voice's card rules "
                                   "it 'not mine at all'. It may be stated as labelled context "
                                   "on the line, never read as a checklist field.")
            if advisory:
                passing = set()
                for t in tr:
                    if t.get("verdict") == "pass":
                        passing |= set(t.get("fields") or [])
                if passing and passing <= advisory:
                    block(tag, f"every field carrying a passing step is advisory ({sorted(passing)}). "
                               "The card rules these informative, never decisive — a nomination "
                               "whose passing steps read only advisory fields is not a nomination.")

        for h in doc.get("held_review") or []:
            if h.get("verdict") in ("TIGHTEN", "EXIT-CASE") and not h.get("canon_ref"):
                warn(f"{date}/{vkey}/{h.get('ticker','?')}",
                     "held verdict carries no canon_ref")
    return len(files)


# ---------------------------------------------------------------- desk (§8b CIO neutrality)

PRINCIPLE_PROSE = re.compile(
    r"\b(always|never|the rule is|principle|by definition|it is well established|"
    r"in general one should|the correct approach)\b", re.I)


def validate_desk(date, idx):
    p = os.path.join(ROOT, "data", "sod", date, "committee.json")
    if not os.path.isfile(p):
        sys.exit(f"no committee.json for {date}")
    desk = json.load(open(p))

    # what each voice ACTUALLY cited today, per ticker
    cited = defaultdict(set)          # (voice, ticker) -> {C-ids}
    nominators = defaultdict(set)     # ticker -> {voices}
    nd = os.path.join(ROOT, "data", "sod", date, "nominations")
    for f in glob.glob(os.path.join(nd, "*.json")):
        doc = json.load(open(f))
        v = doc.get("voice") or os.path.basename(f)[:-5]
        for n in doc.get("nominations") or []:
            tk = n.get("ticker")
            nominators[tk].add(v)
            for t in n.get("checklist_trace") or []:
                cited[(v, tk)] |= set(t.get("canon_ref") or [])

    for vd in desk.get("verdicts") or []:
        tk = vd.get("ticker", "?")
        tag = f"{date}/desk/{tk}"
        refs = vd.get("canon_refs") or []
        if not refs:
            block(tag, "the desk recorded no canon_refs. The desk holds no canon of its own — "
                       "it may only weigh principles a nominating voice actually cited today. "
                       "Zero refs means the verdict rests on the desk's own priors, which is "
                       "precisely the house view this seat must not grow.")
            continue

        # (1) every ref was really cited by that voice, for that ticker, today
        for r in refs:
            v, cid = r.get("voice"), r.get("id")
            if cid not in cited.get((v, tk), set()):
                block(tag, f"weighs {v}:{cid} — {v} did not cite {cid} for {tk} today. "
                           "The desk cannot import a principle nobody brought to the table.")

        # (2) an ADVANCE must rest on more than one voice
        if vd.get("verdict") == "ADVANCE":
            if len({r.get("voice") for r in refs}) < 2:
                block(tag, "ADVANCE resting on a single voice's canon — locked doctrine: "
                           "DATA leads, LENS seconds, VOICES corroborate. A voice never buys a seat alone.")

        # (3) where nominators disagreed, the desk must show it weighed the other side
        if len(nominators.get(tk, ())) >= 2:
            if not any(r.get("weighed") in ("outweighed", "conflicted") for r in refs):
                warn(tag, "every canon_ref is 'supported' though multiple voices weighed in — "
                          "a desk that never records what it set aside is not deliberating")

        # (4) THE ONE THAT MATTERS — a principle asserted in prose that maps to no ref
        prose = " ".join(str(vd.get(k) or "") for k in ("bear_case", "conditions"))
        if PRINCIPLE_PROSE.search(prose) and not refs:
            block(tag, "the verdict prose states a general principle with no canon_ref behind it")

    for hv in desk.get("held_verdicts") or []:
        if hv.get("held_verdict") in ("EXIT", "TAKE-PARTIAL") and not (hv.get("canon_refs") or []):
            warn(f"{date}/desk/{hv.get('ticker','?')}",
                 "an exit/partial decision with no canon_ref — record what it rested on")
    return len(desk.get("verdicts") or [])


# ---------------------------------------------------------------- drift audits (§4d)

def drift(days, idx):
    dates = sorted(os.listdir(os.path.join(ROOT, "data", "sod")))[-days:]
    per_voice = defaultdict(Counter)
    traces = 0
    for d in dates:
        for f in glob.glob(os.path.join(ROOT, "data", "sod", d, "nominations", "*.json")):
            doc = json.load(open(f))
            v = doc.get("voice") or os.path.basename(f)[:-5]
            for n in doc.get("nominations") or []:
                for t in n.get("checklist_trace") or []:
                    traces += 1
                    for r in t.get("canon_ref") or []:
                        per_voice[v][r] += 1

    print(f"\nDRIFT AUDIT — {len(dates)} session(s), {traces} traced steps\n" + "=" * 66)
    for vkey, vi in sorted((idx.get("voices") or {}).items()):
        if not vi.get("grounded"):
            print(f"{vkey:16s} ungrounded — skipped")
            continue
        ids = set(vi["principles"])
        c = per_voice.get(vkey, Counter())
        total = sum(c.values())
        print(f"\n{vkey}  ({len(ids)} principles, {total} citations)")

        # AUDIT 1 — COVERAGE
        dead = sorted(ids - set(c))
        if dead:
            warn(f"drift/{vkey}", f"never cited in {len(dates)} sessions: {', '.join(dead)} — "
                                  "either dead weight in the lock, or the voice is skipping them")
            print(f"  coverage      {len(ids)-len(dead)}/{len(ids)} cited · never used: {', '.join(dead)}")
        else:
            print(f"  coverage      {len(ids)}/{len(ids)} — every principle used")

        # AUDIT 2 — CONCENTRATION
        if total >= 20:
            top3 = sum(n for _, n in c.most_common(3))
            share = top3 / total
            distinct = len(c)
            flag = share > CONCENTRATION_MAX_SHARE or distinct < CONCENTRATION_MIN_DISTINCT
            print(f"  concentration top-3 = {share:.0%} of citations, {distinct} distinct"
                  f"{'   <-- COLLAPSING' if flag else ''}")
            if flag:
                warn(f"drift/{vkey}",
                     f"top-3 principles carry {share:.0%} of citations across {distinct} distinct ids — "
                     "the voice has stopped reading its canon and started pattern-matching a habit")
        else:
            print(f"  concentration n/a (only {total} citations)")

        # AUDIT 3 — TRACE COMPLETENESS
        # only grounded voices reach here (ungrounded ones `continue` above), so BLOCK is right
        nsteps = require_card_steps(vkey, True)
        short = 0
        for d in dates:
            f = os.path.join(ROOT, "data", "sod", d, "nominations", f"{vkey}.json")
            if not os.path.isfile(f):
                continue
            for n in json.load(open(f)).get("nominations") or []:
                tr = n.get("checklist_trace") or []
                if nsteps and len({t.get("step") for t in tr}) != nsteps:
                    short += 1
        print(f"  completeness  {short} nomination(s) with an incomplete walk")
        if short:
            block(f"drift/{vkey}", f"{short} nominations did not walk the full checklist")

    # AUDIT 4 — BLIND RE-RUN MANIFEST
    if dates:
        past = dates[0]
        u = os.path.join("data", "sod", past, "universe.json")
        print("\n" + "=" * 66)
        print("blind re-run — re-put a past universe to each voice and diff the nominations.\n"
              "A voice that cannot reproduce itself against identical data is not stable;\n"
              "the drift is in the model, not the market.\n")
        print(f"  universe: {u}   (session {past})")
        for vkey, vi in sorted((idx.get("voices") or {}).items()):
            if vi.get("grounded"):
                print(f"  spawn agents/voice-{vkey}.md  <-  {u}   then diff vs "
                      f"data/sod/{past}/nominations/{vkey}.json")


# ---------------------------------------------------------------- cli

def report():
    if not _problems:
        print("\nOK — no findings")
        return 0
    print()
    for lvl, where, msg in _problems:
        print(f"{lvl:5s} {where}\n      {msg}")
    n = sum(1 for p in _problems if p[0] == "BLOCK")
    print(f"\n{n} BLOCK, {len(_problems)-n} WARN")
    return 1 if n else 0


def main():
    ap = argparse.ArgumentParser(prog="canon_validate.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["nominations", "desk", "drift", "all"])
    ap.add_argument("date", nargs="?")
    ap.add_argument("--days", type=int, default=COVERAGE_WINDOW_DAYS)
    a = ap.parse_args()
    idx = load_index()
    if a.mode in ("nominations", "all"):
        n = validate_nominations(a.date, idx)
        print(f"checked {n} voice file(s) for {a.date}")
    if a.mode in ("desk", "all"):
        n = validate_desk(a.date, idx)
        print(f"checked {n} desk verdict(s) for {a.date}")
    if a.mode == "drift":
        drift(a.days, idx)
    sys.exit(report())


if __name__ == "__main__":
    main()
