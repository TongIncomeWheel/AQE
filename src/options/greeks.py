"""Black-Scholes pricing + Greeks + implied-vol back-out (pure stdlib).

The chain from IBKR carries spot, strike, expiry and IV — but no Δ/Γ/Θ/ν/ρ. Those
are a deterministic transform of exactly those inputs; IBKR's own platform computes
them the same way (Black-Scholes for European, a binomial for American exercise — for
liquid ATM/OTM wheel puts the difference is within rounding).

Conventions
-----------
* `S` spot, `K` strike, `T` time-to-expiry in YEARS, `sigma` annualised vol (decimal,
  e.g. 0.25 = 25%), `r` risk-free (decimal), `q` continuous dividend yield (decimal).
* `right` is "CALL" or "PUT".
* Greeks are returned in **trader units**: delta per $1, gamma per $1, **theta per
  calendar day**, **vega per 1 vol point (1%)**, **rho per 1% rate**.
"""

from __future__ import annotations

import math
from statistics import NormalDist

from . import config as C

_N = NormalDist()          # standard normal
_cdf = _N.cdf
_pdf = _N.pdf


def year_fraction(dte_days: float) -> float:
    """Calendar days-to-expiry → year fraction on the config day-basis."""
    return max(float(dte_days), 0.0) / C.YEAR_DAYS


def _d1_d2(S, K, T, sigma, r, q):
    """The two Black-Scholes arguments. Caller guarantees T>0 and sigma>0."""
    vol_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    return d1, d2


def bs_price(S, K, T, sigma, right, r=None, q=None) -> float:
    """Black-Scholes fair (mid) value of one option — the market-maker price."""
    r = C.RISK_FREE_RATE if r is None else r
    q = C.DIVIDEND_YIELD if q is None else q
    right = right.upper()
    # Degenerate expiry → intrinsic value.
    if T <= 0 or sigma <= 0:
        if right == "CALL":
            return max(S - K, 0.0)
        return max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, sigma, r, q)
    disc_r, disc_q = math.exp(-r * T), math.exp(-q * T)
    if right == "CALL":
        return S * disc_q * _cdf(d1) - K * disc_r * _cdf(d2)
    return K * disc_r * _cdf(-d2) - S * disc_q * _cdf(-d1)


def bs_greeks(S, K, T, sigma, right, r=None, q=None) -> dict:
    """Full Greeks for one option in trader units (see module docstring).

    Returns a dict: price, delta, gamma, theta (per day), vega (per 1%),
    rho (per 1%), plus d1/d2 and the prob-ITM `nd2` used for POP.
    """
    r = C.RISK_FREE_RATE if r is None else r
    q = C.DIVIDEND_YIELD if q is None else q
    right = right.upper()
    price = bs_price(S, K, T, sigma, right, r, q)
    if T <= 0 or sigma <= 0:
        # No time value → intrinsic only, Greeks collapse.
        itm = (S > K) if right == "CALL" else (S < K)
        delta = (1.0 if right == "CALL" else -1.0) if itm else 0.0
        return {"price": price, "delta": delta, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "rho": 0.0, "d1": None, "d2": None,
                "nd2": (1.0 if (right == "CALL" and itm) else 0.0)}
    d1, d2 = _d1_d2(S, K, T, sigma, r, q)
    disc_r, disc_q = math.exp(-r * T), math.exp(-q * T)
    pdf_d1 = _pdf(d1)
    sqrt_t = math.sqrt(T)

    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t / 100.0       # per 1 vol point
    common_theta = -S * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
    if right == "CALL":
        delta = disc_q * _cdf(d1)
        theta = common_theta - r * K * disc_r * _cdf(d2) + q * S * disc_q * _cdf(d1)
        rho = K * T * disc_r * _cdf(d2) / 100.0
        nd2 = _cdf(d2)                                  # P(finish ITM) for a call
    else:
        delta = -disc_q * _cdf(-d1)
        theta = common_theta + r * K * disc_r * _cdf(-d2) - q * S * disc_q * _cdf(-d1)
        rho = -K * T * disc_r * _cdf(-d2) / 100.0
        nd2 = _cdf(-d2)                                 # P(finish ITM) for a put
    return {"price": price, "delta": delta, "gamma": gamma,
            "theta": theta / C.YEAR_DAYS,               # per calendar day
            "vega": vega, "rho": rho, "d1": d1, "d2": d2, "nd2": nd2}


def prob_below(S, K, T, sigma, r=None, q=None) -> float:
    """Risk-neutral P(S_T < K) — used for a short put's assignment probability
    and for prob-of-profit at an arbitrary breakeven level. `None` if undefined."""
    r = C.RISK_FREE_RATE if r is None else r
    q = C.DIVIDEND_YIELD if q is None else q
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 1.0 if S < K else 0.0
    _, d2 = _d1_d2(S, K, T, sigma, r, q)
    return _cdf(-d2)


def implied_vol(price, S, K, T, right, r=None, q=None,
                lo=1e-4, hi=5.0, tol=1e-6, max_iter=100):
    """Back out annualised IV from a market price (bisection — robust, no vega).

    Returns None when the price is outside the no-arbitrage band (below intrinsic
    or above the forward), i.e. no vol reproduces it. Handy when IV is missing from
    the feed, or to sanity-check the feed's IV against the mid.
    """
    r = C.RISK_FREE_RATE if r is None else r
    q = C.DIVIDEND_YIELD if q is None else q
    if price is None or T <= 0:
        return None
    intrinsic = (max(S - K, 0.0) if right.upper() == "CALL" else max(K - S, 0.0))
    if price < intrinsic - 1e-8 or price <= 0:
        return None
    f_lo = bs_price(S, K, T, lo, right, r, q) - price
    f_hi = bs_price(S, K, T, hi, right, r, q) - price
    if f_lo * f_hi > 0:                     # price not bracketed by [lo, hi] vols
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = bs_price(S, K, T, mid, right, r, q) - price
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)
