"""One-off historical signal ledger population.

Run locally or on AQE cloud. Rebuilds scores_daily (so readiness/health
columns are present for all dates), then replays the longlist/elder_list
filter on ~365 days of history and fills forward returns from panel_daily.

Usage:
    python -m scripts.backfill_ledger          # use existing panel
    python -m scripts.backfill_ledger --pull   # pull fresh bars from FMP first

The --pull flag runs build_panel() first (incremental FMP pull to fill any
gaps in panel_daily.parquet). Without it, uses whatever panel already exists.

Runtime: ~5-10 minutes depending on universe size (scoring is the bulk).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.paths import DATA_DIR, PANEL_DAILY, SCORES_DAILY


def main():
    pull = "--pull" in sys.argv
    t0 = time.time()

    print("=" * 60)
    print("  AQE Signal Ledger — Historical Backfill")
    print("=" * 60)

    # Step 1: Ensure panel_daily exists (optionally pull fresh bars)
    if pull:
        print("\n[1/4] Pulling fresh bars from FMP...")
        from src.data.panel_builder import build_panel
        build_panel()
    else:
        print("\n[1/4] Using existing panel (pass --pull to refresh from FMP)")

    if not PANEL_DAILY.exists():
        print(f"  ERROR: {PANEL_DAILY} not found. Run with --pull or run the pipeline first.")
        sys.exit(1)

    import pandas as pd
    panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker"])
    panel["date"] = pd.to_datetime(panel["date"])
    n_tickers = panel["ticker"].nunique()
    n_days = panel["date"].nunique()
    date_range = f"{panel['date'].min().date()} → {panel['date'].max().date()}"
    print(f"  Panel: {n_tickers} tickers, {n_days} days ({date_range})")

    # Step 2: Rebuild scores_daily.parquet (full universe, all dates)
    # This ensures readiness/health columns are computed for all historical dates.
    print("\n[2/4] Rebuilding scores_daily.parquet (all engines, all dates)...")
    print("  This is the slow step — scoring ~600 tickers × all bars...")
    t_scores = time.time()

    from src.scanner.score_runner import build_scores
    build_scores()

    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker"])
    scores["date"] = pd.to_datetime(scores["date"])
    s_days = scores["date"].nunique()
    s_tickers = scores["ticker"].nunique()
    s_range = f"{scores['date'].min().date()} → {scores['date'].max().date()}"
    print(f"  Scores: {s_tickers} tickers, {s_days} days ({s_range})")
    print(f"  Took {time.time() - t_scores:.0f}s")

    # Step 3: Backfill signal ledger from scores_daily
    print("\n[3/4] Populating signal ledger (longlist + elder_list filter)...")
    from src.data.signal_ledger import backfill_historical
    result = backfill_historical()

    if not result.get("ok"):
        print(f"  ERROR: {result.get('reason')}")
        sys.exit(1)

    # Step 4: Summary
    print("\n[4/4] Done.")
    stats = result["stats"]
    print("=" * 60)
    print(f"  Signals recorded:    {stats['snapshots']:,}")
    print(f"  Unique tickers:      {stats['unique_tickers']:,}")
    print(f"  Unique dates:        {stats['unique_dates']:,}")
    print(f"  Outcomes filled:     {stats['filled']:,}")
    print(f"  Outcomes pending:    {stats['pending']:,}")
    if stats["date_range"]:
        print(f"  Date range:          {stats['date_range'][0]} → {stats['date_range'][1]}")
    print(f"  Total time:          {time.time() - t0:.0f}s")
    print(f"  Database:            {DATA_DIR / 'aqe.db'}")
    print("=" * 60)

    # Quick hit rate preview
    print("\n  Quick hit rate preview (all signals, T+20 filled):")
    from src.data.signal_ledger import get_hit_rates
    rates = get_hit_rates()
    if rates["n"] > 0:
        print(f"  N = {rates['n']:,}")
        print(f"  Avg T+5:  {rates['avg_ret_t5']:+.2f}%")
        print(f"  Avg T+10: {rates['avg_ret_t10']:+.2f}%")
        print(f"  Avg T+20: {rates['avg_ret_t20']:+.2f}%")
        if rates.get("tp1_hit_rate") is not None:
            print(f"  TP1 hit:  {rates['tp1_hit_rate']:.1f}%")
        if rates.get("tp2_hit_rate") is not None:
            print(f"  TP2 hit:  {rates['tp2_hit_rate']:.1f}%")
        if rates.get("sl_hit_rate") is not None:
            print(f"  SL hit:   {rates['sl_hit_rate']:.1f}%")
        print(f"  % positive T+20: {rates['pct_positive_t20']:.1f}%")
    else:
        print(f"  {rates.get('message', 'No data yet')}")


if __name__ == "__main__":
    main()
