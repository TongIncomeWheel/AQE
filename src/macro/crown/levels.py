"""Key levels — and most of them are not prices.

Crown's letter puts a levels table near the front: call wall, gamma flip,
Friday's close, hedge wall, put wall. Every row is an SPX price, and each says
what happens if the market gets there.

That table is worth copying, but stopping at prices would waste what this layer
already computes. The levels that decide the regime here are mostly **not**
prices at all:

  * the breadth ratio's 12-month range — the level that decides whether a
    broadening wave is early or tired
  * the volatility gap's own percentile bands — the level at which "the index
    is hiding something" becomes true
  * the trend models' flip prices across eighteen markets — mechanical selling
    switches on there, in instruments other than the S&P
  * implied correlation — the level below which selection pays and index
    exposure does not

So this builds ONE table across all of them, in the same shape: what it is,
where it is now, where the level sits, how far away, and **what changes if it
breaks**. A reader should be able to scan one list and see every line in the
sand, whether it is quoted in dollars, vol points or a percentile.

Rows are sorted by distance, so the thing about to happen is at the top.
"""

from __future__ import annotations

from . import spec as S


def _row(kind, what, now, level, unit, if_it_breaks, *, distance_pct=None,
         source=None, quotable=True):
    return {"kind": kind, "what": what, "now": now, "level": level,
            "unit": unit, "distance_pct": distance_pct,
            "if_it_breaks": if_it_breaks, "source": source,
            "quotable_as_contract": quotable}


def _pct_away(now, level):
    try:
        if now and level and float(now) != 0:
            return round((float(level) / float(now) - 1.0) * 100.0, 2)
    except (TypeError, ValueError):
        pass
    return None


def price_levels(crown: dict) -> list[dict]:
    """Dealer-positioning levels — the ones Crown's own table carries."""
    rows = []
    for sym, prof in ((crown.get("gamma") or {}).get("underlyings") or {}).items():
        spot = prof.get("spot")
        flip = prof.get("gamma_flip")
        if flip:
            pos = prof.get("regime") == "POSITIVE"
            rows.append(_row(
                "dealer positioning", f"{sym} gamma flip", spot, flip, "price",
                ("Below here dealers stop damping moves and start amplifying "
                 "them, so intraday swings widen."
                 if pos else
                 "Above here dealers stop amplifying moves and start damping "
                 "them, so swings should settle."),
                distance_pct=prof.get("flip_distance_pct")))
        cw = prof.get("call_wall") or {}
        if cw.get("strike"):
            rows.append(_row(
                "dealer positioning", f"{sym} call wall", spot, cw["strike"],
                "price",
                "The heaviest call positioning above the market. Rallies into "
                "it tend to meet dealer selling unless momentum forces through.",
                distance_pct=_pct_away(spot, cw["strike"])))
        pw = prof.get("put_wall") or {}
        if pw.get("strike"):
            rows.append(_row(
                "dealer positioning", f"{sym} put wall", spot, pw["strike"],
                "price",
                "The heaviest put positioning below the market. It usually acts "
                "as support, and losing it removes the cushion.",
                distance_pct=_pct_away(spot, pw["strike"])))
    return rows


def trend_flip_levels(crown: dict, limit: int | None = None) -> list[dict]:
    """Where systematic money changes side, across every market we read."""
    fresh = ((crown.get("freshness") or {}).get("cta_markets") or {})
    rows = []
    for key, m in (crown.get("cta_markets") or {}).items():
        if m.get("signal") is None:
            continue
        src = (fresh.get(key) or {}).get("via", "unknown")
        for f in (m.get("flips") or []):
            if f.get("horizon") != 1 or f.get("level") is None:
                continue
            selling = f.get("direction") == "sell_below"
            row = _row(
                "trend followers", f"{m.get('label', key)} flip", f.get("spot"),
                f.get("level"), "price",
                ("Trend-following funds turn from buyer to seller here, and "
                 "they all use much the same rule, so the selling arrives "
                 "together." if selling else
                 "Trend-following funds turn from seller to buyer here."),
                distance_pct=f.get("distance_pct"), source=src,
                quotable=src in ("futures", "yahoo_futures"))
            # Kept from the old standalone flip table so one list can serve
            # both jobs: the nearest-line summary and the market-by-market read.
            row.update({"market": key, "sector": m.get("sector"),
                        "trend_signal": m.get("signal"),
                        "direction": f.get("direction")})
            rows.append(row)
    rows.sort(key=lambda r: abs(r.get("distance_pct") or 999))
    return rows if limit is None else rows[:limit]


def breadth_levels(crown: dict) -> list[dict]:
    """The golden ratio's own levels — RSP/SPY against its 12-month range."""
    hb = crown.get("heartbeat") or {}
    s = hb.get("series") or {}
    now = hb.get("ratio")
    rows = []
    if now and s.get("range_high"):
        rows.append(_row(
            "breadth", "RSP/SPY 12-month high", now, s["range_high"], "ratio",
            "Breadth at the top of its range. A broadening phase reaching here "
            "is late rather than early, and usually turns back toward the "
            "large caps.",
            distance_pct=_pct_away(now, s["range_high"])))
    if now and s.get("range_low"):
        rows.append(_row(
            "breadth", "RSP/SPY 12-month low", now, s["range_low"], "ratio",
            "Breadth at the bottom of its range. A narrowing phase reaching "
            "here is usually exhausted, and it is where breadth trades start "
            "to work.",
            distance_pct=_pct_away(now, s["range_low"])))
    ma = (s.get("ma_20") or [None])[-1]
    if now and ma:
        rows.append(_row(
            "breadth", "RSP/SPY 20-day average", now, ma, "ratio",
            "The average stock crossing below its own recent trend against the "
            "index. It turns before the regime label does.",
            distance_pct=_pct_away(now, ma)))
    return rows


def volatility_levels(crown: dict) -> list[dict]:
    """Levels quoted in vol points and percentiles, not dollars."""
    vol = crown.get("volatility") or {}
    disp = vol.get("dispersion") or {}
    s = disp.get("series") or {}
    rows = []
    spread = disp.get("spread")
    if spread is not None and s.get("band_elevated"):
        rows.append(_row(
            "volatility", "Single-stock vs index gap — elevated band", spread,
            s["band_elevated"], "vol points",
            "Above here the index is hiding what individual names are doing. "
            "It only counts as a warning while the gap is still widening.",
            distance_pct=_pct_away(spread, s["band_elevated"])))
    if spread is not None and s.get("band_calm"):
        rows.append(_row(
            "volatility", "Single-stock vs index gap — calm band", spread,
            s["band_calm"], "vol points",
            "Below here stocks move together and selection stops paying. Only "
            "direction matters in that regime.",
            distance_pct=_pct_away(spread, s["band_calm"])))
    vix = vol.get("vix")
    if vix is not None:
        rows.append(_row(
            "volatility", "VIX — premium-selling threshold", vix,
            S.VIX_VERY_LOW, "vol points",
            "Below this, with dealers damping moves, the tape favours selling "
            "premium over chasing breakouts.",
            distance_pct=_pct_away(vix, S.VIX_VERY_LOW)))
        rows.append(_row(
            "volatility", "VIX — already-priced threshold", vix,
            S.VIX_ELEVATED, "vol points",
            "Above this, protection is already expensive. A spike through it "
            "is not a fresh reason to sell.",
            distance_pct=_pct_away(vix, S.VIX_ELEVATED)))
    return rows


def correlation_levels(crown: dict) -> list[dict]:
    """Where a stock-picker's market stops being one."""
    corr = ((crown.get("volatility") or {}).get("corroboration") or {})
    pctl = corr.get("correlation_percentile")
    val = corr.get("implied_correlation")
    if val is None or pctl is None:
        return []
    return [_row(
        "correlation", "Implied correlation percentile", round(pctl * 100, 1),
        50.0, "percentile",
        "Low correlation means stocks trade on their own news and selection "
        "pays. Rising back through the middle of its range means everything "
        "starts moving together again, and only direction matters.",
        distance_pct=None)]


def build(crown: dict) -> dict:
    """One table across price, breadth, volatility and correlation."""
    rows = (price_levels(crown) + trend_flip_levels(crown)
            + breadth_levels(crown) + volatility_levels(crown)
            + correlation_levels(crown))
    # Nearest first, so the line about to be crossed is the one read first.
    rows.sort(key=lambda r: abs(r.get("distance_pct")
                                if r.get("distance_pct") is not None else 999))
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    return {
        "levels": rows,
        "count": len(rows),
        "by_kind": by_kind,
        "note": ("Every line in the sand this layer knows about, sorted "
                 "nearest first. Most of these are not prices — a breadth "
                 "ratio, a volatility gap and a correlation percentile all "
                 "have levels that change the regime when they break. Rows "
                 "where quotable_as_contract is false carry a tracking fund's "
                 "price, not the contract's."),
    }
