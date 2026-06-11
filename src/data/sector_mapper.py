"""Auto-map tickers to GICS sector ETFs using FMP company profiles.

FMP /stable/profile returns sector + industry for each ticker.
We map those to the 11 GICS ETFs used by SRM.

Run:
    python -m src.data.sector_mapper
"""

from __future__ import annotations

import json
import os
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

# Central sector RAG on Drive — the round-trip source of truth. AQE restores
# the local flat map from this file on startup and republishes it (auto-filled)
# each run. Override the folder with GDRIVE_SECTOR_FOLDER_ID.
SECTOR_MAP_DRIVE_FILENAME = "aqe_sector_map.json"
SECTOR_MAP_FOLDER_ID = (
    os.environ.get("GDRIVE_SECTOR_FOLDER_ID")
    or "1CKhgB_wjtZipC8TdagIGN0dINiwhk6Ul"
)

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


def restore_sector_map_from_drive() -> int:
    """Overwrite the local sector map from the central Drive RAG (source of truth).

    Drive's `aqe_sector_map.json` is the single source of truth. Parses its rich
    §6.2 format ({tickers: {tk: {gics_etf, ...}}}) into the flat {ticker: ETF}
    map AQE reads, merging into the local file (Drive wins on conflicts). Runs on
    pipeline startup so an ephemeral container reflects Drive WITHOUT re-querying
    FMP for GICS already resolved on a prior run. Returns the number of mappings
    restored from Drive (0 if Drive is unconfigured/empty). Never raises.
    """
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return 0
        content = gdrive_uploader.download_text(
            SECTOR_MAP_DRIVE_FILENAME, SECTOR_MAP_FOLDER_ID
        )
        if not content:
            return 0
        data = json.loads(content)
        rich = data.get("tickers") or {}
        flat = {
            tk: info["gics_etf"]
            for tk, info in rich.items()
            if isinstance(info, dict) and info.get("gics_etf")
        }
        if not flat:
            return 0
        existing = load_sector_map()
        existing.update(flat)  # Drive is authoritative on conflicts
        _save_sector_map(existing)
        return len(flat)
    except Exception:  # noqa: BLE001
        return 0


def get_sector_map_gaps(tickers: list[str] | None = None) -> list[str]:
    """Universe tickers with no GICS ETF mapping (blank sector). Sorted."""
    sm = load_sector_map()
    if tickers is None:
        try:
            tickers = load_universe(include_benchmark=False)
        except Exception:  # noqa: BLE001
            tickers = list(sm.keys())
    return sorted(
        t for t in set(tickers)
        if t not in sm and t not in GICS_ETFS and t != "SPY"
    )


def probe_profiles(tickers: list[str]) -> list[dict]:
    """Fetch FMP sector/industry for each ticker so the PM can resolve blanks.

    Returns [{ticker, fmp_sector, fmp_industry, suggested_etf}, ...]. The
    suggested_etf is filled when FMP's sector maps cleanly via SECTOR_TO_ETF;
    otherwise it's blank and needs a manual call (e.g. TradingView 'Commercial
    services' → XLK). Never raises — failures degrade to blank rows.
    """
    out: list[dict] = []
    try:
        client = FMPClient()
    except Exception:  # noqa: BLE001
        return [{"ticker": t, "fmp_sector": "", "fmp_industry": "",
                 "suggested_etf": ""} for t in tickers]
    for t in tickers:
        sector = industry = ""
        try:
            url = "https://financialmodelingprep.com/stable/profile"
            resp = client._get_json(url, {"symbol": t, "apikey": client.config.api_key})
            if isinstance(resp, list) and resp:
                sector = resp[0].get("sector", "") or ""
                industry = resp[0].get("industry", "") or ""
        except Exception:  # noqa: BLE001
            pass
        out.append({
            "ticker": t,
            "fmp_sector": sector,
            "fmp_industry": industry,
            "suggested_etf": SECTOR_TO_ETF.get(sector, ""),
        })
    return out


def add_sector_mappings(mapping: dict[str, str]) -> dict[str, str]:
    """Merge {ticker: ETF} into the canonical sector_map.json and save it.

    Only non-empty ETF values are written. Returns the full updated map.
    """
    existing = load_sector_map()
    existing.update({k.upper().strip(): v for k, v in mapping.items() if v})
    _save_sector_map(existing)
    return existing


def _save_sector_map(mapping: dict[str, str]) -> None:
    """Save sector map to disk."""
    SECTOR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SECTOR_MAP_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    build_sector_map()
