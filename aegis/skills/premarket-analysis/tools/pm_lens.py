#!/usr/bin/env python3
"""PM LENS -- a parallel visibility layer over the committee (PM rule, 2026-08-19).

WHAT THIS IS, IN ONE LINE
-------------------------
The committee's own filtering is UNCHANGED and UNTOUCHED. PM LENS runs beside it,
deterministically, and flashes the names that pass the PM's own manual checks --
so a name can never again be strong on the PM's criteria and simply invisible.

PM ruling 2026-08-19, verbatim: "lets have both -- what i mean is we stick to the
committee doing their filtering as-is now, but we also flash these names as 'PM
lens' - this is to ensure coverage and not prematurely blocking names or
over-using tokens to look at too big a list of candidates."

Three consequences, all load-bearing:
  * NOTHING IS BLOCKED. PM LENS removes no name from the longlist, from any
    voice's menu, from the tally, or from the deliberation set. It cannot cut.
  * THE COMMITTEE IS UNCHANGED. Voices still nominate from the full AQE longlist
    (D-66). The cap, the ranking key, the consensus rule: all as-is.
  * IT COSTS NO TOKENS. Deterministic, 0 spawns, pure field arithmetic. That is
    the point -- coverage without enlarging the candidate list the model reads.

THE COVERAGE QUESTION IT ANSWERS
--------------------------------
Every section of the brief (ADVANCE / HOLD / PASS / NEAR-MISS) requires at least
one nomination to exist first. So a name could clear the longlist, pass every
check the PM makes by hand, and appear NOWHERE in the report. TER on 2026-08-18
was exactly that: 5 of 6 checks passed, zero nominations, zero mentions. The PM
found it by eye a day later, off-sequence.

With --phase4, every PM LENS name is cross-referenced against what the committee
actually did, and lands in one of three states:
  DELIBERATED        -- the committee saw and argued it (coverage worked)
  NOMINATED_CUT_BY_CAP -- nominated but dropped by the deliberation cap (already
                        visible in the brief's NEAR MISS section)
  UNSEEN             -- ZERO nominations. The committee never looked at it. This
                        is the coverage gap, and the reason this tool exists.

VOCABULARY (fixed deliberately -- two different "6"s caused a real
misunderstanding on 2026-08-19 and must never collide again):
  * CHECK  -- one of the SIX screening checks below (C1..C6). A name has a
              CHECK SCORE out of 6.
  * LENS   -- one of AQE's SIX detect lenses (leadership, coil, insti_money,
              structure, resistance, sector). A name has a LENS COUNT out of 6.
  CHECK SCORE and LENS COUNT are different numbers. Never print one as the
  other, never say "all six" without saying which.

Bracket validity is deliberately absent from every check. PM standing rule,
restated 2026-08-19: bracket.valid=False is ENTRY MECHANICS, never a
name-quality signal and never a reason to screen a name out. The committee has
cleared names to ADVANCE with bracket.valid=False (EQNR, BBVA on 2026-08-18) --
name analysis stands, entry is the PM's own step.

THE SIX CHECKS (every field is an AQE field, read verbatim, no guesswork)
------------------------------------------------------------------------
  C1  LISTS      on_longlist AND on_elder -- on both lists, not just one
  C2  RS         rs_leadership in (LEADER, IN-LINE)          [excludes LAGGARD]
  C3  SECTOR     sector_rrg_quadrant in (IMPROVING, LEADING) [excludes
                 WEAKENING/LAGGING], AND thematic_rrg_quadrant likewise IF the
                 name has a basket. A null basket is NOT a fail -- 129 of 194
                 rows carry no thematic basket; absence is not weakness.
  C4  STRUCTURE  structure_shift in (ABOVE_STRUCTURE, BULLISH_BOS)
  C5  VWAP       5d VWAP position ABOVE and slope RISING, AND 14d position ABOVE
  C6  LENS       LENS COUNT >= 4 of 6 strong, AND coil strong, AND insti_money
                 strong. The coil/insti_money requirement is an ADDITIONAL layer
                 ON TOP of the >=4 count (PM, 2026-08-19: "4 out of 6 lens to be
                 strong - with an additional layer that coil and insti_money are
                 strong"). It is NOT a requirement that all six lenses be strong.
                 `extension` is ALWAYS null in AQE by design (the voices disagree
                 on what extension means) so it is not a lens and is not counted.

QS IS A RANKING INPUT, NOT A CHECK -- and here is the measured reason.
---------------------------------------------------------------------
The PM's framing was "EXTRA look if it is also on QS list, or has +ve QS edge
pts. higher = better" -- a tiebreak, not a gate. Encoded as a binary
"on_qs OR edge>0" and measured against the 2026-08-18 export, it passes 194 of
194 rows: qs.odds.edge is positive on every row (values cluster 0.067-0.117). A
check that never fails is not a check. So QS is carried as a RANKING and DISPLAY
field (qs_edge, on_qs, qs_signal), sorting the list after check score -- exactly
the "higher = better" the PM asked for -- and never includes or excludes a name.
Demoting it changed the list by zero names, which is the proof it was inert.

THRESHOLD
---------
--min-checks N (default 5, out of 6 CHECKS). Measured on the 2026-08-18 export:
a strict 6-of-6 CHECK gate returns exactly ONE row of 194 (DINO). C6 (lens) is
the sole binding check -- dropping any other check does not change the count;
dropping C6 takes 1 -> 13. At 5 of 6 the list is 13 names: short enough to read
at a glance (the PM's "not over-using tokens to look at too big a list"), wide
enough to catch TER. Because PM LENS blocks nothing, a loose threshold costs
visibility noise at worst -- never a missed name.

Deterministic. No model, no network, no judgment. Same input -> same output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "pm_lens.v1"

# AQE's six detect lenses. `extension` is always null by design and is NOT a lens.
LENSES = ("leadership", "coil", "insti_money", "structure", "resistance", "sector")

# C6 has TWO parts, both required:
#   (a) LENS COUNT >= LENS_MIN_STRONG   -- "4 out of 6 lens to be strong"
#   (b) every lens in LENS_MANDATORY is strong -- "an additional layer that coil
#       and insti_money are strong"
# (b) is ON TOP OF (a). This is NOT "all six lenses strong".
LENS_MIN_STRONG = 4
LENS_MANDATORY = ("coil", "insti_money")

RS_OK = ("LEADER", "IN-LINE")
RRG_OK = ("IMPROVING", "LEADING")
STRUCTURE_OK = ("ABOVE_STRUCTURE", "BULLISH_BOS")

ST_DELIBERATED = "DELIBERATED"
ST_CUT_BY_CAP = "NOMINATED_CUT_BY_CAP"
ST_UNSEEN = "UNSEEN"


def lens_count(r: dict) -> int:
    """LENS COUNT -- how many of the six lenses read 'strong' (0-6)."""
    L = r.get("lens") or {}
    return sum(1 for k in LENSES if L.get(k) == "strong")


# --- the six checks; each returns (passed, evidence) -------------------------
# Evidence is the literal field value(s) so every verdict is auditable without
# re-reading the export.

def c1_lists(r: dict) -> tuple:
    ll, el = bool(r.get("on_longlist")), bool(r.get("on_elder"))
    return (ll and el,
            "longlist=%s elder_list=%s elder=%s pattern=%s"
            % (ll, el, r.get("elder"), r.get("elder_pattern")))


def c2_rs(r: dict) -> tuple:
    v = r.get("rs_leadership")
    return (v in RS_OK, "rs_leadership=%s" % v)


def c3_sector(r: dict) -> tuple:
    sq, sd = r.get("sector_rrg_quadrant"), r.get("sector_rrg_direction")
    tq, td = r.get("thematic_rrg_quadrant"), r.get("thematic_rrg_direction")
    sector_ok = sq in RRG_OK
    thematic_ok = (tq is None) or (tq in RRG_OK)  # no basket != weakness
    ev = "sector_rrg=%s/%s" % (sq, sd)
    ev += (" thematic_rrg=%s/%s grade=%s" % (tq, td, r.get("thematic_grade"))
           if tq is not None else " thematic=none")
    return (sector_ok and thematic_ok, ev)


def c4_structure(r: dict) -> tuple:
    v = r.get("structure_shift")
    return (v in STRUCTURE_OK, "structure_shift=%s" % v)


def c5_vwap(r: dict) -> tuple:
    v5 = ((r.get("elder_context") or {}).get("vwap_5d")) or {}
    if not isinstance(v5, dict):
        v5 = {}
    pos5, slope5 = v5.get("position"), v5.get("slope_5d")
    pos14 = r.get("vwap_14d_position")
    return (pos5 == "ABOVE" and slope5 == "RISING" and pos14 == "ABOVE",
            "vwap5d=%s/%s vwap14d=%s" % (pos5, slope5, pos14))


def c6_lens(r: dict) -> tuple:
    """LENS COUNT >= 4 of 6, AND coil strong, AND insti_money strong."""
    L = r.get("lens") or {}
    n = lens_count(r)
    count_ok = n >= LENS_MIN_STRONG
    mandatory_ok = all(L.get(k) == "strong" for k in LENS_MANDATORY)
    detail = " ".join("%s=%s" % (k, L.get(k)) for k in LENSES)
    return (count_ok and mandatory_ok,
            "lens_count=%d/6 (need>=%d) count_ok=%s coil+insti_strong=%s | %s"
            % (n, LENS_MIN_STRONG, count_ok, mandatory_ok, detail))


CHECKS = (
    ("C1_lists", "On BOTH longlist and elder list", c1_lists),
    ("C2_rs_leadership", "RS leadership LEADER or IN-LINE", c2_rs),
    ("C3_sector_thematic", "Sector (and thematic, if any) RRG IMPROVING/LEADING", c3_sector),
    ("C4_structure", "ABOVE_STRUCTURE or BULLISH_BOS", c4_structure),
    ("C5_vwap", "VWAP 5d ABOVE+RISING and 14d ABOVE", c5_vwap),
    ("C6_lens", "Lens count >=4/6 strong AND coil strong AND insti_money strong", c6_lens),
)
N_CHECKS = len(CHECKS)


def score_row(r: dict) -> dict:
    checks, met, missing = {}, [], []
    for key, label, fn in CHECKS:
        passed, evidence = fn(r)
        checks[key] = {"label": label, "passed": passed, "evidence": evidence}
        (met if passed else missing).append(key)
    qs = r.get("qs") or {}
    return {
        "ticker": r.get("ticker"),
        "sector": r.get("gics_sector_name"),
        "sc_momentum": r.get("sc_momentum"),
        "elder": r.get("elder"),
        "elder_pattern": r.get("elder_pattern"),
        "structure_shift": r.get("structure_shift"),
        "lens_count": lens_count(r),          # out of 6 LENSES
        "qs_edge": ((qs.get("odds") or {}).get("edge")),   # ranking/display only
        "qs_signal": qs.get("signal"),
        "on_qs": bool(r.get("on_qs")),
        "check_score": len(met),              # out of 6 CHECKS
        "checks_total": N_CHECKS,
        "met": met,
        "missing": missing,
        "checks": checks,
        "committee_status": None,             # filled by cross_reference()
        "committee_detail": None,
    }


def cross_reference(scored: list, phase4: dict) -> None:
    """Tag each row with what the committee actually did with it.

    NOTE this NEVER changes membership or score -- it only records status. The
    committee's own output is read, never written.
    """
    delib = set(phase4.get("deliberation_set") or [])
    ranked = {e.get("ticker"): e for e in (phase4.get("ranked") or [])}
    # dropped entries look like "T(1s/c4)" -- take the leading ticker symbol
    dropped = set()
    for d in (phase4.get("dropped") or []):
        m = re.match(r"^([A-Z0-9.\-]+)", str(d))
        if m:
            dropped.add(m.group(1))
    for s in scored:
        t = s["ticker"]
        if t in delib:
            e = ranked.get(t) or {}
            s["committee_status"] = ST_DELIBERATED
            s["committee_detail"] = "seats=%s conviction_sum=%s" % (e.get("seats"), e.get("sumc"))
        elif t in dropped or t in ranked:
            e = ranked.get(t) or {}
            s["committee_status"] = ST_CUT_BY_CAP
            s["committee_detail"] = "nominated (seats=%s sumc=%s) then cut by cap" % (
                e.get("seats"), e.get("sumc"))
        else:
            s["committee_status"] = ST_UNSEEN
            s["committee_detail"] = "zero nominations — the committee never looked at this name"


def build(export: dict, min_checks: int, phase4: dict = None) -> dict:
    rows = export.get("daily_list") or []
    # Sort: check score, then QS edge (the PM's "higher = better" tiebreak),
    # then sc_momentum. QS influences ORDER only, never membership.
    scored = sorted(
        (score_row(r) for r in rows),
        key=lambda s: (-s["check_score"], -(s["qs_edge"] or 0), -(s["sc_momentum"] or 0)),
    )
    if phase4:
        cross_reference(scored, phase4)

    flagged = [s for s in scored if s["check_score"] >= min_checks]

    attrition = {}
    for key, label, _ in CHECKS:
        attrition[key] = {
            "label": label,
            "passed": sum(1 for s in scored if s["checks"][key]["passed"]),
            "of": len(scored),
        }

    dist = {}
    for s in scored:
        dist[s["check_score"]] = dist.get(s["check_score"], 0) + 1

    coverage = None
    if phase4:
        unseen = [s["ticker"] for s in flagged if s["committee_status"] == ST_UNSEEN]
        coverage = {
            "deliberated": [s["ticker"] for s in flagged if s["committee_status"] == ST_DELIBERATED],
            "cut_by_cap": [s["ticker"] for s in flagged if s["committee_status"] == ST_CUT_BY_CAP],
            "unseen": unseen,
            "unseen_count": len(unseen),
            "note": ("UNSEEN names passed the PM's own checks and drew zero nominations. "
                     "They are not errors and not verdicts — they are names the committee "
                     "never looked at, surfaced here so the PM sees them in sequence."),
        }

    return {
        "schema": SCHEMA,
        "as_of": export.get("date"),
        "export_generated_at": export.get("exported_at"),
        "min_checks": min_checks,
        "checks_total": N_CHECKS,
        "checks": [{"key": k, "label": lb} for k, lb, _ in CHECKS],
        "rule_note": (
            "PM LENS is a VISIBILITY layer, not a gate. The committee's filtering is "
            "unchanged; nothing here removes a name from the longlist, any voice's menu, "
            "the tally, or the deliberation set. C6 is 'lens count >=4 of 6 strong' PLUS "
            "an additional mandatory layer that coil and insti_money are each strong -- "
            "it is NOT a requirement that all six lenses be strong. Bracket validity is "
            "deliberately NOT a check (entry mechanics, never name quality). QS is "
            "ranking/display only -- positive on 100% of rows, so it cannot discriminate."
        ),
        "rows_scored": len(scored),
        "flagged_count": len(flagged),
        "check_score_distribution": {str(k): dist[k] for k in sorted(dist, reverse=True)},
        "check_attrition": attrition,
        "coverage": coverage,
        "flagged": flagged,
        "all_scored": scored,
        "markdown": render_markdown(flagged, min_checks, len(scored), bool(phase4), coverage),
    }


def render_markdown(flagged: list, min_checks: int, total: int,
                    has_phase4: bool, coverage: dict = None) -> str:
    if not flagged:
        return ("*No name met %d of %d PM LENS checks today (out of %d scored). "
                "The lens ran and found nothing — this is a real reading, not a "
                "missing section.*" % (min_checks, N_CHECKS, total))
    hdr = "| Ticker | Sector | Checks | Lenses strong | SC-mom | Elder | Structure | QS edge | Failed check |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    if has_phase4:
        hdr = hdr + " Committee saw it? |"
        sep = sep + "---|"
    out = [hdr, sep]
    for s in flagged:
        miss = ", ".join(m.split("_", 1)[1] for m in s["missing"]) or "— none —"
        e = s["qs_edge"]
        edge_s = ("+%.1fpp" % (e * 100)) if isinstance(e, (int, float)) else "—"
        if s["on_qs"]:
            edge_s += " (on QS)"
        row = ("| **%s** | %s | **%d/%d** | %d/6 | %s | %s | %s | %s | %s |"
               % (s["ticker"], s["sector"] or "—", s["check_score"], N_CHECKS,
                  s["lens_count"], s["sc_momentum"], s["elder"],
                  s["structure_shift"] or "—", edge_s, miss))
        if has_phase4:
            st = s["committee_status"]
            mark = {ST_DELIBERATED: "yes — deliberated",
                    ST_CUT_BY_CAP: "nominated, cut by cap",
                    ST_UNSEEN: "**NO — zero nominations**"}.get(st, "—")
            row = row + " " + mark + " |"
        out.append(row)
    if coverage and coverage["unseen_count"]:
        out.append("")
        out.append("**Coverage gap — %d PM LENS name(s) the committee never saw: %s.** "
                   "These drew zero nominations, so they appear in no other section of "
                   "this brief. Not a verdict, not an error — a name the PM's own checks "
                   "flagged and the committee did not look at."
                   % (coverage["unseen_count"], ", ".join(coverage["unseen"])))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="PM LENS — parallel visibility layer")
    ap.add_argument("--export", required=True, help="path to aqe_daily_export.json")
    ap.add_argument("--phase4", help="path to phase4.json (enables committee cross-reference)")
    ap.add_argument("--out", help="path to write pm_lens.json")
    ap.add_argument("--min-checks", type=int, default=5,
                    help="flag a name at >= this many of %d CHECKS (default 5)" % N_CHECKS)
    ap.add_argument("--print-markdown", action="store_true")
    a = ap.parse_args()

    export = json.loads(Path(a.export).read_text())
    phase4 = json.loads(Path(a.phase4).read_text()) if a.phase4 else None
    result = build(export, a.min_checks, phase4)

    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1))
    if a.print_markdown:
        print(result["markdown"])
    else:
        summary = {
            "as_of": result["as_of"],
            "min_checks": result["min_checks"],
            "rows_scored": result["rows_scored"],
            "flagged_count": result["flagged_count"],
            "check_score_distribution": result["check_score_distribution"],
            "flagged": [s["ticker"] for s in result["flagged"]],
        }
        if result["coverage"]:
            summary["coverage"] = {k: v for k, v in result["coverage"].items() if k != "note"}
        print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
