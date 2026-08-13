"""VIX regime classification — portfolio-level, macro sizing input.

PTRS and the disposition ceiling that replaced it are both retired
(2026-08-13). Both were a re-read of SC_MOMENTUM through a threshold table
that nothing downstream consumed to change behaviour — the shortlist's own
floor is now a direct SC_MOMENTUM comparison in
`daily_orchestrator._compute_candidates`, not a disposition label. See
`docs/AQE_DATA_TAXONOMY.csv` for what actually gates the shortlist.

This module now holds the one piece of it that was real: the VIX bucket,
which sets the regime's own size ceiling and is unrelated to any per-ticker
score.
"""

from __future__ import annotations


def classify_vix_regime(vix: float) -> str:
    if vix > 30:
        return "RED"
    elif vix > 25:
        return "ORANGE"
    elif vix > 18:
        return "YELLOW"
    else:
        return "GREEN"
