"""AQE Pricer — a pure bracket CALCULATOR (no recommendation, no decision).

Unlike `plan.py` (recommend-only, gates to ENTER/STAND_DOWN), this always returns
a full bracket for ANY ticker — in or out of the AQE universe — so it never blanks.
It is a calculator, not a gatekeeper of logic: it computes the best entry/stop/TP
from multi-timeframe structure (daily FIB / MA / DSL / coil + a 5-day hourly
swing read + the live 5-min momentum), shows the candidate levels and the metrics,
and leaves the call to the human/AIC.

Inputs are plain bar lists/frames (feed-agnostic). For a ticker already in the AQE
export, its precomputed record is used; for any other symbol the structural levels
are computed on the fly from daily bars (reusing AQE's own DSL/fib/structure math).
"""

from __future__ import annotations

import math

import numpy as np

from . import config as C
from .momentum import intraday_momentum, normalize_bars


# ── helpers ────────────────────────────────────────────────────────────────
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _atr_from_df(df, n: int = 14) -> float:
    """Wilder-ish ATR (simple mean TR) over the last n daily bars."""
    if df is None or len(df) < 2:
        return 0.0
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
          for i in range(1, len(df))]
    tail = tr[-n:] if len(tr) >= n else tr
    return float(np.mean(tail)) if tail else 0.0


def _pivot_lows(bars: list[dict], price: float, k: int = 3, n: int = 4) -> list[dict]:
    """Last n confirmed fractal pivot lows below price (for hourly / 5-min)."""
    if len(bars) < 2 * k + 1:
        return []
    lows = [b["l"] for b in bars]
    out = []
    for i in range(len(lows) - k - 1, k - 1, -1):
        if lows[i] <= min(lows[i - k:i + k + 1]) and lows[i] < price:
            out.append({"price": round(lows[i], 2),
                        "date": bars[i]["dt"].strftime("%Y-%m-%d %H:%M")})
            if len(out) >= n:
                break
    return out


def ensure_levels(ticker: str, rec: dict | None, daily_df) -> dict:
    """Return a record carrying the structural levels the bracket needs.

    If `rec` (the AQE export record) already has them, use it. Otherwise compute
    entry/DSL/fib/MA/structural_levels/targets from daily bars — reusing AQE's
    own `levels_for_ticker` + the drive_sync structural helpers — so a typed-in
    symbol gets the exact same treatment as a universe name.
    """
    rec = dict(rec or {})
    rec.setdefault("ticker", ticker)
    if _num(rec.get("dsl_stop")) and _num(rec.get("atr_14d")):
        return rec
    if daily_df is None or len(daily_df) < 20:
        return rec
    try:
        from src.scanner.levels import levels_for_ticker
        from src.data.drive_sync import (
            _structural_stop_analysis, _structural_target_analysis,
        )
        close = float(daily_df["close"].iloc[-1])
        atr14 = _atr_from_df(daily_df, 14)
        d = levels_for_ticker(
            close, atr14,
            daily_df["high"].to_numpy(float),
            daily_df["low"].to_numpy(float),
            daily_df["date"].to_numpy(),
        )
        if not d:
            return rec
        ma = {w: round(float(daily_df["close"].tail(w).mean()), 2)
              for w in (20, 50, 100, 200) if len(daily_df) >= w}
        slevels, opt = _structural_stop_analysis(d, ma)
        stargets = _structural_target_analysis(d)
        rets = (d.get("fib") or {}).get("retracements") or {}
        rec.update({
            "entry": d["entry"], "dsl_stop": d["stop"], "dsl_risk": d["risk"],
            "atr_14d": round(atr14, 2),
            "dsl_tp_1r": d["tp_1r"], "dsl_tp_2r": d["tp_2r"], "dsl_tp_3r": d["tp_3r"],
            "dsl_rr_pct": d.get("rr_pct"), "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "coil_entry": round(d["stop"] + atr14, 2),
            "max_chase_tp2": round((d["tp_2r"] + 2 * d["stop"]) / 3, 2),
            "ma_20": ma.get(20), "ma_50": ma.get(50),
            "ma_100": ma.get(100), "ma_200": ma.get(200),
            "fib_618": rets.get("0.618"), "fib_786": rets.get("0.786"),
            "structural_levels": slevels, "structural_targets": stargets,
            "optimal_stop": opt, "_computed": True,
        })
    except Exception:  # noqa: BLE001 — calculator must still return a partial rec
        pass
    return rec


def _candidate_stops(rec: dict, entry: float, bars5: list[dict],
                     bars1h: list[dict]) -> list[dict]:
    """All support levels below `entry`, de-duped, each tagged with its basis.

    The menu the PM asked for: FIB / MA / DSL / coil-region + swing lows across
    daily (AQE structural_levels), 5-day hourly, and live 5-min.
    """
    seen: set[float] = set()
    out: list[dict] = []

    def add(basis, p):
        p = _num(p)
        if p is None or p >= entry or p <= 0:
            return
        r = round(float(p), 2)
        if r in seen:
            return
        seen.add(r)
        out.append({"basis": basis, "price": r})

    add("dsl_stop", rec.get("dsl_stop"))
    add("fib_618", rec.get("fib_618"))
    add("fib_786", rec.get("fib_786"))
    for w in (20, 50, 100, 200):
        add(f"ma_{w}", rec.get(f"ma_{w}"))
    for lvl in (rec.get("structural_levels") or []):
        if isinstance(lvl, dict):
            add(f"aqe_{lvl.get('type', 'struct')}", lvl.get("price"))
    for sl in _pivot_lows(bars1h, entry):
        add("hourly_swing_low", sl["price"])
    for sl in _pivot_lows(bars5, entry):
        add("intraday_swing_low", sl["price"])
    return out


def _tp2_ref(rec: dict, entry: float, fallback_risk: float) -> float:
    above = sorted(t["price"] for t in (rec.get("structural_targets") or [])
                   if isinstance(t, dict) and _num(t.get("price")) and t["price"] > entry)
    if len(above) >= 2:
        return above[1]
    if above:
        return above[0]
    return round(entry + 2 * fallback_risk, 2)


def price_ticker(ticker: str, rec: dict | None, bars5, bars1h, daily_df,
                 regime=None, risk_budget: float = C.RISK_BUDGET) -> dict:
    """Compute a full bracket for one ticker. Never blanks (given price data)."""
    in_universe = rec is not None
    rec = ensure_levels(ticker, rec, daily_df)
    b5 = normalize_bars(bars5)
    b1 = normalize_bars(bars1h)

    # Live price: latest 5-min close → else latest daily close → else rec.entry.
    price = (b5[-1]["c"] if b5 else
             (float(daily_df["close"].iloc[-1]) if daily_df is not None and len(daily_df)
              else _num(rec.get("entry"))))
    if price is None:
        return {"ticker": ticker, "error": "no price data"}
    entry = round(float(price), 2)

    atr14 = _num(rec.get("atr_14d")) or _atr_from_df(daily_df, 14) or round(entry * 0.02, 2)
    ceiling = C.regime_stop_ceiling(regime)

    # 5-day reference range (daily preferred, else hourly).
    rng = None
    if daily_df is not None and len(daily_df) >= 1:
        tail = daily_df.tail(5)
        rng = {"high": round(float(tail["high"].max()), 2),
               "low": round(float(tail["low"].min()), 2)}
    elif b1:
        rng = {"high": round(max(x["h"] for x in b1[-35:]), 2),
               "low": round(min(x["l"] for x in b1[-35:]), 2)}

    # ── operative stop = the best point among FIB/MA/DSL/swing candidates ──
    cands = _candidate_stops(rec, entry, b5, b1)
    tp2_ref = _tp2_ref(rec, entry, atr14)
    scored = []
    for c in cands:
        risk = entry - c["price"]
        if risk <= 0:
            continue
        atr_ratio = round(risk / atr14, 2) if atr14 else None
        rr_tp2 = round((tp2_ref - entry) / risk, 2) if risk else None
        stop_pct = round(risk / entry * 100, 2)
        scored.append({**c, "risk": round(risk, 2), "atr_ratio": atr_ratio,
                       "rr_tp2": rr_tp2, "stop_pct": stop_pct,
                       "gate_atr": bool(atr_ratio and atr_ratio >= C.MIN_ATR_RATIO),
                       "gate_rr": bool(rr_tp2 and rr_tp2 >= C.MIN_RR_TP2),
                       "within_ceiling": stop_pct <= ceiling})

    def _pick(pred):
        ok = [s for s in scored if pred(s)]
        return max(ok, key=lambda s: s["price"]) if ok else None  # tightest

    op = (_pick(lambda s: s["gate_atr"] and s["gate_rr"] and s["within_ceiling"])
          or _pick(lambda s: s["gate_atr"] and s["within_ceiling"])
          or _pick(lambda s: s["atr_ratio"] and s["atr_ratio"] >= 0.5))
    if op is None:                       # nothing sensible below entry — 1×ATR floor
        risk = round(atr14, 2) or round(entry * 0.02, 2)
        op = {"basis": "atr_fallback", "price": round(entry - risk, 2),
              "risk": risk, "atr_ratio": 1.0,
              "rr_tp2": round((tp2_ref - entry) / risk, 2) if risk else None,
              "stop_pct": round(risk / entry * 100, 2),
              "gate_atr": True, "gate_rr": None, "within_ceiling": (risk / entry * 100) <= ceiling}

    risk = op["risk"]
    coil = round(op["price"] + atr14, 2)          # 1×ATR pullback entry alternative
    # ── TP ladder: mechanical R-multiples (always present) + structural refs ──
    tp1 = round(entry + 1 * risk, 2)
    tp2 = round(entry + 2 * risk, 2)
    tp3 = round(entry + 3 * risk, 2)
    struct_tps = [{"type": t.get("type"), "price": t["price"],
                   "rr": round((t["price"] - entry) / risk, 2)}
                  for t in (rec.get("structural_targets") or [])
                  if isinstance(t, dict) and _num(t.get("price")) and t["price"] > entry][:4]
    shares = int(math.floor(risk_budget / risk)) if risk else 0

    mom = intraday_momentum(bars5, rec) if b5 else {"ims": None, "state": "NO_INTRADAY",
                                                    "components": {}}

    # Full Elder Context (Instruction v1.1) — hourly VWAP/volume + daily VCP.
    elder_ctx = None
    try:
        from src.engines.elder_context import compute_elder_context
        _daily_list = ([] if daily_df is None else [
            {"date": str(d), "open": o, "high": h, "low": low, "close": c, "volume": v}
            for d, o, h, low, c, v in zip(
                daily_df["date"].astype(str), daily_df["open"], daily_df["high"],
                daily_df["low"], daily_df["close"], daily_df["volume"])])
        _res = (rec.get("structural_targets") or [{}])
        _res = _res[0].get("price") if _res and isinstance(_res[0], dict) else None
        elder_ctx = compute_elder_context(
            rec.get("elder_5d"), bars1h, _daily_list, resistance_price=_res)
    except Exception:  # noqa: BLE001
        elder_ctx = None

    notes = []
    if not op.get("within_ceiling"):
        notes.append(f"stop {op['stop_pct']}% exceeds the {ceiling}% regime ceiling")
    if op.get("gate_rr") is False:
        notes.append("R:R to structural TP2 < 2.0 at this stop")
    if rec.get("_computed"):
        notes.append("levels computed live from daily bars (not in AQE universe)")

    return {
        "ticker": ticker,
        "in_universe": in_universe,
        "price": entry,
        "atr_14d": round(atr14, 2),
        "range_5d": rng,
        "entry": entry,
        "coil_entry": coil,
        "operative_stop": op,
        "risk": risk,
        "shares": shares,
        "tp": {"tp1": tp1, "tp2": tp2, "tp3": tp3},
        "rr_tp2": 2.0,
        "structural_tps": struct_tps,
        "candidates": sorted(scored, key=lambda s: -s["price"]),
        "momentum": mom.get("components", {}),
        "ims": mom.get("ims"),
        "state": mom.get("state"),
        "elder_context": elder_ctx,
        "elder_pattern": (elder_ctx or {}).get("elder_pattern") if elder_ctx else None,
        "notes": notes,
        "ibkr_spec": {
            "symbol": ticker, "action": "BUY", "order_type": "LMT",
            "entry": entry, "stop": op["price"], "take_profit": tp2,
            "quantity": shares,
            "note": "Calculated levels — recommend-only; you/the AIC decide.",
        },
    }
