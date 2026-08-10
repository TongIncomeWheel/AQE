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

    a = pd.DataFrame({"date": pd.to_datetime(rsp["date"]),
                      "rsp": pd.to_numeric(rsp["close"], errors="coerce")})
    b = pd.DataFrame({"date": pd.to_datetime(spy["date"]),
                      "spy": pd.to_numeric(spy["close"], errors="coerce")})
    m = a.merge(b, on="date", how="inner").dropna().sort_values("date")
    if m.empty:
        return _insufficient(0.0, "RSP and SPY share no common dates")

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
    out["series"] = {
        "dates": [str(d.date()) for d in m["date"].tail(tail)],
        "ratio": [round(float(x), 6) for x in ratio_series[-tail:]],
        "ma_20": [None if pd.isna(v) else round(float(v), 6)
                  for v in ratio_s.rolling(S.HB_SLOPE_WINDOW,
                                           min_periods=S.HB_SLOPE_WINDOW)
                                   .mean().tail(tail)],
        "range_high": round(float(win.max()), 6),
        "range_low": round(float(win.min()), 6),
        "lookback_days": int(tail),
    }
    return out
