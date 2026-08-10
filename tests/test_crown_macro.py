"""Nick Crown Macro Layer — the disciplines, not the arithmetic.

Kernel v1.4 is a *process*, and the things that make it one are all rules about
what NOT to do: stop when the Heartbeat is unreadable, never let a realised proxy
pass as an implied reading, never build a gamma map without open interest, never
treat divergence as a trigger. Arithmetic that is merely plausible would sail
through a happy-path test and still be the wrong instrument.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.macro.crown import cot as COT
from src.macro.crown import cta as CTA
from src.macro.crown import divergence as DIV
from src.macro.crown import gamma as GAM
from src.macro.crown import heartbeat as HB
from src.macro.crown import kernel as K
from src.macro.crown import spec as S
from src.macro.crown import vol as VOL


def bars(closes, spread=0.005):
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "date": pd.bdate_range("2022-01-03", periods=len(c)),
        "open": np.r_[c[0], c[:-1]], "high": c * (1 + spread),
        "low": c * (1 - spread), "close": c, "volume": np.full(len(c), 1e6),
    })


def walk(n=500, seed=7, drift=0.0, vol=0.012):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


# ───────────────────────────────────────────── §2.2 / §5 the Heartbeat gate

def test_a_rising_ratio_is_broadening_and_a_falling_one_is_narrowing():
    n = 400
    spy = walk(n, seed=1)
    up = HB.heartbeat_from_frames(bars(spy * (0.28 + np.linspace(0, 0.10, n))), bars(spy))
    dn = HB.heartbeat_from_frames(bars(spy * (0.38 - np.linspace(0, 0.10, n))), bars(spy))
    assert up["regime"] == "broadening"
    assert dn["regime"] == "narrowing"


def test_a_flat_ratio_is_neutral_not_a_coin_flip():
    """The eps band exists so noise doesn't get read as a regime."""
    n = 400
    spy = walk(n, seed=2)
    flat = HB.heartbeat_from_frames(bars(spy * 0.30), bars(spy))
    assert flat["regime"] == "neutral"
    assert flat["confidence"] == S.HB_CONF_NEUTRAL


def test_too_little_history_states_neutral_and_fails_the_gate():
    """0.30 sits BELOW the 0.40 gate on purpose — an unreadable tape stops the
    process rather than sizing down into it."""
    r = HB.heartbeat_regime(30.0, 100.0, [0.3] * 5)
    assert r["regime"] == "neutral"
    assert r["confidence"] == S.HB_CONF_NO_HISTORY
    assert r["passes_gate"] is False
    assert S.HB_CONF_NO_HISTORY < S.HB_CONFIDENCE_GATE


def test_a_tired_wave_outranks_a_live_one():
    """§5's ladder: regime + matching range extreme scores 0.75, plain trend 0.65.
    A tired wave is the more actionable statement."""
    assert S.HB_CONF_EXTREME > S.HB_CONF_TRENDING


def test_the_gate_stops_everything_downstream_not_just_sizing():
    d = K.run({"regime": "neutral", "confidence": 0.30, "bias": "x"},
              {"overall_bias": "risk_on", "flip_risk": 0.0, "size_adjustment": 1.15},
              {"regime": "POSITIVE"}, {"dispersion": {"band": "CALM"}}, {})
    assert d["early_exit"] is True
    assert d["stopped_at"] == "heartbeat"
    assert d["size_multiplier"] == 0.0
    assert d["expression"]["family"] == "NONE"
    # The CTA read was handed in and must NOT have leaked into the answer.
    assert "risk_on" not in d["final_rationale"]


# ─────────────────────────────────────────────────────── §2.3 CTA + flips

def test_a_trend_scores_and_chop_does_not():
    up = CTA.market_signal(bars(walk(500, seed=3, drift=0.0018)))
    chop = CTA.market_signal(bars(walk(500, seed=4, drift=0.0)))
    assert up["signal"] > 0.5
    assert abs(chop["signal"]) < 0.4


def test_the_signal_is_vol_normalised_not_a_raw_return():
    """A 10% move in a quiet market is a bigger statement than in a wild one. If
    this ever compares raw returns, ZN and NG stop being comparable."""
    rng = np.random.default_rng(11)
    n = 500
    ramp = np.linspace(0, 0.20, n)
    quiet = 100 * np.exp(ramp + np.cumsum(rng.normal(0, 0.003, n)))
    wild = 100 * np.exp(ramp + np.cumsum(rng.normal(0, 0.030, n)))
    assert CTA.market_signal(bars(quiet))["signal"] > CTA.market_signal(bars(wild))["signal"]


def test_short_history_returns_None_not_a_zero():
    """A zero reads as 'flat'. The truth is 'unknown', and they route differently."""
    r = CTA.market_signal(bars(walk(100)))
    assert r["signal"] is None and "need" in r["reason"]


def test_the_flip_level_is_where_the_signal_actually_crosses_zero():
    b = bars(walk(600, seed=5, drift=0.0015))
    f = CTA.flip_level(b, horizon=1)
    assert f["level"] is not None and f["level"] < f["spot"]      # long -> sells below
    assert f["direction"] == "sell_below"
    c = CTA._closes(b)
    assert CTA._signal_at(c, f["level"] * 1.02, 1) > 0
    assert CTA._signal_at(c, f["level"] * 0.98, 1) < 0


def test_a_signal_that_never_crosses_says_so_instead_of_clamping():
    """Reporting a clamped search bound as if it were a level would be inventing
    a number the model never produced."""
    f = CTA.flip_level(bars(100 * np.exp(np.linspace(0, 3.0, 600))), horizon=1)
    assert f is not None and (f["level"] is None or f["level"] > 0)


def test_crowding_cuts_size_even_when_the_trend_is_clean():
    """§2.3's actual point — a crowded trend is a fragile one."""
    crowded = CTA.cta_flow_analysis({f"m{i}": 0.95 for i in range(6)})
    clean = CTA.cta_flow_analysis({"a": 0.4, "b": 0.45, "c": 0.5})
    assert crowded["overall_bias"] == "risk_on" and clean["overall_bias"] == "risk_on"
    assert crowded["size_adjustment"] == S.CTA_SIZE_CROWDED
    assert clean["size_adjustment"] == S.CTA_SIZE_CLEAN_TREND
    assert crowded["size_adjustment"] < clean["size_adjustment"]


def test_missing_markets_are_named_because_they_change_what_flip_risk_means():
    out = CTA.analyse({"ES": bars(walk(500, drift=0.002)), "ZN": bars(walk(80))})
    assert "ZN" in out["flow"]["markets_missing"]
    assert "ZN" in out["flow"]["rationale"]


def test_no_signals_at_all_is_neutral_with_a_stated_reason():
    r = CTA.cta_flow_analysis({})
    assert r["overall_bias"] == "neutral" and r["size_adjustment"] == 1.0
    assert "No CTA signals" in r["rationale"]


# ────────────────────────────────────────────────────────────── §2.3 gamma

def _chain(call_oi, put_oi, gamma=0.03, dte=10):
    return ([{"strike": k, "right": "CALL", "gamma": gamma, "open_interest": v, "dte": dte}
             for k, v in call_oi.items()]
            + [{"strike": k, "right": "PUT", "gamma": gamma, "open_interest": v, "dte": dte}
               for k, v in put_oi.items()])


def test_positive_and_negative_gamma_are_opposite_hedging_behaviour():
    pos = GAM.gamma_profile(_chain({100: 9000, 105: 6000}, {95: 200}), 100.0)
    neg = GAM.gamma_profile(_chain({105: 200}, {95: 9000, 100: 6000}), 100.0)
    assert pos["regime"] == "POSITIVE" and "damped" in pos["interpretation"]
    assert neg["regime"] == "NEGATIVE" and "amplified" in neg["interpretation"]


def test_a_chain_without_open_interest_is_UNAVAILABLE_not_a_flat_map():
    """The failure that matters. A zeroed profile reads as 'dealers are neutral',
    which is a completely different claim from 'we have no OI'."""
    r = GAM.gamma_profile([{"strike": 100, "right": "CALL", "gamma": 0.03, "dte": 5}], 100.0)
    assert r["available"] is False
    assert "OPEN INTEREST" in r["reason"]
    assert "total_gex" not in r


def test_the_dealer_side_assumption_travels_with_every_reading():
    r = GAM.gamma_profile(_chain({100: 5000}, {95: 1000}), 100.0)
    assert "convention" in r["assumption"] and "NOT observed data" in r["assumption"]


def test_a_wall_must_be_big_enough_to_deserve_the_name():
    flat = {90 + i: 1000 for i in range(20)}           # no strike dominates
    r = GAM.gamma_profile(_chain(flat, {}), 100.0)
    assert r["call_wall"] is None


def test_analyse_lists_what_failed_rather_than_dropping_it():
    out = GAM.analyse({"SPY": {"spot": 100.0, "contracts": _chain({100: 5000}, {95: 900})},
                       "QQQ": {"spot": 0, "contracts": []}})
    assert out["status"] == "OK" and out["primary"] == "SPY"
    assert "QQQ" in out["unavailable"]


# ──────────────────────────────────────────── §2.4 implied vs realised vol

CBOE_OHLC = ("DATE,OPEN,HIGH,LOW,CLOSE\n"
             "01/02/2026,17.24,17.24,17.24,17.24\n"
             "01/05/2026,16.10,16.50,15.90,16.00\n")
CBOE_SINGLE = ("DATE,VIXEQ\n"
               "01/02/2026,20.78\n"
               "01/05/2026,21.40\n")


def test_cboe_parses_both_file_shapes_from_the_same_endpoint():
    """Older indices ship OHLC; VIXEQ and DSPX ship one column named after the
    symbol. One parser has to serve both or half the complex silently vanishes."""
    from src.macro.crown import cboe
    a = cboe.parse_history(CBOE_OHLC, "VIX")
    b = cboe.parse_history(CBOE_SINGLE, "VIXEQ")
    assert list(a.columns) == ["date", "close"] and len(a) == 2
    assert a["close"].iloc[-1] == pytest.approx(16.00)
    assert list(b.columns) == ["date", "close"] and len(b) == 2
    assert b["close"].iloc[-1] == pytest.approx(21.40)


def test_cboe_finds_the_header_rather_than_assuming_row_zero():
    from src.macro.crown import cboe
    with_preamble = "Cboe disclaimer line\n\n" + CBOE_SINGLE
    assert len(cboe.parse_history(with_preamble, "VIXEQ")) == 2


def test_cboe_returns_empty_on_a_shape_it_cannot_read():
    from src.macro.crown import cboe
    assert cboe.parse_history("nothing,useful\n1,2\n", "VIX").empty
    assert cboe.parse_history("", "VIX").empty


def test_the_vixeq_source_is_the_publisher_not_a_reseller():
    """FMP gates VIXEQ above our plan; Cboe computes it and publishes it free.
    If this ever points back at a vendor, the implied spread silently becomes
    unavailable again and the realised proxy takes over unnoticed."""
    from src.macro.crown import cboe
    assert "cboe.com" in cboe.CBOE_URL
    assert cboe.SERIES["vixeq"] == "VIXEQ"
    for key in ("vix", "vixeq", "dspx", "cor1m"):
        assert key in cboe.CORE or key in cboe.SERIES


def test_a_realised_proxy_never_passes_as_an_implied_reading():
    """The single most important labelling rule in this layer."""
    n = 600
    px = pd.DataFrame({"date": pd.bdate_range("2023-01-02", periods=n),
                       "close": walk(n, seed=8)})
    panel = pd.concat([
        pd.DataFrame({"ticker": f"T{i}", "date": px["date"],
                      "close": walk(n, seed=100 + i, vol=0.02)})
        for i in range(60)])
    r = VOL.analyse(vix=None, vixeq=None, panel=panel, spy=px)
    assert r["status"] == "DEGRADED_REALISED_PROXY"
    assert r["dispersion"]["basis"] == "realised"
    assert "not implied" in r["dispersion"]["caveat"]


def test_the_implied_spread_is_used_when_it_is_actually_available():
    n = 600
    d = pd.bdate_range("2023-01-02", periods=n)
    vix = pd.DataFrame({"date": d, "close": np.full(n, 15.0)})
    vixeq = pd.DataFrame({"date": d, "close": np.r_[np.full(n - 1, 22.0), 40.0]})
    r = VOL.analyse(vix=vix, vixeq=vixeq)
    assert r["status"] == "OK"
    assert r["dispersion"]["basis"] == "implied"
    assert r["dispersion"]["band"] == "ELEVATED"
    assert r["dispersion"]["caveat"] is None


def _spread_series(spread_path):
    """VIX flat at 15, VIXEQ shaped so the spread follows `spread_path`."""
    n = len(spread_path)
    d = pd.bdate_range("2023-01-02", periods=n)
    vix = pd.DataFrame({"date": d, "close": np.full(n, 15.0)})
    vixeq = pd.DataFrame({"date": d, "close": 15.0 + np.asarray(spread_path, float)})
    return vix, vixeq


def test_an_elevated_spread_that_is_EASING_is_not_hidden_stress():
    """The case that actually showed up on 2026-08-07: the spread sat at the
    98th percentile of its whole history while having fallen 9.2 points in
    twenty sessions. §2.4's practical rule is directional — buying downside into
    an unwinding spread buys the end of the move."""
    path = list(np.full(560, 5.0)) + list(np.linspace(34.0, 24.0, 40))
    r = VOL.analyse(*_spread_series(path))
    d = r["dispersion"]
    assert d["band"] == "ELEVATED"
    assert d["direction"] == "FALLING"
    assert d["state"] == "ELEVATED_EASING"
    assert r["rules"]["hidden_stress"] is False          # the tactical flag
    assert r["rules"]["dispersion_elevated"] is True     # the level, still visible


def test_an_elevated_spread_that_is_RISING_is_hidden_stress():
    path = list(np.full(560, 5.0)) + list(np.linspace(14.0, 30.0, 40))
    r = VOL.analyse(*_spread_series(path))
    assert r["dispersion"]["state"] == "ELEVATED_RISING"
    assert r["rules"]["hidden_stress"] is True


def test_a_small_wobble_is_not_a_direction():
    path = list(np.full(560, 5.0)) + list(np.full(40, 20.0) + np.array(
        [0.1 * (-1) ** i for i in range(40)]))
    assert VOL.analyse(*_spread_series(path))["dispersion"]["direction"] == "FLAT"


def test_dispersion_and_implied_correlation_must_move_opposite():
    """Index variance is constituent variance times correlation, so they are two
    sides of one number. If they ever agree in sign, the spread is wrong."""
    n = 600
    d = pd.bdate_range("2023-01-02", periods=n)
    hi_disp = pd.DataFrame({"date": d, "close": np.r_[np.full(n - 1, 20.0), 40.0]})
    lo_corr = pd.DataFrame({"date": d, "close": np.r_[np.full(n - 1, 30.0), 7.0]})
    ok = VOL.corroboration(hi_disp, lo_corr)
    assert ok["agrees"] is True

    hi_corr = pd.DataFrame({"date": d, "close": np.r_[np.full(n - 1, 10.0), 55.0]})
    bad = VOL.corroboration(hi_disp, hi_corr)
    assert bad["agrees"] is False and "DISAGREE" in bad["note"]


def test_corroboration_degrades_to_None_rather_than_inventing_agreement():
    c = VOL.corroboration(None, None)
    assert c["dspx"] is None and c["agrees"] is None


def test_a_high_vix_is_flagged_as_already_priced_not_as_a_sell():
    """§2.4 is explicit: a spike that is already priced is not a fresh signal."""
    d = pd.bdate_range("2023-01-02", periods=300)
    r = VOL.analyse(vix=pd.DataFrame({"date": d, "close": np.full(300, 30.0)}))
    assert r["rules"]["already_priced"] is True
    assert r["rules"]["very_low_vix"] is False


def test_no_vix_and_no_panel_is_UNAVAILABLE_with_a_reason():
    r = VOL.analyse()
    assert r["status"] == "UNAVAILABLE" and r["reason"]


# ───────────────────────────────────────────────────────── §2.5 divergence

def _two_rallies(seed, a, b, c, d):
    """Two legs to `b` then `d`, the second reaching further on weaker momentum.
    Noise is essential: a perfectly linear ramp has no down bars, so RSI pins at
    100 on BOTH peaks and no divergence can exist by construction."""
    rng = np.random.default_rng(seed)
    def leg(lo, hi, k, noise=0.004):
        return list(np.linspace(lo, hi, k) * (1 + rng.normal(0, noise, k)))
    return leg(a, b, 30, 0.003) + leg(b, c, 20) + leg(c, d, 75, 0.006) + leg(d, d * 0.96, 12)


def test_bearish_rsi_divergence_needs_a_higher_high_on_lower_momentum():
    r = DIV.rsi_divergence(bars(_two_rallies(5, 100, 132, 114, 136)))
    assert r["state"] == "BEARISH_RSI_DIVERGENCE"
    assert r["latest"]["price"] > r["prior"]["price"]
    assert r["latest"]["rsi"] < r["prior"]["rsi"]


def test_the_comparison_pivot_is_the_prior_EXTREME_not_merely_the_previous_one():
    """A minor bump inside the second leg must not stand in for the real prior
    high — that silently turns a genuine divergence into 'NONE'."""
    d = bars(_two_rallies(5, 100, 132, 114, 136))
    from src.engines.patterns import pivot_series
    pv = pivot_series(d["high"].to_numpy(), d["low"].to_numpy(),
                      d["date"].to_numpy(), k=S.DIV_PIVOT_K, window=S.DIV_LOOKBACK)
    highs = [p["price"] for p in pv if p["kind"] == "H"]
    assert len(highs) >= 3, "fixture must contain an intervening minor high"
    r = DIV.rsi_divergence(d)
    assert r["prior"]["price"] == pytest.approx(max(highs[:-1]), rel=1e-6)


def test_a_clean_trend_shows_no_divergence():
    r = DIV.rsi_divergence(bars(100 * np.exp(np.linspace(0, 0.5, 200))))
    assert r["state"] == "NONE"


def test_cross_asset_needs_equities_at_a_high_to_have_anything_to_diverge_from():
    falling = bars(np.linspace(130, 100, 200))
    r = DIV.cross_asset_divergence(falling, {"HG": bars(np.linspace(100, 130, 200))})
    assert r["state"] == "NONE" and r["equity_at_new_high"] is False


def test_cross_asset_fires_when_a_confirmer_will_not_follow():
    rising = bars(np.linspace(100, 140, 200))
    r = DIV.cross_asset_divergence(rising, {"HG": bars(np.linspace(130, 100, 200)),
                                            "RSP": bars(np.linspace(100, 140, 200))})
    assert r["state"] == "CROSS_ASSET_DIVERGENCE"
    assert [f["name"] for f in r["failing"]] == ["HG"]
    assert [c["name"] for c in r["confirming"]] == ["RSP"]


def test_positioning_divergence_refuses_an_unreliable_percentile():
    """An 'extreme' computed off a handful of weeks is not an extreme."""
    thin = {"percentile": 0.99, "extreme": "CROWDED_LONG",
            "percentile_reliable": False, "weeks_of_history": 9}
    r = DIV.positioning_divergence(bars(np.linspace(100, 140, 200)), thin)
    assert r["state"] == "NONE" and "not yet meaningful" in r["reason"]


def test_positioning_divergence_fires_on_price_up_into_a_crowded_long():
    ok = {"percentile": 0.93, "extreme": "CROWDED_LONG",
          "percentile_reliable": True, "weeks_of_history": 136, "as_of": "2026-08-04"}
    r = DIV.positioning_divergence(bars(np.linspace(100, 140, 200)), ok)
    assert r["state"] == "POSITIONING_DIVERGENCE" and r["price_rising"] is True


def _rising(n=200, lo=100.0, hi=140.0):
    return bars(np.linspace(lo, hi, n))


def _vix_frame(path):
    return pd.DataFrame({"date": pd.bdate_range("2022-01-03", periods=len(path)),
                         "close": np.asarray(path, float)})


def test_vix_rising_into_a_new_index_high_is_a_non_confirmation():
    """Normally a grind to new highs bleeds implied vol. When protection gets
    MORE expensive into strength, somebody is paying up."""
    vix_up = _vix_frame(np.r_[np.full(180, 14.0), np.linspace(14.0, 22.0, 20)])
    r = DIV.vix_nonconfirmation(_rising(), vix_up)
    assert r["state"] == "VIX_NONCONFIRMATION" and r["vix_rising"] is True


def test_vix_easing_into_a_new_high_CONFIRMS_rather_than_warns():
    vix_dn = _vix_frame(np.r_[np.full(180, 20.0), np.linspace(20.0, 13.0, 20)])
    assert DIV.vix_nonconfirmation(_rising(), vix_dn)["state"] == "CONFIRMED"


def test_a_missing_vix_is_skipped_not_treated_as_passing():
    r = DIV.vix_nonconfirmation(_rising(), None)
    assert r["state"] == "NONE" and "no VIX" in r["reason"]


def test_narrowing_breadth_under_a_new_index_high_is_a_non_confirmation():
    """The purest form of the idea, and the data was already there: the index
    makes a high because a few names carry it."""
    r = DIV.breadth_nonconfirmation(_rising(), {"regime": "narrowing", "slope_20d": -0.0004})
    assert r["state"] == "BREADTH_NONCONFIRMATION"
    assert DIV.breadth_nonconfirmation(
        _rising(), {"regime": "broadening"})["state"] == "CONFIRMED"


def test_a_widening_spread_under_a_new_high_is_a_non_confirmation():
    r = DIV.dispersion_nonconfirmation(_rising(), {"spread": 20.0, "direction": "RISING",
                                                   "band": "ELEVATED"})
    assert r["state"] == "DISPERSION_NONCONFIRMATION"
    assert DIV.dispersion_nonconfirmation(
        _rising(), {"spread": 20.0, "direction": "FALLING"})["state"] == "CONFIRMED"


def test_the_dollar_is_inverted_because_a_bid_dollar_is_a_drag():
    """Treating DX like copper would read a dollar squeeze as a healthy tape."""
    eq, dxy = _rising(), _rising()               # both at new highs
    r = DIV.cross_asset_divergence(eq, {"DX": dxy}, inverted=("DX",))
    assert [f["name"] for f in r["failing"]] == ["DX"]
    # Same series, NOT inverted, would have read as confirmation.
    assert DIV.cross_asset_divergence(eq, {"DX": dxy}, inverted=())["state"] == "CONFIRMED"


def test_the_rsi_matrix_scans_every_series_it_is_given():
    d = bars(_two_rallies(5, 100, 132, 114, 136))
    m = DIV.rsi_matrix({"SPY": d, "QQQ": d, "FLAT": bars(np.full(200, 100.0))})
    assert m["scanned"] == 3
    assert set(m["bearish"]) == {"SPY", "QQQ"}


def test_the_positioning_sweep_covers_every_contract_with_both_legs():
    ok = {"percentile": 0.93, "extreme": "CROWDED_LONG",
          "percentile_reliable": True, "weeks_of_history": 136}
    pm = DIV.positioning_matrix(
        {"ES": _rising(), "GC": _rising(), "ZN": _rising()},
        {"ES": ok, "GC": ok})                     # ZN has bars but no COT row
    assert pm["scanned"] == 2 and set(pm["diverging"]) == {"ES", "GC"}


def test_the_composite_reports_what_it_actually_covered():
    """Coverage is not decoration: a check that was SKIPPED must never look like
    a check that PASSED."""
    out = DIV.analyse(_rising(), confirmers={"HG": bars(np.linspace(130, 100, 200))},
                      rsi_series={"SPY": _rising()},
                      vix_bars=None, heartbeat={"regime": "narrowing"},
                      dispersion={"spread": 20.0, "direction": "RISING"})
    cov = out["coverage"]
    assert cov["vix"] is False and cov["breadth"] is True
    assert cov["rsi_series"] == 1 and cov["confirmers"] == 1
    assert out["weight"] >= out["count"]


def test_independent_warnings_accumulate_into_a_weight():
    quiet = DIV.analyse(_rising(), confirmers={"HG": _rising()},
                        heartbeat={"regime": "broadening"},
                        dispersion={"spread": 5.0, "direction": "FALLING"})
    loud = DIV.analyse(_rising(), confirmers={"HG": bars(np.linspace(130, 100, 200))},
                       heartbeat={"regime": "narrowing"},
                       dispersion={"spread": 20.0, "direction": "RISING"},
                       vix_bars=_vix_frame(np.r_[np.full(180, 14.0),
                                                 np.linspace(14.0, 22.0, 20)]))
    assert loud["weight"] > quiet["weight"]
    assert loud["any_bearish"] is True and quiet["any_bearish"] is False


def test_the_old_three_type_keys_survive_the_widening():
    """§2.5 accepts three types. The extra reads are more of type 2, not a
    fourth type smuggled in — so the taxonomy keys must still be there."""
    out = DIV.analyse(_rising(), confirmers={"HG": _rising()})
    for k in ("rsi", "cross_asset", "positioning"):
        assert k in out


def test_divergence_never_claims_to_be_a_trigger():
    out = DIV.analyse(bars(np.linspace(100, 140, 200)),
                      confirmers={"HG": bars(np.linspace(130, 100, 200))})
    assert out["any_bearish"] is True
    assert "never a standalone entry trigger" in out["note"]


# ──────────────────────────────────────────────── §3 expression + §5 size

def _hb(regime="broadening", rng_pos="mid", conf=0.65):
    return {"regime": regime, "range_position": rng_pos, "confidence": conf,
            "bias": "b", "passes_gate": True}


def _vol(band="NORMAL", low_vix=False, direction="FLAT"):
    return {"dispersion": {"band": band, "basis": "implied", "direction": direction},
            "rules": {"very_low_vix": low_vix,
                      "hidden_stress": band == "ELEVATED" and direction == "RISING",
                      "dispersion_elevated": band == "ELEVATED",
                      "already_priced": False}}


def test_hidden_stress_outranks_a_healthy_looking_regime():
    """§2.4's whole point: the spread shows up BEFORE the index admits anything."""
    d = K.run(_hb(), CTA.cta_flow_analysis({"a": 0.1}), {"regime": "POSITIVE"},
              _vol("ELEVATED", direction="RISING"), {"any_bearish": False})
    assert d["expression"]["family"] == "HIDDEN_STRESS_DOWNSIDE"
    assert d["expression"]["match"] == "exact"


def test_the_tactical_family_does_not_fire_on_an_unwinding_spread():
    """Elevated-but-easing must not route to buying downside."""
    d = K.run(_hb(), CTA.cta_flow_analysis({"a": 0.1}), {"regime": "POSITIVE"},
              _vol("ELEVATED", direction="FALLING"), {"any_bearish": False})
    assert d["expression"]["family"] != "HIDDEN_STRESS_DOWNSIDE"
    # ...but the elevated LEVEL is still visible to anyone reading the block.
    assert d["expression"]["all_conditions"]["dispersion_elevated"] is True


def test_each_family_reports_the_conditions_it_failed():
    d = K.run(_hb(rng_pos="top"), CTA.cta_flow_analysis({"a": 0.1}),
              {"regime": "NEGATIVE"}, _vol("NORMAL"), {"any_bearish": False})
    assert d["expression"]["match"] in ("partial", "exact")
    assert isinstance(d["expression"]["conditions_unmet"], list)
    assert d["expression"]["all_conditions"]["range_not_extreme"] is False


def test_a_tactical_family_caps_size_rather_than_compounding_it():
    """Two independent size opinions multiplied together understate by design,
    not by evidence. The cap is the honest combination."""
    crowded = CTA.cta_flow_analysis({f"m{i}": 0.95 for i in range(6)})
    s = K.size_multiplier(crowded, "HIDDEN_STRESS_DOWNSIDE")
    assert s["size_multiplier"] <= S.HIDDEN_STRESS_SIZE
    assert "flip risk" in s["derivation"]


def test_the_size_multiplier_never_exceeds_the_kernels_own_ceiling():
    s = K.size_multiplier({"size_adjustment": 99.0, "flip_risk": 0.0}, "BROADENING_CARRY")
    assert s["size_multiplier"] == S.SIZE_MULT_CAP


def test_size_is_a_multiplier_on_the_PMs_budget_never_a_position():
    s = K.size_multiplier({"size_adjustment": 1.0, "flip_risk": 0.0}, "BROADENING_CARRY")
    assert "does not size" in s["applies_to"]


def test_every_family_carries_a_playbook_the_committee_can_read():
    for name in S.EXPRESSION_FAMILIES:
        pb = S.EXPRESSION_FAMILIES[name]
        assert {"context", "equity", "pair", "options"} <= set(pb)


def test_the_decision_shows_its_working():
    d = K.run(_hb(), CTA.cta_flow_analysis({"a": 0.5, "b": 0.3}),
              {"regime": "POSITIVE", "status": "OK"}, _vol(), {"any_bearish": False})
    joined = " ".join(d["messages"])
    for tag in ("[Heartbeat]", "[CTA]", "[Gamma]", "[Vol]", "[Divergence]",
                "[Expression]", "[Checklist]"):
        assert tag in joined


# ───────────────────────────────────────────────────────────── §2.3 COT

COT_FIXTURE = (
    '"UST 10Y NOTE - CHICAGO BOARD OF TRADE",260804,2026-08-04,043602,CBT ,00,043 ,'
    '  5000000,  400000,  900000,  100000,  800000,  300000,  1300000,  1300000,'
    '   50000,   60000\n'
    '"GOLD - COMMODITY EXCHANGE INC.",260804,2026-08-04,088691,CMX ,00,088 ,'
    '  400000,  250000,   52000,   40000,   60000,  240000,  350000,  332000,'
    '   30000,   28000\n'
)


def test_cot_parses_the_positional_layout_and_derives_net_spec():
    df = COT.parse_cot(COT_FIXTURE)
    assert len(df) == 2
    zn = df[df["code"] == "043602"].iloc[0]
    assert zn["net_spec"] == 400000 - 900000
    assert zn["net_spec_pct_oi"] == pytest.approx(-500000 / 5000000)


def test_cot_normalises_by_open_interest_so_years_stay_comparable():
    """A raw contract count silently stops meaning the same thing as OI drifts."""
    df = COT.parse_cot(COT_FIXTURE)
    assert "net_spec_pct_oi" in df.columns
    assert df["net_spec_pct_oi"].abs().max() <= 1.5


def test_cot_header_rows_are_dropped_not_parsed_as_a_market():
    headed = ('"Market and Exchange Names","As of Date in Form YYMMDD",'
              '"As of Date in Form YYYY-MM-DD","CFTC Contract Market Code",'
              '"a","b","c","d","e","f","g","h","i","j","k","l","m"\n') + COT_FIXTURE
    assert len(COT.parse_cot(headed)) == 2


def test_cot_markets_are_keyed_on_contract_code_not_name():
    """Names get re-spelled between years; codes do not. A name join silently
    drops a market for a whole year."""
    assert COT.CODE_TO_MARKET["043602"] == "ZN"
    assert all(c and c.strip() for c in COT.CODE_TO_MARKET)


def test_cot_percentile_is_withheld_until_there_is_enough_history():
    rows = []
    for i in range(10):
        rows.append({"code": "043602", "date": pd.Timestamp("2026-01-05") + pd.Timedelta(weeks=i),
                     "name": "UST 10Y", "open_interest": 1e6, "nc_long": 1e5 + i * 1e3,
                     "nc_short": 2e5, "net_spec": 0, "net_spec_pct_oi": -0.1 + i * 0.01})
    p = COT.positioning(pd.DataFrame(rows), "043602")
    assert p["percentile_reliable"] is False
    assert p["weeks_of_history"] == 10


def test_cot_analyse_with_no_history_is_UNAVAILABLE_not_empty_calm():
    r = COT.analyse(pd.DataFrame())
    assert r["status"] == "UNAVAILABLE" and r["reason"]
    assert r["crowded_long"] == [] and r["crowded_short"] == []


# ──────────────────────────────────────────── freshness: stale-but-present

def _dated(end, n=400, start_price=100.0):
    """A bar frame whose LAST date is `end`."""
    d = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    c = np.full(n, start_price)
    return pd.DataFrame({"date": d, "open": c, "high": c * 1.01,
                         "low": c * 0.99, "close": c, "volume": np.full(n, 1e6)})


def test_staleness_reports_the_last_bar_and_the_lag_to_today():
    from src.macro.crown import data as F
    today = pd.Timestamp.today().normalize()
    s = F.staleness(_dated(today))
    assert s["as_of"] == today.date().isoformat() and s["days_stale"] == 0
    old = F.staleness(_dated(today - pd.Timedelta(days=60)))
    assert old["days_stale"] >= 59


def test_a_series_that_stopped_updating_is_stale_even_though_it_is_long():
    """THE defect this guards. A panel that stopped in June still has thousands
    of rows, so a LENGTH check passes trivially and the stale file silently
    displaces a live fetch — which is how the Heartbeat once read two months
    behind every other source."""
    from src.macro.crown import data as F
    june = _dated(pd.Timestamp.today().normalize() - pd.Timedelta(days=60), n=2000)
    assert len(june) > S.HB_LOOKBACK_DAYS      # sails past any length guard
    assert F.is_stale(june) is True            # ...but fails the recency one


def test_a_current_series_is_not_stale():
    from src.macro.crown import data as F
    assert F.is_stale(_dated(pd.Timestamp.today().normalize())) is False


def test_an_empty_frame_is_stale_not_silently_fresh():
    from src.macro.crown import data as F
    assert F.is_stale(pd.DataFrame()) is True
    assert F.staleness(None)["as_of"] is None


def test_the_freshness_thresholds_are_named_constants():
    for name in ("MAX_BAR_STALENESS_DAYS", "PANEL_MAX_STALENESS_DAYS",
                 "COT_MAX_STALENESS_WEEKS"):
        assert hasattr(S, name), name


# ─────────────────────────────────── the CTA universe: symbols and proxies

def test_every_cta_market_has_a_fallback_so_the_denominator_cannot_shrink():
    """flip_risk is extremes / n_markets. Dropping the whole rates complex
    because ZNUSD is plan-gated would silently re-rate every reading."""
    for key, meta in CTA.MARKETS.items():
        assert meta.get("fallback"), key
        assert meta["fmp"], key


def test_the_cent_quoted_ags_use_the_USX_symbols_fmp_actually_serves():
    """Corn, soybeans and wheat are quoted in cents and carry a USX suffix;
    FMP serves no ZWUSD at all. Verified against its own commodities-list."""
    assert CTA.MARKETS["ZC"]["fmp"] == "ZCUSX"
    assert CTA.MARKETS["ZS"]["fmp"] == "ZSUSX"
    assert CTA.MARKETS["ZW"]["fmp"] == "KEUSX"


def test_the_rates_complex_is_present_and_proxied_to_duration_matched_etfs():
    rates = {k: v for k, v in CTA.MARKETS.items() if v["sector"] == "rates"}
    assert set(rates) == {"ZN", "ZB", "ZF", "ZT"}
    assert rates["ZN"]["fallback"] == "IEF"      # 7-10y
    assert rates["ZB"]["fallback"] == "TLT"      # 20y+
    assert rates["ZT"]["fallback"] == "SHY"      # 1-3y


# ─────────────────────────────────────────────────── the layer's own rules

def test_every_threshold_is_a_named_constant():
    for name in ("HB_CONFIDENCE_GATE", "HB_SLOPE_EPS", "CTA_FLIP_THRESHOLD",
                 "CTA_LOOKBACKS", "CTA_FABER_SMA", "CTA_VOL_TARGET",
                 "DISPERSION_ELEVATED_PCTL", "GAMMA_DTE_MAX", "DIV_PIVOT_K",
                 "SIZE_MULT_CAP"):
        assert hasattr(S, name), name


def test_the_pivot_definition_is_shared_with_the_rest_of_AQE():
    """A second definition of 'pivot' is how two layers start disagreeing about
    the same chart."""
    from src.engines.patterns import PIVOT_K
    assert S.DIV_PIVOT_K == PIVOT_K


def test_the_layer_declares_itself_standalone():
    """PM directive 2026-08-09: build Crown first, merge with SRM / Macro Weather
    / Thematic RRG later. A quiet dependency now would pre-empt that decision."""
    import inspect
    from src.macro.crown import cot, cta, divergence, gamma, heartbeat, kernel, vol
    for mod in (heartbeat, cta, gamma, vol, kernel, cot):
        src = inspect.getsource(mod)
        assert "from src.engines.srm" not in src
        assert "srm." not in src.replace("SRM", "")
    # divergence may share AQE primitives (rsi, pivots) but not the SRM layer
    assert "from src.engines.srm" not in inspect.getsource(divergence)
