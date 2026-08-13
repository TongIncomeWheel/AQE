"""Regime detection — VIX classification.

Hurst-exponent trend/mean-revert classification was removed 2026-08-13
(PM: "totally useless now"). Its own accuracy note said as much: at the
60-day lookback used here, ~73% of genuinely random markets still received
a TRENDING or MEAN_REVERT label — a single day's reading was never evidence
— and the "implication" text it produced ("Momentum strategies favoured")
read as a trade decision, which AQE does not make. VIX is the sole regime
input now.
"""

from __future__ import annotations

from src.analyzer.ptrs import classify_vix_regime


def compute_regime(vix: float) -> dict:
    """VIX-only regime assessment."""
    return {
        "vix": round(vix, 1),
        "vix_regime": classify_vix_regime(vix),
    }
