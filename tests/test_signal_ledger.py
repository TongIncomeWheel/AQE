"""Tests for the signal ledger — append-only daily signal archive."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    """Redirect the ledger to a temp database."""
    db = tmp_path / "test_aqe.db"
    with patch("src.data.signal_ledger.DB_PATH", db):
        yield db


def _make_export(scan_date="2026-06-25", longlist=None, elder_list=None):
    return {
        "date": scan_date,
        "longlist": longlist or [],
        "elder_list": elder_list or [],
    }


def _rec(ticker, sc=70, ptrs=65, elder=8, close=100.0, **kw):
    return {
        "ticker": ticker, "sc_momentum": sc, "sc_momentum_raw": sc,
        "ptrs": ptrs, "elder": elder, "close": close,
        "flow": 80, "energy": 70, "structure": 65, "mp": 60, "bq": 55,
        "mp_state": "BULLISH", "on_longlist": True, "pe": False,
        "rd_score": kw.get("rd_score", 42), "rd_state": "WATCH",
        "hl_score": kw.get("hl_score", 68), "hl_state": "HOLD",
        "gics_sector": "XLK", "gics_gate": "PASS",
        "entry": close, "dsl_stop": close * 0.93,
        "dsl_risk": close * 0.07,
        "dsl_tp_1r": close * 1.07, "dsl_tp_2r": close * 1.14,
        **kw,
    }


def test_record_signals_basic():
    from src.data.signal_ledger import record_signals, ledger_stats

    export = _make_export(
        longlist=[_rec("AAPL"), _rec("MSFT")],
        elder_list=[_rec("NVDA", elder=9)],
    )
    n = record_signals(export)
    assert n == 3

    stats = ledger_stats()
    assert stats["snapshots"] == 3
    assert stats["outcomes"] == 3
    assert stats["unique_tickers"] == 3
    assert stats["unique_dates"] == 1


def test_record_signals_dedup():
    from src.data.signal_ledger import record_signals, ledger_stats

    export = _make_export(longlist=[_rec("AAPL"), _rec("AAPL")])
    n = record_signals(export)
    assert n == 1  # dedup'd

    stats = ledger_stats()
    assert stats["snapshots"] == 1


def test_record_signals_idempotent():
    from src.data.signal_ledger import record_signals, ledger_stats

    export = _make_export(longlist=[_rec("AAPL")])
    record_signals(export)
    record_signals(export)  # re-run same day

    stats = ledger_stats()
    assert stats["snapshots"] == 1  # INSERT OR REPLACE


def test_backfill_outcomes(tmp_path, _tmp_db):
    from src.data.signal_ledger import record_signals, backfill_outcomes, get_signal_history

    export = _make_export(
        scan_date="2026-06-01",
        longlist=[_rec("AAPL", close=190.0)],
    )
    record_signals(export)

    dates = pd.bdate_range("2026-06-01", periods=25)
    prices = [190.0 + i * 0.5 for i in range(25)]
    highs = [p + 2.0 for p in prices]
    lows = [p - 1.5 for p in prices]

    panel = pd.DataFrame({
        "date": dates,
        "ticker": "AAPL",
        "close": prices,
        "high": highs,
        "low": lows,
    })
    panel_path = tmp_path / "panel.parquet"
    try:
        panel.to_parquet(panel_path, index=False)
    except ImportError:
        pytest.skip("pyarrow not installed — parquet backfill test skipped")

    n = backfill_outcomes(panel_path)
    assert n == 1

    history = get_signal_history(ticker="AAPL")
    assert len(history) == 1
    row = history.iloc[0]
    assert row["ret_t5"] is not None
    assert row["ret_t10"] is not None
    assert row["ret_t20"] is not None
    assert row["ret_t5"] > 0  # prices are rising


def test_get_hit_rates_empty():
    from src.data.signal_ledger import get_hit_rates

    rates = get_hit_rates()
    assert rates["n"] == 0


def test_multi_day_signals():
    from src.data.signal_ledger import record_signals, ledger_stats

    for d in ("2026-06-23", "2026-06-24", "2026-06-25"):
        export = _make_export(scan_date=d, longlist=[_rec("AAPL"), _rec("MSFT")])
        record_signals(export)

    stats = ledger_stats()
    assert stats["snapshots"] == 6  # 2 tickers × 3 days
    assert stats["unique_dates"] == 3


def test_signal_history_filters():
    from src.data.signal_ledger import record_signals, get_signal_history

    record_signals(_make_export(
        scan_date="2026-06-20",
        longlist=[_rec("AAPL")],
        elder_list=[_rec("NVDA")],
    ))
    record_signals(_make_export(
        scan_date="2026-06-25",
        longlist=[_rec("MSFT")],
    ))

    all_rows = get_signal_history()
    assert len(all_rows) == 3

    aapl = get_signal_history(ticker="AAPL")
    assert len(aapl) == 1
    assert aapl.iloc[0]["ticker"] == "AAPL"

    longlist_only = get_signal_history(list_source="longlist")
    assert len(longlist_only) == 2

    recent = get_signal_history(from_date="2026-06-24")
    assert len(recent) == 1
    assert recent.iloc[0]["ticker"] == "MSFT"
