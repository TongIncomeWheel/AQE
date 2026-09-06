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
