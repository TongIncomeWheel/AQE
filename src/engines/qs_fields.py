"""QS field engine — the five inputs QS needs that AQE does not already compute.

QS (Quiet Strength) reads AQE's existing subcomponents for 33 of its 36 fields.
This module supplies the rest, per the QS handover §2.2:

| field           | formula                                                    | window |
|-----------------|------------------------------------------------------------|--------|
| `ret20`         | close / close[20] - 1, x100                                 |  21    |
| `rs_consist`    | fraction of the last 126 sessions the ticker's daily return |  126   |
|                 | beat the EQUAL-WEIGHT ELIGIBLE-UNIVERSE return (not SPY)    |        |
| `rank_in_sector`| pct-rank of ret20 within (date, sector) — awareness only     | daily  |
| `trend_200`     | ew_index / SMA200(ew_index) - 1                             |  200   |
| `vol_60`        | annualised stdev of daily ew_index returns                  |  60    |

`qs_persist` is NOT here — it is a memory field read back from stored
`recipe_hits`, so it lives with the QS storage layer.

THE BENCHMARK IS THE EQUAL-WEIGHT UNIVERSE, NOT SPY. This is deliberate and
load-bearing: `rs_consist` asks "does this name beat the average eligible
stock", which is a breadth question. SPY is cap-weighted, so in a
mega-cap-led tape SPY and the average stock diverge sharply and an
SPY-benchmarked answer measures something else entirely. AQE already carries
SPY-relative reads (`rs_vs_spy`, `excess_return`); this is not one of them.

CAUSALITY. The regime terciles are expanding-window and shifted one day: the
boundaries that classify date `t` are computed from history up to `t-1` only.
A tercile fitted on the full series would leak the future into every historical
row and quietly inflate any backtest run against it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Windows — fixed by the QS handover §2.2. Not tunable at runtime: the frozen
# calibration was measured against exactly these.
RET_WINDOW = 20            # ret20 lookback in sessions
RS_CONSIST_WINDOW = 126    # ~6 months of sessions
TREND_SMA_WINDOW = 200     # trend_200
VOL_WINDOW = 60            # vol_60
TRADING_DAYS = 252         # annualisation factor

# A regime cell is only assigned once we have enough *history of trend_200 /
# vol_60 values* to fit a meaningful tercile. Below this the day is
# "unclassified" and QS declines to score it rather than guessing.
MIN_REGIME_HISTORY = 60


def _close_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    """date x ticker matrix of closes, sorted, deduped."""
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p = p.drop_duplicates(subset=["date", "ticker"], keep="last")
    return p.pivot(index="date", columns="ticker", values="close").sort_index()


def build_ew_index(panel: pd.DataFrame,
                   tickers: list[str] | None = None) -> pd.DataFrame:
    """Equal-weight index of the eligible universe.

    Returns a frame indexed by date with `ew_ret` (that day's equal-weight mean
    daily return) and `ew_index` (cumulative, base 100).

    The daily return is the *cross-sectional mean* of every eligible ticker's
    return that day — an equal-weight portfolio rebalanced daily, which is what
    "the average eligible stock" means. Tickers with no bar that day are simply
    absent from the mean rather than treated as zero-return; a NaN is missing
    data, not a flat day, and averaging it in as 0 would damp the index.
    """
    closes = _close_matrix(panel)
    if tickers:
        keep = [t for t in tickers if t in closes.columns]
        if keep:
            closes = closes[keep]
    rets = closes.pct_change()
    ew_ret = rets.mean(axis=1, skipna=True)
    ew_ret = ew_ret.replace([np.inf, -np.inf], np.nan)
    out = pd.DataFrame({"ew_ret": ew_ret})
    out["ew_index"] = 100.0 * (1.0 + out["ew_ret"].fillna(0.0)).cumprod()
    # The first row has no prior close, so its return is undefined, not zero.
    out.loc[out.index[:1], "ew_ret"] = np.nan
    return out


def compute_regime_series(ew: pd.DataFrame) -> pd.DataFrame:
    """trend_200 and vol_60 from the equal-weight index.

    trend_200 = ew_index / SMA200(ew_index) - 1   (how far above/below trend)
    vol_60    = stdev(daily ew returns, 60) * sqrt(252)   (annualised)
    """
    idx = ew["ew_index"]
    sma = idx.rolling(TREND_SMA_WINDOW, min_periods=TREND_SMA_WINDOW).mean()
    trend_200 = (idx / sma) - 1.0
    vol_60 = (ew["ew_ret"].rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std(ddof=1)
              * np.sqrt(TRADING_DAYS))
    return pd.DataFrame({"trend_200": trend_200, "vol_60": vol_60})


def _causal_tercile(s: pd.Series, min_history: int = MIN_REGIME_HISTORY
                    ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bucket each value into 1/2/3 against terciles fitted on PRIOR days only.

    `.expanding().quantile()` includes the current row, so the result is
    shifted one day — the boundaries classifying date t come from t-1 back.
    Returns (tercile, lower_boundary, upper_boundary); the boundaries are
    returned so the export can show WHY a day landed where it did rather than
    asserting a cell code the reader has to take on trust.
    NaN until `min_history` prior observations exist.
    """
    lo = s.expanding(min_periods=min_history).quantile(1 / 3).shift(1)
    hi = s.expanding(min_periods=min_history).quantile(2 / 3).shift(1)
    out = pd.Series(np.nan, index=s.index, dtype="float64")
    ok = s.notna() & lo.notna() & hi.notna()
    out[ok & (s <= lo)] = 1.0
    out[ok & (s > lo) & (s <= hi)] = 2.0
    out[ok & (s > hi)] = 3.0
    return out, lo, hi


def assign_regime_cells(regime: pd.DataFrame) -> pd.DataFrame:
    """Add causal terciles, their boundaries, and the T{1-3}V{1-3} cell code.

    Days without enough history to fit a tercile are labelled `unclassified`,
    matching the recipe book's own regime key for that state.
    """
    out = regime.copy()
    out["t_tercile"], out["t_lo"], out["t_hi"] = _causal_tercile(out["trend_200"])
    out["v_tercile"], out["v_lo"], out["v_hi"] = _causal_tercile(out["vol_60"])
    cell = []
    for t, v in zip(out["t_tercile"], out["v_tercile"]):
        if pd.isna(t) or pd.isna(v):
            cell.append("unclassified")
        else:
            cell.append(f"T{int(t)}V{int(v)}")
    out["regime_cell"] = cell
    return out


def compute_ret20(panel: pd.DataFrame) -> pd.DataFrame:
    """ret20 = close / close[20] - 1, x100. Long frame (date, ticker, ret20)."""
    closes = _close_matrix(panel)
    ret20 = (closes / closes.shift(RET_WINDOW) - 1.0) * 100.0
    ret20 = ret20.replace([np.inf, -np.inf], np.nan)
    out = ret20.stack().dropna().reset_index()
    out.columns = ["date", "ticker", "ret20"]
    return out


def compute_rs_consist(panel: pd.DataFrame, ew: pd.DataFrame,
                       tickers: list[str] | None = None) -> pd.DataFrame:
    """Fraction of the last 126 sessions the ticker beat the EW universe.

    MATCHES THE REFERENCE IMPLEMENTATION EXACTLY (`daily_scan.py:80-91`):

        beat = (rets > idx_ret[:, None]).astype(float)
        rs   = DataFrame(beat).rolling(126, min_periods=126).mean()

    Two consequences of that formulation are deliberate, surprising, and load
    bearing — the frozen calibration was measured against them, so they are
    reproduced rather than "improved":

    1. A day the ticker did NOT trade counts as a LOSS, not as an excluded
       observation. `NaN > x` is False, which `.astype(float)` turns into 0.0.
       The denominator is therefore always a flat 126, never a count of days
       actually compared. A halted name is penalised for the gap.
    2. The window is strict (`min_periods=126`): no value at all is emitted
       until a full 126 sessions exist, rather than a partial-sample estimate.

    Changing either would shift every name's LEADERSHIP lens score, move names
    across `lens_total` band boundaries, and silently re-price the whole book.
    """
    closes = _close_matrix(panel)
    if tickers:
        keep = [t for t in tickers if t in closes.columns]
        if keep:
            closes = closes[keep]
    rets = closes.pct_change()
    # nan_to_num on the index return mirrors the reference: a day where the
    # cross-sectional mean is undefined is treated as a 0% index day.
    ew_ret = ew["ew_ret"].reindex(rets.index).fillna(0.0)

    beat = rets.gt(ew_ret, axis=0).astype(float)   # NaN -> False -> 0.0
    frac = beat.rolling(RS_CONSIST_WINDOW,
                        min_periods=RS_CONSIST_WINDOW).mean()

    out = frac.stack().dropna().reset_index()
    out.columns = ["date", "ticker", "rs_consist"]
    return out


def compute_rank_in_sector(ret20: pd.DataFrame,
                           sector_map: dict[str, str]) -> pd.DataFrame:
    """Pct-rank of ret20 within (date, sector). AWARENESS ONLY.

    Never touches recipe_hits, conviction, ranking or the calibrated
    probability (recipe book `awareness_notes.decision`, PM 2026-08-04).

    A sector with a single name that day yields rank 1.0 by construction,
    which is meaningless rather than strong; those are dropped so a thin
    sector cannot manufacture a "sector leader" note out of nothing.
    """
    df = ret20.copy()
    df["sector"] = df["ticker"].map(sector_map)
    df = df[df["sector"].notna() & df["ret20"].notna()]
    if df.empty:
        return pd.DataFrame(columns=["date", "ticker", "rank_in_sector"])
    grp = df.groupby(["date", "sector"])["ret20"]
    df["rank_in_sector"] = grp.rank(pct=True)
    df = df[grp.transform("size") >= 2]
    return df[["date", "ticker", "rank_in_sector"]]


def compute_all(panel: pd.DataFrame, tickers: list[str] | None = None,
                sector_map: dict[str, str] | None = None
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Everything in one pass.

    Returns (per_ticker, regime):
      per_ticker — long frame: date, ticker, ret20, rs_consist, rank_in_sector
      regime     — indexed by date: trend_200, vol_60, terciles, regime_cell
    """
    ew = build_ew_index(panel, tickers)
    regime = assign_regime_cells(compute_regime_series(ew))

    ret20 = compute_ret20(panel)
    rs = compute_rs_consist(panel, ew, tickers)
    per = ret20.merge(rs, on=["date", "ticker"], how="outer")
    if sector_map:
        ris = compute_rank_in_sector(ret20, sector_map)
        per = per.merge(ris, on=["date", "ticker"], how="left")
    else:
        per["rank_in_sector"] = np.nan
    return per, regime
