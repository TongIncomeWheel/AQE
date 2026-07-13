"""MA Proximity Scanner — find stocks near key moving averages.

Scans ALL US-listed stocks above $1B market cap for proximity to their
20/50/100/200-day simple moving averages. Tracks how many consecutive
days each stock has been within ±10% of each MA.

Use case: finding quality companies that have pulled back to key MAs
for swing entries or calendar trades.

Runs DAILY alongside the daily pipeline (in the in-app scheduler, right after
the trading feed is published — decoupled from the pipeline's critical path so a
slow FMP pull can't fail the feed). Stores results in data/ma_scan.parquet and
publishes one overwritten JSON (`aqe_ma_scan.json`) to a dedicated Drive folder
(`MA_SCAN_FOLDER_ID`). The first run pulls ~250 days of bars for the full MA
universe (~2000 tickers, ~8 min at 250 calls/min); subsequent daily runs are
incremental (only new bars since last pull, most tickers skipped) so they're fast.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data.fmp_client import FMPClient, FMPError, FMPQuotaError, iter_with_progress
from src.data.paths import DATA_DIR, OUTPUT_DIR

MA_PANEL = DATA_DIR / "ma_panel.parquet"
MA_SCAN = DATA_DIR / "ma_scan.parquet"
MA_UNIVERSE_CACHE = DATA_DIR / "ma_universe.json"

PROXIMITY_PCT = 10.0
MA_PERIODS = [20, 50, 100, 200]
LOOKBACK_CALENDAR_DAYS = 400  # enough for 200 trading days + buffer
MIN_MCAP = 1_000_000_000

# Dedicated Drive folder for the daily MA-scan output (one overwritten JSON).
MA_SCAN_FOLDER_ID = (
    os.environ.get("GDRIVE_MA_SCAN_FOLDER_ID")
    or "1HAh3Vw0sWASm5GccifPUP5_cZh31Z7oC"
)
MA_SCAN_DRIVE_FILENAME = "aqe_ma_scan.json"


def get_ma_universe(client: FMPClient | None = None) -> pd.DataFrame:
    """Screen for all US stocks > $1B market cap.

    Returns DataFrame with columns: ticker, name, market_cap, sector, exchange.
    Caches to ma_universe.json for reuse within the same day.
    """
    import json

    today_str = date.today().isoformat()
    if MA_UNIVERSE_CACHE.exists():
        try:
            cached = json.loads(MA_UNIVERSE_CACHE.read_text(encoding="utf-8"))
            if cached.get("date") == today_str and cached.get("tickers"):
                return pd.DataFrame(cached["tickers"])
        except Exception:
            pass

    if client is None:
        client = FMPClient()

    raw = client.get_screener(
        min_mcap=MIN_MCAP,
        min_price=1.0,
        min_volume=0,
        exchanges=["NASDAQ", "NYSE"],
        limit=5000,
    )

    EXCLUDED_SUFFIXES = ("-W", "-U", ".W", ".U", "-R", "-RT")
    EXCLUDED_CONTAINS = ("-P", "-PA", "-PB", "-PC", "-PD")
    tickers = []
    for r in raw:
        sym = r.get("symbol", "")
        if not sym or any(sym.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        if "." in sym and not sym.startswith("."):
            continue
        if "-" in sym and any(sym.endswith(s) or f"{s}" in sym for s in EXCLUDED_CONTAINS):
            continue
        tickers.append({
            "ticker": sym,
            "name": r.get("companyName", ""),
            "market_cap": r.get("marketCap", 0),
            "sector": r.get("sector", ""),
            "exchange": r.get("exchange", ""),
        })

    cache_data = {"date": today_str, "tickers": tickers}
    MA_UNIVERSE_CACHE.write_text(json.dumps(cache_data), encoding="utf-8")

    print(f"  MA universe: {len(tickers)} tickers (>{MIN_MCAP/1e9:.0f}B mcap, US exchanges)")
    return pd.DataFrame(tickers)


def build_ma_panel(
    universe: pd.DataFrame | None = None,
    client: FMPClient | None = None,
) -> pd.DataFrame:
    """Pull/update daily bars for the MA universe. Incremental."""
    if client is None:
        client = FMPClient()
    if universe is None:
        universe = get_ma_universe(client)

    tickers = sorted(universe["ticker"].unique())
    to_date = date.today()
    from_date = to_date - timedelta(days=LOOKBACK_CALENDAR_DAYS)

    existing = pd.DataFrame()
    if MA_PANEL.exists():
        existing = pd.read_parquet(MA_PANEL)
        existing["date"] = pd.to_datetime(existing["date"]).dt.normalize()

    existing_tickers = set()
    last_dates: dict[str, date] = {}
    if not existing.empty:
        existing_tickers = set(existing["ticker"].unique())
        for tk, grp in existing.groupby("ticker"):
            last_dates[tk] = grp["date"].max().date()

    new_frames = []
    pulled = 0
    skipped = 0

    for ticker in iter_with_progress(tickers, label="ma_bars"):
        last = last_dates.get(ticker)
        if last and last >= to_date - timedelta(days=1):
            skipped += 1
            continue

        pull_from = last + timedelta(days=1) if last else from_date
        try:
            bars = client.get_daily_bars(ticker, from_date=pull_from, to_date=to_date)
            if not bars.empty:
                bars["ticker"] = ticker
                new_frames.append(bars)
            pulled += 1
        except FMPQuotaError:
            print(f"\n  [MA Scanner] FMP quota reached after {pulled} pulls. "
                  f"Saving partial results — next run will continue.")
            break
        except FMPError:
            continue

    if new_frames:
        new_bars = pd.concat(new_frames, ignore_index=True)
        if not existing.empty:
            panel = pd.concat([existing, new_bars], ignore_index=True)
            panel = panel.drop_duplicates(subset=["date", "ticker"], keep="last")
        else:
            panel = new_bars
    else:
        panel = existing

    if panel.empty:
        print("  [MA Scanner] No bars available")
        return panel

    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    cutoff = pd.Timestamp(from_date)
    panel = panel[panel["date"] >= cutoff].reset_index(drop=True)

    panel.to_parquet(MA_PANEL, index=False)
    n_tickers = panel["ticker"].nunique()
    print(f"  MA panel: {n_tickers} tickers, {len(panel):,} rows "
          f"(pulled {pulled}, skipped {skipped} current)")
    return panel


def compute_ma_proximity(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute SMA values, distances, and streak counts for each ticker.

    Returns one row per ticker with the latest date's proximity data.
    """
    results = []

    for ticker, grp in panel.groupby("ticker", sort=False):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < 20:
            continue

        close = grp["close"]
        latest_close = close.iloc[-1]
        latest_date = grp["date"].iloc[-1]

        row = {"ticker": ticker, "close": latest_close, "date": latest_date}

        for period in MA_PERIODS:
            col_sma = f"sma_{period}"
            col_dist = f"dist_sma{period}"
            col_near = f"near_sma{period}"
            col_side = f"side_sma{period}"
            col_days = f"days_near_{period}"

            if len(grp) < period:
                row[col_sma] = np.nan
                row[col_dist] = np.nan
                row[col_near] = False
                row[col_side] = ""
                row[col_days] = 0
                continue

            sma_series = close.rolling(period).mean()
            sma_val = sma_series.iloc[-1]

            if sma_val == 0 or np.isnan(sma_val):
                row[col_sma] = np.nan
                row[col_dist] = np.nan
                row[col_near] = False
                row[col_side] = ""
                row[col_days] = 0
                continue

            dist_pct = (latest_close - sma_val) / sma_val * 100
            is_near = abs(dist_pct) <= PROXIMITY_PCT

            # Streak: consecutive days (ending today) within ±10% of this MA
            dist_series = (close - sma_series) / sma_series * 100
            near_series = dist_series.abs() <= PROXIMITY_PCT
            streak = 0
            for val in reversed(near_series.dropna().values):
                if val:
                    streak += 1
                else:
                    break

            row[col_sma] = round(sma_val, 2)
            row[col_dist] = round(dist_pct, 2)
            row[col_near] = is_near
            row[col_side] = "ABOVE" if dist_pct > 0 else "BELOW"
            row[col_days] = streak

        # How many MAs is this stock near?
        row["ma_near_count"] = sum(
            1 for p in MA_PERIODS if row.get(f"near_sma{p}", False)
        )

        results.append(row)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df[df[[f"near_sma{p}" for p in MA_PERIODS]].any(axis=1)].copy()
    df = df.sort_values("ma_near_count", ascending=False).reset_index(drop=True)
    return df


def publish_ma_scan(scan: pd.DataFrame, stats: dict) -> dict:
    """Publish the MA scan to the dedicated Drive folder as ONE overwritten JSON
    (`aqe_ma_scan.json`), plus a local working copy in output/. Best-effort —
    never raises. Records are the near-an-MA rows (sorted by ma_near_count desc).
    """
    import json
    sgt = ZoneInfo("Asia/Singapore")
    records = [] if scan is None or scan.empty else json.loads(
        scan.assign(date=scan["date"].astype(str)).to_json(orient="records"))
    payload = {
        "generated_at": datetime.now(sgt).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "proximity_pct": PROXIMITY_PCT,
        "ma_periods": MA_PERIODS,
        "min_mcap": MIN_MCAP,
        "stats": stats,
        "count": len(records),
        "scan": records,
    }
    content = json.dumps(payload, indent=2)

    # Local working copy (erase-then-write, single file).
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / MA_SCAN_DRIVE_FILENAME).write_text(content, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    # Drive — overwrite in place, then trim the folder to this single file.
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return {"ok": False, "reason": "Drive not configured (local copy only)"}
        r = gdrive_uploader.upload_or_replace(
            MA_SCAN_DRIVE_FILENAME, content, mime="application/json",
            folder_id=MA_SCAN_FOLDER_ID)
        if r.get("ok") and r.get("file_id"):
            try:
                gdrive_uploader.keep_only_file(MA_SCAN_FOLDER_ID, r["file_id"])
            except Exception:  # noqa: BLE001
                pass
        return r
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def run_ma_scan(client: FMPClient | None = None, publish: bool = True) -> dict:
    """Full MA scan: screen universe → pull bars → compute proximity.

    Returns dict with scan results and stats.
    """
    t0 = time.time()
    if client is None:
        client = FMPClient()

    print("[MA Scanner] Step 1: Screen universe...")
    universe = get_ma_universe(client)
    if universe.empty:
        return {"ok": False, "reason": "No tickers from screener"}

    print("[MA Scanner] Step 2: Pull/update daily bars...")
    panel = build_ma_panel(universe, client)
    if panel.empty:
        return {"ok": False, "reason": "No bars available"}

    print("[MA Scanner] Step 3: Compute MA proximity...")
    scan = compute_ma_proximity(panel)

    # Enrich with universe metadata
    meta_cols = ["ticker", "name", "market_cap", "sector", "exchange"]
    meta = universe[meta_cols].drop_duplicates(subset="ticker")
    if not scan.empty:
        scan = scan.merge(meta, on="ticker", how="left")

    # Flag tickers also in AQE universe
    try:
        from src.data.universe import load_universe
        aqe_tickers = set(load_universe(include_benchmark=False))
        scan["in_aqe"] = scan["ticker"].isin(aqe_tickers)
    except Exception:
        scan["in_aqe"] = False

    # Save results
    if not scan.empty:
        scan.to_parquet(MA_SCAN, index=False)

    elapsed = time.time() - t0

    stats = {
        "universe_size": len(universe),
        "panel_tickers": panel["ticker"].nunique() if not panel.empty else 0,
        "near_any_ma": len(scan),
        "near_sma20": int(scan["near_sma20"].sum()) if not scan.empty else 0,
        "near_sma50": int(scan["near_sma50"].sum()) if not scan.empty else 0,
        "near_sma100": int(scan["near_sma100"].sum()) if not scan.empty else 0,
        "near_sma200": int(scan["near_sma200"].sum()) if not scan.empty else 0,
        "elapsed_seconds": round(elapsed),
    }

    print(f"[MA Scanner] Done in {elapsed:.0f}s — "
          f"{stats['near_any_ma']} stocks near at least one MA")
    for p in MA_PERIODS:
        print(f"  Near SMA{p}: {stats[f'near_sma{p}']}")

    # Publish the scan to the dedicated Drive folder (one overwritten JSON).
    pub = {"ok": False, "reason": "publish skipped"}
    if publish:
        pub = publish_ma_scan(scan, stats)
        print(f"[MA Scanner] Drive publish: "
              f"{'ok' if pub.get('ok') else pub.get('reason')}")

    return {"ok": True, "scan": scan, "stats": stats, "publish": pub}


def load_latest_scan() -> pd.DataFrame:
    """Load cached MA scan results. Returns empty DataFrame if none."""
    if MA_SCAN.exists():
        df = pd.read_parquet(MA_SCAN)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame()
