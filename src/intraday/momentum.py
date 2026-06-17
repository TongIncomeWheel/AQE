"""Deterministic intraday momentum read from 5-min OHLCV bars.

Pure functions, no network I/O — unit-tested with synthetic bars and reused by
the Claude Code skill (which fetches bars via the financial MCP `chart` tool).

`intraday_momentum(bars5, rec)` returns:
    {ims, state, components} where
      ims        : 0–100 Intraday Momentum Score
      state      : ACCELERATING | PULLBACK_HOLDING | COILING | EXTENDED |
                   FADING | BROKEN | UNKNOWN
      components : the raw sub-metrics (VWAP, OR, RVOL pace, accel, …) so the
                   plan + verdict can explain themselves.

Bars are list[dict] with keys date/open/high/low/close/volume (FMP `chart`
shape). Order doesn't matter — they're normalised + sorted ascending here.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from . import config as C


# ── bar normalisation ──────────────────────────────────────────────────────
def normalize_bars(bars) -> list[dict]:
    """Parse + sort ascending. Each → {dt, o, h, l, c, v}. Bad rows dropped."""
    out: list[dict] = []
    for b in bars or []:
        d = b.get("date")
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(str(d), fmt)
                break
            except (ValueError, TypeError):
                continue
        if dt is None:
            try:
                dt = datetime.fromisoformat(str(d))
            except (ValueError, TypeError):
                continue
        try:
            out.append({
                "dt": dt, "o": float(b["open"]), "h": float(b["high"]),
                "l": float(b["low"]), "c": float(b["close"]),
                "v": float(b.get("volume", 0) or 0),
            })
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["dt"])
    return out


def _intraday_atr(bars: list[dict], n: int = C.ATR_BARS) -> float:
    """Mean true range over the last n 5-min bars (intraday volatility unit)."""
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    tail = trs[-n:] if len(trs) >= n else trs
    return float(np.mean(tail)) if tail else 0.0


def _vwap_series(day_bars: list[dict]) -> list[float]:
    """Running session VWAP for one day's bars (ascending)."""
    cum_pv = 0.0
    cum_v = 0.0
    out = []
    for b in day_bars:
        typ = (b["h"] + b["l"] + b["c"]) / 3.0
        cum_pv += typ * b["v"]
        cum_v += b["v"]
        out.append(cum_pv / cum_v if cum_v > 0 else b["c"])
    return out


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(max(lo, min(hi, x)))


def intraday_momentum(bars5, rec: dict | None = None) -> dict:
    """Compute the intraday momentum read from 5-min bars + the AQE record."""
    rec = rec or {}
    bars = normalize_bars(bars5)
    if len(bars) < 4:
        return {"ims": None, "state": "UNKNOWN",
                "components": {"reason": "insufficient bars"}}

    # Split into trading days; "today" = the latest session present.
    by_day: dict = {}
    for b in bars:
        by_day.setdefault(b["dt"].date(), []).append(b)
    days = sorted(by_day)
    today = days[-1]
    today_bars = by_day[today]
    price = today_bars[-1]["c"]
    now_t = today_bars[-1]["dt"].time()

    intraday_atr = _intraday_atr(bars) or (price * 0.002)  # avoid /0

    # ── VWAP position + slope ──
    vwaps = _vwap_series(today_bars)
    vwap = vwaps[-1]
    vwap_pos = (price - vwap) / intraday_atr if intraday_atr else 0.0
    above_vwap = price >= vwap
    slope_ref = vwaps[-7] if len(vwaps) >= 7 else vwaps[0]
    vwap_slope_up = vwap > slope_ref

    # ── Opening range (first OR_MINUTES of the session) ──
    open_min = C.SESSION_OPEN[0] * 60 + C.SESSION_OPEN[1]
    or_bars = [b for b in today_bars
               if (b["dt"].hour * 60 + b["dt"].minute) < open_min + C.OR_MINUTES]
    or_high = max((b["h"] for b in or_bars), default=None)
    or_low = min((b["l"] for b in or_bars), default=None)
    or_break = bool(or_high is not None and price > or_high)
    below_or = bool(or_low is not None and price < or_low)

    # ── RVOL pace: today's cum volume vs avg cum volume by this time-of-day ──
    def _cum_to(t, day_bars):
        m = t.hour * 60 + t.minute
        return sum(b["v"] for b in day_bars
                   if (b["dt"].hour * 60 + b["dt"].minute) <= m)
    today_cum = _cum_to(now_t, today_bars)
    prior = days[-(C.RVOL_LOOKBACK_DAYS + 1):-1]
    prior_cums = [_cum_to(now_t, by_day[d]) for d in prior]
    prior_cums = [c for c in prior_cums if c > 0]
    rvol_pace = (today_cum / float(np.mean(prior_cums))) if prior_cums else None

    # ── Acceleration: slope of the last ACCEL_LOOKBACK closes (normalised) ──
    closes = [b["c"] for b in today_bars]
    k = min(C.ACCEL_LOOKBACK, len(closes))
    if k >= 3:
        y = np.array(closes[-k:], dtype=float)
        slope = float(np.polyfit(np.arange(k), y, 1)[0])     # $/bar
    else:
        slope = 0.0
    accel_norm = slope / intraday_atr if intraday_atr else 0.0  # ATR/bar
    accel_up = slope > 0

    # ── Trend quality: consecutive higher lows on recent bars ──
    lows = [b["l"] for b in today_bars]
    hl_count = 0
    for i in range(len(lows) - 1, 0, -1):
        if lows[i] > lows[i - 1]:
            hl_count += 1
        else:
            break

    # ── Extension vs the AQE reference entry (R's already run) ──
    entry_ref = rec.get("entry")
    dsl_risk = rec.get("dsl_risk")
    ext_r = None
    if isinstance(entry_ref, (int, float)) and isinstance(dsl_risk, (int, float)) \
            and dsl_risk:
        ext_r = (price - entry_ref) / dsl_risk

    near_vwap = abs(vwap_pos) <= C.VWAP_NEAR_ATR

    # ── IMS composite (0–100) ──
    vwap_score = _clip(50 + vwap_pos * 20)
    slope_score = 100.0 if vwap_slope_up else 30.0
    or_score = 100.0 if or_break else (10.0 if below_or else 50.0)
    rvol_score = _clip(rvol_pace * 50) if rvol_pace is not None else 50.0
    accel_score = _clip(50 + accel_norm * 50)
    trend_score = _clip(40 + hl_count * 20)
    w = C.IMS_WEIGHTS
    ims = (vwap_score * w["vwap"] + slope_score * w["slope"]
           + or_score * w["or"] + rvol_score * w["rvol"]
           + accel_score * w["accel"] + trend_score * w["trend"]) / sum(w.values())

    # ── State machine (priority order) ──
    if not above_vwap:
        state = "BROKEN" if below_or else "FADING"
    elif (ext_r is not None and ext_r >= C.EXTENDED_R
          and vwap_pos >= C.EXTENDED_VWAP_ATR):
        state = "EXTENDED"
    elif near_vwap and vwap_slope_up and hl_count >= 1:
        state = "PULLBACK_HOLDING"
    elif (vwap_slope_up and accel_up
          and (rvol_pace is None or rvol_pace >= C.RVOL_STRONG)
          and (or_break or vwap_pos > 0)):
        state = "ACCELERATING"
    else:
        state = "COILING"

    return {
        "ims": round(ims, 1),
        "state": state,
        "components": {
            "price": round(price, 2),
            "vwap": round(vwap, 2),
            "vwap_pos_atr": round(vwap_pos, 2),
            "vwap_slope_up": vwap_slope_up,
            "intraday_atr": round(intraday_atr, 3),
            "or_high": round(or_high, 2) if or_high is not None else None,
            "or_low": round(or_low, 2) if or_low is not None else None,
            "or_break": or_break,
            "rvol_pace": round(rvol_pace, 2) if rvol_pace is not None else None,
            "accel_atr_per_bar": round(accel_norm, 3),
            "higher_lows": hl_count,
            "ext_r": round(ext_r, 2) if ext_r is not None else None,
            "session": str(today),
            "as_of": today_bars[-1]["dt"].strftime("%Y-%m-%d %H:%M"),
        },
    }
