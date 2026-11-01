#!/usr/bin/env python3
"""canon_check.py — does each seat's CARD still say what its CANON says, and is the canon intact?

WHY THIS EXISTS. On 2026-09-07 the weis card declared "Canon status: GROUNDED, NOT SEALED,
pm_signed: null, four open PM decisions, page cites NOT folio-verified" and told the seat to repeat
that in `notes` on every return. The canon had been sealed on 2026-08-24 — pm_signed Ash, 23 of 23
citations spot-checked, zero open decisions. The card was fourteen days stale, so the seat hedged
every nomination against a problem that no longer existed. Nothing compared the two. This does.

    python3 tools/canon_check.py             # check every seat
    python3 tools/canon_check.py --reindex   # regenerate contracts/canon_index.json from the locks

CHECKS
  1. the lock file parses and its declared counts match what it actually contains
  2. principle ids are contiguous — no rule silently dropped
  3. every principle is either CITED or explicitly labelled `unsourced_retained` / `pm_override`.
     House doctrine is legitimate; an UNLABELLED uncited principle claiming `verified` is not.
  4. R1 — no recogniser uses a bracket field as a DISQUALIFIER. Naming a bracket field as a
     limitation is fine; acting on one to refuse or cap a candidate is not.
  5. the card's stated seal status matches the lock's actual one.

PARSER NOTE: uses PyYAML when importable, else a reduced regex reader that DECLARES itself as
degraded. Two earlier versions of this file hand-rolled the parsing and got the answer wrong twice
in opposite directions — flagging crown for citations it has, and missing detect-lens's real ones.
A checker that cannot parse the thing it checks is worse than no checker.
"""
import os, re, sys

try:
    import yaml
    YAML = True
except ImportError:
    YAML = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CANON = os.path.join(ROOT, "canon")
SKILLS = os.path.join(ROOT, "skills")

FAILS, WARNS = [], []
def ok(n, c, d=""):
    print(("  ok    " if c else "  FAIL  ") + n + (("  -- " + d) if d and not c else ""))
    if not c: FAILS.append(n)
def warn(n, d=""):
    print("  warn  " + n + (("  -- " + d) if d else "")); WARNS.append(n)

# A citation is optional ONLY when the principle says so.
HOUSE = {"unsourced_retained", "pm_override", "house", "doctrine"}

BRACKET_FIELD = re.compile(
    r"\bbracket\.(valid|risk_pct|rr\b|rr_tp\d|stop_type|stop_atr_dist|atr_fallback_stop|invalid_reason)\b|"
    r"\br:?r\s*(too\s*thin|below|<)|\bno usable stop\b|\bstop too wide\b", re.I)
DISQUALIFY = re.compile(
    r"\b(do not nominate|don't nominate|reject the|refuse|disqualif\w*|oppose|abstain|"
    r"cap(?:ped)? (?:at|conviction)|veto|exclude|drop the (?:name|candidate))\b", re.I)


def load_lock(path):
    txt = open(path).read()
    if YAML:
        return yaml.safe_load(txt), txt
    return None, txt


def check_seat(seat, path):
    d, txt = load_lock(path)
    print(f"\n{seat}")
    if d is None:
        warn("PyYAML unavailable — structural checks skipped, card/seal check only")
        signed = (re.search(r"^pm_signed:\s*(.+)$", txt, re.M) or [None, None])[1]
        return {"sealed": bool(signed and signed.strip().lower() not in ("null", "~"))}

    prin = d.get("principles") or []
    recs = d.get("recognisers") or []
    # SHAPE TOLERANCE: crown wraps its recognisers as {note, items: [...]}, everyone else uses a
    # bare list. An earlier version counted the wrapper's two keys and reported "2 vs declared 11".
    # Same defect class as the pipeline's silent shape mismatches -- accept the real shape, loudly.
    if isinstance(recs, dict):
        recs = recs.get("items") or recs.get("recognisers") or []
    counts = d.get("counts") or {}

    ok("lock parses and carries principles", bool(prin), "no principles block")

    ids = [p.get("id") for p in prin if isinstance(p, dict)]
    pfx = re.match(r"[A-Z]+", ids[0]).group() if ids else ""
    nums = [int(re.sub(r"[A-Z]+", "", i)) for i in ids if i]
    ok("principle ids are contiguous (no rule silently dropped)",
       nums == list(range(min(nums), min(nums) + len(nums))) if nums else False,
       f"{pfx}{min(nums)}..{pfx}{max(nums)} with {len(nums)} entries" if nums else "")

    if "principles" in counts:
        ok(f"declared principle count matches actual ({len(prin)})",
           int(counts["principles"]) == len(prin), f"declared {counts['principles']}")
    if "recognisers" in counts:
        ok(f"declared recogniser count matches actual ({len(recs)})",
           int(counts["recognisers"]) == len(recs), f"declared {counts['recognisers']}")

    bad = [p.get("id") for p in prin
           if not p.get("cite") and str(p.get("status", "")).lower() not in HOUSE]
    house = [p.get("id") for p in prin if str(p.get("status", "")).lower() in HOUSE]
    ok("every principle is cited OR labelled house doctrine", not bad, f"unlabelled+uncited: {bad}")
    if house:
        print(f"        ({len(house)} house-doctrine principle(s), correctly labelled)")

    offenders = []
    for r in recs:
        if not isinstance(r, dict): continue
        c, t = str(r.get("if", "")), str(r.get("then", ""))
        # A recogniser that names the forbidden action in order to FORBID it is compliant, not a
        # violation. oneil R6 says "NEVER a reject, non-nomination or conviction cap" and cites R1;
        # an earlier version of this check flagged it for containing the word "reject". Judge the
        # instruction, not the vocabulary.
        negated = re.search(r"\bnever a (reject|non-nomination)|\bnever a reason to reject|"
                            r"\bis not a reject|\bnever a conviction cap", t, re.I)
        if BRACKET_FIELD.search(c) and DISQUALIFY.search(t) and not negated:
            offenders.append(f"{r.get('id')}: {t[:70]}")
    ok("R1 — no recogniser uses a bracket field as a disqualifier", not offenders, str(offenders))

    signed = d.get("pm_signed")
    return {"sealed": bool(signed and str(signed).lower() not in ("null", "~")),
            "pm_signed": signed}


def check_card(seat, lock):
    card = os.path.join(SKILLS, f"voice-{seat}", "SKILL.md")
    if not os.path.exists(card):
        warn(f"no card at skills/voice-{seat}/SKILL.md (canon shipped, seat not in this plugin)")
        return
    txt = open(card).read()
    stale = bool(re.search(r"NOT SEALED|PENDING_PM_SIGNOFF|pm_signed:\s*null|canon unsealed", txt, re.I))
    if lock["sealed"]:
        ok("card does not claim unsealed while the lock is signed", not stale,
           "STALE CARD — the seat will hedge every return against a problem already fixed")
    else:
        ok("card correctly declares the canon unsealed", stale)


def _recs(d):
    r = d.get("recognisers") or []
    return (r.get("items") or r.get("recognisers") or []) if isinstance(r, dict) else r


def rebuild_index():
    import json
    out = {"generated_from": "canon/*/canon.lock.yaml", "generated_at": "2026-09-07",
           "note": "GENERATED — do not hand-edit. Rebuild: python3 tools/canon_check.py --reindex. "
                   "The previous hand-maintained index reported detect-lens and druckenmiller as "
                   "grounded:false with zero principles; both carry full signed canon. An index that "
                   "is typed rather than generated drifts from what it indexes.",
           "voices": {}}
    for s in sorted(os.listdir(CANON)):
        p = os.path.join(CANON, s, "canon.lock.yaml")
        if not os.path.exists(p): continue
        d, txt = load_lock(p)
        if d is None: continue
        prin = d.get("principles") or []
        out["voices"][s] = {
            "grounded": bool(d.get("pm_signed") and str(d["pm_signed"]).lower() not in ("null", "~")),
            "pm_signed": d.get("pm_signed"),
            "principles": [p_.get("id") for p_ in prin if isinstance(p_, dict)],
            "principles_verified": sum(1 for p_ in prin if p_.get("status") == "verified"),
            "principles_house": sum(1 for p_ in prin if str(p_.get("status", "")).lower() in HOUSE),
            "recognisers": [r.get("id") for r in _recs(d) if isinstance(r, dict)],
            "shipped": f"canon/{s}/canon.lock.yaml", "bytes": len(txt)}
    dst = os.path.join(ROOT, "contracts", "canon_index.json")
    json.dump(out, open(dst, "w"), indent=1)
    v = out["voices"]
    print(f"rebuilt {dst}\n  {len(v)} seats · "
          f"{sum(len(x['principles']) for x in v.values())} principles "
          f"({sum(x['principles_verified'] for x in v.values())} verified, "
          f"{sum(x['principles_house'] for x in v.values())} house) · "
          f"{sum(len(x['recognisers']) for x in v.values())} recognisers")
    return 0


def main():
    if "--reindex" in sys.argv:
        return rebuild_index()
    if not os.path.isdir(CANON):
        sys.exit(f"no canon/ at {CANON} — lock files are not shipped with this plugin")
    seats = sorted(d for d in os.listdir(CANON) if os.path.isdir(os.path.join(CANON, d)))
    print(f"canon_check — {len(seats)} seats" + ("" if YAML else "  [DEGRADED: no PyYAML]"))
    for s in seats:
        p = os.path.join(CANON, s, "canon.lock.yaml")
        if not os.path.exists(p):
            warn(f"{s}: directory present, no canon.lock.yaml"); continue
        check_card(s, check_seat(s, p))
    cards = [d[6:] for d in sorted(os.listdir(SKILLS)) if d.startswith("voice-") and d != "voice-common"]
    nocanon = [c for c in cards if c not in seats]
    print()
    if nocanon: warn(f"{len(nocanon)} seat(s) with NO canon: " + ", ".join(nocanon))
    print(f"\n{len(FAILS)} failed, {len(WARNS)} warning(s)")
    if FAILS: print("FAILED:"); [print("  - " + f) for f in FAILS]
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
