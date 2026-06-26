"""Longlist screen — the SINGLE source of truth for what is on the longlist.

The longlist IS this screen. There is no second, separate gate: the Drive
export filters its `longlist` array with these exact thresholds (so the 15-min
alert engine, which monitors `longlist`, fires off exactly this set), and the
Scanner "Signals" sliders default to these exact values. Tighten via the
sliders; the defaults are the definition.

PM ruling (26 Jun 2026): the longlist is SC_MOM > 64 AND PTRS >= 60 AND
Elder >= 7 — nothing else. The broad raw-SC >= 50 candidate pool was noise and
was firing random alerts every evening during market hours. The standalone
Elder >= 8 list is separate and unaffected.

`MIN_SC` is an inclusive floor on the *raw* SC_MOM, so 65 == "strictly > 64".
"""

from __future__ import annotations

MIN_SC: int = 65       # raw SC_MOM floor — inclusive 65 == "> 64"
MIN_PTRS: int = 60
MIN_ELDER: int = 7


def passes(rec: dict) -> bool:
    """True if a record qualifies for the longlist (membership == slider default).

    Mirrors the Scanner slider filter exactly: raw SC_MOM (fallback gated
    SC_MOM), PTRS, and Elder against the module thresholds.
    """
    sc = rec.get("sc_momentum_raw") or rec.get("sc_momentum") or 0
    if sc < MIN_SC:
        return False
    if (rec.get("ptrs") or 0) < MIN_PTRS:
        return False
    if (rec.get("elder") or 0) < MIN_ELDER:
        return False
    return True
