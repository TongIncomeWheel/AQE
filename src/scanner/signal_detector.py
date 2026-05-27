"""Detect cross-up signals on SC_MOMENTUM with cooldown.

A signal fires on the bar where SC_MOMENTUM crosses up through `threshold`,
provided it has been below `threshold` for at least `cooldown_days` consecutive
bars beforehand. The cooldown prevents autocorrelated re-triggers when a stock
oscillates around the threshold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_crossups(
    scores: pd.DataFrame,
    *,
    score_column: str = "sc_momentum",
    threshold: float = 75.0,
    cooldown_days: int = 21,
) -> pd.DataFrame:
    """Return signal events as a DataFrame [date, ticker] sorted by (ticker, date).

    `scores` must have columns [date, ticker, score_column]. Ticker rows are processed
    independently.
    """
    if scores.empty:
        return scores.iloc[0:0].copy()

    out_frames: list[pd.DataFrame] = []
    for ticker, group in scores.sort_values(["ticker", "date"]).groupby("ticker", sort=False):
        s = group[score_column].astype(float).to_numpy()
        finite = np.isfinite(s)
        below = finite & (s < threshold)
        # days_below_prior[t] = run-length of consecutive "below" bars ending at t-1.
        # NaN bars BREAK the run (they don't count as below); cooldown must accumulate
        # only over real, scored bars.
        days_below_prior = np.zeros(len(s), dtype=int)
        run = 0
        for t in range(len(s)):
            days_below_prior[t] = run
            run = run + 1 if below[t] else 0
        crossed_up = np.zeros(len(s), dtype=bool)
        for t in range(1, len(s)):
            if (
                finite[t]
                and finite[t - 1]
                and s[t] >= threshold
                and s[t - 1] < threshold
                and days_below_prior[t] >= cooldown_days
            ):
                crossed_up[t] = True

        events = group.loc[crossed_up, ["date", "ticker"]].copy()
        if not events.empty:
            events[score_column] = group.loc[crossed_up, score_column].to_numpy()
            out_frames.append(events)

    if not out_frames:
        return scores.iloc[0:0].copy()
    return pd.concat(out_frames, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)
