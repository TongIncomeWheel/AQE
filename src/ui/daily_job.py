"""In-app scheduler — universe/CSP pre-market jobs. The main daily pipeline is
NO LONGER auto-fired from here (2026-09-06 PM decision).

Schedule (SGT, Tuesday–Saturday):
  05:30 — Universe CSP theta scan (Alpaca → options_scan.json to the CSP Drive folder)
  06:00 — Universe refresh (FMP screener → mcap/$2B + SMA20/50 + volume)
Sunday and Monday (SGT) are skipped (US markets closed Sat/Sun).

The 05:30 CSP scan runs ~1h after the US close, before the 06:00 universe
refresh, so the options sweep never contends with it.

The daily pipeline itself (`_run_pipeline_and_record`, and the MA Proximity
Scan that rides along right after it) is triggered EXTERNALLY now — a
Claude-scheduled Routine dispatches the `daily-run.yml` GitHub Actions
workflow each morning as part of the same sequential job as the PTJ command,
and the "Bootstrap + run daily pipeline" Scanner sidebar button covers a
manual run. Both call `_run_pipeline_and_record` directly.

Why: this used to auto-fire here at 08:30, gated on a real browser session
having started the scheduler thread (require_login()) -- which a keepalive/
uptime ping can never do (Streamlit only executes the app script for an
actual WebSocket session, not a bare HTTP request) -- and on a Space rebuilt
many times a day, that state kept getting wiped. A 2026-09-06 fix moved the
thread startup to scripts/scheduler_daemon.py (container-boot, no page-visit
dependency), which made this reliable again -- but the PM then decided a
single external trigger (Claude + PTJ, with a manual UX button as fallback)
is simpler and more predictable than reconciling three independent
schedulers (HF in-app, GitHub's own flaky `schedule:` cron, and this one),
and asked for the in-app and GitHub-cron paths torn out rather than kept as
a redundant safety net. This file still owns the CSP scan and universe
refresh -- those were never part of that decision.

Requirements:
- The container must be awake for the 05:30/06:00 jobs to fire -- keep it up
  with an external uptime monitor. This scheduler can't wake a sleeping
  container by itself.
- Active only on HF (SPACE_HOST set) unless AQE_ENABLE_SCHEDULER=1 forces it on.
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
# Python weekday(): Mon=0 .. Sun=6. Skip Sunday(6) and Monday(0).
SKIP_WEEKDAYS = {6, 0}

# Universe CSP theta scan runs at 05:30 SGT — ~1h after the US close, BEFORE the
# 06:00 universe refresh. Publishes options_scan.json to the dedicated CSP Drive
# folder.
CSP_SCAN_HOUR = 5
CSP_SCAN_MIN = 30
CSP_SCAN_WINDOW_END_HOUR = 8        # catch late wake-ups up to 08:00

# Universe auto-refresh runs at 06:00 SGT.
UNIVERSE_HOUR = 6
UNIVERSE_MIN = 0
UNIVERSE_WINDOW_END_HOUR = 8        # catch late wake-ups up to 08:00

# MA Proximity Scanner — runs right after `_run_pipeline_and_record`'s own feed
# publish (see that function), against a persisted ma_panel so it stays
# incremental. Decoupled from the pipeline's critical path so a slow FMP pull
# can't fail the trading feed.

MARKER_FILENAME = "aqe_last_run.json"

_started = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Schedule decision (pure — unit-testable)
# ---------------------------------------------------------------------------

def _is_run_day(d) -> bool:
    return d.weekday() not in SKIP_WEEKDAYS




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
    # 2026-09-06: there is no more in-app 08:30 auto-fire to name a time for --
    # the daily pipeline is triggered externally (a Claude-scheduled Routine
    # alongside PTJ) or manually from this UX's own sidebar button.
    return "via the morning PTJ+AQE task, or manually from the sidebar"


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
    # 2026-09-04: this write happens in THIS process, AFTER daily_orchestrator's
    # own subprocess (and its Step 8a-2 GitHub publish, which runs mid-subprocess
    # and so never sees this marker) has already exited. On a persistent HF Space
    # container the local write above is enough -- the same process keeps serving
    # pages. On a GitHub Actions runner the local write is DISCARDED the moment
    # the job ends and is never otherwise pushed anywhere durable, so the true,
    # final status of an Actions-run backstop was invisible outside that one job's
    # own log -- exactly what made a genuinely successful 2026-09-03 backstop run
    # look, from the published marker alone, like nothing had run since 2026-09-02.
    # Push it to GitHub too so it survives regardless of which environment ran it.
    try:
        from src.data import github_sync
        if github_sync.is_configured():
            github_sync.put_output(MARKER_FILENAME, content,
                                   message=f"data: daily output {marker.get('date_sgt', '')}")
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

    def _artifacts_published(stdout: str) -> dict | None:
        """Which of the DAILY_ARTIFACTS files (Step 8a-2) actually reached
        GitHub this run -- the status bar used to show only a bare
        timestamp, which says WHEN something last happened but nothing about
        WHAT reached GitHub. A run can report an on-time timestamp while half
        the artifacts silently failed to publish; this makes that visible
        instead of assumed. Scans for the exact JSON receipt line
        src/pipeline/daily_orchestrator.py prints right after Step 8a-2.
        Returns None if the line was never printed (older run / crashed
        before that step) rather than fabricating a shape."""
        for line in reversed((stdout or "").splitlines()):
            if line.startswith("ARTIFACTS_PUBLISH_JSON:"):
                try:
                    return json.loads(line.split(":", 1)[1].strip())
                except Exception:  # noqa: BLE001
                    return None
        return None

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
            "artifacts_published": _artifacts_published(proc.stdout),
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
            "artifacts_published": _artifacts_published(partial),
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
    # MA Proximity Scan rides along right after the feed, on whatever actually
    # triggered this run (external dispatch or the manual UX button) -- no
    # longer a separate 08:30 branch in the (now removed) in-app scheduler
    # loop. Decoupled from the pipeline's own critical path: it runs AFTER
    # the marker is already written, so a slow/failing MA scan can never turn
    # a genuine feed success into a reported failure.
    try:
        _, feed_today_now = _feed_status()
        if feed_today_now:
            _run_ma_scan_and_record(now)
    except Exception:  # noqa: BLE001
        pass
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
    last_universe_date: str | None = None
    last_csp_date: str | None = _csp_scan_seed_date()
    while True:
        try:
            now = datetime.now(SGT)
            # 05:30 SGT — universe CSP theta scan (before the refresh)
            if _should_run_csp_scan(now, last_csp_date):
                _run_csp_scan_and_record(now)
                last_csp_date = now.date().isoformat()
            # 06:00 SGT — universe refresh
            if _should_refresh_universe(now, last_universe_date):
                _refresh_universe_and_record(now)
                last_universe_date = now.date().isoformat()
            # The daily pipeline itself (+ the MA scan that rides along right
            # after it) is triggered externally now -- see the module
            # docstring. Nothing to check for it here.
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
