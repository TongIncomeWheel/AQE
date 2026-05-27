"""Aegis Quant Engine -- Scheduler (Page 4).

Register Windows scheduled tasks that run AQE jobs automatically. Pick a job,
tick the days, set the time, and save. Scheduled jobs run via Windows Task
Scheduler even when this app and the browser are closed -- the machine just
needs to be powered on with you logged in.
"""

from __future__ import annotations

import sys
from datetime import time as dtime
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Scheduler", page_icon=":calendar:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import scheduler as sch

st.title("Scheduler")
st.caption(
    "Run AQE jobs automatically via Windows Task Scheduler. Scheduled jobs run "
    "even when this app is closed -- the machine just needs to be on with you "
    "logged in. Times use the machine clock (Singapore time)."
)

# A flash message survives the rerun that follows an action button.
_flash = st.session_state.pop("sched_flash", None)
if _flash:
    (st.success if _flash["ok"] else st.error)(_flash["msg"])

if not sch.is_windows():
    st.error(
        "The Scheduler needs Windows Task Scheduler, which is not available on "
        "this machine."
    )
    st.stop()


def _act(result: tuple[bool, str]) -> None:
    """Stash an action result as a flash message, then rerun."""
    ok, msg = result
    st.session_state["sched_flash"] = {"ok": ok, "msg": msg}
    st.rerun()


# ---------------------------------------------------------------------------
# Active schedules
# ---------------------------------------------------------------------------

st.subheader("Active schedules")

just_ran = st.session_state.pop("sched_just_ran", None)
overview = sch.schedule_overview()

if not overview:
    st.info("No schedules yet. Use the form below to add one.")

for row in overview:
    key = row["key"]
    live = row["live"]
    days = row["days"]
    days_str = ", ".join(sch.DAY_LABELS.get(d, d) for d in days) if days else "-"

    with st.container(border=True):
        head = st.columns([4, 1])
        with head[0]:
            st.markdown(f"### {row['label']}")
            st.caption(row["description"])
        with head[1]:
            if live is None:
                st.error("Not registered")
            elif live["enabled"]:
                st.success("Enabled")
            else:
                st.warning("Disabled")

        if live is None:
            st.caption(
                "The Windows task for this schedule is missing. Re-save it in "
                "the form below, or remove this stale entry."
            )
            if st.button("Remove stale entry", key=f"rm_{key}"):
                _act(sch.delete_schedule(key))
            continue

        st.markdown(
            f"**Days:** {days_str}  |  **Time:** {row['time'] or '-'}  |  "
            f"**Status:** {live['status']}  |  **Last run:** {live['last_run']}"
            f"  |  **Last result:** {live['last_result_text']}"
        )
        st.caption(f"Next run: {live['next_run']}  |  Task: {live['task_name']}")

        b = st.columns(4)
        if b[0].button("Run now", key=f"run_{key}"):
            ok, msg = sch.run_now(key)
            st.session_state["sched_flash"] = {"ok": ok, "msg": msg}
            st.session_state["sched_just_ran"] = key
            st.rerun()
        if live["enabled"]:
            if b[1].button("Disable", key=f"dis_{key}"):
                _act(sch.set_enabled(key, False))
        else:
            if b[1].button("Enable", key=f"en_{key}"):
                _act(sch.set_enabled(key, True))
        if b[2].button("Delete", key=f"del_{key}"):
            _act(sch.delete_schedule(key))

        with st.expander("Run log", expanded=(just_ran == key)):
            log_text = sch.read_log(key)
            if log_text.strip():
                st.code(log_text, language=None)
            else:
                st.caption("No log yet -- this job has not run.")
            if st.button("Clear log", key=f"clr_{key}"):
                sch.clear_log(key)
                st.rerun()

# ---------------------------------------------------------------------------
# Add or update a schedule
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Add or update a schedule")

job_key = st.selectbox(
    "Job to run",
    options=[j.key for j in sch.JOBS],
    format_func=lambda k: sch.JOBS_BY_KEY[k].label,
)
job = sch.JOBS_BY_KEY[job_key]
st.caption(job.description)

if job_key == "daily_scan":
    st.info(
        "The Daily AQE Scan needs end-of-day US market data. US markets close "
        "around 04:00-05:00 SGT and FMP posts EOD bars a few hours later -- "
        "schedule this for the morning SGT (08:00-10:00) so fresh data is ready."
    )

existing = sch.get_schedule_meta(job_key)
default_days = set(existing["days"]) if existing else set(sch.WEEKDAYS)
default_time = dtime(8, 0)
if existing and existing.get("time"):
    try:
        _hh, _mm = existing["time"].split(":")
        default_time = dtime(int(_hh), int(_mm))
    except Exception:
        pass

if existing:
    st.caption(f"This job already has a schedule (saved {existing.get('saved_at', '')}). Saving will replace it.")

with st.form("add_schedule"):
    st.markdown("**Days**")
    day_cols = st.columns(7)
    ticks: dict[str, bool] = {}
    for i, d in enumerate(sch.DAY_CODES):
        ticks[d] = day_cols[i].checkbox(
            sch.DAY_LABELS[d],
            value=(d in default_days),
            key=f"day_{job_key}_{d}",
        )
    run_time = st.time_input(
        "Time (machine clock = Singapore time)",
        value=default_time,
        key=f"time_{job_key}",
    )
    submitted = st.form_submit_button("Save schedule", type="primary")

if submitted:
    chosen = [d for d in sch.DAY_CODES if ticks[d]]
    if not chosen:
        st.session_state["sched_flash"] = {
            "ok": False, "msg": "Tick at least one day before saving.",
        }
        st.rerun()
    else:
        _act(sch.create_schedule(job_key, chosen, run_time.strftime("%H:%M")))

# ---------------------------------------------------------------------------
# How it works
# ---------------------------------------------------------------------------

st.divider()
with st.expander("How scheduling works"):
    st.markdown(
        f"- Saving a schedule registers a task in **Windows Task Scheduler** "
        f"under the `{sch.TASK_FOLDER}` folder.\n"
        "- Tasks run as you, need no administrator rights, and **do not need "
        "this app open** -- only the machine on with you logged in.\n"
        "- Each job runs a small generated `.bat` in `scheduler/jobs/`; all "
        "output is appended to `scheduler/logs/<job>.log`.\n"
        "- A job runs on battery and **catches up** if the machine was off at "
        "the scheduled time (it runs at the next opportunity).\n"
        "- A brief console window may appear while a job runs -- that is normal.\n"
        "- **Run now** triggers a job immediately -- a good way to test it."
    )
