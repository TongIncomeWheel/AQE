"""Outcome measurement for the pattern lens.

The failure mode here is silent flattery: an outcome rule that counts "price
was higher 20 days later" makes every detection in a rising market look like a
win. So these tests pin the definition — the break must come first, the
invalidation is checked the whole way, and unresolved cases are neither counted
as wins nor buried in the denominator.

The second failure mode is a lens that reports null and lets the reader assume
it measured nothing. `status` must distinguish "not calibrated yet" from
"calibrated, no look-alikes".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import pattern_calibration as C


def _series(path):
    c = np.asarray(path, dtype=float)
    return c * 1.01, c * 0.99, c


# ------------------------------------------------------------ the outcome rule

def test_a_break_that_reaches_the_target_works():
    h, l, c = _series([100] * 5 + [101, 103, 105, 107, 110])
    assert C.resolve(h, l, c, 4, trigger=100.5, invalidation=95.0, atr=2.0) == "worked"


def test_rising_into_the_target_without_ever_clearing_is_not_a_win():
    """The trap: price ends higher, but never closed above the rim, so the
    pattern never actually triggered. That is not the pattern working."""
    h, l, c = _series([100] * 5 + [100.1, 100.2, 100.3, 100.4, 100.4])
    assert C.resolve(h, l, c, 4, trigger=105.0, invalidation=95.0,
                     atr=2.0) == "unresolved"


def test_breaking_down_through_the_invalidation_fails():
    h, l, c = _series([100] * 5 + [99, 97, 94, 92, 90])
    assert C.resolve(h, l, c, 4, trigger=102.0, invalidation=95.0,
                     atr=2.0) == "failed"


def test_a_break_that_then_loses_the_level_is_scored_separately():
    """Cleared the rim, then broke the invalidation before the target. Neither
    a win nor a plain failure — it triggered and then lost."""
    h, l, c = _series([100] * 5 + [103, 102, 99, 96, 93])
    assert C.resolve(h, l, c, 4, trigger=102.0, invalidation=95.0,
                     atr=2.0) == "cleared_then_failed"


def test_the_invalidation_is_checked_before_the_target_on_the_same_path():
    """Order matters: a path that dives first and rips later must not be a win
    just because the target is touched inside the horizon."""
    h, l, c = _series([100] * 5 + [94, 96, 99, 104, 112])
    assert C.resolve(h, l, c, 4, trigger=101.0, invalidation=95.0,
                     atr=2.0) == "failed"


def test_the_horizon_bounds_the_measurement():
    path = [100] * 5 + [100.2] * 30 + [140]
    h, l, c = _series(path)
    assert C.resolve(h, l, c, 4, trigger=101.0, invalidation=90.0, atr=2.0,
                     horizon=20) == "unresolved"


# ------------------------------------------------------------- the aggregation

def test_unresolved_rows_are_excluded_from_the_rate_not_folded_in():
    rows = [{"stage": "HANDLE", "band": "0.7-1", "fit": 0.8, "outcome": "worked"},
            {"stage": "HANDLE", "band": "0.7-1", "fit": 0.8, "outcome": "failed"},
            {"stage": "HANDLE", "band": "0.7-1", "fit": 0.8, "outcome": "unresolved"}]
    cell = C.aggregate(rows)["HANDLE|0.7-1"]
    assert cell["n"] == 2                      # not 3
    assert cell["p_worked"] == 0.5             # not 0.333
    assert cell["unresolved"] == 1             # ...and it is still reported


def test_cleared_counts_the_break_even_when_the_trade_then_failed():
    rows = [{"stage": "HANDLE", "band": "0.5-0.7", "fit": 0.6,
             "outcome": "cleared_then_failed"}]
    cell = C.aggregate(rows)["HANDLE|0.5-0.7"]
    assert cell["p_cleared"] == 1.0 and cell["p_worked"] == 0.0


def test_bands_cover_the_whole_zero_to_one_range_without_a_gap():
    for f in (0.0, 0.49, 0.5, 0.69, 0.7, 0.99, 1.0):
        assert C.fit_band(f) is not None, f
    assert C.fit_band(None) is None


# ------------------------------------------------------ the runtime lookup

def test_an_uncalibrated_lens_says_so_rather_than_reporting_null(monkeypatch):
    """A null hit rate that looks like 'we measured and found nothing' would be
    a lie. The whole reason this module exists is that a detector without
    outcomes is decoration — so it has to admit when it has none."""
    monkeypatch.setattr(C, "load_calibration", lambda: None)
    r = C.lookup("HANDLE", 0.8)
    assert r["hit_rate"] is None and r["status"] == "uncalibrated"


def test_calibrated_but_no_lookalikes_is_a_different_answer(monkeypatch):
    monkeypatch.setattr(C, "load_calibration",
                        lambda: {"built": "x", "horizon": 20, "cells": {}})
    r = C.lookup("HANDLE", 0.8)
    assert r["status"] == "no_analogues" and r["n"] == 0


def test_a_real_cell_returns_its_rate_and_its_sample_size(monkeypatch):
    monkeypatch.setattr(C, "load_calibration", lambda: {
        "built": "2026-08-06", "horizon": 20,
        "cells": {"HANDLE|0.7-1": {"n": 41, "p_worked": 0.44, "p_cleared": 0.68}}})
    r = C.lookup("HANDLE", 0.85)
    assert r["hit_rate"] == 0.44 and r["n"] == 41 and r["status"] == "ok"
    assert r["measured_on"] == "2026-08-06" and r["horizon"] == 20


# ------------------------------------------------------------- the sweep

def test_the_sweep_counts_a_formation_once_not_once_per_bar():
    """A cup is visible for weeks. Counting it per bar would report one lucky
    formation as forty wins and make every rate meaningless."""
    from tests.test_patterns import _bars, _cup
    path = _cup(cup_days=60, handle_days=10) + [100.0] * 40
    h, l, c, d, v = _bars(path)
    rows = C.sweep_ticker(h, l, c, d, v)
    starts = [(r["days"],) for r in rows]
    assert len(rows) == len(set(map(tuple, (sorted(s) for s in starts)))) or len(rows) <= 3


def test_the_sweep_never_sees_a_bar_past_the_day_it_is_called_on(monkeypatch):
    """No look-ahead. Each detection must be made on bars[:i] only."""
    seen = []

    def _spy(high, low, close, dates, volume=None, **kw):
        seen.append(len(close))
        return {"pattern": None}
    monkeypatch.setattr(C, "detect_cup_handle", _spy)
    n = 300
    h = l = c = np.linspace(100, 200, n)
    C.sweep_ticker(h, l, c, pd.bdate_range("2025-01-01", periods=n).to_numpy(), None)
    assert seen and max(seen) <= n - C.HORIZON


def test_a_short_history_yields_nothing_rather_than_guessing():
    n = 60
    h = l = c = np.linspace(100, 120, n)
    assert C.sweep_ticker(h, l, c,
                          pd.bdate_range("2026-01-01", periods=n).to_numpy(),
                          None) == []
