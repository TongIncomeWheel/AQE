"""Daily PTJ folder cleanup — keeps exactly one live file for AQE to read.

Cowork writes the daily `aegis_trade_journal_*` JSON to the PTJ Drive folder
but isn't authorised to overwrite or delete the previous day's file, so the
folder accumulates one file per write. `ptj.py` already defends against this
by always reading the latest-modified file, but this script proactively tidies
the folder so nothing downstream (human or app) can grab a stale one by
mistake: it moves every file except the newest into a `Legacy/` subfolder.

Run:  python -m scripts.cleanup_ptj_folder
Needs env: GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN (the PTJ folder ID is
pinned in code, override with GDRIVE_PTJ_FOLDER_ID).

Scheduled via .github/workflows/ptj-cleanup.yml shortly before the daily
pipeline run, so the pipeline always sees a tidy folder.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.drive_folder_cleanup import archive_extra_files  # noqa: E402
from src.data.ptj import PTJ_FOLDER_ID  # noqa: E402


def main() -> int:
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    stamp = now.strftime("%Y-%m-%d %a %H:%M SGT")

    result = archive_extra_files(PTJ_FOLDER_ID)
    if not result.get("ok"):
        print(f"[ptj-cleanup] {stamp}: FAILED — {result.get('reason')}")
        return 1

    kept = result.get("kept")
    archived = result.get("archived") or []
    if not archived:
        print(f"[ptj-cleanup] {stamp}: nothing to do — folder already holds a single file ({kept}).")
    else:
        print(f"[ptj-cleanup] {stamp}: kept '{kept}', archived {len(archived)} older file(s) to Legacy/:")
        for name in archived:
            print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
