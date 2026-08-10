"""§2.2 Heartbeat — the central regime filter, and the process's centre of gravity.

RSP / SPY. Rising = the average stock is winning (broadening). Falling = the
leaders are carrying everything (narrowing). Where the ratio sits in its own
252-day range tells you when the current wave is tired.

This is a faithful transcription of `heartbeat_regime` from kernel §5, with the
magic numbers lifted into `spec.py` and the history handling made explicit. The
arithmetic is unchanged on purpose: this function is the one thing every other
Crown reading is gated on, so it must be auditable against the source line by
line, not "improved" into something that no longer matches the doc.

One property worth stating because it is easy to get wrong: `range_position` is
computed against the SAME window as the slope's parent history, so a ratio at
the top of a 252-day range means top-of-range *for the year*, not for the last
month. That is what makes "broadening tired" a year-scale statement.
"""

from __future__ import annotations

import numpy as np

from . import spec as S


def heartbeat_regime(
    rsp_close: float,
    spy_close: float,
    history: list[float] | np.ndarray,
    lookback_days: int = S.HB_LOOKBACK_DAYS,
) -> dict:
    """Classify the breadth regime from the RSP/SPY ratio.

    `history` is the trailing series of the ratio itself (not of either leg),
    oldest-first, and should already include today's value or not — either is
    fine, because the ratio is passed separately and the range test uses the
    history's own min/max.

    Returns regime / ratio / range_position / bias / confidence / rationale.
    Never raises: too little history is a *stated* neutral, not an exception.
    """
    if not spy_close:
        return _insufficient(0.0, "SPY close is zero or missing")

    ratio = float(rsp_close) / float(spy_close)
    hist = np.asarray(history, dtype=float)
    hist = hist[np.isfinite(hist)]
    hist = hist[-int(lookback_days):]

    if len(hist) < S.HB_MIN_HISTORY:
        return _insufficient(ratio, f"History too short ({len(hist)} obs)")

    window = hist[-S.HB_SLOPE_WINDOW:]
    recent_slope = float(np.polyfit(np.arange(len(window)), window, 1)[0])

    hist_min, hist_max = float(hist.min()), float(hist.max())
    range_pct = (ratio - hist_min) / (hist_max - hist_min + 1e-9)

    if recent_slope > S.HB_SLOPE_EPS:
        regime = "broadening"
    elif recent_slope < -S.HB_SLOPE_EPS:
        regime = "narrowing"
    else:
        regime = "neutral"

    if range_pct > S.HB_RANGE_TOP:
        range_position = "top"
    elif range_pct < S.HB_RANGE_BOTTOM:
        range_position = "bottom"
    else:
        range_position = "mid"

    # §5's ladder. The two "exhausted" cases score higher than the plain trend
    # cases because a tired wave is a more actionable statement than a live one.
    if regime == "broadening" and range_position == "top":
        bias = ("Broadening tired -> prepare rotation into leaders / mega-cap / "
                "AI bottlenecks")
        confidence = S.HB_CONF_EXTREME
    elif regime == "narrowing" and range_position == "bottom":
        bias = ("Narrowing exhausted -> hunt breadth trades (healthcare, "
                "financials, defensives)")
        confidence = S.HB_CONF_EXTREME
    elif regime == "broadening":
        bias = "Favor equal-weight, mid/small, defensives, financials"
        confidence = S.HB_CONF_TRENDING
    elif regime == "narrowing":
        bias = "Favor mega-cap / AI hardware / physical bottlenecks"
        confidence = S.HB_CONF_TRENDING
    else:
        bias = "Neutral regime - wait for clearer slope"
        confidence = S.HB_CONF_NEUTRAL

    return {
        "regime": regime,
        "ratio": round(ratio, 6),
        "range_position": range_position,
        "range_pct": round(float(range_pct), 4),
        "slope_20d": round(recent_slope, 8),
        "bias": bias,
        "confidence": float(confidence),
        "passes_gate": bool(confidence >= S.HB_CONFIDENCE_GATE),
        "observations": int(len(hist)),
        "rationale": (f"RSP/SPY={ratio:.4f} | slope={recent_slope:.6f} | "
                      f"range%={range_pct:.1%} | n={len(hist)}"),
    }


def _insufficient(ratio: float, why: str) -> dict:
    return {
        "regime": "neutral",
        "ratio": round(float(ratio), 6),
        "range_position": "mid",
        "range_pct": None,
        "slope_20d": None,
        "bias": "Insufficient history - stay neutral",
        "confidence": S.HB_CONF_NO_HISTORY,
        "passes_gate": False,       # 0.30 < 0.40 gate — the process stops
        "observations": 0,
        "rationale": why,
    }


def heartbeat_from_frames(rsp: "object", spy: "object") -> dict:
    """Convenience wrapper: two OHLCV frames (date, close) -> the regime read.

    Aligns the two on date first. An unaligned join is the classic way to get a
    ratio series with holes in it that still *looks* like a clean series.
    """
    import pandas as pd

    if rsp is None or spy is None or len(rsp) == 0 or len(spy) == 0:
        return _insufficient(0.0, "RSP or SPY bars unavailable")

    def _cols(df, tag):
        out = {"date": pd.to_datetime(df["date"]),
               f"{tag}_c": pd.to_numeric(df["close"], errors="coerce")}
        # OHLC when the frame carries it, so the ratio can be drawn as candles
        # rather than as a line nobody can read on a 0.30-0.35 scale.
        for src, dst in (("open", "o"), ("high", "h"), ("low", "l")):
            if src in getattr(df, "columns", []):
                out[f"{tag}_{dst}"] = pd.to_numeric(df[src], errors="coerce")
        return pd.DataFrame(out)

    a, b = _cols(rsp, "rsp"), _cols(spy, "spy")
    m = a.merge(b, on="date", how="inner").dropna(
        subset=["rsp_c", "spy_c"]).sort_values("date")
    if m.empty:
        return _insufficient(0.0, "RSP and SPY share no common dates")
    m = m.rename(columns={"rsp_c": "rsp", "spy_c": "spy"})

    ratio_series = (m["rsp"] / m["spy"]).to_numpy()
    out = heartbeat_regime(float(m["rsp"].iloc[-1]), float(m["spy"].iloc[-1]),
                           ratio_series)
    out["as_of"] = m["date"].iloc[-1].date().isoformat()

    # The series, so the reading can be SEEN rather than inferred. "Range
    # position: TOP" is not interpretable without the range it refers to, and
    # a 20-day slope is a number nobody can picture. Both are shipped with the
    # 252-day band they are measured against.
    tail = min(len(m), S.HB_LOOKBACK_DAYS)
    win = pd.Series(ratio_series[-S.HB_LOOKBACK_DAYS:])
    ratio_s = pd.Series(ratio_series)

    def _ratio(num, den):
        """One OHLC leg of the ratio, if both sides carry that column.

        The high of a RATIO is not the ratio of the two highs — it is the
        biggest numerator over the smallest denominator, so high = rsp_high /
        spy_LOW and low = rsp_low / spy_HIGH. Using high/high produced candles
        whose high sat below their own open.
        """
        if num not in m.columns or den not in m.columns:
            return None
        v = (m[num] / m[den]).tail(tail)
        return [None if pd.isna(x) else float(x) for x in v]

    r_open = _ratio("rsp_o", "spy_o")
    r_high = _ratio("rsp_h", "spy_l")      # max numerator / min denominator
    r_low = _ratio("rsp_l", "spy_h")       # min numerator / max denominator
    r_close = [float(x) for x in ratio_series[-tail:]]

    # These are BOUNDS — the two legs need not print their extremes at the same
    # instant — so clamp them around the bars that are exact. Without this a
    # bound can still cross the body it is supposed to contain.
    if r_open and r_high and r_low:
        for i in range(len(r_close)):
            body_hi = max(r_open[i], r_close[i])
            body_lo = min(r_open[i], r_close[i])
            r_high[i] = max(r_high[i], body_hi)
            r_low[i] = min(r_low[i], body_lo)

    def _round(xs):
        return None if xs is None else [round(x, 6) for x in xs]

    out["series"] = {
        "dates": [str(d.date()) for d in m["date"].tail(tail)],
        "ratio": [round(float(x), 6) for x in ratio_series[-tail:]],
        "open": _round(r_open),
        "high": _round(r_high),
        "low": _round(r_low),
        "close": _round(r_close),
        "ma_20": [None if pd.isna(v) else round(float(v), 6)
                  for v in ratio_s.rolling(S.HB_SLOPE_WINDOW,
                                           min_periods=S.HB_SLOPE_WINDOW)
                                   .mean().tail(tail)],
        "range_high": round(float(win.max()), 6),
        "range_low": round(float(win.min()), 6),
        "lookback_days": int(tail),
        "percentile_252d": round(float((win <= ratio_series[-1]).sum() - 1)
                                 / max(len(win) - 1, 1), 4),
        "ohlc_note": ("High/low are bounds: biggest RSP over smallest SPY and "
                      "the reverse. The two legs need not print their extremes "
                      "together, so the wick is a bound, not an observed tick."),
    }

    # The numbers a reader needs to judge the regime rather than take the label
    # on trust: how far breadth has moved over three horizons, where it sits
    # against its own average, and how long this regime has actually held.
    for w in (5, 20, 60):
        out[f"change_{w}d_pct"] = (
            round((ratio_series[-1] / ratio_series[-1 - w] - 1.0) * 100.0, 3)
            if len(ratio_series) > w and ratio_series[-1 - w] else None)

    ma_last = out["series"]["ma_20"][-1] if out["series"]["ma_20"] else None
    out["dist_to_ma20_pct"] = (
        round((ratio_series[-1] / ma_last - 1.0) * 100.0, 3)
        if ma_last else None)

    # How many consecutive sessions the 20-day slope has kept its current sign.
    # A regime three days old and one three months old are different statements
    # wearing the same label.
    streak, cur = 0, None
    for i in range(len(ratio_series) - 1,
                   max(S.HB_SLOPE_WINDOW, len(ratio_series) - 130) - 1, -1):
        seg = ratio_series[i - S.HB_SLOPE_WINDOW + 1: i + 1]
        if len(seg) < S.HB_SLOPE_WINDOW:
            break
        sl = float(np.polyfit(np.arange(len(seg)), seg, 1)[0])
        lab = ("broadening" if sl > S.HB_SLOPE_EPS
               else "narrowing" if sl < -S.HB_SLOPE_EPS else "neutral")
        if cur is None:
            cur = lab
        if lab != cur:
            break
        streak += 1
    out["days_in_regime"] = int(streak)
    return out
