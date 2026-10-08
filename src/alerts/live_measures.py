"""AQE handoff D123/R21 (2026-10-02) §4 — pure functions for the new
condition-watching alerts. Every function here takes already-fetched bar
lists and returns a plain dict/number; no network, no file access, so each
is independently unit-testable (same discipline card.py/gex.py already
hold to).

Bars are FMP's own `get_intraday_bars()` shape: {date, open, high, low,
close, volume}, `date` a "YYYY-MM-DD HH:MM:SS" string in exchange-local
time (America/New_York) — FMP's intraday endpoints are always exchange
time, never UTC. A bar whose date can't be parsed is dropped rather than
crashing the read; a thin night is a data gap, not a reason to blow up a
15-minute cycle that has ~50 other names to get through.

Replaces the "linear clock" src/alerts/intraday.py's own docstring already
flags as knowingly wrong at the edges (volume is U-shaped through the
session, heaviest at the open and the close) — but ONLY for this new
conditions pathway. The existing live trigger emails keep reading
intraday.py's own `vol_pace` unchanged (handoff §7: "existing trigger
emails carry on unchanged"); retrofitting that shared, currently-live path
is explicitly out of scope for a shadow-mode build whose entire point is
zero behaviour change to anything already emailing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import condition_spec as S

_ET = ZoneInfo("America/New_York")


def _f(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None  # reject NaN
    except (TypeError, ValueError):
        return None


def _parse_bar_dt(bar: dict) -> datetime | None:
    raw = bar.get("date")
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_ET)
    except ValueError:
        try:
            return datetime.fromisoformat(str(raw)).replace(tzinfo=_ET)
        except ValueError:
            return None


def _slot_index(dt: datetime) -> int | None:
    """Which of the 26 15-minute slots (0-25) this bar's START time falls
    in, on the 09:30 grid. None outside the regular session."""
    mins = dt.hour * 60 + dt.minute
    if mins < S.SESSION_OPEN_MIN or mins >= S.SESSION_CLOSE_MIN:
        return None
    return (mins - S.SESSION_OPEN_MIN) // S.SLOT_MINUTES


def _session_date(dt: datetime) -> str:
    return dt.date().isoformat()


def volume_profile(bars_20d: list[dict]) -> dict[int, float]:
    """§4.1: one slot per 15 minutes on the 09:30 grid (26 slots). Average
    over the last 20 FULL sessions; a half day (fewer than N_SLOTS bars
    seen for that date) is dropped entirely rather than averaged in and
    quietly deflating every slot after noon.

    Returns {slot_index: avg_volume}. A slot with no sessions contributing
    is simply absent — callers (vol_x) treat a missing slot as "no
    profile", never as zero (a session with a zero-volume slot is never a
    real session)."""
    by_date: dict[str, dict[int, float]] = {}
    for b in bars_20d or []:
        dt = _parse_bar_dt(b)
        if dt is None:
            continue
        slot = _slot_index(dt)
        if slot is None:
            continue
        vol = _f(b.get("volume"))
        if vol is None:
            continue
        day = by_date.setdefault(_session_date(dt), {})
        day[slot] = day.get(slot, 0.0) + vol

    full_sessions = [day for day in by_date.values() if len(day) >= S.N_SLOTS]
    if not full_sessions:
        return {}

    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for day in full_sessions:
        for slot, vol in day.items():
            totals[slot] = totals.get(slot, 0.0) + vol
            counts[slot] = counts.get(slot, 0) + 1
    return {slot: round(totals[slot] / counts[slot], 1) for slot in totals}


def vol_x(today_bars: list[dict], profile: dict[int, float]) -> dict:
    """§4.2: `so_far` = sum of today's volume through the last COMPLETED
    slot, divided by the sum of the profile over those same slots.
    `last_slot` = the last completed slot's own volume ÷ its own profile
    slot. Both None if the profile has no coverage for the slots seen, or
    today has no completed slot yet (never a divide-by-zero guess)."""
    out = {"so_far": None, "last_slot": None}
    if not profile:
        return out
    today_by_slot: dict[int, float] = {}
    for b in today_bars or []:
        dt = _parse_bar_dt(b)
        if dt is None:
            continue
        slot = _slot_index(dt)
        if slot is None:
            continue
        vol = _f(b.get("volume"))
        if vol is None:
            continue
        today_by_slot[slot] = today_by_slot.get(slot, 0.0) + vol
    if not today_by_slot:
        return out

    completed_slots = sorted(today_by_slot)
    today_sum = sum(today_by_slot[s] for s in completed_slots if s in profile)
    profile_sum = sum(profile[s] for s in completed_slots if s in profile)
    if profile_sum > 0:
        out["so_far"] = round(today_sum / profile_sum, 2)

    last_slot = completed_slots[-1]
    last_profile = profile.get(last_slot)
    if last_profile:
        out["last_slot"] = round(today_by_slot[last_slot] / last_profile, 2)
    return out


def hourly(bars_15m: list[dict]) -> list[dict]:
    """§4.3: roll 15-min bars up into completed 1-hour candles on the
    09:30 grid (09:30-10:30, ..., 15:00-16:00 — 6 candles). A candle
    counts ONLY when all four of its 15-minute bars are present; a
    partial hour (e.g. three of four bars, mid-cycle) is never returned —
    callers must see NOT_YET, not a candle built on 75% of the hour."""
    by_hour: dict[int, list[dict]] = {}
    for b in bars_15m or []:
        dt = _parse_bar_dt(b)
        if dt is None:
            continue
        mins = dt.hour * 60 + dt.minute
        if mins < S.SESSION_OPEN_MIN or mins >= S.SESSION_CLOSE_MIN:
            continue
        hour_start = S.SESSION_OPEN_MIN + ((mins - S.SESSION_OPEN_MIN) // 60) * 60
        by_hour.setdefault(hour_start, []).append(b)

    candles = []
    for hour_start in sorted(by_hour):
        bars = sorted(by_hour[hour_start], key=lambda b: b.get("date", ""))
        if len(bars) < 4:
            continue  # partial hour — never used (§4.3)
        opens = _f(bars[0].get("open"))
        closes = _f(bars[-1].get("close"))
        highs = [h for h in (_f(b.get("high")) for b in bars) if h is not None]
        lows = [lo for lo in (_f(b.get("low")) for b in bars) if lo is not None]
        vols = [v for v in (_f(b.get("volume")) for b in bars) if v is not None]
        if opens is None or closes is None or not highs or not lows:
            continue
        candles.append({
            "hour_start_min": hour_start,
            "open": opens, "high": max(highs), "low": min(lows), "close": closes,
            "volume": sum(vols) if vols else None,
        })
    return candles


def opening_range(bars_15m: list[dict]) -> dict | None:
    """High/low of the FIRST 15-minute bar of today's regular session (the
    09:30 bar). The U&R write-up uses a 5-minute opening range; FMP's
    intraday feed here is 15-minute, so this is the opening 15 minutes and
    the card says so. None before the first bar exists."""
    first = None
    for b in bars_15m or []:
        dt = _parse_bar_dt(b)
        if dt is None or dt.hour * 60 + dt.minute != S.SESSION_OPEN_MIN:
            continue
        first = b
        break
    if first is None:
        return None
    hi, lo = _f(first.get("high")), _f(first.get("low"))
    if hi is None or lo is None:
        return None
    return {"high": hi, "low": lo}


def session_vwap(hourly_candles: list[dict]) -> dict:
    """§4.4: sum(typical x volume) / sum(volume) over today's completed
    hourly candles, typical = (H+L+C)/3. `provisional: True` before
    VWAP_MIN_CANDLES (2) candles are in — the handoff's own rule, not a
    gate this module invents. Returns {vwap, provisional, n_candles};
    `vwap` is None if there is nothing to sum yet."""
    n = len(hourly_candles or [])
    out = {"vwap": None, "provisional": True, "n_candles": n}
    if n == 0:
        return out
    num = den = 0.0
    for c in hourly_candles:
        vol = c.get("volume")
        if vol is None:
            continue
        typical = (c["high"] + c["low"] + c["close"]) / 3.0
        num += typical * vol
        den += vol
    if den > 0:
        out["vwap"] = round(num / den, 4)
    out["provisional"] = n < S.VWAP_MIN_CANDLES
    return out


def vwap_trigger(bars_15m: list[dict]) -> dict:
    """Valen's entry trigger on the finest bars we have (15-minute; his chart
    uses 5-minute -- FMP's feed here is 15-minute and delayed). VWAP is
    cumulative from the open over every bar so far. Reads the latest bar:

      TRIGGERED  its close is above the VWAP AND an earlier bar today closed
                 under it: the candle that reclaimed VWAP. `at` = that bar's
                 close time, `entry` = its close.
      ABOVE      above VWAP since the first bar: nothing to reclaim, no trigger.
      WAIT       its close is under VWAP ("below VWAP: wait").
      NOT_READY  no usable bars yet.
    Figures and a state, never an instruction."""
    from datetime import timedelta
    rows = []
    cum_pv = cum_v = 0.0
    parsed = []
    for b in bars_15m or []:
        dt = _parse_bar_dt(b)
        if dt is None:
            continue
        mins = dt.hour * 60 + dt.minute
        if mins < S.SESSION_OPEN_MIN or mins >= S.SESSION_CLOSE_MIN:
            continue
        parsed.append((dt, b))
    parsed.sort(key=lambda x: x[0])
    for dt, b in parsed:
        h, lo, c, v = (_f(b.get("high")), _f(b.get("low")), _f(b.get("close")),
                       _f(b.get("volume")))
        if None in (h, lo, c, v):
            continue
        cum_pv += (h + lo + c) / 3.0 * v
        cum_v += v
        if cum_v > 0:
            rows.append((dt, c, cum_pv / cum_v))
    if not rows:
        return {"state": "NOT_READY"}
    last_dt, last_c, last_vw = rows[-1]
    out = {"vwap": round(last_vw, 2), "last_close": round(last_c, 2)}
    if last_c <= last_vw:
        out["state"] = "WAIT"
        return out
    i = len(rows) - 1
    while i > 0 and rows[i - 1][1] > rows[i - 1][2]:
        i -= 1
    if i == 0:
        # Above VWAP since the very first bar: there was no "below VWAP: wait"
        # to reclaim, so no trigger candle. (With one bar in, VWAP is just that
        # bar's own average, so "above" would be true for half of all names.)
        out["state"] = "ABOVE"
        return out
    cross_dt, cross_c, _ = rows[i]
    out.update({"state": "TRIGGERED", "was_below": True, "entry": round(cross_c, 2),
                "at": (cross_dt + timedelta(minutes=15)).strftime("%H:%M")})
    return out


def heat_row(today_bars: list[dict], profile: dict[int, float]) -> list[float | None]:
    """§4.5: each COMPLETED hour's volume ÷ its own normal hour (the sum
    of that hour's 4 profile slots) — one value per hourly bucket, for the
    after-close volume heatmap. None for an hour with no profile
    coverage, never a fabricated 1.0."""
    today_by_slot: dict[int, float] = {}
    for b in today_bars or []:
        dt = _parse_bar_dt(b)
        if dt is None:
            continue
        slot = _slot_index(dt)
        if slot is None:
            continue
        vol = _f(b.get("volume"))
        if vol is None:
            continue
        today_by_slot[slot] = today_by_slot.get(slot, 0.0) + vol

    row: list[float | None] = []
    n_hours = (S.SESSION_CLOSE_MIN - S.SESSION_OPEN_MIN) // 60
    slots_per_hour = 60 // S.SLOT_MINUTES
    for h in range(n_hours):
        slots = range(h * slots_per_hour, (h + 1) * slots_per_hour)
        hour_today = sum(today_by_slot.get(s, 0.0) for s in slots if s in today_by_slot)
        hour_profile = sum(profile.get(s, 0.0) for s in slots if s in profile)
        have_all_slots = all(s in today_by_slot for s in slots)
        if hour_profile > 0 and have_all_slots:
            row.append(round(hour_today / hour_profile, 2))
        else:
            row.append(None)
    return row


def rs_today(quote: dict, spy_quote: dict) -> float | None:
    """§4.6: the stock's %-change today minus SPY's. None if either side
    can't compute a change (no prev_close), never defaulting the missing
    side to zero."""
    def chg(q):
        price, prev = _f((q or {}).get("price")), _f((q or {}).get("prev_close"))
        if price is None or not prev:
            return None
        return (price / prev - 1.0) * 100.0

    a, b = chg(quote), chg(spy_quote)
    if a is None or b is None:
        return None
    return round(a - b, 3)
