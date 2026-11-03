"""2026-11-03: the whole-market panel is refreshed to the last COMPLETED session, never judged by calendar days."""
from datetime import date

import pandas as pd

from src.scanner import ma_scanner, ma_refresh
from src.valen import breadth as B


class FakeClient:
    def __init__(self, bars_to):
        self.bars_to, self.calls = bars_to, []

    def get_daily_bars(self, ticker, from_date=None, to_date=None):
        self.calls.append((ticker, from_date))
        d = pd.bdate_range(start=from_date, end=self.bars_to)
        return pd.DataFrame({"date": d, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1.0})


def _panel(tmp_path, last):
    d = pd.bdate_range(end=last, periods=260)
    rows = [{"ticker": t, "date": x, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0 + 0.001 * i, "volume": 1.0}
            for t in ("AAA", "BBB", "CCC") for i, x in enumerate(d)]
    p = tmp_path / "ma_panel.parquet"
    pd.DataFrame(rows).to_parquet(p, index=False)
    return p


def _patch(monkeypatch, tmp_path, expected):
    p = _panel(tmp_path, "2026-10-30")
    monkeypatch.setattr(ma_scanner, "MA_PANEL", p)
    monkeypatch.setattr("src.data.sessions.last_completed_session", lambda now=None: date.fromisoformat(expected))
    monkeypatch.setattr(B, "_expected_last_session", lambda: expected)
    monkeypatch.setattr(B, "ensure_ma_panel", lambda path: pd.read_parquet(path))
    return p


def test_a_panel_one_session_behind_is_refreshed_not_skipped_as_current(monkeypatch, tmp_path):
    """The old skip rule (last >= today - 1 calendar day) called Fri 30 Oct current on Tue 3 Nov's morning."""
    p = _patch(monkeypatch, tmp_path, "2026-11-02")
    uni = pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]})
    c = FakeClient("2026-11-02")
    panel = ma_scanner.build_ma_panel(uni, c, max_runtime_seconds=None)
    assert len(c.calls) == 3, c.calls                            # every ticker was behind, every ticker pulled
    assert str(pd.to_datetime(panel["date"]).max().date()) == "2026-11-02"
    assert not B.freshness(panel, "2026-11-02")["stale"]


def test_a_current_panel_costs_no_calls(monkeypatch, tmp_path):
    p = _patch(monkeypatch, tmp_path, "2026-10-30")
    uni = pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]})
    c = FakeClient("2026-10-30")
    ma_scanner.build_ma_panel(uni, c)
    assert c.calls == []


def test_refresh_for_breadth_reports_fresh_refreshed_partial_and_never_raises(monkeypatch, tmp_path):
    p = _patch(monkeypatch, tmp_path, "2026-11-02")
    uni = pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"]})
    monkeypatch.setattr(ma_scanner, "get_ma_universe", lambda client=None: uni)
    r = ma_refresh.refresh_for_breadth(60, client=FakeClient("2026-11-02"), panel_path=p, expected="2026-11-02")
    assert r["status"] == "REFRESHED" and r["after"]["share_current"] == 1.0, r
    r2 = ma_refresh.refresh_for_breadth(60, client=FakeClient("2026-11-02"), panel_path=p, expected="2026-11-02")
    assert r2["status"] == "FRESH" and "0" not in str(r2.get("reason") or "")
    # a refresh that cannot reach the new session (feed has nothing newer) leaves the panel STALE and says PARTIAL, loudly
    p = _panel(tmp_path, "2026-10-30")
    r3 = ma_refresh.refresh_for_breadth(60, client=FakeClient("2026-10-30"), panel_path=p, expected="2026-11-02")
    assert r3["status"] == "PARTIAL" and "2026-11-02" in r3["reason"]
    # a broken environment is a FAILED result with a reason, not an exception
    monkeypatch.setattr(B, "ensure_ma_panel", lambda path: (_ for _ in ()).throw(RuntimeError("boom")))
    r4 = ma_refresh.refresh_for_breadth(60, client=FakeClient("2026-11-02"), panel_path=p, expected="2026-11-02")
    assert r4["status"] == "FAILED" and "boom" in r4["reason"]
    assert "FAILED" in ma_refresh.summary_line(r4)
