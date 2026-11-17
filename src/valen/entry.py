"""VALEN entry layer, daily half (PM 2026-11-17): Valen's stop-fit test as a visible fact on every row.

Valen buys at a level and puts the stop under the low of the day, "never more than one ATR from the entry; too far? skip the
trade". The LOD distance (how far price sits above the low, in daily ranges) is the same fact seen from the entry side: want it
under about 0.6-0.7, at 1.0 the stop is a full range away.

    stop_fit(entry, low, atr)   -> {entry, stop, risk, atr_multiple, lod_dist_atr, fit, within_cap}
    entry_last_day(panel, rows) -> {ticker: {"stop_fit": {...}}}  on the LAST completed bar (entry = close, anchor = that bar's low)

`fit`: GOOD (at or under the preferred distance), OK (under the cap), TOO_FAR (over one ATR), NA (no ATR or price). A reading, never a
gate and never a size: AQE exports the arithmetic, the PM decides. Pure; no network.
"""

from __future__ import annotations

from . import spec as S

GOOD, OK, TOO_FAR, NA = "GOOD", "OK", "TOO_FAR", "NA"


def stop_fit(entry, low, atr, tick: float = S.ENTRY_TICK) -> dict:
    """Stop one tick under `low`; risk = entry - stop; the ATR multiple of that risk against the cap."""
    try:
        entry, low, atr = float(entry), float(low), float(atr)
    except (TypeError, ValueError):
        return {"fit": NA, "reason": "no price, low or ATR"}
    if not (entry > 0 and low > 0 and atr > 0) or entry != entry or low != low or atr != atr:
        return {"fit": NA, "reason": "no price, low or ATR"}
    stop = round(low - tick, 2)
    risk = round(entry - stop, 2)
    mult = risk / atr
    lod = (entry - low) / atr
    fit = TOO_FAR if mult > S.ENTRY_STOP_CAP_ATR else (GOOD if lod <= S.ENTRY_LOD_PREFERRED_ATR else OK)
    return {"entry": round(entry, 2), "stop": stop, "risk": risk, "atr": round(atr, 2), "atr_multiple": round(mult, 2),
            "lod_dist_atr": round(lod, 2), "within_cap": bool(mult <= S.ENTRY_STOP_CAP_ATR), "cap_atr": S.ENTRY_STOP_CAP_ATR, "fit": fit}


def plain(sf: dict | None) -> str:
    """One plain sentence for a card or a table cell."""
    if not sf or sf.get("fit") in (None, NA):
        return "Stop fit: not read (" + ((sf or {}).get("reason") or "no data") + ")"
    word = {GOOD: "a good fit", OK: "inside the cap", TOO_FAR: "too far: Valen skips it"}[sf["fit"]]
    return (f"Stop fit: stop {sf['stop']:.2f} is {sf['atr_multiple']:.2f} daily ranges under the entry {sf['entry']:.2f} "
            f"(cap {sf['cap_atr']:g}), {word}")


def entry_last_day(panel, rows: list[dict]) -> dict[str, dict]:
    """For every row's ticker: the stop-fit fact on the last completed bar (entry = its close, anchor = its low, ATR14 from the panel)."""
    import numpy as np
    want = {r.get("ticker") for r in rows if r.get("ticker")}
    row_atr = {r.get("ticker"): r.get("atr_14d") for r in rows if r.get("ticker")}      # the house ATR first, so the fact matches the bracket's own unit
    out: dict[str, dict] = {}
    for tk, df in panel[panel["ticker"].isin(want)].groupby("ticker", sort=False):
        df = df.sort_values("date").tail(40)
        if len(df) < 16:
            out[tk] = {"stop_fit": {"fit": NA, "reason": "not enough daily price history"}}
            continue
        h, lo, c = (df[k].astype(float).to_numpy() for k in ("high", "low", "close"))
        pc = np.concatenate([[c[0]], c[:-1]])
        tr = np.maximum(h - lo, np.maximum(abs(h - pc), abs(lo - pc)))
        try:
            atr = float(row_atr.get(tk))
            atr = atr if atr > 0 else float(np.mean(tr[-14:]))
        except (TypeError, ValueError):
            atr = float(np.mean(tr[-14:]))                  # fallback only: simple 14-bar mean
        sf = stop_fit(c[-1], lo[-1], atr)
        sf["as_of"] = str(df["date"].iloc[-1])[:10]
        out[tk] = {"stop_fit": sf}
    return out
