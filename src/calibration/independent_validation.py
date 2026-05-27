"""Independent statistical validation — three methods that don't share assumptions.

Each method answers a different question:
1. Permutation Test: "Is this recipe's edge REAL, or could random shuffling produce the same?"
2. MinTRL (Minimum Track Record Length): "Do we have ENOUGH trades to trust the Sharpe ratio?"
3. Regime-Conditional: "Does the recipe work in DIFFERENT market conditions, or just one lucky period?"

These are fully independent from DSR, WFER, and Monte Carlo. Together with those,
they form 6 independent lines of evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


# ─── 1. Permutation Test ─────────────────────────────────────────────────

@dataclass
class PermutationResult:
    observed_avg_r: float
    observed_win_rate: float
    p_value_avg_r: float
    p_value_win_rate: float
    n_permutations: int
    percentile_avg_r: float
    percentile_win_rate: float
    is_significant: bool


def permutation_test(
    all_outcomes: pd.DataFrame,
    recipe_mask: np.ndarray,
    r_column: str = "dsl_r_realized",
    n_permutations: int = 5000,
    seed: int = 42,
) -> PermutationResult:
    """Test whether the recipe's selection is better than random selection.

    Null hypothesis: the recipe's filter doesn't select better trades than random.
    We shuffle which trades are "selected" by the recipe and recompute avg R and
    win rate each time. If the real recipe beats >95% of random selections,
    we reject H0 — the recipe has genuine predictive power.
    """
    rng = np.random.default_rng(seed)
    rs_raw = all_outcomes[r_column].values.astype(float)
    valid = ~np.isnan(rs_raw)
    rs = rs_raw[valid]
    mask = recipe_mask[valid] if len(recipe_mask) == len(rs_raw) else recipe_mask
    n_total = len(rs)
    n_selected = int(mask.sum())

    if n_selected < 30 or n_selected >= n_total:
        return PermutationResult(
            observed_avg_r=0, observed_win_rate=0,
            p_value_avg_r=1.0, p_value_win_rate=1.0,
            n_permutations=0, percentile_avg_r=0, percentile_win_rate=0,
            is_significant=False,
        )

    observed_r = float(np.mean(rs[mask]))
    observed_wr = float(np.sum(rs[mask] > 0) / n_selected)

    perm_avg_rs = np.empty(n_permutations)
    perm_win_rates = np.empty(n_permutations)

    for i in range(n_permutations):
        perm_idx = rng.choice(n_total, size=n_selected, replace=False)
        perm_rs = rs[perm_idx]
        perm_avg_rs[i] = np.mean(perm_rs)
        perm_win_rates[i] = np.sum(perm_rs > 0) / n_selected

    p_value_r = float(np.mean(perm_avg_rs >= observed_r))
    p_value_wr = float(np.mean(perm_win_rates >= observed_wr))
    pctile_r = float(np.mean(perm_avg_rs < observed_r) * 100)
    pctile_wr = float(np.mean(perm_win_rates < observed_wr) * 100)

    return PermutationResult(
        observed_avg_r=round(observed_r, 4),
        observed_win_rate=round(observed_wr, 4),
        p_value_avg_r=round(p_value_r, 4),
        p_value_win_rate=round(p_value_wr, 4),
        n_permutations=n_permutations,
        percentile_avg_r=round(pctile_r, 1),
        percentile_win_rate=round(pctile_wr, 1),
        is_significant=(p_value_r < 0.05),
    )


# ─── 2. Minimum Track Record Length (MinTRL) ─────────────────────────────

@dataclass
class MinTRLResult:
    observed_sharpe_annual: float
    min_trades_needed: float
    trades_available: int
    sufficient: bool
    confidence_level: float


def min_track_record_length(
    rs: np.ndarray,
    target_sharpe: float = 0.0,
    confidence: float = 0.95,
    trades_per_year: float = 52.0,
) -> MinTRLResult:
    """López de Prado (2014) MinTRL: minimum number of observations needed
    to conclude the Sharpe ratio is statistically > target_sharpe.

    Formula: MinTRL = 1 + (1 + skew^2/4 + kurt/4) * (z_alpha / SR)^2

    If trades_available > MinTRL, we have sufficient evidence.
    """
    n = len(rs)
    if n < 10:
        return MinTRLResult(0, float("inf"), n, False, confidence)

    avg = float(np.mean(rs))
    std = float(np.std(rs, ddof=1))
    if std == 0:
        return MinTRLResult(0, float("inf"), n, False, confidence)

    sr_per_trade = avg / std
    sr_annual = sr_per_trade * np.sqrt(trades_per_year)

    skew = float(pd.Series(rs).skew())
    kurt = float(pd.Series(rs).kurtosis())

    z_alpha = norm.ppf(confidence)
    sr_diff = sr_per_trade - (target_sharpe / np.sqrt(trades_per_year))

    if sr_diff <= 0:
        return MinTRLResult(
            round(sr_annual, 3), float("inf"), n, False, confidence,
        )

    min_trl = 1 + (1 + skew**2 / 4 + kurt / 4) * (z_alpha / sr_diff) ** 2

    return MinTRLResult(
        observed_sharpe_annual=round(sr_annual, 3),
        min_trades_needed=round(min_trl, 0),
        trades_available=n,
        sufficient=(n >= min_trl),
        confidence_level=confidence,
    )


# ─── 3. Regime-Conditional Validation ────────────────────────────────────

@dataclass
class RegimeSlice:
    regime: str
    n_trades: int
    avg_r: float
    win_rate: float
    sharpe: float
    profitable: bool


@dataclass
class RegimeResult:
    slices: list[RegimeSlice]
    n_profitable_regimes: int
    n_total_regimes: int
    all_regimes_profitable: bool


def regime_conditional_validation(
    outcomes: pd.DataFrame,
    recipe_mask: np.ndarray,
    panel: pd.DataFrame,
    r_column: str = "dsl_r_realized",
) -> RegimeResult:
    """Split by market regime and check recipe works in each.

    Regimes are defined by SPY's rolling 63-day return:
    - Bull: SPY 63d return > +5%
    - Sideways: SPY 63d return between -5% and +5%
    - Bear: SPY 63d return < -5%

    A recipe that only works in one regime is fragile.
    """
    df = outcomes.loc[recipe_mask].copy()
    if df.empty or r_column not in df.columns:
        return RegimeResult([], 0, 0, False)

    df["date"] = pd.to_datetime(df["date"])

    spy = panel.loc[panel["ticker"] == "SPY"].copy() if "ticker" in panel.columns else pd.DataFrame()
    if spy.empty:
        spy = panel.copy()

    spy = spy.sort_values("date")
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    spy["spy_ret_63d"] = spy["close"].pct_change(63)
    spy_regime = spy[["date", "spy_ret_63d"]].dropna()

    df = df.merge(spy_regime, on="date", how="left")
    df["spy_ret_63d"] = df["spy_ret_63d"].ffill()

    def _classify(ret):
        if pd.isna(ret):
            return "Unknown"
        if ret > 0.05:
            return "Bull"
        elif ret < -0.05:
            return "Bear"
        return "Sideways"

    df["regime"] = df["spy_ret_63d"].apply(_classify)

    slices = []
    for regime in ["Bull", "Sideways", "Bear"]:
        subset = df.loc[df["regime"] == regime, r_column].dropna()
        if len(subset) < 10:
            continue
        rs = subset.values
        avg = float(np.mean(rs))
        wr = float(np.sum(rs > 0) / len(rs))
        std = float(np.std(rs))
        sharpe = avg / std if std > 0 else 0
        slices.append(RegimeSlice(
            regime=regime,
            n_trades=len(rs),
            avg_r=round(avg, 4),
            win_rate=round(wr, 4),
            sharpe=round(sharpe, 3),
            profitable=(avg > 0),
        ))

    n_profitable = sum(1 for s in slices if s.profitable)
    return RegimeResult(
        slices=slices,
        n_profitable_regimes=n_profitable,
        n_total_regimes=len(slices),
        all_regimes_profitable=(n_profitable == len(slices) and len(slices) >= 2),
    )


# ─── Serialization ──────────────────────────────────────────────────────

def _to_python(obj):
    """Convert numpy/dataclass types to JSON-safe Python primitives."""
    if isinstance(obj, (np.bool_, np.generic)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_python(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_python(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    return obj


def results_to_dict(results: dict) -> dict:
    """Convert validation results to JSON-serializable dict."""
    return _to_python(results)


# ─── Combined Report ─────────────────────────────────────────────────────

def run_independent_validation(
    all_outcomes: pd.DataFrame,
    recipe_mask: np.ndarray,
    panel: pd.DataFrame,
    r_column: str = "dsl_r_realized",
) -> dict:
    """Run all three independent validations and return structured results."""
    rs = all_outcomes.loc[recipe_mask, r_column].dropna().values

    perm = permutation_test(all_outcomes, recipe_mask, r_column)
    mintrl = min_track_record_length(rs)
    regime = regime_conditional_validation(all_outcomes, recipe_mask, panel, r_column)

    return {
        "permutation": perm,
        "min_trl": mintrl,
        "regime": regime,
    }


def format_validation_report(results: dict) -> str:
    """Format the independent validation as readable text."""
    lines = []
    lines.append("=" * 90)
    lines.append("  INDEPENDENT STATISTICAL VALIDATION (3 methods, zero shared assumptions)")
    lines.append("=" * 90)

    # 1. Permutation
    p = results["permutation"]
    lines.append("\n  1. PERMUTATION TEST — 'Is this edge real, or could luck produce it?'")
    lines.append("  " + "-" * 70)
    lines.append(f"     Method: Randomly select {p.n_permutations:,} groups of the same size from ALL trades.")
    lines.append(f"     Does the recipe's selection beat random? If p < 0.05, YES.")
    lines.append(f"     Observed avg R:   {p.observed_avg_r:+.4f}")
    lines.append(f"     Observed win rate: {p.observed_win_rate*100:.1f}%")
    lines.append(f"     p-value (avg R):   {p.p_value_avg_r:.4f}  {'SIGNIFICANT' if p.p_value_avg_r < 0.05 else 'NOT significant'}")
    lines.append(f"     p-value (win rate):{p.p_value_win_rate:.4f}  {'SIGNIFICANT' if p.p_value_win_rate < 0.05 else 'NOT significant'}")
    lines.append(f"     Percentile:        {p.percentile_avg_r:.1f}th  (recipe beats {p.percentile_avg_r:.0f}% of random selections)")
    verdict_1 = "PASS" if p.is_significant else "FAIL"
    lines.append(f"     VERDICT: {verdict_1}")

    # 2. MinTRL
    m = results["min_trl"]
    lines.append("\n  2. MINIMUM TRACK RECORD LENGTH — 'Do we have enough trades?'")
    lines.append("  " + "-" * 70)
    lines.append(f"     Method: López de Prado (2014). How many trades needed to confirm Sharpe > 0?")
    lines.append(f"     Annualized Sharpe:  {m.observed_sharpe_annual:.3f}")
    lines.append(f"     Trades needed:      {m.min_trades_needed:.0f}")
    lines.append(f"     Trades available:   {m.trades_available}")
    if m.sufficient:
        lines.append(f"     VERDICT: PASS — we have {m.trades_available - m.min_trades_needed:.0f} more trades than needed")
    else:
        lines.append(f"     VERDICT: FAIL — need {m.min_trades_needed - m.trades_available:.0f} more trades")

    # 3. Regime
    r = results["regime"]
    lines.append("\n  3. REGIME-CONDITIONAL — 'Does it work in bull, sideways, AND bear?'")
    lines.append("  " + "-" * 70)
    lines.append(f"     Method: Split by SPY 63-day return. Recipe must profit in multiple regimes.")
    for s in r.slices:
        flag = "PROFIT" if s.profitable else "LOSS"
        lines.append(
            f"     {s.regime:>8}: {s.n_trades:>4} trades | Avg R {s.avg_r:+.4f} | "
            f"Win {s.win_rate*100:.1f}% | Sharpe {s.sharpe:.3f} | {flag}"
        )
    lines.append(f"     Profitable in {r.n_profitable_regimes}/{r.n_total_regimes} regimes")
    verdict_3 = "PASS" if r.all_regimes_profitable else "PARTIAL" if r.n_profitable_regimes > 0 else "FAIL"
    lines.append(f"     VERDICT: {verdict_3}")

    # Overall
    lines.append("\n" + "=" * 90)
    verdicts = [
        p.is_significant,
        m.sufficient,
        r.all_regimes_profitable,
    ]
    passing = sum(verdicts)
    lines.append(f"  OVERALL: {passing}/3 independent tests PASS")
    if passing == 3:
        lines.append("  CONCLUSION: Strong independent evidence that this recipe has genuine predictive power.")
    elif passing >= 2:
        lines.append("  CONCLUSION: Majority of evidence supports genuine edge. Monitor the failing test.")
    else:
        lines.append("  CONCLUSION: Insufficient independent evidence. Use with caution.")
    lines.append("=" * 90)

    return "\n".join(lines)
