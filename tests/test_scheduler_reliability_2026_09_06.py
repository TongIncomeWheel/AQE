"""Regression tests for the 2026-09-06 daily-scheduler-reliability fix.

Root cause: keepalive/daily_job/alert_job used to be started from
require_login() (src/ui/shared.py) -- which only executes when Streamlit runs
the app script for a REAL browser session. Confirmed empirically: a plain
HTTP GET (exactly what an uptime/keepalive monitor sends) gets a 200 from
Streamlit's server without ever running a line of the app's Python code --
Streamlit only executes the script once a browser's JS opens the live
WebSocket session. On a Space redeployed many times a day, that meant the
08:30 SGT scheduler only re-armed itself if a human happened to open the app
between the last redeploy and 08:30 -- not guaranteed, and on several
recent days it silently never fired at all.

The fix: scripts/scheduler_daemon.py runs as its own OS process, launched
directly by docker-entrypoint.sh at container boot -- independent of
Streamlit, independent of any browser ever connecting. require_login() no
longer starts these itself, so there is exactly one scheduler per container,
not a race between it and a page-visit-triggered one."""

from __future__ import annotations

import inspect

import pytest


def test_require_login_no_longer_starts_the_scheduler_itself():
    """The exact regression this guards against: re-adding start_keepalive()/
    start_daily_job()/start_alert_job() calls inside require_login() would
    silently reintroduce the two-scheduler race and the page-visit
    dependency, even though scripts/scheduler_daemon.py also starts them."""
    from src.ui import shared

    src = inspect.getsource(shared.require_login)
    for forbidden in ("start_keepalive(", "start_daily_job(", "start_alert_job("):
        assert forbidden not in src, (
            f"require_login() must not call {forbidden} -- that call now "
            "belongs solely to scripts/scheduler_daemon.py, started at "
            "container boot, independent of any page visit")


def test_scheduler_daemon_starts_all_three_background_jobs(monkeypatch):
    from scripts import scheduler_daemon as D

    calls = []
    monkeypatch.setattr(D, "start_keepalive", lambda: calls.append("keepalive"))
    monkeypatch.setattr(D, "start_daily_job", lambda: calls.append("daily_job"))
    monkeypatch.setattr(D, "start_alert_job", lambda: calls.append("alert_job"))
    monkeypatch.setattr(D.time, "sleep", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    with pytest.raises(KeyboardInterrupt):
        D.main()

    assert calls == ["keepalive", "daily_job", "alert_job"]


def test_docker_entrypoint_launches_the_scheduler_daemon_before_streamlit():
    txt = open("docker-entrypoint.sh", encoding="utf-8").read()
    assert "scripts.scheduler_daemon" in txt
    assert "streamlit run" in txt
    # the daemon must be backgrounded (&), not block the container from ever
    # reaching the streamlit exec
    daemon_line = next(l for l in txt.splitlines() if "scripts.scheduler_daemon" in l)
    assert daemon_line.strip().endswith("&"), (
        "the scheduler daemon must be backgrounded, or it would block the "
        "container from ever starting the actual Streamlit server")


def test_dockerfile_uses_the_wrapper_entrypoint():
    txt = open("Dockerfile", encoding="utf-8").read()
    assert 'ENTRYPOINT ["./docker-entrypoint.sh"]' in txt
    assert "chmod +x docker-entrypoint.sh" in txt


# ── PM decision (2026-09-06): decommission the in-app + GitHub-cron triggers
# for the daily pipeline entirely, in favour of one external trigger (a
# Claude-scheduled Routine dispatching daily-run.yml alongside PTJ) plus the
# AQE UX's own manual "Bootstrap + run daily pipeline" button as the fallback.
# CSP scan (05:30) and universe refresh (06:00) were never part of that
# decision and must keep auto-firing from the in-app scheduler.

def test_daily_run_workflow_has_no_schedule_trigger():
    import yaml
    with open(".github/workflows/daily-run.yml") as f:
        wf = yaml.safe_load(f)
    # YAML 1.1 parses the bare `on:` key as the boolean True, not the string
    # "on" -- a well-known gotcha with GitHub Actions workflow files.
    triggers = wf[True]
    assert "schedule" not in triggers, (
        "GitHub's own cron trigger was removed -- it fired 4-5+ hours late "
        "most days (documented platform behaviour); the workflow is now "
        "triggered ONLY via workflow_dispatch")
    assert "workflow_dispatch" in triggers


def test_daily_job_loop_no_longer_auto_fires_the_pipeline():
    """The exact regression this guards against: re-adding a time-of-day
    check that calls _run_pipeline_and_record() inside _loop() would silently
    reintroduce the decommissioned in-app auto-fire the PM asked to remove."""
    from src.ui import daily_job

    src = inspect.getsource(daily_job._loop)
    assert "_run_pipeline_and_record(" not in src

    # CSP scan + universe refresh were never part of the decommission and
    # must still be there.
    assert "_run_csp_scan_and_record(" in src
    assert "_refresh_universe_and_record(" in src


def test_should_run_helper_for_the_pipeline_is_gone():
    """_should_run() decided whether it was past 08:30 and not yet run today
    -- purely dead code with no caller once _loop() stopped using it. Left in
    place, it would read as a live scheduling path to a future reader."""
    from src.ui import daily_job

    assert not hasattr(daily_job, "_should_run"), (
        "_should_run (the removed 08:30 pipeline gate) should have been "
        "deleted, not left as dead code")
