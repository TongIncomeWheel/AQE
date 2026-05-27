"""K39 weekly stochastic gate — used by SC_POSITION composite.

Per Design Committee Spec:
    k39 = stochastic(weekly_close, weekly_high, weekly_low, 39)
    obv_weekly = obv(weekly)
    obv_sma30 = sma(obv_weekly, 30)
    k39_gate = (k39 > 50) AND (obv_weekly > obv_sma30)

The gate is computed on weekly bars and then mapped back to daily dates
via asof_weekly_value (no look-ahead).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute_k39_gate(
    weekly: pd.DataFrame,
    daily_dates: pd.Series,
) -> pd.Series:
    """Return a boolean Series aligned to daily_dates: True where K39 gate passes."""
    if weekly is None or weekly.empty or len(weekly) < 39:
        return pd.Series(False, index=daily_dates.index)

    wk = weekly.sort_values("date").reset_index(drop=True)
    wk_close = wk["close"].astype(float)
    wk_high = wk["high"].astype(float)
    wk_low = wk["low"].astype(float)
    wk_volume = wk["volume"].astype(float)

    k39 = U.stochastic_k(wk_close, wk_high, wk_low, 39)
    wk_obv = U.obv(wk_close, wk_volume)
    obv_sma30 = U.sma(wk_obv, 30)

    gate_weekly = (k39 > 50) & (wk_obv > obv_sma30)
    gate_weekly = gate_weekly.fillna(False)

    wk_with_gate = pd.DataFrame({
        "date": wk["date"],
        "k39_gate": gate_weekly.astype(float),
        "k39_value": k39,
    })

    gate_daily = U.asof_weekly_value(daily_dates, wk_with_gate, "k39_gate")
    k39_daily = U.asof_weekly_value(daily_dates, wk_with_gate, "k39_value")

    return pd.Series((gate_daily == 1.0).fillna(False).to_numpy(), index=daily_dates.index), k39_daily
