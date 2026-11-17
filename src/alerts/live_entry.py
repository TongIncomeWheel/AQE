"""VALEN entry layer, intraday half (PM 2026-11-17): Valen's entry methods as facts on the live card.

Pure functions over the 15-minute bars the cycle already fetched (no new FMP call, no network, no file access). Valen's own charts are 1 and 5
minute; our feed is 15-minute and delayed, and every readout says so. Facts and booleans only: nothing here gates an alert, sizes a trade or
places an order.

  volume_gate   share of a NORMAL day's volume traded by Valen's two marks (20% by 09:35, 40% by 10:00), read at the first completed 15-minute bar
                at or after each mark (09:45, 10:00). PASS / FAIL / NOT_YET / UNKNOWN (no volume profile is UNKNOWN, never a pass).
  pivot_30m     undercut-and-rally entry b: after a 30-minute candle undercuts the daily level, the FIRST GREEN 30-minute candle after it sets the
                pivot (its high) and the stop (its low). TRIGGERED when a later bar breaks the pivot. 30-minute candles are exact pairs of 15-minute bars.
  orb           the opening-range break. SHADOW MODE (PM 2026-11-17: log only, no email, until the PM says go): it is returned under `shadow`
                and written to the condition ledger line, never to a card.
  build         one call for the cycle: {"visible": {stop_fit, volume_gate, pivot_30m}, "shadow": {orb}}.
"""

from __future__ import annotations

from datetime import datetime

from src.valen import entry as VE
from src.valen import spec as VS

from . import condition_spec as S
from . import live_measures as LM

NOT_YET, PASS, FAIL, UNKNOWN = "NOT_YET", "PASS", "FAIL", "UNKNOWN"


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _by_slot(bars: list[dict]) -> dict[int, dict]:
    """{slot: bar} for today's regular-session 15-minute bars (the last bar wins on a duplicate)."""
    out = {}
    for b in bars or []:
        dt = LM._parse_bar_dt(b)
        if dt is None:
            continue
        slot = LM._slot_index(dt)
        if slot is None:
            continue
        out[slot] = b
    return out


def volume_gate(today_bars: list[dict], profile: dict[int, float] | None) -> dict:
    """Share of a normal day's volume at each of Valen's marks. A mark with no completed bar yet is NOT_YET; no profile is UNKNOWN."""
    res = {"state": UNKNOWN, "marks": [], "resolution": "15-minute bars: the 09:35 mark is read at the 09:45 bar", "reason": None}
    if not profile:
        res["reason"] = "no 20-day volume profile for this name"
        return res
    normal_day = sum(profile.values())
    if normal_day <= 0:
        res["reason"] = "the volume profile sums to zero"
        return res
    slots = _by_slot(today_bars)
    for mark, need in VS.ENTRY_VOLUME_MARKS:
        # first completed bar at or after the mark: the bar that STARTS at or after (mark - 15 minutes), ending at or after the mark
        read_slot = max(0, -(-(_mins(mark) - S.SESSION_OPEN_MIN) // S.SLOT_MINUTES) - 1)
        have = [slots[k] for k in range(read_slot + 1) if k in slots]
        row = {"mark": mark, "read_at": _slot_end(read_slot), "need": need, "share": None, "state": NOT_YET}
        if len(have) == read_slot + 1:
            vol = sum(LM._f(b.get("volume")) or 0.0 for b in have)
            row["share"] = round(vol / normal_day, 3)
            row["state"] = PASS if row["share"] >= need else FAIL
        res["marks"].append(row)
    done = [m for m in res["marks"] if m["state"] != NOT_YET]
    res["state"] = done[-1]["state"] if done else NOT_YET        # the latest mark that can be read speaks
    return res


def _slot_end(slot: int) -> str:
    m = S.SESSION_OPEN_MIN + (slot + 1) * S.SLOT_MINUTES
    return f"{m // 60:02d}:{m % 60:02d}"


def candles_30m(bars_15m: list[dict]) -> list[dict]:
    """Completed 30-minute candles on the 09:30 grid (an exact pair of 15-minute bars each); a half-built candle is not returned."""
    slots = _by_slot(bars_15m)
    out = []
    for k in range(0, S.N_SLOTS - 1, 2):
        a, b = slots.get(k), slots.get(k + 1)
        if a is None or b is None:
            continue
        vals = [LM._f(x.get(f)) for x in (a, b) for f in ("open", "high", "low", "close")]
        if None in vals:
            continue
        out.append({"slot": k // 2, "start": _slot_end(k - 1) if k else "09:30", "open": vals[0], "close": vals[7],
                    "high": max(vals[1], vals[5]), "low": min(vals[2], vals[6]), "green": vals[7] > vals[0]})
    return out


def pivot_30m(bars_15m: list[dict], level: float | None, atr: float | None = None) -> dict:
    """Undercut-and-rally entry b. `level` is the daily support level that was undercut. States: NO_LEVEL, NO_UNDERCUT, WAIT_GREEN, ARMED, TRIGGERED."""
    if level is None:
        return {"state": "NO_LEVEL", "reason": "no daily level to measure the undercut against"}
    cs = candles_30m(bars_15m)
    cut = next((i for i, c in enumerate(cs) if c["low"] < level), None)
    if cut is None:
        return {"state": "NO_UNDERCUT", "level": round(level, 2)}
    green = next((c for c in cs[cut + 1:] if c["green"]), None)
    if green is None:
        return {"state": "WAIT_GREEN", "level": round(level, 2), "undercut_low": round(cs[cut]["low"], 2)}
    pivot, low = green["high"], green["low"]
    out = {"state": "ARMED", "level": round(level, 2), "pivot": round(pivot, 2), "stop": round(low - VS.ENTRY_TICK, 2),
           "candle": green["start"], "entry": round(pivot + VS.ENTRY_TICK, 2)}
    later = [b for b in (bars_15m or []) if _after(b, green)]
    if any((LM._f(b.get("high")) or 0.0) > pivot for b in later):
        out["state"] = "TRIGGERED"
    if atr:
        out["stop_fit"] = VE.stop_fit(out["entry"], low, atr)
    return out


def _after(bar: dict, candle: dict) -> bool:
    dt = LM._parse_bar_dt(bar)
    if dt is None:
        return False
    slot = LM._slot_index(dt)
    return slot is not None and slot >= (candle["slot"] + 1) * 2


READY_FAMILIES = ("vcp", "high tight", "episodic")      # the setups Daily marks READY that the opening-range break applies to (PM 2026-11-17)


def ready_pivot(setups: list[dict] | None) -> dict | None:
    """The READY grade (VCP, high tight flag, episodic pivot) with a pivot, from the row's `setups` block; None when the name is not READY."""
    for g in setups or []:
        nm = str(g.get("setup") or "").lower()
        if g.get("status") == "READY" and g.get("pivot") is not None and any(f in nm for f in READY_FAMILIES):
            return {"setup": g["setup"], "pivot": float(g["pivot"])}
    return None


def orb(bars_15m: list[dict], pivot: float | None = None, volume_state: str | None = None) -> dict:
    """Opening-range break on the opening 15 minutes (Valen's is 5; stated). SHADOW ONLY. States: NOT_READY, INSIDE, BROKE_UP, BROKE_DOWN.
    For a name Daily marks READY, `orb_break` (state ORB_BREAK) = the break is up, price is above the daily pivot and the volume gate is PASS."""
    rng = LM.opening_range(bars_15m)
    if rng is None:
        return {"state": "NOT_READY", "basis": "opening 15 minutes (Valen: 5)"}
    slots = _by_slot(bars_15m)
    later = [slots[k] for k in sorted(slots) if k >= 1]
    state, at = "INSIDE", None
    for b in later:                                        # the FIRST bar that closes outside the range decides; Valen buys the break, so up wins a tie
        c = LM._f(b.get("close"))
        if c is None:
            continue
        if c > rng["high"]:
            state, at = "BROKE_UP", b.get("date")
            break
        if c < rng["low"]:
            state, at = "BROKE_DOWN", b.get("date")
            break
    out = {"state": state, "high": rng["high"], "low": rng["low"], "at": at, "basis": "opening 15 minutes (Valen: 5)"}
    if pivot is not None:
        last = LM._f((later[-1] if later else {}).get("close"))
        out.update({"daily_pivot": round(pivot, 2), "above_pivot": bool(last is not None and last > pivot), "volume_gate": volume_state,
                    "orb_break": bool(state == "BROKE_UP" and last is not None and last > pivot and volume_state == PASS)})
        if out["orb_break"]:
            out["state"] = "ORB_BREAK"
    return out


def build(today_bars: list[dict], profile: dict[int, float] | None, spot: float | None, day_low: float | None, atr: float | None,
          level: float | None = None, pivot: float | None = None) -> dict:
    """The cycle's one call. Never raises: each part is wrapped so one failure is one `error` line, not a lost card."""
    vis: dict = {}
    for key, fn in (("stop_fit", lambda: VE.stop_fit(spot, day_low, atr)),
                    ("volume_gate", lambda: volume_gate(today_bars, profile)),
                    ("pivot_30m", lambda: pivot_30m(today_bars, level, atr))):
        try:
            vis[key] = fn()
        except Exception as exc:  # noqa: BLE001
            vis[key] = {"state": "ERROR", "fit": "NA", "reason": f"{type(exc).__name__}: {exc}"}
    try:
        shadow = {"orb": orb(today_bars, pivot, (vis.get("volume_gate") or {}).get("state"))}
    except Exception as exc:  # noqa: BLE001
        shadow = {"orb": {"state": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}}
    return {"visible": vis, "shadow": shadow}


def plain_line(vis: dict | None) -> str | None:
    """One plain card line from the visible facts; None when there is nothing to say."""
    if not vis:
        return None
    bits = []
    sf = vis.get("stop_fit") or {}
    if sf.get("fit") not in (None, VE.NA):
        word = {VE.GOOD: "a good fit", VE.OK: "inside the cap", VE.TOO_FAR: "too far, Valen skips it"}[sf["fit"]]
        bits.append(f"stop is {sf['atr_multiple']:.2f} daily ranges away ({word})")
    vg = vis.get("volume_gate") or {}
    for m in vg.get("marks") or []:
        if m["state"] in (PASS, FAIL):
            bits.append(f"volume {m['share'] * 100:.0f}% of a normal day by {m['read_at']} (needs {m['need'] * 100:.0f}%, {'passed' if m['state'] == PASS else 'short'})")
    pv = vis.get("pivot_30m") or {}
    if pv.get("state") in ("ARMED", "TRIGGERED"):
        bits.append(f"30-minute pivot {pv['pivot']:.2f} ({'broken' if pv['state'] == 'TRIGGERED' else 'not broken yet'}), its stop {pv['stop']:.2f}")
    elif pv.get("state") == "WAIT_GREEN":
        bits.append("30-minute pivot: waiting for the first green 30-minute candle after the dip")
    return ("Entry check: " + "; ".join(bits)) if bits else None
