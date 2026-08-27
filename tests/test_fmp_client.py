"""Regression test for the transient-connection-drop failure class (2026-08-21,
recurred 2026-08-27): a raw `requests` network exception (ConnectionError /
RemoteDisconnected) used to propagate straight out of FMPClient._get_json
uncaught -- neither FMPError nor FMPQuotaError, so it slid right past the
per-ticker try/except in build_panel()/pull_tickers() (already proven to
handle FMPError gracefully, see test_panel_builder_held.py) and took the
ENTIRE ~800-ticker daily pull down with it, leaving panel_daily.parquet
completely unwritten for the run (the crash happened before that file's own
write step ever ran)."""

from __future__ import annotations

import requests

from src.data.fmp_client import FMPClient, FMPConfig, FMPError


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.text = ""

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload


def _client():
    return FMPClient(FMPConfig(api_key="test-key"))


def test_a_transient_connection_drop_is_retried_and_then_succeeds(monkeypatch):
    client = _client()
    monkeypatch.setattr("time.sleep", lambda *_: None)

    calls = []

    def _get(*_a, **_k):
        calls.append(1)
        if len(calls) == 1:
            raise requests.exceptions.ConnectionError(
                "Connection aborted.", requests.exceptions.RequestException("boom"))
        return _Resp(200, [{"date": "2025-01-02", "open": 1, "high": 1,
                            "low": 1, "close": 1, "volume": 1}])

    monkeypatch.setattr(client._session, "get", _get)

    df = client.get_daily_bars("AAPL")
    assert len(calls) == 2, "must retry once after a connection drop"
    assert len(df) == 1, "the successful retry's data must be returned, not lost"


def test_a_connection_drop_that_persists_becomes_a_normal_fmperror(monkeypatch):
    """Callers (build_panel/pull_tickers) already catch FMPError per-ticker and
    move on to the next ticker -- this is what makes that safety net reachable
    for a network failure instead of it crashing the whole ~800-ticker loop."""
    client = _client()
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def _get(*_a, **_k):
        raise requests.exceptions.ConnectionError("Connection aborted.")

    monkeypatch.setattr(client._session, "get", _get)

    try:
        client.get_daily_bars("AAPL")
        assert False, "must raise, not return silently"
    except FMPError as exc:
        assert not isinstance(exc, requests.exceptions.RequestException), (
            "must be converted to FMPError, not the raw requests exception -- "
            "callers only catch FMPError/FMPQuotaError, never a bare "
            "requests.RequestException"
        )


def test_a_healthy_call_never_pays_the_retry_cost(monkeypatch):
    client = _client()
    monkeypatch.setattr("time.sleep", lambda *_: (_ for _ in ()).throw(
        AssertionError("must not sleep on a call that never fails")))

    calls = []

    def _get(*_a, **_k):
        calls.append(1)
        return _Resp(200, [{"date": "2025-01-02", "open": 1, "high": 1,
                            "low": 1, "close": 1, "volume": 1}])

    monkeypatch.setattr(client._session, "get", _get)

    client.get_daily_bars("AAPL")
    assert len(calls) == 1
