"""Auto-map tickers to GICS sector ETFs using FMP company profiles.

FMP /stable/profile returns sector + industry for each ticker.
We map those to the 11 GICS ETFs used by SRM.

Run:
    python -m src.data.sector_mapper
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.fmp_client import FMPClient, FMPError
from src.data.paths import DATA_DIR
from src.data.universe import load_universe
from src.engines.srm import GICS_ETFS

SECTOR_MAP_PATH = DATA_DIR / "sector_map.json"

SECTOR_TO_ETF = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}

# Reverse map: ETF ticker → human-readable sector name (GICS standard)
ETF_TO_NAME = {
    "XLK": "Technology",
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLE": "Energy",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
}


def build_sector_map(tickers: list[str] | None = None) -> dict[str, str]:
    """Fetch FMP profiles and build ticker → ETF mapping.

    Respects rate limits. Saves to data/sector_map.json.
    Incremental: only fetches tickers not already in the map.
    """
    existing = load_sector_map()

    if tickers is None:
        tickers = load_universe(include_benchmark=False)

    to_fetch = [t for t in tickers if t not in existing and t not in GICS_ETFS and t != "SPY"]
    if not to_fetch:
        print(f"[sector] All {len(existing)} tickers already mapped.")
        return existing

    print(f"[sector] Fetching profiles for {len(to_fetch)} unmapped tickers...")
    client = FMPClient()
    mapped = 0

    for i, ticker in enumerate(to_fetch):
        try:
            url = "https://financialmodelingprep.com/stable/profile"
            resp = client._get_json(url, {"symbol": ticker, "apikey": client.config.api_key})
            if isinstance(resp, list) and resp:
                sector = resp[0].get("sector", "")
                etf = SECTOR_TO_ETF.get(sector)
                if etf:
                    existing[ticker] = etf
                    mapped += 1
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(to_fetch)}] mapped so far: {mapped}")
        except FMPError:
            continue
        except Exception:
            continue

    _save_sector_map(existing)
    print(f"[sector] Done. {mapped} new mappings. Total: {len(existing)} tickers mapped.")
    return existing


def load_sector_map() -> dict[str, str]:
    """Load existing sector map from disk."""
    if SECTOR_MAP_PATH.exists():
        with open(SECTOR_MAP_PATH) as f:
            return json.load(f)
    return {}


def _save_sector_map(mapping: dict[str, str]) -> None:
    """Save sector map to disk."""
    SECTOR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SECTOR_MAP_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    build_sector_map()
