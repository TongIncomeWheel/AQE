"""Regression test for the 2026-09-01 incident: `_run_pipeline_and_record`
marked a run "status: success" purely off the subprocess exit code (rc==0),
never checking whether aegis/output/aqe_daily_export.json was actually
refreshed for today. daily_orchestrator's own Step 8 wraps export_to_drive()
in a blanket except-and-warn that never re-raises (src/pipeline/
daily_orchestrator.py), so ANY failure inside it -- a real bug, or the
universe-collapse guard in drive_sync.py correctly refusing to publish --
reduces to one buried WARN line and the rest of the pipeline still exits 0.
That let a run report "success" here while the live export sat unrefreshed
for days, with nothing loud enough to notice. The TimeoutExpired/Exception
branches already checked "did the feed update for today" correctly; only
the far more common plain-exit path never did."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.ui import daily_job as J

SGT = ZoneInfo("Asia/Singapore")


class _FakeProc:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


@pytest.fixture
def _wired(tmp_path, monkeypatch):
    from src.data import paths as P
    monkeypatch.setattr(P, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(P, "EXPORT_JSON", tmp_path / "aqe_daily_export.json")
    monkeypatch.setattr(P, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(J, "_write_marker", lambda marker: None)
    return tmp_path


def _write_export(tmp_path, date_str):
    (tmp_path / "aqe_daily_export.json").write_text(
        json.dumps({"date": date_str, "exported_at": f"{date_str} 10:00:00 SGT"}),
        encoding="utf-8",
    )


def test_rc_zero_with_a_stale_export_is_not_reported_as_success(_wired, monkeypatch):
    """The exact 2026-09-01 shape: the subprocess exits clean, but Step 8's
    export never actually landed for today (still shows a prior day)."""
    now = datetime(2026, 9, 1, 10, 30, tzinfo=SGT)
    _write_export(_wired, "2026-08-29")  # stale -- days old, not today
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc(returncode=0))

    marker = J._run_pipeline_and_record(now)

    assert marker["status"] != "success", (
        "rc==0 alone must never mean success -- the export was not refreshed today"
    )
    assert marker["rc"] == 0
    assert marker["exported_at"] == "2026-08-29 10:00:00 SGT"


def test_rc_zero_with_a_fresh_export_is_a_genuine_success(_wired, monkeypatch):
    now = datetime(2026, 9, 1, 10, 30, tzinfo=SGT)
    _write_export(_wired, "2026-09-01")  # today
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc(returncode=0))

    marker = J._run_pipeline_and_record(now)

    assert marker["status"] == "success"
    assert marker["rc"] == 0


def test_rc_nonzero_is_still_failed_regardless_of_the_export(_wired, monkeypatch):
    now = datetime(2026, 9, 1, 10, 30, tzinfo=SGT)
    _write_export(_wired, "2026-09-01")  # today, but the process itself failed
    monkeypatch.setattr(subprocess, "run",
                         lambda *a, **k: _FakeProc(returncode=1, stdout="boom\n"))

    marker = J._run_pipeline_and_record(now)

    assert marker["status"] == "failed"
    assert marker["rc"] == 1


def test_a_stale_export_run_captures_a_tail_for_diagnosis(_wired, monkeypatch):
    """Before this fix, `tail` was only captured when rc != 0 -- a clean-exit
    run that silently failed to export left NO diagnostic trail at all."""
    now = datetime(2026, 9, 1, 10, 30, tzinfo=SGT)
    _write_export(_wired, "2026-08-29")
    monkeypatch.setattr(subprocess, "run",
                         lambda *a, **k: _FakeProc(returncode=0, stdout="line1\nline2\n"))

    marker = J._run_pipeline_and_record(now)

    assert marker.get("tail"), "a silently-stale run must still leave a diagnosable tail"
