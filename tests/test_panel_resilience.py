"""2026-11-10/11 incident: the panel job ran 30 min, one dropped connection right after a 429 backoff escaped as a raw requests.ConnectionError, the MA panel loop
caught only FMPError, and every bar already pulled (2,130 of 3,774 tickers) was thrown away ('0/3776 tickers carry 2026-11-10'). Two guards."""
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

from src.data import fmp_client as F
from src.scanner import ma_scanner
from src.valen import breadth as B


def test_a_connection_dropped_right_after_the_429_backoff_is_an_fmp_error_not_a_raw_exception(monkeypatch):
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Resp:
        def __init__(self, code): self.status_code, self.ok, self.text = code, code < 400, ""

    class Sess:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return Resp(429)
            raise requests.exceptions.ConnectionError("Remote end closed connection without response")

    c = F.FMPClient.__new__(F.FMPClient)
    c._session, c.config, c._ok_count = Sess(), SimpleNamespace(timeout_seconds=1, rate_limit_per_min=10 ** 6, api_key="K"), 0
    c._throttle = lambda: None
    with pytest.raises(F.FMPError, match="network error"):
        c._get_json("https://x/stable/y", {})
    assert calls["n"] == 1 + len(F.FMPClient._NETWORK_RETRY_DELAYS_S) + 1      # the 429, then the full network-retry ladder, then a clean FMPError


def test_one_ticker_raising_an_unexpected_error_never_discards_the_bars_already_pulled(monkeypatch, tmp_path):
    p = tmp_path / "ma_panel.parquet"
    monkeypatch.setattr(ma_scanner, "MA_PANEL", p)
    monkeypatch.setattr("src.data.sessions.last_completed_session", lambda now=None: date(2026, 11, 10))

    class Client:
        def get_daily_bars(self, ticker, from_date=None, to_date=None):
            if ticker == "BBB":
                raise requests.exceptions.ConnectionError("Remote end closed connection without response")
            d = pd.bdate_range(end="2026-11-10", periods=30)
            return pd.DataFrame({"date": d, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1.0})

    panel = ma_scanner.build_ma_panel(pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]}), Client(), max_runtime_seconds=None)
    assert sorted(panel["ticker"].unique()) == ["AAA", "CCC"]                   # the two good names are kept, the bad one is skipped and reported
    assert p.exists() and sorted(pd.read_parquet(p)["ticker"].unique()) == ["AAA", "CCC"]
