"""Rolling beta vs SPY — 30-day and 60-day market sensitivity per ticker.

    beta = Cov(stock daily returns, SPY daily returns) / Var(SPY daily returns)

over trailing windows of 30 and 60 trading days. Computed from the cached
price panel + SPY series — no extra FMP calls, the prices were already pulled.

30-day beta captures recent market sensitivity and is used for β-adjusted
DSL stops (DSL v2.1): high-β names (≥1.5) get a wider ATR clamp so normal
intraday volatility doesn't sweep the initial stop. 60-day beta provides a
smoother, less noisy view of market sensitivity for committee analysis.

One shared module so the Scanner tables, the ad-hoc scorer, and the Drive
export all compute beta the same way.
"""

from __future__ import annotations

import pandas as pd

from src.data.panel_builder import PANEL_DAILY, SPY_DAILY

BETA_WINDOWS = (30, 60)          # trailing trading days; 30d for DSL stops, 60d for committee view


def compute_betas(
    panel: pd.DataFrame,
    spy: pd.DataFrame,
    windows: tuple[int, ...] = BETA_WINDOWS,
) -> dict[str, dict[int, float]]:
    """Trailing beta vs SPY for every ticker in `panel`, for each window.

    panel -- daily panel with columns date, ticker, close.
    spy   -- SPY daily with columns date, close.
    Returns {ticker: {window: beta}}.
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    spy = spy.copy()
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()

    dates = sorted(panel["date"].unique())
    pivot = panel.pivot_table(index="date", columns="ticker", values="close")
    spy_sorted = spy.sort_values("date")

    out: dict[str, dict[int, float]] = {}
    for w in windows:
        if len(dates) < w + 1:
            continue
        cutoff = dates[-(w + 1)]                       # w+1 dates -> w returns
        stock_ret = pivot[pivot.index >= cutoff].pct_change().iloc[1:]
        spy_ret = (
            spy_sorted[spy_sorted["date"] >= cutoff]
            .set_index("date")["close"].pct_change().dropna()
        )
        common = stock_ret.index.intersection(spy_ret.index)
        if len(common) < 2:
            continue
        stock_ret = stock_ret.loc[common]
        spy_ret = spy_ret.loc[common]
        var = spy_ret.var()
        if var == 0 or pd.isna(var):
            continue
        betas = (stock_ret.apply(lambda col: col.cov(spy_ret)) / var).dropna().round(2)
        for ticker, b in betas.items():
            out.setdefault(ticker, {})[w] = float(b)
    return out


def load_betas(windows: tuple[int, ...] = BETA_WINDOWS) -> dict[str, dict[int, float]]:
    """Compute trailing betas from the cached panel + SPY parquet files."""
    if not PANEL_DAILY.exists() or not SPY_DAILY.exists():
        return {}
    panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "close"])
    spy = pd.read_parquet(SPY_DAILY, columns=["date", "close"])
    return compute_betas(panel, spy, windows)


def betas_for_ticker(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    windows: tuple[int, ...] = BETA_WINDOWS,
) -> dict[int, float]:
    """Trailing beta vs SPY for a single ticker from its own daily frame.

    For the ad-hoc scorer, which holds one freshly-fetched ticker rather than
    the cached panel. stock_df / spy_df -- daily frames with date + close.
    Returns {window: beta}.
    """
    s = stock_df[["date", "close"]].copy()
    s["date"] = pd.to_datetime(s["date"]).dt.normalize()
    b = spy_df[["date", "close"]].copy()
    b["date"] = pd.to_datetime(b["date"]).dt.normalize()

    s_ret = s.set_index("date")["close"].pct_change().dropna()
    b_ret = b.set_index("date")["close"].pct_change().dropna()
    common = s_ret.index.intersection(b_ret.index)
    s_ret = s_ret.loc[common]
    b_ret = b_ret.loc[common]

    out: dict[int, float] = {}
    for w in windows:
        if len(b_ret) < w:
            continue
        sw = s_ret.iloc[-w:]
        bw = b_ret.iloc[-w:]
        var = bw.var()
        if var == 0 or pd.isna(var):
            continue
        out[w] = round(float(sw.cov(bw) / var), 2)
    return out
