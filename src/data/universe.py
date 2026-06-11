"""Universe management — load + persist the curated ticker list (the "fishing net").

The universe is a FIXED, manually-curated list. It lives as a single CSV in a
dedicated Google Drive folder (`UNIVERSE_FOLDER_ID`), which is the source of
truth. On startup `restore_universe_from_drive()` overwrites the local
`universe.txt` from that folder. Update it by uploading a new CSV via the app
(overwrites the canonical file) or by replacing the file directly in Drive.

`refresh_universe()` (FMP screener) is retained for MANUAL use only — it is no
longer called by the daily pipeline (it ballooned the list to ~1800 tickers).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from src.data.paths import DATA_DIR, PROJECT_ROOT

DEFAULT_UNIVERSE_FILE = DATA_DIR / "universe.txt"
# Manual, version-controlled add-on list. Merged on top of universe.txt at load
# time so the tickers survive `restore_universe_from_drive()` (which overwrites
# universe.txt but not this file). Used when the canonical Drive universe.csv
# can't be re-uploaded yet. De-duped against the main list; safe to leave in
# place — delete once the Drive CSV carries these names.
SUPPLEMENT_UNIVERSE_FILE = DATA_DIR / "universe_supplement.txt"
BENCHMARK = "SPY"

# Dedicated Drive folder holding the universe CSV (a subfolder of the AQE
# folder). Override per-deploy with GDRIVE_UNIVERSE_FOLDER_ID.
UNIVERSE_FOLDER_ID = (
    os.environ.get("GDRIVE_UNIVERSE_FOLDER_ID")
    or "16wAS7Xsn6h8bHQRcWxFgq7bXPVd2jQhA"
)
# Canonical filename the app writes — single file, overwritten each upload.
UNIVERSE_DRIVE_FILENAME = "universe.csv"

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

    sources = [file]
    # Only merge the supplement when reading the default universe (not an
    # explicit ad-hoc path), and only if it exists.
    if path is None and SUPPLEMENT_UNIVERSE_FILE.exists():
        sources.append(SUPPLEMENT_UNIVERSE_FILE)

    for src in sources:
        for raw in src.read_text(encoding="utf-8").splitlines():
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


def _read_text(csv_path_or_bytes) -> str:
    """Read CSV text from a path, a Streamlit UploadedFile, or raw bytes/str."""
    if isinstance(csv_path_or_bytes, (str, Path)):
        return Path(csv_path_or_bytes).read_text(encoding="utf-8-sig")
    data = (csv_path_or_bytes.getvalue() if hasattr(csv_path_or_bytes, "getvalue")
            else csv_path_or_bytes.read())
    return data.decode("utf-8-sig") if isinstance(data, bytes) else data


def upload_universe(csv_path_or_bytes) -> dict:
    """Set the universe from a screener CSV (with a Symbol column).

    Writes the parsed tickers to the local universe.txt AND uploads the raw CSV
    to the universe Drive folder as the canonical file (overwriting it), so the
    new list persists across container restarts. Accepts a path or a Streamlit
    UploadedFile.

    Returns: {tickers, count, previous_count, drive_ok, drive_reason}.
    """
    raw = _read_text(csv_path_or_bytes)
    universe_txt = _csv_to_universe_text(raw)
    if universe_txt is None:
        raise ValueError("CSV has no recognisable 'Symbol' column.")

    try:
        previous = load_universe(include_benchmark=False)
    except Exception:  # noqa: BLE001
        previous = []

    DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_UNIVERSE_FILE.write_text(universe_txt, encoding="utf-8")
    tickers = [ln for ln in universe_txt.splitlines() if ln and not ln.startswith("#")]

    # Overwrite the canonical CSV in the universe Drive folder.
    drive_ok, drive_reason = False, "not configured"
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            r = gdrive_uploader.upload_or_replace(
                UNIVERSE_DRIVE_FILENAME, raw, mime="text/csv",
                folder_id=UNIVERSE_FOLDER_ID,
            )
            drive_ok = bool(r.get("ok"))
            drive_reason = r.get("reason", "ok" if drive_ok else "failed")
    except Exception as exc:  # noqa: BLE001
        drive_reason = f"{type(exc).__name__}: {exc}"

    return {
        "tickers": tickers,
        "count": len(tickers),
        "previous_count": len(previous),
        "drive_ok": drive_ok,
        "drive_reason": drive_reason,
    }


def _write_universe(tickers: list[str]) -> None:
    """Write universe.txt locally (used by the manual refresh path only)."""
    lines = [f"# AQE Universe — updated {date.today()}",
             f"# {len(tickers)} tickers", "", *tickers, ""]
    DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_UNIVERSE_FILE.write_text("\n".join(lines), encoding="utf-8")


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


def _drive_service():
    """Return (service, universe_folder_id), or (None, None) if Drive isn't set up."""
    from src.data import gdrive_uploader
    if not gdrive_uploader.is_configured():
        return None, None
    cfg = gdrive_uploader.DriveConfig.from_env()
    if cfg is None:
        return None, None
    return gdrive_uploader._build_service(cfg), UNIVERSE_FOLDER_ID


def _active_universe_file(service, folder_id) -> dict | None:
    """The canonical universe.csv if present, else the newest CSV in the folder."""
    q = f"'{folder_id}' in parents and trashed = false"
    res = service.files().list(
        q=q, orderBy="modifiedTime desc",
        fields="files(id,name,modifiedTime,mimeType)",
    ).execute()
    files = [f for f in (res.get("files") or [])
             if f.get("name", "").lower().endswith(".csv")
             or f.get("mimeType") == "text/csv"]
    if not files:
        return None
    for f in files:
        if f.get("name", "").lower() == UNIVERSE_DRIVE_FILENAME:
            return f
    return files[0]  # newest by modifiedTime


def restore_universe_from_drive() -> bool:
    """Overwrite the local universe.txt from the universe Drive folder.

    Drive is the single source of truth. Reads the canonical universe.csv (or the
    newest CSV in the folder), parses the Symbol column, and writes universe.txt.
    Runs on every pipeline startup so a fresh/ephemeral container always reflects
    what's in Drive. Returns True if a restore happened.
    """
    try:
        service, folder_id = _drive_service()
        if not service:
            return False
        f = _active_universe_file(service, folder_id)
        if not f:
            return False
        content = service.files().get_media(fileId=f["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        txt = _csv_to_universe_text(content)
        if txt is None:  # not a Symbol-column CSV — treat as a plain ticker list
            txt = content if content.strip() else None
        if txt is None:
            return False
        DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_UNIVERSE_FILE.write_text(txt, encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False


def get_drive_universe_status() -> dict | None:
    """Metadata for the active universe file in Drive: {name, modified, count}.

    None when Drive isn't configured or the folder has no CSV. Downloads the file
    to count tickers, so callers should cache the result.
    """
    try:
        service, folder_id = _drive_service()
        if not service:
            return None
        f = _active_universe_file(service, folder_id)
        if not f:
            return None
        content = service.files().get_media(fileId=f["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        txt = _csv_to_universe_text(content) or ""
        count = len([ln for ln in txt.splitlines() if ln and not ln.startswith("#")])
        return {"name": f.get("name"), "modified": f.get("modifiedTime"), "count": count}
    except Exception:  # noqa: BLE001
        return None
