"""VALEN Execution — the read-only half of the VIV handbook's Part 4
("When to walk in"). Covers piece 13 (how we enter: trigger, then volume
confirmation, then stop, in that fixed order) and piece 16 (cutting
losers: a stop-breach FACT). Pieces 14 ("sizing is arithmetic") and 15
("the three limits") are deliberately absent from this module — they are
sizing and position-limit decisions, and CLAUDE.md's "AQE makes no
decisions, no sizing" forbids computing them; the handbook's own wording
for those two ships as quoted doctrine text in the UI instead (see
src/ui/pages/7_VALEN_Dashboard.py), never as a number this module produces.

Every field read here is bracket_engine's or an existing DETECT flag's own
output — no new stop math, no new trigger detection. Pure functions of an
already-loaded row/list."""

from __future__ import annotations


def entry_sequence(row: dict) -> dict:
    """Piece 13, read in the handbook's own fixed order: trigger, then
    volume, then the stop bracket_engine already computed."""
    trigger = None
    if row.get("structure_shift") == "BULLISH_BOS":
        trigger = "Break of structure (BULLISH_BOS)"
    elif row.get("squeeze_breakout_state") == "BREAKOUT_UP":
        trigger = "Squeeze breakout (BREAKOUT_UP)"
    elif row.get("pattern_stage") == "TRIGGERED":
        trigger = f"Pattern triggered ({row.get('pattern')})"

    bracket = row.get("bracket") or {}
    return {
        "ticker": row.get("ticker"),
        "trigger": trigger,
        "volume_confirmed": row.get("squeeze_breakout_volume_confirmed"),
        "stop": bracket.get("stop"),
        "stop_type": bracket.get("stop_type"),
        "risk_pct": bracket.get("risk_pct"),
        "bracket_valid": bracket.get("valid"),
        "invalid_reason": bracket.get("invalid_reason"),
    }


def entry_candidates(daily_list: list[dict], only_candidates: bool = True) -> list[dict]:
    """Every candidate with a real trigger AND a bracket to show — a row
    with no trigger recognised is left out rather than shown as a false
    "nothing to enter on" read for a name that simply isn't set up today."""
    rows = daily_list
    if only_candidates:
        rows = [r for r in daily_list
               if r.get("on_longlist") or r.get("on_elder") or r.get("on_qs")]
    out = [entry_sequence(r) for r in rows if r.get("bracket")]
    return [e for e in out if e["trigger"] is not None]


def stop_breach(held_row: dict) -> dict:
    """Piece 16 — a fact, never a decision: is the live price already
    through the position's own stop? `held_sl` can be null (a documented
    PTJ journal gap) — that reads as UNKNOWN, never as "clear.\""""
    sl = held_row.get("held_sl")
    live = held_row.get("live_px")
    if sl is None or live is None:
        return {"ticker": held_row.get("ticker"), "status": "UNKNOWN",
               "reason": "no stop or live price on this position"}
    return {"ticker": held_row.get("ticker"), "status": "OK",
           "breached": bool(live <= sl), "live_px": live, "held_sl": sl}


def stop_breaches(held_positions: list[dict]) -> list[dict]:
    return [stop_breach(h) for h in held_positions]
