"""Tests for src/data/ptj.py — the PTJ status tracking added after the
2026-07-15 incident where a failed Drive fetch silently rendered as an
empty (indistinguishable from genuinely-flat) held book on a real-money
export. A fetch failure must be LOUD (status != "live"), never silent.

D-84 (2026-07-2x) retired Drive as the PTJ store — fetch_latest_ptj() now reads
the latest dated journal from aegis/data/journal/ in git via github_sync,
instead of polling a Drive folder. The Drive-fixture tests below were rewritten
to mock github_sync instead of gdrive_uploader; the cache-contract tests
(status tracking, fallback-on-failure) are unchanged since they mock
fetch_latest_ptj() directly and never cared which backend it used."""

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
    monkeypatch.setattr(ptj, "_published_floor", lambda: None)
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
    monkeypatch.setattr(ptj, "_published_floor", lambda: None)
    # Seed a prior "live" cache, as if yesterday's run succeeded.
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "IBM", "qty": 111}],
        "_ptj_file": "f.json", "_ptj_modified": "t", "snapshot": "s",
    })
    ptj.refresh_held_positions()
    assert ptj.ptj_status() == "live"

    # Now simulate today's git fetch failing outright (returns None).
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: None)
    held = ptj.refresh_held_positions()
    # The prior positions are preserved (not silently wiped)...
    assert held == [{"ticker": "IBM", "qty": 111}]
    # ...but the status makes clear this was NOT a live read this run.
    assert ptj.ptj_status() == "cache_fallback"


def test_refresh_rejects_a_fetch_older_than_the_published_floor(monkeypatch):
    """2026-08-21 incident: the HF Space and the GitHub Actions backstop both
    ran the daily pipeline within seconds of each other. One fetched a stale
    journal (for reasons still under investigation) and its publish landed
    last, silently regressing the book back to a month-old snapshot. This is
    the guard that makes that class of bug impossible: a fetch is only ever
    accepted if it is at least as current as what is already published."""
    monkeypatch.setattr(ptj, "_published_floor", lambda: {
        "source_file": "aegis_journal_2026-08-20.json", "modified": "2026-08-20",
        "positions": [{"ticker": "OXY", "qty": 304}], "options": [], "status": "live",
    })
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "AMPL", "qty": 571}],
        "_ptj_file": "aegis_trade_journal_2026-07-21_PTJ.json",
        "_ptj_modified": "2026-07-21T21:23:45.099Z",
        "snapshot": None,
    })
    held = ptj.refresh_held_positions()
    # The already-published (newer) book wins, not the stale fetch.
    assert held == [{"ticker": "OXY", "qty": 304}]
    assert ptj.ptj_status() == "stale_fetch_rejected"
    cache = ptj.load_ptj_cache()
    assert cache["rejected_fetch"]["source_file"] == "aegis_trade_journal_2026-07-21_PTJ.json"


def test_refresh_accepts_a_fetch_newer_than_the_published_floor(monkeypatch):
    monkeypatch.setattr(ptj, "_published_floor", lambda: {
        "source_file": "aegis_journal_2026-08-19.json", "modified": "2026-08-19",
        "positions": [{"ticker": "OLD", "qty": 1}], "options": [], "status": "live",
    })
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "NEW", "qty": 2}],
        "_ptj_file": "aegis_journal_2026-08-20.json",
        "_ptj_modified": "2026-08-20", "snapshot": None,
    })
    held = ptj.refresh_held_positions()
    assert held == [{"ticker": "NEW", "qty": 2}]
    assert ptj.ptj_status() == "live"


def test_refresh_accepts_a_fetch_when_the_floor_is_unreadable(monkeypatch):
    """No floor (GitHub unreachable, nothing published yet) means nothing to
    enforce — the guard must never block a fetch it cannot evaluate."""
    monkeypatch.setattr(ptj, "_published_floor", lambda: None)
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "open_positions": [{"ticker": "IBM", "qty": 111}],
        "_ptj_file": "aegis_journal_2026-08-20.json",
        "_ptj_modified": "2026-08-20", "snapshot": None,
    })
    held = ptj.refresh_held_positions()
    assert held == [{"ticker": "IBM", "qty": 111}]
    assert ptj.ptj_status() == "live"


def test_refresh_fetch_failure_with_no_prior_cache_returns_empty_but_flagged(monkeypatch):
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: None)
    held = ptj.refresh_held_positions()
    assert held == []
    assert ptj.ptj_status() == "cache_fallback"


def test_load_ptj_cache_survives_missing_file(tmp_path):
    assert ptj.load_ptj_cache() == {}
    assert ptj.load_held_positions() == []


def test_journal_name_regex_matches_dated_journals_and_rejects_others():
    real_names = [
        "aegis_journal_2026-08-19.json",
        "aegis_journal_2026-08-20.json",
        "aegis_journal_2026-07-21.json",
    ]
    non_journal_names = [
        "aegis_trade_journal_ARCHIVE_master.json",
        "aegis_journal_2026-08-19.json.bak",
        "aegis_journal.json",
        "some_other_file.json",
    ]
    for name in real_names:
        assert ptj._JOURNAL_NAME_RE.match(name), name
    for name in non_journal_names:
        assert not ptj._JOURNAL_NAME_RE.match(name), name


def test_fetch_latest_ptj_picks_latest_dated_journal_by_filename(monkeypatch):
    """aegis/data/journal/ is kept to dated snapshots only by the post-market
    pipeline (the running ARCHIVE master lives at a different path entirely),
    so no archive-file-exclusion logic is needed here — but "most recent" must
    still be decided by the DATE IN THE FILENAME, not github_sync's listing
    order, since the Contents API does not guarantee any particular order."""
    list_response = {"ok": True, "files": [
        {"name": "aegis_journal_2026-08-18.json", "sha": "a", "size": 100},
        {"name": "aegis_journal_2026-08-19.json", "sha": "b", "size": 200},
    ]}
    file_by_path = {
        "aegis/data/journal/aegis_journal_2026-08-18.json":
            {"ok": True, "text": json.dumps({"date": "2026-08-18",
             "open_positions": [{"ticker": "IBM", "qty": 111, "entry": 200.0}]})},
        "aegis/data/journal/aegis_journal_2026-08-19.json":
            {"ok": True, "text": json.dumps({"date": "2026-08-19",
             "open_positions": [{"ticker": "IBM", "qty": 111, "entry": 205.0}]})},
    }

    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "list_dir", lambda path: list_response)
    monkeypatch.setattr(github_sync, "get_file", lambda path: file_by_path[path])

    result = ptj.fetch_latest_ptj()
    assert result is not None
    assert result["_ptj_file"] == "aegis_journal_2026-08-19.json"
    assert result["open_positions"][0]["entry"] == 205.0


def test_fetch_latest_ptj_maps_option_positions_to_options_field(monkeypatch):
    """The journal schema names option legs "option_positions"; the PTJ cache
    contract (refresh_held_positions) expects "options" — fetch_latest_ptj()
    must bridge that naming gap."""
    list_response = {"ok": True, "files": [
        {"name": "aegis_journal_2026-08-19.json", "sha": "b", "size": 200},
    ]}
    file_by_path = {
        "aegis/data/journal/aegis_journal_2026-08-19.json":
            {"ok": True, "text": json.dumps({
                "date": "2026-08-19",
                "open_positions": [{"ticker": "IBM", "qty": 111}],
                "option_positions": [{"ticker": "IBM", "right": "CALL"}],
            })},
    }

    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "list_dir", lambda path: list_response)
    monkeypatch.setattr(github_sync, "get_file", lambda path: file_by_path[path])

    result = ptj.fetch_latest_ptj()
    assert result["options"] == [{"ticker": "IBM", "right": "CALL"}]


def test_fetch_latest_ptj_returns_none_when_github_not_configured(monkeypatch):
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: False)
    assert ptj.fetch_latest_ptj() is None


def test_fetch_latest_ptj_returns_none_when_journal_dir_empty(monkeypatch):
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "list_dir", lambda path: {"ok": True, "files": []})
    assert ptj.fetch_latest_ptj() is None
