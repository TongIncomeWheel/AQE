"""QS engine tests.

These are fidelity tests, not feature tests. The frozen calibration was
measured through one exact arithmetic; a deviation here does not raise, it
returns a plausible number that means something other than what it claims. So
each trap gets a test that would fail loudly if the behaviour drifted:

  * `between` right-inclusive, NaN/missing always failing a condition
  * recipe_hits counting all 40 entries including the 8 duplicate pairs
  * MOMENTUM inverted, so quiet momentum scores HIGH
  * lens rounding at both levels, and the strict `<` band boundary
  * the 2-D fallback carrying no path stats
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.data.paths import DATA_DIR
from src.engines import qs_engine as E
from src.engines import qs_spec as S

BOOK = json.load(open(DATA_DIR / "qs" / "recipe_book.json"))
CAL = json.load(open(DATA_DIR / "qs" / "calibration.json"))
REGIME = {"cell": "T3V3", "desc": "Hot, fast, wild bull run",
          "stance": "PRESS_EXPECT_WHIPSAW", "base_rate_test": 0.446}


# ------------------------------------------------------- condition semantics

@pytest.fixture
def frame():
    return pd.DataFrame({"x": [1.0, 5.0, 10.0, np.nan],
                         "s": ["RED", "GREEN", "RED", None]})


def test_between_is_right_inclusive(frame):
    """lo < x <= hi — daily_scan.py uses inclusive='right'."""
    m = E.cond_mask(frame, {"field": "x", "op": "between", "lo": 1.0, "hi": 10.0})
    assert m.tolist() == [False, True, True, False]


def test_le_and_gt(frame):
    assert E.cond_mask(frame, {"field": "x", "op": "le",
                               "value": 5.0}).tolist() == [True, True, False, False]
    assert E.cond_mask(frame, {"field": "x", "op": "gt",
                               "value": 5.0}).tolist() == [False, False, True, False]


def test_eq_compares_as_string(frame):
    assert E.cond_mask(frame, {"field": "s", "op": "eq",
                               "value": "RED"}).tolist() == [True, False, True, False]


def test_nan_never_satisfies_a_condition(frame):
    """A missing value fails every operator — it must never pass."""
    for c in ({"field": "x", "op": "le", "value": 99.0},
              {"field": "x", "op": "gt", "value": -99.0},
              {"field": "x", "op": "between", "lo": -99.0, "hi": 99.0}):
        assert E.cond_mask(frame, c).iloc[3] == False  # noqa: E712


def test_missing_column_fails_rather_than_raising(frame):
    assert not E.cond_mask(frame, {"field": "nope", "op": "gt", "value": 0}).any()


# ------------------------------------------------------------- recipe counting

@pytest.fixture
def dup_row():
    """Satisfies a condition-set that appears TWICE in the book."""
    return pd.DataFrame([{"vp_position_score": 20.0, "roc_zscore": -1.5,
                          "rel_mom_score": -1.0, "ms_pos_score": 9.0,
                          "abs_mom_score": -1.0, "en_pos50": 80.0}])


def test_duplicate_recipes_are_counted_twice(dup_row):
    """The whole point: 40 entries, not 32 unique sets.

    The calibration's hit bands were fitted on the double-counted total.
    Deduping halves the count here and drops the name a whole band, which
    silently understates its probability.
    """
    all40 = E.count_recipe_hits(dup_row, BOOK["recipes"])[0]
    seen, uniq = set(), []
    for r in BOOK["recipes"]:
        k = frozenset(json.dumps(c, sort_keys=True) for c in r["conditions"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    deduped = E.count_recipe_hits(dup_row, uniq)[0]
    assert len(uniq) == 32 and len(BOOK["recipes"]) == 40
    assert all40 == 2 * deduped
    assert S.hits_band(all40) == "8+" and S.hits_band(deduped) == "3-7"


def test_book_is_still_forty_recipes():
    """A guard on the frozen artifact itself."""
    assert len(BOOK["recipes"]) == 40
    assert len(BOOK["vetoes"]) == 5


# -------------------------------------------------------------------- lenses

def _cohort(n=40, seed=1):
    rng = np.random.default_rng(seed)
    d = {"ticker": [f"T{i}" for i in range(n)]}
    for f, _ in [p for lens in S.LENSES.values() for p in lens]:
        d[f] = rng.uniform(0, 10, n)
    return pd.DataFrame(d)


def test_momentum_lens_is_inverted():
    """LOW raw momentum must score HIGH — the core of the method.

    A sign error here inverts the signal rather than degrading it, so it is
    worth an explicit assertion.
    """
    df = _cohort()
    for f, _ in S.LENSES["MOMENTUM"]:
        df[f] = np.linspace(0, 10, len(df))     # row 0 quietest
    out = E.score_lenses(df)
    assert out["L_MOMENTUM"].iloc[0] > out["L_MOMENTUM"].iloc[-1]


def test_non_inverted_lens_scores_high_on_high_raw():
    df = _cohort()
    for f, _ in S.LENSES["STRUCTURE"]:
        df[f] = np.linspace(0, 10, len(df))
    out = E.score_lenses(df)
    assert out["L_STRUCTURE"].iloc[-1] > out["L_STRUCTURE"].iloc[0]


def test_lens_scores_are_bounded_and_rounded():
    out = E.score_lenses(_cohort())
    for lens in S.LENSES:
        col = out[f"L_{lens}"].dropna()
        assert (col >= 0).all() and (col <= 10).all()
        assert (col.round(S.LENS_SCORE_DP) == col).all()
    lt = out["lens_total"].dropna()
    assert (lt.round(S.LENS_TOTAL_DP) == lt).all()


def test_missing_component_is_skipped_and_recorded():
    """A lens averages what it has, but the shortfall must be visible."""
    df = _cohort().drop(columns=["cmf"])
    out = E.score_lenses(df)
    assert out["L_FLOW"].notna().all()
    assert (out["lens_components_used"] < 15).all()


# --------------------------------------------------------------- probability

def test_three_d_bucket_is_preferred():
    r = E.lookup_probability(17, 6.14, 2, CAL)
    assert r["bucket"] == "8+|6-7|2-3" and r["bucket_kind"] == "3-D"
    assert r["p"] == 0.596 and r["n_analogues"] == 552


def test_two_d_fallback_when_the_three_d_cell_is_absent():
    r = E.lookup_probability(10, 4.0, 0, CAL)      # 8+|<5|0-1 not in 3-D table
    assert r["bucket"] == "8+|<5" and r["bucket_kind"] == "2-D fallback"


def test_two_d_fallback_carries_no_path_stats():
    """So the card omits days/dip rather than inventing them."""
    r = E.lookup_probability(10, 4.0, 0, CAL)
    assert r["days_median"] is None and r["mae_atr_median"] is None


def test_lens_band_boundary_uses_strict_less_than():
    """lens_total 6.0 -> "6-7", not "5-6". Rounded totals hit this often."""
    assert E.lookup_probability(17, 6.0, 2, CAL)["bucket"] == "8+|6-7|2-3"
    assert E.lookup_probability(17, 5.9, 2, CAL)["bucket"] == "8+|5-6|2-3"


def test_null_lens_total_yields_no_probability():
    assert E.lookup_probability(5, float("nan"), 0, CAL)["p"] is None


# -------------------------------------------------------------------- vetoes

def test_veto_fires_only_when_every_condition_holds():
    v = [{"name": "test", "conditions": [
        {"field": "a", "op": "le", "value": 1.0},
        {"field": "b", "op": "gt", "value": 5.0}]}]
    df = pd.DataFrame({"a": [0.0, 0.0, 9.0], "b": [9.0, 0.0, 9.0]})
    fired, _ = E.evaluate_vetoes(df, v)
    assert fired == [["test"], [], []]


def test_unevaluable_veto_is_flagged_without_changing_the_outcome():
    """Fail-open matches the reference; the gap must still be visible."""
    v = [{"name": "gap", "conditions": [{"field": "a", "op": "le", "value": 1.0}]}]
    df = pd.DataFrame({"a": [0.0, np.nan]})
    fired, ungraded = E.evaluate_vetoes(df, v)
    assert fired == [["gap"], []]          # NaN row not struck — as reference
    assert ungraded == [[], ["gap"]]       # but recorded as unevaluable


# ------------------------------------------------------------ awake / state

def test_awake_reads_any_of_the_three_triggers():
    df = pd.DataFrame({
        "abs_mom_score": [1.0, 0.0, 0.0, 0.0],
        "rel_mom_score": [0.0, 1.0, 0.0, 0.0],
        "impulse_state": ["RED", "RED", "GREEN", "RED"]})
    assert E.compute_awake(df).tolist() == [True, True, True, False]


def test_awake_survives_missing_columns():
    assert E.compute_awake(pd.DataFrame({"x": [1]})).tolist() == [False]


# ------------------------------------------------------------ rank / emission

def _run(day, persist=None, regime=None):
    return E.run_qs(day, BOOK, CAL, regime or REGIME, persist_map=persist or {})


@pytest.fixture
def day():
    rng = np.random.default_rng(3)
    n = 50
    d = {"ticker": [f"T{i:02d}" for i in range(n)],
         "close": rng.uniform(20, 300, n), "atr14": rng.uniform(0.5, 8, n),
         "impulse_state": rng.choice(["GREEN", "RED", "NEUTRAL"], n)}
    for f in (S.CARD_COMPONENTS + ["vp_position_score", "k39_value", "pr_ma_score",
                                   "pr_ret_12m", "excess_return", "rs_accel",
                                   "pipe_rank", "volume_score", "fip_quality",
                                   "pr_vol_score", "earn_score", "exhaustion_score"]):
        d.setdefault(f, rng.uniform(0, 30, n))
    return pd.DataFrame(d)


def test_run_returns_one_row_per_name(day):
    assert len(_run(day)) == len(day)


def test_stand_down_emits_nothing(day):
    reg = dict(REGIME, stance="STAND_DOWN")
    assert not any(r["emitted"] for r in _run(day, regime=reg))


def test_vetoed_names_are_emitted_so_the_strike_is_visible(day):
    rows = _run(day)
    vetoed = [r for r in rows if r["vetoes"]
              and r["engine"]["recipe_hits"] >= S.SHEET_MIN_HITS]
    assert all(r["conviction"] == 0 for r in vetoed)
    assert all(r["emitted"] for r in vetoed)


def test_conviction_one_is_suppressed_as_noise(day):
    """PM directive: no edge over today's market, so never shown."""
    rows = _run(day)
    assert not any(r["emitted"] for r in rows if r["conviction"] == 1)


def test_ranked_pool_excludes_vetoed_names(day):
    assert all(not r["vetoes"] for r in _run(day) if r["rank"])


def test_rank_is_capped(day):
    ranks = [r["rank"] for r in _run(day) if r["rank"]]
    assert len(ranks) <= S.QS_RANK_TOP_N
    assert sorted(ranks) == list(range(1, len(ranks) + 1))


def test_regime_without_a_base_rate_falls_back_not_undefined(day):
    reg = {"cell": "T1V1", "desc": "Drifting", "stance": "NEUTRAL"}
    rows = _run(day, regime=reg)
    assert all(r["odds"]["market_avg"] == round(S.DEFAULT_CELL_BASE_RATE, 3)
               for r in rows)


def test_persist_feeds_through_to_the_bucket(day):
    lo = _run(day, persist={t: 0 for t in day.ticker})
    hi = _run(day, persist={t: 5 for t in day.ticker})
    lo_b = [r["odds"]["bucket"] for r in lo]
    hi_b = [r["odds"]["bucket"] for r in hi]
    assert lo_b != hi_b


def test_awareness_notes_never_touch_hits_or_conviction(day):
    """Commentary only — PM ruling 2026-08-04."""
    stripped = dict(BOOK)
    stripped["awareness_notes"] = {"patterns": []}
    a = E.run_qs(day, BOOK, CAL, REGIME)
    b = E.run_qs(day, stripped, CAL, REGIME)
    assert [r["engine"]["recipe_hits"] for r in a] == [r["engine"]["recipe_hits"] for r in b]
    assert [r["conviction"] for r in a] == [r["conviction"] for r in b]


def test_objective_is_two_atr_either_side(day):
    for r in _run(day):
        o = r["objective"]
        if o:
            span = o["target_2atr"] - o["now"]
            assert abs((o["now"] - o["give_up_2atr"]) - span) < 0.02


def test_row_carries_versions_for_audit(day):
    r = _run(day)[0]
    assert r["versions"]["recipe_book"] and r["versions"]["calibration"]


def test_empty_day_returns_empty():
    assert E.run_qs(pd.DataFrame(), BOOK, CAL, REGIME) == []
