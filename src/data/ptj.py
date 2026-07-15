"""Pre-Trade Journal (PTJ) reader — the daily held-positions feed from Drive.

The PM/AIC writes an `aegis_trade_journal_*` JSON to a dedicated Drive folder
each day. Runtime hiccups sometimes leave duplicates, so AQE always reads the
**latest-modified** file in that folder (zero ambiguity). We extract the OPEN
(held) positions and cache them locally so the engine can flag held names and
the UI/Charts can show entry vs current price.

Folder: GDRIVE_PTJ_FOLDER_ID (default = the AEGIS Trade Journal Drive folder).
Failures degrade to the local cache, then to empty — never raise.
"""

from __future__ import annotations

import json
import os

from src.data.paths import OUTPUT_DIR

PTJ_FOLDER_ID = (
    os.environ.get("GDRIVE_PTJ_FOLDER_ID")
    or "15PR74ws_kTXTqCcEfRGga_jjHrMvbCEM"
)
PTJ_CACHE = OUTPUT_DIR / "held_positions.json"


def fetch_latest_ptj() -> dict | None:
    """Download + parse the most-recently-modified file in the PTJ folder."""
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return None
        cfg = gdrive_uploader.DriveConfig.from_env()
        if cfg is None:
            return None
        service = gdrive_uploader._build_service(cfg)
        q = f"'{PTJ_FOLDER_ID}' in parents and trashed = false"
        res = service.files().list(
            q=q, orderBy="modifiedTime desc",
            fields="files(id,name,modifiedTime,mimeType)", pageSize=10,
        ).execute()
        files = [f for f in (res.get("files") or [])
                 if f.get("mimeType") != "application/vnd.google-apps.folder"]
        if not files:
            return None
        latest = files[0]  # newest by modifiedTime
        content = service.files().get_media(fileId=latest["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        data = json.loads(content)
        data["_ptj_file"] = latest.get("name")
        data["_ptj_modified"] = latest.get("modifiedTime")
        return data
    except Exception:  # noqa: BLE001
        return None


def refresh_held_positions() -> list[dict]:
    """Fetch the latest PTJ, extract held positions, cache locally. Returns them.

    Falls back to the local cache when Drive is unavailable — but NEVER lets a
    failed live fetch silently masquerade as a genuine flat book: the cache
    always carries a `status` ("live" | "cache_fallback") so downstream
    readers (the export, the Scanner UI) can tell "PTJ fetch failed this run"
    apart from "the book is actually empty". Real-money system — a silent
    empty is worse than a stale-but-labeled one.
    """
    ptj = fetch_latest_ptj()
    if not ptj:
        prior = load_ptj_cache()
        prior["status"] = "cache_fallback"
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            PTJ_CACHE.write_text(json.dumps(prior, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return prior.get("positions") or []
    held = ptj.get("open_positions") or []
    cache = {
        "source_file": ptj.get("_ptj_file"),
        "modified": ptj.get("_ptj_modified"),
        "snapshot": ptj.get("snapshot"),
        "positions": held,
        "options": ptj.get("options") or [],
        "status": "live",
    }
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        PTJ_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return held


def load_ptj_cache() -> dict:
    """The cached PTJ snapshot ({source_file, modified, positions, options, status})."""
    try:
        if PTJ_CACHE.exists():
            return json.loads(PTJ_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {}


def load_held_positions() -> list[dict]:
    """Held (open) positions from the local cache — no Drive call."""
    return load_ptj_cache().get("positions") or []


def ptj_status() -> str:
    """'live' (this run fetched fresh from Drive), 'cache_fallback' (Drive fetch
    failed/unreachable and we fell back to whatever was last cached — possibly
    stale or, on a freshly-restarted container, empty), or 'unknown' (no cache
    file has ever been written)."""
    cache = load_ptj_cache()
    return cache.get("status") or ("unknown" if not cache else "cache_fallback")
