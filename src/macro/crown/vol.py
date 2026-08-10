"""§2.4 VIX structure — what Crown actually uses it for, which is not fear.

The kernel is explicit that VIX is *not* a fear gauge or an automatic sell
signal. It is the options market's price of 30-day SPX realised volatility. A
spike says protection got expensive; a high level often means it is ALREADY
expensive, which is the opposite of a fresh entry.

The tool Crown actually trades is **VIXEQ - VIX**: single-stock vol minus
cap-weighted index vol. When that spread rises, the index can look calm while the
average stock is coming apart underneath — and §2.4 records that an elevated
spread has preceded 5-7% drawdowns.

**A plan limit that has to be stated, not buried.** `^VIX` is available on our FMP
Starter plan. `^VIXEQ`, `^VIX3M` and `^VIX9D` are NOT (probed 2026-08-09). So the
implied spread is attempted every run, and when it is unavailable we fall back to
a **realised** dispersion measure computed from bars we already hold:

    mean(30d realised vol of every universe name) - 30d realised vol of SPY

That measures the same phenomenon — single-stock vol rising while the index stays
calm — but it is realised, not implied. It lags, and it carries none of the
forward-looking risk premium that makes the implied version tradeable. The two
are named differently everywhere (`spread_implied` vs `spread_realised`) and the
`basis` field always says which one produced the reading, because a realised
number quietly standing in for an implied one is exactly how a weaker claim gets
mistaken for a stronger one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import spec as S


# ── primitives ────────────────────────────────────────────────────────────

def realised_vol(closes, window: int = S.DISP_REALISED_WINDOW) -> float | None:
    c = pd.to_numeric(pd.Series(closes), errors="coerce").dropna().to_numpy(dtype=float)
    if len(c) < window + 1:
        return None
    r = np.diff(np.log(c[-(window + 1):]))
    sd = float(np.std(r, ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return None
    return sd * np.sqrt(S.TRADING_DAYS) * 100.0        # vol POINTS, like VIX


def percentile_of_last(series, window: int = S.DISPERSION_WINDOW) -> float | None:
    s = pd.to_numeric(pd.Series(series), errors="coerce").dropna().tail(window)
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])
    return float((s <= last).sum() - 1) / max(len(s) - 1, 1)


def _band(pctl: float | None) -> str:
    if pctl is None:
        return "UNKNOWN"
    if pctl >= S.DISPERSION_ELEVATED_PCTL:
        return "ELEVATED"
    if pctl <= S.DISPERSION_CALM_PCTL:
        return "CALM"
    return "NORMAL"


def _direction(change: float | None) -> str:
    """RISING / FALLING / FLAT over the rise window."""
    if change is None:
        return "UNKNOWN"
    if change > S.DISPERSION_RISE_EPS:
        return "RISING"
    if change < -S.DISPERSION_RISE_EPS:
        return "FALLING"
    return "FLAT"


def _state(band: str, direction: str) -> str:
    """Level and direction as one label, because they routinely disagree.

    On 2026-08-07 the spread was at the 98th percentile of its entire history
    AND had fallen 9.2 points in twenty sessions. "ELEVATED" alone would have
    read as a live warning; "ELEVATED_EASING" says what is actually happening.
    """
    if band == "ELEVATED":
        return "ELEVATED_RISING" if direction == "RISING" else "ELEVATED_EASING"
    if band == "UNKNOWN":
        return "UNKNOWN"
    return f"{band}_{direction}" if direction == "RISING" else band


# ── the dispersion spread, both bases ─────────────────────────────────────

def implied_spread(vix: pd.DataFrame | None,
                   vixeq: pd.DataFrame | None) -> dict | None:
    """VIXEQ - VIX from the two index series. None if VIXEQ is unavailable."""
    if vix is None or vixeq is None or len(vix) == 0 or len(vixeq) == 0:
        return None
    a = pd.DataFrame({"date": pd.to_datetime(vix["date"]),
                      "vix": pd.to_numeric(vix["close"], errors="coerce")})
    b = pd.DataFrame({"date": pd.to_datetime(vixeq["date"]),
                      "vixeq": pd.to_numeric(vixeq["close"], errors="coerce")})
    m = a.merge(b, on="date", how="inner").dropna().sort_values("date")
    if m.empty:
        return None
    m["spread"] = m["vixeq"] - m["vix"]
    pctl = percentile_of_last(m["spread"])
    pctl_full = percentile_of_last(m["spread"], len(m))
    w = S.DISPERSION_RISE_WINDOW
    change = (round(float(m["spread"].iloc[-1] - m["spread"].iloc[-(w + 1)]), 2)
              if len(m) > w else None)
    band, direction = _band(pctl), _direction(change)
    return {
        "basis": "implied",
        "as_of": m["date"].iloc[-1].date().isoformat(),
        "vix": round(float(m["vix"].iloc[-1]), 2),
        "single_stock_vol": round(float(m["vixeq"].iloc[-1]), 2),
        "spread": round(float(m["spread"].iloc[-1]), 2),
        "spread_20d_change": change,
        "percentile": round(pctl, 4) if pctl is not None else None,
        "percentile_full_history": round(pctl_full, 4) if pctl_full is not None else None,
        "band": band,
        "direction": direction,
        "state": _state(band, direction),
        "observations": int(len(m)),
        "caveat": None,
    }


def realised_spread(panel: pd.DataFrame | None, spy: pd.DataFrame | None,
                    window: int = S.DISP_REALISED_WINDOW,
                    history: int = S.DISPERSION_WINDOW) -> dict | None:
    """The fallback: cross-sectional mean realised vol minus SPY realised vol.

    `panel` is the long-format daily panel (ticker, date, close). The spread is
    computed for every date in the trailing history so the percentile has
    something to rank against — a single day's number is meaningless here, since
    the level of the spread depends on the vol regime.
    """
    if panel is None or len(panel) == 0 or spy is None or len(spy) == 0:
        return None

    p = panel[["ticker", "date", "close"]].copy()
    p["date"] = pd.to_datetime(p["date"])
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    wide = p.pivot_table(index="date", columns="ticker", values="close",
                         aggfunc="last").sort_index()
    need = history + window + 5
    wide = wide.tail(need)
    if len(wide) < window + 2:
        return None

    lr = np.log(wide).diff()
    vol = lr.rolling(window).std(ddof=1) * np.sqrt(S.TRADING_DAYS) * 100.0
    counts = vol.notna().sum(axis=1)
    mean_single = vol.mean(axis=1, skipna=True)

    s = pd.DataFrame({"date": pd.to_datetime(spy["date"]),
                      "close": pd.to_numeric(spy["close"], errors="coerce")}
                     ).dropna().sort_values("date").set_index("date")
    slr = np.log(s["close"]).diff()
    spy_vol = slr.rolling(window).std(ddof=1) * np.sqrt(S.TRADING_DAYS) * 100.0

    m = pd.DataFrame({"single": mean_single, "n": counts}).join(
        spy_vol.rename("spy"), how="inner").dropna()
    m = m[m["n"] >= S.DISP_MIN_CONSTITUENTS]
    if m.empty:
        return None
    m["spread"] = m["single"] - m["spy"]

    pctl = percentile_of_last(m["spread"], history)
    w = S.DISPERSION_RISE_WINDOW
    change = (round(float(m["spread"].iloc[-1] - m["spread"].iloc[-(w + 1)]), 2)
              if len(m) > w else None)
    band, direction = _band(pctl), _direction(change)
    return {
        "basis": "realised",
        "as_of": m.index[-1].date().isoformat(),
        "vix": None,
        "single_stock_vol": round(float(m["single"].iloc[-1]), 2),
        "index_vol": round(float(m["spy"].iloc[-1]), 2),
        "spread": round(float(m["spread"].iloc[-1]), 2),
        "spread_20d_change": change,
        "percentile": round(pctl, 4) if pctl is not None else None,
        "percentile_full_history": None,
        "band": band,
        "direction": direction,
        "state": _state(band, direction),
        "constituents": int(m["n"].iloc[-1]),
        "observations": int(len(m)),
        "caveat": ("REALISED, not implied — the last resort, used only when the "
                   "Cboe VIXEQ series could not be fetched. It lags and carries "
                   "no volatility risk premium, so it is not the number §2.4 "
                   "describes, only the same question asked of bars we hold."),
    }


# ── term structure ────────────────────────────────────────────────────────

def term_structure(vix: pd.DataFrame | None, vix3m: pd.DataFrame | None,
                   vix9d: pd.DataFrame | None) -> dict:
    """VIX9D / VIX / VIX3M. Backwardation is the stress tell; contango is normal."""
    out = {"vix9d": None, "vix": None, "vix3m": None,
           "ratio_9d_30d": None, "ratio_30d_3m": None,
           "shape": "UNKNOWN", "available": False}

    def last(df):
        if df is None or len(df) == 0:
            return None
        v = pd.to_numeric(pd.DataFrame(df)["close"], errors="coerce").dropna()
        return float(v.iloc[-1]) if len(v) else None

    out["vix"], out["vix3m"], out["vix9d"] = last(vix), last(vix3m), last(vix9d)
    if out["vix"] and out["vix3m"]:
        out["ratio_30d_3m"] = round(out["vix"] / out["vix3m"], 4)
        out["shape"] = "BACKWARDATION" if out["ratio_30d_3m"] > 1.0 else "CONTANGO"
        out["available"] = True
    if out["vix"] and out["vix9d"]:
        out["ratio_9d_30d"] = round(out["vix9d"] / out["vix"], 4)
    return out


# ── corroboration: Cboe's own dispersion + implied correlation ───────────

def corroboration(dspx: pd.DataFrame | None,
                  cor1m: pd.DataFrame | None) -> dict:
    """DSPX and implied correlation, as a cross-check on the hand-built spread.

    Two independent readings of one question. DSPX is Cboe's purpose-built
    dispersion index — same question, constructed by the people who define the
    inputs. Implied correlation is the mechanical other side: index variance is
    constituent variance times correlation, so a collapsing correlation IS a
    widening spread, and it must move OPPOSITE. If it ever stops doing so, the
    spread is wrong, not the market.
    """
    out = {"dspx": None, "dspx_percentile": None, "dspx_band": None,
           "implied_correlation": None, "correlation_percentile": None,
           "agrees": None, "note": None}

    def _last_and_pctl(df):
        if df is None or len(df) == 0:
            return None, None
        v = pd.to_numeric(pd.DataFrame(df)["close"], errors="coerce").dropna()
        if v.empty:
            return None, None
        return float(v.iloc[-1]), percentile_of_last(v, S.DISPERSION_WINDOW)

    d_last, d_pctl = _last_and_pctl(dspx)
    c_last, c_pctl = _last_and_pctl(cor1m)
    out["dspx"] = round(d_last, 2) if d_last is not None else None
    out["dspx_percentile"] = round(d_pctl, 4) if d_pctl is not None else None
    out["dspx_band"] = _band(d_pctl)
    out["implied_correlation"] = round(c_last, 2) if c_last is not None else None
    out["correlation_percentile"] = round(c_pctl, 4) if c_pctl is not None else None

    if d_pctl is not None and c_pctl is not None:
        # High dispersion should pair with LOW correlation.
        out["agrees"] = bool((d_pctl >= 0.5) == (c_pctl <= 0.5))
        out["note"] = ("Dispersion and correlation agree (they move opposite by "
                       "construction)" if out["agrees"] else
                       "Dispersion and implied correlation DISAGREE — treat the "
                       "spread with suspicion")
    return out


# ── the §2.4 reading ──────────────────────────────────────────────────────

def analyse(vix: pd.DataFrame | None = None,
            vixeq: pd.DataFrame | None = None,
            vix3m: pd.DataFrame | None = None,
            vix9d: pd.DataFrame | None = None,
            panel: pd.DataFrame | None = None,
            spy: pd.DataFrame | None = None,
            dspx: pd.DataFrame | None = None,
            cor1m: pd.DataFrame | None = None) -> dict:
    """The volatility regime, and the three Crown rules that read off it."""
    disp = implied_spread(vix, vixeq)
    if disp is None:
        disp = realised_spread(panel, spy)

    vix_last = None
    vix_pctl = None
    if vix is not None and len(vix):
        v = pd.to_numeric(pd.DataFrame(vix)["close"], errors="coerce").dropna()
        if len(v):
            vix_last = float(v.iloc[-1])
            vix_pctl = percentile_of_last(v)

    if disp is None:
        status = "UNAVAILABLE"
    elif disp["basis"] == "implied":
        status = "OK"
    else:
        status = "DEGRADED_REALISED_PROXY"

    band = disp["band"] if disp else "UNKNOWN"
    direction = (disp or {}).get("direction", "UNKNOWN")

    # §2.4's three practical rules, stated as flags rather than prose so the
    # kernel can act on them without re-parsing a sentence.
    rules = {
        # "RISING VIXEQ-VIX spread -> hidden stress -> favour defined-risk
        #  downside or reduce risk." Level alone is not the rule: an elevated
        #  spread that is unwinding is stress LEAVING the market, and buying
        #  downside into it is buying the end of the move.
        "hidden_stress": bool(band == "ELEVATED" and direction == "RISING"),
        # The narrative claim ("an elevated spread has predicted 5-7% drawdowns")
        # kept separate, so an elevated-but-easing tape is never invisible.
        "dispersion_elevated": bool(band == "ELEVATED"),
        # "Very low VIX + positive gamma -> premium-selling / mean-reversion."
        # Gamma is not this module's business, so only the VIX half is decided
        # here and the kernel ANDs it with the gamma sign.
        "very_low_vix": bool(vix_last is not None and vix_last < S.VIX_VERY_LOW),
        # "A VIX spike that is already priced is not a fresh sell signal."
        "already_priced": bool(vix_last is not None and vix_last >= S.VIX_ELEVATED),
    }

    return {
        "status": status,
        "vix": round(vix_last, 2) if vix_last is not None else None,
        "vix_percentile": round(vix_pctl, 4) if vix_pctl is not None else None,
        "dispersion": disp,
        "corroboration": corroboration(dspx, cor1m),
        "term_structure": term_structure(vix, vix3m, vix9d),
        "rules": rules,
        "reason": None if disp else "no VIX series and no panel to fall back on",
    }
