"""GitHub Actions entrypoint for the daily run.

2026-09-06 PM decision: this is now the primary, ONLY automatic trigger for
the daily pipeline -- fired externally via workflow_dispatch on
.github/workflows/daily-run.yml (a Claude-scheduled Routine dispatches it
each morning alongside the PTJ command; see that workflow file for the full
history). The in-app HF scheduler no longer auto-fires the pipeline itself
(src/ui/daily_job.py), and GitHub's own `schedule:` cron was removed from
that workflow -- it was firing this workflow 4-5+ hours late most days, a
documented platform characteristic, not something this script could fix.

Still dedups against an already-successful run today (e.g. via the AQE UX's
own "Bootstrap + run daily pipeline" manual button) using the same marker
logic the pipeline function itself writes, so triggering this twice in one
day -- or on top of a manual run -- is a safe no-op, not a double-run.

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
            print(f"[backstop] {stamp}: today already ran successfully "
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
