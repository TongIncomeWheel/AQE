"""VALEN GEX Traffic Light — a Weather companion instrument (Part 1, piece
01: "check the market first"). Answers one question in one glance: will the
market be calm or wild, and how fragile is the current level. Negative GEX
(below the flip) = fast and wild; positive GEX = slow and calm.

GEX is a RISK FILTER, not a trade signal — it never generates a trade, and
per CLAUDE.md's "AQE makes no decisions, no sizing" charter, it never
computes a position size either. The traffic light and its one-line
commentary are a market READING (same category as `stance`/`regime`); the
handbook's own sizing guide (100%/75%/50% by light colour) ships as quoted
doctrine text in the UI only — see theme.py's `gex_sizing_doctrine_html` —
never as a field this module returns.

No new data pull: reuses Crown Macro's own real gamma computation
(src/macro/crown/gamma.py) — a genuine per-contract OI x gamma x 100 x
spot^2 x 0.01 sum from Alpaca/Tiger options chains with real open interest,
already producing `gamma_flip`/`call_wall`/`put_wall` for SPY and QQQ. Crown
runs at Step 6f, before VALEN's own Step 6i, so its output is already on
disk by the time this reads it. Honors the SAME "UNAVAILABLE, never a flat
read" discipline Crown itself holds to: a missing feed degrades to
UNAVAILABLE, never a fabricated GREEN/calm reading.
"""

from __future__ import annotations

from . import spec as S


def gex_light(price: float, flip: float, call_wall: float | None,
              put_wall: float | None) -> dict:
    """The frozen rule table, checked in this exact order, first match wins
    — transcribed from the GEX Traffic Light spec's own reference
    pseudocode, never re-derived. `call_wall`/`put_wall` may be None (a
    wall that didn't clear the dominance test) — rules that need one are
    simply skipped, never treated as zero."""
    if price < flip:
        return {"light": "RED",
                "commentary": "Below flip: moves get amplified. Cut size, tighten stops."}
    if put_wall is not None and price < put_wall:
        return {"light": "RED",
                "commentary": "Put wall broken: selloff feeds itself. Reduce exposure."}
    if price <= flip * (1 + S.GEX_AMBER_ABOVE_FLIP_PCT / 100):
        return {"light": "AMBER",
                "commentary": "Just above flip: fragile. A small drop enters the wild zone."}
    if (call_wall is not None and call_wall > 0
            and abs(price - call_wall) / call_wall <= S.GEX_AMBER_NEAR_CALL_WALL_PCT / 100):
        return {"light": "AMBER",
                "commentary": "At call wall: rally likely to stall. Don't chase."}
    if call_wall is not None and price > call_wall:
        return {"light": "GREEN",
                "commentary": "Call wall cleared: ceiling gone, momentum can run."}
    return {"light": "GREEN",
            "commentary": "Above flip: calm regime. Normal size, normal stops."}


def dealer_positioning_sentence(u: dict | None) -> str | None:
    """One plain sentence translating the raw dealer-positioning numbers
    into what a trader actually does with them — regime -> volatile/calm,
    put wall -> support, call wall -> resistance, the flip (when found) ->
    the pivot that flips one into the other. A PM ask (2026-10-01): "it's
    just easier to write it out — volatile market, support XXX, breakout
    YYY, resistance XXX" instead of reading four raw numbers and inferring
    what they mean. Built from whatever subset is actually available —
    unlike gex_light()'s red/amber/green rule, this never needs the flip
    (a real SPY session, 2026-10-01: regime/walls computed fine, no flip
    found in the ±15% strike band — see gamma.py's _zero_crossing) and
    still has something worth saying."""
    if not u or not u.get("available"):
        return None
    regime = u.get("regime")
    if regime == "NEGATIVE":
        read = ("Volatile market — dealers are short gamma and amplify "
                "moves in both directions")
    elif regime == "POSITIVE":
        read = ("Calm market — dealers are long gamma and dampen moves "
                "(price tends to pin)")
    else:
        return None

    price = u.get("spot")
    flip = u.get("gamma_flip")
    call_wall = (u.get("call_wall") or {}).get("strike")
    put_wall = (u.get("put_wall") or {}).get("strike")

    levels = []
    if put_wall is not None:
        levels.append(f"support ~{put_wall:.0f}")
    if flip is not None and price is not None:
        if price < flip:
            levels.append(f"breakout level ~{flip:.0f} (reclaiming it calms the market)")
        else:
            levels.append(f"breakdown level ~{flip:.0f} (losing it turns the market volatile)")
    if call_wall is not None:
        levels.append(f"resistance ~{call_wall:.0f}")

    if not levels:
        return read + "."
    return f"{read}: " + ", ".join(levels) + "."


def compute_gex_reading(crown_gamma: dict | None, ticker: str = S.GEX_TICKER) -> dict:
    """Reads Crown's already-computed gamma block for `ticker` and applies
    the traffic-light rule. Never raises; degrades to UNAVAILABLE with a
    real reason on any miss — a crown read of None (Crown didn't run),
    gamma.status != "OK" (Crown ran but every underlying's fetch failed),
    or this ticker missing/unavailable within a run that succeeded for
    others.

    When the underlying itself IS available but the flip specifically
    wasn't found (a real, data-dependent outcome — see
    dealer_positioning_sentence()), the light can't be assigned but the
    regime/walls/dealer_read are still attached rather than blanked —
    "can't give a red/amber/green" and "can't say anything" are different
    facts, and the second one shouldn't follow automatically from the
    first."""
    if not crown_gamma:
        return {"status": "UNAVAILABLE", "ticker": ticker,
               "reason": "Crown macro has not run yet this session"}
    if crown_gamma.get("status") != "OK":
        return {"status": "UNAVAILABLE", "ticker": ticker,
               "reason": crown_gamma.get("reason") or "Crown gamma unavailable this run"}

    underlyings = crown_gamma.get("underlyings") or {}
    u = underlyings.get(ticker)
    if not u or not u.get("available"):
        reason = ((crown_gamma.get("unavailable") or {}).get(ticker)
                 or "no gamma data for this ticker")
        return {"status": "UNAVAILABLE", "ticker": ticker, "reason": reason}

    price = u.get("spot")
    flip = u.get("gamma_flip")
    call_wall = (u.get("call_wall") or {}).get("strike")
    put_wall = (u.get("put_wall") or {}).get("strike")
    dealer_read = dealer_positioning_sentence(u)

    if price is None or flip is None:
        return {
            "status": "UNAVAILABLE", "ticker": ticker,
            "reason": ("missing spot price" if price is None
                      else "no gamma flip found in today's strike band"),
            "price": round(price, 2) if price is not None else None,
            "call_wall": round(call_wall, 2) if call_wall is not None else None,
            "put_wall": round(put_wall, 2) if put_wall is not None else None,
            "regime": u.get("regime"), "dealer_read": dealer_read,
        }

    rule = gex_light(price, flip, call_wall, put_wall)

    return {
        "status": "OK", "ticker": ticker,
        "price": round(price, 2), "flip": round(flip, 2),
        "call_wall": round(call_wall, 2) if call_wall is not None else None,
        "put_wall": round(put_wall, 2) if put_wall is not None else None,
        "flip_distance_pct": u.get("flip_distance_pct"),
        "total_gex": u.get("total_gex"), "regime": u.get("regime"),
        "light": rule["light"], "commentary": rule["commentary"],
        "assumption": u.get("assumption"), "dealer_read": dealer_read,
    }
