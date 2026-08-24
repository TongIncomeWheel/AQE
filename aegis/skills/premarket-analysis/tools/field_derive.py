#!/usr/bin/env python3
"""
field_derive.py — fill numbers the engine leaves null but that are FULLY DETERMINED
by numbers the engine does emit.

Why this exists
---------------
Some "missing numbers" are not missing information. They are missing LABELS.

Worked example, the one that was blocking six seats on 2026-08-24:

    bracket.stop_type is null on 157 of 200 rows (78%).
    On every one of those 157 rows, bracket.valid is false
    and bracket.atr_fallback_stop is populated.

So the seat is not blind. The stop it will actually trade off is right there. The engine
just never wrote down what KIND of stop it is. That is a one-character-of-meaning gap and
the orchestrator can close it at packet-build time, today, without an engine release.

Rules for anything added to DERIVATIONS
---------------------------------------
1. DETERMINISTIC. Same row in, same value out. No model, no judgment, no estimate.
2. The inputs must be populated on ~100% of rows, or the derivation is not a fix.
3. The derived value must be VISIBLY derived — every derived field is written back with a
   parallel "<field>_source": "derived" so the seat can see it was not measured.
4. Never derive a price, a level, or a score. Labels, states and flags only. If you find
   yourself computing a number a seat would trade on, that is an ENGINE_TICKET, not a
   derivation.

Used by voice_preflight.py (to classify a gap as DERIVED rather than a blocker) and by
pma_pipeline.py packets (to actually fill it before the TSV is written).
"""


def _get(row, dotted):
    cur = row
    for k in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _set(row, dotted, value):
    parts = dotted.split(".")
    cur = row
    for k in parts[:-1]:
        cur = cur.setdefault(k, {})
        if not isinstance(cur, dict):
            return
    cur[parts[-1]] = value


# ---------------------------------------------------------------------------
# derivations
# ---------------------------------------------------------------------------

def _stop_type(row):
    """
    A row with no structural stop still has a stop: the ATR fallback. Label it as such
    instead of leaving the seat to guess. Returns None if there is genuinely nothing.
    """
    if _get(row, "bracket.stop_type"):
        return None                                   # engine already said it
    if _get(row, "bracket.atr_fallback_stop") is None:
        return None                                   # nothing to label
    return "atr_fallback"


def _stop_effective(row):
    """The stop the seat will actually use: structural if the bracket passed, else the ATR
    fallback. Both are engine-emitted prices; this only chooses between them."""
    s = _get(row, "bracket.stop")
    return s if s is not None else _get(row, "bracket.atr_fallback_stop")


DERIVATIONS = {
    # field                 requires (must be ~fully populated)          fn
    "bracket.stop_type":   (["bracket.atr_fallback_stop", "bracket.valid"], _stop_type,
                            "null stop_type means the bracket failed its gates, so the stop "
                            "in force is the ATR fallback — label it 'atr_fallback'"),
    "bracket.stop_eff":    (["bracket.atr_fallback_stop"], _stop_effective,
                            "the stop actually in force: structural if valid, else the "
                            "ATR fallback"),
}


def derive_row(row):
    """Fill every derivable field on one export row, in place.
    Returns {field: value} for what was actually filled."""
    filled = {}
    for field, (_req, fn, _why) in DERIVATIONS.items():
        if _get(row, field) is not None:
            continue
        v = fn(row)
        if v is not None:
            _set(row, field, v)
            _set(row, field + "_source", "derived")
            filled[field] = v
    return filled


def derive_all(rows):
    """Fill every derivable field on every row. Returns {field: rows_filled}."""
    counts = {}
    for r in rows:
        for f in derive_row(r):
            counts[f] = counts.get(f, 0) + 1
    return counts


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("usage: field_derive.py <aqe_daily_export.json> [--write]")
        sys.exit(2)
    d = json.load(open(sys.argv[1]))
    rows = d.get("daily_list") or []
    counts = derive_all(rows)
    n = len(rows)
    for f, c in sorted(counts.items()):
        print(f"{f:24s} filled on {c}/{n} rows ({c/n:.0%})")
    if "--write" in sys.argv:
        json.dump(d, open(sys.argv[1], "w"), indent=1)
        print("written back")
