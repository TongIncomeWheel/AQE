"""AQE run 127 (2026-11-02 01:51 SGT, GitHub Actions runner on UTC): the
orchestrator stamped the export / candidate_set / SRM cache with the naive
system date 2026-11-01 while the marker (SGT) said 2026-11-02 -> `partial`,
workflow red, handoff gate refused a run that had completed. Every 06:30 SGT
run is 22:30 UTC the day before, so this is the daily path, not an edge case."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_default_run_date_is_the_singapore_date():
    from src.pipeline import daily_orchestrator as D
    assert D._sgt_today() == datetime.now(ZoneInfo("Asia/Singapore")).date()


def test_no_naive_date_today_on_the_daily_stamping_path():
    """The run date, the SRM cache date and the export's version stamps must
    all come from the SGT clock -- a naive date.today() anywhere on this path
    reintroduces the midnight split."""
    for rel in ("src/pipeline/daily_orchestrator.py", "src/data/drive_sync.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        hits = [l for l in code.splitlines() if re.search(r"\bdate\.today\(\)", l)]
        assert not hits, f"{rel}: naive date.today() on the daily path: {hits}"


def test_marker_and_export_agree_across_utc_midnight(tmp_path, monkeypatch):
    """The marker's `feed_today` is the SGT date; the export written by the
    same run must carry that date even when UTC is still yesterday."""
    from src.pipeline import daily_orchestrator as D

    class _Now:
        @staticmethod
        def now(tz=None):
            # 01:51 SGT on the 2nd == 17:51 UTC on the 1st
            return datetime(2026, 11, 2, 1, 51, tzinfo=ZoneInfo("Asia/Singapore")).astimezone(tz)
    monkeypatch.setattr(D, "datetime", _Now)
    assert D._sgt_today().isoformat() == "2026-11-02"
