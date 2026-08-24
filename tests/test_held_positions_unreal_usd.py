"""Test for held_positions[].unreal_usd — PM ruling 2026-07-29, wired
2026-08-21. The Aegis journal's own unrealised-P&L field was retired in its
D-84 restructure (2026-07-28), so this reader used to always read None from a
key nothing writes anymore. AQE already has qty, entry, and live_px on the
exact same record; there was no reason to keep leaving this null."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pytest

from src.data import drive_sync


@pytest.fixture(autouse=True)
def _stub_v21(monkeypatch, tmp_path):
    # _build_held_positions() pulls in the full per-ticker AQE read via
    # _v21_record_fields and indexes many of its keys directly (v21["x"]) —
    # irrelevant to this test, which only cares about unreal_usd. A
    # defaultdict(None) answers every v21["anything"] with None without
    # having to enumerate every field the surrounding code touches.
    def _stub(tk, d, lk, sm, sector_grades, regime_level=None):
        v21 = defaultdict(lambda: None)
        v21["bracket"] = {"targets": []}
        return v21
    monkeypatch.setattr(drive_sync, "_v21_record_fields", _stub)
    from src.data import paths
    monkeypatch.setattr(paths, "SCORES_DAILY", tmp_path / "scores_daily.parquet")
    yield


def _score_row(ticker: str, close: float):
    from src.data.paths import SCORES_DAILY
    pd.DataFrame({"date": ["2026-08-21"], "ticker": [ticker], "close": [close]}
                ).to_parquet(SCORES_DAILY, index=False)


def test_unreal_usd_is_qty_times_live_px_minus_entry():
    _score_row("IBM", close=215.0)
    held = [{"ticker": "IBM", "qty": 100, "entry": 200.0, "type": "STK"}]

    out = drive_sync._build_held_positions(held, {}, {}, {}, {}, {})

    assert out[0]["unreal_usd"] == pytest.approx(1500.0)  # 100 * (215 - 200)
    assert out[0]["live_px"] == 215.0
    assert out[0]["entry"] == 200.0


def test_unreal_usd_is_negative_when_underwater():
    _score_row("IBM", close=180.0)
    held = [{"ticker": "IBM", "qty": 100, "entry": 200.0, "type": "STK"}]

    out = drive_sync._build_held_positions(held, {}, {}, {}, {}, {})

    assert out[0]["unreal_usd"] == pytest.approx(-2000.0)  # 100 * (180 - 200)


def test_unreal_usd_is_null_not_wrong_when_live_px_is_unavailable():
    """No score row for the ticker means no live_px — must stay null, never a
    garbage number computed from a missing price."""
    held = [{"ticker": "GHOST", "qty": 100, "entry": 200.0, "type": "STK"}]

    out = drive_sync._build_held_positions(held, {}, {}, {}, {}, {})

    assert out[0]["live_px"] is None
    assert out[0]["unreal_usd"] is None
