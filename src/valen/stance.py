"""VALEN stance — combines trend + extension + breadth into ONE market
reading: RISK_ON | NEUTRAL | RISK_OFF | None.

READING ONLY (CLAUDE.md: "AQE makes no decisions, no sizing"). This value
sits beside AQE's own `regime` field, in the same category — never a size,
size tier, or disposition; see docs/AQE_VALEN_DASHBOARD_PROPOSAL.md §2.1.
The handbook's own "what I do with each answer" sizing guidance is UI-only
quoted doctrine, never computed here and never exported.

The stance's own flip rules (piece 01 + web edition) are WHOLE-MARKET
breadth rules — "monthly big risers clear 350" is unreachable on AQE's
curated ~819-ticker panel (proposal §2.2). Until Phase 2 wires in a
market-wide breadth population (src/scanner/ma_scanner.py, widened), this
module is honest about not being able to flip the stance on rules it cannot
evaluate: status is DEGRADED and stance is None — never a guess dressed up
as a reading. Trend and extension still compute and still render; only the
one-word stance withholds itself.

Documented simplification, flagged for Phase 2: the handbook's own language
("it flips when a rule is met") suggests hysteresis — a persisted stance
that only CHANGES on a flip event, not a value recomputed from scratch each
day. This module computes a fresh pure read each run instead. That is a
real difference worth resolving before Phase 2 ships (state would need to
live in aqe.db, same pattern as qs_store.py's persistence), but it cannot
matter until breadth is available to flip on in the first place.
"""

from __future__ import annotations

from . import spec as S

_REQUIRED_BREADTH_KEYS = (
    "pct_above_40d", "monthly_risers", "five_day_count", "daily_count_green",
)


def compute_stance(trend: dict, extension: dict, breadth: dict) -> dict:
    """`breadth` = {key: {"status": "OK", "value": ...} | UNAVAILABLE shape}
    for each of _REQUIRED_BREADTH_KEYS — see extension.whole_market_breadth_
    unavailable() for the UNAVAILABLE shape.
    """
    missing = [k for k in _REQUIRED_BREADTH_KEYS
               if (breadth.get(k) or {}).get("status") != "OK"]
    if missing:
        return {
            "stance": None, "status": "DEGRADED",
            "reason": f"whole-market breadth unavailable: {', '.join(missing)}",
            "rules": {}, "watch_for": [],
        }

    pct40 = breadth["pct_above_40d"]["value"]
    risers = breadth["monthly_risers"]["value"]
    five_day = breadth["five_day_count"]["value"]
    daily_green = bool(breadth["daily_count_green"]["value"])

    to_positive = (pct40 >= S.STANCE_TO_POSITIVE_PCT_ABOVE_40D
                   and risers >= S.STANCE_TO_POSITIVE_MONTHLY_RISERS
                   and five_day >= S.STANCE_TO_POSITIVE_5D_COUNT)
    to_negative = (not daily_green) or (five_day < S.STANCE_TO_NEGATIVE_5D_COUNT)

    if to_negative:
        stance = S.STANCE_RISK_OFF
    elif to_positive:
        stance = S.STANCE_RISK_ON
    else:
        stance = S.STANCE_NEUTRAL

    watch_for = [
        {"what": "Stocks above their 40-day line", "now": pct40,
         "level": S.STANCE_TO_POSITIVE_PCT_ABOVE_40D, "direction": "to_positive"},
        {"what": "Monthly big risers (25%+)", "now": risers,
         "level": S.STANCE_TO_POSITIVE_MONTHLY_RISERS, "direction": "to_positive"},
        {"what": "5-day up/down 4% count", "now": five_day,
         "level": S.STANCE_TO_POSITIVE_5D_COUNT, "direction": "to_positive"},
        {"what": "5-day up/down 4% count", "now": five_day,
         "level": S.STANCE_TO_NEGATIVE_5D_COUNT, "direction": "to_negative"},
    ]

    return {"stance": stance, "status": "OK", "reason": None,
            "rules": {"to_positive": to_positive, "to_negative": to_negative},
            "watch_for": watch_for}
