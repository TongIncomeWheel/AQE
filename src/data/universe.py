"""Universe management — load, screen, and persist the scan ticker list.

The universe is auto-refreshed daily at 06:00 SGT by `build_universe()` — an
FMP-driven screen (market cap > $2B, price > 20-day SMA, price > 50-day SMA,
10-day average volume > 1.5M). The result is written to the local
`universe.txt` AND uploaded as the canonical CSV to a dedicated Google Drive
folder (`UNIVERSE_FOLDER_ID`), so it persists across container restarts.

On pipeline startup `restore_universe_from_drive()` overwrites the local
`universe.txt` from that folder (Drive is source of truth between refreshes).

The old `refresh_universe()` (screener-only, no SMA/volume filters) is kept for
manual / legacy use. It previously ballooned the list to ~1800 — the new
`build_universe()` is tighter by design.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from src.data.paths import DATA_DIR, PROJECT_ROOT

DEFAULT_UNIVERSE_FILE = DATA_DIR / "universe.txt"
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

# --- Automated universe screening (PM ruling, 27 Jun 2026) ---
# The daily pipeline scans only this filtered set. Refreshed at 06:00 SGT
# (before the 08:30 pipeline run) by the in-app scheduler.
SCREEN_MCAP = 2_000_000_000          # $2B minimum market cap
SCREEN_AVG_VOL_10D = 1_500_000       # 1.5M shares/day (10-day average)
SCREEN_LOOKBACK_DAYS = 90            # calendar days fetched (covers ~55 trading days)


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


def build_universe(dry_run: bool = False) -> dict:
    """Screen US equities to produce the AQE scan universe.

    Criteria:
      1. Market cap > $2B  (FMP screener)
      2. Price > 20-day SMA  (computed from bars)
      3. Price > 50-day SMA  (computed from bars)
      4. 10-day average volume > 1.5M shares/day  (computed from bars)

    Flow: FMP screener → fetch 55 bars per candidate → filter on SMA20/SMA50/
    volume → write universe.txt + upload CSV to Drive.  ~300-500 API calls,
    takes 2-4 minutes at ~250 calls/min (FMP Starter).

    Returns a summary dict with status, counts, and any errors.
    """
    from datetime import timedelta

    from src.data.fmp_client import FMPClient, FMPError

    client = FMPClient()
    today = date.today()
    from_dt = today - timedelta(days=SCREEN_LOOKBACK_DAYS)

    # ── FMP screener → broad candidates ──────────────────────────────────
    print(f"[universe] Screening: mcap > ${SCREEN_MCAP / 1e9:.0f}B, "
          f"US exchanges ({', '.join(UNIVERSE_EXCHANGES)})...")
    try:
        raw = client.get_screener(
            min_mcap=SCREEN_MCAP,
            min_price=5.0,
            min_volume=100_000,            # generous pre-filter; 10d avg checked from bars
            exchanges=UNIVERSE_EXCHANGES,
            limit=5000,
        )
    except FMPError as exc:
        return {"status": "error", "reason": f"screener failed: {exc}"}

    print(f"[universe] Screener raw response: {len(raw)} items")

    candidates = [
        r["symbol"].upper().strip()
        for r in raw
        if r.get("symbol")
        and not any(r["symbol"].endswith(s) for s in EXCLUDED_SUFFIXES)
        and "." not in r["symbol"]
        and " " not in r["symbol"]
    ]
    print(f"[universe] After symbol cleanup: {len(candidates)} candidates")
    if not candidates:
        sample = [r.get("symbol", r) for r in raw[:5]] if raw else "empty"
        return {"status": "error",
                "reason": f"screener returned {len(raw)} items but 0 valid symbols. "
                          f"Sample: {sample}"}

    # ── Fetch bars → compute SMA20, SMA50, 10-day avg volume ─────────────
    passed: list[str] = []
    skipped_bars = 0
    skipped_sma = 0
    skipped_vol = 0
    errors: list[str] = []
    for i, tk in enumerate(candidates):
        if (i + 1) % 100 == 0:
            print(f"[universe] Checking {i + 1}/{len(candidates)} "
                  f"({len(passed)} passed so far)...")
        try:
            bars = client.get_daily_bars(tk, from_date=from_dt, to_date=today)
            if bars is None or bars.empty or len(bars) < 50:
                skipped_bars += 1
                continue
            close = bars["close"].astype(float)
            volume = bars["volume"].astype(float)

            price = float(close.iloc[-1])
            sma20 = float(close.tail(20).mean())
            sma50 = float(close.tail(50).mean())
            avg_vol = float(volume.tail(10).mean())

            if not (price > sma20 and price > sma50):
                skipped_sma += 1
                continue
            if avg_vol < SCREEN_AVG_VOL_10D:
                skipped_vol += 1
                continue
            passed.append(tk)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tk}: {exc}")

    print(f"[universe] {len(passed)} passed | "
          f"{skipped_bars} too few bars | "
          f"{skipped_sma} below SMA20/50 | "
          f"{skipped_vol} low volume | "
          f"{len(errors)} errors")

    if not passed:
        return {"status": "error",
                "reason": f"0 tickers passed from {len(candidates)} candidates "
                          f"(bars={skipped_bars}, sma={skipped_sma}, vol={skipped_vol}, "
                          f"err={len(errors)})"}

    # ── Compare with existing ─────────────────────────────────────────────
    try:
        existing = set(load_universe(include_benchmark=False))
    except Exception:  # noqa: BLE001
        existing = set()
    new_set = set(passed)
    added = sorted(new_set - existing)
    removed = sorted(existing - new_set)
    kept = sorted(existing & new_set)

    if dry_run:
        return {"status": "dry_run", "total": len(passed),
                "added": len(added), "removed": len(removed), "kept": len(kept),
                "tickers": sorted(passed), "errors": errors[:20]}

    # ── Write + upload ────────────────────────────────────────────────────
    final = sorted(passed)
    _write_universe(final)

    csv_text = "Symbol\n" + "\n".join(final) + "\n"
    drive_ok, drive_reason = False, "not attempted"
    try:
        result = upload_universe(csv_text.encode("utf-8"))
        drive_ok = result.get("drive_ok", False)
        drive_reason = result.get("drive_reason", "unknown")
    except Exception as exc:  # noqa: BLE001
        drive_reason = f"{type(exc).__name__}: {exc}"

    summary = {
        "status": "ok",
        "total": len(final),
        "added": len(added),
        "removed": len(removed),
        "kept": len(kept),
        "drive_ok": drive_ok,
        "drive_reason": drive_reason,
        "errors": errors[:20],
    }
    print(f"[universe] Done: {len(final)} tickers "
          f"(+{len(added)} / -{len(removed)} / ={len(kept)})"
          f" | Drive: {'ok' if drive_ok else drive_reason}")
    return summary


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
