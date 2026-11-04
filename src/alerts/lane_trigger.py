"""Lane triggers for the brief-list names (PM 2026-11-04): each AQE-list name fires on ITS lane's one trigger, not on a generic
"hourly close above the line". The lane comes from the same code the committee uses (aegis/plugin/aegis-core/tools/lanes_v1.py,
R43), so an alert and a ticket can never disagree about which lane a name is in.

  MOMENTUM_CONTINUATION  trigger = an hourly close above the CONTINUATION PIVOT (the high of its last 3-10 bar tight pause);
                         stop = the extension bracket's stop (the lower of the pause low and one daily range under price)
  MOMENTUM_BREAKOUT      trigger = an hourly close above the BASE PIVOT (last confirmed pivot high / structure ref)
  PULLBACK               trigger = an hourly close above the rising 20-DAY AVERAGE (the reclaim)
If a lane's line is not above the last close (the break already happened) or the field is missing, the name falls back to the generic
rule (prior bar's high / last pivot) and the card says so; nothing is silently dropped. Data only: nothing here sizes or decides.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LANES = _ROOT / "aegis" / "plugin" / "aegis-core" / "tools" / "lanes_v1.py"
_mod = None
_mod_err = None

LABEL = {"MOMENTUM_CONTINUATION": "Continuation", "MOMENTUM_BREAKOUT": "Breakout", "PULLBACK": "Pullback", "UNLANED": "No lane"}


def _lanes():
    global _mod, _mod_err
    if _mod is None and _mod_err is None:
        try:
            spec = importlib.util.spec_from_file_location("lanes_v1_alerts", _LANES)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            _mod = m
        except Exception as e:  # noqa: BLE001
            _mod_err = f"{e.__class__.__name__}: {e}"
    return _mod


def _n(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def lane_for(rec: dict) -> tuple[str, list[str]]:
    m = _lanes()
    if m is None:
        return "UNLANED", [f"lane module not found ({_mod_err})"]
    return m.assign_lane(rec)


def lane_trigger(rec: dict) -> dict | None:
    """-> {lane, label, line, plain, stop, note} for the lane's trigger, or {lane, label, line: None, note} when the lane line is not
    usable (caller falls back to the generic line and shows `note`). None only when the row has no entry."""
    entry = _n(rec.get("entry"))
    if entry is None or entry <= 0:
        return None
    lane, why = lane_for(rec)
    out = {"lane": lane, "label": LABEL.get(lane, lane), "line": None, "plain": None, "stop": None, "why": why}
    if lane == "MOMENTUM_CONTINUATION":
        line = _n(rec.get("continuation_pivot"))
        if line is not None and line > entry:
            out.update(line=line, plain=f"an hourly candle closes above {line:.2f}, the high of its last tight pause (continuation)")
            eb = rec.get("extension_bracket") or {}
            if eb.get("available") and _n(eb.get("stop")) is not None:
                out["stop"] = _n(eb["stop"])
        else:
            out["note"] = "its pause high is already behind price (or not served): generic break-of-prior-high line"
    elif lane == "MOMENTUM_BREAKOUT":
        line = _n((rec.get("last_pivot_high") or {}).get("price")) or _n(rec.get("pivot_high"))
        if line is not None and line > entry:
            out.update(line=line, plain=f"an hourly candle closes above {line:.2f}, its base pivot (breakout)")
        else:
            out["note"] = "its base pivot is already behind price: generic break-of-prior-high line"
    elif lane == "PULLBACK":
        line = _n(rec.get("ma_20"))
        if line is not None and line > entry:
            out.update(line=line, plain=f"an hourly candle closes above {line:.2f}, its rising 20-day average (the reclaim)")
        else:
            out["note"] = "it already holds its 20-day average: generic break-of-prior-high line"
    else:
        out["note"] = "no lane rule applies: generic line"
    return out
