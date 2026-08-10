"""§2.5 Divergence — the three types Crown accepts, and nothing else.

The kernel rates plain RSI as C-tier, because price can sit overbought for weeks
and the level tells you nothing. What Crown uses RSI for is **divergence**, and
only three kinds count:

  1. **Classic RSI divergence** — price makes a new high (or low) while RSI does
     not. Momentum is failing behind the price.
  2. **Cross-asset / intermarket** — equities at new highs while copper or
     breadth refuses to confirm.
  3. **Positioning vs price** — price rising while COT large specs are already at
     an extreme, so the marginal buyer is already in.

**The rule that governs all three (§2.5, verbatim in spirit):** divergence is a
warning or confirmation filter, *never* a standalone entry trigger. It earns its
weight only when it lines up with the Heartbeat regime or an elevated dispersion
spread. So this module reports; it never routes on its own.

Pivots use `patterns.pivot_series` — the same confirmed-fractal definition every
other AQE layer uses. A divergence drawn on an unconfirmed high would fire on a
turn that has not held yet, which is the whole failure mode the confirmation rule
exists to prevent.

**Breadth of coverage.** The taxonomy stays at three types because §2.5 accepts
three — but each type now reads everything the layer holds rather than one
series:

  * Type 1 runs RSI divergence across a MATRIX of series (SPY, QQQ, RSP and every
    CTA market), not just the index.
  * Type 2 covers every non-confirmation we can source: the growth/rates/dollar
    complex, **breadth** (the RSP/SPY heartbeat refusing to follow the index),
    **VIX** (the market paying up for protection into strength), and the
    **dispersion spread**. All four are intermarket non-confirmations, which is
    what type 2 is; none of them is a new type smuggled in.
  * Type 3 sweeps all 16 COT contracts against their own price, not only ES.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines import utils as U
from src.engines.patterns import pivot_series
from . import spec as S


def _frame(bars) -> pd.DataFrame | None:
    if bars is None or len(bars) == 0:
        return None
    df = pd.DataFrame(bars).copy()
    for c in ("high", "low", "close"):
        if c not in df.columns:
            return None
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "date" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["high", "low", "close"]).sort_values("date").reset_index(drop=True)


# ── 1. classic RSI divergence ─────────────────────────────────────────────

def rsi_divergence(bars, *, period: int = S.DIV_RSI_PERIOD,
                   lookback: int = S.DIV_LOOKBACK) -> dict:
    """Compare the two most recent confirmed pivots of the same kind.

    Bearish: a higher price high on a lower RSI high. Bullish: a lower price low
    on a higher RSI low. Both pivots must be confirmed, and separated by at least
    `DIV_MIN_SEPARATION` bars so one drawn-out turn does not read as two.
    """
    df = _frame(bars)
    if df is None or len(df) < period + 2 * S.DIV_PIVOT_K + 10:
        return {"state": "NONE", "reason": "insufficient history"}

    rsi = U.rsi(df["close"], period)
    pivots = pivot_series(df["high"].to_numpy(), df["low"].to_numpy(),
                          df["date"].to_numpy(), k=S.DIV_PIVOT_K, window=lookback)
    if len(pivots) < 2:
        return {"state": "NONE", "reason": "fewer than two confirmed pivots"}

    offset = len(df) - min(len(df), lookback)

    def _pair(kind: str):
        """The latest pivot, against the most EXTREME prior pivot of that kind.

        Not simply the previous one. §2.5 says "price makes a new high" — that is
        a claim against the prior significant high, and comparing blindly to the
        last pivot lets a minor bump inside the second leg stand in for the real
        one, which quietly turns a genuine divergence into 'NONE'.
        """
        same = [p for p in pivots if p["kind"] == kind]
        if len(same) < 2:
            return None
        a = same[-1]                                          # latest
        prior = [p for p in same[:-1]
                 if a["idx"] - p["idx"] >= S.DIV_MIN_SEPARATION]
        if not prior:
            return None
        b = (max(prior, key=lambda p: p["price"]) if kind == "H"
             else min(prior, key=lambda p: p["price"]))
        return b, a

    for kind, direction in (("H", "bearish"), ("L", "bullish")):
        pair = _pair(kind)
        if pair is None:
            continue
        b, a = pair
        r_b, r_a = float(rsi.iloc[offset + b["idx"]]), float(rsi.iloc[offset + a["idx"]])
        if not (np.isfinite(r_b) and np.isfinite(r_a)):
            continue
        if kind == "H" and a["price"] > b["price"] and r_a < r_b:
            return _div("BEARISH_RSI_DIVERGENCE", direction, b, a, r_b, r_a,
                        "Price made a higher high; RSI did not")
        if kind == "L" and a["price"] < b["price"] and r_a > r_b:
            return _div("BULLISH_RSI_DIVERGENCE", direction, b, a, r_b, r_a,
                        "Price made a lower low; RSI did not")

    return {"state": "NONE", "rsi": round(float(rsi.iloc[-1]), 2)
            if np.isfinite(rsi.iloc[-1]) else None,
            "reason": "no divergence between the last two confirmed pivots"}


def _div(state, direction, b, a, r_b, r_a, why) -> dict:
    return {
        "state": state,
        "direction": direction,
        "prior": {"date": b["date"], "price": round(b["price"], 4), "rsi": round(r_b, 2)},
        "latest": {"date": a["date"], "price": round(a["price"], 4), "rsi": round(r_a, 2)},
        "bars_ago": a["bars_ago"],
        "rsi_gap": round(r_a - r_b, 2),
        "why": why,
        "reason": None,
    }


# ── 2. cross-asset / intermarket ──────────────────────────────────────────

def cross_asset_divergence(equity_bars, confirmers: dict,
                           window: int = S.DIV_NEW_HIGH_WINDOW,
                           inverted: tuple = S.DIV_INVERTED_CONFIRMERS) -> dict:
    """Equities at a new high while the growth/rates/dollar complex is not.

    `confirmers` is {name: bars} — copper and oil for growth, RSP for breadth.
    A confirmer that simply is not at a new high is the point; that is the
    non-confirmation. The reading only fires when the EQUITY leg is at a new
    high, because "nothing is at a new high" is not a divergence.

    `inverted` names the series whose SIGN is flipped — a bid dollar is a drag on
    risk, so DX at a new high is the warning, not the confirmation. Treating it
    like copper would read a dollar squeeze as a healthy tape.
    """
    eq = _frame(equity_bars)
    if eq is None or len(eq) < window + 1:
        return {"state": "NONE", "reason": "insufficient equity history"}

    eq_high, _ = _at_new_high(eq, window)
    if not eq_high:
        return {"state": "NONE", "equity_at_new_high": False,
                "reason": f"equities not at a {window}-day high — nothing to diverge from"}

    confirming, failing, missing = [], [], []
    for name, bars in (confirmers or {}).items():
        df = _frame(bars)
        if df is None or len(df) < window + 1:
            missing.append(name)
            continue
        hi, last = _at_new_high(df, window)
        tail = df["close"].tail(window)
        pct_of_high = float(last / float(tail.max())) if float(tail.max()) else None
        flip = name in (inverted or ())
        agrees = (not hi) if flip else hi
        entry = {"name": name, "inverted": flip,
                 "pct_of_window_high": round(pct_of_high, 4) if pct_of_high else None}
        (confirming if agrees else failing).append(entry)

    state = "CROSS_ASSET_DIVERGENCE" if failing else "CONFIRMED"
    return {
        "state": state,
        "equity_at_new_high": True,
        "confirming": confirming,
        "failing": failing,
        "unavailable": missing,
        "why": (f"Equities at a {window}-day high; "
                f"{', '.join(f['name'] for f in failing)} not confirming"
                if failing else
                f"All confirmers at {window}-day highs alongside equities"),
        "reason": None,
    }


def rsi_matrix(series: dict) -> dict:
    """Type 1 across every series we hold, not just the index.

    A divergence on SPY alone is one observation. The same divergence showing on
    SPY, QQQ *and* copper is a different statement, and we already hold the bars
    to tell them apart.
    """
    out, bearish, bullish = {}, [], []
    for name, bars in (series or {}).items():
        r = rsi_divergence(bars)
        out[name] = r
        if r.get("state") == "BEARISH_RSI_DIVERGENCE":
            bearish.append(name)
        elif r.get("state") == "BULLISH_RSI_DIVERGENCE":
            bullish.append(name)
    return {"by_series": out, "bearish": sorted(bearish), "bullish": sorted(bullish),
            "scanned": len(out)}


# ── 2b. the other intermarket non-confirmations ───────────────────────────

def _is_rising(bars, window: int, eps: float = 0.0) -> tuple[bool | None, float | None]:
    """(rising?, change) over `window` sessions, from a (date, close) frame."""
    if bars is None or len(bars) == 0:
        return None, None
    v = pd.to_numeric(pd.DataFrame(bars)["close"], errors="coerce").dropna()
    if len(v) <= window:
        return None, None
    change = float(v.iloc[-1] - v.iloc[-(window + 1)])
    return bool(change > eps), round(change, 4)


def _at_new_high(bars, window: int) -> tuple[bool, float | None]:
    df = _frame(bars)
    if df is None or len(df) < window + 1:
        return False, None
    tail = df["close"].tail(window)
    last = float(tail.iloc[-1])
    return bool(last >= float(tail.max()) - 1e-9), last


def vix_nonconfirmation(equity_bars, vix_bars,
                        window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Equities at a new high while VIX is RISING.

    Normally they move opposite: a market grinding to new highs bleeds implied
    vol. When the index makes a high and protection gets MORE expensive at the
    same time, someone is paying up into strength. That is a non-confirmation in
    exactly the §2.5 sense — an intermarket series refusing to agree with price.
    """
    hi, _ = _at_new_high(equity_bars, window)
    rising, change = _is_rising(vix_bars, S.DIV_VIX_WINDOW, S.DIV_VIX_EPS)
    if rising is None:
        return {"state": "NONE", "reason": "no VIX series"}
    if not hi:
        return {"state": "NONE", "equity_at_new_high": False, "vix_rising": rising,
                "vix_change": change,
                "reason": f"equities not at a {window}-day high"}
    if not rising:
        return {"state": "CONFIRMED", "equity_at_new_high": True,
                "vix_rising": False, "vix_change": change,
                "why": "Index at a new high and VIX easing — they agree"}
    return {"state": "VIX_NONCONFIRMATION", "equity_at_new_high": True,
            "vix_rising": True, "vix_change": change,
            "why": (f"Index at a {window}-day high while VIX ROSE {change:+.2f} over "
                    f"{S.DIV_VIX_WINDOW} sessions — protection getting more "
                    "expensive into strength"),
            "reason": None}


def breadth_nonconfirmation(equity_bars, heartbeat: dict | None,
                            window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Equities at a new high while the RSP/SPY heartbeat is NARROWING.

    The purest form of the §2.5 idea and the one the layer already had the data
    for: the index makes a high because a handful of names carry it, while the
    average stock is going the other way. Reuses the Heartbeat rather than
    recomputing breadth, so the two can never disagree about the same ratio.
    """
    if not heartbeat or heartbeat.get("regime") is None:
        return {"state": "NONE", "reason": "no heartbeat read"}
    hi, _ = _at_new_high(equity_bars, window)
    regime = heartbeat.get("regime")
    if not hi:
        return {"state": "NONE", "equity_at_new_high": False, "regime": regime,
                "reason": f"equities not at a {window}-day high"}
    if regime != "narrowing":
        return {"state": "CONFIRMED", "equity_at_new_high": True, "regime": regime,
                "why": f"Index at a new high with breadth {regime} — they agree"}
    return {"state": "BREADTH_NONCONFIRMATION", "equity_at_new_high": True,
            "regime": regime, "heartbeat_slope": heartbeat.get("slope_20d"),
            "why": (f"Index at a {window}-day high while RSP/SPY is NARROWING — "
                    "the average stock is not coming along"),
            "reason": None}


def dispersion_nonconfirmation(equity_bars, dispersion: dict | None,
                               window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Equities at a new high while the single-stock vol spread is widening."""
    if not dispersion or dispersion.get("spread") is None:
        return {"state": "NONE", "reason": "no dispersion reading"}
    hi, _ = _at_new_high(equity_bars, window)
    direction = dispersion.get("direction")
    if not hi:
        return {"state": "NONE", "equity_at_new_high": False, "direction": direction,
                "reason": f"equities not at a {window}-day high"}
    if direction != "RISING":
        return {"state": "CONFIRMED", "equity_at_new_high": True,
                "direction": direction,
                "why": f"Index at a new high with dispersion {str(direction).lower()}"}
    return {"state": "DISPERSION_NONCONFIRMATION", "equity_at_new_high": True,
            "direction": "RISING", "spread": dispersion.get("spread"),
            "band": dispersion.get("band"),
            "why": ("Index at a new high while single-stock vol pulls away from "
                    "index vol — the tape is calm only at the index level"),
            "reason": None}


# ── 3. positioning vs price ───────────────────────────────────────────────

def positioning_divergence(equity_bars, cot_reading: dict | None,
                           window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Price rising into positioning that is already at an extreme.

    Crown's version of "who is left to buy". Needs a COT reading whose percentile
    is backed by enough weeks to mean anything — an extreme computed off twelve
    observations is not an extreme.
    """
    if not cot_reading:
        return {"state": "NONE", "reason": "no COT reading available"}
    if not cot_reading.get("percentile_reliable"):
        return {"state": "NONE",
                "reason": (f"only {cot_reading.get('weeks_of_history')} weeks of COT "
                           "history — percentile not yet meaningful")}

    eq = _frame(equity_bars)
    if eq is None or len(eq) < window + 1:
        return {"state": "NONE", "reason": "insufficient equity history"}

    tail = eq["close"].tail(window)
    rising = float(tail.iloc[-1]) > float(tail.iloc[0])
    pctl = cot_reading.get("percentile")
    extreme = cot_reading.get("extreme")

    if rising and extreme == "CROWDED_LONG":
        state, why = ("POSITIONING_DIVERGENCE",
                      "Price rising into a large-spec long already at an extreme")
    elif (not rising) and extreme == "CROWDED_SHORT":
        state, why = ("POSITIONING_DIVERGENCE",
                      "Price falling into a large-spec short already at an extreme")
    else:
        state, why = "NONE", "Price direction and positioning are not at odds"

    return {
        "state": state,
        "price_rising": bool(rising),
        "cot_percentile": pctl,
        "cot_extreme": extreme,
        "cot_as_of": cot_reading.get("as_of"),
        "weeks_stale": None,
        "why": why,
        "reason": None,
    }


def positioning_matrix(market_bars: dict | None, cot_markets: dict | None,
                       window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Type 3 across every contract that has both bars and a COT reading.

    ES alone answers one question. Sweeping all 16 tells you *where* the crowd is
    offside — a crowded long in copper diverging from a falling copper price is a
    different trade from the same thing in gold.
    """
    out, fired = {}, []
    for key, bars in (market_bars or {}).items():
        reading = (cot_markets or {}).get(key)
        if not reading:
            continue
        r = positioning_divergence(bars, reading, window)
        out[key] = r
        if r.get("state") == "POSITIONING_DIVERGENCE":
            fired.append(key)
    return {"by_market": out, "diverging": sorted(fired), "scanned": len(out)}


# ── the §2.5 composite ────────────────────────────────────────────────────

def analyse(equity_bars, *, confirmers: dict | None = None,
            cot_reading: dict | None = None,
            rsi_series: dict | None = None,
            vix_bars=None,
            heartbeat: dict | None = None,
            dispersion: dict | None = None,
            market_bars: dict | None = None,
            cot_markets: dict | None = None) -> dict:
    """All three types, read across everything the layer holds.

    `any_bearish` deliberately does NOT mean "sell". §2.5 is explicit that
    divergence is a filter, and the kernel only lets it act when the Heartbeat or
    the dispersion spread agrees.
    """
    # Type 1 — classic RSI, on the index and across the matrix.
    rsi_d = rsi_divergence(equity_bars)
    matrix = rsi_matrix(rsi_series or {})

    # Type 2 — every intermarket non-confirmation we can source.
    cross = cross_asset_divergence(equity_bars, confirmers or {})
    vix_nc = vix_nonconfirmation(equity_bars, vix_bars)
    breadth_nc = breadth_nonconfirmation(equity_bars, heartbeat)
    disp_nc = dispersion_nonconfirmation(equity_bars, dispersion)

    # Type 3 — positioning, on ES and across the contract sweep.
    pos = positioning_divergence(equity_bars, cot_reading)
    pos_matrix = positioning_matrix(market_bars, cot_markets)

    checks = {
        "rsi": rsi_d,
        "cross_asset": cross,
        "vix": vix_nc,
        "breadth": breadth_nc,
        "dispersion": disp_nc,
        "positioning": pos,
    }
    fired = [n for n, d in checks.items()
             if d.get("state") not in (None, "NONE", "CONFIRMED")]

    bearish = bool(
        rsi_d.get("state") == "BEARISH_RSI_DIVERGENCE"
        or matrix["bearish"]
        or cross.get("state") == "CROSS_ASSET_DIVERGENCE"
        or vix_nc.get("state") == "VIX_NONCONFIRMATION"
        or breadth_nc.get("state") == "BREADTH_NONCONFIRMATION"
        or disp_nc.get("state") == "DISPERSION_NONCONFIRMATION"
        or (pos.get("state") == "POSITIONING_DIVERGENCE" and pos.get("price_rising"))
    )
    bullish = bool(rsi_d.get("state") == "BULLISH_RSI_DIVERGENCE" or matrix["bullish"])

    # How many INDEPENDENT warnings are lit. §2.5 says divergence is most
    # powerful when it aligns with something else; the count is how a reader
    # tells one straw from a pile of them.
    weight = len(fired) + len(matrix["bearish"]) + len(pos_matrix["diverging"])

    return {
        # the three accepted types
        "rsi": rsi_d,
        "cross_asset": cross,
        "positioning": pos,
        # the widened reads
        "rsi_matrix": matrix,
        "vix": vix_nc,
        "breadth": breadth_nc,
        "dispersion": disp_nc,
        "positioning_matrix": pos_matrix,
        # the summary the kernel routes on
        "any_bearish": bearish,
        "any_bullish": bullish,
        "types_fired": fired,
        "count": len(fired),
        "weight": weight,
        "coverage": {
            "rsi_series": matrix["scanned"],
            "confirmers": len(confirmers or {}),
            "cot_contracts": pos_matrix["scanned"],
            "vix": vix_bars is not None,
            "breadth": bool(heartbeat),
            "dispersion": bool(dispersion),
        },
        "note": ("A warning or confirmation filter, never a standalone entry "
                 "trigger (§2.5). Weight it only where the Heartbeat regime or "
                 "an elevated dispersion spread agrees."),
    }
