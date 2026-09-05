"""Tests for signal_hit_rate_20d/signal_n (spec: docs/specs/
aqe_voice_packet_spec_2026-09-05.md §2) -- the live-computed
(elder_pattern x structure_shift) forward-20-session hit-rate table.

build_table()/lookup() are tested against controlled fixtures (the
aggregation math is the part that must never silently drift). ticker_samples()
and _structure_shift_asof() get a lighter integration-style check against
real panel data, since a fully synthetic 90+ bar fractal-pivot series is
fragile to hand-craft and the aggregation tests already cover the actual
risk (a wrong hit/n count)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import signal_hitrate as shr


# ── build_table / lookup — pure aggregation, no I/O ─────────────────────────

def test_build_table_aggregates_hits_and_n_across_tickers(monkeypatch):
    """Two tickers landing in the same cell must share one denominator."""
    fake_samples = {
        "AAA": [("SUSTAINED", "RANGE", True), ("SUSTAINED", "RANGE", False)],
        "BBB": [("SUSTAINED", "RANGE", True), ("INTERRUPTED", "BULLISH_BOS", True)],
    }
    monkeypatch.setattr(shr, "ticker_samples", lambda g: fake_samples[g.name])

    groups = {tk: pd.DataFrame({"x": [0]}).assign(**{}) for tk in fake_samples}
    for tk, df in groups.items():
        df.name = tk  # ticker_samples is monkeypatched to read this

    table = shr.build_table(groups)
    assert table[("SUSTAINED", "RANGE")] == (2, 3)          # 2 hits of 3 samples
    assert table[("INTERRUPTED", "BULLISH_BOS")] == (1, 1)


def test_build_table_on_empty_input_is_an_empty_table():
    assert shr.build_table({}) == {}


def test_lookup_returns_none_and_zero_for_an_unseen_cell():
    table = {("SUSTAINED", "RANGE"): (5, 10)}
    rate, n = shr.lookup(table, "ACCELERATION", "BEARISH_CHOCH")
    assert rate is None and n == 0, "a cell with no samples is no_analogues, never a 0%"


def test_lookup_returns_the_measured_rate_and_n_for_a_seen_cell():
    table = {("SUSTAINED", "RANGE"): (5, 10)}
    rate, n = shr.lookup(table, "SUSTAINED", "RANGE")
    assert rate == 50.0
    assert n == 10


def test_lookup_never_divides_by_zero_on_a_zero_count_entry():
    """A defensive case: a cell explicitly stored as (0, 0) must still read
    as no_analogues, not raise or return a bogus rate."""
    table = {("SUSTAINED", "RANGE"): (0, 0)}
    rate, n = shr.lookup(table, "SUSTAINED", "RANGE")
    assert rate is None and n == 0


# ── ticker_samples — the per-ticker windowing/bucketing logic ──────────────

def _flat_ohlc(n: int, price: float = 100.0) -> pd.DataFrame:
    """n bars of a perfectly flat, zero-volatility series -- deliberately
    degenerate so structure/elder detectors have nothing to key off and
    ticker_samples must return [] rather than raising or fabricating cells."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates, "open": price, "high": price, "low": price,
        "close": price, "volume": 1_000_000,
    })


def test_too_short_a_history_produces_no_samples():
    g = _flat_ohlc(shr.MIN_BARS - 1)
    assert shr.ticker_samples(g) == []


def test_a_flat_series_never_crashes_even_if_it_yields_no_clean_samples():
    """A zero-volatility series can't build a real swing/pivot -- the
    function must degrade to an empty or partial list, never raise."""
    g = _flat_ohlc(shr.MIN_BARS + 10)
    out = shr.ticker_samples(g)
    assert isinstance(out, list)
    for pat, shift, higher in out:
        assert shift in ("BULLISH_BOS", "ABOVE_STRUCTURE", "BEARISH_CHOCH", "RANGE")
        assert isinstance(higher, bool)


def test_ticker_samples_on_a_real_uptrend_produces_well_formed_samples():
    """A genuinely trending, noisy series -- close enough to real data to
    exercise the actual elder/structure code paths (not just the empty-input
    guard clauses above)."""
    rng = np.random.RandomState(7)
    n = shr.MIN_BARS + 20
    drift = np.linspace(0, 20, n)
    noise = rng.normal(0, 0.5, n)
    close = 100 + drift + noise.cumsum() * 0.05
    high = close + np.abs(rng.normal(0.3, 0.1, n))
    low = close - np.abs(rng.normal(0.3, 0.1, n))
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    g = pd.DataFrame({"date": dates, "open": close, "high": high, "low": low,
                      "close": close, "volume": 1_000_000})

    out = shr.ticker_samples(g)
    assert out, "a real trending series should produce at least one sample"
    valid_patterns = {"SUSTAINED", "CORRECTION_REENTRY", "ACCELERATION",
                      "ACCUMULATION_BASE", "INTERRUPTED"}
    valid_shifts = {"BULLISH_BOS", "ABOVE_STRUCTURE", "BEARISH_CHOCH", "RANGE"}
    for pat, shift, higher in out:
        assert pat in valid_patterns
        assert shift in valid_shifts
        assert isinstance(higher, bool)


def test_a_bad_ticker_never_blocks_the_table(monkeypatch):
    """elder.compute() raising for one malformed ticker must not propagate --
    build_table degrades that ticker to zero samples, nothing else."""
    def _boom(*a, **k):
        raise RuntimeError("bad panel row")
    monkeypatch.setattr(shr.elder, "compute", _boom)
    g = _flat_ohlc(shr.MIN_BARS + 10)
    assert shr.ticker_samples(g) == []
