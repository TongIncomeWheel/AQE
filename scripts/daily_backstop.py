"""GitHub Actions backstop for the daily run.

The HF Space runs the pipeline in-app at 08:30 SGT (Tue–Sat). This backstop runs
on GitHub's schedulers ~1h later and executes the pipeline ONLY if the Space
hasn't already done today's run — covering days the Space was asleep or down.

It reuses the same logic + marker as the in-app job, so the Scanner status bar
stays accurate regardless of which path actually ran.

Run:  python -m scripts.daily_backstop
Needs env: FMP_API_KEY, GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN
(the Drive folders are pinned in code).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.daily_job import (  # noqa: E402
    _is_run_day,
    _run_pipeline_and_record,
    last_run_status,
)


def main() -> int:
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    stamp = now.strftime("%Y-%m-%d %a %H:%M SGT")
    force = os.environ.get("AQE_FORCE", "").strip().lower() == "true"

    if force:
        print(f"[backstop] {stamp}: FORCE run requested — ignoring day/already-ran checks.")
    else:
        if not _is_run_day(now.date()):
            print(f"[backstop] {stamp}: Sun/Mon — US market was closed, skipping.")
            return 0
        lr = last_run_status()
        if (lr and lr.get("date_sgt") == now.date().isoformat()
                and lr.get("status") == "success"):
            print(f"[backstop] {stamp}: today already ran via the Space "
                  f"({lr.get('finished_at')}) — skipping.")
            return 0
        print(f"[backstop] {stamp}: no successful run today — running pipeline now.")
    marker = _run_pipeline_and_record(now)
    print(f"[backstop] result: status={marker.get('status')} "
          f"picks={marker.get('top_picks')} exported_at={marker.get('exported_at')}")
    if marker.get("status") != "success":
        print(f"[backstop] tail:\n{marker.get('tail') or marker.get('reason') or ''}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
