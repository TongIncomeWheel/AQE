"""Regime detection — VIX classification + Hurst exponent (Chan EC-4).

Hurst exponent on SPY 60-day returns:
    H > 0.55: TRENDING  — momentum strategies favoured
    H ~ 0.50: RANDOM    — no edge either way
    H < 0.45: MEAN_REVERT — momentum gets chopped up

Uses rescaled range (R/S). No external dependencies.

ACCURACY, MEASURED (2026-08-04, 400 synthetic series per case). The estimator
was rebuilt after simulation showed the previous one returned a mean of 0.593
on GENUINELY RANDOM data — above the 0.55 TRENDING threshold. A market with no
structure read as "momentum strategies favoured", which is the one direction a
momentum system's regime bias must not run. Three fixes, all strictly better:

    overlapping windows        the old code took NON-overlapping segments, so a
                               32-day window over 59 returns yielded ONE sample
    log-spaced window grid     powers of two gave 2 regression points at 60d;
                               a dense grid gives ~10
    Anis-Lloyd bias correction divides out the R/S a random series would show,
                               which is what re-centres the estimate on 0.5

                    mean(random)      sd    signal/noise
    before               0.593      0.265        0.51
    after                0.499      0.135        1.39

RESIDUAL NOISE IS STILL LARGE, and is the reason this stays context and never a
gate. At a 60-day lookback with the 0.45/0.55 thresholds, ~73% of genuinely
random markets still receive a TRENDING or MEAN_REVERT label. The bias is gone
and the spread is halved, but a single day's reading is not evidence. Lookback
was kept at 60 by PM choice (2026-08-04) for responsiveness; 250d would give
sd 0.063 and ~40% mislabelling, at the cost of turning over weeks not days.
"""

from __future__ import annotations

from math import lgamma

import numpy as np
import pandas as pd

from src.analyzer.ptrs import classify_vix_regime

# Overlap step as a fraction of window length. w//4 gives ~4x the samples of
# non-overlapping segments without the near-duplicate windows a step of 1
# produces (which add compute, not information).
_OVERLAP_DIVISOR = 4
_N_WINDOW_SIZES = 12      # log-spaced grid density
_MIN_REGRESSION_POINTS = 3


def _expected_rs(w: int) -> float:
    """Anis-Lloyd expected R/S for a RANDOM series of length w.

    R/S is upward-biased at small w, so raw R/S slopes read above 0.5 even on
    pure noise. Dividing by this expectation removes the bias — it is the
    single change that moves the random-data mean from 0.593 to 0.499.
    """
    k = np.arange(1, w)
    # gamma((w-1)/2) / (sqrt(pi) * gamma(w/2)), via lgamma so large w can't overflow
    ratio = np.exp(lgamma((w - 1) / 2) - lgamma(w / 2)) / np.sqrt(np.pi)
    return float((w - 0.5) / w * np.sum(np.sqrt((w - k) / k)) * ratio)


def _rescaled_range(segment: np.ndarray) -> float | None:
    s = float(np.std(segment, ddof=1))
    if s <= 0:
        return None
    deviate = np.cumsum(segment - segment.mean())
    return float((deviate.max() - deviate.min()) / s)


def hurst_exponent(prices: np.ndarray, min_window: int = 10) -> float:
    """Hurst exponent via bias-corrected rescaled-range (R/S) analysis.

    prices: array of close prices (not returns).
    Returns H in [0, 1]: >0.5 persistent (moves extend), <0.5 mean-reverting
    (moves get given back), 0.5 random walk.

    Returns 0.50 when there is not enough data to fit — note this makes 0.50
    ambiguous between "genuinely random" and "could not compute".
    """
    if len(prices) < min_window * 2:
        return 0.50  # default to random walk if insufficient data

    returns = np.diff(np.log(prices))
    returns = returns[np.isfinite(returns)]
    n = len(returns)
    if n < min_window * 2:
        return 0.50

    # Log-spaced window grid, capped at n//2 so every size still yields several
    # overlapping samples.
    hi = max(min_window, n // 2)
    if hi <= min_window:
        return 0.50
    window_sizes = sorted({
        int(round(w)) for w in np.logspace(np.log10(min_window), np.log10(hi),
                                           _N_WINDOW_SIZES)
    })

    xs: list[float] = []
    ys: list[float] = []
    for w in window_sizes:
        if w < min_window or w > n:
            continue
        step = max(1, w // _OVERLAP_DIVISOR)
        samples = [rs for i in range(0, n - w + 1, step)
                   if (rs := _rescaled_range(returns[i:i + w])) is not None]
        if not samples:
            continue
        rs_mean = float(np.mean(samples))
        expected = _expected_rs(w)
        if expected > 0:
            # Normalise out the random-series expectation, then restore the
            # sqrt(w) scaling so the fitted slope is still H (not H - 0.5).
            rs_mean = rs_mean / expected * np.sqrt(w)
        xs.append(np.log(w))
        ys.append(np.log(rs_mean))

    if len(xs) < _MIN_REGRESSION_POINTS:
        return 0.50

    x, y = np.array(xs), np.array(ys)
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
