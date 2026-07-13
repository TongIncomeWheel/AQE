"""Timing tests for the nightly 05:30 SGT CSP scan slot — pure, no I/O."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.ui import daily_job as J

SGT = ZoneInfo("Asia/Singapore")


def _sgt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=SGT)


# 2026-07-14 is a Tuesday (a run day).
def test_runs_at_0530_on_run_day():
    assert J._should_run_csp_scan(_sgt(2026, 7, 14, 5, 30), None) is True


def test_not_before_0530():
    assert J._should_run_csp_scan(_sgt(2026, 7, 14, 5, 29), None) is False


def test_not_after_window():
    # 08:00+ is past the catch-up window (keeps it clear of the 08:30 pipeline).
    assert J._should_run_csp_scan(_sgt(2026, 7, 14, 8, 0), None) is False


def test_not_twice_same_day():
    assert J._should_run_csp_scan(_sgt(2026, 7, 14, 6, 0), "2026-07-14") is False


def test_skips_sunday_and_monday_sgt():
    assert J._should_run_csp_scan(_sgt(2026, 7, 12, 5, 30), None) is False  # Sun
    assert J._should_run_csp_scan(_sgt(2026, 7, 13, 5, 30), None) is False  # Mon


def test_csp_window_precedes_pipeline():
    # The CSP catch-up window closes before the pipeline's run time — no contention.
    assert J.CSP_SCAN_WINDOW_END_HOUR <= J.RUN_HOUR
