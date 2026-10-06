"""VALEN Part 3 — House: the five setups, MEASURED (handbook pp. 30-40).

Replaces the DETECT-field relabelling that shipped 2026-09-30 (PM sign-off
2026-10-05 on docs/AQE_VALEN_HOUSE_SETUPS_PROPOSAL.md). The handbook's own
test: "Each one is defined tightly enough to say no with." So every grader
here returns a checklist -- each rule, the measured value, PASS / FAIL /
NOT_YET / INFO -- and a status derived from it, never a score:

    TRIGGERED   every rule passes and the trigger happened on the LATEST bar
    READY       every rule passes, waiting on the trigger (a watchlist name)
    WATCH       structure is there, a required rule is not met yet
    PAST_PIVOT  the trigger already happened on an earlier bar ("I am not
                buying on day three")
    FAILED      a no-partial-credit rule broke; the reason is in `fails`

Piece 12 is LONG-ONLY (PM 2026-10-05): two risk warnings (parabolic,
failed leader) on held names and candidates, statuses WARNING / CRACKED /
BROKEN -- never a short signal. Pivot and stop are LEVELS; AQE sizes
nothing and decides nothing.

Pure functions of daily OHLCV bars (+ SPY closes, earnings dates, the
row's own RS/in-theme context). No file access, no network.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from . import spec as S

PASS, FAIL, NOT_YET, INFO = "PASS", "FAIL", "NOT_YET", "INFO"

TRIGGERED, READY, WATCH, PAST_PIVOT, FAILED = (
    "TRIGGERED", "READY", "WATCH", "PAST_PIVOT", "FAILED")
WARNING, CRACKED, BROKEN = "WARNING", "CRACKED", "BROKEN"

STATUS_ORDER = [TRIGGERED, READY, BROKEN, CRACKED, WARNING, WATCH, PAST_PIVOT, FAILED]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _check(rule: str, value, result: str, hard: bool = False) -> dict:
    return {"rule": rule, "value": value, "result": result, "hard": hard}


def _r(x, nd=2):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(f, nd)


def _pct(x):
    return None if x is None else f"{x:.1f}%"


def _sma(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        c = np.cumsum(np.insert(a.astype(float), 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _atr(h, l, c, n=14) -> np.ndarray:
    """Wilder ATR, the same house formula the rest of VALEN uses."""
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def _r2_log(closes: np.ndarray) -> float | None:
    """R^2 of log(close) vs time -- how straight a climb is. 1.0 = a ruler."""
    y = np.log(closes[closes > 0])
    if len(y) < 3:
        return None
    x = np.arange(len(y))
    c = np.corrcoef(x, y)[0, 1]
    return None if np.isnan(c) else float(c * c)


def zigzag(high: np.ndarray, low: np.ndarray, pct: float, start: int = 0) -> list[tuple]:
    """Alternating swing pivots [(pos, price, 'H'|'L', confirmed)], starting at
    `start` treated as a high. The final pivot is provisional (unconfirmed):
    it is the running extreme since the last reversal."""
    th = pct / 100.0
    n = len(high)
    if start >= n:
        return []
    piv = [(start, float(high[start]), "H", True)]
    mode, ext_i, ext_p = "H", start, float(high[start])
    for i in range(start + 1, n):
        if mode == "H":
            if high[i] > ext_p:
                ext_i, ext_p = i, float(high[i])
            elif low[i] <= ext_p * (1 - th):
                piv[-1] = (ext_i, ext_p, "H", True)
                mode, ext_i, ext_p = "L", i, float(low[i])
                piv.append((ext_i, ext_p, "L", False))
        else:
            if low[i] < ext_p:
                ext_i, ext_p = i, float(low[i])
                piv[-1] = (ext_i, ext_p, "L", False)
            elif high[i] >= ext_p * (1 + th):
                piv[-1] = (ext_i, ext_p, "L", True)
                mode, ext_i, ext_p = "H", i, float(high[i])
                piv.append((ext_i, ext_p, "H", False))
        if mode == "H" and len(piv) > 1:
            piv[-1] = (ext_i, ext_p, "H", False)
    return piv


def count_bases(high: np.ndarray, low: np.ndarray, pct: float, end: int | None = None) -> int:
    """Which base (or pullback) of the current run price is in now.

    Run origin = the lowest low of the last year. Every swing high after it
    that pulled back >= `pct` and was later EXCEEDED is one completed base;
    the base price is in now is completed + 1."""
    end = len(high) if end is None else end
    lo0 = max(0, end - 252)
    origin = lo0 + int(np.argmin(low[lo0:end]))
    piv = zigzag(high[:end], low[:end], pct, start=origin)
    highs = [p for p in piv if p[2] == "H" and p[3] and p[0] > origin]
    completed = 0
    for pos, price, _, _ in highs:
        if pos + 1 < end and np.max(high[pos + 1:end]) > price:
            completed += 1
    return completed + 1


def expansion_day(o, h, l, c, v, i: int) -> dict:
    """The 4% expansion day, p.31 Stage 3 (also piece 13's trigger)."""
    prev_c = c[i - 1]
    chg = (c[i] / prev_c - 1) * 100 if prev_c else None
    rng = h[i] - l[i]
    prior = h[i - S.HB_EXPANSION_BIGGER_THAN_BARS:i] - l[i - S.HB_EXPANSION_BIGGER_THAN_BARS:i]
    pos_in_range = (c[i] - l[i]) / rng if rng > 0 else 0.0
    ups = 0
    j = i - 1
    while j > 0 and c[j] > c[j - 1]:
        ups += 1
        j -= 1
    checks = [
        _check("Day expands ≥ 4%", _pct(chg),
               PASS if chg is not None and chg >= S.HB_EXPANSION_MIN_PCT else FAIL),
        _check("Bar bigger than the last 5", _r(rng),
               PASS if len(prior) and rng > prior.max() else FAIL),
        _check("Closes in the top 30% of its range", f"{pos_in_range:.0%}",
               PASS if pos_in_range >= 1 - S.HB_EXPANSION_CLOSE_TOP_FRAC else FAIL),
        _check("Volume above the day before", None, PASS if v[i] > v[i - 1] else FAIL),
        _check("No more than 2 up-days into it", ups,
               PASS if ups <= S.HB_MAX_UP_DAYS_INTO_TRIGGER else FAIL),
    ]
    return {"ok": all(x["result"] == PASS for x in checks), "checks": checks}


def _status(checks: list[dict], triggered: bool, past: bool = False) -> tuple[str, list[str]]:
    fails = [f'{x["rule"]}: {x["value"]}' if x["value"] is not None else x["rule"]
             for x in checks if x["result"] == FAIL]
    if any(x["result"] == FAIL and x["hard"] for x in checks):
        return FAILED, fails
    if past:
        return PAST_PIVOT, fails
    if any(x["result"] in (FAIL, NOT_YET) for x in checks):
        return WATCH, fails
    return (TRIGGERED if triggered else READY), fails


def _grade(piece, setup, status, fails, checks, pivot=None, stop=None, note=None, **extra):
    g = {"piece": piece, "setup": setup, "status": status,
         "pivot": _r(pivot), "stop": _r(stop), "checks": checks, "fails": fails}
    if note:
        g["note"] = note
    g.update(extra)
    return g


class Bars:
    """Arrays for one ticker, oldest first."""

    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("date")
        self.dates = pd.to_datetime(df["date"]).dt.date.to_numpy()
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float)
        self.n = len(df)
        self.sma10 = _sma(self.c, 10)
        self.sma20 = _sma(self.c, 20)
        self.sma50 = _sma(self.c, 50)
        self.atr = _atr(self.h, self.l, self.c)
        self.vol50 = _sma(self.v, 50)

    def rising(self, ma: np.ndarray, i: int, back: int = 5) -> bool:
        return bool(i - back >= 0 and not np.isnan(ma[i]) and not np.isnan(ma[i - back])
                    and ma[i] > ma[i - back])

    def falling(self, ma: np.ndarray, i: int, back: int = 5) -> bool:
        return bool(i - back >= 0 and not np.isnan(ma[i]) and not np.isnan(ma[i - back])
                    and ma[i] < ma[i - back])


# ---------------------------------------------------------------------------
# 08 — VCP (p.31)
# ---------------------------------------------------------------------------

def grade_vcp(b: Bars) -> dict | None:
    t = b.n - 1
    if b.n < max(S.IMPL_VCP_BASE_LOOKBACK, 60):
        return None
    lo = t - S.IMPL_VCP_BASE_LOOKBACK
    hi_pos = lo + int(np.argmax(b.h[lo:t]))            # base high, excluding today
    if t - hi_pos < S.IMPL_VCP_MIN_BASE_BARS:
        return None
    r0 = max(0, hi_pos - S.IMPL_VCP_RUN_LOOKBACK)
    run_lo_pos = r0 + int(np.argmin(b.l[r0:hi_pos + 1]))
    run_pct = (b.h[hi_pos] / b.l[run_lo_pos] - 1) * 100
    if run_pct < S.HB_VCP_MIN_RUN_PCT:
        return None                                     # no Stage 1: not a VCP candidate

    piv = zigzag(b.h[:t + 1], b.l[:t + 1], S.IMPL_VCP_ZIGZAG_PCT, start=hi_pos)
    pairs = []
    for k in range(len(piv) - 1):
        if piv[k][2] == "H" and piv[k + 1][2] == "L":
            hpos, hp = piv[k][0], piv[k][1]
            lpos, lp = piv[k + 1][0], piv[k + 1][1]
            pairs.append((hpos, hp, lpos, lp, (hp - lp) / hp * 100))
    if len(pairs) < 2:
        return None                                     # "one quiet week" is not a VCP

    depths = [p[4] for p in pairs]
    last_h_pos, pivot, last_l_pos, last_low, last_depth = pairs[-1]
    base_no = count_bases(b.h, b.l, 10.0, end=t + 1)

    shrinking = all(depths[k] <= depths[k - 1] * S.IMPL_VCP_SHRINK_RATIO
                    for k in range(1, len(depths)))
    if not shrinking:
        return None                                     # "without pullbacks that get
                                                        # smaller, it is just a range"
    vol_by_pair = [b.v[p[0]:p[2] + 1].mean() for p in pairs]
    dry = vol_by_pair[-1] == min(vol_by_pair) and vol_by_pair[-1] < b.v[hi_pos:t + 1].mean()
    lows = [p[3] for p in pairs]
    higher_lows = all(lows[k] > lows[k - 1] for k in range(1, len(lows)))
    riding = all(b.c[t] > ma[t] and b.rising(ma, t) for ma in (b.sma10, b.sma20, b.sma50))
    run_r2 = _r2_log(b.c[run_lo_pos:hi_pos + 1])
    mas = [b.sma10[t], b.sma20[t], b.sma50[t]]
    converge = (max(mas) / min(mas) - 1) * 100 if min(mas) > 0 else None
    inside = any(b.h[i] <= b.h[i - 1] and b.l[i] >= b.l[i - 1] for i in range(t - 2, t + 1))

    exp = expansion_day(b.o, b.h, b.l, b.c, b.v, t)
    broke_today = b.c[t] > pivot and b.c[t - 1] <= pivot
    broke_before = bool(np.any(b.c[last_l_pos:t] > pivot))

    checks = [
        _check("Stage 1: run of ≥ 30% into the base", _pct(run_pct), PASS, hard=True),
        _check("Stage 1: clean, steady run (not a zig-zag)", _r(run_r2),
               PASS if run_r2 is not None and run_r2 >= S.IMPL_RUN_CLEAN_R2 else FAIL),
        _check("Stage 1: young trend — 1st, 2nd or 3rd base", f"base #{base_no}",
               PASS if base_no <= S.HB_MAX_YOUNG_BASE else FAIL, hard=True),
        _check("Stage 2: each pullback clearly shallower",
               " -> ".join(f"{d:.0f}%" for d in depths),
               PASS if shrinking else FAIL, hard=True),
        _check("Stage 2: last pullback ≤ 10%", _pct(last_depth),
               PASS if last_depth <= S.HB_VCP_LAST_PULLBACK_MAX_PCT else NOT_YET),
        _check("Stage 2: volume quietest in the final pullback", None, PASS if dry else FAIL),
        _check("Stage 2: higher lows into the buy point", None, PASS if higher_lows else FAIL),
        _check("Stage 2: riding rising 10/20/50-day lines", None, PASS if riding else FAIL),
        _check("Extra: inside bar before the trigger", None, INFO if inside else INFO),
        _check("Extra: 10/20/50-day lines converging", _pct(converge), INFO),
    ]
    trig = [dict(x, rule="Stage 3: " + x["rule"]) for x in exp["checks"]]
    if broke_today:
        checks += trig
    status, fails = _status(checks, triggered=broke_today and exp["ok"],
                            past=broke_before and not broke_today)
    stop = b.l[t] if status == TRIGGERED else last_low
    return _grade("08", "VCP", status, fails, checks, pivot=pivot, stop=stop,
                  base_number=base_no, pullbacks_pct=[_r(d, 1) for d in depths],
                  note=("Expansion day on the latest bar; stop = that day's low." if status == TRIGGERED
                        else "Until the expansion day arrives, this is a watchlist name."))


# ---------------------------------------------------------------------------
# 09 — High tight flag (p.33). No partial credit.
# ---------------------------------------------------------------------------

def grade_htf(b: Bars) -> dict | None:
    t = b.n - 1
    if b.n < 120:
        return None
    lo = t - (S.HB_HTF_FLAG_MAX_BARS + 20)
    hi_pos = lo + int(np.argmax(b.h[lo:t]))            # pole high, excluding today
    p0 = max(0, hi_pos - S.HB_HTF_POLE_MAX_BARS)
    pole_lo_pos = p0 + int(np.argmin(b.l[p0:hi_pos + 1]))
    pole_high = b.h[hi_pos]
    pole_pct = (pole_high / b.l[pole_lo_pos] - 1) * 100
    if pole_pct < S.HB_HTF_POLE_MIN_PCT:
        return None                                     # "the pole is a measured number"

    pole_bars = hi_pos - pole_lo_pos
    flag_bars = t - hi_pos
    seg = b.c[pole_lo_pos:hi_pos + 1]
    lr = np.diff(np.log(seg[seg > 0]))
    total = float(np.log(pole_high / b.l[pole_lo_pos]))
    spike = float(lr.max() / total) if len(lr) and total > 0 else 1.0
    r2 = _r2_log(seg)
    flag_low = float(b.l[hi_pos + 1:t + 1].min()) if flag_bars else pole_high
    depth = (pole_high - flag_low) / pole_high * 100
    fl_v = b.v[hi_pos + 1:t + 1]
    half = len(fl_v) // 2
    fading = len(fl_v) >= 4 and fl_v[half:].mean() < fl_v[:half].mean()
    quieter = len(fl_v) > 0 and fl_v.mean() < b.v[pole_lo_pos:hi_pos + 1].mean()
    rng = b.h[hi_pos + 1:t + 1] - b.l[hi_pos + 1:t + 1]
    narrowing = len(rng) >= 10 and rng[-5:].mean() < rng.mean()
    flag_no = count_bases(b.h, b.l, 10.0, end=t + 1)

    if flag_bars < S.HB_HTF_FLAG_MIN_BARS:
        dur = NOT_YET
    elif flag_bars <= S.HB_HTF_FLAG_MAX_BARS:
        dur = PASS
    else:
        dur = FAIL
    broke_today = b.c[t] > pole_high and b.c[t - 1] <= pole_high
    broke_before = bool(np.any(b.c[hi_pos + 1:t] > pole_high))
    rising_vol = b.v[t] > b.v[t - 1] and not np.isnan(b.vol50[t]) and b.v[t] > b.vol50[t]

    checks = [
        _check("Pole: ~a double (≥ 90%) in ≤ 8 weeks",
               f"{pole_pct:.0f}% in {pole_bars} sessions",
               PASS if pole_bars <= S.HB_HTF_POLE_MAX_BARS else FAIL, hard=True),
        _check("Pole is a staircase, not a near-vertical blow-off", f"{pole_bars} sessions",
               PASS if pole_bars >= S.IMPL_HTF_POLE_MIN_BARS else FAIL, hard=True),
        _check("Pole is not one big spike day", f"biggest day = {spike:.0%} of the pole",
               PASS if spike <= S.IMPL_HTF_SPIKE_MAX_SHARE else FAIL, hard=True),
        _check("Pole climbs steadily (~45 degrees)", _r(r2),
               PASS if r2 is not None and r2 >= S.IMPL_HTF_POLE_R2 else FAIL),
        _check("Flag is shallow: ≤ 20-25% off the pole high", _pct(depth),
               PASS if depth <= S.HB_HTF_FLAG_MAX_PCT else FAIL, hard=True),
        _check("Flag is brief: 3-5 weeks, not much past 8", f"{flag_bars} sessions", dur,
               hard=(dur == FAIL)),
        _check("Flag is tight: volume fading through it", None, PASS if fading else FAIL),
        _check("Flag is quieter than the pole", None, PASS if quieter else FAIL),
        _check("Narrow days into the buy point", None, PASS if narrowing else FAIL),
        _check("First or second flag of the run", f"flag #{flag_no}",
               PASS if flag_no <= S.HB_HTF_MAX_FLAG_NUMBER else FAIL, hard=True),
        _check("Trend that built the pole still intact (above 50-day)", None,
               PASS if b.c[t] > b.sma50[t] else FAIL, hard=True),
    ]
    if broke_today:
        checks.append(_check("Trigger: break above the PATTERN HIGH on rising volume",
                             _r(b.c[t]), PASS if rising_vol else FAIL))
    status, fails = _status(checks, triggered=broke_today and rising_vol,
                            past=broke_before and not broke_today)
    if depth > S.HB_HTF_FLAG_IDEAL_MAX_PCT and status != FAILED:
        fails.append(f"Flag {depth:.0f}% deep: inside the 25% limit but past the 20% ideal")
    stop = b.l[t] if status == TRIGGERED else flag_low
    return _grade("09", "High tight flag", status, fails, checks, pivot=pole_high, stop=stop,
                  pole_pct=_r(pole_pct, 1), flag_depth_pct=_r(depth, 1), flag_sessions=flag_bars,
                  note="There is no partial credit: a flag that rounds out or cuts deep is gone.")


# ---------------------------------------------------------------------------
# 10 — Undercut and rally (p.35)
# ---------------------------------------------------------------------------

def _swing_lows(low: np.ndarray, a: int, z: int, side: int) -> list[int]:
    out = []
    for i in range(max(a, side), min(z, len(low) - side)):
        if low[i] == low[i - side:i + side + 1].min():
            out.append(i)
    return out


def grade_unr(b: Bars, rs_rank: float | None = None, in_theme: bool | None = None) -> dict | None:
    t = b.n - 1
    if b.n < 80:
        return None
    if not (b.c[t] > b.sma50[t] and b.rising(b.sma50, t)):
        return None                                     # a broken stock, not a pullback
    win0 = t - S.IMPL_UNR_WINDOW + 1
    sw = _swing_lows(b.l, t - S.IMPL_UNR_SUPPORT_LOOKBACK, win0 - 1, S.IMPL_UNR_PIVOT_SIDE)
    if not sw:
        return None
    sup_pos = sw[-1]
    level = float(b.l[sup_pos])
    atr = b.atr[t]
    if np.isnan(atr):
        return None
    under = [i for i in range(win0, t + 1)
             if b.l[i] < level - S.IMPL_UNR_MIN_UNDERCUT_ATR * atr]
    if not under:
        return None                                     # no real dip = no shakeout
    u_pos = under[0]
    pull_low_pos = u_pos + int(np.argmin(b.l[u_pos:t + 1]))
    pull_low = float(b.l[pull_low_pos])
    reclaim_today = b.c[t] > level and (b.c[t - 1] <= level or b.l[t] < level)
    # An earlier reclaim only counts if price is STILL above the level --
    # a reclaim that fell back under is no reclaim.
    reclaim_before = (bool(np.any(b.c[u_pos:t] > level)) and b.c[t] > level
                      and not reclaim_today)
    pb_no = count_bases(b.h, b.l, S.IMPL_PULLBACK_ZIGZAG_PCT, end=t + 1)
    top_pos = max(0, u_pos - 20) + int(np.argmax(b.h[max(0, u_pos - 20):u_pos + 1]))
    down_vol = b.v[top_pos:pull_low_pos + 1].mean()
    dry = not np.isnan(b.vol50[top_pos]) and down_vol < b.vol50[top_pos]
    entry = max(level, b.c[t])
    stop_dist = entry - pull_low
    mas_up = b.rising(b.sma20, t) and b.rising(b.sma50, t)
    rs_ok = None if rs_rank is None else rs_rank >= S.IMPL_UNR_RS_RANK_MIN

    checks = [
        _check("Moving averages still rising (20 and 50-day)", None, PASS if mas_up else FAIL),
        _check("Price still above the longer average (50-day)", _r(b.sma50[t]),
               PASS if b.c[t] > b.sma50[t] else FAIL, hard=True),
        _check("Young trend: 1st, 2nd or 3rd pullback", f"pullback #{pb_no}",
               PASS if pb_no <= S.HB_MAX_YOUNG_BASE else FAIL, hard=True),
        _check("Volume drying up on the way down", None, PASS if dry else FAIL),
        _check("A real dip below the prior low", f"low {pull_low:.2f} under {level:.2f}", PASS),
        _check("Then a real reclaim (close back above)", _r(b.c[t]),
               PASS if (reclaim_today or reclaim_before) else NOT_YET),
        _check("Stop at the pullback low, under one daily range",
               f"{stop_dist:.2f} vs ATR {atr:.2f}" if not np.isnan(atr) else None,
               PASS if not np.isnan(atr) and stop_dist <= S.HB_UNR_STOP_MAX_ATR * atr else FAIL,
               hard=True),
        _check("Relative strength still holding", _r(rs_rank, 0),
               INFO if rs_ok is None else (PASS if rs_ok else FAIL)),
        _check("Group still being bought (in-theme)", None,
               INFO if in_theme is None else (PASS if in_theme else FAIL)),
    ]
    status, fails = _status(checks, triggered=reclaim_today, past=reclaim_before)
    return _grade("10", "Undercut and rally", status, fails, checks, pivot=level, stop=pull_low,
                  note=("Reclaim on the latest bar." if status == TRIGGERED else
                        "I buy nothing while price is still falling. The reclaim is the signal."))


# ---------------------------------------------------------------------------
# 11 — Episodic pivot (p.37), day one + the Delayed EP
# ---------------------------------------------------------------------------

def _is_earnings_day(d: date, prev: date | None, earnings: set) -> bool:
    return d in earnings or (prev is not None and prev in earnings)


def grade_ep(b: Bars, earnings_dates: set | None = None) -> dict | None:
    t = b.n - 1
    if b.n < 140:
        return None
    earn = earnings_dates or set()
    g = None
    for i in range(t, t - S.IMPL_EP_WINDOW, -1):
        gap = (b.o[i] / b.c[i - 1] - 1) * 100
        chg = (b.c[i] / b.c[i - 1] - 1) * 100
        is_e = _is_earnings_day(b.dates[i], b.dates[i - 1], earn)
        if gap >= S.HB_EP_GAP_MIN_PCT or (is_e and chg >= S.HB_EP_EARNINGS_EXPANSION_PCT):
            g = (i, gap, chg, is_e)
            break
    if g is None:
        return None
    gi, gap, chg, is_e = g
    pre = gi - 1
    n0 = pre - S.IMPL_EP_NEGLECT_BARS
    ret_pre = (b.c[pre] / b.c[n0] - 1) * 100
    f0 = max(1, gi - S.IMPL_EP_FIRST_GAP_LOOKBACK)
    prior_gaps = [i for i in range(f0, gi)
                  if (b.o[i] / b.c[i - 1] - 1) * 100 >= S.HB_EP_GAP_MIN_PCT]
    vmult = b.v[gi] / b.vol50[pre] if b.vol50[pre] else None
    rng = b.h[gi] - b.l[gi]
    upper = rng > 0 and (b.c[gi] - b.l[gi]) / rng >= 0.5
    holds = upper and b.c[gi] > b.h[pre]
    atr_pre = b.atr[pre]
    day_stop = b.c[gi] - b.l[gi]
    stop_fits = not np.isnan(atr_pre) and day_stop <= S.HB_EP_STOP_MAX_ATR * atr_pre
    y0 = max(0, pre - 252)
    prior_high = float(b.h[y0:gi].max())
    over = (prior_high / b.c[gi] - 1) * 100
    clear = over <= 0 or over > S.IMPL_EP_OVERHEAD_PCT

    checks = [
        _check("Neglect before it: no big run in the prior 3 months", _pct(ret_pre),
               PASS if ret_pre <= S.IMPL_EP_NEGLECT_MAX_RUN_PCT else FAIL, hard=True),
        _check("Out of an orderly base, not a falling knife", _pct(ret_pre),
               PASS if ret_pre >= S.IMPL_EP_FALLING_KNIFE_PCT else FAIL, hard=True),
        _check("The first surprise: no gap like it in 6 months", len(prior_gaps),
               PASS if not prior_gaps else FAIL, hard=True),
        _check("The gap: ≥ 10%, or ≥ 4% expansion on an earnings day",
               f"gap {gap:.1f}%, day {chg:.1f}%" + (" (earnings)" if is_e else ""), PASS),
        _check("Volume that proves it: ≥ 3x normal", None if vmult is None else f"{vmult:.1f}x",
               PASS if vmult is not None and vmult >= S.HB_EP_VOLUME_MULT else FAIL, hard=True),
        _check("It holds the gap: upper part of range, above the prior day", None,
               PASS if holds else FAIL, hard=True),
        _check("Clear air overhead (no 1-year high within 15% above)", _pct(over),
               PASS if clear else FAIL),
        _check("Catalyst", "earnings day" if is_e else
               "technical fingerprint only — AQE has no news feed",
               PASS if is_e else INFO),
    ]
    gap_high, gap_low = float(b.h[gi]), float(b.l[gi])
    if gi == t:
        checks.append(_check("A stop that fits: day's low within 1.5 daily ranges",
                             f"{day_stop:.2f} vs ATR {atr_pre:.2f}",
                             PASS if stop_fits else NOT_YET))
        status, fails = _status(checks, triggered=stop_fits)
        note = ("Gap day is the latest bar. Day-one entry is the opening-range high, stop the "
                "day's low (Part 4)." if stop_fits else
                "Gap too big to size against the day's low: wait for the Delayed EP -- the first "
                "constructive pause, trigger = reclaim of the gap-day high.")
        return _grade("11", "Episodic pivot", status, fails, checks,
                      pivot=gap_high, stop=gap_low, gap_day=str(b.dates[gi]), note=note)

    after_low = float(b.l[gi + 1:t + 1].min())
    held = after_low > gap_low
    checks.append(_check("Delayed EP: pause holds above the gap-day low",
                         f"pause low {after_low:.2f} vs {gap_low:.2f}",
                         PASS if held else FAIL, hard=True))
    reclaim_today = b.c[t] > gap_high and b.c[t - 1] <= gap_high
    reclaim_before = bool(np.any(b.c[gi + 1:t] > gap_high))
    pause_low = float(b.l[t]) if reclaim_today else after_low
    stop_ok = not np.isnan(b.atr[t]) and (gap_high - pause_low) <= S.HB_EP_STOP_MAX_ATR * b.atr[t]
    checks.append(_check("A stop that fits (pause low within 1.5 daily ranges)",
                         f"{gap_high - pause_low:.2f} vs ATR {b.atr[t]:.2f}",
                         PASS if stop_ok else FAIL))
    status, fails = _status(checks, triggered=reclaim_today,
                            past=reclaim_before and not reclaim_today)
    return _grade("11", "Episodic pivot (delayed)", status, fails, checks,
                  pivot=gap_high, stop=pause_low, gap_day=str(b.dates[gi]),
                  note="Delayed EP: trigger = reclaim of the gap-day high, stop = the day's low.")


# ---------------------------------------------------------------------------
# 12 — Parabolic / failed leader: LONG-ONLY RISK WARNINGS (p.39)
# ---------------------------------------------------------------------------

def warn_parabolic(b: Bars) -> dict | None:
    t = b.n - 1
    if b.n < 60:
        return None
    r0 = t - S.IMPL_PARA_RUN_BARS
    lo_pos = r0 + int(np.argmin(b.l[r0:t + 1]))
    hi_pos = max(lo_pos, t - 5) + int(np.argmax(b.h[max(lo_pos, t - 5):t + 1]))
    run = (b.h[hi_pos] / b.l[lo_pos] - 1) * 100
    if run < S.HB_PARA_MIN_RUN_PCT or hi_pos <= lo_pos:
        return None
    streak, j = 0, hi_pos
    while j > 0 and b.c[j] > b.c[j - 1]:
        streak += 1
        j -= 1
    ext = ((b.c[hi_pos] - b.sma50[hi_pos]) / b.atr[hi_pos]
           if not np.isnan(b.atr[hi_pos]) and b.atr[hi_pos] else None)
    crack = (b.c[t] < b.o[t] and b.c[t] < b.c[t - 1]
             and not np.isnan(b.atr[t]) and (b.h[t] - b.l[t]) >= b.atr[t])
    checks = [
        _check("Vertical run: ≥ 50% in days to weeks",
               f"{run:.0f}% in {hi_pos - lo_pos} sessions", PASS),
        _check("3+ up days in a row into the top", streak,
               PASS if streak >= S.HB_PARA_MIN_UP_STREAK else FAIL),
        _check("Far above its rising averages (rare-air ATR multiple)", _r(ext, 1),
               PASS if ext is not None and ext >= S.IMPL_PARA_FAR_ATR_MULT else FAIL),
        _check("First crack: big red bar on the latest session", None,
               PASS if crack else NOT_YET),
    ]
    met = sum(1 for x in checks[1:3] if x["result"] == PASS)
    if met == 0 and not crack:
        return None
    return _grade("12", "Parabolic — risk warning on a long", CRACKED if crack else WARNING,
                  [], checks, note="A risk flag on a long, never a short call. "
                  "The handbook: 'I do not short strength.'")


def warn_failed_leader(b: Bars, spy_close: pd.Series | None = None) -> dict | None:
    t = b.n - 1
    if b.n < 260:
        return None
    y0 = t - 252
    hi_pos = y0 + int(np.argmax(b.h[y0:t + 1]))
    lo52 = float(b.l[y0:t + 1].min())
    was_leader = t - hi_pos <= 126 and (b.h[hi_pos] / lo52 - 1) * 100 >= 50
    if not was_leader or b.c[t] >= b.sma50[t]:
        return None
    L0 = t - S.IMPL_FL_LOOKBACK
    chg = (b.c[1:] / b.c[:-1] - 1) * 100
    red = sum(1 for i in range(L0, t + 1)
              if chg[i - 1] <= S.IMPL_FL_RED_DAY_PCT and not np.isnan(b.vol50[i - 1])
              and b.v[i] >= S.IMPL_FL_RED_DAY_VOL_MULT * b.vol50[i - 1])
    roll = (b.c[t] < b.sma10[t] and b.c[t] < b.sma20[t] and b.c[t] < b.sma50[t]
            and b.falling(b.sma10, t) and b.falling(b.sma20, t) and not b.rising(b.sma50, t))
    k = S.HB_FL_NO_RECOVERY_SESSIONS
    no_recovery = bool(np.all(b.c[t - k + 1:t + 1] < b.sma50[t - k + 1:t + 1]))
    down_on_up = None
    if spy_close is not None and len(spy_close):
        s = spy_close.copy()
        s.index = pd.to_datetime(s.index).date
        sret = s.pct_change()
        ups = downs = 0
        for i in range(t - 19, t + 1):
            d = b.dates[i]
            if d in sret.index and sret[d] > 0:
                ups += 1
                if b.c[i] < b.c[i - 1]:
                    downs += 1
        down_on_up = downs / ups if ups else None
    s0 = t - 60
    support = float(b.l[s0:t].min())
    band = support * (1 + S.IMPL_FL_SUPPORT_BAND_PCT / 100)
    tests = len([i for i in _swing_lows(b.l, s0, t, 2) if b.l[i] <= band])
    rng = b.h[t] - b.l[t]
    broke = (b.c[t] < support and b.v[t] > b.v[t - 1] and rng > 0
             and (b.c[t] - b.l[t]) / rng <= S.HB_EXPANSION_CLOSE_TOP_FRAC
             and not np.isnan(b.atr[t]) and rng >= b.atr[t])
    checks = [
        _check("Selling at the top: big red high-volume days", red,
               PASS if red >= S.IMPL_FL_RED_DAYS_MIN else FAIL),
        _check("Averages roll over: below 10/20/50, lines turning down", None,
               PASS if roll else FAIL),
        _check("50-day lost, no recovery within 5 sessions", None,
               PASS if no_recovery else FAIL),
        _check("Down on days the market is up",
               None if down_on_up is None else f"{down_on_up:.0%}",
               INFO if down_on_up is None else
               (PASS if down_on_up >= S.IMPL_FL_DOWN_ON_UP_FRAC else FAIL)),
        _check("Level wears out: 3+ tests of the same support", tests,
               PASS if tests >= S.HB_FL_SUPPORT_TESTS else FAIL),
        _check("Breakdown: closes below support on a bigger down bar", _r(support),
               PASS if broke else NOT_YET),
    ]
    met = sum(1 for x in checks[:5] if x["result"] == PASS)
    if met < S.IMPL_FL_MIN_CHECKS and not broke:
        return None
    return _grade("12", "Failed leader — risk warning on a long", BROKEN if broke else WARNING,
                  [], checks, stop=None, pivot=support,
                  note="A risk flag on a long, never a short call.")


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------

def grade_ticker(df: pd.DataFrame, *, rs_rank: float | None = None,
                 in_theme: bool | None = None, earnings_dates: set | None = None,
                 spy_close: pd.Series | None = None) -> list[dict]:
    """Every setup grade + warning one ticker earns. Empty list = none of
    the five shapes is present, which is a real answer."""
    if df is None or len(df) < 60:
        return []
    b = Bars(df)
    out = []
    for fn, kw in ((grade_vcp, {}), (grade_htf, {}),
                   (grade_unr, {"rs_rank": rs_rank, "in_theme": in_theme}),
                   (grade_ep, {"earnings_dates": earnings_dates}),
                   (warn_parabolic, {}), (warn_failed_leader, {"spy_close": spy_close})):
        try:
            g = fn(b, **kw)
        except Exception as exc:  # noqa: BLE001 -- one grader never blanks the others
            g = {"piece": "?", "setup": fn.__name__, "status": "ERROR", "error": str(exc),
                 "checks": [], "fails": []}
        if g:
            g["as_of"] = str(b.dates[-1])
            out.append(g)
    out.sort(key=lambda g: STATUS_ORDER.index(g["status"]) if g["status"] in STATUS_ORDER else 99)
    return out


def grade_universe(panel: pd.DataFrame, rows: list[dict], *,
                   earnings: dict[str, list[str]] | None = None,
                   in_theme_tickers: set[str] | None = None,
                   spy_close: pd.Series | None = None) -> dict[str, list[dict]]:
    """{ticker: grades} for every row's ticker present in `panel`. A ticker
    absent from the panel is ABSENT from the result (not graded), never an
    empty list (graded, nothing found)."""
    earnings = earnings or {}
    want = {r.get("ticker") for r in rows if r.get("ticker")}
    rs = {r.get("ticker"): r.get("rs_rank_pct") for r in rows}
    sub = panel[panel["ticker"].isin(want)]
    out: dict[str, list[dict]] = {}
    for tk, df in sub.groupby("ticker", sort=False):
        e = {date.fromisoformat(d[:10]) for d in earnings.get(tk, []) if d}
        out[tk] = grade_ticker(
            df.tail(400), rs_rank=rs.get(tk),
            in_theme=None if in_theme_tickers is None else tk in in_theme_tickers,
            earnings_dates=e, spy_close=spy_close)
    return out
