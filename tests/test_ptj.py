"""Tests for src/data/ptj.py — the PTJ status tracking added after the
2026-07-15 incident where a failed Drive fetch silently rendered as an
empty (indistinguishable from genuinely-flat) held book on a real-money
export. A fetch failure must be LOUD (status != "live"), never silent."""

from __future__ import annotations

import json

import pytest

from src.data import ptj


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "held_positions.json"
    monkeypatch.setattr(ptj, "PTJ_CACHE", cache_path)
    monkeypatch.setattr(ptj, "OUTPUT_DIR", tmp_path)
    yield cache_path


def test_ptj_status_unknown_when_no_cache_ever_written():
    assert ptj.ptj_status() == "unknown"


def test_refresh_live_fetch_success_marks_status_live(monkeypatch):
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "IBM", "qty": 111}],
        "_ptj_file": "aegis_trade_journal_x.json",
        "_ptj_modified": "2026-07-15T01:28:56Z",
        "snapshot": "2026-07-15 09:28 SGT",
    })
    held = ptj.refresh_held_positions()
    assert held == [{"ticker": "IBM", "qty": 111}]
    assert ptj.ptj_status() == "live"
    assert ptj.load_held_positions() == held


def test_refresh_fetch_failure_falls_back_but_flags_cache_fallback(monkeypatch):
    # Seed a prior "live" cache, as if yesterday's run succeeded.
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "IBM", "qty": 111}],
        "_ptj_file": "f.json", "_ptj_modified": "t", "snapshot": "s",
    })
    ptj.refresh_held_positions()
    assert ptj.ptj_status() == "live"

    # Now simulate today's Drive fetch failing outright (returns None).
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: None)
    held = ptj.refresh_held_positions()
    # The prior positions are preserved (not silently wiped)...
    assert held == [{"ticker": "IBM", "qty": 111}]
    # ...but the status makes clear this was NOT a live read this run.
    assert ptj.ptj_status() == "cache_fallback"


def test_refresh_fetch_failure_with_no_prior_cache_returns_empty_but_flagged(monkeypatch):
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: None)
    held = ptj.refresh_held_positions()
    assert held == []
    assert ptj.ptj_status() == "cache_fallback"


def test_load_ptj_cache_survives_missing_file(tmp_path):
    assert ptj.load_ptj_cache() == {}
    assert ptj.load_held_positions() == []


class _FakeFilesList:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeGetMedia:
    def __init__(self, content):
        self._content = content

    def execute(self):
        return self._content


class _FakeFiles:
    """Stub for service.files() — routes list()/get_media() to fixtures."""

    def __init__(self, list_response, content_by_id):
        self._list_response = list_response
        self._content_by_id = content_by_id

    def list(self, **kwargs):
        return _FakeFilesList(self._list_response)

    def get_media(self, fileId):
        return _FakeGetMedia(self._content_by_id[fileId])


class _FakeService:
    def __init__(self, list_response, content_by_id):
        self._files = _FakeFiles(list_response, content_by_id)

    def files(self):
        return self._files


def test_fetch_latest_ptj_skips_archive_file_with_newer_modtime(monkeypatch):
    """Regression for the 2026-07-16 incident: an ARCHIVE_master.json summary
    (open_positions stripped of entry/livePx) landed in the SAME top-level PTJ
    folder with a NEWER modifiedTime than the actual daily journal, so
    "most-recently-modified file wins" picked the archive and every held
    position shipped with entry=null. The filename shape filter must reject it."""
    list_response = {"files": [
        {"id": "archive1", "name": "aegis_trade_journal_ARCHIVE_master.json",
         "modifiedTime": "2026-07-15T23:32:27.272Z", "mimeType": "application/json"},
        {"id": "real1", "name": "aegis_trade_journal_2026-07-15_v2.9.2_INTRADAY",
         "modifiedTime": "2026-07-15T15:34:01.825Z", "mimeType": "application/json"},
    ]}
    content_by_id = {
        "archive1": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111}]}),
        "real1": json.dumps({"open_positions": [
            {"ticker": "IBM", "qty": 111, "entry": 263.14, "livePx": 216.97},
        ]}),
    }

    from src.data import gdrive_uploader
    monkeypatch.setattr(gdrive_uploader, "is_configured", lambda: True)
    monkeypatch.setattr(gdrive_uploader.DriveConfig, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        gdrive_uploader, "_build_service",
        lambda cfg: _FakeService(list_response, content_by_id),
    )

    result = ptj.fetch_latest_ptj()
    assert result is not None
    assert result["_ptj_file"] == "aegis_trade_journal_2026-07-15_v2.9.2_INTRADAY"
    assert result["open_positions"][0]["entry"] == 263.14
    assert result["open_positions"][0]["livePx"] == 216.97


def test_ptj_name_regex_matches_real_journals_and_rejects_artifacts():
    real_names = [
        # New convention (PM ruling 2026-07-16): dated CoB snapshots, accumulate.
        "aegis_trade_journal_2026-07-16_PTJ.json",
        "aegis_trade_journal_2026-07-17_PTJ.json",
        # Pre-2026-07-16 versioned shape — still accepted for continuity.
        "aegis_trade_journal_2026-07-14_v2.9.1_CORRECTED.json",
        "aegis_trade_journal_2026-07-15_v2.9.2_INTRADAY",
        "aegis_trade_journal_2026-06-08_v2.8_eod_sync",
    ]
    non_journal_names = [
        "aegis_trade_journal_ARCHIVE_master.json",
        "aegis_trade_journal_ARCHIVE_master",
        "some_other_file.json",
    ]
    for name in real_names:
        assert ptj._PTJ_NAME_RE.match(name), name
    for name in non_journal_names:
        assert not ptj._PTJ_NAME_RE.match(name), name


def test_fetch_latest_ptj_uses_new_ptj_naming_convention(monkeypatch):
    """The PM's new standing convention: aegis_trade_journal_YYYY-MM-DD_PTJ.json,
    dated CoB snapshots that accumulate (never overwritten), vs the ARCHIVE
    master which overwrites daily and must always be ignored."""
    list_response = {"files": [
        {"id": "archive1", "name": "aegis_trade_journal_ARCHIVE_master.json",
         "modifiedTime": "2026-07-17T23:59:59.000Z", "mimeType": "application/json"},
        {"id": "ptj_16", "name": "aegis_trade_journal_2026-07-16_PTJ.json",
         "modifiedTime": "2026-07-16T09:00:00.000Z", "mimeType": "application/json"},
        {"id": "ptj_17", "name": "aegis_trade_journal_2026-07-17_PTJ.json",
         "modifiedTime": "2026-07-17T09:00:00.000Z", "mimeType": "application/json"},
    ]}
    content_by_id = {
        "archive1": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111}]}),
        "ptj_16": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111, "entry": 200.0}]}),
        "ptj_17": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111, "entry": 205.0}]}),
    }
    from src.data import gdrive_uploader
    monkeypatch.setattr(gdrive_uploader, "is_configured", lambda: True)
    monkeypatch.setattr(gdrive_uploader.DriveConfig, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        gdrive_uploader, "_build_service",
        lambda cfg: _FakeService(list_response, content_by_id),
    )

    result = ptj.fetch_latest_ptj()
    assert result["_ptj_file"] == "aegis_trade_journal_2026-07-17_PTJ.json"
    assert result["open_positions"][0]["entry"] == 205.0


def test_fetch_latest_ptj_sorts_by_filename_date_not_raw_modtime(monkeypatch):
    """Extra safety guard (2026-07-16 ruling): the date IN THE FILENAME is the
    primary sort key, not Drive's modifiedTime alone — so a metadata quirk
    (e.g. an older-dated file re-saved/touched later, bumping its
    modifiedTime) can't make a stale journal look newest."""
    list_response = {"files": [
        # Older calendar date, but a LATER modifiedTime than the real latest.
        {"id": "stale", "name": "aegis_trade_journal_2026-07-15_PTJ.json",
         "modifiedTime": "2026-07-17T23:00:00.000Z", "mimeType": "application/json"},
        {"id": "actual_latest", "name": "aegis_trade_journal_2026-07-16_PTJ.json",
         "modifiedTime": "2026-07-16T09:00:00.000Z", "mimeType": "application/json"},
    ]}
    content_by_id = {
        "stale": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111, "entry": 199.0}]}),
        "actual_latest": json.dumps({"open_positions": [{"ticker": "IBM", "qty": 111, "entry": 201.0}]}),
    }
    from src.data import gdrive_uploader
    monkeypatch.setattr(gdrive_uploader, "is_configured", lambda: True)
    monkeypatch.setattr(gdrive_uploader.DriveConfig, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        gdrive_uploader, "_build_service",
        lambda cfg: _FakeService(list_response, content_by_id),
    )

    result = ptj.fetch_latest_ptj()
    assert result["_ptj_file"] == "aegis_trade_journal_2026-07-16_PTJ.json"
    assert result["open_positions"][0]["entry"] == 201.0
