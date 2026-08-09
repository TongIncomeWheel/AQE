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
                           window: int = S.DIV_NEW_HIGH_WINDOW) -> dict:
    """Equities at a new high while the growth/breadth confirmers are not.

    `confirmers` is {name: bars} — copper for global growth, RSP for breadth.
    A confirmer that simply is not at a new high is the point; that is the
    non-confirmation. The reading only fires when the EQUITY leg is at a new
    high, because "nothing is at a new high" is not a divergence.
    """
    eq = _frame(equity_bars)
    if eq is None or len(eq) < window + 1:
        return {"state": "NONE", "reason": "insufficient equity history"}

    def _at_new_high(df) -> tuple[bool, float]:
        tail = df["close"].tail(window)
        last = float(tail.iloc[-1])
        return bool(last >= float(tail.max()) - 1e-9), last

    eq_high, _ = _at_new_high(eq)
    if not eq_high:
        return {"state": "NONE", "equity_at_new_high": False,
                "reason": f"equities not at a {window}-day high — nothing to diverge from"}

    confirming, failing, missing = [], [], []
    for name, bars in (confirmers or {}).items():
        df = _frame(bars)
        if df is None or len(df) < window + 1:
            missing.append(name)
            continue
        hi, last = _at_new_high(df)
        tail = df["close"].tail(window)
        pct_of_high = float(last / float(tail.max())) if float(tail.max()) else None
        (confirming if hi else failing).append(
            {"name": name, "pct_of_window_high": round(pct_of_high, 4)
             if pct_of_high else None})

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


# ── the §2.5 composite ────────────────────────────────────────────────────

def analyse(equity_bars, *, confirmers: dict | None = None,
            cot_reading: dict | None = None) -> dict:
    """All three types, plus the single flag the kernel routes on.

    `any_bearish` deliberately does NOT mean "sell". §2.5 is explicit that
    divergence is a filter, and the kernel only lets it act when the Heartbeat or
    the dispersion spread agrees.
    """
    rsi_d = rsi_divergence(equity_bars)
    cross = cross_asset_divergence(equity_bars, confirmers or {})
    pos = positioning_divergence(equity_bars, cot_reading)

    bearish = (rsi_d.get("state") == "BEARISH_RSI_DIVERGENCE"
               or cross.get("state") == "CROSS_ASSET_DIVERGENCE"
               or (pos.get("state") == "POSITIONING_DIVERGENCE"
                   and pos.get("price_rising")))
    bullish = rsi_d.get("state") == "BULLISH_RSI_DIVERGENCE"

    fired = [n for n, d in (("rsi", rsi_d), ("cross_asset", cross),
                            ("positioning", pos))
             if d.get("state") not in (None, "NONE", "CONFIRMED")]

    return {
        "rsi": rsi_d,
        "cross_asset": cross,
        "positioning": pos,
        "any_bearish": bool(bearish),
        "any_bullish": bool(bullish),
        "types_fired": fired,
        "count": len(fired),
        "note": ("A warning or confirmation filter, never a standalone entry "
                 "trigger (§2.5). Weight it only where the Heartbeat regime or "
                 "an elevated dispersion spread agrees."),
    }
