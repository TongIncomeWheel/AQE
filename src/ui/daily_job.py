"""In-app daily scheduler — universe refresh + pipeline, each market morning.

Schedule (SGT, Tuesday–Saturday):
  06:00 — Universe refresh (FMP screener → mcap/$2B + SMA20/50 + volume)
  08:30 — Daily pipeline (pull → score → SRM → PTRS → Drive export)
Sunday and Monday (SGT) are skipped (US markets closed Sat/Sun).

How it works:
- A daemon thread (started once per process) checks the SGT clock every minute.
- On a run day, once the time is past 08:30 and the pipeline hasn't run today, it
  launches `python -m src.pipeline.daily_orchestrator` (full pull → score → SRM →
  PTRS → Drive export). The export lands in the AQE Drive folder.
- A "last run" marker (status, time, counts) is written locally AND to Drive so
  the in-app status bar survives container restarts and never double-runs a day.

Requirements:
- The container must be awake at 08:30 — keep it up with the UptimeRobot monitor
  (every ~30 min). This scheduler can't wake a sleeping container by itself.
- Active only on HF (SPACE_HOST set) unless AQE_ENABLE_SCHEDULER=1 forces it on.

Reliability note: an in-process scheduler is best-effort. For guaranteed runs
regardless of Space state, an external cron (e.g. GitHub Actions) running the
orchestrator would be more robust — but this keeps everything in the app per
the current design.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")
RUN_HOUR = 8
RUN_MIN = 30
# Catch late wake-ups: still run if the Space only came up after 08:30, up to noon.
WINDOW_END_HOUR = 12
# Python weekday(): Mon=0 .. Sun=6. Skip Sunday(6) and Monday(0).
SKIP_WEEKDAYS = {6, 0}

# Universe auto-refresh runs at 06:00 SGT — 2.5 hours before the pipeline.
UNIVERSE_HOUR = 6
UNIVERSE_MIN = 0
UNIVERSE_WINDOW_END_HOUR = 8        # catch late wake-ups up to 08:00

MARKER_FILENAME = "aqe_last_run.json"

_started = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Schedule decision (pure — unit-testable)
# ---------------------------------------------------------------------------

def _is_run_day(d) -> bool:
    return d.weekday() not in SKIP_WEEKDAYS


def _should_run(now: datetime, last_run_date_iso: str | None) -> bool:
    """True if it's a run day, past 08:30 (within window), not already run today."""
    if not _is_run_day(now.date()):
        return False
    if now.hour >= WINDOW_END_HOUR:
        return False
    if now.hour < RUN_HOUR or (now.hour == RUN_HOUR and now.minute < RUN_MIN):
        return False
    return last_run_date_iso != now.date().isoformat()


def _should_refresh_universe(now: datetime,
                             last_refresh_date_iso: str | None) -> bool:
    """True if it's a run day, past 06:00 (within window), not refreshed today."""
    if not _is_run_day(now.date()):
        return False
    if now.hour >= UNIVERSE_WINDOW_END_HOUR:
        return False
    if (now.hour < UNIVERSE_HOUR
            or (now.hour == UNIVERSE_HOUR and now.minute < UNIVERSE_MIN)):
        return False
    return last_refresh_date_iso != now.date().isoformat()


def next_run_hint() -> str:
    return "08:30 SGT, Tue–Sat"


# ---------------------------------------------------------------------------
# Marker persistence (local + Drive)
# ---------------------------------------------------------------------------

def _marker_path() -> Path:
    from src.data.paths import OUTPUT_DIR
    return OUTPUT_DIR / MARKER_FILENAME


def _write_marker(marker: dict) -> None:
    content = json.dumps(marker, indent=2)
    try:
        p = _marker_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    # Best-effort Drive copy so the status survives container restarts.
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(
                MARKER_FILENAME, content, mime="application/json",
            )
    except Exception:  # noqa: BLE001
        pass


def last_run_status() -> dict | None:
    """Read the last-run marker — local first, then Drive. None if never run."""
    try:
        p = _marker_path()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if not gdrive_uploader.is_configured():
            return None
        cfg = gdrive_uploader.DriveConfig.from_env()
        service = gdrive_uploader._build_service(cfg)
        folder_id = gdrive_uploader._resolve_folder_id(service, cfg)
        if not folder_id:
            return None
        found = gdrive_uploader._find_file(service, folder_id, MARKER_FILENAME)
        if not found:
            return None
        content = service.files().get_media(fileId=found["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return json.loads(content)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _run_pipeline_and_record(now: datetime) -> dict:
    """Run the daily orchestrator as a subprocess and record a marker."""
    from src.data.paths import PROJECT_ROOT, EXPORT_JSON

    started = now.strftime("%Y-%m-%d %H:%M:%S SGT")
    marker = {"date_sgt": now.date().isoformat(), "started_at": started}
    try:
        proc = subprocess.run(
            [sys.executable, "-u", "-m", "src.pipeline.daily_orchestrator"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=2400,
        )
        rc = proc.returncode
        picks = None
        exported_at = None
        try:
            if EXPORT_JSON.exists():
                exp = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
                picks = (exp.get("summary") or {}).get("top_picks_count")
                exported_at = exp.get("exported_at")
        except Exception:  # noqa: BLE001
            pass
        marker.update({
            "status": "success" if rc == 0 else "failed",
            "rc": rc,
            "finished_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "exported_at": exported_at,
            "top_picks": picks,
            "tail": "\n".join((proc.stdout or "").splitlines()[-8:]) if rc != 0 else "",
        })
    except Exception as exc:  # noqa: BLE001
        marker.update({
            "status": "failed",
            "finished_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "reason": f"{type(exc).__name__}: {exc}",
        })
    _write_marker(marker)
    return marker


def _refresh_universe_and_record(now: datetime) -> None:
    """Run the automated universe screener. Best-effort — failures are logged
    but never block the pipeline run at 08:30."""
    try:
        from src.data.universe import build_universe
        print(f"[daily-job] Universe refresh starting at "
              f"{now.strftime('%Y-%m-%d %H:%M SGT')}")
        result = build_universe()
        status = result.get("status", "unknown")
        total = result.get("total", 0)
        added = result.get("added", 0)
        removed = result.get("removed", 0)
        print(f"[daily-job] Universe refresh {status}: "
              f"{total} tickers (+{added}/-{removed})")
    except Exception as exc:  # noqa: BLE001
        print(f"[daily-job] Universe refresh failed: {exc}")


def _loop() -> None:
    # Seed last-run date from the persisted marker so a restart doesn't re-run.
    last = last_run_status()
    last_date = last.get("date_sgt") if last else None
    last_universe_date: str | None = None
    while True:
        try:
            now = datetime.now(SGT)
            # 06:00 SGT — universe refresh (before the pipeline)
            if _should_refresh_universe(now, last_universe_date):
                _refresh_universe_and_record(now)
                last_universe_date = now.date().isoformat()
            # 08:30 SGT — daily pipeline
            if _should_run(now, last_date):
                _run_pipeline_and_record(now)
                last_date = now.date().isoformat()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


def start_daily_job() -> bool:
    """Start the scheduler thread once per process. Returns True if it started."""
    global _started
    on_hf = bool(os.environ.get("SPACE_HOST") or os.environ.get("SPACE_ID"))
    forced = os.environ.get("AQE_ENABLE_SCHEDULER") == "1"
    if not (on_hf or forced):
        return False
    with _lock:
        if _started:
            return False
        threading.Thread(target=_loop, daemon=True, name="aqe-daily-job").start()
        _started = True
        return True
