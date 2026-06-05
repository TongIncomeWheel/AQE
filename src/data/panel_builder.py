"""Build / refresh the cached daily + weekly price panels.

Reads `data/universe.txt`, pulls 5+ years of daily bars from FMP, writes long-format
parquet files under `data/`. SPY is cached separately for fast joins.

Idempotent: on rerun, only pulls bars newer than what is already cached.

Run from a fresh shell:
    python -m src.data.panel_builder
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .fmp_client import FMPClient, FMPError, iter_with_progress, resample_to_weekly
from .paths import (
    DATA_DIR,
    PANEL_DAILY,
    PANEL_WEEKLY,
    SPY_DAILY,
)
from .universe import BENCHMARK, PROJECT_ROOT, load_universe

DEFAULT_HISTORY_YEARS = 6  # pulls 6yr so we have 5yr of warm scores after engine warmup


def _us_market_date() -> date:
    """Latest US trading date — avoids requesting bars for a session that hasn't happened.

    Uses America/New_York wall clock: before 4:30 PM ET (market close + 30 min
    settlement buffer), today's bars don't exist yet, so we use yesterday's date.
    This matters when the caller is in SGT (UTC+8) where date.today() can be
    one calendar day ahead of the US date.
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.hour < 16 or (now_et.hour == 16 and now_et.minute < 30):
        return (now_et - timedelta(days=1)).date()
    return now_et.date()


def build_panel(history_years: int = DEFAULT_HISTORY_YEARS) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today = _us_market_date()
    earliest = today - timedelta(days=int(history_years * 365.25))
    tickers = load_universe(include_benchmark=True)

    # Always pull GICS sector ETFs for SRM grading — they are excluded from
    # scoring but grade_all_sectors() and _build_srm_table() need them in the
    # panel. Without this, every SRM grade defaults to WATCH (empty frame).
    from src.engines.srm import GICS_ETFS as _GICS_ETFS
    _seen = set(tickers)
    for _etf in _GICS_ETFS:
        if _etf not in _seen:
            tickers.append(_etf)
            _seen.add(_etf)

    client = FMPClient()

    existing_daily = _load_existing(PANEL_DAILY)
    daily_rows: list[pd.DataFrame] = [] if existing_daily.empty else [existing_daily]

    for ticker in iter_with_progress(tickers, label="daily"):
        from_dt = _next_pull_start(existing_daily, ticker, earliest)
        if from_dt > today:
            continue  # already current
        try:
            df = client.get_daily_bars(ticker, from_date=from_dt, to_date=today)
        except FMPError as exc:
            print(f"  !! {ticker}: {exc}", file=sys.stderr)
            continue
        if df.empty:
            print(f"  -- {ticker}: no bars returned", file=sys.stderr)
            continue
        df["ticker"] = ticker
        daily_rows.append(df[["date", "ticker", "open", "high", "low", "close", "volume"]])

    if not daily_rows:
        print("No data pulled. Aborting.", file=sys.stderr)
        return

    daily = (
        pd.concat(daily_rows, ignore_index=True)
        .drop_duplicates(subset=["date", "ticker"], keep="last")
        .sort_values(["ticker", "date"], kind="stable")
        .reset_index(drop=True)
    )
    daily.to_parquet(PANEL_DAILY, index=False)
    print(f"Wrote {PANEL_DAILY.name}: {len(daily):,} rows across {daily['ticker'].nunique()} tickers")

    # Weekly resample per ticker.
    weekly_rows: list[pd.DataFrame] = []
    for ticker, group in daily.groupby("ticker", sort=False):
        weekly = resample_to_weekly(group[["date", "open", "high", "low", "close", "volume"]])
        if weekly.empty:
            continue
        weekly["ticker"] = ticker
        weekly_rows.append(weekly[["date", "ticker", "open", "high", "low", "close", "volume"]])
    weekly_panel = pd.concat(weekly_rows, ignore_index=True)
    weekly_panel.to_parquet(PANEL_WEEKLY, index=False)
    print(f"Wrote {PANEL_WEEKLY.name}: {len(weekly_panel):,} rows")

    # SPY snapshot for fast benchmark joins (deduped — corrupted parquets can dup).
    spy = (
        daily.loc[daily["ticker"] == BENCHMARK, ["date", "open", "high", "low", "close", "volume"]]
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    if not spy.empty:
        spy.to_parquet(SPY_DAILY, index=False)
        print(f"Wrote {SPY_DAILY.name}: {len(spy):,} rows")
    else:
        print(f"Warning: {BENCHMARK} not present in panel. spy_daily.parquet not refreshed.", file=sys.stderr)


def _load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # corrupt cache → start fresh
        print(f"  !! could not read {path.name}: {exc}; rebuilding from scratch", file=sys.stderr)
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def _next_pull_start(existing: pd.DataFrame, ticker: str, earliest: date) -> date:
    if existing.empty:
        return earliest
    sub = existing.loc[existing["ticker"] == ticker, "date"]
    if sub.empty:
        return earliest
    last = sub.max().date()
    return last + timedelta(days=1)


if __name__ == "__main__":
    build_panel()
