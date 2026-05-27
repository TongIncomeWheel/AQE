"""Null-hypothesis baselines for the analyzer.

For every recipe, the trader needs to compare the recipe's expectancy and win
rate against what they would have gotten from:

  - **random**: a random entry on the same universe over the same date range,
    matched on ticker and the month bucket of the signal date. This controls
    for ticker mix and regime composition. The matched-pair structure means
    the random cohort answers "would a coin flip on these tickers in these
    months have produced a similar result?"

  - **spy**: holding SPY for the same N days from each signal date. Controls
    for the market-beta floor. If a recipe shows +0.4R 21-day expectancy but
    SPY did the same, the recipe added zero edge above buy-and-hold.

Both baselines use the same outcome math as the real signals (2×ATR stop, 2:1
target, R-multiple, gap-stop handling) so they're directly comparable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.scanner.outcome_tracker import compute_outcomes


def random_baseline(
    signals: pd.DataFrame,
    panel: pd.DataFrame,
    scores: pd.DataFrame,
    *,
    seed: int = 1234,
    multiplier: int = 1,
) -> pd.DataFrame:
    """Match each signal with a randomly chosen (ticker, date) from the same panel.

    For each signal at (ticker_i, date_i), draws `multiplier` matched entries by:
      1. Filter the panel to the same year-month as date_i (regime match).
      2. Draw a random (ticker, date) uniformly from that pool.
      3. Use the score panel's atr14 on that random date as the entry ATR.

    Returns an `outcomes`-shaped DataFrame (same columns as compute_outcomes) so
    that the analyzer can compute the same metrics on it.
    """
    if signals.empty or panel.empty:
        return signals.iloc[0:0].copy()

    rng = np.random.default_rng(seed)
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p["ym"] = p["date"].dt.to_period("M")
    by_month = {ym: g.reset_index(drop=True) for ym, g in p.groupby("ym", sort=False)}

    sc = scores.copy()
    sc["date"] = pd.to_datetime(sc["date"]).dt.normalize()
    sc_lookup = sc.set_index(["ticker", "date"])

    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()
    sig["ym"] = sig["date"].dt.to_period("M")

    rows: list[dict] = []
    for _, s in sig.iterrows():
        pool = by_month.get(s["ym"])
        if pool is None or len(pool) == 0:
            continue
        for _ in range(multiplier):
            pick = pool.iloc[int(rng.integers(0, len(pool)))]
            key = (pick["ticker"], pick["date"])
            if key in sc_lookup.index:
                score_row = sc_lookup.loc[key]
                atr_at_entry = float(score_row["atr14"]) if "atr14" in score_row else np.nan
            else:
                atr_at_entry = np.nan
            rows.append({
                "date": pick["date"],
                "ticker": pick["ticker"],
                "atr14_at_entry": atr_at_entry,
                "_synthetic": True,
            })
    if not rows:
        return signals.iloc[0:0].copy()
    synthetic = pd.DataFrame(rows)
    return compute_outcomes(synthetic, panel)


def spy_baseline(
    signals: pd.DataFrame,
    spy_panel: pd.DataFrame,
    windows: tuple[int, ...] = (5, 10, 21),
) -> pd.DataFrame:
    """For each signal date, compute SPY's forward return over each window.

    Returns a DataFrame with one row per signal and columns:
      spy_fwd_ret_5d, spy_fwd_ret_10d, spy_fwd_ret_21d

    Does NOT apply the ATR-stop / 2:1 target framework — SPY itself doesn't get
    stopped out; this is a pure "what did the market do?" reference.
    """
    if signals.empty or spy_panel.empty:
        return signals.iloc[0:0].copy().assign(**{f"spy_fwd_ret_{w}d": np.nan for w in windows})

    spy = spy_panel.copy()
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    spy = spy.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    spy_dates = spy["date"].to_numpy()
    spy_close = spy["close"].astype(float).to_numpy()
    date_to_idx = {d: i for i, d in enumerate(spy_dates)}

    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()

    out = sig[["date", "ticker"]].copy()
    for w in windows:
        col = []
        for d in sig["date"].to_numpy():
            idx = date_to_idx.get(d)
            if idx is None or idx + w >= len(spy_close):
                col.append(np.nan)
            else:
                col.append((spy_close[idx + w] - spy_close[idx]) / spy_close[idx])
        out[f"spy_fwd_ret_{w}d"] = col
    return out
