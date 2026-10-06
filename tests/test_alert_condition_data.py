"""Tests for src/alerts/condition_data.py (AQE handoff D123/R21,
2026-10-02 §3/§4.1) -- the volume-profile cache and intraday bar pulls.
"""

from __future__ import annotations

from datetime import date

from src.alerts import condition_data as CD


class _FakeClient:
    def __init__(self):
        self.calls: list[tuple] = []

    def get_intraday_bars(self, ticker, interval="15min", from_date=None, to_date=None):
        self.calls.append((ticker, interval, from_date, to_date))
        return [{"date": "2026-09-01 09:30:00", "open": 100, "high": 101,
                "low": 99, "close": 100.5, "volume": 1000}]


def test_ensure_volume_profiles_builds_only_missing_tickers(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    client = _FakeClient()
    today = date(2026, 10, 2)
    CD.ensure_volume_profiles(client, ["A", "B"], today)
    assert len(client.calls) == 2

    # Second call for the SAME day, overlapping tickers -> only the new
    # ticker triggers a fetch; A and B are already cached.
    CD.ensure_volume_profiles(client, ["A", "B", "C"], today)
    assert len(client.calls) == 3
    assert client.calls[-1][0] == "C"


def test_ensure_volume_profiles_caches_empty_on_fetch_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")

    class _BoomClient:
        def get_intraday_bars(self, *a, **k):
            raise RuntimeError("fmp down")

    profiles = CD.ensure_volume_profiles(_BoomClient(), ["X"], date(2026, 10, 2))
    assert profiles["X"] == {}


def test_profiles_persist_across_cache_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    client = _FakeClient()
    today = date(2026, 10, 2)
    CD.ensure_volume_profiles(client, ["A"], today)
    reloaded = CD.load_cached_profiles(today.isoformat())
    assert "A" in reloaded
    assert all(isinstance(k, int) for k in reloaded["A"])


def test_load_cached_profiles_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    assert CD.load_cached_profiles("2026-10-02") == {}


def test_fetch_today_bars_returns_empty_on_failure():
    class _BoomClient:
        def get_intraday_bars(self, *a, **k):
            raise RuntimeError("fmp down")

    assert CD.fetch_today_bars(_BoomClient(), "X", date(2026, 10, 2)) == []


def test_fetch_today_bars_passes_through():
    client = _FakeClient()
    bars = CD.fetch_today_bars(client, "X", date(2026, 10, 2))
    assert len(bars) == 1
    assert client.calls[0][0] == "X"
