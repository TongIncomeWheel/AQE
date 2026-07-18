#!/usr/bin/env python3
"""Feed tripwires — run against every AQE export BEFORE any agent reads it.
The BULLISH_BOS lesson, permanent: a field state that never fires (or always fires) is an alarm.
Exit code 0 = clean, 1 = BLOCK (orchestrator must stop and notify PM).
Usage: python3 tripwires.py path/to/aqe_daily_export.json [--history data/tripwire_history.json]
"""
import json, sys, argparse, collections

ENUM_FIELDS = ["structure_shift", "mp_state", "mp_accel_state", "choch_state", "div_state",
               "pin_bar_state", "elder_pattern", "rs_leadership", "mover_subtype"]
BRACKET_VALID_BAND = (0.03, 0.60)   # share of daily_list with bracket.valid — outside band = alarm

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export"); ap.add_argument("--history", default=None)
    ap.add_argument("--journal", default=None, help="journal file to cross-check held tickers")
    a = ap.parse_args()
    data = json.load(open(a.export))
    problems = []

    dl = data.get("daily_list", [])
    if not dl:
        problems.append("daily_list empty")
    # 1. enum distributions: any documented state observed zero times across a healthy-size list
    for f in ENUM_FIELDS:
        counts = collections.Counter(str(r.get(f)) for r in dl if f in r)
        if counts and len(counts) == 1 and len(dl) > 50:
            problems.append(f"enum '{f}' shows a single state across {len(dl)} rows: {dict(counts)} — dead or stuck field?")
    # 2. bracket validity rate band
    if dl:
        rate = sum(1 for r in dl if (r.get("bracket") or {}).get("valid")) / len(dl)
        if not BRACKET_VALID_BAND[0] <= rate <= BRACKET_VALID_BAND[1]:
            problems.append(f"bracket.valid rate {rate:.1%} outside band {BRACKET_VALID_BAND}")
    # 3. glossary/schema coverage: every glossary term should exist as a field somewhere
    gloss = set(data.get("field_glossary", {})) - {"_convention", "_decision_framework"}
    fields = set().union(*[set(r) for r in dl[:20]]) if dl else set()
    ghost = {g for g in gloss if g not in fields and not any(g in (r.get("bracket") or {}) for r in dl[:5])}
    if len(ghost) > len(gloss) * 0.4:
        problems.append(f"{len(ghost)}/{len(gloss)} glossary terms not found in records — prose/code drift?")
    # 4. held-book consistency vs journal
    if a.journal:
        j = json.load(open(a.journal))
        held_j = {p["ticker"] for p in j.get("open_positions", [])}
        held_f = {p.get("ticker") for p in data.get("held_positions", [])}
        if held_j - held_f:
            problems.append(f"journal positions missing from feed held_positions: {sorted(held_j - held_f)}")
    # 5. staleness
    if data.get("held_positions_status") not in (None, "live"):
        problems.append(f"held_positions_status = {data.get('held_positions_status')} — disclose staleness on every render")

    if problems:
        print("TRIPWIRE BLOCK:"); [print(" -", p) for p in problems]; sys.exit(1)
    print(f"tripwires clean: {len(dl)} rows"); sys.exit(0)

if __name__ == "__main__":
    main()
