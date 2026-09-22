"""VALEN extension — piece 01, "how stretched the market is".

VIX/VIX3M and the SPY/QQQ ATR-multiple-from-50-day are computed here in
full. The four whole-market breadth instruments (T2108, mover counts,
Net High/Low) are NOT computed here — see
docs/AQE_VALEN_DASHBOARD_PROPOSAL.md §2.2: they require a market-wide
population AQE's curated ~819-ticker panel cannot honestly supply (one of
VALEN's own stance-flip rules needs 350+ monthly movers, arithmetically
unreachable on this panel). `breadth_pct_above_20d()` is written generically
against WHATEVER panel is handed to it, specifically so wiring in the wider
`ma_scanner` population later (Phase 2) is a one-line change, not a rewrite —
but until that population is wired in, callers MUST pass
`population=spec.POPULATION_CURATED` and this module refuses to label a
curated-population number `t2108`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.utils import atr as _atr

from . import spec as S


def index_atr_multiple(daily_bars: pd.DataFrame) -> dict:
    """SPY/QQQ "how stretched from the 50-day, in that symbol's own ATRs".

    `daily_bars` needs columns [date, open, high, low, close], oldest first,
    for ONE symbol. Wilder ATR(14) — src/engines/utils.py:atr, the same
    formula every other AQE engine uses (house formula, not the VIV Pine
    script — see spec.py module docstring on FORMULA_BASIS_*).
    """
    out = {"atr_multiple_from_50d": None, "stretched": None,
           "formula_basis": S.FORMULA_BASIS_AQE_HOUSE}
    if daily_bars is None or len(daily_bars) < 51:
        return out
    df = daily_bars.sort_values("date")
    close = pd.to_numeric(df["close"], errors="coerce")
    atr14 = _atr(pd.to_numeric(df["high"], errors="coerce"),
                 pd.to_numeric(df["low"], errors="coerce"), close, 14)
    sma50 = close.rolling(50, min_periods=50).mean()
    last_close, last_atr, last_sma = close.iloc[-1], atr14.iloc[-1], sma50.iloc[-1]
    if not (np.isfinite(last_close) and np.isfinite(last_atr)
            and np.isfinite(last_sma) and last_atr > 0):
        return out
    mult = round(float((last_close - last_sma) / last_atr), 2)
    out["atr_multiple_from_50d"] = mult
    out["stretched"] = bool(mult >= S.INDEX_ATR_MULT_STRETCHED)
    return out


def vix_vix3m(vix_frame: pd.DataFrame | None, vix3m_frame: pd.DataFrame | None,
              *, live_vix: float | None = None,
              live_vix_ts: str | None = None) -> dict:
    """VIX/VIX3M ratio, reusing crown's own term_structure() where possible.

    `vix_frame`/`vix3m_frame` are Cboe-CSV shaped {date, close} DataFrames
    from `src.macro.crown.cboe.series_frames()` — the nightly cache. VIX3M
    is NOT available live (FMP Starter plan does not carry it; Cboe's file
    is end-of-day only), so a live refresh can only ever move the VIX leg —
    `live_vix` overrides the cached VIX close for the ratio's numerator, and
    `basis` says so explicitly so a reader never mistakes a mixed-freshness
    ratio for a fully live one.
    """
    from src.macro.crown import vol as _vol
    ts = _vol.term_structure(vix_frame, vix3m_frame, None)
    basis = "eod"
    if live_vix is not None:
        vix3m_last = ts.get("vix3m")
        if vix3m_last:
            ts = dict(ts)
            ts["vix"] = round(float(live_vix), 2)
            ts["ratio_30d_3m"] = round(float(live_vix) / vix3m_last, 4)
            ts["shape"] = "BACKWARDATION" if ts["ratio_30d_3m"] > 1.0 else "CONTANGO"
            basis = "vix_live_vix3m_eod"
    return {
        "vix": ts.get("vix"), "vix3m": ts.get("vix3m"),
        "ratio": ts.get("ratio_30d_3m"),
        "uncertainty": (ts.get("ratio_30d_3m") is not None
                         and ts["ratio_30d_3m"] > S.VIX_VIX3M_UNCERTAINTY_ABOVE),
        "calm": (ts.get("ratio_30d_3m") is not None
                 and ts["ratio_30d_3m"] < S.VIX_VIX3M_CALM_BELOW),
        "basis": basis, "live_vix_ts": live_vix_ts if basis != "eod" else None,
    }


def breadth_pct_above_20d(panel: pd.DataFrame, population: str) -> dict:
    """% of `panel`'s tickers trading above their own 20-day SMA, today.

    `population` MUST be one of spec.POPULATION_*. When it is
    POPULATION_CURATED, the caller is expected to treat this as context, NOT
    as VALEN's T2108 (which is whole-market, 40-day, absolute thresholds
    20/80) — see this module's docstring. `panel` needs [date, ticker, close].
    """
    if population not in (S.POPULATION_CURATED, S.POPULATION_US_WIDE):
        raise ValueError(f"unknown population: {population!r}")
    if panel is None or panel.empty:
        return {"status": "UNAVAILABLE", "reason": "no panel", "population": population}
    df = panel.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    above, total = 0, 0
    for _tk, g in df.groupby("ticker", sort=False):
        c = pd.to_numeric(g["close"], errors="coerce").dropna()
        if len(c) < 20:
            continue
        sma20 = c.tail(20).mean()
        if not np.isfinite(sma20) or sma20 <= 0:
            continue
        total += 1
        if float(c.iloc[-1]) > sma20:
            above += 1
    if total == 0:
        return {"status": "UNAVAILABLE", "reason": "no ticker had 20 bars",
                "population": population}
    pct = round(100.0 * above / total, 1)
    return {"status": "OK", "pct_above_20d": pct, "n": total, "n_above": above,
            "population": population,
            "washed_out": pct <= S.EXT_PCT_ABOVE_20D_LOW_DEFAULT,
            "overheated": pct >= S.EXT_PCT_ABOVE_20D_HIGH_DEFAULT}


def whole_market_breadth_unavailable(reason: str) -> dict:
    """T2108 / mover counts / Net-High-Net-Low — the honest absence.

    See module docstring. Every VALEN whole-market instrument this module
    does not yet compute returns this shape rather than a curated-panel
    number wearing the real name.
    """
    return {"status": "UNAVAILABLE", "reason": reason,
            "population_needed": S.POPULATION_US_WIDE}
