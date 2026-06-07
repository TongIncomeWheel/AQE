"""Google Drive uploader — the REST write path for AQE.

Both local and cloud runs publish the export to one pinned Google Drive folder
(`DEFAULT_FOLDER_ID`, override with `GDRIVE_FOLDER_ID`) via this REST path.
There is no local Drive-mount write; `drive_sync.py` keeps only a working copy
in `output/`.

**Auth model:** personal OAuth 2.0 with refresh token. The user runs
`scripts/setup_gdrive_oauth.py` ONCE on their PC to capture a refresh token,
then pastes three values into Hugging Face Space secrets:

    GOOGLE_OAUTH_CLIENT_ID         -- OAuth Client ID from GCP
    GOOGLE_OAUTH_CLIENT_SECRET     -- OAuth Client Secret from GCP
    GOOGLE_OAUTH_REFRESH_TOKEN     -- refresh token from the consent flow

The target folder is pinned in code (`DEFAULT_FOLDER_ID`), so no folder env var
is required. Optional overrides:

    GDRIVE_FOLDER_ID               -- a different Drive folder ID to write to
                                       OR
    GDRIVE_FOLDER_PATH             -- a forward-slash path like
                                       "Trading Strategy/AQE" -- resolved to a
                                       folder ID at runtime (only used when no
                                       folder ID is in effect).

Import safety: the module imports without google-api-python-client installed.
`upload_or_replace()` simply returns `{"ok": False, "reason": "not configured"}`
when secrets or libraries are missing, so callers can wire it unconditionally.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

# Defer google imports so module is import-safe everywhere
_GOOGLE_LIBS_OK = False
try:
    from google.auth.transport.requests import Request                          # noqa: F401
    from google.oauth2.credentials import Credentials                           # noqa: F401
    from googleapiclient.discovery import build                                 # noqa: F401
    from googleapiclient.http import MediaInMemoryUpload                        # noqa: F401
    _GOOGLE_LIBS_OK = True
except ImportError:
    pass


# Full Drive scope — required to write into a pre-existing folder (created in
# the Drive UI) by ID. `drive.file` only grants access to app-created files and
# cannot see the linked folder below. Changing this requires re-running
# scripts/setup_gdrive_oauth.py to mint a new refresh token under the new scope.
SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# The pinned destination folder (your shared Drive link). Override per-deploy
# with the GDRIVE_FOLDER_ID env var / HF secret if you ever move it.
#   https://drive.google.com/drive/folders/1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger
DEFAULT_FOLDER_ID = "1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger"


@dataclass
class DriveConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    folder_id: str | None = None
    folder_path: str | None = None

    @classmethod
    def from_env(cls) -> "DriveConfig | None":
        cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        csec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        rtok = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")
        # Folder is pinned by default; env var overrides if set.
        fid = os.environ.get("GDRIVE_FOLDER_ID") or DEFAULT_FOLDER_ID
        fpath = os.environ.get("GDRIVE_FOLDER_PATH")
        # Only the OAuth credentials are mandatory — the folder always resolves.
        if not (cid and csec and rtok):
            return None
        return cls(client_id=cid, client_secret=csec, refresh_token=rtok,
                   folder_id=fid, folder_path=fpath)


def is_configured() -> bool:
    """True iff env has the OAuth triple + a folder target, and libs are present."""
    return _GOOGLE_LIBS_OK and DriveConfig.from_env() is not None


def is_libs_installed() -> bool:
    """True iff google-api-python-client is importable."""
    return _GOOGLE_LIBS_OK


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_or_replace(filename: str, content: str | bytes,
                      mime: str = "application/json",
                      folder_path: str | None = None) -> dict[str, Any]:
    """Upload `content` to a Drive folder as `filename`.

    If a file with that name already exists in the folder, REPLACE it in
    place (same file ID, so downstream consumers don't get a broken link
    on every export).

    folder_path -- optional override. When provided, resolves this path
        (e.g. "Trading Strategy/SRM Daily") instead of the env-configured
        GDRIVE_FOLDER_PATH. This lets a single OAuth config push files to
        multiple sibling Drive folders.

    Returns a dict:
      {"ok": True, "file_id": "...", "filename": "...", "replaced": bool}
      {"ok": False, "reason": "<short message>"}

    Never raises. The caller is the daily orchestrator, which has to keep
    going even if Drive is broken.
    """
    if not _GOOGLE_LIBS_OK:
        return {"ok": False, "reason": "google-api-python-client not installed"}
    cfg = DriveConfig.from_env()
    if cfg is None:
        return {"ok": False, "reason": "OAuth env vars not set"}

    try:
        service = _build_service(cfg)

        # Resolve folder — override path wins, then configured path/id
        if folder_path:
            override_cfg = DriveConfig(
                client_id=cfg.client_id, client_secret=cfg.client_secret,
                refresh_token=cfg.refresh_token,
                folder_id=None, folder_path=folder_path,
            )
            folder_id = _resolve_folder_id(service, override_cfg)
            if not folder_id:
                return {"ok": False, "reason":
                        f"Drive folder not found (path={folder_path!r})"}
        else:
            folder_id = _resolve_folder_id(service, cfg)
            if not folder_id:
                return {"ok": False, "reason":
                        f"Drive folder not found (path={cfg.folder_path!r})"}

        existing = _find_file(service, folder_id, filename)
        body = content if isinstance(content, (bytes, bytearray)) else content.encode("utf-8")
        media = MediaInMemoryUpload(body, mimetype=mime, resumable=False)

        if existing:
            file_id = existing["id"]
            service.files().update(fileId=file_id, media_body=media).execute()
            return {"ok": True, "file_id": file_id, "filename": filename,
                    "replaced": True, "folder_id": folder_id}
        else:
            metadata = {"name": filename, "parents": [folder_id]}
            created = service.files().create(
                body=metadata, media_body=media, fields="id"
            ).execute()
            return {"ok": True, "file_id": created.get("id"),
                    "filename": filename, "replaced": False,
                    "folder_id": folder_id}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def test_credentials() -> dict[str, Any]:
    """Validate that the OAuth refresh token can mint an access token.

    Used by the cloud diagnostic panel to give a green/red on Drive sync
    without actually uploading anything.
    """
    if not _GOOGLE_LIBS_OK:
        return {"ok": False, "reason": "google-api-python-client not installed"}
    cfg = DriveConfig.from_env()
    if cfg is None:
        return {"ok": False, "reason": "OAuth env vars not set"}
    try:
        service = _build_service(cfg)
        # Cheapest possible authenticated call -- "about" returns the auth'd user
        about = service.about().get(fields="user(emailAddress,displayName)").execute()
        return {"ok": True, "user": about.get("user", {}).get("emailAddress", "?")}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _build_service(cfg: DriveConfig):
    creds = Credentials(
        token=None,                       # refreshed on first use
        refresh_token=cfg.refresh_token,
        token_uri=TOKEN_URI,
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_file(service, folder_id: str, filename: str) -> dict | None:
    """Find a file by exact name inside a folder. None if absent."""
    # Escape single quotes per Drive query syntax
    name_q = filename.replace("'", "\\'")
    q = (f"name = '{name_q}' and '{folder_id}' in parents and trashed = false")
    res = service.files().list(q=q, fields="files(id,name)").execute()
    files = res.get("files") or []
    return files[0] if files else None


def _resolve_folder_id(service, cfg: DriveConfig) -> str | None:
    """Resolve cfg.folder_id, OR walk cfg.folder_path to find the leaf folder ID."""
    if cfg.folder_id:
        # Validate it exists + is a folder
        try:
            info = service.files().get(fileId=cfg.folder_id,
                                       fields="id,name,mimeType").execute()
            if info.get("mimeType") == "application/vnd.google-apps.folder":
                return cfg.folder_id
        except Exception:                                                       # noqa: BLE001
            return None
        return None

    # Walk the path. Forward-slash separated. Handles 'Trading Strategy/AQE'
    # and 'My Drive/Trading Strategy/AQE' (we strip 'My Drive' prefix).
    parts = [p for p in (cfg.folder_path or "").replace("\\", "/").split("/") if p]
    if parts and parts[0].lower() in ("my drive", "drive"):
        parts = parts[1:]
    parent = "root"
    for name in parts:
        name_q = name.replace("'", "\\'")
        q = (f"name = '{name_q}' and '{parent}' in parents "
             f"and mimeType = 'application/vnd.google-apps.folder' "
             f"and trashed = false")
        res = service.files().list(q=q, fields="files(id,name)").execute()
        files = res.get("files") or []
        if not files:
            return None
        parent = files[0]["id"]
    return parent if parent != "root" else None


if __name__ == "__main__":
    # CLI diagnostic:
    #   python -m src.data.gdrive_uploader
    print("libs installed :", _GOOGLE_LIBS_OK)
    print("configured     :", is_configured())
    if is_configured():
        print("test creds    :", json.dumps(test_credentials(), indent=2))
