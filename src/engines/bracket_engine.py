"""Bracketing Engine — the SINGLE source of truth for every stop/target in AQE.

PM ruling (2026-07-07): one engine owns the bracket. The export, alerts, Pricer,
charts, and signal ledger all reference THIS output — same data, same tables, no
re-derivation anywhere. Mechanical DSL/TP is retired; there is only the structural
bracket.

Design
------
Structural levels (support / resistance / MA / Fib) are FIXED from the daily bars.
What varies is the **price** you measure against:
  • daily run  → price = FMP close-of-day  (the EOD watchlist snapshot)
  • live pull  → price = FMP 15-min quote   (chart / bracket / entry)
So `compute_bracket(levels, ma, regime, price, price_source)` takes the price in and
derives risk + R:R against it. Structural levels don't move; the bracket re-prices.

Stop rule (PM: "tightest valid")
  Among the structural support candidates BELOW price that pass all 3 gates, take the
  one CLOSEST to price (highest price = smallest risk). The gates are the tie-breaker
  that makes "closest support" well-defined.

Targets (PM: closest structural resistance, Fibs preferred)
  Resistance pivots + prior swing high + Fib measured-move extensions ABOVE price,
  nearest-first, near-equal levels collapsed (resistance label wins ties).

3 gates (Charter §4.2), all measured STRUCTURALLY (no mechanical inputs):
  1. atr_dist ≥ 1.0            (stop at least 1×ATR away — not noise)
  2. rr ≥ 2.0                  (R:R to the structural TP2 ≥ 2:1)
  3. risk_pct ≤ regime ceiling (GREEN 12 / YELLOW 8 / ORANGE 6 / RED 4 %)

Un-bracketable → valid=False + invalid_reason; the feed shows "no valid bracket"
(no mechanical fallback). Every distance is ATR-relative (`*_atr` fields) so the AIC
reads risk in ATRs, not raw USD.
"""
from __future__ import annotations

# Charter §4.2 regime-calibrated stop-% ceiling.
REGIME_STOP_CEILINGS: dict[str, float] = {
    "GREEN": 12.0, "YELLOW": 8.0, "ORANGE": 6.0, "RED": 4.0,
}
# Gate thresholds.
ATR_FLOOR = 1.0
RR_MIN = 2.0
TARGET_COLLAPSE_ATR = 0.5     # near-equal targets within 0.5×ATR collapse


def regime_stop_ceiling(regime_level: str | None) -> float:
    return REGIME_STOP_CEILINGS.get((regime_level or "GREEN").upper(), 12.0)


def classify_vix_regime(vix: float) -> str:
    """VIX -> GREEN/YELLOW/ORANGE/RED, the input to regime_stop_ceiling above.

    Moved here 2026-08-13 from src/analyzer/ptrs.py, itself retired the same
    day: after PTRS and the disposition ceiling were both removed earlier
    that day, the file existed only to hold this one function — "no point
    keeping one .py for essentially one data pull" (PM). This is the
    function's one real structural consumer, so it lives beside it now
    instead of behind a single-purpose module."""
    if vix > 30:
        return "RED"
    elif vix > 25:
        return "ORANGE"
    elif vix > 18:
        return "YELLOW"
    else:
        return "GREEN"


def _num(*vals) -> bool:
    for v in vals:
        try:
            if v is None or v != v:   # None or NaN
                return False
            float(v)
        except (TypeError, ValueError):
            return False
    return True


# ---------------------------------------------------------------------------
# Structural targets (resistance / prior high / Fib extensions) above price
# ---------------------------------------------------------------------------
def _candidate_targets(levels: dict, price: float, atr14: float) -> list[dict]:
    """Structural resistance above `price`, nearest-first, near-equal collapsed.
    Resistance pivots win de-dup ties over Fib extensions."""
    fib = levels.get("fib") or {}
    exts = fib.get("extensions") or {}
    raw: list[dict] = []

    def _add(typ: str, p, date: str | None = None) -> None:
        if not _num(p) or float(p) <= price:      # a long's target sits above price
            return
        raw.append({"type": typ, "price": round(float(p), 2), "date": date})

    for r in (levels.get("resistance") or []):
        if isinstance(r, dict):
            _add("resistance", r.get("price"), r.get("date"))
    _add("prior_high", fib.get("swing_high"))
    _add("fib_1272", exts.get("1.272"))
    _add("fib_1618", exts.get("1.618"))
    _add("fib_2000", exts.get("2.0"))
    _add("fib_2618", exts.get("2.618"))

    raw.sort(key=lambda x: x["price"])
    gap = atr14 * TARGET_COLLAPSE_ATR if _num(atr14) and atr14 > 0 else 0.0
    out: list[dict] = []
    for t in raw:
        if out and gap > 0 and (t["price"] - out[-1]["price"]) < gap:
            continue                               # collapse near-equal
        if t.get("date") is None:
            t.pop("date", None)
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# Structural stop candidates (swing lows / MA cluster / MA / Fib) below price
# ---------------------------------------------------------------------------
def _candidate_stops(levels: dict, ma: dict | None, price: float,
                     atr14: float, tp2_ref: float | None,
                     ceiling: float) -> list[dict]:
    """Every structural support below `price`, each gated against the STRUCTURAL
    TP2 reference. NO mechanical dsl_stop candidate — that vocabulary is retired."""
    fib = levels.get("fib") or {}
    rets = fib.get("retracements") or {}
    seen: set[float] = set()
    cands: list[dict] = []

    def _add(typ: str, p, date: str | None = None) -> None:
        if not _num(p):
            return
        risk = price - float(p)
        if risk <= 0:                              # stop must sit below price
            return
        p2 = round(float(p), 2)
        if p2 in seen:                             # same shelf, earlier label wins
            return
        seen.add(p2)
        atr_dist = round(risk / atr14, 2) if atr14 > 0 else None
        risk_pct = round(risk / price * 100, 2) if price else 99.0
        rr = round((tp2_ref - price) / risk, 2) if _num(tp2_ref) else None
        regime_ok = bool(risk_pct <= ceiling)
        valid = bool(atr_dist is not None and atr_dist >= ATR_FLOOR
                     and rr is not None and rr >= RR_MIN and regime_ok)
        item = {"type": typ, "price": p2, "risk": round(risk, 2),
                "atr_dist": atr_dist, "rr": rr, "risk_pct": risk_pct,
                "regime_valid": regime_ok, "valid": valid}
        if date:
            item["date"] = date
        cands.append(item)

    _add("swing_low", fib.get("swing_low"), fib.get("swing_low_date"))
    for i, sl in enumerate(levels.get("swing_lows") or [], 1):
        if isinstance(sl, dict):
            _add(f"swing_low_{i}", sl.get("price"), sl.get("date"))
    _add("fib_618", rets.get("0.618"))
    _add("fib_786", rets.get("0.786"))
    ma20, ma50 = (ma or {}).get(20), (ma or {}).get(50)
    if _num(ma20, ma50) and abs(ma20 - ma50) <= atr14:
        _add("ma_cluster", min(ma20, ma50))        # MA20/50 confluence shelf
    for w in (20, 50, 100, 200):
        _add(f"ma{w}", (ma or {}).get(w))
    return cands


# ---------------------------------------------------------------------------
# The canonical bracket
# ---------------------------------------------------------------------------
def compute_bracket(levels: dict, ma: dict | None, regime_level: str | None,
                    price: float, price_source: str = "eod_close") -> dict:
    """THE bracket for a ticker at `price`. Returns the canonical object every
    consumer reads. Never raises — a bad input degrades to valid=False.

    `levels` = the per-ticker structural bundle (fib retracements/extensions +
    swing_low(s) + resistance), e.g. from levels.levels_for_ticker(). `ma` = {period:
    value}. `price` = FMP EOD close (daily) or 15-min quote (live).
    """
    atr14 = levels.get("atr14")
    ceiling = regime_stop_ceiling(regime_level)
    out: dict = {
        "price": round(float(price), 2) if _num(price) else None,
        "price_source": price_source,
        "stop": None, "stop_type": None, "stop_atr_dist": None, "stop_date": None,
        "risk": None, "risk_pct": None,
        "targets": [], "rr": None,
        "rr_tp1": None, "rr_tp2": None, "rr_tp3": None,
        # Where a stop WOULD sit if there is no structural level = 1×ATR below
        # price. This is the reference for un-bracketable names (valid=false) —
        # NOT the operative stop when a structural bracket exists.
        "atr_fallback_stop": None,
        "valid": False, "invalid_reason": None,
        "candidates": [], "regime_ceiling_pct": ceiling,
    }
    if not _num(price, atr14) or atr14 <= 0 or price <= 0:
        out["invalid_reason"] = "no valid bracket — missing price/ATR"
        return out

    # ATR-fallback stop = 1×ATR below price. Present on every bracket; it's the
    # reference stop to use ONLY when valid=false (no structural level exists).
    out["atr_fallback_stop"] = round(price - atr14, 2)

    # 1) Structural targets above price (fixed from bars).
    targets = _candidate_targets(levels, price, atr14)
    if not targets:
        out["invalid_reason"] = "no valid bracket — no structural resistance above price"
        return out
    # TP2 reference for the R:R gate = the 2nd structural target (else the 1st).
    tp2_ref = targets[1]["price"] if len(targets) >= 2 else targets[0]["price"]

    # 2) Structural stop candidates below price, gated vs the structural TP2.
    cands = _candidate_stops(levels, ma, price, atr14, tp2_ref, ceiling)
    out["candidates"] = cands
    valids = [c for c in cands if c["valid"]]
    if not valids:
        out["targets"] = [
            {**t, "atr_dist": round((t["price"] - price) / atr14, 2)} for t in targets
        ]
        out["invalid_reason"] = (
            "no valid bracket — no structural support passes the 3 gates "
            "(atr≥1.0, rr≥2.0, risk%≤regime ceiling)")
        return out

    # 3) Optimal stop = tightest valid (closest to price).
    best = max(valids, key=lambda c: c["price"])
    risk = round(price - best["price"], 2)
    out["stop"] = best["price"]
    out["stop_type"] = best["type"]
    out["stop_atr_dist"] = best["atr_dist"]
    out["stop_date"] = best.get("date")     # pivot date when the stop is swing-based
    out["risk"] = risk
    out["risk_pct"] = best["risk_pct"]

    # 4) Re-price every target's R against the structural risk + tag ATR distance.
    #    The first three carry a TP1/TP2/TP3 label so the AIC reads R:R per target
    #    directly (r = (target − price) / risk = the reward:risk to that level).
    _tp_labels = {0: "TP1", 1: "TP2", 2: "TP3"}
    out["targets"] = [
        {"type": t["type"], "price": t["price"],
         "tp": _tp_labels.get(i),
         "r": round((t["price"] - price) / risk, 2) if risk > 0 else None,
         "atr_dist": round((t["price"] - price) / atr14, 2),
         **({"date": t["date"]} if t.get("date") else {})}
        for i, t in enumerate(targets)
    ]
    # 5) R:R to each of the first three structural targets (offloads the calc for
    #    the AIC). rr == rr_tp2 (the headline). None when that target doesn't exist.
    def _rr_to(i):
        return out["targets"][i]["r"] if i < len(out["targets"]) else None
    out["rr_tp1"] = _rr_to(0)
    out["rr_tp2"] = _rr_to(1)
    out["rr_tp3"] = _rr_to(2)
    out["rr"] = out["rr_tp2"] if out["rr_tp2"] is not None else out["rr_tp1"]
    out["valid"] = True
    return out


def stamp_bracket_volume(bracket: dict | None, dates, volumes) -> None:
    """Volume-validate a bracket's dated levels IN PLACE (TV-analysis Phase 4,
    the BigBeluga high-volume-pivot rule): a level DEFENDED on high volume is a
    stronger level. Adds `vol_ratio` (that level's pivot-bar volume / trailing
    20-bar average as of that date) and `vol_validated` (ratio >= 1.2) to every
    dated item in `bracket["targets"]`, and `stop_vol_ratio`/
    `stop_vol_validated` when `bracket["stop_date"]` is set.

    `dates`/`volumes` are the ticker's own daily bars (ascending, aligned) —
    the SAME data every caller already has, so this stays a pure function with
    no panel/lookup dependency. Single source of truth: both the daily-list
    build (drive_sync.py, looping many tickers via a panel groupby) and the
    ad-hoc scorer (adhoc.py, one ticker's own fetched bars) call this same
    function — never duplicate the ratio math.

    Data only — the 3 charter gates are unchanged. No-op on missing/malformed
    input; never raises.
    """
    if not bracket or dates is None or volumes is None:
        return
    try:
        import pandas as pd
        vs = pd.Series(volumes).astype(float).reset_index(drop=True)
        ds = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
        if len(vs) == 0 or len(ds) == 0:
            return
        avg = vs.rolling(20).mean()
        dix = {str(d.date()): j for j, d in enumerate(ds)}

        def _ratio_at(dt):
            j = dix.get(dt)
            if j is None:
                return None
            a = avg.iloc[j]
            if a and a == a and a > 0:
                return round(float(vs.iloc[j]) / float(a), 2)
            return None

        for item in (bracket.get("targets") or []):
            rt = _ratio_at(item.get("date"))
            if rt is not None:
                item["vol_ratio"] = rt
                item["vol_validated"] = bool(rt >= 1.2)
        srt = _ratio_at(bracket.get("stop_date"))
        if srt is not None:
            bracket["stop_vol_ratio"] = srt
            bracket["stop_vol_validated"] = bool(srt >= 1.2)
    except Exception:  # noqa: BLE001 — data enrichment, never blocks the caller
        pass
