"""Daily Persist — snapshot the runtime AQE state to Drive and restore it.

HF Spaces have an ephemeral filesystem: every rebuild/restart wipes the runtime
parquets (`panel_daily`, `scores_daily`, …) and outputs, so the app would force a
full ~minutes-long pipeline re-run (burning FMP quota) just to be usable again.

This module bundles those files into ONE zip (`aqe_state_snapshot.zip`) on the
pinned AQE Drive folder so a restart can restore the last good run in seconds:

    save_snapshot()  — zip the present data/ + output/ artifacts → Drive (+ meta)
    load_snapshot()  — pull the zip from Drive → extract into DATA_DIR/OUTPUT_DIR
    snapshot_status() — the meta of the last saved snapshot (for the UI)

Everything degrades gracefully (Drive down / file missing → {ok: False, reason}).
The export JSON itself is still published separately by drive_sync; this snapshot
is the heavier price/score state that the export alone can't rebuild.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.paths import DATA_DIR, OUTPUT_DIR

SNAPSHOT_FILENAME = "aqe_state_snapshot.zip"
SNAPSHOT_META = "aqe_snapshot_meta.json"
_SGT = ZoneInfo("Asia/Singapore")


def _members() -> list[tuple]:
    """(absolute path, arcname) for every artifact worth persisting."""
    data_files = [
        "panel_daily.parquet", "panel_weekly.parquet", "spy_daily.parquet",
        "scores_daily.parquet", "sector_map.json", "active_recipe.json", "aqe.db",
    ]
    out_files = [
        "shortlist.json", "aqe_daily_export.json", "held_positions.json",
    ]
    items = [(DATA_DIR / f, f"data/{f}") for f in data_files]
    items += [(OUTPUT_DIR / f, f"output/{f}") for f in out_files]
    return items


def build_snapshot_bytes() -> dict:
    """Zip the present runtime artifacts in memory — NO Drive involved.

    Returns {ok, blob, files, bytes, saved_at} or {ok: False, reason}. This is
    the Drive-independent core: used both by save_snapshot() (which uploads the
    blob) and by the UI's local-PC download fallback (which serves the blob
    through the browser when Drive auth is broken).
    """
    try:
        buf = io.BytesIO()
        saved = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for path, arc in _members():
                if path.exists():
                    z.write(path, arc)
                    saved.append(arc)
        if not saved:
            return {"ok": False, "reason": "no runtime files to save (run the pipeline first)"}
        blob = buf.getvalue()
        return {
            "ok": True,
            "blob": blob,
            "saved_at": datetime.now(_SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "files": saved,
            "bytes": len(blob),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def restore_snapshot_bytes(raw: bytes) -> dict:
    """Extract a snapshot zip (given as bytes) into DATA_DIR/OUTPUT_DIR.

    Drive-independent — used by load_snapshot() (after a Drive download) AND by
    the UI's local-PC upload fallback (a zip the user uploads from disk).
    """
    try:
        if not raw:
            return {"ok": False, "reason": "empty file"}
        extracted = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for arc in z.namelist():
                if arc.startswith("data/"):
                    target = DATA_DIR / arc[len("data/"):]
                elif arc.startswith("output/"):
                    target = OUTPUT_DIR / arc[len("output/"):]
                else:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(arc))
                extracted.append(arc)
        if not extracted:
            return {"ok": False, "reason": "no data/ or output/ members in the zip"}
        return {"ok": True, "files": extracted, "count": len(extracted)}
    except zipfile.BadZipFile:
        return {"ok": False, "reason": "not a valid snapshot .zip"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def save_snapshot() -> dict:
    """Zip the present runtime artifacts and upload to the AQE Drive folder."""
    built = build_snapshot_bytes()
    if not built.get("ok"):
        return built
    blob = built["blob"]
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return {"ok": False, "reason": "Drive not configured"}

        up = gdrive_uploader.upload_or_replace(
            SNAPSHOT_FILENAME, blob, mime="application/zip")
        if not up.get("ok"):
            return {"ok": False, "reason": f"upload failed: {up.get('reason')}"}

        meta = {
            "saved_at": built["saved_at"],
            "files": built["files"],
            "bytes": built["bytes"],
        }
        # Best-effort export timestamp for context.
        try:
            exp = OUTPUT_DIR / "aqe_daily_export.json"
            if exp.exists():
                meta["export_date"] = json.loads(exp.read_text())\
                    .get("exported_at")
        except Exception:  # noqa: BLE001
            pass
        gdrive_uploader.upload_or_replace(
            SNAPSHOT_META, json.dumps(meta, indent=2), mime="application/json")

        return {"ok": True, **meta}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def load_snapshot() -> dict:
    """Download the snapshot zip from Drive and extract into DATA_DIR/OUTPUT_DIR."""
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return {"ok": False, "reason": "Drive not configured"}

        raw = gdrive_uploader.download_bytes(SNAPSHOT_FILENAME)
        if not raw:
            return {"ok": False, "reason": "no snapshot on Drive yet (Save one first)"}

        res = restore_snapshot_bytes(raw)
        if res.get("ok"):
            meta = snapshot_status() or {}
            res["saved_at"] = meta.get("saved_at")
        return res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def snapshot_status() -> dict | None:
    """Meta of the last saved snapshot ({saved_at, files, bytes}). None if none."""
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return None
        txt = gdrive_uploader.download_text(SNAPSHOT_META)
        return json.loads(txt) if txt else None
    except Exception:  # noqa: BLE001
        return None
