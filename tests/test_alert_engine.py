"""Tests for src/alerts/engine.py's load_export() — the local-vs-Drive freshness
fix (a stale git-committed local copy must never shadow a fresher Drive export)."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import engine as E


def _today_ny() -> str:
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


@pytest.fixture(autouse=True)
def _isolate_export_json(tmp_path, monkeypatch):
    """Point EXPORT_JSON at a scratch file so tests never touch the real repo."""
    p = tmp_path / "aqe_daily_export.json"
    monkeypatch.setattr(E, "EXPORT_JSON", p)
    return p


def test_no_local_no_drive_returns_none(monkeypatch):
    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", lambda: False)
    assert E.load_export() is None


def test_local_missing_falls_back_to_drive(monkeypatch):
    drive_export = {"date": _today_ny(), "exported_at": f"{_today_ny()} 12:00:00 SGT"}
    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", lambda: True)
    monkeypatch.setattr("src.data.gdrive_uploader.download_text",
                        lambda name: json.dumps(drive_export))
    out = E.load_export()
    assert out == drive_export


def test_local_todays_date_skips_drive_roundtrip(_isolate_export_json, monkeypatch):
    """Fast path: a local export already dated TODAY is trusted outright — Drive
    must never even be queried (proves no wasted round-trip on the common case)."""
    local_export = {"date": _today_ny(), "exported_at": f"{_today_ny()} 08:00:00 SGT"}
    _isolate_export_json.write_text(json.dumps(local_export), encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("Drive should not be consulted when local is fresh")

    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", _boom)
    out = E.load_export()
    assert out == local_export


def test_stale_committed_local_is_shadowed_by_fresher_drive(_isolate_export_json, monkeypatch):
    """The exact bug: a stale git-committed local copy (old date) must NOT win
    over a genuinely fresher Drive export."""
    stale_local = {"date": "2026-05-27", "exported_at": "2026-05-27 12:50:51 SGT"}
    _isolate_export_json.write_text(json.dumps(stale_local), encoding="utf-8")

    fresh_drive = {"date": _today_ny(), "exported_at": f"{_today_ny()} 12:36:52 SGT"}
    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", lambda: True)
    monkeypatch.setattr("src.data.gdrive_uploader.download_text",
                        lambda name: json.dumps(fresh_drive))

    out = E.load_export()
    assert out == fresh_drive
    assert out != stale_local


def test_local_newer_than_drive_wins(_isolate_export_json, monkeypatch):
    """If Drive is somehow lagging (e.g. an upload failure), a genuinely newer
    local copy should still win the comparison."""
    newer_local = {"date": "2026-07-13", "exported_at": "2026-07-13 20:00:00 SGT"}
    _isolate_export_json.write_text(json.dumps(newer_local), encoding="utf-8")

    older_drive = {"date": "2026-07-12", "exported_at": "2026-07-12 12:00:00 SGT"}
    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", lambda: True)
    monkeypatch.setattr("src.data.gdrive_uploader.download_text",
                        lambda name: json.dumps(older_drive))

    out = E.load_export()
    assert out == newer_local


def test_drive_unconfigured_falls_back_to_stale_local(_isolate_export_json, monkeypatch):
    """No Drive access at all (e.g. OAuth broken) — degrade to whatever local
    has, rather than returning nothing."""
    stale_local = {"date": "2026-05-27", "exported_at": "2026-05-27 12:50:51 SGT"}
    _isolate_export_json.write_text(json.dumps(stale_local), encoding="utf-8")
    monkeypatch.setattr("src.data.gdrive_uploader.is_configured", lambda: False)

    out = E.load_export()
    assert out == stale_local


def test_export_age_days_flags_the_stale_committed_copy():
    """Regression pin: confirms _export_age_days would have correctly flagged
    the May 27 committed export as ~stale — proving the guard itself was never
    the bug; load_export() feeding it the wrong file was."""
    stale = {"date": "2026-05-27"}
    age = E._export_age_days(stale)
    assert age is not None and age > 30
