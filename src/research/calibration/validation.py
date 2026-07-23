"""Calibration validation — overfitting detection and purged cross-validation.

Implements:
    PBO (Probability of Backtest Overfitting) — López de Prado MLP-2
    Purged K-Fold CV — López de Prado MLP-3
    DSR (Deflated Sharpe Ratio) — López de Prado MLP-1 (moved from recipe_optimizer)

PBO uses Combinatorially Symmetric Cross-Validation (CSCV) with 16 partitions.
Splits data into 16 time-ordered chunks, tests all C(16,8) = 12,870 train/test
splits. If the best in-sample model underperforms OOS in >40% of splits, the
system is likely overfit.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


CSCV_PARTITIONS = 16
PBO_MAXIMUM = 0.40
EMBARGO_PCT = 0.01
PURGE_WINDOW_BARS = 40


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray,
    n_partitions: int = CSCV_PARTITIONS,
) -> dict:
    """Compute PBO via Combinatorially Symmetric Cross-Validation.

    Args:
        returns_matrix: (n_trades, n_models) array. Each column is a different
            model/recipe's per-trade returns. All models evaluated on the same
            trades in the same order.
        n_partitions: number of time-ordered partitions (default 16).

    Returns:
        dict with keys: pbo, n_combinations, overfit_count, pass_threshold,
        logit_distribution (list of logit values for each combination).
    """
    n_trades, n_models = returns_matrix.shape
    if n_trades < n_partitions * 2 or n_models < 2:
        return {
            "pbo": 0.0,
            "n_combinations": 0,
            "overfit_count": 0,
            "pass_threshold": True,
            "logit_distribution": [],
        }

    partition_size = n_trades // n_partitions
    partitions = []
    for i in range(n_partitions):
        start = i * partition_size
        end = start + partition_size if i < n_partitions - 1 else n_trades
        partitions.append(returns_matrix[start:end])

    half = n_partitions // 2
    overfit_count = 0
    total = 0
    logits = []

    for train_idx in combinations(range(n_partitions), half):
        test_idx = tuple(i for i in range(n_partitions) if i not in train_idx)

        train_data = np.vstack([partitions[i] for i in train_idx])
        test_data = np.vstack([partitions[i] for i in test_idx])

        is_perf = train_data.mean(axis=0)
        oos_perf = test_data.mean(axis=0)

        best_is = int(np.argmax(is_perf))

        oos_rank = stats.rankdata(oos_perf)[best_is]
        relative_rank = oos_rank / n_models

        if relative_rank <= 0.5:
            overfit_count += 1

        epsilon = 1e-10
        logit = np.log(relative_rank / (1.0 - relative_rank + epsilon) + epsilon)
        logits.append(float(logit))

        total += 1

    pbo = overfit_count / total if total > 0 else 0.0

    return {
        "pbo": round(pbo, 4),
        "n_combinations": total,
        "overfit_count": overfit_count,
        "pass_threshold": pbo <= PBO_MAXIMUM,
        "logit_distribution": logits,
    }


def purged_kfold_cv(
    returns: pd.Series,
    dates: pd.Series,
    n_folds: int = 5,
    embargo_pct: float = EMBARGO_PCT,
    purge_bars: int = PURGE_WINDOW_BARS,
) -> dict:
    """Purged K-Fold Cross-Validation with embargo.

    Standard K-fold leaks information because trade outcomes in fold K
    overlap with the training data of fold K+1. Purging removes training
    observations whose forward windows overlap the test set. Embargo adds
    a buffer after each test set.

    Args:
        returns: Series of R-multiples (one per trade/signal).
        dates: Series of signal dates (same index as returns).
        n_folds: number of CV folds.
        embargo_pct: fraction of dataset to embargo after each test set.
        purge_bars: forward window (bars) to purge from training.

    Returns:
        dict with per-fold and aggregate metrics.
    """
    n = len(returns)
    if n < n_folds * 10:
        return {"avg_r": float("nan"), "folds": [], "n_folds": 0}

    sorted_idx = dates.argsort()
    sorted_returns = returns.iloc[sorted_idx].values
    sorted_dates = dates.iloc[sorted_idx].values

    fold_size = n // n_folds
    embargo_size = max(1, int(n * embargo_pct))

    folds = []
    for k in range(n_folds):
        test_start = k * fold_size
        test_end = min(test_start + fold_size, n)

        test_returns = sorted_returns[test_start:test_end]

        purge_start = max(0, test_start - purge_bars)
        embargo_end = min(n, test_end + embargo_size)

        train_mask = np.ones(n, dtype=bool)
        train_mask[purge_start:embargo_end] = False
        train_returns = sorted_returns[train_mask]

        if len(train_returns) == 0 or len(test_returns) == 0:
            continue

        train_avg = float(np.mean(train_returns))
        test_avg = float(np.mean(test_returns))
        train_wr = float((train_returns > 0).sum() / len(train_returns))
        test_wr = float((test_returns > 0).sum() / len(test_returns))

        folds.append({
            "fold": k + 1,
            "train_n": len(train_returns),
            "test_n": len(test_returns),
            "train_avg_r": round(train_avg, 4),
            "test_avg_r": round(test_avg, 4),
            "train_wr": round(train_wr, 3),
            "test_wr": round(test_wr, 3),
            "purged": purge_bars,
            "embargoed": embargo_size,
        })

    if not folds:
        return {"avg_r": float("nan"), "folds": [], "n_folds": 0}

    avg_test_r = np.mean([f["test_avg_r"] for f in folds])
    avg_test_wr = np.mean([f["test_wr"] for f in folds])
    cv_r = np.std([f["test_avg_r"] for f in folds]) / (abs(avg_test_r) + 1e-10)

    return {
        "avg_r": round(float(avg_test_r), 4),
        "avg_wr": round(float(avg_test_wr), 3),
        "cv_across_folds": round(float(cv_r), 3),
        "n_folds": len(folds),
        "folds": folds,
    }


def deflated_sharpe_ratio(
    sharpe_obs: float,
    n_trials: int,
    n_trades: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio (López de Prado MLP-1).

    Adjusts observed Sharpe for multiple testing. When you test N parameter
    combinations and pick the best, the expected maximum Sharpe under the null
    is E[max(N draws from N(0,1))] ~ sqrt(2*ln(N)). DSR tests whether the
    observed Sharpe significantly exceeds this threshold.

    Returns the p-value (probability that the observed Sharpe is due to chance).
    DSR < 0.05 means the result is statistically significant.
    """
    if n_trials <= 1 or n_trades <= 1:
        return 0.0

    e_max_sr = np.sqrt(2.0 * np.log(n_trials))
    e_max_sr *= (1.0 - 0.5772 / np.log(n_trials))

    se = np.sqrt(
        (1.0 - skewness * sharpe_obs + (kurtosis - 1.0) / 4.0 * sharpe_obs**2)
        / (n_trades - 1.0)
    )

    if se < 1e-10:
        return 0.0

    z = (sharpe_obs - e_max_sr) / se
    return float(stats.norm.cdf(z))
