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
        # MA Proximity Scanner state — persisted so the WEEKLY standalone scan stays
        # incremental across HF recycles (else it re-pulls ~2000 tickers each time).
        "ma_panel.parquet", "ma_scan.parquet", "ma_universe.json",
        # The universe itself. It is a DYNAMIC daily screen (~933 names), so a
        # recycle between the 06:00 rebuild and the 08:30 run would otherwise
        # leave the pipeline with no list at all. Drive restore covers this too;
        # this is the belt to that braces.
        "universe.txt",
        # Crown's COT history. The CFTC publishes one snapshot a week, so this
        # file IS the percentile window — without it a recycle leaves every
        # market reading "no history" instead of "crowded long", which is a
        # different answer wearing the same shape.
        "crown_cot.parquet",
        # Crown's volatility complex from Cboe (VIX / VIXEQ / DSPX / COR1M /
        # VIX3M / VIX9D). Cheap to re-pull, but caching it means the page and
        # the percentile windows are live the moment a container comes back.
        "crown_cboe.parquet",
    ]
    # QS's memory (recipe_hits trail + regime series) rides inside aqe.db above,
    # which is why that file is load-bearing rather than incidental: without it
    # qs_persist reads 0 for every name after a recycle and the whole book
    # re-prices downward with nothing in the output looking wrong.
    #
    # The frozen QS config (data/qs/*.json) is deliberately NOT here — it ships
    # in the Docker image with the repo, so it is restored by a rebuild, not by
    # a snapshot. Snapshotting it would let a stale copy silently outlive a
    # re-freeze.
    out_files = [
        "shortlist.json", "aqe_daily_export.json", "held_positions.json",
        # QS's standalone artifact — same numbers as the export's qs blocks.
        "qs_daily.json",
        # The Crown macro read, so the page renders instantly after a recycle.
        "crown_macro.json",
        # The macro scenario read (Crown x Macro Weather merge point).
        "macro_scenarios.json",
        # The Crown reading copy — the plain-English-first file the committee
        # and the AIC actually open. Published to Drive too, but persisted so a
        # recycle does not leave the page without it.
        "aqe_crown_macro.json",
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


def restore_snapshot_bytes(raw: bytes, only: list[str] | None = None) -> dict:
    """Extract a snapshot zip (given as bytes) into DATA_DIR/OUTPUT_DIR.

    Drive-independent — used by load_snapshot() (after a Drive download) AND by
    the UI's local-PC upload fallback (a zip the user uploads from disk).

    `only` restricts the restore to member basenames (e.g. ["ma_panel.parquet"]).
    That matters because a snapshot restore OVERWRITES: a caller that wants one
    file back would otherwise also roll panel_daily/scores_daily/universe.txt
    back to whenever the zip was written, silently discarding bars pulled since
    and forcing a re-pull nobody asked for. Restoring everything is right after
    a container recycle (there is nothing to lose) and wrong mid-session.
    """
    try:
        if not raw:
            return {"ok": False, "reason": "empty file"}
        wanted = set(only) if only else None
        extracted, skipped = [], []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for arc in z.namelist():
                if arc.startswith("data/"):
                    target = DATA_DIR / arc[len("data/"):]
                elif arc.startswith("output/"):
                    target = OUTPUT_DIR / arc[len("output/"):]
                else:
                    continue
                if wanted is not None and target.name not in wanted:
                    skipped.append(arc)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(arc))
                extracted.append(arc)
        if not extracted:
            reason = ("no member matched " + ", ".join(sorted(wanted))
                      if wanted else "no data/ or output/ members in the zip")
            return {"ok": False, "reason": reason}
        return {"ok": True, "files": extracted, "count": len(extracted),
                "skipped": skipped}
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


def load_snapshot(only: list[str] | None = None) -> dict:
    """Download the snapshot zip from Drive and extract into DATA_DIR/OUTPUT_DIR.

    Pass `only` to restore specific members (see restore_snapshot_bytes) when
    the caller wants one artifact back and must NOT roll everything else to
    whenever the zip was written.
    """
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return {"ok": False, "reason": "Drive not configured"}

        raw = gdrive_uploader.download_bytes(SNAPSHOT_FILENAME)
        if not raw:
            return {"ok": False, "reason": "no snapshot on Drive yet (Save one first)"}

        res = restore_snapshot_bytes(raw, only=only)
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
