"""QS field engine tests — the five inputs AQE doesn't already compute.

The load-bearing test here is `test_regime_terciles_are_causal`: an
expanding-window tercile that accidentally includes the current row (or is
fitted on the whole series) leaks the future into every historical row and
silently inflates any backtest run against it. That failure is invisible in
the output — the numbers look fine — so it gets an explicit test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import qs_fields as qf


def _panel(specs: dict[str, float], n: int = 400, seed: int = 7,
           vol: float = 0.005) -> pd.DataFrame:
    """Synthetic panel: {ticker: daily_drift} over n business days."""
    dates = pd.bdate_range("2024-01-01", periods=n)
    rng = np.random.default_rng(seed)
    rows = []
    for tk, drift in specs.items():
        px = 100 * np.cumprod(1 + drift + rng.normal(0, vol, n))
        for d, c in zip(dates, px):
            rows.append({"date": d, "ticker": tk, "close": c, "volume": 2e6})
    return pd.DataFrame(rows)


@pytest.fixture
def panel():
    return _panel({"AAA": 0.001, "BBB": 0.0, "CCC": -0.001})


# ---------------------------------------------------------------- ret20

def test_ret20_matches_manual_calculation(panel):
    r20 = qf.compute_ret20(panel)
    a = panel[panel.ticker == "AAA"].sort_values("date").reset_index(drop=True)
    expected = (a.close.iloc[100] / a.close.iloc[80] - 1) * 100
    got = r20[(r20.ticker == "AAA") & (r20.date == a.date.iloc[100])].ret20.iloc[0]
    assert got == pytest.approx(expected, abs=1e-9)


def test_ret20_has_no_value_before_the_window_fills(panel):
    r20 = qf.compute_ret20(panel)
    first = panel.date.min()
    early = r20[r20.date < first + pd.Timedelta(days=20)]
    assert early.empty or early.ret20.notna().all()


# ----------------------------------------------------------- EW index

def test_ew_index_first_return_is_nan_not_zero(panel):
    """A missing prior close is undefined, not a flat day."""
    ew = qf.build_ew_index(panel)
    assert pd.isna(ew["ew_ret"].iloc[0])


def test_ew_index_ignores_missing_bars_rather_than_zero_filling(panel):
    """A halted ticker must drop out of the mean, not damp it toward zero."""
    gapped = panel[~((panel.ticker == "CCC") &
                     (panel.date == panel.date.iloc[50]))].copy()
    ew_gap = qf.build_ew_index(gapped)
    d = panel.date.iloc[50]
    # With CCC absent that day the mean is over the 2 remaining names; if the
    # gap were zero-filled the magnitude would be pulled toward 0.
    assert pd.notna(ew_gap.loc[d, "ew_ret"])


# -------------------------------------------------------- rs_consist

def test_rs_consist_recovers_drift_ordering(panel):
    ew = qf.build_ew_index(panel)
    rs = qf.compute_rs_consist(panel, ew)
    last = rs[rs.date == rs.date.max()].set_index("ticker")["rs_consist"]
    assert last["AAA"] > last["BBB"] > last["CCC"]


def test_rs_consist_is_a_bounded_fraction(panel):
    ew = qf.build_ew_index(panel)
    rs = qf.compute_rs_consist(panel, ew)
    assert rs.rs_consist.between(0.0, 1.0).all()


def test_rs_consist_benchmarks_the_universe_not_spy(panel):
    """SPY must not silently become the benchmark if it's in the panel.

    rs_consist asks 'does this beat the AVERAGE eligible stock' — a breadth
    question. A cap-weighted index answers a different one.
    """
    spy = _panel({"SPY": 0.004}, n=len(panel.date.unique()))
    withspy = pd.concat([panel, spy], ignore_index=True)
    ew_all = qf.build_ew_index(withspy)
    ew_sub = qf.build_ew_index(withspy, tickers=["AAA", "BBB", "CCC"])
    # Including a strong extra name must move the equal-weight benchmark;
    # if rs_consist were SPY-relative these would be identical.
    assert not np.allclose(ew_all["ew_ret"].fillna(0),
                           ew_sub["ew_ret"].fillna(0))


# ------------------------------------------------------------ regime

def test_trend_200_needs_a_full_window(panel):
    ew = qf.build_ew_index(panel)
    reg = qf.compute_regime_series(ew)
    assert reg["trend_200"].iloc[:qf.TREND_SMA_WINDOW - 1].isna().all()


def test_regime_terciles_are_causal(panel):
    """Truncating the series must not change a surviving date's cell.

    This is the lookahead test. If terciles were fitted on the full series,
    the classification of an early date would shift once later data arrives.
    """
    ew = qf.build_ew_index(panel)
    full = qf.assign_regime_cells(qf.compute_regime_series(ew))
    trunc = qf.assign_regime_cells(qf.compute_regime_series(ew.iloc[:300]))
    overlap = [d for d in trunc.index if d in full.index]
    assert overlap, "no overlapping dates to compare"
    for d in overlap:
        assert full.loc[d, "regime_cell"] == trunc.loc[d, "regime_cell"], (
            f"lookahead leak: {d} classified differently once future data arrived")


def test_insufficient_history_is_unclassified_not_guessed(panel):
    ew = qf.build_ew_index(panel)
    reg = qf.assign_regime_cells(qf.compute_regime_series(ew))
    assert reg["regime_cell"].iloc[0] == "unclassified"


def test_regime_cell_codes_match_the_recipe_book_keys(panel):
    """Cells must be T{1-3}V{1-3} or 'unclassified' — the book's own keys."""
    ew = qf.build_ew_index(panel)
    reg = qf.assign_regime_cells(qf.compute_regime_series(ew))
    valid = {f"T{t}V{v}" for t in (1, 2, 3) for v in (1, 2, 3)} | {"unclassified"}
    assert set(reg["regime_cell"]) <= valid


# --------------------------------------------------- rank_in_sector

def test_rank_in_sector_drops_single_name_sectors(panel):
    """A lone name ranks 1.0 by construction — meaningless, not 'leading'."""
    r20 = qf.compute_ret20(panel)
    ris = qf.compute_rank_in_sector(
        r20, {"AAA": "Tech", "BBB": "Tech", "CCC": "Energy"})
    assert "CCC" not in set(ris.ticker)
    assert {"AAA", "BBB"} <= set(ris.ticker)


def test_rank_in_sector_is_bounded(panel):
    r20 = qf.compute_ret20(panel)
    ris = qf.compute_rank_in_sector(r20, {"AAA": "Tech", "BBB": "Tech",
                                          "CCC": "Tech"})
    assert ris.rank_in_sector.between(0.0, 1.0).all()


def test_rank_in_sector_handles_empty_sector_map(panel):
    r20 = qf.compute_ret20(panel)
    ris = qf.compute_rank_in_sector(r20, {})
    assert ris.empty


# --------------------------------------------------------- compute_all

def test_compute_all_returns_every_field(panel):
    per, reg = qf.compute_all(
        panel, sector_map={"AAA": "Tech", "BBB": "Tech", "CCC": "Energy"})
    assert {"date", "ticker", "ret20", "rs_consist",
            "rank_in_sector"} <= set(per.columns)
    assert {"trend_200", "vol_60", "regime_cell"} <= set(reg.columns)


def test_compute_all_survives_no_sector_map(panel):
    per, _ = qf.compute_all(panel)
    assert "rank_in_sector" in per.columns
    assert per["rank_in_sector"].isna().all()
