#!/usr/bin/env python3
"""Intraday tape READ — measurement only, never a verdict (PM ruling, 29 Jul).

Ported from the borrowed src/intraday/momentum.py with one deliberate change:
the old module emitted ENTER/CAUTION/STAND_DOWN — a trading call baked into
deterministic code with hardcoded thresholds, ahead of both the committee and
the PM. That call is deleted. This module reports six measurements, a 0-100
composite score, and a labelled STATE — an observation the bracket's entry
zone reads and the committee/PM may weigh. It never tells anyone what to do.

Deterministic (law 4): pure functions on bars already fetched by the
orchestrator (FMP `chart`, 5-min bars). No network I/O here.

Used ONLY intraday. Premarket has no tape — bracket_calc.py skips this
module entirely before the open and says so on the line.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

# ── unapproved-provenance constants, carried from the borrowed module ──────
# These shape the ENTRY ZONE only (never the stop, never size, never a
# verdict). Flagged in skills/bracket/SKILL.md as not charter-sourced.
OR_MINUTES = 30
SESSION_OPEN = (9, 30)
RVOL_LOOKBACK_DAYS = 10
ATR_BARS = 14
ACCEL_LOOKBACK = 6
EXTENDED_R = 1.0
EXTENDED_VWAP_ATR = 2.0
VWAP_NEAR_ATR = 0.5
RVOL_STRONG = 1.3
IMS_WEIGHTS = {"vwap": 0.25, "slope": 0.15, "or": 0.15, "rvol": 0.20, "accel": 0.15, "trend": 0.10}


def normalize_bars(bars) -> list[dict]:
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
            out.append({"dt": dt, "o": float(b["open"]), "h": float(b["high"]),
                        "l": float(b["low"]), "c": float(b["close"]),
                        "v": float(b.get("volume", 0) or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["dt"])
    return out


def _intraday_atr(bars: list[dict], n: int = ATR_BARS) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    tail = trs[-n:] if len(trs) >= n else trs
    return float(np.mean(tail)) if tail else 0.0


def _vwap_series(day_bars: list[dict]) -> list[float]:
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


def intraday_read(bars5, rec: dict | None = None) -> dict:
    """Measurement only. Returns {ims, state, components}. NO action/verdict field."""
    rec = rec or {}
    bars = normalize_bars(bars5)
    if len(bars) < 4:
        return {"ims": None, "state": "UNKNOWN", "components": {"reason": "insufficient bars"}}

    by_day: dict = {}
    for b in bars:
        by_day.setdefault(b["dt"].date(), []).append(b)
    days = sorted(by_day)
    today = days[-1]
    today_bars = by_day[today]
    price = today_bars[-1]["c"]
    now_t = today_bars[-1]["dt"].time()

    intraday_atr = _intraday_atr(bars) or (price * 0.002)

    vwaps = _vwap_series(today_bars)
    vwap = vwaps[-1]
    vwap_pos = (price - vwap) / intraday_atr if intraday_atr else 0.0
    above_vwap = price >= vwap
    slope_ref = vwaps[-7] if len(vwaps) >= 7 else vwaps[0]
    vwap_slope_up = vwap > slope_ref

    open_min = SESSION_OPEN[0] * 60 + SESSION_OPEN[1]
    or_bars = [b for b in today_bars if (b["dt"].hour * 60 + b["dt"].minute) < open_min + OR_MINUTES]
    or_high = max((b["h"] for b in or_bars), default=None)
    or_low = min((b["l"] for b in or_bars), default=None)
    or_break = bool(or_high is not None and price > or_high)
    below_or = bool(or_low is not None and price < or_low)

    def _cum_to(t, day_bars):
        m = t.hour * 60 + t.minute
        return sum(b["v"] for b in day_bars if (b["dt"].hour * 60 + b["dt"].minute) <= m)
    today_cum = _cum_to(now_t, today_bars)
    prior = days[-(RVOL_LOOKBACK_DAYS + 1):-1]
    prior_cums = [_cum_to(now_t, by_day[d]) for d in prior]
    prior_cums = [c for c in prior_cums if c > 0]
    rvol_pace = (today_cum / float(np.mean(prior_cums))) if prior_cums else None

    closes = [b["c"] for b in today_bars]
    k = min(ACCEL_LOOKBACK, len(closes))
    if k >= 3:
        y = np.array(closes[-k:], dtype=float)
        slope = float(np.polyfit(np.arange(k), y, 1)[0])
    else:
        slope = 0.0
    accel_norm = slope / intraday_atr if intraday_atr else 0.0
    accel_up = slope > 0

    lows = [b["l"] for b in today_bars]
    hl_count = 0
    for i in range(len(lows) - 1, 0, -1):
        if lows[i] > lows[i - 1]:
            hl_count += 1
        else:
            break

    entry_ref = rec.get("entry")
    _risk = (rec.get("bracket") or {}).get("risk")
    ext_r = None
    if isinstance(entry_ref, (int, float)) and isinstance(_risk, (int, float)) and _risk:
        ext_r = (price - entry_ref) / _risk

    near_vwap = abs(vwap_pos) <= VWAP_NEAR_ATR

    vwap_score = _clip(50 + vwap_pos * 20)
    slope_score = 100.0 if vwap_slope_up else 30.0
    or_score = 100.0 if or_break else (10.0 if below_or else 50.0)
    rvol_score = _clip(rvol_pace * 50) if rvol_pace is not None else 50.0
    accel_score = _clip(50 + accel_norm * 50)
    trend_score = _clip(40 + hl_count * 20)
    w = IMS_WEIGHTS
    ims = (vwap_score * w["vwap"] + slope_score * w["slope"] + or_score * w["or"]
           + rvol_score * w["rvol"] + accel_score * w["accel"] + trend_score * w["trend"]) / sum(w.values())

    # State machine — a LABEL on the tape, not an instruction.
    if not above_vwap:
        state = "BROKEN" if below_or else "FADING"
    elif ext_r is not None and ext_r >= EXTENDED_R and vwap_pos >= EXTENDED_VWAP_ATR:
        state = "EXTENDED"
    elif near_vwap and vwap_slope_up and hl_count >= 1:
        state = "PULLBACK_HOLDING"
    elif (vwap_slope_up and accel_up and (rvol_pace is None or rvol_pace >= RVOL_STRONG)
          and (or_break or vwap_pos > 0)):
        state = "ACCELERATING"
    else:
        state = "COILING"

    return {
        "ims": round(ims, 1), "state": state,
        "components": {
            "price": round(price, 2), "vwap": round(vwap, 2),
            "vwap_pos_atr": round(vwap_pos, 2), "vwap_slope_up": vwap_slope_up,
            "intraday_atr": round(intraday_atr, 3),
            "or_high": round(or_high, 2) if or_high is not None else None,
            "or_low": round(or_low, 2) if or_low is not None else None,
            "or_break": or_break,
            "rvol_pace": round(rvol_pace, 2) if rvol_pace is not None else None,
            "accel_atr_per_bar": round(accel_norm, 3), "higher_lows": hl_count,
            "ext_r": round(ext_r, 2) if ext_r is not None else None,
            "session": str(today), "as_of": today_bars[-1]["dt"].strftime("%Y-%m-%d %H:%M"),
        },
    }


def entry_zone_from_state(read: dict, aqe_entry: float | None) -> dict:
    """Queue shape from the tape state. {low, high, kind, note}. Never stands a name down —
    it just says where to queue it; STAND_DOWN reads no longer exist (PM ruling)."""
    comp = read.get("components", {})
    state = read.get("state", "UNKNOWN")
    price = comp.get("price")
    vwap = comp.get("vwap")
    or_high = comp.get("or_high")
    if state in ("FADING", "BROKEN", "UNKNOWN") or price is None:
        ref = aqe_entry if aqe_entry is not None else price
        return {"kind": "watch", "low": None, "high": None,
                "note": f"{state}: no queueable intraday entry — watching. Last AQE/ref entry {ref}."}
    if state == "EXTENDED":
        support = vwap if vwap is not None else price
        return {"kind": "limit", "low": round(support, 2), "high": round(price, 2),
                "note": "Extended — queue the pullback toward VWAP, do not chase."}
    if state == "COILING":
        trig = or_high if or_high is not None else price
        return {"kind": "stop_breakout", "low": round(trig, 2), "high": round(trig * 1.003, 2),
                "note": "Coiling above VWAP — queue a buy-stop on the range break."}
    if state == "PULLBACK_HOLDING":
        lo = vwap if vwap is not None else price
        return {"kind": "limit", "low": round(min(lo, price), 2), "high": round(price, 2),
                "note": "Pulled back to VWAP and holding — best queue point."}
    return {"kind": "now", "low": round(price * 0.999, 2), "high": round(price * 1.005, 2),
            "note": "Accelerating, not extended — queue at/near market."}
