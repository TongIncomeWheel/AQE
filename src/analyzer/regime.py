"""Regime detection — VIX classification + Hurst exponent (Chan EC-4).

Hurst exponent on SPY 60-day returns:
    H > 0.55: TRENDING  — momentum strategies favoured
    H ~ 0.50: RANDOM    — no edge either way
    H < 0.45: MEAN_REVERT — momentum gets chopped up

Uses rescaled range (R/S) method. No external dependencies.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analyzer.ptrs import classify_vix_regime


def hurst_exponent(prices: np.ndarray, min_window: int = 10) -> float:
    """Compute Hurst exponent via rescaled range (R/S) analysis.

    prices: array of close prices (not returns).
    Returns H in [0, 1]. Uses log-log regression of R/S vs window size.
    """
    if len(prices) < min_window * 2:
        return 0.50  # default to random walk if insufficient data

    returns = np.diff(np.log(prices))
    returns = returns[np.isfinite(returns)]
    if len(returns) < min_window * 2:
        return 0.50

    n = len(returns)
    # Window sizes: powers of 2 that fit within the data
    max_k = int(np.floor(np.log2(n)))
    min_k = int(np.ceil(np.log2(min_window)))
    if max_k <= min_k:
        return 0.50

    window_sizes = [2**k for k in range(min_k, max_k + 1)]
    rs_values = []

    for w in window_sizes:
        n_windows = n // w
        if n_windows < 1:
            continue

        rs_list = []
        for i in range(n_windows):
            segment = returns[i * w:(i + 1) * w]
            mean_seg = np.mean(segment)
            deviate = np.cumsum(segment - mean_seg)
            r = np.max(deviate) - np.min(deviate)
            s = np.std(segment, ddof=1)
            if s > 0:
                rs_list.append(r / s)

        if rs_list:
            rs_values.append((np.log(w), np.log(np.mean(rs_list))))

    if len(rs_values) < 2:
        return 0.50

    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])

    # Linear regression: y = H * x + c
    slope = (np.sum((x - x.mean()) * (y - y.mean())) /
             np.sum((x - x.mean()) ** 2))

    return float(np.clip(slope, 0.0, 1.0))


def classify_hurst(h: float) -> str:
    if h > 0.55:
        return "TRENDING"
    elif h < 0.45:
        return "MEAN_REVERT"
    else:
        return "RANDOM"


def compute_regime(
    spy_closes: np.ndarray,
    vix: float,
    lookback: int = 60,
) -> dict:
    """Full regime assessment: VIX level + Hurst exponent."""
    vix_regime = classify_vix_regime(vix)

    prices = spy_closes[-lookback:] if len(spy_closes) >= lookback else spy_closes
    h = hurst_exponent(prices)
    hurst_regime = classify_hurst(h)

    if hurst_regime == "TRENDING":
        implication = "Momentum strategies favoured"
    elif hurst_regime == "MEAN_REVERT":
        implication = "Caution: momentum may underperform"
    else:
        implication = "No clear edge — market is random walk"

    return {
        "vix": round(vix, 1),
        "vix_regime": vix_regime,
        "hurst": round(h, 3),
        "hurst_regime": hurst_regime,
        "implication": implication,
    }


def compute_regime_from_panel(
    spy_panel: pd.DataFrame,
    vix: float = 18.0,
    lookback: int = 60,
) -> dict:
    """Convenience: compute regime from SPY panel DataFrame."""
    spy = spy_panel.sort_values("date")
    closes = spy["close"].values
    return compute_regime(closes, vix, lookback)
