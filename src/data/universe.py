"""Universe management — load, refresh, and persist the ticker list.

data/universe.txt is the canonical source. refresh_universe() pulls from the FMP
screener to catch new listings meeting the criteria ($1B+ mcap, $5+ price,
500K+ daily volume, NYSE/NASDAQ only).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.data.paths import DATA_DIR, PROJECT_ROOT

DEFAULT_UNIVERSE_FILE = DATA_DIR / "universe.txt"
BENCHMARK = "SPY"

UNIVERSE_MIN_MCAP = 1_000_000_000
UNIVERSE_MIN_PRICE = 5.0
UNIVERSE_MIN_VOLUME = 500_000
UNIVERSE_EXCHANGES = ["NASDAQ", "NYSE"]

EXCLUDED_SUFFIXES = ("-W", "-U", ".W", ".U")


def load_universe(path: Path | None = None, include_benchmark: bool = True) -> list[str]:
    """Read tickers from universe.txt.

    Strips comments (# ...) and blank lines. De-duplicates while preserving order.
    """
    file = path or DEFAULT_UNIVERSE_FILE
    tickers: list[str] = []
    seen: set[str] = set()
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        sym = line.upper()
        if sym in seen:
            continue
        seen.add(sym)
        tickers.append(sym)

    if include_benchmark and BENCHMARK not in seen:
        tickers.insert(0, BENCHMARK)
    return tickers


def refresh_universe(dry_run: bool = False) -> dict:
    """Pull FMP screener and update universe.txt with qualifying tickers.

    Returns dict with: added (new tickers), removed (dropped below threshold),
    total (final count), unchanged (bool).
    """
    from src.data.fmp_client import FMPClient

    client = FMPClient()
    results = client.get_screener(
        min_mcap=UNIVERSE_MIN_MCAP,
        min_price=UNIVERSE_MIN_PRICE,
        min_volume=UNIVERSE_MIN_VOLUME,
        exchanges=UNIVERSE_EXCHANGES,
    )

    new_tickers: list[str] = []
    for item in results:
        sym = item.get("symbol", "").upper().strip()
        if not sym or any(sym.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        if "." in sym or " " in sym:
            continue
        new_tickers.append(sym)

    new_set = set(new_tickers)
    current = load_universe(include_benchmark=False)
    current_set = set(current)

    added = sorted(new_set - current_set)
    removed = sorted(current_set - new_set)

    if not added and not removed:
        return {"added": [], "removed": [], "total": len(current), "unchanged": True}

    # Merge: keep existing order, append new at end, drop removed
    merged: list[str] = [t for t in current if t not in removed]
    merged.extend(added)

    if not dry_run:
        _write_universe(merged)

    return {
        "added": added,
        "removed": removed,
        "total": len(merged),
        "unchanged": False,
    }


def upload_universe(csv_path_or_bytes) -> dict:
    """Replace universe.txt from a CSV upload (e.g. TradingView screener export).

    Accepts either a file path (str/Path) or an UploadedFile (BytesIO) from
    Streamlit's file_uploader. Looks for a 'Symbol' column, extracts tickers,
    filters junk, writes universe.txt.

    Returns dict with: tickers (list), count (int), previous_count (int).
    """
    import pandas as pd

    if isinstance(csv_path_or_bytes, (str, Path)):
        df = pd.read_csv(csv_path_or_bytes)
    else:
        # Streamlit UploadedFile (BytesIO-like)
        df = pd.read_csv(csv_path_or_bytes)

    # Find the Symbol column (case-insensitive)
    sym_col = None
    for col in df.columns:
        if col.strip().lower() == "symbol":
            sym_col = col
            break
    if sym_col is None:
        raise ValueError(
            f"CSV has no 'Symbol' column. Found columns: {list(df.columns)}"
        )

    raw = df[sym_col].dropna().astype(str).str.strip().str.upper().tolist()

    # Filter: skip warrants/units, tickers with dots/spaces
    tickers: list[str] = []
    seen: set[str] = set()
    for sym in raw:
        if not sym or sym in seen:
            continue
        if any(sym.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        if "." in sym or " " in sym:
            continue
        seen.add(sym)
        tickers.append(sym)

    previous = load_universe(include_benchmark=False)
    _write_universe(tickers)

    return {
        "tickers": tickers,
        "count": len(tickers),
        "previous_count": len(previous),
    }


def _write_universe(tickers: list[str]) -> None:
    """Write universe.txt locally AND back up to Google Drive for persistence.

    The local file is the runtime read path. The Drive copy survives container
    restarts on HuggingFace (ephemeral filesystem). On next startup,
    ``restore_universe_from_drive()`` pulls it back before the first
    ``load_universe()`` call.
    """
    lines = [
        f"# AQE Universe — updated {date.today()}",
        f"# {len(tickers)} tickers",
        "",
    ]
    lines.extend(tickers)
    lines.append("")
    content = "\n".join(lines)
    DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_UNIVERSE_FILE.write_text(content, encoding="utf-8")

    # Back up to Drive (best-effort — never blocks the pipeline)
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(
                "universe.txt", content, mime="text/plain",
            )
    except Exception:  # noqa: BLE001
        pass


def _csv_to_universe_text(content: str) -> str | None:
    """Extract tickers from a screener CSV (Symbol column) → universe.txt text.

    Returns None if there is no recognisable Symbol column.
    """
    import csv
    import io

    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return None
    header = [h.strip().lower() for h in rows[0]]
    try:
        sym_idx = next(i for i, h in enumerate(header)
                       if h in ("symbol", "ticker", "symbols", "tickers"))
    except StopIteration:
        return None

    tickers: list[str] = []
    seen: set[str] = set()
    for r in rows[1:]:
        if len(r) <= sym_idx:
            continue
        sym = r[sym_idx].strip().upper()
        if not sym or sym in seen:
            continue
        if any(sym.endswith(s) for s in EXCLUDED_SUFFIXES) or "." in sym or " " in sym:
            continue
        seen.add(sym)
        tickers.append(sym)
    if not tickers:
        return None
    return "\n".join([f"# AQE Universe — restored from Drive CSV ({date.today()})",
                      f"# {len(tickers)} tickers", "", *tickers, ""])


def restore_universe_from_drive() -> bool:
    """Pull the universe from the pinned Drive folder and overwrite the local copy.

    Drive is the single source of truth for the universe (the "fishing net").
    Looks for `universe.txt` first, then `universe.csv` (a screener export with a
    Symbol column). Runs on every startup so a fresh HF container — or one with a
    stale baked-in universe.txt — always reflects what you put in Drive.
    Returns True if a restore happened.
    """
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return False

        cfg = gdrive_uploader.DriveConfig.from_env()
        if cfg is None:
            return False
        service = gdrive_uploader._build_service(cfg)
        folder_id = gdrive_uploader._resolve_folder_id(service, cfg)
        if not folder_id:
            return False

        # Prefer a plain universe.txt; fall back to a universe.csv export.
        found = gdrive_uploader._find_file(service, folder_id, "universe.txt")
        as_csv = False
        if not found:
            found = gdrive_uploader._find_file(service, folder_id, "universe.csv")
            as_csv = True
        if not found:
            return False

        content = service.files().get_media(fileId=found["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        if as_csv:
            converted = _csv_to_universe_text(content)
            if converted is None:
                return False
            content = converted

        DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_UNIVERSE_FILE.write_text(content, encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False
