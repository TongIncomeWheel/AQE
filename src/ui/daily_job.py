"""In-app daily scheduler — universe refresh + pipeline, each market morning.

Schedule (SGT, Tuesday–Saturday):
  05:30 — Universe CSP theta scan (Alpaca → options_scan.json to the CSP Drive folder)
  06:00 — Universe refresh (FMP screener → mcap/$2B + SMA20/50 + volume)
  08:30 — Daily pipeline (pull → score → SRM → candidates → publish)
Sunday and Monday (SGT) are skipped (US markets closed Sat/Sun).

The 05:30 CSP scan runs ~1h after the US close and 3h before the pipeline, so the
options sweep never contends with the AQE feed run.

How it works:
- A daemon thread (started once per process) checks the SGT clock every minute.
- On a run day, once the time is past 08:30 and the pipeline hasn't run today, it
  launches `python -m src.pipeline.daily_orchestrator` (full pull → score → SRM →
  candidates → publish). The export lands in aegis/output/ and on Drive.
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

# Universe CSP theta scan runs at 05:30 SGT — ~1h after the US close, BEFORE the
# 06:00 universe refresh + 08:30 pipeline, so the options sweep never contends with
# the AQE feed. Publishes options_scan.json to the dedicated CSP Drive folder.
CSP_SCAN_HOUR = 5
CSP_SCAN_MIN = 30
CSP_SCAN_WINDOW_END_HOUR = 8        # catch late wake-ups up to 08:00 (before AQE)

# Universe auto-refresh runs at 06:00 SGT — 2.5 hours before the pipeline.
UNIVERSE_HOUR = 6
UNIVERSE_MIN = 0
UNIVERSE_WINDOW_END_HOUR = 8        # catch late wake-ups up to 08:00

# MA Proximity Scanner — runs DAILY right after the 08:30 pipeline (in the run
# block below), against a persisted ma_panel so it stays incremental. Decoupled
# from the pipeline's critical path so a slow FMP pull can't fail the trading feed.

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


def _should_run_csp_scan(now: datetime, last_csp_date_iso: str | None) -> bool:
    """True if it's a run day, past 05:30 (within window), not scanned today."""
    if not _is_run_day(now.date()):
        return False
    if now.hour >= CSP_SCAN_WINDOW_END_HOUR:
        return False
    if (now.hour < CSP_SCAN_HOUR
            or (now.hour == CSP_SCAN_HOUR and now.minute < CSP_SCAN_MIN)):
        return False
    return last_csp_date_iso != now.date().isoformat()


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


def _read_drive_marker() -> dict | None:
    """Read the last-run marker from Drive. None on any miss."""
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


def _marker_key(m: dict | None):
    """Sort key for recency — (run date, finished/started timestamp)."""
    if not m:
        return ("", "")
    return (m.get("date_sgt") or "", m.get("finished_at") or m.get("started_at") or "")


def last_run_status() -> dict | None:
    """Read the last-run marker — the MORE RECENT of the local file and the Drive
    copy. The daily run can happen via the in-app scheduler (writes the local
    marker) OR the GitHub backstop on a separate runner (writes only the Drive
    marker). Reading local-only made the status bar under-report on backstop days,
    so we compare both and show the newest. Best-effort; Drive read failure → local.
    """
    local_m = None
    try:
        p = _marker_path()
        if p.exists():
            local_m = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    # Fast path: if the LOCAL marker already reflects today's run, trust it and
    # skip the Drive round-trip (avoids a REST call on every page render).
    today = datetime.now(SGT).date().isoformat()
    if local_m and local_m.get("date_sgt") == today:
        return local_m
    # Otherwise the local marker may be stale (e.g. the GitHub backstop ran today
    # on a separate runner and only updated Drive) — compare and show the newest.
    drive_m = _read_drive_marker()
    candidates = [m for m in (local_m, drive_m) if m]
    if not candidates:
        return None
    newest = max(candidates, key=_marker_key)
    # Refresh the local copy when Drive is newer, so subsequent reads are cheap
    # and the container reflects the backstop run after a restart.
    if newest is drive_m and drive_m is not local_m:
        try:
            _marker_path().write_text(json.dumps(newest, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return newest


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _run_pipeline_and_record(now: datetime) -> dict:
    """Run the daily orchestrator as a subprocess and record a marker."""
    from src.data.paths import PROJECT_ROOT, EXPORT_JSON

    started = now.strftime("%Y-%m-%d %H:%M:%S SGT")
    marker = {"date_sgt": now.date().isoformat(), "started_at": started}

    # Timeout budget for the whole pipeline subprocess. The FMP pull + scoring +
    # SRM + export + snapshot + signal ledger + MA scan (≈2000 tickers) can run
    # long; 2400s was too tight and killed the process mid-tail (after the export
    # was already written). 3300s (55 min) gives headroom while still bounding a
    # genuine runaway.
    _PIPELINE_TIMEOUT = 3300

    def _feed_status():
        """Was today's export actually written? Returns (exported_at, is_today)."""
        try:
            if EXPORT_JSON.exists():
                exp = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
                return exp.get("exported_at"), (exp.get("date") == now.date().isoformat())
        except Exception:  # noqa: BLE001
            pass
        return None, False

    def _packets_status(stdout: str) -> str:
        """Did Step 8a-3 (voice packets) actually publish? Independent of the
        overall run's rc/status -- 2026-09-01: the export refreshed cleanly
        (rc==0, feed_today True) while candidate_set.json + all 11 packet
        files sat stuck on a THREE-DAYS-OLD run, invisible because Step 8a-3
        (src/pipeline/daily_orchestrator.py) is wrapped in its own
        except-and-warn, and daily_backstop.py only ever prints/keeps `tail`
        when the overall run is not "success" -- an otherwise-clean run
        discarded every line telling you the publish had failed. Scans the
        captured stdout regardless of overall outcome so this can never again
        be silent; matches the exact print()s Step 8a-3 emits."""
        for line in reversed((stdout or "").splitlines()):
            if "Voice packets published:" in line:
                return line.strip()
            if ("[WARN] voice packets" in line
                    or "[WARN] Voice packet split failed" in line):
                return line.strip()
        return "unknown -- Step 8a-3 produced no recognizable output"

    try:
        proc = subprocess.run(
            [sys.executable, "-u", "-m", "src.pipeline.daily_orchestrator"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            timeout=_PIPELINE_TIMEOUT,
        )
        rc = proc.returncode
        exported_at, feed_today = _feed_status()
        # 2026-09-01 incident: rc==0 alone used to mean "success" -- but
        # daily_orchestrator's own Step 8 (src/pipeline/daily_orchestrator.py)
        # wraps export_to_drive() in a blanket except-and-warn that never
        # re-raises, so ANY failure inside it (a genuine bug, or the
        # universe-collapse guard in drive_sync.py correctly refusing to
        # publish) reduces to one buried WARN line and the rest of the
        # pipeline still runs to a clean exit. That let a run report
        # "status: success" here while aqe_daily_export.json sat unrefreshed
        # for days -- the one check that would have caught it (did the feed
        # actually update for TODAY) already existed, just only in the
        # TimeoutExpired/Exception branches below, never on the plain rc==0
        # path most runs actually take. A clean subprocess exit is necessary
        # but not sufficient; the export must ALSO be dated today.
        ok = rc == 0 and feed_today
        marker.update({
            "status": "success" if ok else ("failed" if rc != 0 else "partial"),
            "rc": rc,
            "finished_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "exported_at": exported_at,
            "packets_status": _packets_status(proc.stdout),
            "tail": "\n".join((proc.stdout or "").splitlines()[-8:]) if not ok else "",
            **({} if ok else {"reason": "pipeline exited 0 but the export was not "
                                         "refreshed for today -- see the tail for "
                                         "which step actually failed"}),
        })
    except subprocess.TimeoutExpired as exc:
        # The orchestrator writes + uploads the export at Step 8, BEFORE the heavy
        # tail steps (snapshot / ledger / MA scan). If those ran past the budget,
        # the feed is still current — mark "partial" (feed OK) not "failed", and
        # capture the last log lines so the slow tail step is diagnosable.
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        exported_at, feed_today = _feed_status()
        marker.update({
            "status": "partial" if feed_today else "failed",
            "finished_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "exported_at": exported_at,
            "packets_status": _packets_status(partial),
            "reason": (f"TimeoutExpired after {_PIPELINE_TIMEOUT}s"
                       + (" — feed EXPORTED OK; a tail step (snapshot/ledger/MA "
                          "scan) ran long. Trading feed is current."
                          if feed_today else " — timed out before the export.")),
            "last_steps": "\n".join(partial.splitlines()[-20:]),
        })
    except Exception as exc:  # noqa: BLE001
        exported_at, feed_today = _feed_status()
        marker.update({
            "status": "partial" if feed_today else "failed",
            "finished_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
            "exported_at": exported_at,
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


def _csp_scan_seed_date() -> str | None:
    """Seed the last-CSP-scan date from the existing options_scan.json so a
    container restart doesn't re-run today's scan."""
    try:
        from src.data.paths import OUTPUT_DIR
        from src.options import config as OC
        p = OUTPUT_DIR / Path(OC.UNIVERSE_SCAN_FILE).name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("generated_for")
    except Exception:  # noqa: BLE001
        pass
    return None


def _run_csp_scan_and_record(now: datetime) -> None:
    """Nightly universe CSP theta scan → the CSP Drive folder. Independent of the
    AQE feed; best-effort. Skips cleanly if Alpaca keys aren't set. Passes the SGT
    date so the run stamp + DTE are correct on a UTC container.
    """
    try:
        from src.options import config as OC
        if not (os.environ.get(OC.ALPACA_KEY_ID_ENV)
                and os.environ.get(OC.ALPACA_SECRET_ENV)):
            print("[daily-job] CSP scan skipped — Alpaca keys not set "
                  f"({OC.ALPACA_KEY_ID_ENV}/{OC.ALPACA_SECRET_ENV})")
            return
        # Use the freshest universe (Drive is source of truth between refreshes).
        try:
            from src.data.universe import restore_universe_from_drive
            restore_universe_from_drive()
        except Exception as exc:  # noqa: BLE001
            print(f"[daily-job] CSP scan: universe restore skipped ({exc})")
        from src.options.universe_scan import scan_universe, export_scan_to_drive
        print(f"[daily-job] CSP universe scan starting "
              f"{now.strftime('%Y-%m-%d %H:%M SGT')}")
        blob = scan_universe(today=now.date(), log=lambda *_: None)
        res = export_scan_to_drive(blob)
        dr = res.get("drive", {})
        print(f"[daily-job] CSP scan: {blob['candidates_count']} candidates across "
              f"{len({c['ticker'] for c in blob['candidates']})} names, Drive "
              + ("ok" if dr.get("ok") else f"FAILED ({dr.get('reason')})"))
    except Exception as exc:  # noqa: BLE001
        print(f"[daily-job] CSP scan failed: {exc}")


def _run_ma_scan_and_record(now: datetime) -> None:
    """Daily MA Proximity Scan — runs right AFTER the trading feed is published
    (so it never delays/fails the feed). Restore the persisted ma_panel first (so
    the pull is incremental, not a cold ~2000-ticker re-pull), scan, publish to
    the MA-scan Drive folder, then persist the freshened panel. Best-effort —
    never blocks anything; the daily feed is independent.
    """
    try:
        print(f"[daily-job] Daily MA scan starting "
              f"{now.strftime('%Y-%m-%d %H:%M SGT')}")
        # Restore last run's ma_panel so the scan is incremental — and ONLY
        # ma_panel. A full restore here would also roll panel_daily,
        # scores_daily and universe.txt back to whenever the zip was written,
        # discarding bars the pipeline pulled since and forcing a re-pull. The
        # MA scan runs after the feed is published, so "since" is exactly the
        # window that matters.
        try:
            from src.data.persist import load_snapshot
            load_snapshot(only=["ma_panel.parquet", "ma_universe.json"])
        except Exception as exc:  # noqa: BLE001
            print(f"[daily-job] MA scan: snapshot restore skipped ({exc})")
        from src.scanner.ma_scanner import run_ma_scan
        from src.data.fmp_client import FMPClient
        result = run_ma_scan(client=FMPClient())
        if result.get("ok"):
            print(f"[daily-job] Daily MA scan: "
                  f"{result['stats']['near_any_ma']} stocks near ≥1 MA")
        else:
            print(f"[daily-job] Daily MA scan skipped ({result.get('reason')})")
        # Persist the freshened ma_panel so next week's scan stays incremental.
        try:
            from src.data.persist import save_snapshot
            save_snapshot()
        except Exception as exc:  # noqa: BLE001
            print(f"[daily-job] MA scan: snapshot save skipped ({exc})")
    except Exception as exc:  # noqa: BLE001
        print(f"[daily-job] Daily MA scan failed: {exc}")


def _loop() -> None:
    # Seed last-run date from the persisted marker so a restart doesn't re-run.
    last = last_run_status()
    last_date = last.get("date_sgt") if last else None
    last_universe_date: str | None = None
    last_ma_date: str | None = None
    last_csp_date: str | None = _csp_scan_seed_date()
    while True:
        try:
            now = datetime.now(SGT)
            # 05:30 SGT — universe CSP theta scan (before the refresh + pipeline)
            if _should_run_csp_scan(now, last_csp_date):
                _run_csp_scan_and_record(now)
                last_csp_date = now.date().isoformat()
            # 06:00 SGT — universe refresh (before the pipeline)
            if _should_refresh_universe(now, last_universe_date):
                _refresh_universe_and_record(now)
                last_universe_date = now.date().isoformat()
            # 08:30 SGT — daily pipeline (trading feed), then the MA scan DAILY
            # right after it. The MA scan runs AFTER the feed is published, so a
            # slow FMP pull can never delay/fail the trading feed (it stays
            # decoupled from the pipeline's critical path), but on the same
            # daily cadence. It publishes its own JSON to the MA-scan Drive folder.
            if _should_run(now, last_date):
                _run_pipeline_and_record(now)
                last_date = now.date().isoformat()
                if last_ma_date != now.date().isoformat():
                    _run_ma_scan_and_record(now)
                    last_ma_date = now.date().isoformat()
                # ...and the CSP scan, if its own 05:30 window was missed.
                #
                # THE WINDOWS DID NOT OVERLAP, so it could never catch up. The
                # CSP slot is 05:30-08:00 and the pipeline slot is 08:30-12:00:
                # any morning the Space was not awake in that first window —
                # which is every morning it restarted overnight — the pipeline
                # ran and the options sweep silently did not, with no path back.
                # The MA scan has ridden along here since it was decoupled; the
                # options scan should have too. Its own marker still guards
                # against a double run when 05:30 DID fire.
                if last_csp_date != now.date().isoformat():
                    _run_csp_scan_and_record(now)
                    last_csp_date = now.date().isoformat()
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
