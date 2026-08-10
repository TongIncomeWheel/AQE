"""The plain-English read — the rules that keep it readable and honest.

This is the only module in the layer whose output is prose, which makes it the
easiest one to let drift: a sentence can stay grammatical long after it has
stopped matching the numbers. These tests hold the two properties that matter —
it is GENERATED from the data every run, and it says what the numbers say.
"""

from __future__ import annotations

from src.macro.crown import explain as E


def crown(*, regime="narrowing", range_pos="mid", disp_state="ELEVATED_EASING",
          band="ELEVATED", pctl=0.98, spread=24.7, chg=-9.2, vix=14.9,
          vix_pctl=0.09, family="DIVERGENCE_PAIR_SHORT", size=0.65,
          early_exit=False, status="OK", gamma_status="SKIPPED",
          fired=("rsi_slope", "breadth_ma"), weight=5,
          crowded_long=("GC", "HG"), crowded_short=("ZN",)):
    return {
        "crown_status": status,
        "generated_at": "2026-08-10T09:00:00+08:00",
        "heartbeat": {"regime": regime, "range_position": range_pos},
        "volatility": {
            "vix": vix, "vix_percentile": vix_pctl,
            "dispersion": {"state": disp_state, "band": band, "percentile": pctl,
                           "spread": spread, "spread_20d_change": chg,
                           "basis": "implied"},
            "rules": {"very_low_vix": vix < 15, "already_priced": vix >= 25,
                      "hidden_stress": disp_state == "ELEVATED_RISING"},
        },
        "gamma": {"status": gamma_status, "regime": "UNKNOWN"},
        "cta": {"overall_bias": "risk_on", "flip_risk": 0.25, "n_markets": 8},
        "cot": {"status": "OK", "as_of": "2026-08-04",
                "crowded_long": list(crowded_long), "crowded_short": list(crowded_short)},
        "cta_markets": {"ES": {"flips": [{"horizon": 1, "level": 7240.0,
                                          "distance_pct": -1.8,
                                          "direction": "sell_below"}]}},
        "divergence": {"types_fired": list(fired), "weight": weight},
        "decision": {"early_exit": early_exit, "size_multiplier": size,
                     "expression": {"family": family, "match": "exact",
                                    "conditions_unmet": []}},
        "freshness": {},
    }


SCEN = {"leading": "DISPERSION_REGIME",
        "scenarios": [{"scenario": "DISPERSION_REGIME",
                       "missing_conditions": ["CTA sector spread 0.31"]}]}


def _all_text(pe) -> str:
    return " ".join([pe["headline"], pe["so_what"], *pe["because"],
                     *pe["watch_for"], *pe.get("caveats", [])])


# ─────────────────────────────────────────────── it says what the data says

def test_an_easing_spread_is_described_as_draining_not_building():
    """The distinction the whole layer turns on. If this sentence ever says
    'building' on an easing tape, the page is telling the PM to buy downside
    into the end of a move."""
    pe = E.explain(crown(disp_state="ELEVATED_EASING"), SCEN)
    text = _all_text(pe)
    assert "the gap is closing" in text
    assert "leaving the market rather than building" in text
    assert "index puts would be late" in text


def test_a_rising_spread_is_described_as_the_warning():
    pe = E.explain(crown(disp_state="ELEVATED_RISING", chg=+6.0), SCEN)
    text = _all_text(pe)
    assert "still growing" in text
    assert "5 to 7 percent" in text


def test_narrowing_and_broadening_read_as_opposite_sentences():
    a = _all_text(E.explain(crown(regime="narrowing"), SCEN))
    b = _all_text(E.explain(crown(regime="broadening"), SCEN))
    assert "average stock is falling behind" in a
    assert "rally is broad" in b


def test_a_tired_wave_is_called_out_as_late():
    pe = E.explain(crown(regime="broadening", range_pos="top"), SCEN)
    assert "closer to its end than its start" in _all_text(pe)


def test_the_size_multiplier_is_explained_not_just_quoted():
    pe = E.explain(crown(size=0.65), SCEN)
    assert "0.65x your normal risk" in pe["so_what"]
    assert "crowded" in pe["so_what"]


def test_the_early_exit_says_the_process_stopped_and_why():
    pe = E.explain(crown(early_exit=True), SCEN)
    assert "not readable" in pe["headline"]
    assert pe["so_what"] == "No new risk."
    assert "stopped there" in " ".join(pe["because"])


def test_an_unavailable_read_does_not_pretend_to_describe_a_market():
    pe = E.explain(crown(status="UNAVAILABLE"), SCEN)
    assert "cannot read the market" in pe["headline"]
    assert pe["watch_for"] == []


# ──────────────────────────────────────────────────── it stays READABLE

def test_no_jargon_survives_without_its_meaning():
    """"Dispersion at the 98th percentile" is not English."""
    text = _all_text(E.explain(crown(), SCEN)).lower()
    for word in ("percentile", "dispersion", "gex", "z-score", "tsmom",
                 "vixeq", "flip_risk", "heartbeat"):
        assert word not in text, f"raw jargon leaked: {word}"


def test_a_long_positioning_list_is_capped_rather_than_recited():
    """Twelve markets joined by commas is not a sentence anyone reads."""
    pe = E.explain(crown(crowded_long=("GC", "HG", "DX", "YM", "ZF", "ZT", "ZW"),
                         crowded_short=("NG", "NQ", "SI", "ZB", "ZN")), SCEN)
    cot_line = next(b for b in pe["because"] if "speculators" in b)
    assert "others" in cot_line
    assert cot_line.count(" and ") <= 2


def test_the_two_positioning_clauses_are_not_joined_by_a_second_and():
    pe = E.explain(crown(), SCEN)
    cot_line = next(b for b in pe["because"] if "speculators" in b)
    assert "; " in cot_line


def test_sentences_do_not_end_in_a_double_period():
    for b in _all_text(E.explain(crown(), SCEN)).split(" "):
        assert ".." not in b


def test_the_warning_count_matches_what_it_then_lists():
    """Quoting a count of 5 and then naming 2 things reads as a mistake."""
    pe = E.explain(crown(fired=("rsi_slope", "breadth_ma"), weight=5), SCEN)
    line = next(b for b in pe["because"] if "warning sign" in b)
    assert line.startswith("2 warning signs lit:")
    assert "A further 3 showed up on individual markets." in line


def test_no_warnings_is_stated_positively_rather_than_omitted():
    pe = E.explain(crown(fired=(), weight=0), SCEN)
    assert "No warning signs are lit" in " ".join(pe["because"])


# ──────────────────────────────────────────────── it says what would change

def test_watch_for_names_a_real_level_not_a_platitude():
    pe = E.explain(crown(), SCEN)
    assert any("7,240" in w for w in pe["watch_for"])
    assert any("trend funds" in w for w in pe["watch_for"])


def test_a_missing_gamma_read_is_admitted_as_a_gap():
    pe = E.explain(crown(gamma_status="SKIPPED"), SCEN)
    assert any("dealer-positioning" in c for c in pe["caveats"])


def test_a_stale_read_says_so_in_the_caveats():
    c = crown()
    c["freshness"] = {"oldest_leg": "2026-06-11", "oldest_leg_days": 60,
                      "today": "2026-08-10"}
    pe = E.explain(c, SCEN)
    assert any("2026-06-11" in x and "only as\ncurrent".replace("\n", " ") in x
               or "2026-06-11" in x for x in pe["caveats"])


# ─────────────────────────────────────────────────── the gamma reading

def _profile(flip_dist_pct, positive=True):
    spot = 773.92
    return {"available": True, "spot": spot,
            "total_gex": (1.52e9 if positive else -1.52e9),
            "regime": "POSITIVE" if positive else "NEGATIVE",
            "gamma_flip": spot * (1 + flip_dist_pct / 100),
            "flip_distance_pct": flip_dist_pct,
            "call_wall": {"strike": 785.0, "share_of_side": 0.33},
            "put_wall": {"strike": 750.0, "share_of_side": 0.24},
            "total_open_interest": 753518}


def test_a_flip_sitting_on_spot_is_called_a_knife_edge():
    """+$1.5bn of positive gamma sounds comfortable. A flip 0.38% away is not,
    and a row of metrics will never say so."""
    r = E.gamma_reading(_profile(0.38))
    assert r["knife_edge"] is True
    joined = " ".join(r["lines"])
    assert "0.38%" in joined and "tipping point" in joined
    assert "Treat the calm as fragile" in joined


def test_a_distant_flip_is_reported_as_a_level_not_an_alarm():
    r = E.gamma_reading(_profile(4.5))
    assert r["knife_edge"] is False
    assert "This holds until" in " ".join(r["lines"])


def test_positive_and_negative_gamma_give_opposite_instructions():
    pos = E.gamma_reading(_profile(3.0, positive=True))
    neg = E.gamma_reading(_profile(3.0, positive=False))
    assert "sell rallies and buy dips" in pos["headline"]
    assert "buy rallies and sell dips" in neg["headline"]
    assert "do not chase breakouts" in " ".join(pos["lines"])
    assert "give stops more room" in " ".join(neg["lines"])


def test_the_walls_are_given_as_the_frame_with_their_share():
    line = next(l for l in E.gamma_reading(_profile(2.0))["lines"]
                if "heaviest positioning" in l)
    assert "750" in line and "785" in line and "%" in line


def test_an_unavailable_profile_says_nothing_rather_than_something_bland():
    r = E.gamma_reading({"available": False, "reason": "no open interest"})
    assert r["headline"] is None and r["lines"] == []
    assert r["reason"] == "no open interest"
    assert E.gamma_reading(None)["headline"] is None


# ────────────────────────────────────────────────────── it is GENERATED

def test_it_is_pure_and_regenerates_from_the_data():
    """No files, no network, no cached prose — the same input gives the same
    sentence, and a different input gives a different one."""
    a = E.explain(crown(vix=14.9), SCEN)
    b = E.explain(crown(vix=14.9), SCEN)
    c = E.explain(crown(vix=31.0), SCEN)
    assert a == b
    assert a["headline"] != c["headline"] or a["because"] != c["because"]


def test_every_family_has_plain_words():
    from src.macro.crown import spec as S
    for fam in S.EXPRESSION_FAMILIES:
        assert fam in E.FAMILY_PLAIN, fam


def test_every_scenario_has_plain_words():
    from src.macro import scenarios as SC
    for name in SC.SCENARIOS:
        assert name in E.SCENARIO_PLAIN, name


def test_every_divergence_check_has_plain_words():
    pe = E.explain(crown(fired=("rsi", "cross_asset", "vix", "breadth",
                                "breadth_ma", "dispersion", "positioning",
                                "rsi_slope"), weight=8), SCEN)
    line = next(b for b in pe["because"] if "warning sign" in b)
    for raw in ("rsi_slope", "breadth_ma", "cross_asset"):
        assert raw not in line


# ──────────────────────────── plain English, enforced not hoped for

def test_no_spec_section_references_reach_the_reader():
    """A reader does not have the kernel document open. "§2.4's practical rule
    is directional" tells them nothing and sends them somewhere they cannot go."""
    text = _all_text(E.explain(crown(), SCEN))
    assert "§" not in text
    for prof in (_profile(0.38), _profile(4.0)):
        assert "§" not in " ".join(E.gamma_reading(prof)["lines"])


def test_the_prose_does_not_explain_our_own_implementation():
    """Why a field exists is a code comment. The reader wants to know what the
    market is doing, not why we store level and direction in two places."""
    text = _all_text(E.explain(crown(), SCEN)).lower()
    for tell in ("shown separately", "we store", "the process trims",
                 "is what makes", "self-damping", "denominator",
                 "reported as", "this field"):
        assert tell not in text, f"implementation talk leaked: {tell}"


def test_sentences_are_sentences():
    """No fragments. Every line starts with a capital and ends with a stop."""
    pe = E.explain(crown(), SCEN)
    for line in pe["because"] + pe["watch_for"]:
        stripped = line.replace("**", "").strip()
        assert stripped[0].isupper() or stripped[0].isdigit(), \
            f"does not start as a sentence: {stripped[:50]}"
        assert stripped.endswith((".", "?")), \
            f"does not end as a sentence: {stripped[-50:]}"


def test_it_does_not_say_the_same_thing_twice_in_one_line():
    """The complaint that prompted this: four restatements of one idea."""
    pe = E.explain(crown(disp_state="ELEVATED_EASING"), SCEN)
    vol_line = next(b for b in pe["because"] if "volatile than the index" in b)
    low = vol_line.lower()
    # "draining", "unwinding", "leaving" and "the end of the move" were four
    # ways of saying one thing. One survivor only.
    synonyms = sum(w in low for w in ("draining", "unwinding", "leaving",
                                      "end of the move"))
    assert synonyms <= 1, f"still restating itself: {vol_line}"
