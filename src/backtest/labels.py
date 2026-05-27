"""Triple Barrier Labeling — López de Prado MLP-4.

Instead of "did it make money?", ask "what happened FIRST:
hit profit target (+3R), hit stop (-1R), or ran out of time (25 bars)?"

This captures trade QUALITY, not just direction. A trade that immediately
hits the stop is worse than one that expires sideways.

Both the triple barrier label and the DSL trail-based label are computed
for every signal. The confidence layer uses trail-based (DSL). Calibration
analyses both.

Config (from Build Brief):
    BARRIER_UPPER_R = 3.0   # take profit at +3R
    BARRIER_LOWER_R = 1.0   # stop at -1R
    BARRIER_MAX_BARS = 25   # vertical barrier (max holding period)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


BARRIER_UPPER_R = 3.0
BARRIER_LOWER_R = 1.0
BARRIER_MAX_BARS = 25


@dataclass
class TripleBarrierResult:
    """Outcome of a single trade through the triple barrier."""
    ticker: str
    entry_date: str
    entry_price: float
    risk_per_share: float
    label: str       # "UPPER" | "LOWER" | "VERTICAL"
    exit_bar: int    # bar index where barrier was hit (0-based from entry)
    exit_price: float
    r_multiple: float
    peak_r: float    # max favourable excursion in R


def apply_triple_barrier(
    entry_price: float,
    risk_per_share: float,
    forward_highs: np.ndarray,
    forward_lows: np.ndarray,
    forward_closes: np.ndarray,
    upper_r: float = BARRIER_UPPER_R,
    lower_r: float = BARRIER_LOWER_R,
    max_bars: int = BARRIER_MAX_BARS,
) -> dict:
    """Apply triple barrier to a single trade.

    Args:
        entry_price: fill price at entry
        risk_per_share: distance from entry to stop (in price terms)
        forward_highs: high prices for bars after entry (bar 0 = day after entry)
        forward_lows: low prices for bars after entry
        forward_closes: close prices for bars after entry
        upper_r: profit target in R-multiples
        lower_r: stop loss in R-multiples
        max_bars: vertical barrier (max bars to hold)

    Returns:
        dict with label, exit_bar, exit_price, r_multiple, peak_r
    """
    if risk_per_share <= 0 or len(forward_closes) == 0:
        return {
            "label": "VERTICAL",
            "exit_bar": 0,
            "exit_price": entry_price,
            "r_multiple": 0.0,
            "peak_r": 0.0,
        }

    upper_price = entry_price + upper_r * risk_per_share
    lower_price = entry_price - lower_r * risk_per_share

    n_bars = min(len(forward_closes), max_bars)
    peak_r = 0.0

    for i in range(n_bars):
        bar_high = forward_highs[i] if i < len(forward_highs) else forward_closes[i]
        bar_low = forward_lows[i] if i < len(forward_lows) else forward_closes[i]
        bar_close = forward_closes[i]

        current_r = (bar_high - entry_price) / risk_per_share
        peak_r = max(peak_r, current_r)

        if bar_low <= lower_price:
            fill = lower_price
            r = (fill - entry_price) / risk_per_share
            return {
                "label": "LOWER",
                "exit_bar": i + 1,
                "exit_price": round(fill, 4),
                "r_multiple": round(r, 4),
                "peak_r": round(peak_r, 4),
            }

        if bar_high >= upper_price:
            fill = upper_price
            r = (fill - entry_price) / risk_per_share
            return {
                "label": "UPPER",
                "exit_bar": i + 1,
                "exit_price": round(fill, 4),
                "r_multiple": round(r, 4),
                "peak_r": round(peak_r, 4),
            }

    final_close = forward_closes[n_bars - 1] if n_bars > 0 else entry_price
    r = (final_close - entry_price) / risk_per_share
    return {
        "label": "VERTICAL",
        "exit_bar": n_bars,
        "exit_price": round(final_close, 4),
        "r_multiple": round(r, 4),
        "peak_r": round(peak_r, 4),
    }


def batch_triple_barrier(
    signals: pd.DataFrame,
    panel: pd.DataFrame,
    upper_r: float = BARRIER_UPPER_R,
    lower_r: float = BARRIER_LOWER_R,
    max_bars: int = BARRIER_MAX_BARS,
) -> pd.DataFrame:
    """Apply triple barrier to all signals in a DataFrame.

    Expects signals to have: ticker, date, entry_close, stop_price.
    Panel must have: ticker, date, open, high, low, close.

    Returns signals with added columns:
        tb_label, tb_exit_bar, tb_exit_price, tb_r_multiple, tb_peak_r
    """
    results = []

    for idx, sig in signals.iterrows():
        ticker = sig["ticker"]
        sig_date = pd.Timestamp(sig["date"])
        entry = float(sig.get("entry_close", sig.get("close", 0)))
        stop = float(sig.get("stop_price", 0))

        if entry <= 0 or stop <= 0 or stop >= entry:
            results.append({
                "tb_label": "INVALID",
                "tb_exit_bar": 0,
                "tb_exit_price": entry,
                "tb_r_multiple": 0.0,
                "tb_peak_r": 0.0,
            })
            continue

        risk = entry - stop

        ticker_bars = panel.loc[panel["ticker"] == ticker].sort_values("date")
        future = ticker_bars.loc[ticker_bars["date"] > sig_date].head(max_bars)

        if future.empty:
            results.append({
                "tb_label": "INSUFFICIENT",
                "tb_exit_bar": 0,
                "tb_exit_price": entry,
                "tb_r_multiple": 0.0,
                "tb_peak_r": 0.0,
            })
            continue

        tb = apply_triple_barrier(
            entry_price=entry,
            risk_per_share=risk,
            forward_highs=future["high"].values,
            forward_lows=future["low"].values,
            forward_closes=future["close"].values,
            upper_r=upper_r,
            lower_r=lower_r,
            max_bars=max_bars,
        )
        results.append({
            "tb_label": tb["label"],
            "tb_exit_bar": tb["exit_bar"],
            "tb_exit_price": tb["exit_price"],
            "tb_r_multiple": tb["r_multiple"],
            "tb_peak_r": tb["peak_r"],
        })

    result_df = pd.DataFrame(results, index=signals.index)
    return pd.concat([signals, result_df], axis=1)
