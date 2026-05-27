"""PTRS — Pre-Trade Readiness Score.

PTRS = Engine_Score + SH

Engine Score = SC_MOMENTUM (breakout pipeline) or SC_POSITION (base pipeline).

Context = Sector Health (SH) only — ticker-specific context.
    SH: from SRM grade:  +3 (DEPLOY) / 0 (HOLD) / -3 (TURNING) / -5 (WATCH) / -8 (AVOID)

SH range: -8 to +3

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

    PTRS = engine_score + SH (sector health).
    No VIX/regime component — regime handles macro sizing separately.

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
    """Compute PTRS for a batch of signals.

    signals must have 'ticker' and score_column.
    sector_grades: output of srm.grade_all_sectors().
    """
    from src.engines.srm import get_sector_health

    if signals.empty:
        return signals.copy()

    results = []
    for _, row in signals.iterrows():
        engine_score = float(row.get(score_column, 0.0))
        ticker = row["ticker"]
        sh = float(get_sector_health(ticker, sector_grades))
        ptrs_result = compute_ptrs(engine_score, sh)
        results.append(ptrs_result)

    ptrs_df = pd.DataFrame(results)
    ptrs_df.columns = [f"ptrs_{c}" if c != "ptrs" else c for c in ptrs_df.columns]
    return pd.concat([signals.reset_index(drop=True), ptrs_df.reset_index(drop=True)], axis=1)
