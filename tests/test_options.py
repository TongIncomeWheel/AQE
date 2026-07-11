"""Unit tests for the AQE Options engine — pure, deterministic, no I/O."""

from __future__ import annotations

import math

import pytest

from src.options import config as C
from src.options.greeks import bs_price, bs_greeks, implied_vol, prob_below, year_fraction
from src.options.csp import analyze_csp, analyze_put_spread
from src.options import scanner as SC


R, Q = 0.04, 0.0
S0, T0, SIG = 100.0, 0.5, 0.25


# ── Black-Scholes core ──────────────────────────────────────────────────────
def test_put_call_parity():
    K = 105.0
    c = bs_price(S0, K, T0, SIG, "CALL", R, Q)
    p = bs_price(S0, K, T0, SIG, "PUT", R, Q)
    lhs = c - p
    rhs = S0 * math.exp(-Q * T0) - K * math.exp(-R * T0)
    assert lhs == pytest.approx(rhs, abs=1e-9)


def test_atm_call_approx():
    # For r=q=0, ATM call ≈ 0.3989·S·σ·√T (the classic approximation).
    c = bs_price(100.0, 100.0, 1.0, 0.20, "CALL", 0.0, 0.0)
    assert c == pytest.approx(0.3989 * 100 * 0.20, abs=0.05)


def test_expiry_is_intrinsic():
    assert bs_price(110, 100, 0.0, 0.25, "CALL", R, Q) == pytest.approx(10.0)
    assert bs_price(90, 100, 0.0, 0.25, "PUT", R, Q) == pytest.approx(10.0)


def test_greek_signs_and_ranges():
    call = bs_greeks(S0, 100, T0, SIG, "CALL", R, Q)
    put = bs_greeks(S0, 100, T0, SIG, "PUT", R, Q)
    assert 0.0 < call["delta"] < 1.0
    assert -1.0 < put["delta"] < 0.0
    assert call["gamma"] > 0 and put["gamma"] > 0
    assert call["gamma"] == pytest.approx(put["gamma"], abs=1e-12)   # gamma is right-agnostic
    assert call["vega"] > 0 and put["vega"] > 0
    assert call["theta"] < 0                                          # long call decays
    # Vega is per 1 vol-point → a fraction of the raw S·φ·√T.
    assert call["vega"] < S0 * T0


def test_iv_roundtrip():
    price = bs_price(S0, 95, T0, 0.32, "PUT", R, Q)
    iv = implied_vol(price, S0, 95, T0, "PUT", R, Q)
    assert iv == pytest.approx(0.32, abs=1e-4)


def test_iv_none_below_intrinsic():
    # A price under intrinsic value cannot be reproduced by any vol.
    assert implied_vol(1.0, 90, 100, T0, "PUT", R, Q) is None


def test_prob_below_matches_put_nd2():
    g = bs_greeks(S0, 95, T0, SIG, "PUT", R, Q)
    assert prob_below(S0, 95, T0, SIG, R, Q) == pytest.approx(g["nd2"], abs=1e-12)


# ── CSP economics ───────────────────────────────────────────────────────────
def _put_contract(strike, dte=30, iv=0.30, spot=100.0, ticker="TEST", spread=0.05):
    T = year_fraction(dte)
    fair = bs_price(spot, strike, T, iv, "PUT", R, Q)
    return {"ticker": ticker, "spot": spot, "strike": strike, "dte": dte, "iv": iv,
            "bid": round(fair - spread, 2), "ask": round(fair + spread, 2),
            "oi": 500, "volume": 100}


def test_csp_core_identities():
    c = _put_contract(95, dte=30, iv=0.30)
    m = analyze_csp(c, r=R, q=Q, fill="mid")
    assert m["valid"]
    credit = m["credit_per_share"]
    # breakeven = strike − credit; static yield = credit / strike.
    assert m["breakeven"] == pytest.approx(95 - credit, abs=0.01)
    assert m["static_yield"] == pytest.approx(credit / 95, abs=1e-4)
    # annualised = static × 365/DTE.
    assert m["annual_yield"] == pytest.approx(m["static_yield"] * 365 / 30, abs=1e-4)
    # collateral is cash-secured = strike × 100.
    assert m["collateral"] == pytest.approx(9500.0)
    # assignment prob = P(finish below strike); not-assigned = 1 − that.
    assert m["assignment_prob"] + m["pop_not_assigned"] == pytest.approx(1.0, abs=1e-6)
    # seller's theta credit is positive (time decay works for the writer).
    assert m["theta_credit_day"] > 0
    # max contracts against one 6-way capital slot ($70k/6 ≈ $11,667 → 1 lot of $9,500).
    assert m["max_contracts"] == 1


def test_csp_edge_sign_on_rich_quote():
    c = _put_contract(95, dte=30, iv=0.30)
    fair = 0.5 * (c["bid"] + c["ask"])
    c["bid"] = round(fair + 0.20, 2)          # market bid well above model
    c["ask"] = round(fair + 0.30, 2)
    m = analyze_csp(c, r=R, q=Q, fill="bid")
    assert m["edge_vs_model"] > 0             # selling above fair → positive edge


# ── Put credit spread ───────────────────────────────────────────────────────
def test_put_spread_defined_risk():
    short = _put_contract(95, dte=30, iv=0.30)
    long = _put_contract(90, dte=30, iv=0.32)
    s = analyze_put_spread(short, long, spot=100.0, r=R, q=Q, fill="mid")
    assert s["valid"]
    assert s["width"] == pytest.approx(5.0)
    # max_profit + max_loss = width × 100 (defined-risk identity).
    assert s["max_profit"] + s["max_loss"] == pytest.approx(500.0, abs=0.5)
    assert s["rrr"] == pytest.approx(s["max_profit"] / s["max_loss"], abs=1e-3)
    # $2,100 risk budget / max_loss per contract.
    assert s["max_contracts"] == int(C.RISK_BUDGET // s["max_loss"])


# ── Scanner: filters, ranking, selection ────────────────────────────────────
def test_scan_delta_band_rejects_far_otm():
    near = _put_contract(97, dte=30, iv=0.30)   # ~ATM-ish, delta in band
    far = _put_contract(70, dte=30, iv=0.30)    # deep OTM, |delta| below floor
    res = SC.scan_csps([near, far], r=R, q=Q,
                       min_annual_yield=0.0, min_pop=0.0, min_oi=0)
    passed_strikes = {p["strike"] for p in res["passed"]}
    assert 97 in passed_strikes
    assert 70 not in passed_strikes             # rejected by the delta floor
    reasons = " ".join(sum((r["reasons"] for r in res["rejected"]), []))
    assert "delta" in reasons


def test_scan_ranks_descending_and_best():
    cs = [_put_contract(k, dte=30, iv=0.35) for k in (96, 94, 92)]
    res = SC.scan_csps(cs, r=R, q=Q, min_annual_yield=0.0, min_pop=0.0,
                       delta_min=0.0, delta_max=1.0, min_oi=0)
    ys = [p["annual_yield"] for p in res["passed"]]
    assert ys == sorted(ys, reverse=True)       # ranked by annual_yield desc
    assert SC.best(res["passed"])["annual_yield"] == ys[0]


def test_calculator_backs_out_missing_iv():
    c = _put_contract(95, dte=30, iv=0.30)
    fair_mid = 0.5 * (c["bid"] + c["ask"])
    c.pop("iv")                                  # drop IV → calculator recovers it
    detail = SC.calculator(c, r=R, q=Q)
    assert detail["iv_used"] == pytest.approx(0.30, abs=0.02)
    assert "greeks" in detail and detail["greeks"]["delta"] < 0
