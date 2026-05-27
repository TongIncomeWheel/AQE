"""Windows Task Scheduler front-end for AQE jobs.

Page 4 (Scheduler) uses this module to register and manage Windows scheduled
tasks that run AQE pipeline jobs automatically. Tasks live under the Task
Scheduler folder \\AQE and run even when the Streamlit app and browser are
closed -- the machine only needs to be powered on with the user logged in.

Each job is backed by a generated .bat under scheduler/jobs/ which changes to
the project root, runs the job, and appends all output to
scheduler/logs/<key>.log.

Windows only. No administrator rights required -- tasks run as the current
user. Power settings are hardened so a job still runs on battery and catches
up if the machine was off at the scheduled time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCHEDULER_DIR = PROJECT_ROOT / "scheduler"
JOBS_DIR = SCHEDULER_DIR / "jobs"
LOGS_DIR = SCHEDULER_DIR / "logs"
SCHEDULES_JSON = SCHEDULER_DIR / "schedules.json"

TASK_FOLDER = "\\AQE"          # Windows Task Scheduler folder

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DAY_LABELS = {
    "MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu",
    "FRI": "Fri", "SAT": "Sat", "SUN": "Sun",
}
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI"]

DAY_XML = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
    "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}

SGT = ZoneInfo("Asia/Singapore")

CREATE_NO_WINDOW = 0x08000000


# ---------------------------------------------------------------------------
# Job registry -- what the scheduler is allowed to run
# ---------------------------------------------------------------------------

class Job(NamedTuple):
    key: str
    label: str
    description: str
    py_args: tuple[str, ...]


JOBS: list[Job] = [
    Job(
        "daily_scan",
        "Daily AQE Scan",
        "Full daily pipeline: incremental bar pull, Pipeline Rank screen, full "
        "scoring, SRM grading, regime, PTRS, recipe + Precision Edge screens, "
        "position tracker, and Google Drive export.",
        ("-m", "src.pipeline.daily_orchestrator"),
    ),
    Job(
        "panel_refresh",
        "Refresh Price Panel",
        "Pull the latest daily bars from FMP into panel_daily.parquet "
        "(plus the weekly panel and SPY).",
        ("-m", "src.data.panel_builder"),
    ),
    Job(
        "score_run",
        "Run Scoring Engines",
        "Run all 5 engines and the composites over the cached panel and write "
        "scores_daily.parquet. Does not pull fresh data.",
        ("-m", "src.scanner.score_runner"),
    ),
    Job(
        "earnings_refresh",
        "Refresh Earnings Calendar",
        "Pull the upcoming earnings calendar from FMP.",
        ("-m", "src.data.earnings"),
    ),
    Job(
        "universe_refresh",
        "Refresh Universe",
        "Re-pull the FMP screener universe ($1B+ market cap, $5+ price, "
        "500K+ volume, NYSE + NASDAQ).",
        (
            "-c",
            "from src.data.universe import refresh_universe; "
            "r = refresh_universe(); "
            "print('Added', len(r['added']), 'Removed', len(r['removed']), "
            "'Total', r['total'])",
        ),
    ),
    Job(
        "sector_map",
        "Rebuild Sector Map",
        "Rebuild the ticker -> GICS sector ETF map from FMP.",
        ("-m", "src.data.sector_mapper"),
    ),
]

JOBS_BY_KEY: dict[str, Job] = {j.key: j for j in JOBS}


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def is_windows() -> bool:
    return os.name == "nt"


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _python_exe() -> str:
    """Console python.exe matching the current interpreter."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def _task_name(key: str) -> str:
    return f"{TASK_FOLDER}\\{key}"


def job_bat_path(key: str) -> Path:
    return JOBS_DIR / f"{key}.bat"


def job_log_path(key: str) -> Path:
    return LOGS_DIR / f"{key}.log"


def _run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a command with no console-window flash. Never raises."""
    kwargs: dict = {}
    if is_windows():
        kwargs["creationflags"] = CREATE_NO_WINDOW
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, **kwargs
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "timed out")
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


# ---------------------------------------------------------------------------
# Generated .bat
# ---------------------------------------------------------------------------

def _quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or "\t" in arg) else arg


def write_job_bat(job: Job) -> Path:
    """Generate the .bat that the scheduled task runs. Returns its path."""
    _ensure_dirs()
    bat = job_bat_path(job.key)
    log = job_log_path(job.key)

    cmd = " ".join([f'"{_python_exe()}"'] + [_quote(a) for a in job.py_args])

    lines = [
        "@echo off",
        f"REM AQE scheduled job: {job.label}",
        "REM Generated by the Scheduler page (Page 4). Do not edit by hand.",
        f'cd /d "{PROJECT_ROOT}"',
        f'echo.>>"{log}"',
        f'echo [%DATE% %TIME%] START {job.label}>>"{log}"',
        f'{cmd} >> "{log}" 2>&1',
        f'echo [%DATE% %TIME%] END (exit %ERRORLEVEL%)>>"{log}"',
        "",
    ]
    bat.write_text("\r\n".join(lines), encoding="utf-8", newline="")
    return bat


# ---------------------------------------------------------------------------
# Schedule metadata cache (days/time chosen by the user)
# ---------------------------------------------------------------------------

def _load_all_meta() -> dict:
    if SCHEDULES_JSON.exists():
        try:
            return json.loads(SCHEDULES_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_all_meta(meta: dict) -> None:
    _ensure_dirs()
    SCHEDULES_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def get_schedule_meta(key: str) -> dict | None:
    return _load_all_meta().get(key)


# ---------------------------------------------------------------------------
# Task operations
# ---------------------------------------------------------------------------

def _build_task_xml(job: Job, bat: Path, days: list[str], time_hhmm: str) -> str:
    """Build Task Scheduler XML for a weekly job.

    Settings are baked in here so creation is a single schtasks call: the task
    runs on battery, catches up if the machine was off at the trigger time
    (StartWhenAvailable), and is killed after 2 hours if it ever hangs.
    """
    start = f"{datetime.now().strftime('%Y-%m-%d')}T{time_hhmm}:00"
    days_xml = "".join(f"          <{DAY_XML[d]} />\n" for d in days)
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" '
        'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        '  <RegistrationInfo>\n'
        f'    <Description>{escape(f"AQE scheduled job: {job.label}")}</Description>\n'
        '  </RegistrationInfo>\n'
        '  <Triggers>\n'
        '    <CalendarTrigger>\n'
        f'      <StartBoundary>{start}</StartBoundary>\n'
        '      <Enabled>true</Enabled>\n'
        '      <ScheduleByWeek>\n'
        '        <DaysOfWeek>\n'
        f'{days_xml}'
        '        </DaysOfWeek>\n'
        '        <WeeksInterval>1</WeeksInterval>\n'
        '      </ScheduleByWeek>\n'
        '    </CalendarTrigger>\n'
        '  </Triggers>\n'
        '  <Principals>\n'
        '    <Principal id="Author">\n'
        '      <LogonType>InteractiveToken</LogonType>\n'
        '      <RunLevel>LeastPrivilege</RunLevel>\n'
        '    </Principal>\n'
        '  </Principals>\n'
        '  <Settings>\n'
        '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
        '    <StartWhenAvailable>true</StartWhenAvailable>\n'
        '    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>\n'
        '    <AllowStartOnDemand>true</AllowStartOnDemand>\n'
        '    <Enabled>true</Enabled>\n'
        '    <Hidden>false</Hidden>\n'
        '    <WakeToRun>false</WakeToRun>\n'
        '    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>\n'
        '    <Priority>7</Priority>\n'
        '  </Settings>\n'
        '  <Actions Context="Author">\n'
        '    <Exec>\n'
        f'      <Command>{escape(str(bat))}</Command>\n'
        f'      <WorkingDirectory>{escape(str(PROJECT_ROOT))}</WorkingDirectory>\n'
        '    </Exec>\n'
        '  </Actions>\n'
        '</Task>\n'
    )


def create_schedule(key: str, days: list[str], time_hhmm: str) -> tuple[bool, str]:
    """Create or replace the Windows scheduled task for a job.

    days      -- subset of DAY_CODES.
    time_hhmm -- 'HH:MM' on the 24-hour machine clock.
    Returns (ok, message).
    """
    if not is_windows():
        return False, "Scheduling requires Windows Task Scheduler."
    job = JOBS_BY_KEY.get(key)
    if job is None:
        return False, f"Unknown job: {key}"
    days = [d for d in DAY_CODES if d in days]      # normalise + order
    if not days:
        return False, "Pick at least one day."

    bat = write_job_bat(job)
    xml_path = JOBS_DIR / f"{key}.task.xml"
    xml_path.write_text(_build_task_xml(job, bat, days, time_hhmm), encoding="utf-16")

    cp = _run([
        "schtasks", "/Create",
        "/TN", _task_name(key),
        "/XML", str(xml_path),
        "/F",
    ])
    try:
        xml_path.unlink()
    except OSError:
        pass

    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        return False, f"Could not create the task: {detail}"

    meta = _load_all_meta()
    meta[key] = {
        "days": days,
        "time": time_hhmm,
        "saved_at": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
    }
    _save_all_meta(meta)

    return True, f"Scheduled '{job.label}' for {', '.join(days)} at {time_hhmm}."


def delete_schedule(key: str) -> tuple[bool, str]:
    """Remove the scheduled task and its saved metadata."""
    if not is_windows():
        return False, "Scheduling requires Windows Task Scheduler."
    cp = _run(["schtasks", "/Delete", "/TN", _task_name(key), "/F"])

    meta = _load_all_meta()
    if key in meta:
        del meta[key]
        _save_all_meta(meta)

    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        if "cannot find" in detail.lower():
            return True, "Schedule removed."
        return False, f"Could not delete the task: {detail}"
    return True, "Schedule removed."


def set_enabled(key: str, enabled: bool) -> tuple[bool, str]:
    """Enable or disable the scheduled task without deleting it."""
    if not is_windows():
        return False, "Scheduling requires Windows Task Scheduler."
    flag = "/ENABLE" if enabled else "/DISABLE"
    cp = _run(["schtasks", "/Change", "/TN", _task_name(key), flag])
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        return False, f"Could not change the task: {detail}"
    return True, ("Schedule enabled." if enabled else "Schedule disabled.")


def run_now(key: str) -> tuple[bool, str]:
    """Trigger the scheduled task immediately (also works as a test run)."""
    if not is_windows():
        return False, "Scheduling requires Windows Task Scheduler."
    cp = _run(["schtasks", "/Run", "/TN", _task_name(key)])
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        return False, f"Could not start the task: {detail}"
    return True, "Run triggered -- check the run log in a minute."


def _result_text(code: str) -> str:
    code = (code or "").strip()
    if code in ("0", "0x0"):
        return "OK"
    if code in ("267011", "0x41303"):
        return "Not yet run"
    if code in ("267009", "0x41301"):
        return "Running"
    if code in ("267010", "0x41302"):
        return "Terminated"
    if not code:
        return "-"
    return f"Error ({code})"


def query_schedule(key: str) -> dict | None:
    """Live status for a job's task, or None if it is not registered."""
    if not is_windows():
        return None
    cp = _run([
        "schtasks", "/Query", "/TN", _task_name(key), "/FO", "LIST", "/V",
    ])
    if cp.returncode != 0:
        return None

    fields: dict[str, str] = {}
    for line in cp.stdout.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    if "TaskName" not in fields:
        return None

    state = fields.get("Scheduled Task State", "")
    last_run = fields.get("Last Run Time", "")
    if last_run.startswith("11/30/1999") or last_run.startswith("30/11/1999"):
        last_run = "Never"

    return {
        "registered": True,
        "status": fields.get("Status", "-"),
        "state": state,
        "enabled": state.strip().lower() != "disabled",
        "next_run": fields.get("Next Run Time", "-"),
        "last_run": last_run or "-",
        "last_result_text": _result_text(fields.get("Last Result", "")),
        "task_name": _task_name(key),
    }


def schedule_overview() -> list[dict]:
    """One row per job with a saved schedule, in JOBS order.

    Only scheduled jobs are queried -- a fresh page render with nothing
    scheduled costs zero schtasks calls.
    """
    meta = _load_all_meta()
    rows = []
    for job in JOBS:
        saved = meta.get(job.key)
        if saved is None:
            continue
        rows.append({
            "key": job.key,
            "label": job.label,
            "description": job.description,
            "days": saved.get("days", []),
            "time": saved.get("time", ""),
            "saved_at": saved.get("saved_at", ""),
            "live": query_schedule(job.key),
        })
    return rows


# ---------------------------------------------------------------------------
# Run logs
# ---------------------------------------------------------------------------

def read_log(key: str, tail: int = 80) -> str:
    """Return the last `tail` lines of a job's run log."""
    log = job_log_path(key)
    if not log.exists():
        return ""
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"(could not read log: {exc})"
    return "\n".join(text.splitlines()[-tail:])


def clear_log(key: str) -> None:
    log = job_log_path(key)
    if log.exists():
        log.write_text("", encoding="utf-8")
