"""PTRS — Pre-Trade Readiness Score.

PTRS = Engine_Score, VERBATIM.

Engine Score = SC_MOMENTUM (breakout pipeline) or SC_POSITION (base pipeline).

    PM ruling (2026-07, AIC Charter Amendment v2.8): the legacy Sector-Health
    (SH) additive term is DROPPED. Sector context is now a committee-level
    QUALITATIVE read via `srm` + RRG (the daily export's sector-rotation
    block), not a per-ticker score penalty/bonus — folding it into PTRS as
    well double-counted the same information. `compute_ptrs`'s `sh` parameter
    is kept (call sites still pass it explicitly) but every production call
    site passes `sh=0.0`; there is no live path where a nonzero SH reaches
    PTRS. See `docs/AQE_AIC_BRIEFING_2026-07-14.md` and
    `docs/MATHLAB_PTRS_CHANGELOG.md` for the ruling history and the incident
    this formalizes (a `+SH` fork had survived in `daily_orchestrator.py`'s
    `_compute_ptrs_all` after the rest of the pipeline moved to `sh=0.0` —
    fixed alongside this file, 2026-07-15).

Disposition bands:
    PTRS >= 60: FULL (1.0×)
    50-59:      HALF (0.5×)
    45-49:      QUARTER (0.25×)
    < 45:       REJECT

Regime (VIX) handles macro sizing separately — no double penalty.
    GREEN  (VIX <= 18): max_new_size = FULL
    YELLOW (18 < VIX <= 25): max_new_size = QUARTER
    ORANGE (25 < VIX <= 30): max_new_size = QUARTER
    RED    (VIX > 30): max_new_size = NONE (all parked)

Final sizing = min(PTRS disposition, regime max_new_size).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---- VIX Regime (portfolio-level, NOT in PTRS) ----

def classify_vix_regime(vix: float) -> str:
    if vix > 30:
        return "RED"
    elif vix > 25:
        return "ORANGE"
    elif vix > 18:
        return "YELLOW"
    else:
        return "GREEN"


# ---- PTRS Computation ----

def compute_ptrs(
    engine_score: float,
    sh: float,
    **_kwargs,
) -> dict:
    """Compute PTRS and disposition for a single candidate.

    PTRS = engine_score + sh. Every production call site passes sh=0.0 (the
    Sector-Health term is retired — see the module docstring); the parameter
    is kept for call-site compatibility, not because a nonzero SH is still
    live anywhere. No VIX/regime component — regime handles macro sizing
    separately.

    Returns dict with: ptrs, sh, disposition, max_size.
    """
    ptrs = engine_score + sh

    if ptrs >= 60:
        disposition = "FULL"
        max_size = 1.0
    elif ptrs >= 50:
        disposition = "HALF"
        max_size = 0.5
    elif ptrs >= 45:
        disposition = "QUARTER"
        max_size = 0.25
    else:
        disposition = "REJECT"
        max_size = 0.0

    return {
        "ptrs": round(ptrs, 1),
        "sh": sh,
        "disposition": disposition,
        "max_size": max_size,
    }


def compute_ptrs_batch(
    signals: pd.DataFrame,
    sector_grades: dict,
    score_column: str = "sc_momentum",
    **_kwargs,
) -> pd.DataFrame:
    """Compute PTRS for a batch of signals — aligned to the live feed.

    signals must have 'ticker' and score_column. `sector_grades` is accepted
    for call-site compatibility but is NO LONGER USED to compute SH (the
    legacy `+SH` fork this function used to implement — via `get_sector_health`
    — is retired; see the module docstring). PTRS = score_column verbatim,
    bit-for-bit identical to the production export's PTRS for the same input,
    which is the whole point: batch/backtest PTRS must never diverge from the
    live feed again.
    """
    if signals.empty:
        return signals.copy()

    results = [compute_ptrs(float(row.get(score_column, 0.0)), 0.0)
               for _, row in signals.iterrows()]

    ptrs_df = pd.DataFrame(results)
    ptrs_df.columns = [f"ptrs_{c}" if c != "ptrs" else c for c in ptrs_df.columns]
    return pd.concat([signals.reset_index(drop=True), ptrs_df.reset_index(drop=True)], axis=1)
