"""QS daily-run tests — eligibility, regime resolution, and loud degradation.

The theme: QS is an ADDITION to a working real-money pipeline. It must never
raise into the orchestrator, and it must never return an empty list that looks
like "nothing qualified" when the truth is "nothing was checked".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import qs_daily as QD
from src.engines import qs_spec as S


def _panel(n_days=30, tickers=("AAA", "BBB", "CCC"), seed=5):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-06-01", periods=n_days)
    rows = []
    for tk in tickers:
        for d in dates:
            rows.append({"date": d, "ticker": tk,
                         "close": float(rng.uniform(20, 100)),
                         "volume": float(rng.uniform(1e6, 2e6))})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- eligibility

def test_eligible_requires_volume_above_own_ten_day_average():
    p = _panel()
    last = p["date"].max()
    # AAA gets a huge final-day volume; BBB a tiny one.
    p.loc[(p.ticker == "AAA") & (p.date == last), "volume"] = 1e9
    p.loc[(p.ticker == "BBB") & (p.date == last), "volume"] = 1.0
    elig = QD.eligible_tickers(p, last)
    assert "AAA" in elig and "BBB" not in elig


def test_ticker_without_enough_history_is_excluded_not_assumed():
    """The rule is a positive test; an unmeasurable name must not be admitted.

    Admitting it would place it in the cross-section that defines every other
    name's percentile.
    """
    p = _panel()
    last = p["date"].max()
    short = pd.DataFrame([{"date": last, "ticker": "NEW",
                           "close": 10.0, "volume": 9e9}])
    assert "NEW" not in QD.eligible_tickers(pd.concat([p, short]), last)


def test_ticker_missing_todays_bar_is_excluded():
    p = _panel()
    last = p["date"].max()
    p = p[~((p.ticker == "CCC") & (p.date == last))]
    assert "CCC" not in QD.eligible_tickers(p, last)


# ----------------------------------------------------------------- regime

def test_regime_resolves_from_the_book():
    book = {"regimes": {"T3V3": {"desc": "Hot, fast, wild bull run",
                                 "stance": "PRESS_EXPECT_WHIPSAW",
                                 "base_rate_test": 0.446}}}
    row = pd.Series({"regime_cell": "T3V3", "trend_200": 0.08, "vol_60": 0.2})
    r = QD.resolve_regime(book, row)
    assert r["cell"] == "T3V3" and r["base_rate_test"] == 0.446
    assert r["stance"] == "PRESS_EXPECT_WHIPSAW"


def test_unknown_regime_falls_back_to_unclassified():
    r = QD.resolve_regime({"regimes": {}}, None)
    assert r["cell"] == "unclassified" and r["base_rate_test"] is None


def test_market_block_flags_an_unmeasured_base_rate():
    """T1V1 and unclassified have no measured base rate — say so, don't imply one."""
    r = QD.resolve_regime({"regimes": {"T1V1": {"desc": "Drifting",
                                                "stance": "NEUTRAL"}}},
                          pd.Series({"regime_cell": "T1V1"}))
    m = QD.market_block(r)
    assert m["base_rate_measured"] is False
    assert m["avg_stock_hits_target"] is None


def test_market_block_carries_the_stance_action_line():
    r = QD.resolve_regime(
        {"regimes": {"T3V1": {"desc": "Calm melt-up", "stance": "STAND_DOWN",
                              "base_rate_test": 0.443}}},
        pd.Series({"regime_cell": "T3V1"}))
    m = QD.market_block(r)
    assert m["stance"] == "STAND_DOWN"
    assert m["action"] == S.STANCE_ACTION["STAND_DOWN"]


# ------------------------------------------------------- loud degradation

def test_missing_parquets_fail_loudly_rather_than_returning_empty(monkeypatch):
    """The distinction the PM must be able to make: outage vs quiet market."""
    monkeypatch.setattr(QD, "PANEL_DAILY", QD.PANEL_DAILY.parent / "nope.parquet")
    r = QD.run()
    assert r["ok"] is False
    assert r["status"] == "error"
    assert "missing" in r["reason"]
    assert r["rows"] == {}


def test_run_never_raises_even_on_a_corrupt_config(monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    monkeypatch.setattr(QD, "RECIPE_BOOK_PATH", bad)
    r = QD.run()          # must not raise into the orchestrator
    assert r["ok"] is False and r["status"] == "error"


def test_frozen_config_loads_and_is_intact():
    book, cal = QD.load_config()
    assert len(book["recipes"]) == 40
    assert len(cal["buckets_persist"]) == 35 and len(cal["buckets"]) == 16
    assert cal["persist_window"] == S.PERSIST_WINDOW


def test_fail_dict_has_the_shape_callers_expect():
    r = QD._fail("boom")
    for k in ("ok", "status", "reason", "market", "rows",
              "eligible_count", "scored_count", "emitted_count"):
        assert k in r
    assert r["ok"] is False
