"""Compute forward returns + ATR-stop / R-target outcomes for each signal.

For a signal at (ticker, date) with `entry_close` and `atr14_at_entry`:

    stop_price    = entry_close - 2.0 * atr14_at_entry
    target_price  = entry_close + 2.0 * (2.0 * atr14_at_entry)   # 2:1 R:R from 2×ATR stop
    1R            = 2 × ATR14 × shares   (the dollars risked per share)

For each window N ∈ {5, 10, 21}:
    fwd_ret_<N>d              — close[entry+N] / entry_close − 1     (paper return, ignores stops)
    hit_target_<N>d            — bool, target touched first
    hit_stop_<N>d              — bool, stop touched first
    days_to_outcome_<N>d       — bar index of the first hit (1..N)
    r_realized_<N>d            — R-multiple LOCKED IN — once a stop hits the trade is over,
                                  regardless of what the underlying does later. This is the
                                  number a trader who actually used the stop would report.
    r_realized_optimistic_<N>d — same, but ties on a single bar (low ≤ stop AND high ≥ target)
                                  resolved as TARGET-first. Pair with r_realized to bound the
                                  ambiguity introduced by intraday path uncertainty.
    gap_stop_<N>d              — True if the stop-hit bar opened below stop (gap-down). When
                                  True, r_realized uses the actual open as the fill, which
                                  can be materially worse than -1R.

Exit logic precedence (per bar, oldest-to-newest):
1. If `open ≤ stop` on bar i: stop hits at the open. r_realized = (open − entry) / risk.
2. Else if both low ≤ stop AND high ≥ target on bar i: ambiguous (stop wins for the
   conservative number, target wins for the optimistic number).
3. Else: whichever side is touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.labels import batch_triple_barrier


WINDOWS = (5, 10, 21)
ATR_STOP_MULT = 2.0
R_MULTIPLIER = 2.0  # target is R_MULTIPLIER * (entry - stop), i.e., 2:1 R:R


def compute_outcomes(
    signals: pd.DataFrame,
    panel_daily: pd.DataFrame,
    *,
    atr_column: str = "atr14_at_entry",
) -> pd.DataFrame:
    """Augment `signals` with forward-return and outcome columns.

    Expected `signals` columns: date, ticker, sc_momentum (and any engine scores
    the caller wants to keep). The caller is responsible for joining the engine
    scores onto the signal rows before calling this — typically done by joining
    against the score panel.

    `panel_daily` must have [date, ticker, open, high, low, close, volume].
    """
    if signals.empty:
        return signals.copy()

    panel = panel_daily.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel_groups = {t: g.reset_index(drop=True) for t, g in panel.groupby("ticker", sort=False)}

    out_rows: list[dict] = []
    sig_by_ticker = signals.copy()
    sig_by_ticker["date"] = pd.to_datetime(sig_by_ticker["date"]).dt.normalize()
    sig_by_ticker = sig_by_ticker.sort_values(["ticker", "date"])

    for ticker, sig_group in sig_by_ticker.groupby("ticker", sort=False):
        bars = panel_groups.get(ticker)
        if bars is None or bars.empty:
            continue
        bars_dates = bars["date"].to_numpy()
        bars_open = bars["open"].astype(float).to_numpy()
        bars_high = bars["high"].astype(float).to_numpy()
        bars_low = bars["low"].astype(float).to_numpy()
        bars_close = bars["close"].astype(float).to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}

        for _, sig in sig_group.iterrows():
            entry_idx = date_to_idx.get(np.datetime64(sig["date"], "ns"))
            if entry_idx is None:
                # The score panel and price panel might disagree on the calendar; skip.
                continue
            entry_close = float(bars_close[entry_idx])
            atr_at_entry = float(sig.get(atr_column, np.nan))
            if not np.isfinite(atr_at_entry) or atr_at_entry <= 0:
                continue

            stop_price = entry_close - ATR_STOP_MULT * atr_at_entry
            target_price = entry_close + R_MULTIPLIER * ATR_STOP_MULT * atr_at_entry

            row = sig.to_dict()
            row["entry_close"] = entry_close
            row["stop_price"] = stop_price
            row["target_price"] = target_price

            risk = ATR_STOP_MULT * atr_at_entry  # 1R in dollars per share

            for w in WINDOWS:
                end_idx = entry_idx + w
                # Paper forward return at close of end_idx (ignores any stop / target hits).
                if end_idx < len(bars_close):
                    fwd_ret = (bars_close[end_idx] - entry_close) / entry_close
                else:
                    fwd_ret = np.nan
                row[f"fwd_ret_{w}d"] = fwd_ret

                # Walk-forward exit detection on bars (entry+1 .. entry+w).
                lo_idx = entry_idx + 1
                hi_idx = min(end_idx, len(bars_close) - 1)
                hit_stop = False
                hit_target = False
                gap_stop = False
                days_to_outcome = np.nan
                r_conservative = np.nan
                r_optimistic = np.nan
                if lo_idx <= hi_idx:
                    opens = bars_open[lo_idx: hi_idx + 1]
                    lows = bars_low[lo_idx: hi_idx + 1]
                    highs = bars_high[lo_idx: hi_idx + 1]

                    # Per-bar event detection:
                    #   gap_stop  : open ≤ stop                  → stop, filled at open (loss > 1R)
                    #   stop_touch: low ≤ stop  (no gap)         → stop, filled at stop_price (= −1R)
                    #   target    : high ≥ target                → target, filled at target (= +2R)
                    gap_stop_idx = np.where(opens <= stop_price)[0]
                    stop_idx = np.where(lows <= stop_price)[0]
                    target_idx = np.where(highs >= target_price)[0]

                    first_gap = int(gap_stop_idx[0]) if len(gap_stop_idx) else None
                    first_stop = int(stop_idx[0]) if len(stop_idx) else None
                    first_target = int(target_idx[0]) if len(target_idx) else None

                    # Resolve the conservative R (ties on a bar go to STOP).
                    cons_hits: list[tuple[int, str]] = []
                    if first_stop is not None:
                        cons_hits.append((first_stop, "stop"))
                    if first_target is not None:
                        cons_hits.append((first_target, "target"))
                    cons_hits.sort(key=lambda t: (t[0], 0 if t[1] == "stop" else 1))

                    # Optimistic R (ties on a bar go to TARGET).
                    opt_hits: list[tuple[int, str]] = []
                    if first_stop is not None:
                        opt_hits.append((first_stop, "stop"))
                    if first_target is not None:
                        opt_hits.append((first_target, "target"))
                    opt_hits.sort(key=lambda t: (t[0], 1 if t[1] == "stop" else 0))

                    if cons_hits:
                        first_idx, kind = cons_hits[0]
                        days_to_outcome = first_idx + 1
                        if kind == "stop":
                            hit_stop = True
                            # Gap-down? Fill at open of the stop-hit bar (worse than -1R).
                            if first_gap is not None and first_gap <= first_idx:
                                gap_stop = True
                                hit_bar = first_gap
                                fill_open = float(opens[hit_bar])
                                r_conservative = (fill_open - entry_close) / risk
                                days_to_outcome = hit_bar + 1
                            else:
                                r_conservative = -1.0
                        else:
                            hit_target = True
                            r_conservative = float(R_MULTIPLIER)

                    if opt_hits:
                        opt_first_idx, opt_kind = opt_hits[0]
                        if opt_kind == "stop":
                            if first_gap is not None and first_gap <= opt_first_idx:
                                fill_open = float(opens[first_gap])
                                r_optimistic = (fill_open - entry_close) / risk
                            else:
                                r_optimistic = -1.0
                        else:
                            r_optimistic = float(R_MULTIPLIER)

                    if not cons_hits:
                        # Neither side hit within the window — exit at the window's close.
                        if end_idx < len(bars_close):
                            terminal_r = (bars_close[end_idx] - entry_close) / risk
                            r_conservative = terminal_r
                            r_optimistic = terminal_r

                row[f"hit_target_{w}d"] = bool(hit_target)
                row[f"hit_stop_{w}d"] = bool(hit_stop)
                row[f"gap_stop_{w}d"] = bool(gap_stop)
                row[f"days_to_outcome_{w}d"] = days_to_outcome
                row[f"r_realized_{w}d"] = r_conservative
                row[f"r_realized_optimistic_{w}d"] = r_optimistic
            out_rows.append(row)

    if not out_rows:
        return signals.iloc[0:0].copy()
    result = pd.DataFrame(out_rows).reset_index(drop=True)

    # Triple barrier labeling (requires entry_close and stop_price columns)
    if "entry_close" in result.columns and "stop_price" in result.columns:
        result = batch_triple_barrier(result, panel)

    return result


def attach_signal_context(signals: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Left-join engine scores + atr14 from the score panel onto the signal rows."""
    if signals.empty:
        return signals.copy()
    keep_cols = [
        "date", "ticker", "close", "atr14",
        "flow_100", "energy_100", "structure_100", "mp_100", "elder_score",
        "bq_100", "k39_value",
        "mp_state", "sc_momentum", "sc_position",
    ]
    score_subset = scores[[c for c in keep_cols if c in scores.columns]].copy()
    score_subset["date"] = pd.to_datetime(score_subset["date"]).dt.normalize()

    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()
    merged = sig.merge(score_subset, on=["date", "ticker"], how="left", suffixes=("", "_score"))
    if "atr14_at_entry" not in merged.columns:
        merged["atr14_at_entry"] = merged["atr14"]
    return merged
