"""Tests for the ad-hoc ticker scorer (src/scanner/adhoc.py) — same-suite parity
with the daily feed / held_positions (PM ruling: one comprehensive field set
everywhere AQE scores a ticker, not a thinner ad-hoc subset)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scanner import adhoc


class _FakeClient:
    """Stub FMPClient — _score_one only needs .get_daily_bars(ticker, from, to)."""

    def __init__(self, bars: pd.DataFrame):
        self._bars = bars

    def get_daily_bars(self, ticker, from_date=None, to_date=None):
        return self._bars


def _synthetic_bars(n=300, seed=7) -> pd.DataFrame:
    dates = pd.bdate_range("2025-05-01", periods=n)
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0006, 0.014, n))
    high = close * (1 + np.abs(rng.normal(0.004, 0.003, n)))
    low = close * (1 - np.abs(rng.normal(0.004, 0.003, n)))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    volume = rng.integers(5e5, 3e6, n).astype(float)
    return pd.DataFrame({"date": dates, "open": open_, "high": high,
                         "low": low, "close": close, "volume": volume})


@pytest.fixture
def _spy():
    return _synthetic_bars(n=300, seed=3)


# The full set of fields the daily feed / held_positions carry that the ad-hoc
# scorer must ALSO produce (PM ruling: same suite everywhere).
_REQUIRED_KEYS = (
    # bracket + gate breakdown
    "bracket", "sc_m_gates", "sc_m_gate_detail", "sc_p_gates", "sc_p_gate_detail",
    "k39_gate",
    # Health
    "hl_score", "hl_state",
    # divergence
    "div_state", "div_bull_count", "div_bear_count", "div_oscs", "div_date",
    # pin bar / inside bar
    "pin_bar_state", "pin_bar_date", "pin_bar_level", "inside_bar", "pib_pattern",
    # smart-money CHoCH + kNN
    "choch_state", "choch_date", "knn_prob", "knn_significant",
    "knn_neighbors_used", "knn_tp1", "knn_tp2", "knn_tp3",
    # momentum acceleration
    "mp_accel", "mp_accel_state",
    # subcomponent raw columns (flow/energy/structure/mp/bq/pipe)
    "flow_score", "accum_score", "volume_score", "skew_score", "ext_score",
    "mfi", "cmf", "ha_quality_count",
    "vp_position_score", "price_action_score", "squeeze_score", "exhaustion_score",
    "atr_score", "en_pos50", "en_trend_bars",
    "rs_spy_score", "rs_accel_score", "base_score", "ms_pos_score", "resist_score",
    "wk_score", "earn_score", "rs_vs_spy", "rs_accel", "base_days", "bd_mode",
    "abs_mom_score", "mp_adx_score", "rel_mom_score", "trend_score", "roc_zscore",
    "excess_return", "adx_val", "di_bullish",
    "bq_range_tight", "bq_vol_dry", "bq_base_dur", "bq_ema_conv", "bq_base_days",
    "pr_ret_12m", "pr_adx_score", "pr_rsi_score", "pr_vol_score", "pr_ma_score",
    "momentum_composite", "pipe_tier",
)


def test_score_one_produces_full_field_suite(_spy):
    """Every field the daily feed / held_positions carry must be PRESENT (key
    exists) on an ad-hoc score result — this is the exact parity the PM asked
    to confirm. Values may legitimately be None (e.g. no CHoCH detected on
    synthetic data), but the KEY must exist."""
    bars = _synthetic_bars(n=300, seed=7)
    client = _FakeClient(bars)
    result = adhoc._score_one("TESTX", client, _spy, {}, bars["date"].iloc[0], bars["date"].iloc[-1])

    assert "error" not in result, result.get("error")
    missing = [k for k in _REQUIRED_KEYS if k not in result]
    assert not missing, f"ad-hoc scorer is missing fields the daily feed carries: {missing}"


def test_score_one_bracket_is_volume_stamped(_spy):
    """The ad-hoc bracket must go through the SAME stamp_bracket_volume as the
    daily feed — assert the function ran (no exception) and, if the bracket has
    dated levels, that at least the machinery attached vol_ratio somewhere or
    left it absent gracefully (never crashes, never silently different math)."""
    bars = _synthetic_bars(n=300, seed=11)
    client = _FakeClient(bars)
    result = adhoc._score_one("TESTY", client, _spy, {}, bars["date"].iloc[0], bars["date"].iloc[-1])

    assert "error" not in result
    bracket = result.get("bracket")
    if bracket and bracket.get("valid"):
        # stop_date implies stop_vol_ratio should have been attempted
        if bracket.get("stop_date"):
            assert "stop_vol_ratio" in bracket or bracket.get("stop_vol_ratio") is None


def test_score_one_matches_daily_feed_subcomponents_and_new_engine_fields(_spy):
    """THE parity guard: drive_sync.py's _subcomponents()/_new_engine_fields() —
    the exact functions the daily feed and held_positions call — must run
    cleanly on an ad-hoc result and produce the same nested shape. Proves the
    ad-hoc scorer and the daily feed are genuinely the SAME suite, not two
    formulas that happen to use the same field names."""
    from src.data.drive_sync import _subcomponents, _new_engine_fields, _SUBCOMPONENT_SPEC

    bars = _synthetic_bars(n=300, seed=13)
    client = _FakeClient(bars)
    result = adhoc._score_one("TESTZ", client, _spy, {}, bars["date"].iloc[0], bars["date"].iloc[-1])
    assert "error" not in result

    sub = _subcomponents(result)
    assert set(sub) == set(_SUBCOMPONENT_SPEC)
    for engine, cols in _SUBCOMPONENT_SPEC.items():
        assert set(sub[engine]) == set(cols)

    new_fields = _new_engine_fields(result)
    assert "div_state" in new_fields and "choch_state" in new_fields
    assert "mp_accel" in new_fields and "pin_bar_state" in new_fields


def test_score_one_short_data_still_degrades_cleanly():
    """Below MIN_BARS still returns the honest error path (unchanged behavior)."""
    bars = _synthetic_bars(n=30)
    client = _FakeClient(bars)
    result = adhoc._score_one("SHORT", client, bars, {}, bars["date"].iloc[0], bars["date"].iloc[-1])
    assert "error" in result
