"""Elder Context block (Instruction v1.1, 19 Jun 2026).

Pure, deterministic VWAP / volume / VCP / pattern / exhaustion context that lets
the AIC read an Elder score with price-volume confirmation. No I/O — callers pass
bar lists (hourly 5-day + daily 20-day). All fields degrade to None on thin data.

`elder_pattern(elder_5d)` is free (needs only the elder_5d array) and is always
computable. `compute_elder_context(...)` returns the full block.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np


# ── Elder pattern taxonomy (Charter §3.8.1) ────────────────────────────────
def elder_pattern(elder_5d) -> str | None:
    """Classify the last-5 Elder readings (oldest→newest = T-4..T-0)."""
    try:
        v = [int(round(float(x))) for x in (elder_5d or []) if x is not None]
    except (TypeError, ValueError):
        return None
    if len(v) < 3:
        return None
    t0 = v[-1]
    ge9 = sum(1 for x in v if x >= 9)

    # 1. SUSTAINED — 4+ sessions ≥9, no dip below 8.
    if ge9 >= 4 and min(v) >= 8:
        return "SUSTAINED"
    # 2. CORRECTION_REENTRY — interior dip ≤7 after a prior high ≥9, recovers ≥9 at T-0.
    for i in range(1, len(v) - 1):
        if v[i] <= 7 and any(v[j] >= 9 for j in range(i)) and t0 >= 9:
            return "CORRECTION_REENTRY"
    # 3. ACCELERATION — early (T-4/T-3) value ≤6, T-0 & T-1 ≥9, rising.
    if (len(v) >= 2 and (v[0] <= 6 or v[1] <= 6)
            and v[-1] >= 9 and v[-2] >= 9 and v[-1] >= v[0]):
        return "ACCELERATION"
    # 4. ACCUMULATION_BASE — all ≤8, none ≥9, min ≤6, non-decreasing.
    if (max(v) <= 8 and min(v) <= 6
            and all(v[i] >= v[i - 1] for i in range(1, len(v)))):
        return "ACCUMULATION_BASE"
    # 5. INTERRUPTED — a ≤5 reading anywhere except T-4 (recent interruption).
    if any(v[i] <= 5 for i in range(1, len(v))):
        return "INTERRUPTED"
    return None


# ── bar helpers ────────────────────────────────────────────────────────────
def _norm(bars) -> list[dict]:
    out = []
    for b in bars or []:
        d = b.get("date")
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(d), fmt)
                break
            except (ValueError, TypeError):
                continue
        if dt is None:
            continue
        try:
            out.append({"dt": dt, "o": float(b["open"]), "h": float(b["high"]),
                        "l": float(b["low"]), "c": float(b["close"]),
                        "v": float(b.get("volume", 0) or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["dt"])
    return out


def _slope_label(series: list[float]) -> str:
    """RISING/FALLING/FLAT from linreg slope as %/bar (×7 ≈ per session)."""
    if len(series) < 3:
        return "FLAT"
    y = np.asarray(series, float)
    x = np.arange(len(y))
    slope = float(np.polyfit(x, y, 1)[0])
    mean = float(np.mean(y)) or 1.0
    pct_per_session = slope / mean * 100 * 7
    if pct_per_session > 0.1:
        return "RISING"
    if pct_per_session < -0.1:
        return "FALLING"
    return "FLAT"


def compute_elder_context(elder_5d, hourly_bars, daily_bars,
                          resistance_price=None, computed_date=None) -> dict:
    """Full elder_context block. Hourly fields → None when hourly bars are thin;
    daily fields (VCP, 20d vol) come from daily_bars."""
    hb = _norm(hourly_bars)[-40:]
    db = _norm(daily_bars)[-20:]
    pattern = elder_pattern(elder_5d)
    ctx: dict = {
        "computed_date": computed_date or (db[-1]["dt"].date().isoformat()
                                           if db else None),
        "hourly_bars_used": len(hb),
        "vwap_5d": {"value": None, "position": None, "slope_5d": None},
        "volume": {"vol_trend_5d": None, "vol_above_20d_avg": None,
                   "up_bar_vol_ratio": None, "avg_vol_20d": None,
                   "avg_vol_5d_up_bars": None, "avg_vol_5d_down_bars": None},
        "vcp": {"base_range_pct": None, "current_range_pct_5d": None,
                "vcp_tightness_pct": None, "vcp_label": "VCP_ABSENT"},
        "elder_pattern": pattern,
        "exhaustion_check": {"vol_contracting_on_up_bars": False,
                             "vwap_flat_or_falling": False,
                             "at_structural_resistance": False,
                             "exhaustion_flag": "CLEAR"},
    }

    price = (hb[-1]["c"] if hb else (db[-1]["c"] if db else None))

    # ── VWAP (5-day hourly) ──
    vwap_pos = None
    if hb:
        run_vwap, cum_pv, cum_v = [], 0.0, 0.0
        for b in hb:
            typ = (b["h"] + b["l"] + b["c"]) / 3
            cum_pv += typ * b["v"]
            cum_v += b["v"]
            run_vwap.append(cum_pv / cum_v if cum_v else b["c"])
        vwap = run_vwap[-1]
        vwap_pos = "ABOVE" if (price is not None and price >= vwap) else "BELOW"
        ctx["vwap_5d"] = {"value": round(vwap, 2), "position": vwap_pos,
                          "slope_5d": _slope_label(run_vwap)}

    # ── Volume (hourly up/down + 5d-vs-20d daily) ──
    if hb:
        up = [b["v"] for b in hb if b["c"] > b["o"]]
        dn = [b["v"] for b in hb if b["c"] < b["o"]]
        au = float(np.mean(up)) if up else 0.0
        ad = float(np.mean(dn)) if dn else 0.0
        ctx["volume"]["avg_vol_5d_up_bars"] = int(au)
        ctx["volume"]["avg_vol_5d_down_bars"] = int(ad)
        ctx["volume"]["up_bar_vol_ratio"] = round(au / ad, 2) if ad else None
        # vol_trend: first 2 sessions vs last 2 sessions (by date)
        by_day: dict = {}
        for b in hb:
            by_day.setdefault(b["dt"].date(), []).append(b["v"])
        days = sorted(by_day)
        if len(days) >= 4:
            early = np.mean([np.mean(by_day[d]) for d in days[:2]])
            late = np.mean([np.mean(by_day[d]) for d in days[-2:]])
            if early > 0:
                chg = (late - early) / early
                ctx["volume"]["vol_trend_5d"] = (
                    "EXPANDING" if chg > 0.10 else
                    "CONTRACTING" if chg < -0.10 else "FLAT")
    if db:
        vols = [b["v"] for b in db]
        avg20 = float(np.mean(vols))
        ctx["volume"]["avg_vol_20d"] = int(avg20)
        if len(vols) >= 5:
            ctx["volume"]["vol_above_20d_avg"] = bool(np.mean(vols[-5:]) > avg20)

    # ── VCP (20-day daily base vs 5-day contraction) ──
    if len(db) >= 5:
        hi20, lo20 = max(b["h"] for b in db), min(b["l"] for b in db)
        mid20 = (hi20 + lo20) / 2 or 1.0
        base = (hi20 - lo20) / mid20 * 100
        d5 = db[-5:]
        hi5, lo5 = max(b["h"] for b in d5), min(b["l"] for b in d5)
        mid5 = (hi5 + lo5) / 2 or 1.0
        cur = (hi5 - lo5) / mid5 * 100
        tight = (cur / base * 100) if base else None
        ctx["vcp"]["base_range_pct"] = round(base, 1)
        ctx["vcp"]["current_range_pct_5d"] = round(cur, 1)
        ctx["vcp"]["vcp_tightness_pct"] = round(tight, 1) if tight is not None else None
        # label
        vt = ctx["volume"]["vol_trend_5d"]
        ratio = ctx["volume"]["up_bar_vol_ratio"]
        conds = [
            tight is not None and tight < 50,
            vt == "CONTRACTING",
            vwap_pos == "ABOVE",
            ratio is not None and ratio > 1.0,
            pattern in ("ACCUMULATION_BASE", "CORRECTION_REENTRY", "ACCELERATION"),
        ]
        if tight is not None and tight >= 50 or vwap_pos == "BELOW":
            ctx["vcp"]["vcp_label"] = "VCP_ABSENT"
        elif all(conds):
            ctx["vcp"]["vcp_label"] = "VCP_SETUP"
        elif tight is not None and tight < 50:
            ctx["vcp"]["vcp_label"] = "VCP_PARTIAL"

    # ── Exhaustion check ──
    near_high = False
    if db and price is not None:
        hi20 = max(b["h"] for b in db)
        near_high = (hi20 - price) / hi20 < 0.02 if hi20 else False
    vol_contract_up = bool(ctx["volume"]["vol_trend_5d"] == "CONTRACTING" and near_high)
    vwap_ff = ctx["vwap_5d"]["slope_5d"] in ("FLAT", "FALLING")
    at_res = False
    if resistance_price and price:
        at_res = abs(price - resistance_price) / price < 0.02
    flags = [vol_contract_up, vwap_ff, at_res]
    n = sum(1 for f in flags if f)
    ctx["exhaustion_check"] = {
        "vol_contracting_on_up_bars": vol_contract_up,
        "vwap_flat_or_falling": vwap_ff,
        "at_structural_resistance": at_res,
        "exhaustion_flag": "RISK" if n == 3 else "CAUTION" if n == 2 else "CLEAR",
    }
    return ctx
