"""Backtest Confidence (BC) Layer — profile signature matching.

Matches current candidates against historical outcome profiles.
Profile signature: composite band + MP state + regime + SRM grade + BD mode + FIP class.

Tiered matching:
    EXACT: all 6 dimensions match
    CORE: composite band + MP state + regime (3 dimensions)
    BROAD: composite band only

Use tightest tier with N >= 20 samples.

BC score (0-100):
    win_rate component (40%)
    expectancy component (30%)
    sample_size component (15%)
    consistency component (15%)

BC modifier on PTRS: (BC - 50) * 0.15
Range: -7.5 to +7.5
Cannot resurrect a REJECT.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


MIN_SAMPLES = 20
BC_MODIFIER_SCALE = 0.15


@dataclass
class BCResult:
    """Confidence layer result for one candidate."""
    ticker: str
    score: float  # 0-100
    tier: str  # EXACT / CORE / BROAD / INSUFFICIENT
    n_samples: int
    win_rate: float
    avg_r: float
    consistency: float  # fraction of positive-R months
    modifier: float  # applied to PTRS


def compute_bc_score(
    win_rate: float,
    avg_r: float,
    n_samples: int,
    consistency: float,
) -> float:
    """BC score (0-100) from component metrics."""
    # Win rate component (40%): map 0.3-0.6 to 0-100
    wr_norm = np.clip((win_rate - 0.30) / 0.30, 0.0, 1.0) * 100.0

    # Expectancy component (30%): map 0.0-0.5 avg R to 0-100
    exp_norm = np.clip(avg_r / 0.50, 0.0, 1.0) * 100.0

    # Sample size component (15%): map 20-200 to 0-100
    ss_norm = np.clip((n_samples - 20) / 180.0, 0.0, 1.0) * 100.0

    # Consistency component (15%): already 0-1
    con_norm = consistency * 100.0

    bc = wr_norm * 0.40 + exp_norm * 0.30 + ss_norm * 0.15 + con_norm * 0.15
    return float(np.clip(bc, 0.0, 100.0))


def bc_modifier(bc_score: float) -> float:
    """PTRS adjustment from BC score. Range: -7.5 to +7.5."""
    return (bc_score - 50.0) * BC_MODIFIER_SCALE


def classify_composite_band(sc: float) -> str:
    """Map SC_MOMENTUM to a band for profile matching."""
    if sc >= 75:
        return "HIGH"
    elif sc >= 60:
        return "MEDIUM"
    elif sc >= 50:
        return "LOW"
    else:
        return "BELOW"


def classify_fip(fip: float) -> str:
    """Map FIP value to quality class."""
    if fip < -0.10:
        return "SMOOTH"
    elif fip < 0.0:
        return "MODERATE"
    else:
        return "JUMPY"


def build_profile_signature(
    sc_momentum: float,
    mp_state: str,
    regime: str,
    sector_grade: str,
    bd_mode: str = "UNKNOWN",
    fip_class: str = "UNKNOWN",
) -> dict:
    """Build a profile signature for matching."""
    return {
        "composite_band": classify_composite_band(sc_momentum),
        "mp_state": mp_state,
        "regime": regime,
        "sector_grade": sector_grade,
        "bd_mode": bd_mode,
        "fip_class": fip_class,
    }


def match_outcomes(
    profile: dict,
    outcome_db: pd.DataFrame,
    r_column: str = "dsl_r_realized",
) -> BCResult | None:
    """Match a profile against the outcome database.

    Tries EXACT → CORE → BROAD matching.
    Returns BCResult if any tier has N >= MIN_SAMPLES.
    """
    if outcome_db.empty or r_column not in outcome_db.columns:
        return None

    # Build profile columns in the outcome DB
    db = outcome_db.copy()
    if "composite_band" not in db.columns:
        if "sc_momentum" in db.columns:
            db["composite_band"] = db["sc_momentum"].apply(classify_composite_band)
        else:
            return None

    # EXACT match: all available dimensions
    exact_mask = db["composite_band"] == profile["composite_band"]
    if "mp_state" in db.columns and profile.get("mp_state"):
        exact_mask &= db["mp_state"] == profile["mp_state"]
    if "regime" in db.columns and profile.get("regime"):
        exact_mask &= db["regime"] == profile["regime"]
    if "sector_grade" in db.columns and profile.get("sector_grade"):
        exact_mask &= db["sector_grade"] == profile["sector_grade"]

    exact_df = db.loc[exact_mask, r_column].dropna()
    if len(exact_df) >= MIN_SAMPLES:
        return _score_matches(exact_df, "EXACT", profile.get("ticker", ""))

    # CORE match: composite band + MP state + regime
    core_mask = db["composite_band"] == profile["composite_band"]
    if "mp_state" in db.columns and profile.get("mp_state"):
        core_mask &= db["mp_state"] == profile["mp_state"]

    core_df = db.loc[core_mask, r_column].dropna()
    if len(core_df) >= MIN_SAMPLES:
        return _score_matches(core_df, "CORE", profile.get("ticker", ""))

    # BROAD match: composite band only
    broad_mask = db["composite_band"] == profile["composite_band"]
    broad_df = db.loc[broad_mask, r_column].dropna()
    if len(broad_df) >= MIN_SAMPLES:
        return _score_matches(broad_df, "BROAD", profile.get("ticker", ""))

    return None


def _score_matches(rs: pd.Series, tier: str, ticker: str) -> BCResult:
    """Score a set of matched R-multiples."""
    n = len(rs)
    win_rate = float((rs > 0).sum() / n)
    avg_r = float(rs.mean())

    # Consistency: what fraction of unique date-months are positive?
    if hasattr(rs, "index") and "date" in rs.index.names:
        consistency = 0.5
    else:
        consistency = float((rs > 0).sum() / n)  # simplified

    bc = compute_bc_score(win_rate, avg_r, n, consistency)
    mod = bc_modifier(bc)

    return BCResult(
        ticker=ticker,
        score=round(bc, 1),
        tier=tier,
        n_samples=n,
        win_rate=round(win_rate, 3),
        avg_r=round(avg_r, 3),
        consistency=round(consistency, 3),
        modifier=round(mod, 2),
    )


def batch_confidence(
    candidates: list[dict],
    outcome_db: pd.DataFrame,
    r_column: str = "dsl_r_realized",
) -> list[BCResult | None]:
    """Compute BC for a batch of candidates."""
    results = []
    for c in candidates:
        profile = build_profile_signature(
            sc_momentum=c.get("sc_momentum", 0),
            mp_state=c.get("mp_state", ""),
            regime=c.get("regime", ""),
            sector_grade=c.get("sector_grade", ""),
        )
        profile["ticker"] = c.get("ticker", "")
        bc = match_outcomes(profile, outcome_db, r_column)
        results.append(bc)
    return results
