"""Drive folder cleanup — keep exactly one live file in a Cowork-fed folder.

Cowork (the daily-report writer) is not authorised to overwrite or delete
files in its destination Drive folder, so every write lands as a new file.
Over time the folder accumulates duplicates and a downstream reader that
doesn't carefully pick the latest-modified file can grab a stale one.

`archive_extra_files()` is the fix: it looks at a folder's direct (non-trashed,
non-folder) children, keeps the most-recently-modified one in place, and moves
every other one into a `Legacy/` subfolder of that same folder. Nothing is
ever deleted — Cowork's write history stays fully recoverable, it's just out
of the way of anything reading "the current file" from the parent folder.

Reuses the OAuth session already configured for AQE's Drive write path
(`gdrive_uploader`) — no separate credentials needed. Best-effort throughout;
never raises, since this runs unattended on a daily GitHub Actions schedule.
"""

from __future__ import annotations

from typing import Any

LEGACY_SUBFOLDER_NAME = "Legacy"


def archive_extra_files(
    folder_id: str,
    legacy_subfolder_name: str = LEGACY_SUBFOLDER_NAME,
) -> dict[str, Any]:
    """Keep the newest file in `folder_id`, move the rest into a Legacy subfolder.

    Returns:
      {"ok": True, "kept": "<filename>" | None, "archived": ["<filename>", ...]}
      {"ok": False, "reason": "<short message>"}
    """
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return {"ok": False, "reason": "Drive OAuth not configured"}
        cfg = gdrive_uploader.DriveConfig.from_env()
        if cfg is None:
            return {"ok": False, "reason": "Drive OAuth not configured"}
        service = gdrive_uploader._build_service(cfg)

        q = f"'{folder_id}' in parents and trashed = false"
        res = service.files().list(
            q=q, orderBy="modifiedTime desc",
            fields="files(id,name,modifiedTime,mimeType)", pageSize=100,
        ).execute()
        entries = res.get("files") or []
        files = [f for f in entries if f.get("mimeType") != "application/vnd.google-apps.folder"]

        if len(files) <= 1:
            return {"ok": True, "kept": files[0]["name"] if files else None, "archived": []}

        keep, extras = files[0], files[1:]

        legacy_id = _find_or_create_subfolder(service, folder_id, legacy_subfolder_name)
        if not legacy_id:
            return {"ok": False, "reason": f"could not find/create '{legacy_subfolder_name}' subfolder"}

        archived: list[str] = []
        for f in extras:
            try:
                service.files().update(
                    fileId=f["id"], addParents=legacy_id, removeParents=folder_id,
                    fields="id,parents",
                ).execute()
                archived.append(f["name"])
            except Exception:  # noqa: BLE001
                continue

        return {"ok": True, "kept": keep["name"], "archived": archived}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def _find_or_create_subfolder(service, parent_id: str, name: str) -> str | None:
    """Find a folder named `name` directly under `parent_id`, creating it if absent."""
    name_q = name.replace("'", "\\'")
    q = (f"name = '{name_q}' and '{parent_id}' in parents "
         f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    res = service.files().list(q=q, fields="files(id,name)").execute()
    found = res.get("files") or []
    if found:
        return found[0]["id"]
    try:
        created = service.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                  "parents": [parent_id]},
            fields="id",
        ).execute()
        return created.get("id")
    except Exception:  # noqa: BLE001
        return None
