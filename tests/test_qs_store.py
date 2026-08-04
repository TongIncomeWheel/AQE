"""QS memory tests.

The important behaviour here is `get_qs_persist`. It reads the last N
DISTINCT STORED DATES before the run date, not the last N calendar days — a
market holiday is not a day a name failed to qualify. Getting that wrong
would quietly deflate persist across every long weekend, pushing names into a
lower persist band and re-pricing the book, with nothing in the output looking
wrong.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data import qs_store


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Point the store at a throwaway db so tests never touch the real aqe.db."""
    monkeypatch.setattr(qs_store, "DB_PATH", tmp_path / "test_aqe.db")
    qs_store.init_qs_tables()
    yield


def _hits(date, mapping, eligible=True):
    return pd.DataFrame([
        {"date": date, "ticker": t, "recipe_hits": h,
         "lens_total": 6.0, "eligible": eligible}
        for t, h in mapping.items()])


# ----------------------------------------------------------------- hits

def test_upsert_and_read_back():
    n = qs_store.upsert_daily_hits(_hits("2026-07-20", {"AAA": 5, "BBB": 1}))
    assert n == 2
    df = qs_store.get_hits_history()
    assert set(df.ticker) == {"AAA", "BBB"}


def test_rerunning_a_date_overwrites_rather_than_duplicates():
    qs_store.upsert_daily_hits(_hits("2026-07-20", {"AAA": 5}))
    qs_store.upsert_daily_hits(_hits("2026-07-20", {"AAA": 9}))
    df = qs_store.get_hits_history(ticker="AAA")
    assert len(df) == 1 and int(df.recipe_hits.iloc[0]) == 9


def test_empty_frame_is_a_noop():
    assert qs_store.upsert_daily_hits(pd.DataFrame()) == 0


# -------------------------------------------------------------- persist

def test_persist_counts_only_days_at_or_above_the_qs_threshold():
    for d, h in (("2026-07-14", 5), ("2026-07-15", 2), ("2026-07-16", 3),
                 ("2026-07-17", 9), ("2026-07-18", 0)):
        qs_store.upsert_daily_hits(_hits(d, {"AAA": h}))
    # hits >= 3 on 07-14, 07-16, 07-17 -> 3
    assert qs_store.get_qs_persist("2026-07-20")["AAA"] == 3


def test_persist_excludes_the_run_date_itself():
    qs_store.upsert_daily_hits(_hits("2026-07-14", {"AAA": 9}))
    qs_store.upsert_daily_hits(_hits("2026-07-20", {"AAA": 9}))
    # only 07-14 is prior; today must not count itself
    assert qs_store.get_qs_persist("2026-07-20")["AAA"] == 1


def test_persist_uses_stored_sessions_not_calendar_days():
    """A holiday gap must not shrink the window.

    Five stored sessions spanning three weeks still give a full 5-day window;
    counting calendar days back would see only the recent ones.
    """
    for d in ("2026-06-29", "2026-07-06", "2026-07-13",
              "2026-07-14", "2026-07-15"):
        qs_store.upsert_daily_hits(_hits(d, {"AAA": 9}))
    assert qs_store.get_qs_persist("2026-07-20")["AAA"] == 5


def test_persist_window_is_capped_at_five_sessions():
    for d in ("2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09",
              "2026-07-10", "2026-07-13", "2026-07-14"):
        qs_store.upsert_daily_hits(_hits(d, {"AAA": 9}))
    assert qs_store.get_qs_persist("2026-07-20")["AAA"] == 5


def test_ticker_absent_on_a_prior_date_scores_zero_for_it():
    qs_store.upsert_daily_hits(_hits("2026-07-14", {"AAA": 9}))
    qs_store.upsert_daily_hits(_hits("2026-07-15", {"AAA": 9, "NEW": 9}))
    p = qs_store.get_qs_persist("2026-07-20")
    assert p["AAA"] == 2 and p["NEW"] == 1


def test_no_history_returns_empty_not_an_error():
    assert qs_store.get_qs_persist("2026-07-20") == {}


# --------------------------------------------------------------- regime

def test_regime_series_roundtrip():
    df = pd.DataFrame([
        {"date": "2026-07-20", "trend_200": 0.08, "vol_60": 0.19,
         "t_tercile": 3, "v_tercile": 3, "regime_cell": "T3V3"}])
    assert qs_store.upsert_regime_series(df) == 1
    assert qs_store.get_regime_cell("2026-07-20") == "T3V3"
    out = qs_store.get_regime_series()
    assert len(out) == 1 and out.regime_cell.iloc[0] == "T3V3"


def test_unknown_date_is_unclassified_not_a_guess():
    assert qs_store.get_regime_cell("2099-01-01") == "unclassified"


def test_regime_handles_nan_terciles():
    """Early dates have trend_200 but no tercile yet — must not crash."""
    df = pd.DataFrame([
        {"date": "2026-01-05", "trend_200": float("nan"),
         "vol_60": float("nan"), "t_tercile": float("nan"),
         "v_tercile": float("nan"), "regime_cell": "unclassified"}])
    assert qs_store.upsert_regime_series(df) == 1
    assert qs_store.get_regime_cell("2026-01-05") == "unclassified"


# --------------------------------------------------------------- status

def test_status_reports_persist_readiness():
    """After a container recycle this is what says 'memory is thin'."""
    assert qs_store.store_status()["persist_ready"] is False
    for d in ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
              "2026-07-17"):
        qs_store.upsert_daily_hits(_hits(d, {"AAA": 9}))
    st = qs_store.store_status()
    assert st["persist_ready"] is True
    assert st["hits_dates"] == 5 and st["hits_to"] == "2026-07-17"


def test_qs_db_is_the_file_persist_already_snapshots():
    """QS memory must ride the existing snapshot, not need a new one."""
    from src.data import persist
    arcs = [arc for _, arc in persist._members()]
    assert "data/aqe.db" in arcs
