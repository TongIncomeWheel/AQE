"""VALEN's macro cockpit — Crown Macro readings given a VALEN-style visual
face, inside Part 1 Weather. The one place Crown and VALEN already touched
before this was GEX (src/valen/gex.py): VALEN reads Crown's finished
artifact read-only and renders it in VALEN's own gauge/LED/tag language;
Crown computes nothing for VALEN and stays standalone (a test forbids the
reverse import — PM directive 2026-08-09). This module is five more
instances of that exact pattern, not a merge of the two layers' code — a
PM ask (2026-10-02), "how Crown and VALEN can be combined... more cockpit
illustration within VALEN's structure," answered "all 5" for breadth
range, CTA crowding, dispersion, divergence and COT crowding.

Every reading here degrades to UNAVAILABLE on the SAME crown_status_ok()
gate rather than five separate reasons — Crown's own top-level status
already answers "can I trust anything from this run," so every cockpit
widget asks that one question once, the same way GEX's own `status` check
already does for the gamma block specifically. Sizing concepts (CTA's own
`size_adjustment`, the_call's size multiplier) are deliberately left out —
same "AQE makes no decisions, no sizing" charter GEX's own sizing guide
already ships as quoted doctrine text, never a computed field.
"""

from __future__ import annotations


def crown_status_ok(crown: dict | None) -> tuple[bool, str | None]:
    """Crown's own top-level status — OK/DEGRADED render fine (DEGRADED
    means some input was missing or substituted, not that this run is
    untrustworthy — Crown's own page shows its full content in that case
    too, just with a warning banner); EARLY_EXIT/UNAVAILABLE, or no Crown
    read at all, gate every widget below with one shared reason."""
    if not crown:
        return False, "Crown macro has not run yet this session"
    status = crown.get("crown_status")
    if status in ("EARLY_EXIT", "UNAVAILABLE"):
        return False, f"Crown macro status: {status}"
    return True, None


def _unavailable(reason: str) -> dict:
    return {"status": "UNAVAILABLE", "reason": reason}


def breadth_range_reading(crown: dict | None) -> dict:
    """RSP/SPY's position in its own 12-month range (crown.heartbeat) —
    the same instrument Crown's own plain-English read already quotes
    ("breadth near the bottom of its range"), given a gauge face."""
    ok, reason = crown_status_ok(crown)
    if not ok:
        return _unavailable(reason)
    hb = (crown or {}).get("heartbeat") or {}
    range_pct = hb.get("range_pct")
    if range_pct is None:
        return _unavailable("no heartbeat read this run")
    return {"status": "OK", "range_pct": round(range_pct * 100, 1),
           "regime": hb.get("regime"), "range_position": hb.get("range_position"),
           "confidence": hb.get("confidence")}


def cta_crowding_reading(crown: dict | None) -> dict:
    """How crowded trend-following flow is across the 18 markets Crown
    tracks (crown.cta) — a high flip_risk means a lot of money is already
    leaning the same way, which is fragile, not confident."""
    ok, reason = crown_status_ok(crown)
    if not ok:
        return _unavailable(reason)
    cta = (crown or {}).get("cta") or {}
    flip_risk = cta.get("flip_risk")
    if flip_risk is None:
        return _unavailable("no CTA read this run")
    return {"status": "OK", "flip_risk_pct": round(flip_risk * 100, 1),
           "bias": cta.get("overall_bias"), "n_markets": cta.get("n_markets")}


def dispersion_reading(crown: dict | None) -> dict:
    """How much more individual stocks are moving than the index
    (crown.volatility.dispersion) — a wide, GROWING gap means the index is
    hiding what single names are doing. Judged against the same 20/80
    percentile bands Crown itself uses (spec.py's DISPERSION_*_PCTL),
    never re-derived here."""
    ok, reason = crown_status_ok(crown)
    if not ok:
        return _unavailable(reason)
    vol = (crown or {}).get("volatility") or {}
    if vol.get("status") == "UNAVAILABLE":
        return _unavailable("no dispersion read this run")
    disp = vol.get("dispersion") or {}
    pctl = disp.get("percentile")
    if pctl is None:
        return _unavailable("no dispersion percentile this run")
    return {"status": "OK", "percentile_pct": round(pctl * 100, 1),
           "state": disp.get("state"), "direction": disp.get("direction"),
           "basis": disp.get("basis")}


def divergence_reading(crown: dict | None) -> dict:
    """How many of Crown's 8 named, independent divergence checks are lit
    right now (crown.divergence) — one warning alone is a straw; several
    agreeing is what the handbook calls a pile of them."""
    ok, reason = crown_status_ok(crown)
    if not ok:
        return _unavailable(reason)
    div = (crown or {}).get("divergence") or {}
    count = div.get("count")
    if count is None:
        return _unavailable("no divergence read this run")
    return {"status": "OK", "count": count, "total": 8,
           "types_fired": div.get("types_fired") or []}


def cot_reading(crown: dict | None) -> dict:
    """Which futures markets large speculators are crowded into, straight
    from cftc.gov (crown.cot) — at least three days old by the time it
    lands here, so it never times anything, only shows where the crowd
    already is."""
    ok, reason = crown_status_ok(crown)
    if not ok:
        return _unavailable(reason)
    cot = (crown or {}).get("cot") or {}
    as_of = cot.get("as_of")
    if as_of is None:
        return _unavailable("no COT read this run")
    return {"status": "OK", "as_of": as_of,
           "crowded_long": cot.get("crowded_long") or [],
           "crowded_short": cot.get("crowded_short") or []}


def compute_crown_cockpit(crown: dict | None) -> dict:
    """All five readings in one call — the shape VALEN's daily.py stashes
    on the artifact and card.py reads back for the page."""
    return {
        "breadth_range": breadth_range_reading(crown),
        "cta_crowding": cta_crowding_reading(crown),
        "dispersion": dispersion_reading(crown),
        "divergence": divergence_reading(crown),
        "cot": cot_reading(crown),
    }
