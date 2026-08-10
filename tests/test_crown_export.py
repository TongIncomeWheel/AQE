"""The Crown reading copy — the file a committee member or a model opens cold.

Two artifacts, two jobs. `crown_macro.json` is the runtime record and carries
the full chart series. This one is the reading copy: plain English first, series
dropped, self-describing, limits attached. The tests here are about the second
job, because a file that is merely correct can still be unusable.
"""

from __future__ import annotations

import json

from src.macro.crown.export import ARTIFACT_NAME, build_llm_export

CROWN = {
    "crown_status": "DEGRADED",
    "kernel_version": "1.4",
    "generated_at": "2026-08-10T09:00:00+08:00",
    "degraded": ["COT is 1 week old"],
    "plain_english": {
        "headline": "A narrow market, calm on the surface.",
        "because": ["A handful of big names are carrying the index."],
        "so_what": "Stay with the leaders. Size at 0.65x your normal risk.",
        "watch_for": ["If the S&P trades below 7,014.30, trend funds start selling."],
        "caveats": ["No dealer-positioning read today."],
    },
    "heartbeat": {"regime": "narrowing", "range_position": "mid",
                  "days_in_regime": 42, "confidence": 0.65, "passes_gate": True,
                  "change_5d_pct": -0.2, "change_20d_pct": -1.1,
                  "change_60d_pct": -2.4,
                  "series": {"ratio": [0.3] * 252, "dates": ["x"] * 252}},
    "volatility": {
        "vix": 14.9,
        "dispersion": {"state": "ELEVATED_EASING", "band": "ELEVATED",
                       "spread": 24.74, "percentile": 0.88,
                       "spread_20d_change": -9.2, "basis": "implied",
                       "single_stock_vol": 39.64,
                       "series": {"spread": [1.0] * 504}},
        "corroboration": {"implied_correlation": 7.38},
        "term_structure": {"shape": "CONTANGO"},
    },
    "cta": {"overall_bias": "risk_on", "flip_risk": 0.11, "n_markets": 18,
            "size_adjustment": 1.0, "sector_bias": {"rates": -0.35}},
    "cta_markets": {
        "ES": {"signal": 0.57, "label": "S&P 500", "sector": "equity",
               "flips": [{"horizon": 1, "level": 7014.3, "spot": 7790.0,
                          "distance_pct": -9.96, "direction": "sell_below"},
                         {"horizon": 20, "level": 7100.0, "spot": 7790.0,
                          "distance_pct": -8.8, "direction": "sell_below"}]},
        "ZT": {"signal": -0.38, "label": "UST 2Y note", "sector": "rates",
               "flips": [{"horizon": 1, "level": 103.65, "spot": 102.96,
                          "distance_pct": 0.67, "direction": "buy_above"}]},
        "NOSIG": {"signal": None, "label": "broken", "flips": []},
    },
    "cot": {"status": "OK", "as_of": "2026-08-04",
            "crowded_long": ["GC"], "crowded_short": ["ZN"]},
    "gamma": {"status": "OK", "regime": "POSITIVE",
              "underlyings": {"SPY": {"spot": 773.92, "total_gex": 1.5e9,
                                      "gamma_flip": 776.88,
                                      "flip_distance_pct": 0.38,
                                      "call_wall": {"strike": 785.0},
                                      "put_wall": {"strike": 750.0},
                                      "assumption": "dealers are assumed short",
                                      "profile": [{"strike": 700}] * 40}}},
    "divergence": {"weight": 3, "types_fired": ["rsi_slope", "breadth_ma"]},
    "freshness": {"today": "2026-08-10", "oldest_leg": "2026-08-04",
                  "oldest_leg_days": 6, "newest_leg": "2026-08-10",
                  "volatility": {"as_of": "2026-08-07"},
                  "cot": {"as_of": "2026-08-04"},
                  "cta_markets": {"ES": {"via": "yahoo_futures"},
                                  "ZT": {"via": "etf_fallback"}}},
}

SCEN = {"leading": "DISPERSION_REGIME", "contested": False,
        "runner_up": "REFLATION", "reading": "Cleanest fit.",
        "scenarios": [{"scenario": "DISPERSION_REGIME", "score": 1.0,
                       "coverage": 1.0, "story": "A stock-picker's market.",
                       "evidence": ["implied correlation 7.38"],
                       "missing_conditions": []}]}


LEVELS_CROWN = CROWN


def doc():
    from src.macro.crown.levels import build
    c = dict(CROWN)
    c["key_levels"] = build(CROWN)
    return build_llm_export(c, SCEN)


# ───────────────────────────── the plain English wraps the data

def test_the_plain_english_comes_first_and_carries_the_whole_reading():
    d = doc()
    keys = list(d)
    assert keys.index("read_me_first") < keys.index("readings")
    assert keys.index("read_me_first") < keys.index("key_levels")
    r = d["read_me_first"]
    assert r["headline"] and r["why"] and r["so_what"]
    assert r["what_would_change_it"]


def test_it_says_what_it_is_without_needing_the_kernel_document():
    d = doc()
    assert "positioning, breadth and regime" in d["what_this_is"]
    assert d["status_means"], "a bare status code means nothing to a reader"
    for block in ("read_me_first", "the_call", "key_levels", "limits"):
        assert block in d["how_to_read"]


def test_the_chart_series_are_dropped():
    """504 dispersion points buy a model nothing the sentence has not already
    bought, and they cost the context the sentence needs."""
    text = json.dumps(doc())
    assert len(text) < 60_000, "the reading copy has grown a series again"
    assert "\"series\"" not in text
    assert "\"profile\"" not in text


def test_the_runtime_record_keeps_what_the_reading_copy_drops():
    """The two artifacts have different jobs and must not converge."""
    assert CROWN["heartbeat"]["series"]["ratio"], "runtime record still has series"
    assert "series" not in json.dumps(doc()["readings"]["breadth"])


# ───────────────────────────── ONE levels table, no duplicate

def test_there_is_only_one_levels_table():
    """key_levels and a separate flip_levels overlapped by six rows in
    different shapes, so a model read the same levels twice."""
    d = doc()
    assert "flip_levels" not in d, "the duplicate table is back"
    assert d["key_levels"], "the surviving table must carry the levels"


def test_the_one_table_still_carries_the_per_market_flip_fields():
    """Merging must not lose what the dropped table knew."""
    from src.macro.crown.levels import build
    rows = [r for r in build(LEVELS_CROWN)["levels"]
            if r["kind"] == "trend followers"]
    assert rows and all({"market", "sector", "trend_signal", "direction"}
                        <= set(r) for r in rows)


def test_every_market_reaches_the_table_not_just_the_nearest_few():
    from src.macro.crown.levels import build
    rows = [r for r in build(LEVELS_CROWN)["levels"]
            if r["kind"] == "trend followers"]
    assert len(rows) == 2, "both markets with a signal must appear"


# ───────────────────────────── the limits travel with it

def test_the_degraded_notes_are_carried_into_the_limits():
    assert any("COT is 1 week old" in x for x in doc()["limits"])


def test_the_four_standing_refusals_are_always_stated():
    limits = " ".join(doc()["limits"]).lower()
    assert "does not size" in limits
    assert "does not name a ticker" in limits
    assert "not a probability" in limits


def test_a_missing_gamma_read_is_named_as_a_gap():
    c = dict(CROWN)
    c["gamma"] = {"status": "SKIPPED", "regime": "UNKNOWN", "reason": "no keys"}
    assert any("dealer-positioning" in x for x in build_llm_export(c, SCEN)["limits"])


def test_how_current_is_answerable_per_source():
    hc = doc()["how_current"]
    assert hc["oldest_source"] == "2026-08-04"
    assert hc["oldest_source_days_behind"] == 6
    assert hc["positioning_as_of"] and hc["volatility_as_of"]


# ───────────────────────────── it survives a thin or broken read

def test_an_empty_crown_read_does_not_raise():
    d = build_llm_export({}, {})
    assert d["artifact"] == "aqe_crown_macro"
    assert d["key_levels"] == []
    assert d["limits"]


def test_it_is_json_serialisable_end_to_end():
    json.dumps(build_llm_export(CROWN, SCEN))
    json.dumps(build_llm_export({}, None))


def test_the_filename_is_stable_because_readers_bookmark_it():
    assert ARTIFACT_NAME == "aqe_crown_macro.json"
