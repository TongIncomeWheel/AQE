"""§2.3 CTA flow — replicated, because the note itself cannot be bought.

The proprietary weekly (GS / Nomura style) is not obtainable through any feed we
have. The *method* behind it is public and simple, and that is the part that
matters: what people actually trade off those notes is not the AUM estimate, it
is **the level at which CTAs flip**. That level is a deterministic function of
the model, not of anyone's book, so we can compute it exactly.

Three public components, equally weighted:

  * Moskowitz-Ooi-Pedersen (2012) time-series momentum at 2 / 6 / 12 months,
    each vol-normalised so a move counts for what it is worth in that market's
    own units rather than in percent.
  * Faber (2007) GTAA — price versus the 10-month (~200 session) average.

Each component is a z-score of the move against what that market's own
volatility would produce over that horizon, saturating at
`CTA_SIGNAL_SCALE_SIGMA`. So `signal = +1` does not mean "up"; it means "up by
about two sigma over the lookback, which is as trending as this model reads".

**The honest caveat, which must travel with every number this module emits:** our
positioning estimate will not match Goldman's. The direction and the flip levels
will be close, because the models are near-identical and the flip level is
arithmetic. The AUM weighting is a guess, and GS additionally surveys real books,
which we cannot do.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import spec as S

# How many sigma of trend saturates a component at +/-1. DERIVED: at 1 sigma
# nearly every drifting market would read "extreme" and Crown's 0.75 threshold
# would fire constantly; 2 sigma makes 0.75 mean ~1.5 sigma, a real trend.
CTA_SIGNAL_SCALE_SIGMA = 2.0


# ── the replicated universe ───────────────────────────────────────────────
# `fmp` is the continuous front-month series on FMP (verified symbols).
# `cot` is the CFTC contract market code, so positioning joins to the same row.
# Crude maps to the ICE Europe WTI contract: it carries ~875k open interest in the
# futures-only report, and the NYMEX flagship is simply not published there.
# `fallback` is an ETF that tracks the same exposure. It exists because several
# treasury-futures symbols are plan-gated on our FMP tier (ZNUSD returns ACCESS
# DENIED), and silently DROPPING four markets would be worse than proxying them:
# `flip_risk` is extremes / n_markets, so losing the whole rates complex changes
# the denominator and quietly re-rates every reading. A proxied market is always
# labelled `via_fallback` so nobody mistakes IEF for the 10-year future.
#
# Symbols verified against FMP's own commodities-list on 2026-08-10. Three were
# wrong on the first pass: corn, soybeans and wheat are quoted in CENTS and carry
# a USX suffix, and there is no ZWUSD at all — FMP's wheat is KEUSX.
MARKETS: dict[str, dict] = {
    "ES":  {"fmp": "ESUSD", "label": "S&P 500",      "sector": "equity", "cot": "13874A", "fallback": "SPY"},
    "NQ":  {"fmp": "NQUSD", "label": "Nasdaq 100",   "sector": "equity", "cot": "209742", "fallback": "QQQ"},
    "YM":  {"fmp": "YMUSD", "label": "Dow",          "sector": "equity", "cot": "124603", "fallback": "DIA"},
    # Only the MICRO Russell 2000 appears in the futures-only report; the full
    # -size contract is not published there, so this is the best available proxy.
    "RTY": {"fmp": "RTYUSD", "label": "Russell 2000", "sector": "equity", "cot": "239747", "fallback": "IWM"},
    "ZN":  {"fmp": "ZNUSD", "label": "UST 10Y note", "sector": "rates",  "cot": "043602", "fallback": "IEF"},
    "ZB":  {"fmp": "ZBUSD", "label": "UST bond",     "sector": "rates",  "cot": "020601", "fallback": "TLT"},
    "ZF":  {"fmp": "ZFUSD", "label": "UST 5Y note",  "sector": "rates",  "cot": "044601", "fallback": "IEI"},
    "ZT":  {"fmp": "ZTUSD", "label": "UST 2Y note",  "sector": "rates",  "cot": "042601", "fallback": "SHY"},
    "CL":  {"fmp": "CLUSD", "label": "WTI crude",    "sector": "energy", "cot": "067411", "fallback": "USO"},
    "BZ":  {"fmp": "BZUSD", "label": "Brent crude",  "sector": "energy", "cot": None,     "fallback": "BNO"},
    "NG":  {"fmp": "NGUSD", "label": "Natural gas",  "sector": "energy", "cot": "023651", "fallback": "UNG"},
    "GC":  {"fmp": "GCUSD", "label": "Gold",         "sector": "metals", "cot": "088691", "fallback": "GLD"},
    "SI":  {"fmp": "SIUSD", "label": "Silver",       "sector": "metals", "cot": "084691", "fallback": "SLV"},
    "HG":  {"fmp": "HGUSD", "label": "Copper",       "sector": "metals", "cot": "085692", "fallback": "CPER"},
    "DX":  {"fmp": "DXUSD", "label": "US dollar",    "sector": "fx",     "cot": "098662", "fallback": "UUP"},
    "ZC":  {"fmp": "ZCUSX", "label": "Corn",         "sector": "ags",    "cot": "002602", "fallback": "CORN"},
    "ZS":  {"fmp": "ZSUSX", "label": "Soybeans",     "sector": "ags",    "cot": "005602", "fallback": "SOYB"},
    "ZW":  {"fmp": "KEUSX", "label": "Wheat",        "sector": "ags",    "cot": "001602", "fallback": "WEAT"},
}


# ── primitives ────────────────────────────────────────────────────────────

def _closes(bars) -> np.ndarray:
    if bars is None or len(bars) == 0:
        return np.array([], dtype=float)
    c = pd.to_numeric(pd.DataFrame(bars)["close"], errors="coerce").to_numpy(dtype=float)
    return c[np.isfinite(c)]


def annualised_vol(closes: np.ndarray, window: int = S.CTA_VOL_WINDOW) -> float | None:
    """Realised vol from log returns, annualised. None if too little history."""
    if len(closes) < window + 1:
        return None
    r = np.diff(np.log(closes[-(window + 1):]))
    sd = float(np.std(r, ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return None
    return sd * np.sqrt(S.TRADING_DAYS)


def _component(move: float, vol_ann: float, horizon_sessions: int) -> float:
    """One vol-normalised trend component, saturating at +/-1.

    `move` is a simple return. The denominator is what this market's own vol
    would typically produce over that many sessions — which is why a 5% move in
    ZN and a 5% move in NG are not the same signal.
    """
    expected = vol_ann * np.sqrt(horizon_sessions / S.TRADING_DAYS)
    if expected <= 0:
        return 0.0
    z = move / expected
    return float(np.clip(z / CTA_SIGNAL_SCALE_SIGMA, -1.0, 1.0))


def market_signal(bars, *, lookbacks=S.CTA_LOOKBACKS) -> dict:
    """The blended trend signal for one market, with its components shown.

    Returns signal in [-1, +1], the four components, realised vol, and the
    vol-targeted weight a managed-futures book would carry. `None` signal when
    history is too short — never a fabricated zero, which would read as
    "flat" rather than "unknown".
    """
    c = _closes(bars)
    need = max(max(lookbacks), S.CTA_FABER_SMA) + 1
    if len(c) < need:
        return {"signal": None, "components": {}, "vol_ann": None, "weight": None,
                "bars": int(len(c)),
                "reason": f"need {need} bars, have {len(c)}"}

    vol = annualised_vol(c)
    if vol is None:
        return {"signal": None, "components": {}, "vol_ann": None, "weight": None,
                "bars": int(len(c)), "reason": "realised vol unavailable"}

    px = float(c[-1])
    comps: dict[str, float] = {}
    for L in lookbacks:
        comps[f"tsmom_{L}"] = _component(px / float(c[-1 - L]) - 1.0, vol, L)
    sma = float(np.mean(c[-S.CTA_FABER_SMA:]))
    comps["faber_200"] = _component(px / sma - 1.0, vol, S.CTA_FABER_SMA)

    signal = float(np.clip(np.mean(list(comps.values())), -1.0, 1.0))
    weight = float(np.clip(S.CTA_VOL_TARGET / vol, 0.0, S.CTA_MAX_LEVERAGE)) * signal

    return {
        "signal": round(signal, 4),
        "components": {k: round(v, 4) for k, v in comps.items()},
        "vol_ann": round(vol, 4),
        "weight": round(weight, 4),
        "price": round(px, 4),
        "sma_200": round(sma, 4),
        "bars": int(len(c)),
        "reason": None,
    }


# ── flip levels: the part worth having ────────────────────────────────────

def _signal_at(c: np.ndarray, price: float, horizon: int,
               lookbacks=S.CTA_LOOKBACKS, vol: float | None = None) -> float:
    """The blended signal if price were `price` and stayed there for `horizon`
    more sessions.

    Volatility is held at today's reading rather than re-projected. Projecting
    it would be a second guess stacked on the first, and it moves the answer far
    less than the price path does.
    """
    n = len(c)
    if vol is None:
        vol = annualised_vol(c) or 0.0
    if vol <= 0:
        return 0.0
    vals = []
    for L in lookbacks:
        idx = n + horizon - 1 - L
        if idx < 0 or idx >= n:
            continue                       # anchor would be a projected bar
        vals.append(_component(price / float(c[idx]) - 1.0, vol, L))
    take = S.CTA_FABER_SMA - horizon
    if 0 < take <= n:
        sma = (horizon * price + float(np.sum(c[n - take:]))) / S.CTA_FABER_SMA
        vals.append(_component(price / sma - 1.0, vol, S.CTA_FABER_SMA))
    if not vals:
        return 0.0
    return float(np.clip(np.mean(vals), -1.0, 1.0))


def flip_level(bars, horizon: int = 1, *, lookbacks=S.CTA_LOOKBACKS) -> dict | None:
    """The price at which this market's blended signal crosses zero, `horizon`
    sessions from now.

    "CTAs turn seller of ES below X" — this is X. Bisection is valid because
    every component is monotone increasing in price.
    """
    c = _closes(bars)
    if len(c) < S.CTA_MIN_HISTORY:
        return None
    vol = annualised_vol(c)
    if vol is None:
        return None
    spot = float(c[-1])

    lo, hi = spot * 0.30, spot * 3.00
    s_lo = _signal_at(c, lo, horizon, lookbacks, vol)
    s_hi = _signal_at(c, hi, horizon, lookbacks, vol)
    if s_lo > 0 or s_hi < 0:
        # The signal saturates before crossing inside a plausible price range.
        # Saying so beats reporting a clamped bound as if it were a level.
        return {"horizon": horizon, "level": None, "spot": round(spot, 4),
                "distance_pct": None, "current_sign": 1 if s_hi > 0 else -1,
                "reason": "no zero-crossing within 0.3x-3x spot"}

    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _signal_at(c, mid, horizon, lookbacks, vol) < 0:
            lo = mid
        else:
            hi = mid
    level = (lo + hi) / 2.0
    cur = _signal_at(c, spot, horizon, lookbacks, vol)

    return {
        "horizon": horizon,
        "level": round(level, 4),
        "spot": round(spot, 4),
        "distance_pct": round((level / spot - 1.0) * 100.0, 2),
        "direction": "sell_below" if cur >= 0 else "buy_above",
        "current_sign": 1 if cur >= 0 else -1,
        "reason": None,
    }


def market_report(key: str, bars) -> dict:
    """Everything Crown's §2.3 wants for one market: signal + the flip table."""
    meta = MARKETS.get(key, {})
    rep = market_signal(bars)
    rep["market"] = key
    rep["label"] = meta.get("label", key)
    rep["sector"] = meta.get("sector")
    rep["flips"] = [f for f in (flip_level(bars, h) for h in S.CTA_FLIP_HORIZONS)
                    if f is not None]
    return rep


# ── §5 cta_flow_analysis, transcribed ─────────────────────────────────────

def cta_flow_analysis(signals: dict[str, float],
                      flip_threshold: float = S.CTA_FLIP_THRESHOLD) -> dict:
    """Kernel §5, transcribed. Aggregate bias, crowding, and the size dial.

    `flip_risk` is the SHARE of markets sitting at an extreme — Crown's point is
    that a crowded trend is a fragile one, so a high reading CUTS size even when
    the bias is clean and directional.
    """
    signals = {k: float(v) for k, v in (signals or {}).items() if v is not None}
    if not signals:
        return {"overall_bias": "neutral", "flip_risk": 0.0,
                "high_conviction_assets": [], "size_adjustment": S.CTA_SIZE_NEUTRAL,
                "n_markets": 0,
                "rationale": "No CTA signals available"}

    values = list(signals.values())
    avg = sum(values) / len(values)
    extreme_count = sum(1 for v in values if abs(v) >= flip_threshold)

    if avg > S.CTA_BIAS_EPS:
        bias = "risk_on"
    elif avg < -S.CTA_BIAS_EPS:
        bias = "risk_off"
    else:
        bias = "mixed" if extreme_count > 0 else "neutral"

    flip_risk = extreme_count / max(len(values), 1)
    high_conviction = sorted(
        (k for k, v in signals.items() if abs(v) >= flip_threshold),
        key=lambda k: -abs(signals[k]))

    if flip_risk > S.CTA_FLIP_RISK_HI:
        size_adj = S.CTA_SIZE_CROWDED
    elif bias in ("risk_on", "risk_off") and flip_risk < S.CTA_FLIP_RISK_LO:
        size_adj = S.CTA_SIZE_CLEAN_TREND
    else:
        size_adj = S.CTA_SIZE_NEUTRAL

    return {
        "overall_bias": bias,
        "avg_signal": round(float(avg), 4),
        "flip_risk": round(float(flip_risk), 4),
        "high_conviction_assets": high_conviction,
        "size_adjustment": float(size_adj),
        "n_markets": len(values),
        "rationale": (f"Avg={avg:.2f} | Extremes={extreme_count}/{len(values)} | "
                      f"Flip risk={flip_risk:.2f}"),
    }


def analyse(bars_by_market: dict[str, object]) -> dict:
    """Full CTA read: per-market reports, the aggregate, and the flip table."""
    reports = {k: market_report(k, b) for k, b in (bars_by_market or {}).items()}
    signals = {k: r["signal"] for k, r in reports.items() if r.get("signal") is not None}
    flow = cta_flow_analysis(signals)

    missing = sorted(k for k, r in reports.items() if r.get("signal") is None)
    flow["markets_scored"] = sorted(signals)
    flow["markets_missing"] = missing
    if missing:
        # Loud, not silent: a thin universe changes what flip_risk MEANS.
        flow["rationale"] += f" | no signal for {', '.join(missing)}"

    by_sector: dict[str, list[float]] = {}
    for k, r in reports.items():
        if r.get("signal") is None:
            continue
        by_sector.setdefault(MARKETS.get(k, {}).get("sector", "other"), []).append(r["signal"])
    flow["sector_bias"] = {s: round(float(np.mean(v)), 4) for s, v in sorted(by_sector.items())}

    return {"flow": flow, "markets": reports}
