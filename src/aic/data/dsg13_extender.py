"""DSG-13 additive extender for the AQE daily export.

The spec mandates 5 new fields on each top_picks / longlist / watchlist entry:
  - sector_corr        Pearson(stock_returns, sector_ETF_returns) over 60 days
  - breakout_stop      Charter §6B: min(DSL, flush_low) * 0.99 if flush exists, else DSL
  - gics_sector        the ticker's mapped GICS ETF (XLK, XLE, ...)
  - sma_distance_pct   (close - SMA20) / SMA20 * 100
  - held               True iff ticker appears in data/open_positions.json

Per the AQE-PRESERVATION mandate, AQE files are not modified. This module is
a *post-processor*: it reads the existing aqe_daily_export.json, computes the
5 fields per entry, and rewrites the same JSON file. Run after the daily
pipeline finishes (or any time you want to refresh DSG-13 against the cached
panel).

CLI:
    python -m src.aic.data.dsg13_extender
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

EXPORT_PATH = PROJECT_ROOT / "output" / "aqe_daily_export.json"
PANEL_PATH = PROJECT_ROOT / "data" / "panel_daily.parquet"
OPEN_POSITIONS_PATH = PROJECT_ROOT / "data" / "open_positions.json"

SECTOR_CORR_WINDOW = 60        # trading days, Pearson
SMA_WINDOW = 20                # for sma_distance_pct (matches PTRS SH definition)
FLUSH_LOOKBACK = 5             # last N sessions for the flush low
BREAKOUT_BUFFER = 0.99         # 1% below structural breakout level


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sector_map() -> dict[str, str]:
    """{ticker: ETF} mapping. Uses the existing AQE sector mapper if present."""
    try:
        from src.data.sector_mapper import load_sector_map
        return load_sector_map() or {}
    except Exception:
        # Fallback to the engines' static map.
        from src.engines.srm import TICKER_TO_SECTOR
        return dict(TICKER_TO_SECTOR)


def _load_held_set() -> set[str]:
    """Tickers currently in open_positions.json -> `held=True` for DSG-13."""
    if not OPEN_POSITIONS_PATH.exists():
        return set()
    try:
        data = json.loads(OPEN_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, list):
        return {str(p.get("ticker", "")).upper() for p in data if isinstance(p, dict)}
    if isinstance(data, dict):
        return {str(k).upper() for k in data.keys()}
    return set()


def _load_panel() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH, columns=["date", "ticker", "high", "low", "close"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    return panel


def _compute_sector_corr(
    panel_pivot_close: pd.DataFrame,
    tickers: list[str],
    sector_map: dict[str, str],
    window: int = SECTOR_CORR_WINDOW,
) -> dict[str, float | None]:
    """Per-ticker Pearson correlation between stock returns and its GICS ETF over `window` days.

    panel_pivot_close: pivot of close prices, columns=tickers, index=dates.
    """
    returns = panel_pivot_close.pct_change().dropna(how="all")
    if len(returns) < window + 1:
        return {t: None for t in tickers}
    recent = returns.iloc[-window:]
    out: dict[str, float | None] = {}
    for t in tickers:
        etf = sector_map.get(t)
        if not etf or t not in recent.columns or etf not in recent.columns:
            out[t] = None
            continue
        s = recent[t]
        e = recent[etf]
        common = s.dropna().index.intersection(e.dropna().index)
        if len(common) < 10:
            out[t] = None
            continue
        try:
            corr = float(s.loc[common].corr(e.loc[common]))
            out[t] = round(corr, 3) if pd.notna(corr) else None
        except Exception:
            out[t] = None
    return out


def _compute_breakout_stop(
    ticker: str,
    entry: float | None,
    dsl_stop: float | None,
    panel_by_ticker: dict[str, pd.DataFrame],
) -> tuple[float | None, str]:
    """Charter §6B breakout stop.

    breakout_stop = min(DSL, flush_low) * 0.99   if flush_low < entry (a flush exists)
                  = DSL                          if no flush in prior 5 sessions
    """
    if dsl_stop is None:
        return None, "no DSL"
    df = panel_by_ticker.get(ticker)
    if df is None or len(df) < FLUSH_LOOKBACK:
        return round(dsl_stop, 2), "DSL only (panel insufficient)"
    flush_low = float(df["low"].iloc[-FLUSH_LOOKBACK:].min())
    if entry is None or flush_low < float(entry):
        candidate = min(dsl_stop, flush_low) * BREAKOUT_BUFFER
        return round(candidate, 2), "min(DSL, flush_low) - 1%"
    return round(dsl_stop, 2), "DSL only (no flush in prior 5)"


def _compute_sma_distance_pct(
    ticker: str,
    panel_by_ticker: dict[str, pd.DataFrame],
    window: int = SMA_WINDOW,
) -> float | None:
    df = panel_by_ticker.get(ticker)
    if df is None or len(df) < window:
        return None
    close = df["close"].astype(float)
    sma = close.rolling(window, min_periods=window).mean().iloc[-1]
    last = close.iloc[-1]
    if pd.isna(sma) or sma == 0:
        return None
    return round((last - sma) / sma * 100.0, 2)


# ---------------------------------------------------------------------------
# Main extender
# ---------------------------------------------------------------------------

def enrich_export(
    export_path: Path | str | None = None,
    write: bool = True,
) -> dict:
    """Read AQE export JSON, append DSG-13 fields to every entry, write back.

    `write=False` -> compute + return the enriched dict without persisting.
    """
    export_path = Path(export_path) if export_path else EXPORT_PATH
    if not export_path.exists():
        raise FileNotFoundError(
            f"AQE export not found at {export_path}. Run the daily pipeline first."
        )
    export = json.loads(export_path.read_text(encoding="utf-8"))

    panel = _load_panel()
    sector_map = _load_sector_map()
    held_set = _load_held_set()

    # Collect tickers needed across all sections we touch
    sections = ["top_picks", "edge_list", "longlist", "watchlist"]
    all_tickers: set[str] = set()
    for s in sections:
        for r in export.get(s, []) or []:
            tk = r.get("ticker")
            if tk:
                all_tickers.add(str(tk))

    # Build the close pivot once -- include the GICS ETFs the tickers map to
    etfs_needed = {sector_map.get(t) for t in all_tickers}
    etfs_needed.discard(None)
    cols_needed = list(all_tickers | etfs_needed)
    panel_close_pivot = (
        panel[panel["ticker"].isin(cols_needed)]
        .pivot_table(index="date", columns="ticker", values="close")
        .sort_index()
    )
    panel_by_ticker = {
        t: g.sort_values("date").reset_index(drop=True)
        for t, g in panel[panel["ticker"].isin(cols_needed)].groupby("ticker", sort=False)
    }

    sector_corr_map = _compute_sector_corr(
        panel_close_pivot, list(all_tickers), sector_map,
    )

    counts = {s: 0 for s in sections}
    for s in sections:
        for r in export.get(s, []) or []:
            ticker = str(r.get("ticker", ""))
            if not ticker:
                continue
            r["sector_corr"] = sector_corr_map.get(ticker)
            r["gics_sector"] = sector_map.get(ticker)
            r["sma_distance_pct"] = _compute_sma_distance_pct(ticker, panel_by_ticker)
            bs, _src = _compute_breakout_stop(
                ticker,
                entry=r.get("entry") or r.get("dsl_entry"),
                dsl_stop=r.get("dsl_stop") or r.get("stop"),
                panel_by_ticker=panel_by_ticker,
            )
            r["breakout_stop"] = bs
            r["held"] = ticker.upper() in held_set
            counts[s] += 1

    export["dsg13_enriched"] = {
        "fields": ["sector_corr", "breakout_stop", "gics_sector",
                   "sma_distance_pct", "held"],
        "counts": counts,
        "sector_corr_window_days": SECTOR_CORR_WINDOW,
        "sma_window_days": SMA_WINDOW,
        "flush_lookback_days": FLUSH_LOOKBACK,
        "breakout_buffer_factor": BREAKOUT_BUFFER,
    }

    if write:
        export_path.write_text(json.dumps(export, indent=2), encoding="utf-8")
    return export


if __name__ == "__main__":
    out = enrich_export()
    print(f"DSG-13 enrichment counts: {out.get('dsg13_enriched', {}).get('counts')}")
