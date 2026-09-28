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


# ── MA Proximity Scan's own 09:00 SGT "Part 2" slot (2026-09-28) ───────────
# Independent of the daily pipeline's own external trigger times (~05:30 the
# AEGIS routine, ~08:30 the dedicated Routine) -- see daily_job.py's module
# docstring for why this must never ride inside the pipeline itself again.


def test_ma_scan_runs_at_0900_on_run_day():
    assert J._should_run_ma_scan(_sgt(2026, 7, 14, 9, 0), None) is True


def test_ma_scan_not_before_0900():
    assert J._should_run_ma_scan(_sgt(2026, 7, 14, 8, 59), None) is False


def test_ma_scan_not_after_window():
    assert J._should_run_ma_scan(_sgt(2026, 7, 14, 14, 0), None) is False


def test_ma_scan_not_twice_same_day():
    assert J._should_run_ma_scan(_sgt(2026, 7, 14, 10, 0), "2026-07-14") is False


def test_ma_scan_skips_sunday_and_monday_sgt():
    assert J._should_run_ma_scan(_sgt(2026, 7, 12, 9, 0), None) is False  # Sun
    assert J._should_run_ma_scan(_sgt(2026, 7, 13, 9, 0), None) is False  # Mon


def test_ma_scan_slot_is_clear_of_both_pipeline_trigger_times():
    """09:00 SGT must sit after both known daily-pipeline external triggers
    (~05:30 AEGIS, ~08:30 the dedicated Routine) so the MA scan's FMP pulls
    never overlap the real feed's."""
    assert J.MA_SCAN_HOUR > 8
