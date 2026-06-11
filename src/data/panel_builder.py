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

from .fmp_client import FMPClient, FMPError, FMPQuotaError, iter_with_progress, resample_to_weekly
from .paths import (
    DATA_DIR,
    PANEL_DAILY,
    PANEL_WEEKLY,
    SPY_DAILY,
)
from .universe import BENCHMARK, PROJECT_ROOT, load_universe

# Engines need at most 252 trading days (Pipeline Rank 12-month return).
# Cloud uses 2yr to cover warmup; local keeps 6yr for recipe optimizer backtests.
LOCAL_HISTORY_YEARS = 6
CLOUD_HISTORY_YEARS = 2


def _default_history_years() -> int:
    """2yr on cloud (engines need ~1yr max), 6yr locally (for recipe optimizer)."""
    import os
    if os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"):
        return CLOUD_HISTORY_YEARS
    return LOCAL_HISTORY_YEARS


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


def build_panel(history_years: int | None = None) -> None:
    if history_years is None:
        history_years = _default_history_years()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today = _us_market_date()
    earliest = today - timedelta(days=int(history_years * 365.25))
    tickers = load_universe(include_benchmark=True)

    # Always pull GICS sector ETFs for SRM grading — they are excluded from
    # scoring but grade_all_sectors() and _build_srm_gics() need them in the
    # panel. Without this, every SRM grade defaults to WATCH (empty frame).
    from src.engines.srm import GICS_ETFS as _GICS_ETFS
    _seen = set(tickers)
    for _etf in _GICS_ETFS:
        if _etf not in _seen:
            tickers.append(_etf)
            _seen.add(_etf)

    # Always pull thematic-basket constituents for SECTOR grading context. Like
    # the GICS ETFs, they're graded (grade_thematic_baskets) but NOT screened —
    # basket membership is a context layer and must not add names to the scan
    # universe (Thematic Basket Map v2.0, PM directive). The scoring/screening
    # stages exclude any basket constituent that isn't in the scan universe.
    from src.engines.srm import BASKET_CONSTITUENTS as _BASKET_CONSTITUENTS
    for _c in _BASKET_CONSTITUENTS:
        if _c not in _seen:
            tickers.append(_c)
            _seen.add(_c)

    # Prioritize critical tickers so they get pulled before any quota cap:
    # 1) SPY (benchmark), 2) GICS sector ETFs (SRM), 3) everything else.
    priority = {BENCHMARK} | set(_GICS_ETFS)
    tickers = sorted(tickers, key=lambda t: (0 if t in priority else 1, t))

    print(f"[panel] pulling {len(tickers)} tickers, {history_years}yr lookback, "
          f"earliest={earliest}", flush=True)

    client = FMPClient()

    existing_daily = _load_existing(PANEL_DAILY)
    daily_rows: list[pd.DataFrame] = [] if existing_daily.empty else [existing_daily]
    pulled = 0
    skipped_current = 0
    quota_hit = False

    for ticker in iter_with_progress(tickers, label="daily"):
        from_dt = _next_pull_start(existing_daily, ticker, earliest)
        if from_dt > today:
            skipped_current += 1
            continue  # already current
        try:
            df = client.get_daily_bars(ticker, from_date=from_dt, to_date=today)
        except FMPQuotaError as exc:
            print(f"\n  *** FMP QUOTA REACHED at ticker {pulled + skipped_current + 1}/"
                  f"{len(tickers)}: {exc}", file=sys.stderr)
            print(f"  *** Saving {pulled} newly pulled tickers + cached data. "
                  f"Run pipeline again to pull remaining tickers.\n",
                  file=sys.stderr)
            quota_hit = True
            break
        except FMPError as exc:
            print(f"  !! {ticker}: {exc}", file=sys.stderr)
            continue
        if df.empty:
            print(f"  -- {ticker}: no bars returned", file=sys.stderr)
            continue
        df["ticker"] = ticker
        daily_rows.append(df[["date", "ticker", "open", "high", "low", "close", "volume"]])
        pulled += 1

    print(f"[panel] pulled={pulled}, cached/current={skipped_current}, "
          f"total_tickers={len(tickers)}, quota_hit={quota_hit}", flush=True)

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
    print(f"Wrote {PANEL_DAILY.name}: {len(daily):,} rows across "
          f"{daily['ticker'].nunique()} tickers")

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
