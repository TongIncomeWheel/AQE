"""Continuation pivot + extension bracket (PM question 2026-11-04: "the pivot lags for a name trending to new highs").

DATA ONLY. Neither output is a gate, a size, or a recommendation, and neither REPLACES anything: `pivot_high` /
`pct_from_pivot` and `bracket` stay exactly as they were. These are second readings placed beside them, labelled.

Continuation pivot (the rule, frozen here; changing it is a PM sign-off):
  the MOST RECENT tight window of 3-10 consecutive daily bars, ending within the last 5 bars (so a base that formed
  and was then left behind by a run does not count as "current"), whose total range (highest high - lowest low) is at
  most 2.5 x ATR14, AND that contains a contraction bar: an inside bar (high <= prior high and low >= prior low) or an
  NR7 (the narrowest range of the last 7 bars). The longest qualifying window at the latest end wins.
  pivot = the window's highest high; low = the window's lowest low.

State against the continuation pivot (entry / pivot - 1) x 100:
  BELOW      < 0   coiling under the pivot: the break has not happened, so this is not yet a buy-the-break ticket
  BUY_ZONE   0-5   the same 0-5% zone the structural pivot uses
  EXTENDED   > 5   still extended even against the continuation pivot

Extension bracket (a SECOND bracket beside the structural one, for names whose structural targets are near or absent):
  TP1 / TP2 = 1.272 / 1.618 extension of the last impulse (fib_swing_low -> fib_swing_high);
  stop      = the lower of the continuation window's low and (entry - 1 x ATR14), i.e. a >= 1 daily-range floor;
  the SAME three gates as the structural bracket: stop >= ATR_FLOOR ranges, R:R to TP2 >= RR_MIN, risk% <= regime
  ceiling. `passed` says whether it clears them. A far target makes R:R easy to clear BY CONSTRUCTION, and it ignores
  real nearby resistance: read it as "what the bracket looks like if the nearby levels are ignored", never as better.
"""
from __future__ import annotations

from src.engines.bracket_engine import ATR_FLOOR, RR_MIN, regime_stop_ceiling

MAX_WINDOW = 10
MIN_WINDOW = 3
MAX_BARS_BACK = 5            # the window must end within the last 5 bars
MAX_RANGE_ATR = 2.5
BUY_ZONE_MAX_PCT = 5.0
LABEL = "extension bracket (beside the structural bracket; not a gate)"


def _num(x) -> bool:
    return isinstance(x, (int, float)) and x == x


def continuation_pivot(highs, lows, atr14):
    """highs/lows: sequences of daily bars, oldest first. Returns dict or None."""
    if not _num(atr14) or atr14 <= 0:
        return None
    n = len(highs)
    if n < MAX_WINDOW + 8 or n != len(lows):
        return None
    rng = [float(h) - float(l) for h, l in zip(highs, lows)]
    for back in range(MAX_BARS_BACK):
        end = n - 1 - back
        for length in range(MAX_WINDOW, MIN_WINDOW - 1, -1):
            s = end - length + 1
            if s < 7:
                continue
            hh = max(float(x) for x in highs[s:end + 1])
            ll = min(float(x) for x in lows[s:end + 1])
            if hh - ll > MAX_RANGE_ATR * atr14:
                continue
            inside = any(float(highs[i]) <= float(highs[i - 1]) and float(lows[i]) >= float(lows[i - 1])
                         for i in range(s + 1, end + 1))
            nr7 = any(rng[i] == min(rng[i - 6:i + 1]) for i in range(max(s, 6), end + 1))
            if inside or nr7:
                return {"pivot": round(hh, 2), "low": round(ll, 2), "bars": length, "ended_bars_ago": back}
    return None


def state_vs_pivot(pct):
    if not _num(pct):
        return None
    if pct < 0:
        return "BELOW"
    return "BUY_ZONE" if pct <= BUY_ZONE_MAX_PCT else "EXTENDED"


def extension_bracket(entry, atr14, swing_low, swing_high, cont, regime_level):
    """Returns the labelled second bracket, or {"label", "available": False, "reason"} - never silently absent."""
    base = {"label": LABEL, "available": False, "reason": None}
    if not (_num(entry) and _num(atr14) and atr14 > 0 and entry > 0):
        base["reason"] = "missing price/ATR"
        return base
    if not cont:
        base["reason"] = "no continuation window"
        return base
    if not (_num(swing_low) and _num(swing_high) and swing_high > swing_low):
        base["reason"] = "no impulse (fib swing low/high missing)"
        return base
    stop = min(cont["low"], entry - ATR_FLOOR * atr14)
    risk = entry - stop
    if risk <= 0:
        base["reason"] = "stop not below price"
        return base
    imp = swing_high - swing_low
    t1, t2 = swing_low + 1.272 * imp, swing_low + 1.618 * imp
    if t1 <= entry or t2 <= entry:
        base["reason"] = "impulse extensions are not above price"
        return base
    ceiling = regime_stop_ceiling(regime_level)
    atr_dist, risk_pct = risk / atr14, risk / entry * 100.0
    rr1, rr2 = (t1 - entry) / risk, (t2 - entry) / risk
    gates = {"atr_floor": bool(atr_dist >= ATR_FLOOR), "rr_min": bool(rr2 >= RR_MIN),
             "regime_ceiling": bool(risk_pct <= ceiling)}
    return {
        "label": LABEL, "available": True, "reason": None,
        "stop": round(stop, 2), "stop_basis": "lower of the continuation-window low and 1 daily range under entry",
        "stop_atr_dist": round(atr_dist, 2), "risk": round(risk, 2), "risk_pct": round(risk_pct, 2),
        "targets": [{"tp": "TP1", "type": "ext_1272", "price": round(t1, 2), "r": round(rr1, 2)},
                    {"tp": "TP2", "type": "ext_1618", "price": round(t2, 2), "r": round(rr2, 2)}],
        "rr_tp2": round(rr2, 2), "impulse": {"low": round(float(swing_low), 2), "high": round(float(swing_high), 2)},
        "gates": gates, "passed": bool(all(gates.values())),
    }
