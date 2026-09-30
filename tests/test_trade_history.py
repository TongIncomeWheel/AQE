"""Tests for src/data/trade_history.py — piece 20's streak fact. compute_streak
is pure and tested directly; fetch_trade_journal/load_streak touch
github_sync, so those are tested only for graceful degradation (never
raising) when github_sync isn't configured or returns nothing.
"""

from __future__ import annotations

from src.data import trade_history as TH


def _trade(pnl, exit_time, tag="aegis"):
    return {"net_pnl_usd": pnl, "exit_time_utc": exit_time, "tag": tag}


def test_compute_streak_counts_trailing_same_sign_run():
    trades = [
        _trade(100, "2026-09-01T00:00:00Z"),
        _trade(-50, "2026-09-05T00:00:00Z"),
        _trade(-30, "2026-09-10T00:00:00Z"),
        _trade(-20, "2026-09-15T00:00:00Z"),
    ]
    out = TH.compute_streak(trades)
    assert out["status"] == "OK"
    assert out["streak"] == 3
    assert out["direction"] == "LOSS"


def test_compute_streak_win_direction():
    trades = [_trade(-10, "2026-09-01T00:00:00Z"), _trade(50, "2026-09-05T00:00:00Z")]
    out = TH.compute_streak(trades)
    assert out["direction"] == "WIN"
    assert out["streak"] == 1


def test_compute_streak_ignores_non_aegis_tag():
    trades = [_trade(100, "2026-09-01T00:00:00Z", tag="other")]
    out = TH.compute_streak(trades)
    assert out["status"] == "UNAVAILABLE"


def test_compute_streak_ignores_trades_with_no_pnl():
    trades = [{"net_pnl_usd": None, "exit_time_utc": "2026-09-01T00:00:00Z", "tag": "aegis"}]
    out = TH.compute_streak(trades)
    assert out["status"] == "UNAVAILABLE"


def test_compute_streak_empty_list_is_unavailable_not_an_exception():
    out = TH.compute_streak([])
    assert out["status"] == "UNAVAILABLE"


def test_compute_streak_sorts_by_exit_time_not_list_order():
    trades = [
        _trade(-10, "2026-09-10T00:00:00Z"),   # most recent, listed first
        _trade(50, "2026-09-01T00:00:00Z"),    # oldest, listed second
    ]
    out = TH.compute_streak(trades)
    assert out["direction"] == "LOSS"   # the actually-most-recent trade


def test_fetch_trade_journal_degrades_when_not_configured(monkeypatch):
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: False)
    assert TH.fetch_trade_journal() is None


def test_load_streak_degrades_when_journal_unreachable(monkeypatch):
    monkeypatch.setattr(TH, "fetch_trade_journal", lambda: None)
    out = TH.load_streak()
    assert out["status"] == "UNAVAILABLE"


def test_load_streak_reads_through_to_compute_streak(monkeypatch):
    monkeypatch.setattr(TH, "fetch_trade_journal",
                        lambda: {"trades": [_trade(10, "2026-09-01T00:00:00Z")]})
    out = TH.load_streak()
    assert out["status"] == "OK"
    assert out["streak"] == 1
