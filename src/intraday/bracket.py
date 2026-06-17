"""Operative stop + momentum-conditioned entry zone + bracket assembly.

Fixes AQE's two real-money problems:
  • the stop — selects an operative stop anchored to REAL intraday support
    (intraday swing low / VWAP / opening-range low / prior-day low) plus AQE's
    daily `structural_levels`, kept only if it passes the charter's 3 gates
    (ATR floor, R:R-to-TP2 ≥ 2, regime stop-% ceiling).
  • the entry — a state-driven entry zone that never chases (bounded by the
    export's `max_chase_tp2`), and stands down when momentum is gone.

Pure functions: bars (normalised dicts from momentum.normalize_bars) + the AQE
export record + the momentum read. No network I/O.
"""

from __future__ import annotations

import math

from . import config as C


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _intraday_swing_low(bars: list[dict], price: float, k: int = C.PIVOT_K):
    """Most-recent confirmed fractal pivot low below price (today's session)."""
    if len(bars) < 2 * k + 1:
        return None
    lows = [b["l"] for b in bars]
    for i in range(len(lows) - k - 1, k - 1, -1):
        seg = lows[i - k:i + k + 1]
        if lows[i] <= min(seg) and lows[i] < price:
            return round(lows[i], 2)
    return None


def _tp2_target(rec: dict, entry: float) -> float | None:
    """The TP2 price used for the R:R gate — structural TP2 if present, else dsl_tp_2r."""
    tgts = rec.get("structural_targets") or []
    above = [t.get("price") for t in tgts
             if isinstance(t, dict) and _num(t.get("price")) and t["price"] > entry]
    if len(above) >= 2:
        return float(sorted(above)[1])     # 2nd structural target ≈ TP2
    if above:
        return float(above[0])
    return _num(rec.get("dsl_tp_2r"))


def candidate_stops(bars: list[dict], rec: dict, momentum: dict) -> list[dict]:
    """All candidate stop PRICES below the current price, de-duped, with source."""
    comp = momentum.get("components", {})
    price = comp.get("price") or (bars[-1]["c"] if bars else None)
    if price is None:
        return []
    vwap = comp.get("vwap")
    iatr = comp.get("intraday_atr") or 0.0
    seen: set[float] = set()
    out: list[dict] = []

    def add(typ, p):
        p = _num(p)
        if p is None or p >= price or p <= 0:
            return
        r = round(float(p), 2)
        if r in seen:
            return
        seen.add(r)
        out.append({"type": typ, "price": r})

    add("intraday_swing_low", _intraday_swing_low(bars, price))
    if vwap is not None and iatr:
        add("vwap_buffer", vwap - C.VWAP_STOP_ATR * iatr)
    add("opening_range_low", comp.get("or_low"))
    # prior-day low from the bar history (the session before today)
    by_day: dict = {}
    for b in bars:
        by_day.setdefault(b["dt"].date(), []).append(b)
    days = sorted(by_day)
    if len(days) >= 2:
        add("prior_day_low", min(x["l"] for x in by_day[days[-2]]))
    # AQE daily structural levels (already validated structure)
    for lvl in (rec.get("structural_levels") or []):
        if isinstance(lvl, dict):
            add(f"aqe_{lvl.get('type', 'struct')}", lvl.get("price"))
    return out


def operative_stop(bars: list[dict], rec: dict, momentum: dict,
                   planned_entry: float, regime=None) -> dict:
    """Pick the TIGHTEST candidate passing all 3 charter gates.

    Returns {price, type, risk, atr_ratio, rr_tp2, stop_pct, valid, ceiling_ok,
    ceiling_pct, gated_out}. Falls back to AQE dsl_stop (flagged) if none pass.
    """
    atr14 = _num(rec.get("atr_14d")) or _num(rec.get("atr14"))
    tp2 = _tp2_target(rec, planned_entry)
    ceiling = C.regime_stop_ceiling(regime)

    scored = []
    for cand in candidate_stops(bars, rec, momentum):
        risk = planned_entry - cand["price"]
        if risk <= 0:
            continue
        atr_ratio = (risk / atr14) if atr14 else None
        rr_tp2 = ((tp2 - planned_entry) / risk) if tp2 else None
        stop_pct = risk / planned_entry * 100.0
        gate_atr = (atr_ratio is not None and atr_ratio >= C.MIN_ATR_RATIO)
        gate_rr = (rr_tp2 is not None and rr_tp2 >= C.MIN_RR_TP2)
        gate_ceiling = stop_pct <= ceiling
        scored.append({
            **cand, "risk": round(risk, 2),
            "atr_ratio": round(atr_ratio, 2) if atr_ratio is not None else None,
            "rr_tp2": round(rr_tp2, 2) if rr_tp2 is not None else None,
            "stop_pct": round(stop_pct, 2),
            "valid": bool(gate_atr and gate_rr and gate_ceiling),
            "ceiling_ok": gate_ceiling,
            "ceiling_pct": ceiling,
        })

    valids = [s for s in scored if s["valid"]]
    if valids:
        best = max(valids, key=lambda s: s["price"])   # tightest passing all gates
        best["gated_out"] = False
        return best
    # No candidate cleared all three gates → fall back to AQE dsl_stop, flagged.
    dsl = _num(rec.get("dsl_stop"))
    if dsl is not None and dsl < planned_entry:
        risk = planned_entry - dsl
        return {
            "type": "dsl_stop_fallback", "price": round(dsl, 2),
            "risk": round(risk, 2),
            "atr_ratio": round(risk / atr14, 2) if atr14 else None,
            "rr_tp2": round((tp2 - planned_entry) / risk, 2) if tp2 else None,
            "stop_pct": round(risk / planned_entry * 100, 2),
            "valid": False, "ceiling_ok": (risk / planned_entry * 100) <= ceiling,
            "ceiling_pct": ceiling, "gated_out": True,
        }
    return {"type": None, "price": None, "valid": False, "gated_out": True,
            "ceiling_pct": ceiling}


def entry_zone(rec: dict, momentum: dict) -> dict:
    """State-driven buy zone. {low, high, kind, note} or kind='stand_down'."""
    comp = momentum.get("components", {})
    state = momentum.get("state", "UNKNOWN")
    price = comp.get("price")
    vwap = comp.get("vwap")
    or_high = comp.get("or_high")
    max_chase = _num(rec.get("max_chase_tp2"))
    cap = max_chase if max_chase is not None else (price * 1.02 if price else None)

    if state in ("FADING", "BROKEN", "UNKNOWN"):
        return {"kind": "stand_down", "low": None, "high": None,
                "note": f"{state}: no intraday momentum — stand down."}

    if state == "EXTENDED":
        support = vwap if vwap is not None else price
        if cap is not None and support > cap:
            return {"kind": "stand_down", "low": None, "high": None,
                    "note": "Extended; even a VWAP pullback breaches max-chase "
                            "(R:R-TP2<2) — wait or skip."}
        return {"kind": "limit", "low": round(support, 2),
                "high": round(min(price, cap) if cap else price, 2),
                "note": "Extended — buy the pullback toward VWAP, do not chase."}

    if state == "COILING":
        trig = or_high if or_high is not None else price
        hi = min(trig * 1.003, cap) if cap else trig * 1.003
        return {"kind": "stop_breakout", "low": round(trig, 2), "high": round(hi, 2),
                "note": "Coiling above VWAP — buy-stop on the range/OR break."}

    if state == "PULLBACK_HOLDING":
        lo = vwap if vwap is not None else price
        return {"kind": "limit", "low": round(min(lo, price), 2),
                "high": round(min(price, cap) if cap else price, 2),
                "note": "Pulled back to VWAP and holding — best R:R entry zone."}

    # ACCELERATING (and not extended)
    hi = min(price * 1.005, cap) if cap else price * 1.005
    if cap is not None and price > cap:
        return {"kind": "stand_down", "low": None, "high": None,
                "note": "Accelerating but already past max-chase (R:R-TP2<2) — "
                        "wait for a pullback."}
    return {"kind": "now", "low": round(price * 0.999, 2), "high": round(hi, 2),
            "note": "Accelerating, not extended — enter now (small band)."}


def build_bracket(rec: dict, bars: list[dict], momentum: dict,
                  regime=None, risk_budget: float = C.RISK_BUDGET) -> dict:
    """Assemble entry zone + operative stop + TP ladder + size + verdict."""
    zone = entry_zone(rec, momentum)
    if zone["kind"] == "stand_down":
        return {"action": "STAND_DOWN", "entry_zone": zone,
                "operative_stop": None, "tp_ladder": [], "rr": None,
                "shares": 0, "verdict": zone["note"]}

    # Reference entry = the worse (higher) edge of the zone → conservative R:R.
    planned_entry = zone["high"] or zone["low"]
    op = operative_stop(bars, rec, momentum, planned_entry, regime)

    tp_ladder = []
    for t in (rec.get("structural_targets") or []):
        if isinstance(t, dict) and _num(t.get("price")) and t["price"] > planned_entry:
            tp_ladder.append({"type": t.get("type"), "price": t["price"]})
    if not tp_ladder:
        for key in ("dsl_tp_1r", "dsl_tp_2r", "dsl_tp_3r"):
            p = _num(rec.get(key))
            if p and p > planned_entry:
                tp_ladder.append({"type": key, "price": p})
    tp_ladder = sorted(tp_ladder, key=lambda x: x["price"])[:3]

    risk = op.get("risk") if op else None
    shares = int(math.floor(risk_budget / risk)) if risk else 0
    tp2 = tp_ladder[1]["price"] if len(tp_ladder) >= 2 else (
        tp_ladder[0]["price"] if tp_ladder else None)
    rr = round((tp2 - planned_entry) / risk, 2) if (tp2 and risk) else None

    # Verdict
    state = momentum.get("state")
    ims = momentum.get("ims")
    if op and op.get("gated_out"):
        verdict = (f"{state} (IMS {ims}): no intraday stop cleared the regime "
                   f"≤{op.get('ceiling_pct')}% / R:R≥2 gates — size down or skip. "
                   f"{zone['note']}")
        action = "CAUTION"
    else:
        verdict = (f"{state} (IMS {ims}): {zone['note']} Stop {op['price']} "
                   f"({op['type']}, {op.get('stop_pct')}%), {shares} sh, R:R≈{rr}.")
        action = "ENTER"

    return {"action": action, "entry_zone": zone, "operative_stop": op,
            "tp_ladder": tp_ladder, "rr": rr, "shares": shares,
            "planned_entry": round(planned_entry, 2), "verdict": verdict}
