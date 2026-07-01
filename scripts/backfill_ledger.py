"""One-off historical signal ledger population.

Run on your LOCAL PC. Three steps:
  1. (Optional) Pull fresh daily bars from FMP for the full universe
  2. Rebuild scores_daily.parquet — runs all 7 engines + readiness/health
     on every ticker × every historical date
  3. Replay longlist/elder_list filter on each date, fill forward returns

The result: a populated aqe.db signal_snapshots + signal_outcomes table
covering ~365 days, with TP1/TP2/SL hit flags and T+5/10/20 returns.

Usage:
    Double-click  backfill_ledger.bat           (uses existing panel)
    Double-click  backfill_ledger_pull.bat       (refreshes bars from FMP first)

    Or from command line:
    python -m scripts.backfill_ledger           # use existing panel
    python -m scripts.backfill_ledger --pull    # pull fresh bars from FMP first

Runtime estimates (local PC):
    --pull:  30-60 min  (FMP pull ~15-20 min + scoring ~15-30 min + ledger ~2 min)
    no pull: 15-30 min  (scoring ~15-30 min + ledger ~2 min)

Requires:
    - .env with FMP_API_KEY (only if using --pull)
    - panel_daily.parquet in data/ (built by the daily pipeline)
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

    print("=" * 65)
    print("  AQE Signal Ledger — Historical Backfill")
    print("  Estimated runtime: %s" % ("30-60 min" if pull else "15-30 min"))
    print("=" * 65)

    # ── Step 1: Ensure panel_daily has bars ──────────────────────────────
    if pull:
        print("\n[1/4] Pulling daily bars from FMP (incremental)...")
        print("  This fetches OHLCV for the full universe — ~15-20 min")
        t_pull = time.time()
        from src.data.panel_builder import build_panel
        build_panel()
        print(f"  Pull complete in {time.time() - t_pull:.0f}s")
    else:
        print("\n[1/4] Using existing panel_daily.parquet")
        print("  (run backfill_ledger_pull.bat to refresh from FMP first)")

    if not PANEL_DAILY.exists():
        print(f"\n  ERROR: {PANEL_DAILY} not found.")
        print("  Either run the daily pipeline first, or re-run with --pull.")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    import pandas as pd
    panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker"])
    panel["date"] = pd.to_datetime(panel["date"])
    n_tickers = panel["ticker"].nunique()
    n_days = panel["date"].nunique()
    date_min = panel["date"].min().date()
    date_max = panel["date"].max().date()
    print(f"  Panel: {n_tickers} tickers × {n_days} trading days")
    print(f"  Range: {date_min} → {date_max}")

    # ── Step 2: Rebuild scores_daily.parquet ─────────────────────────────
    print("\n[2/4] Rebuilding scores_daily.parquet...")
    print(f"  Running 7 engines + readiness + health on {n_tickers} tickers")
    print("  Progress bar below — this is the slow step (~15-30 min)")
    t_scores = time.time()

    from src.scanner.score_runner import build_scores
    build_scores()

    elapsed_scores = time.time() - t_scores
    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker"])
    scores["date"] = pd.to_datetime(scores["date"])
    s_days = scores["date"].nunique()
    s_tickers = scores["ticker"].nunique()
    print(f"  Scores built: {s_tickers} tickers × {s_days} dates in {elapsed_scores:.0f}s")

    # ── Step 3: Populate the signal ledger ───────────────────────────────
    print("\n[3/4] Populating signal ledger...")
    print("  Replaying longlist (SC_MOM≥65, Elder≥7) + elder (Elder≥8)")
    print("  on each historical date, then filling forward returns")
    t_ledger = time.time()

    from src.data.signal_ledger import backfill_historical
    result = backfill_historical()

    if not result.get("ok"):
        print(f"\n  ERROR: {result.get('reason')}")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    elapsed_ledger = time.time() - t_ledger
    print(f"  Ledger populated in {elapsed_ledger:.0f}s")

    # ── Step 4: Summary ─────────────────────────────────────────────────
    stats = result["stats"]
    total_time = time.time() - t0

    print("\n" + "=" * 65)
    print("  BACKFILL COMPLETE")
    print("=" * 65)
    print(f"  Signals recorded:    {stats['snapshots']:,}")
    print(f"  Unique tickers:      {stats['unique_tickers']:,}")
    print(f"  Unique dates:        {stats['unique_dates']:,}")
    print(f"  Outcomes filled:     {stats['filled']:,}")
    print(f"  Outcomes pending:    {stats['pending']:,}"
          f"  (last ~20 trading days — forward bars don't exist yet)")
    if stats["date_range"]:
        print(f"  Date range:          {stats['date_range'][0]} → {stats['date_range'][1]}")
    print(f"  Total time:          {total_time / 60:.1f} min")
    print(f"  Database:            {DATA_DIR / 'aqe.db'}")
    print("=" * 65)

    # ── Hit rate preview ────────────────────────────────────────────────
    print("\n  === HIT RATE PREVIEW (all filled T+20 outcomes) ===\n")
    from src.data.signal_ledger import get_hit_rates
    rates = get_hit_rates()
    if rates["n"] > 0:
        print(f"  Signals with outcomes:  {rates['n']:,}")
        print(f"  Avg return T+5:        {rates['avg_ret_t5']:+.2f}%")
        print(f"  Avg return T+10:       {rates['avg_ret_t10']:+.2f}%")
        print(f"  Avg return T+20:       {rates['avg_ret_t20']:+.2f}%")
        if rates.get("tp1_hit_rate") is not None:
            print(f"  TP1 hit rate:          {rates['tp1_hit_rate']:.1f}%")
        if rates.get("tp2_hit_rate") is not None:
            print(f"  TP2 hit rate:          {rates['tp2_hit_rate']:.1f}%")
        if rates.get("sl_hit_rate") is not None:
            print(f"  SL hit rate:           {rates['sl_hit_rate']:.1f}%")
        print(f"  % positive at T+10:    {rates['pct_positive_t10']:.1f}%")
        print(f"  % positive at T+20:    {rates['pct_positive_t20']:.1f}%")

        # Longlist-only slice
        ll_rates = get_hit_rates(list_source="longlist")
        if ll_rates["n"] > 0:
            print(f"\n  --- Longlist only (SC_MOM≥65, Elder≥7) ---")
            print(f"  N = {ll_rates['n']:,}")
            print(f"  Avg T+20:  {ll_rates['avg_ret_t20']:+.2f}%  |  "
                  f"TP1: {ll_rates.get('tp1_hit_rate', 0):.1f}%  |  "
                  f"SL: {ll_rates.get('sl_hit_rate', 0):.1f}%")

        # High-conviction slice
        hc_rates = get_hit_rates(min_sc=75, list_source="longlist")
        if hc_rates["n"] > 0:
            print(f"\n  --- High-conviction longlist (SC_MOM≥75) ---")
            print(f"  N = {hc_rates['n']:,}")
            print(f"  Avg T+20:  {hc_rates['avg_ret_t20']:+.2f}%  |  "
                  f"TP1: {hc_rates.get('tp1_hit_rate', 0):.1f}%  |  "
                  f"SL: {hc_rates.get('sl_hit_rate', 0):.1f}%")
    else:
        print(f"  {rates.get('message', 'No data yet')}")

    print("\n" + "=" * 65)
    print("  Next: open Math Lab → Section 9 to slice by any factor combo")
    print("  Daily pipeline Step 8c will keep appending from here")
    print("=" * 65)

    input("\n  Press Enter to exit...")


if __name__ == "__main__":
    main()
