"""Macro scenario reads — the first merge point, and the claims it must not make.

A scenario score is the SHARE OF CONDITIONS MET. Nothing was fitted, nothing was
backtested, no base rate was measured. The failure mode this file guards is a
weaker claim being read as a stronger one: a score being taken for a probability,
a thin-coverage scenario outranking a fully-evidenced one, or a contested tape
being reported as a call.
"""

from __future__ import annotations

import pytest

from src.macro import scenarios as SC


def weather(**kw):
    """Macro Weather shape: direction score in [-2, +2] per instrument."""
    return {k: {"score": v, "roc5": round(v * 1.1, 2), "roc20": round(v * 2.2, 2),
                "direction": "RISING" if v > 0 else ("FALLING" if v < 0 else "FLAT")}
            for k, v in kw.items()}


def crown(*, corr_pctl=0.5, band="NORMAL", vix=18.0, regime="neutral",
          sector_bias=None):
    return {
        "volatility": {
            "vix": vix,
            "dispersion": {"band": band, "spread": 12.0, "direction": "FLAT"},
            "corroboration": {"implied_correlation": 25.0,
                              "correlation_percentile": corr_pctl,
                              "dspx": 20.0, "dspx_percentile": 0.5},
        },
        "cta": {"sector_bias": sector_bias if sector_bias is not None
                else {"equity": 0.3, "rates": -0.2, "energy": 0.1, "fx": 0.0}},
        "heartbeat": {"regime": regime},
    }


REFLATION_TAPE = dict(CPER=2, COPPER_GOLD=2, HYG=1, IWM=2, TLT=-2, UUP=-1, GLD=-1, USO=1)
STRESS_TAPE = dict(UUP=2, GLD=2, HYG=-2, TLT=2, CPER=-2, IWM=-2, USO=-1, COPPER_GOLD=-2)


# ─────────────────────────────────────────── the claim it is allowed to make

def test_a_score_is_never_presented_as_a_probability():
    """QS ships a calibrated `p`. This ships a share of conditions met. If the
    two ever read as the same kind of number, the weaker one gets promoted."""
    r = SC.analyse(weather(**REFLATION_TAPE), crown())
    assert "SHARE OF CONDITIONS MET" in r["note"]
    assert "not a probability" in r["note"].lower()
    for s in r["scenarios"]:
        assert "probability" not in s and "p" not in s


def test_every_scenario_ships_its_falsifiers_not_just_its_evidence():
    """What is NOT true is what would have to change for the story to become the
    read — the more useful column, and the one that is easy to omit."""
    r = SC.analyse(weather(**REFLATION_TAPE), crown())
    for s in r["scenarios"]:
        assert "evidence" in s and "missing_conditions" in s
        assert isinstance(s["missing_conditions"], list)
    assert any(s["missing_conditions"] for s in r["scenarios"])


def test_evidence_lines_carry_the_actual_numbers():
    r = SC.analyse(weather(**REFLATION_TAPE), crown())
    ref = next(s for s in r["scenarios"] if s["scenario"] == "REFLATION")
    assert any("roc5" in e for e in ref["evidence"])


# ────────────────────────────────────────────────────── ranking discipline

def test_a_reflationary_tape_ranks_reflation_above_a_growth_scare():
    r = SC.analyse(weather(**REFLATION_TAPE), crown())
    by = {s["scenario"]: s["score"] for s in r["scenarios"]}
    assert by["REFLATION"] > by["GROWTH_SCARE"]


def test_a_stress_tape_flips_the_order():
    r = SC.analyse(weather(**STRESS_TAPE), crown())
    by = {s["scenario"]: s["score"] for s in r["scenarios"]}
    assert by["GROWTH_SCARE"] > by["REFLATION"]
    assert by["DOLLAR_SQUEEZE"] > by["REFLATION"]


def test_a_thin_scenario_cannot_outrank_a_fully_evidenced_one():
    """A score from two of seven conditions is not comparable to seven of seven.
    Ranking them together lets a scenario lead on the data we are MISSING."""
    r = SC.analyse({}, crown(corr_pctl=0.05, band="ELEVATED", vix=13.0))
    lead = next(s for s in r["scenarios"] if s["scenario"] == r["leading"])
    assert lead["coverage"] >= SC.MIN_COVERAGE_TO_LEAD
    thin = [s for s in r["scenarios"] if not s["can_lead"]]
    assert thin and all("not eligible to lead" in s["caveat"] for s in thin)


def test_two_stories_fitting_one_tape_is_reported_as_contested():
    r = SC.analyse(weather(**STRESS_TAPE), crown(corr_pctl=0.9))
    if r["contested"]:
        assert "Two stories fit the same tape" in r["reading"]
    scores = [s["score"] for s in r["scenarios"] if s["can_lead"]]
    if len(scores) > 1 and scores[0] - scores[1] < SC.CONTESTED_MARGIN:
        assert r["contested"] is True


def test_a_muddled_tape_leads_with_nothing():
    """Every instrument flat: no story should be declared."""
    flat = weather(CPER=0, COPPER_GOLD=0, HYG=0, IWM=0, TLT=0, UUP=0, GLD=0, USO=0)
    r = SC.analyse(flat, crown())
    assert r["leading"] is None
    assert "not currently expressing a clean macro story" in r["reading"]


# ───────────────────────────────────────── the dispersion regime, from Crown

def test_the_dispersion_regime_is_driven_by_correlation_not_by_price():
    """The scenario that only Crown can see: collapsed implied correlation plus
    an elevated spread on a calm index."""
    hot = SC.evaluate("DISPERSION_REGIME", {},
                      crown(corr_pctl=0.05, band="ELEVATED", vix=13.0)["volatility"],
                      crown()["cta"], crown()["heartbeat"])
    cold = SC.evaluate("DISPERSION_REGIME", {},
                       crown(corr_pctl=0.85, band="CALM", vix=28.0)["volatility"],
                       crown()["cta"], crown()["heartbeat"])
    assert hot["score"] > cold["score"]
    assert any("correlation" in e for e in hot["evidence"])


def test_an_unavailable_input_is_skipped_not_counted_as_failed():
    """A missing feed must not read as evidence against a scenario."""
    s = SC.evaluate("LIQUIDITY_STRESS", weather(UUP=2, GLD=2, HYG=-2, TLT=2),
                    {}, {}, {})
    assert s["unavailable"]
    assert s["coverage"] < 1.0
    assert all("unavailable" in u for u in s["unavailable"])


# ──────────────────────────────────────────────── the merge-point contract

def test_crown_stays_standalone_and_the_merge_happens_HERE():
    """PM directive: build Crown separately, merge later, keep the overlap
    measurable. Importing SRM inside a Crown module would pre-empt that
    decision; this module reading BOTH finished outputs is what a merge point
    is."""
    import inspect
    src = inspect.getsource(SC)
    assert "from src.engines.srm import" in src        # the merge is explicit here
    from src.macro.crown import vol, kernel, heartbeat
    for mod in (vol, kernel, heartbeat):
        assert "srm" not in inspect.getsource(mod).lower().replace("srm_", "")


def test_the_direction_score_is_reused_not_reimplemented():
    """If this module computed its own 'is copper rising', it could disagree
    with the sector headwind built from the same bars."""
    import inspect
    assert "compute_macro_weather" in inspect.getsource(SC.fetch_weather)


def test_no_inputs_at_all_is_UNAVAILABLE_with_a_reason():
    r = SC.analyse(None, None)
    assert r["status"] == "UNAVAILABLE" and r["reason"]
    assert r["leading"] is None


def test_every_scenario_has_a_story_and_an_expression():
    for name, spec in SC.SCENARIOS.items():
        assert spec["story"] and spec["expression"]
        assert spec["conditions"], name
        for source, _key, _expected, weight in spec["conditions"]:
            assert source in ("macro", "vol", "cta", "heartbeat"), source
            assert weight > 0
