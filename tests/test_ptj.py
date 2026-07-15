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
