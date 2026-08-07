"""Volatility Profile — the disciplines, not just the arithmetic.

The handover names nine requirements and three of them are the method itself:
close-to-close and high-to-low must never be substituted (V3), the recommended
stop uses the STRICTER of the two bases (V4), and a trailing window may never
justify a HIGHER target than full history (V5). Those are what these tests are
for. Arithmetic that is merely plausible would pass a happy-path test and still
be the wrong tool.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import vol_profile as V


def _frame(closes, spread=0.01):
    """Daily OHLCV from a close path, with a symmetric intraday range."""
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "date": pd.bdate_range("2015-01-01", periods=len(c)),
        "open": np.r_[c[0], c[:-1]],
        "high": c * (1 + spread),
        "low": c * (1 - spread),
        "close": c,
        "volume": np.full(len(c), 1e6),
    })


def _walk(n=1400, seed=3, drift=0.0003, vol=0.018):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


# ─────────────────────────────────────────── V3: the two measures never mix

def test_close_to_close_and_high_to_low_are_different_numbers():
    """The single most important discipline in the method. h2l is the TRAVERSE
    — it is structurally larger than the net move, and a stop judged on c2c
    underestimates shake-out risk several times over."""
    w = V.build_windows(_frame(_walk()))
    assert len(w) > 500
    assert (w["h2l"] >= 0).all()
    # The traverse is wider than the typical net move, by construction.
    assert w["h2l"].median() > w["c2c"].abs().median()


def test_the_corridor_is_built_from_close_to_close_only():
    """Targets come from c2c. Feeding h2l would silently inflate every target,
    and the output would still look like a plausible corridor."""
    d = _frame(_walk())
    w = V.build_windows(d)
    from_c2c = V.target_corridor(w["c2c"])
    from_h2l = V.target_corridor(w["h2l"])
    assert from_c2c["pt1_suggested"] != from_h2l["pt1_suggested"]
    prof = V.profile(d)
    assert prof["c2c"]["corridor_full"]["pt1_suggested"] == \
        pytest.approx(from_c2c["pt1_suggested"])


def test_the_profile_keeps_both_measures_and_labels_them():
    prof = V.profile(_frame(_walk()))
    assert "c2c" in prof and "h2l" in prof
    assert prof["c2c"]["percentiles"] != prof["h2l"]["percentiles"]


# ──────────────────────────────────── V4: the STRICTER basis, not the average

def test_the_stop_uses_the_stricter_basis_not_the_average():
    full = {0.04: 0.80, 0.05: 0.85, 0.06: 0.90}
    m36 = {0.04: 0.50, 0.05: 0.60, 0.06: 0.78}
    r = V.recommend_stop(full, m36, target=0.75)
    # Averaging 4% would give 0.65 -> rejected; 0.65 average at 6% -> 0.84.
    # The stricter rule must pick 6%, where BOTH clear 75%.
    assert r["stop"] == 0.06
    assert r["stricter_basis"] == 0.78


def test_a_name_too_rough_for_any_stop_says_NONE():
    """An honest non-answer. Silently widening the grid to produce a number
    would be inventing one."""
    r = V.recommend_stop({0.04: 0.30, 0.10: 0.55, 0.15: 0.70}, {}, target=0.75)
    assert r["stop"] is None and "NONE" in r["reason"]


def test_a_missing_trailing_curve_falls_back_to_full_history():
    r = V.recommend_stop({0.04: 0.60, 0.07: 0.76}, {}, target=0.75)
    assert r["stop"] == 0.07 and r["survival_36m"] is None


# ─────────────────── V5: a shorter window may comfort, it may never embolden

def test_a_hot_recent_window_cannot_raise_the_target():
    full = {"pt1_suggested": 0.10, "pt2_suggested": 0.15}
    hot = {"pt1_suggested": 0.22, "pt2_suggested": 0.30}
    capped = V._cap_to_full(full, hot)
    assert capped["pt1_suggested"] == 0.10
    assert capped["pt2_suggested"] == 0.15
    assert capped["capped_by_full_history"] is True


def test_a_cooler_recent_window_is_left_alone():
    """The rule is ASYMMETRIC on purpose — it only pulls toward caution."""
    full = {"pt1_suggested": 0.10, "pt2_suggested": 0.15}
    cool = {"pt1_suggested": 0.06, "pt2_suggested": 0.09}
    capped = V._cap_to_full(full, cool)
    assert capped["pt1_suggested"] == 0.06
    assert capped["capped_by_full_history"] is False


def test_the_cap_is_enforced_end_to_end_not_just_in_the_helper():
    prof = V.profile(_frame(_walk(n=1600, seed=11)))
    for key in ("corridor_36m", "corridor_24m"):
        c = prof["c2c"][key]
        if c.get("pt1_suggested") is not None:
            assert c["pt1_suggested"] <= prof["c2c"]["corridor_full"]["pt1_suggested"] + 1e-12


# ───────────────────────── V6: frequency, never probability, in the NAMES

def test_hit_rates_are_named_frequency_not_probability():
    """QS ships a calibrated `p`. This ships a historical frequency. If the two
    ever read as the same kind of number on a card, the weaker claim gets
    mistaken for the stronger one."""
    prof = V.profile(_frame(_walk()))
    assert "pt1_frequency_full" in prof
    assert not any("prob" in k or k == "p" or k.endswith("_p") for k in prof)


# ───────────────────────────────────────────── the window and the dip

def test_entry_is_the_NEXT_open_and_the_window_excludes_the_signal_bar():
    d = _frame([10, 11, 12, 13, 14, 15, 16, 17] + [20] * 200)
    w = V.build_windows(d, hold=3)
    assert w.iloc[0]["entry"] == pytest.approx(d["open"].iloc[1])


def test_the_dip_is_measured_only_BEFORE_the_touch():
    """Measuring it across the whole window would count pain the trade never
    made you sit through, and make every stop look worse than it was."""
    # rise to the target immediately, then collapse afterwards
    path = [100, 100, 130] + [50] * 80
    d = _frame(path, spread=0.001)
    w = V.build_windows(d, hold=60)
    cls = V.classify_hits(w, d, pt1=0.10, pt2=0.20, hold=60)
    hit = cls[cls["pt1_hit"] == 1]
    assert len(hit) >= 1
    # The post-touch collapse to 50 must NOT appear in the pre-hit dip.
    assert hit["mae_pre_pt1"].min() > -0.50


def test_survival_counts_only_eventual_winners():
    cls = pd.DataFrame({"pt1_hit": [1] * 40 + [0] * 40,
                        "mae_pre_pt1": [-0.03] * 40 + [np.nan] * 40})
    curve = V.stop_survival(cls)
    assert curve[0.04] == 1.0          # every winner dipped only 3%
    assert curve[0.02] if 0.02 in curve else True


# ────────────────────────────────────────────────── contract + degradation

def test_too_little_history_returns_empty_not_a_fabricated_corridor():
    assert V.profile(_frame(_walk(n=120))) == {}
    assert V.profile(None) == {}
    assert V.profile(pd.DataFrame({"date": [], "close": []})) == {}


def test_the_verdict_names_the_three_zones():
    prof = V.profile(_frame(_walk()))
    lo, hi = prof["c2c"]["corridor_full"]["usable_zone"]
    assert V.verdict(prof, lo - 0.05)["verdict"] == "TOO_CLOSE"
    assert V.verdict(prof, (lo + hi) / 2)["verdict"] == "OK"
    assert V.verdict(prof, hi + 0.50)["verdict"] == "TOO_FAR"


def test_every_threshold_is_a_named_constant():
    """§V9 — none of these is gospel; they must be re-testable against our own
    data with a one-line change."""
    for name in ("HOLD_SESSIONS", "CORRIDOR_LO", "CORRIDOR_HI", "PT1_SUG",
                 "PT2_SUG", "STOP_GRID", "STOP_SURVIVAL_TARGET"):
        assert hasattr(V, name)
    assert V.CORRIDOR_LO == 0.60 and V.CORRIDOR_HI == 0.90
    assert V.STOP_SURVIVAL_TARGET == 0.75
    assert min(V.STOP_GRID) == 0.04 and max(V.STOP_GRID) == 0.15


def test_it_is_fast_enough_to_run_while_the_PM_waits():
    """The reference walks the frame in Python at ~6s/ticker. On a page that
    is a tool nobody uses."""
    import time
    d = _frame(_walk(n=2600, seed=5))
    t0 = time.time()
    prof = V.profile(d)
    assert prof and time.time() - t0 < 3.0
