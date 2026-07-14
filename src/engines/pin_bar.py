"""Pin Bar / Inside Bar Pattern Detector — pure candlestick geometry.

Port of the deterministic parts of AlgoFyre's "P.I.B. System" (Pin Bar / Inside
Bar). Evaluates the LAST bar in `daily` (which, for an EOD panel, is already
fully closed — no lookahead / no repaint risk).

Pin bar (rejection candle): a long wick on one side, a small body, and a small
opposite wick — the market pushed hard one way and got rejected.
    BULLISH pin bar: lower_wick >= wick_ratio*range AND body <= body_ratio*range
                     AND upper_wick <= opp_wick_ratio*range
    BEARISH pin bar: the mirror (a long upper wick).

Inside bar: the last bar's range is fully engulfed by the PRIOR bar's range
(high < prev_high AND low > prev_low) — a one-bar consolidation.

P.I.B. combo (the source strategy's named pattern): a pin bar immediately
FOLLOWED by an inside bar — the rejection candle, then a pause. Evaluated as
bar[-2] == pin bar AND bar[-1] == inside bar (relative to bar[-2]).

Optional small-candle filter (small_candle_filter=True): a pin bar only counts
if its total range is >= small_candle_mult times the PRECEDING candle's range —
filters out "pin bars" that are just noise inside an already-tiny range.

Pure, deterministic, single-ticker, no engine analog exists elsewhere in AQE.
Never raises — malformed input or too few bars degrades to the null result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_REQUIRED_COLS = {"date", "open", "high", "low", "close"}
_MIN_BARS = 4

_NULL = {
    "pin_bar_state": "NONE",
    "pin_bar_date": None,
    "pin_bar_level": None,
    "inside_bar": False,
    "pib_pattern": False,
}


def _pin_bar_at(o: float, h: float, l: float, c: float, prev_range: float, *,
                wick_ratio: float, body_ratio: float, opp_wick_ratio: float,
                small_candle_filter: bool, small_candle_mult: float) -> str | None:
    """Pin-bar geometry test for one OHLC bar. Returns 'BULLISH_PIN' /
    'BEARISH_PIN' / None. `prev_range` = the range of the bar immediately
    before it (used only by the optional small-candle filter)."""
    rng = h - l
    if not (np.isfinite(rng) and rng > 0):
        return None
    if small_candle_filter and np.isfinite(prev_range) and prev_range > 0:
        if rng < small_candle_mult * prev_range:
            return None
    body = abs(c - o)
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    if (lower_wick >= wick_ratio * rng and body <= body_ratio * rng
            and upper_wick <= opp_wick_ratio * rng):
        return "BULLISH_PIN"
    if (upper_wick >= wick_ratio * rng and body <= body_ratio * rng
            and lower_wick <= opp_wick_ratio * rng):
        return "BEARISH_PIN"
    return None


def compute_pin_bar(
    daily: pd.DataFrame,
    *,
    wick_ratio: float = 0.66,
    body_ratio: float = 0.4,
    opp_wick_ratio: float = 0.4,
    small_candle_filter: bool = True,
    small_candle_mult: float = 2.0,
) -> dict:
    """Pin bar / inside bar / P.I.B.-combo read on the LAST bar of `daily`.

    `daily`: single-ticker OHLC(V) frame, ascending date, columns
    date/open/high/low/close (volume not required — pure geometry).

    Returns (always present, never raises):
        pin_bar_state:  "BULLISH_PIN" | "BEARISH_PIN" | "NONE" — the LAST bar
        pin_bar_date:   date of that pin bar (None if NONE)
        pin_bar_level:  the pin bar's rejection extreme (USD) — the low for a
                        bullish pin (support), the high for a bearish pin
                        (resistance); None if NONE
        inside_bar:     bool — is the LAST bar an inside bar vs the prior one?
        pib_pattern:    bool — was the SECOND-TO-LAST bar a pin bar, immediately
                        followed by the last bar as an inside bar?
    """
    try:
        if daily is None or len(daily) < _MIN_BARS:
            return dict(_NULL)
        if not _REQUIRED_COLS.issubset(daily.columns):
            return dict(_NULL)

        d = daily.tail(4).reset_index(drop=True)
        o = d["open"].astype(float).to_numpy()
        h = d["high"].astype(float).to_numpy()
        l = d["low"].astype(float).to_numpy()
        c = d["close"].astype(float).to_numpy()
        dates = d["date"].to_numpy()

        # Indices: 0=bar[-4], 1=bar[-3], 2=bar[-2], 3=bar[-1] (the last/most
        # recent CLOSED bar). rng_m1 = range of bar[-2] (prev of bar[-1]);
        # rng_m2 = range of bar[-3] (prev of bar[-2]).
        rng_m1 = h[2] - l[2]
        rng_m2 = h[1] - l[1]

        kw = dict(wick_ratio=wick_ratio, body_ratio=body_ratio,
                  opp_wick_ratio=opp_wick_ratio,
                  small_candle_filter=small_candle_filter,
                  small_candle_mult=small_candle_mult)
        last_state = _pin_bar_at(o[3], h[3], l[3], c[3], rng_m1, **kw)
        prev_state = _pin_bar_at(o[2], h[2], l[2], c[2], rng_m2, **kw)

        inside_bar = bool(np.isfinite(h[3]) and np.isfinite(h[2])
                          and np.isfinite(l[3]) and np.isfinite(l[2])
                          and h[3] < h[2] and l[3] > l[2])
        pib_pattern = bool(prev_state is not None and inside_bar)

        out = dict(_NULL)
        if last_state is not None:
            out["pin_bar_state"] = last_state
            out["pin_bar_date"] = str(pd.Timestamp(dates[3]).date())
            out["pin_bar_level"] = round(
                float(l[3] if last_state == "BULLISH_PIN" else h[3]), 2)
        out["inside_bar"] = inside_bar
        out["pib_pattern"] = pib_pattern
        return out
    except Exception:  # noqa: BLE001 — pure geometry read, never blocks the caller
        return dict(_NULL)
