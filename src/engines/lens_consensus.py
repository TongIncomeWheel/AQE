"""Lens consensus — the ONE thing AQE adds for the AIC read.

PM design (2026-07-16): AQE already exports every score and subcomponent. The only
addition is a count of how many lenses agree. Tiering falls out of sorting on it.
The voice glossary is added on the AIC side, not here.

RULES:
  * AQE presents, AIC decides. Sort only — never cut, never eliminate.
  * No invented thresholds. Every verdict is either a label AQE ALREADY computes
    (BULLISH_BOS, A-TIER, mp_state STRONG, gics_gate PASS) or a "top/bottom third of
    today's list" position — a fact about today's list, not a judgment.
  * NO WEIGHTING. We never earned one; four attempts to fit weights all failed.
    The count is unweighted and has zero fitted parameters.
  * EXTENSION carries NO verdict (PM: "not your call, just provide data") — the voices
    disagree on what extension means, so AQE prints the numbers and stays out of it.
    General rule: where the voices disagree on meaning, AQE prints and shuts up.
  * A lens with no data reads "--". Absence is never agreement.

The count is a READING AID, not a prediction. Whether 5-of-6 outperforms 2-of-6 is
untested — testing it would require the weighting we just refused.

Reads only fields the export already carries. Zero new data, zero FMP calls.
"""
from __future__ import annotations

STRONG, OK, WARN, NONE = "strong", "ok", "warn", "--"

# EXTENSION is deliberately absent: it is data-only and never contributes to the count.
LENSES = ("leadership", "coil", "insti_money", "structure", "resistance", "sector")


def _sub(rec: dict, group: str, key: str):
    return ((rec.get("subcomponents") or {}).get(group) or {}).get(key)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _terciles(records: list[dict], getter) -> dict:
    """Map record index -> strong/ok/warn by position in TODAY's list. Not a judgment."""
    vals = [(i, _num(getter(r))) for i, r in enumerate(records)]
    have = sorted([(v, i) for i, v in vals if v is not None])
    out = {i: NONE for i, _ in vals}
    n = len(have)
    if n < 3:
        return out
    for rank, (_, i) in enumerate(have):
        p = rank / (n - 1)
        out[i] = WARN if p <= 1 / 3 else (STRONG if p >= 2 / 3 else OK)
    return out


def compute_lens_consensus(records: list[dict]) -> list[dict]:
    """Add `lens`, `lens_positive`, `lens_warnings` to every record. Mutates in place."""
    if not records:
        return records

    t_lead = _terciles(records, lambda r: _sub(r, "pipe", "pr_ret_12m"))
    t_coil = _terciles(records, lambda r: _sub(r, "energy", "squeeze_score"))
    t_inst = _terciles(records, lambda r: _sub(r, "flow", "accum_score"))
    # resist_score: HIGH = clear air (AQE's own polarity). The 52-week overhead-supply
    # read the AIC asked for is not built yet — this is the 50-day window until it is.
    t_resist = _terciles(records, lambda r: _sub(r, "structure", "resist_score"))

    for i, rec in enumerate(records):
        lens = {}

        # 1 LEADERSHIP — AQE's own pipe_tier label wins; else where 12m return sits today
        tier = _sub(rec, "pipe", "pipe_tier")
        if tier == "A-TIER":
            lens["leadership"] = STRONG
        elif tier in ("D-SKIP", "C-WATCH"):
            lens["leadership"] = WARN
        else:
            lens["leadership"] = t_lead[i]

        # 2 COIL — premove_setup is AQE's own label and wins; else squeeze position
        lens["coil"] = STRONG if rec.get("premove_setup") is True else t_coil[i]

        # 3 INSTI MONEY — accumulation position today
        lens["insti_money"] = t_inst[i]

        # 4 STRUCTURE — AQE's own structure_shift label, ALONE. §6 PM ruling
        # (2026-07-17, Option B): "You do not decide. You present." — no
        # joint read with div_state. structure_shift is a pure label
        # pass-through, same treatment as every other lens field.
        ss = rec.get("structure_shift")
        if ss == "BULLISH_BOS":
            lens["structure"] = STRONG
        elif ss == "BEARISH_CHOCH":
            lens["structure"] = WARN
        elif ss == "RANGE":
            lens["structure"] = OK
        else:
            lens["structure"] = NONE

        # 5 RESISTANCE — clear air above
        lens["resistance"] = t_resist[i]

        # 6 EXTENSION — NO VERDICT. Data only, by PM ruling. Never counted.
        lens["extension"] = None

        # 7 SECTOR — AQE's own gate label
        lens["sector"] = {"PASS": STRONG, "BLOCKED": WARN, "CAUTION": WARN,
                          "WATCH": OK, "CHECK": OK}.get(rec.get("gics_gate"), NONE)

        rec["lens"] = lens
        rec["lens_positive"] = sum(1 for k in LENSES if lens.get(k) == STRONG)
        rec["lens_warnings"] = sum(1 for k in LENSES if lens.get(k) == WARN)

    return records


def build_lens_ranking(records: list[dict]) -> dict:
    """PART 1 of the AIC read: the ranking. Compact, ordered, self-contained.

    Duplicates nothing but the counts — the FULL data for every one of these names is
    Part 2 (`daily_list`), unchanged. Read Part 1 to know where to start; drill into
    Part 2 to deliberate.

    Sort only. Every scored name appears — nothing is eliminated. `rank` is a reading
    order, not a verdict.
    """
    ranked = sorted(records, key=lambda r: (-(r.get("lens_positive") or 0),
                                            r.get("lens_warnings") or 0,
                                            -(r.get("ptrs") or 0)))
    return {
        "method": ("Count of lenses reading `strong`. UNWEIGHTED — no weighting was ever "
                   "earned, so none is applied. Sort only: nothing is filtered, capped, or "
                   "eliminated. Every scored name is here."),
        "lens_set": list(LENSES),
        "extension_note": ("`extension` is data-only and NEVER counted. The voices disagree "
                           "on what extension means, so AQE prints the numbers "
                           "(subcomponents.flow.ext_score, energy.en_pos50 / "
                           "exhaustion_score / atr_score) and makes no call."),
        "reading_aid_not_a_prediction": ("Whether 5-of-6 outperforms 2-of-6 is UNTESTED. "
                                         "Testing it would require the weighting we refused. "
                                         "This exists to make the read consistent and cheap."),
        "full_data_in": "daily_list",
        "count": len(ranked),
        "ranked": [{"rank": i,
                    "ticker": r.get("ticker"),
                    "positive": r.get("lens_positive"),
                    "warnings": r.get("lens_warnings"),
                    "lens": r.get("lens")}
                   for i, r in enumerate(ranked, 1)],
    }


LENS_GLOSSARY = {
    "lens_ranking": "PART 1 of the AIC read — every scored name ordered by how many lenses "
                    "agree (`positive` desc, then `warnings` asc, then ptrs). A READING "
                    "ORDER, not a verdict, and not a filter: nothing is eliminated and the "
                    "count carries no proven edge. The FULL per-name data is Part 2 = "
                    "`daily_list`, unchanged.",
    "lens": "Per-lens read: strong/ok/warn/-- for leadership, coil, insti_money, structure, "
            "resistance, sector. `extension` is ALWAYS null — the voices disagree on what "
            "extension means, so AQE prints the numbers (subcomponents.flow.ext_score, "
            "energy.en_pos50/exhaustion_score/atr_score) and makes no call. Every verdict "
            "comes from a label AQE already computes, or from top/bottom-third position in "
            "TODAY's list. No fitted thresholds anywhere. '--' = no data; absence is never "
            "agreement.",
    "lens_positive": "Count of lenses reading `strong` (0-6). UNWEIGHTED — no weighting was "
                     "ever earned. Sort on it to tier the read; it is a READING AID, not a "
                     "prediction, and whether 5-of-6 beats 2-of-6 is untested. Never a gate: "
                     "nothing is eliminated, every name keeps its full block.",
    "lens_warnings": "Count of lenses reading `warn` (0-6).",
}
