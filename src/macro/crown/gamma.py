"""§2.3 Gamma — dealer hedging pressure, the short-term structural force.

Crown's mechanics, restated so the code can be checked against them:

  * Dealers are usually short options. Their net gamma forces hedging.
  * **Positive** gamma -> they sell rallies and buy dips -> moves are damped and
    price pins. **Negative** gamma -> they buy rallies and sell dips -> moves are
    amplified.
  * The **gamma flip** is the regime boundary — the price at which the sign
    changes.
  * The **call wall** and **put wall** are concrete magnets and acceleration
    zones.
  * 0DTE concentrates enormous gamma right at the money.

**This is a model, not a measurement — and the distinction is load-bearing.**
Exchange data gives open interest and greeks. It does NOT say who is long and who
is short. The standard convention, used here, is that customers buy calls and buy
puts, leaving dealers long call gamma and short put gamma. That assumption is
sometimes wrong, and when it is wrong the map points the wrong way. Every reading
this module emits carries `assumption` naming it, for the same reason `pattern`
ships as a visual flag rather than a signal.

The arithmetic. For one contract, the dealer's gamma exposure in dollars per 1%
move is

    GEX = OI * gamma * multiplier * spot^2 * 0.01

signed `+` for calls and `-` for puts under the convention above. Summing by
strike gives the profile; the strike where the cumulative sum crosses zero is
the flip.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import spec as S


def _clean(contracts, spot: float) -> pd.DataFrame:
    """Normalise a contract list, dropping anything that cannot carry gamma."""
    if not contracts:
        return pd.DataFrame()
    df = pd.DataFrame(list(contracts))
    for col in ("strike", "gamma", "open_interest"):
        if col not in df.columns:
            return pd.DataFrame()
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "right" not in df.columns:
        return pd.DataFrame()
    df["right"] = df["right"].astype(str).str.upper().str[0].map(
        {"C": "CALL", "P": "PUT"})
    if "dte" in df.columns:
        df["dte"] = pd.to_numeric(df["dte"], errors="coerce")
        df = df[df["dte"].between(S.GAMMA_DTE_MIN, S.GAMMA_DTE_MAX)]
    df = df.dropna(subset=["strike", "gamma", "open_interest", "right"])
    df = df[(df["open_interest"] > 0) & (df["gamma"] > 0) & (df["strike"] > 0)]
    if spot and spot > 0:
        lo, hi = spot * (1 - S.GAMMA_STRIKE_BAND), spot * (1 + S.GAMMA_STRIKE_BAND)
        df = df[df["strike"].between(lo, hi)]
    return df


def gamma_profile(contracts, spot: float) -> dict:
    """Dealer gamma by strike, plus flip / call wall / put wall.

    Returns `available: False` with a stated reason rather than a zeroed profile
    — a gamma map of all zeros reads as "neutral positioning", which is a
    completely different claim from "we could not get open interest".
    """
    if not spot or spot <= 0:
        return {"available": False, "reason": "no spot price"}

    df = _clean(contracts, spot)
    if df.empty:
        return {"available": False,
                "reason": ("no usable contracts — needs strike, right, gamma and "
                           "OPEN INTEREST per contract")}

    unit = S.GAMMA_CONTRACT_MULTIPLIER * (spot ** 2) * 0.01
    df["gex"] = df["open_interest"] * df["gamma"] * unit
    df.loc[df["right"] == "PUT", "gex"] *= -1.0

    by_strike = (df.groupby("strike", as_index=False)["gex"].sum()
                   .sort_values("strike").reset_index(drop=True))
    total = float(by_strike["gex"].sum())

    # The flip: cumulative gamma from the bottom of the strike ladder up. Where
    # it crosses zero, dealer hedging changes sign.
    by_strike["cumulative"] = by_strike["gex"].cumsum()
    flip = _zero_crossing(by_strike["strike"].to_numpy(),
                          by_strike["cumulative"].to_numpy())

    calls = df[df["right"] == "CALL"].groupby("strike")["gex"].sum()
    puts = df[df["right"] == "PUT"].groupby("strike")["gex"].sum().abs()
    call_wall = _wall(calls)
    put_wall = _wall(puts)

    return {
        "available": True,
        "spot": round(float(spot), 4),
        "total_gex": round(total, 2),
        "regime": "POSITIVE" if total > 0 else "NEGATIVE",
        "interpretation": ("Dealers sell rallies / buy dips — moves damped, price pins"
                           if total > 0 else
                           "Dealers buy rallies / sell dips — moves amplified"),
        "gamma_flip": flip,
        "flip_distance_pct": (round((flip / spot - 1.0) * 100.0, 2)
                              if flip is not None else None),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "strikes": int(len(by_strike)),
        "contracts": int(len(df)),
        "total_open_interest": int(df["open_interest"].sum()),
        "profile": [{"strike": float(r.strike), "gex": round(float(r.gex), 2),
                     "cumulative": round(float(r.cumulative), 2)}
                    for r in by_strike.itertuples()],
        "assumption": ("Customers are long calls and long puts, so dealers are long "
                       "call gamma and short put gamma. This is the standard "
                       "convention, NOT observed data — exchange feeds publish open "
                       "interest, never who is on which side."),
        "reason": None,
    }


def _zero_crossing(x: np.ndarray, y: np.ndarray) -> float | None:
    """First strike where cumulative gamma changes sign, linearly interpolated."""
    if len(x) < 2:
        return None
    sign = np.sign(y)
    idx = np.where(np.diff(sign) != 0)[0]
    if len(idx) == 0:
        return None
    i = int(idx[0])
    y0, y1 = float(y[i]), float(y[i + 1])
    if y1 == y0:
        return float(x[i])
    t = -y0 / (y1 - y0)
    return round(float(x[i]) + t * (float(x[i + 1]) - float(x[i])), 4)


def _wall(series: pd.Series) -> dict | None:
    """The strike carrying the most gamma on one side — if it actually dominates.

    Two tests, and the relative one is the one that matters. An evenly-spread
    ladder of 30 strikes gives every strike 3.3% of the side; a fixed floor alone
    would happily crown one of them and call it a wall. So the strike must carry
    `GAMMA_WALL_DOMINANCE` times its even share as well as clearing the floor.
    """
    if series is None or series.empty:
        return None
    total = float(series.sum())
    if total <= 0:
        return None
    strike = float(series.idxmax())
    share = float(series.max()) / total
    even_share = 1.0 / len(series)
    if share < S.GAMMA_WALL_MIN_SHARE or share < S.GAMMA_WALL_DOMINANCE * even_share:
        return None
    return {"strike": strike, "gex": round(float(series.max()), 2),
            "share_of_side": round(share, 4),
            "vs_even_share": round(share / even_share, 2)}


def analyse(chains: dict[str, dict]) -> dict:
    """Gamma across the index underlyings.

    `chains` is {underlying: {"spot": float, "contracts": [...]}}. Anything that
    cannot be profiled is listed in `unavailable` with its reason attached —
    never dropped, because a missing SPY map changes what the whole Crown read
    is worth.
    """
    out, bad = {}, {}
    for sym, payload in (chains or {}).items():
        prof = gamma_profile((payload or {}).get("contracts"),
                             (payload or {}).get("spot"))
        if prof.get("available"):
            out[sym] = prof
        else:
            bad[sym] = prof.get("reason")

    primary = out.get("SPY") or (next(iter(out.values())) if out else None)
    return {
        "status": "OK" if out else "UNAVAILABLE",
        "underlyings": out,
        "unavailable": bad,
        # The kernel needs one sign to route on. SPY is the market's gamma;
        # falling back to whatever else parsed is stated, not silent.
        "regime": primary["regime"] if primary else "UNKNOWN",
        "primary": ("SPY" if "SPY" in out else
                    (next(iter(out)) if out else None)),
        "reason": None if out else "; ".join(f"{k}: {v}" for k, v in bad.items()) or
                  "no chains supplied",
    }
