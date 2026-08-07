"""Volatility Profile — the per-ticker EXIT layer (target corridor + stop).

Reimplemented from the handover (QS Phase 2). Method provenance: a fellow
trader's technique (rolling-window empirical percentiles + MAE-based stop
survival), re-derived independently. No source workbook or proprietary text is
reproduced here — the statistical method only (handover §V8).

WHAT QUESTION IT ANSWERS, and which one it does NOT.
QS answers "which stock, and is now the time" — cross-sectional, calibrated
against 634k rows. This answers a different question, once a name is already
surfaced: FOR THIS STOCK, GIVEN ITS OWN HISTORY, where is a target credible and
where should the stop sit? Per ticker, never across the universe.

THE ONE IDEA. Simulate the trade you are considering thousands of times using
only this stock's past: buy at tomorrow's open, hold one quarter, repeat from
every day in the history. That population of simulated trades — not an opinion
about the company — sizes the target and the stop.

THREE DISCIPLINES, and they are the whole method:

  CLOSE-TO-CLOSE AND HIGH-TO-LOW NEVER MIX (§V3). c2c — where the stock ended
  versus where it started — governs TARGETS. h2l — how far it travelled between
  its high and low on the way — governs STOPS. Judging a stop by close-to-close
  underestimates shake-out risk several times over, every time. They are
  computed, stored and returned separately and there is no code path that
  substitutes one for the other.

  PERCENTILES ARE FREQUENCY, NOT PROBABILITY (§V6). "68th percentile" means
  "exceeded 32% of the time in the past", NOT "32% chance next quarter". This
  is a deliberately weaker claim than QS's calibrated `p`, and every field name
  and label here says so. Never render the two as the same kind of number.

  A SHORTER WINDOW MAY COMFORT, NEVER EMBOLDEN (§V5). Stats are computed over
  full history, trailing 36m and trailing 24m. A stronger recent window may
  make a full-history target more comfortable — it must NEVER justify a HIGHER
  one. Asymmetric on purpose; it only pulls toward caution, and the code
  enforces it rather than trusting the reader to remember.

ADDITIVE, NOT A REPLACEMENT (§V7). QS's `obj_2atr` and its calibrated `p` stay
exactly as they are — changing the objective would invalidate the calibration.
This sits alongside as a per-ticker sanity check and an evidence-based stop.
Where the two disagree, that disagreement is information for the committee, not
a bug to reconcile.

STATED LIMITS, carried over rather than quietly dropped: overlapping windows
are not independent observations (acknowledged, not corrected for); percentiles
describe the past, not a forward probability; single-name only — no
cross-sectional or regime layer, which remains QS's job. And the method
measures what a stock CAN do, not what it SHOULD: targets are
volatility-permitted levels, to be weighed against fundamentals and the lower
of the two taken.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Named constants, NOT sacred (§V9). Every threshold from the source method
# is overridable and re-testable against our own data; none is gospel.
HOLD_SESSIONS = 65            # ~1 quarter
CORRIDOR_LO, CORRIDOR_HI = 0.60, 0.90     # below = ordinary drift; above = a best-ever quarter
PT1_LO, PT1_HI, PT1_SUG = 0.65, 0.75, 0.70
PT2_LO, PT2_HI, PT2_SUG = 0.75, 0.85, 0.80
STOP_GRID = tuple(round(x, 2) for x in np.arange(0.04, 0.151, 0.01))
STOP_SURVIVAL_TARGET = 0.75
MIN_WINDOWS = 100             # below this the percentiles are not worth quoting
MIN_WINNERS = 30              # below this a survival curve is noise

SESSIONS_36M = 756
SESSIONS_24M = 504


def build_windows(d: pd.DataFrame, hold: int = HOLD_SESSIONS) -> pd.DataFrame:
    """One row per possible window start: enter at the NEXT day's open, hold
    `hold` sessions. c2c and h2l are both measured over the sessions AFTER
    entry — never including the signal bar itself.

    Vectorised. The reference walks the frame in Python (~6s/ticker); this runs
    the same arithmetic as strided numpy so the page can price a name while the
    PM waits, which is the difference between a tool that gets used and one
    that does not.
    """
    n = len(d)
    if n < hold + 2:
        return pd.DataFrame(columns=["start_date", "entry", "c2c", "h2l", "start_idx"])
    op, hi, lo, cl = (d[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close"))
    dt = d["date"].to_numpy()

    last = n - hold - 1                       # need i+1 .. i+hold in range
    idx = np.arange(last)
    entry = op[idx + 1]
    exit_close = cl[idx + hold]

    # Rolling max/min over the hold window, without a Python loop.
    win_hi = np.lib.stride_tricks.sliding_window_view(hi, hold)[1:last + 1].max(axis=1)
    win_lo = np.lib.stride_tricks.sliding_window_view(lo, hold)[1:last + 1].min(axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        c2c = exit_close / entry - 1.0
        h2l = (win_hi - win_lo) / win_lo
    ok = np.isfinite(entry) & (entry > 0) & np.isfinite(c2c)
    return pd.DataFrame({"start_date": dt[idx][ok], "entry": entry[ok],
                         "c2c": c2c[ok], "h2l": h2l[ok], "start_idx": idx[ok]})


def descriptive_stats(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    if len(x) < 30:
        return {}
    out = dict(n=int(len(x)), mean=float(x.mean()), median=float(x.median()),
               std=float(x.std(ddof=1)), min=float(x.min()), max=float(x.max()))
    try:
        from scipy import stats as _st
        out["skew"] = float(_st.skew(x))
        out["kurtosis"] = float(_st.kurtosis(x))
    except Exception:  # noqa: BLE001 — shape stats are a nicety, not the method
        pass
    return out


def percentile_row(x: pd.Series, qs=(15, 25, 50, 65, 75, 85, 90)) -> dict:
    x = pd.Series(x).dropna()
    if len(x) < 30:
        return {}
    return {f"p{q}": float(np.percentile(x, q)) for q in qs}


def target_corridor(c2c: pd.Series) -> dict:
    """The usable band, from the CLOSE-TO-CLOSE distribution only (§V3)."""
    x = pd.Series(c2c).dropna()
    if len(x) < MIN_WINDOWS:
        return {}
    def pc(q):
        return float(np.percentile(x, q * 100))
    return {
        "usable_zone": (pc(CORRIDOR_LO), pc(CORRIDOR_HI)),
        "pt1_band": (pc(PT1_LO), pc(PT1_HI)), "pt1_suggested": pc(PT1_SUG),
        "pt2_band": (pc(PT2_LO), pc(PT2_HI)), "pt2_suggested": pc(PT2_SUG),
    }


def classify_hits(w: pd.DataFrame, d: pd.DataFrame, pt1: float, pt2: float,
                  hold: int = HOLD_SESSIONS) -> pd.DataFrame:
    """Did the forward HIGH ever reach PT1/PT2, and — for windows that did —
    how far did the LOW sink BEFORE that first touch (the pre-hit dip)?

    The dip is measured strictly before the touch. Measuring it over the whole
    window would count pain the trade never made you sit through, and would
    make every stop look worse than it was.
    """
    if w.empty:
        return w.assign(pt1_hit=[], pt2_hit=[], sessions_to_pt1=[], mae_pre_pt1=[])
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    starts = w["start_idx"].to_numpy(dtype=int)
    entry = w["entry"].to_numpy(dtype=float)

    wh = np.lib.stride_tricks.sliding_window_view(hi, hold)[starts + 1]
    wl = np.lib.stride_tricks.sliding_window_view(lo, hold)[starts + 1]
    tgt1 = entry[:, None] * (1 + pt1)
    tgt2 = entry[:, None] * (1 + pt2)

    reach1 = wh >= tgt1
    hit1 = reach1.any(axis=1)
    first = np.argmax(reach1, axis=1)                 # 0 where never hit; masked below

    # Worst low up to and including the touch bar.
    ar = np.arange(wh.shape[1])[None, :]
    upto = ar <= first[:, None]
    lows = np.where(upto, wl, np.inf).min(axis=1)
    mae = np.where(hit1, lows / entry - 1.0, np.nan)

    out = w.copy()
    out["pt1_hit"] = hit1.astype(int)
    out["pt2_hit"] = np.where(hit1, (wh >= tgt2).any(axis=1).astype(int), 0)
    out["sessions_to_pt1"] = np.where(hit1, first + 1, np.nan)
    out["mae_pre_pt1"] = mae
    return out


def stop_survival(classified: pd.DataFrame, grid=STOP_GRID) -> dict:
    """Among windows that EVENTUALLY hit PT1, the share that never dipped
    through each candidate stop before the touch — i.e. the winners a
    stop-holder would actually have kept."""
    if classified.empty:
        return {}
    winners = classified[classified["pt1_hit"] == 1]
    if len(winners) < MIN_WINNERS:
        return {}
    mae = winners["mae_pre_pt1"].to_numpy(dtype=float)
    return {round(float(s), 2): float(np.nanmean(mae > -s)) for s in grid}


def recommend_stop(curve_full: dict, curve_36m: dict,
                   target: float = STOP_SURVIVAL_TARGET) -> dict:
    """Tightest grid distance clearing `target` on the STRICTER of the two
    bases (§V4) — the stricter one, NOT the average.

    "NONE" is a real, honest answer: this name's path is too rough for a
    survivable stop at this target. Widening the grid silently to produce a
    number would be inventing one.
    """
    if not curve_full:
        return {"stop": None, "reason": "insufficient full-history sample"}
    for s in sorted(curve_full):
        s36 = (curve_36m or {}).get(s)
        stricter = min(curve_full[s], s36) if s36 is not None else curve_full[s]
        if stricter >= target:
            return {"stop": s, "survival_full": curve_full[s],
                    "survival_36m": s36, "stricter_basis": stricter}
    return {"stop": None,
            "reason": (f"NONE of {min(curve_full):.0%}-{max(curve_full):.0%} "
                       f"clears {target:.0%} survival")}


def entry_confirmation(d: pd.DataFrame) -> pd.Series:
    """0-3 per bar: EMA20>EMA40 (trend), close>EMA20 (price), MACD>signal
    (momentum). REPORTED, never gating — whether confirmation actually paid is
    a per-name question, and the engine does not assume the answer."""
    cl = d["close"].astype(float)
    ema20, ema40 = cl.ewm(span=20, adjust=False).mean(), cl.ewm(span=40, adjust=False).mean()
    ema12, ema26 = cl.ewm(span=12, adjust=False).mean(), cl.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    return ((ema20 > ema40).astype(int) + (cl > ema20).astype(int)
            + (macd > sig).astype(int))


def confirmation_payoff(classified: pd.DataFrame, conf: pd.Series) -> dict:
    """Hit rate by confirmation score at entry — per name, not a universal rule."""
    if classified.empty or conf is None or len(conf) == 0:
        return {}
    s = conf.to_numpy()
    idx = classified["start_idx"].to_numpy(dtype=int)
    idx = np.clip(idx, 0, len(s) - 1)
    out = {}
    for score in (0, 1, 2, 3):
        m = s[idx] == score
        if m.sum() >= 20:
            out[score] = {"n": int(m.sum()),
                          "pt1_hit_rate": float(classified.loc[m, "pt1_hit"].mean())}
    return out


def _cap_to_full(full: dict, shorter: dict) -> dict:
    """§V5, ENFORCED rather than trusted. A trailing window may make a target
    more comfortable; it may never justify a HIGHER one. Any shorter-window
    suggestion above the full-history figure is pulled back down to it, and the
    fact is recorded so the reader sees the rule bite."""
    if not full or not shorter:
        return shorter
    out = dict(shorter)
    out["capped_by_full_history"] = False
    for key in ("pt1_suggested", "pt2_suggested"):
        if key in out and key in full and out[key] > full[key]:
            out[key] = full[key]
            out["capped_by_full_history"] = True
    return out


def profile(df: pd.DataFrame, hold: int = HOLD_SESSIONS,
            pt1: float | None = None, pt2: float | None = None) -> dict:
    """The full profile for one ticker from its daily OHLCV.

    `df` needs date/open/high/low/close. Returns {} when there is not enough
    history to say anything — an empty dict, never a fabricated corridor.
    """
    need = {"date", "open", "high", "low", "close"}
    if df is None or not need.issubset(df.columns) or len(df) < hold + MIN_WINDOWS:
        return {}
    d = df.sort_values("date").reset_index(drop=True)

    w = build_windows(d, hold)
    if len(w) < MIN_WINDOWS:
        return {}

    # Trailing slices are on WINDOW STARTS, so a "36m" figure means windows
    # that STARTED in the last 36 months, not windows that merely ended there.
    w36 = w[w["start_idx"] >= (len(d) - SESSIONS_36M)]
    w24 = w[w["start_idx"] >= (len(d) - SESSIONS_24M)]

    corridor_full = target_corridor(w["c2c"])
    if not corridor_full:
        return {}
    corridor_36 = _cap_to_full(corridor_full, target_corridor(w36["c2c"]))
    corridor_24 = _cap_to_full(corridor_full, target_corridor(w24["c2c"]))

    _pt1 = pt1 if pt1 is not None else corridor_full["pt1_suggested"]
    _pt2 = pt2 if pt2 is not None else corridor_full["pt2_suggested"]

    cls = classify_hits(w, d, _pt1, _pt2, hold)
    cls36 = cls[cls["start_idx"] >= (len(d) - SESSIONS_36M)]
    curve_full = stop_survival(cls)
    curve_36 = stop_survival(cls36)
    stop = recommend_stop(curve_full, curve_36)

    winners = cls[cls["pt1_hit"] == 1]
    last_close = float(d["close"].iloc[-1])
    return {
        "windows": {"full": int(len(w)), "trailing_36m": int(len(w36)),
                    "trailing_24m": int(len(w24))},
        "hold_sessions": hold,
        "last_close": round(last_close, 2),
        # CLOSE-TO-CLOSE — targets only (§V3)
        "c2c": {"stats": descriptive_stats(w["c2c"]),
                "percentiles": percentile_row(w["c2c"]),
                "corridor_full": corridor_full,
                "corridor_36m": corridor_36, "corridor_24m": corridor_24},
        # HIGH-TO-LOW — the traverse, kept apart from targets on purpose (§V3)
        "h2l": {"stats": descriptive_stats(w["h2l"]),
                "percentiles": percentile_row(w["h2l"])},
        "pt1_pct": round(float(_pt1), 4), "pt2_pct": round(float(_pt2), 4),
        "pt1_price": round(last_close * (1 + _pt1), 2),
        "pt2_price": round(last_close * (1 + _pt2), 2),
        # FREQUENCIES, not probabilities (§V6) — the names say so.
        "pt1_frequency_full": round(float(cls["pt1_hit"].mean()), 4),
        "pt1_frequency_36m": (round(float(cls36["pt1_hit"].mean()), 4)
                              if len(cls36) >= MIN_WINNERS else None),
        "pt2_frequency_full": round(float(cls["pt2_hit"].mean()), 4),
        "median_pre_hit_dip": (round(float(winners["mae_pre_pt1"].median()), 4)
                               if len(winners) else None),
        "median_sessions_to_pt1": (float(winners["sessions_to_pt1"].median())
                                   if len(winners) else None),
        "stop_survival_curve": curve_full,
        "stop_survival_curve_36m": curve_36,
        "recommended_stop_pct": stop.get("stop"),
        "recommended_stop_price": (round(last_close * (1 - stop["stop"]), 2)
                                   if stop.get("stop") else None),
        "recommended_stop_survival": stop.get("stricter_basis"),
        "recommended_stop_reason": stop.get("reason"),
        "confirmation_payoff": confirmation_payoff(cls, entry_confirmation(d)),
    }


def verdict(prof: dict, target_pct: float) -> dict:
    """Where a PROPOSED target sits against this stock's own corridor.

    This is the line the committee reads. It is a statement about historical
    frequency for one name, never a probability and never a recommendation.
    """
    if not prof or not prof.get("c2c", {}).get("corridor_full"):
        return {"verdict": None, "reason": "no profile"}
    lo, hi = prof["c2c"]["corridor_full"]["usable_zone"]
    if target_pct < lo:
        v, why = "TOO_CLOSE", ("inside its own ordinary drift — reaching it "
                               "proves little and pays little")
    elif target_pct > hi:
        v, why = "TOO_FAR", ("beyond the 90th percentile of its own 3-month "
                             "history — possible, but not a base case")
    else:
        v, why = "OK", "inside its usable zone"
    return {"verdict": v, "reason": why, "usable_zone": (lo, hi),
            "target_pct": round(float(target_pct), 4)}
