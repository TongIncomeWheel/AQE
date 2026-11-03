#!/usr/bin/env python3
"""mtf.py -- the WEEKLY / DAILY / 1-HOUR grid for the room (R39, PM 2026-11-02).

PM: "An alternative suggestion maybe is to force a multi timeframe look (weekly, daily, 1hour)." ... "Agree,
implement it." Every tier-1 ruling and every tier-2 trigger carries this grid. The seats' own canons are
multi-timeframe (Elder's Triple Screen; O'Neil and Minervini judge the base on the weekly; Wyckoff reads
structure across frames; Raschke times on the lower frame), so this is information each voice uses by its own
method. On 2 Nov MA's daily breakout was 6% extended on the weekly -- the fact that settles ADVANCE vs WATCH --
and no packet carried it.

  build   mtf_bars/<T>.json (transcribed from FMP by a data-steward courier) + phase4.json + the export
          -> mtf.json. One row per deliberation_set name, ALWAYS: a name with no bars, an `unserved` flag, too
          few bars or stale bars is declared NOT SERVED with its reason -- never a neutral reading. A name with
          SOME frames shows them and labels the others a GAP (served: true, complete: false, gaps: [...]).

Input per name, mtf_bars/<T>.json:
  {"daily": [{"date": "YYYY-MM-DD", "open", "high", "low", "close", "volume"}, ...],   any order; sorted here
   "h1":    [{"date": "YYYY-MM-DD HH:MM:SS", ...}, ...],
   "m15":   [{"date": "YYYY-MM-DD HH:MM:SS", ...}, ...],                              optional: 15-minute bars
   "unserved": true}                                                                  optional

`m15` is rolled up HERE (rollup_hourly) into :30-anchored 1-hour bars -- 09:30, 10:30 ... 15:30 ET, the last one
the 30-minute close -- when the file carries no `h1` (a courier that cannot save FMP's hourly output to a file can
save the 15-minute pulls instead). open = first, high = max, low = min, close = last, volume = sum; a bucket with
fewer than 2 of its 15-minute bars is dropped and counted, never passed off as a full hour. Checked against FMP's
own native hourly bars on MP, 2 Nov 2026 (tests/fixtures/fmp_mp): open / high / low / close identical in all 7
buckets; volume identical in 6 of 7 -- the 09:30 bucket sums to 676,274 from the 15-minute bars against 583,974 in
FMP's hourly bar (FMP's hourly leaves out volume the 15-minute opening bar carries). Nothing in the grid reads
volume, so no reading changes; the native `1hour` pull is preferred and this roll-up is the fallback.

  build --grid mtf_grid.json   (3 Nov 2026) take each room name's row from the grid the daily AQE run already
          computed for the whole export (src/pipeline/committee_data.py) instead of from courier-written bars.
          A grid that is missing, malformed or for another run date is a hard stop (exit 2) so the conductor
          falls back to the courier loudly; a room name the grid does not hold is declared NOT SERVED.

Per frame (W = weekly bars built from the daily by ISO week; D = daily; H1 = 1-hour):
  close, ema9, ema21 (EMA over closes, alpha 2/(n+1), seeded with the SMA of the first n closes; needs >= 21
  bars, else the frame is served: false with the reason), ema_order "9>21" / "9<21" / "9=21", close_vs_ema9
  "above" / "below", last_bar "green" / "red" / "flat", hh_hl_3 over the last 3 completed bars "HH/HL" /
  "LH/LL" / "mixed", dist_to_20bar_high_pct (how far the close sits under the highest high of the last 20 bars),
  and on H1 pos_in_day_range_pct (the last close inside the last session's H1 high-low, 0 = low, 100 = high).

Every served frame also carries `summary`: its reading WITHOUT the W / D / H1 label (the packet, the claims board
and the tier-2 packets print "W <summary> | D <summary> | H1 <summary>" and add the label themselves). The name row
keeps the joined, labelled `summary` for reading the file by eye. (3 Nov 2026: build wrote only the joined one, so
every name printed "W not served | D not served | H1 not served" the moment real bars arrived.)

Deterministic, pure python (no pandas, like every pma tool). It forms no opinion: no score, no verdict, no
"bullish". Bars dated after --date are dropped (never a look-ahead) and counted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

SCHEMA = "mtf.v1"
FRAMES = ("W", "D", "H1")
EMA_FAST, EMA_SLOW = 9, 21
MIN_BARS = EMA_SLOW
HIGH_LOOKBACK = 20
STALE_DAYS = 6          # a last daily bar more than 6 calendar days before the run is stale = NOT SERVED
CLOSE_TOL = 0.005       # last daily close vs the export's close: 0.5% before it is declared a mismatch
UNIT = {"W": "wk", "D": "day", "H1": "hr"}


def _load(p, default=None):
    if not p or not os.path.exists(p):
        if default is not None:
            return default
        sys.exit(f"mtf: required file missing: {p}")
    with open(p) as f:
        return json.load(f)


# ----------------------------------------------------------------------------------------- maths
def ema(closes, n):
    """EMA over closes: SMA of the first n closes as the seed, then alpha = 2 / (n + 1). None if < n closes."""
    if len(closes) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(closes[:n]) / n
    for c in closes[n:]:
        e = c * k + e * (1 - k)
    return e


def _num(b, k):
    v = b.get(k)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _clean(bars):
    """Bars with all four prices numeric, sorted by date string (ISO dates sort lexically)."""
    out = []
    for b in bars or []:
        if not isinstance(b, dict) or not isinstance(b.get("date"), str):
            continue
        o, h, l, c = (_num(b, k) for k in ("open", "high", "low", "close"))
        if None in (o, h, l, c):
            continue
        out.append({"date": b["date"], "open": o, "high": h, "low": l, "close": c,
                    "volume": _num(b, "volume") or 0.0})
    out.sort(key=lambda b: b["date"])
    return out


def weekly(daily):
    """ISO-week bars from daily bars (sorted): open = first, high = max, low = min, close = last, volume = sum.
    A week bar is dated by its last session."""
    out, key = [], None
    for b in daily:
        y, w, _ = dt.date.fromisoformat(b["date"][:10]).isocalendar()
        if (y, w) != key:
            key = (y, w)
            out.append(dict(b, week=f"{y}-W{w:02d}"))
        else:
            cur = out[-1]
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]
            cur["volume"] += b["volume"]
            cur["date"] = b["date"]
    return out


SESSION_OPEN_MIN = 9 * 60 + 30      # 09:30 ET, in minutes from midnight
SESSION_CLOSE_MIN = 16 * 60         # 16:00 ET
MIN_M15_PER_HOUR = 2                # a :30 bucket needs at least this many 15-minute bars to be a bar at all


def rollup_hourly(m15):
    """15-minute bars (cleaned, sorted) -> :30-anchored 1-hour bars. Returns (bars, dropped).
    Only regular-session bars (09:30 <= start < 16:00) count; the rest are `dropped`, as are buckets thinner than
    MIN_M15_PER_HOUR (the 15:30 bucket is a half hour by design and carries exactly 2)."""
    buckets, dropped = {}, 0
    for b in m15:
        d = b["date"]
        if len(d) < 16 or d[10] not in (" ", "T"):
            dropped += 1                      # no time of day: not an intraday bar
            continue
        try:
            mins = int(d[11:13]) * 60 + int(d[14:16])
        except ValueError:
            dropped += 1
            continue
        if not SESSION_OPEN_MIN <= mins < SESSION_CLOSE_MIN:
            dropped += 1
            continue
        start = SESSION_OPEN_MIN + (mins - SESSION_OPEN_MIN) // 60 * 60
        buckets.setdefault((d[:10], start), []).append(b)
    out = []
    for (day, start), bs in sorted(buckets.items()):
        if len(bs) < MIN_M15_PER_HOUR:
            dropped += len(bs)
            continue
        bs.sort(key=lambda x: x["date"])
        out.append({"date": f"{day} {start // 60:02d}:{start % 60:02d}:00", "open": bs[0]["open"],
                    "high": max(x["high"] for x in bs), "low": min(x["low"] for x in bs),
                    "close": bs[-1]["close"], "volume": sum(x["volume"] for x in bs)})
    return out, dropped


def _hh_hl(bars):
    if len(bars) < 3:
        return None
    a, b, c = bars[-3:]
    if a["high"] < b["high"] < c["high"] and a["low"] < b["low"] < c["low"]:
        return "HH/HL"
    if a["high"] > b["high"] > c["high"] and a["low"] > b["low"] > c["low"]:
        return "LH/LL"
    return "mixed"


def frame(bars, tf, completed=None):
    """One frame of the grid. `completed` = the bars hh_hl_3 may read (default: all of them)."""
    if len(bars) < MIN_BARS:
        return {"served": False, "bars": len(bars),
                "reason": f"only {len(bars)} {UNIT[tf]} bars; EMA21 needs {MIN_BARS}"}
    closes = [b["close"] for b in bars]
    last = bars[-1]
    e9, e21 = ema(closes, EMA_FAST), ema(closes, EMA_SLOW)
    hi20 = max(b["high"] for b in bars[-HIGH_LOOKBACK:])
    f = {"served": True, "bars": len(bars), "last_bar_date": last["date"],
         "close": round(last["close"], 4), "ema9": round(e9, 4), "ema21": round(e21, 4),
         "ema_order": "9>21" if e9 > e21 else ("9<21" if e9 < e21 else "9=21"),
         "close_vs_ema9": "above" if last["close"] >= e9 else "below",
         "last_bar": "green" if last["close"] > last["open"] else ("red" if last["close"] < last["open"] else "flat"),
         "hh_hl_3": _hh_hl(completed if completed is not None else bars),
         "high_20bar": round(hi20, 4),
         "dist_to_20bar_high_pct": round((hi20 - last["close"]) / hi20 * 100, 2) if hi20 > 0 else None}
    if tf == "H1":
        day = last["date"][:10]
        sess = [b for b in bars if b["date"][:10] == day]
        hi, lo = max(b["high"] for b in sess), min(b["low"] for b in sess)
        f["session"] = day
        f["pos_in_day_range_pct"] = round((last["close"] - lo) / (hi - lo) * 100, 1) if hi > lo else None
    return f


def frame_text(tf, f):
    """The frame's reading, WITHOUT its W / D / H1 label -- what the per-frame `summary` holds."""
    if not f.get("served"):
        return f"NOT SERVED ({f.get('reason')})"
    d = f.get("dist_to_20bar_high_pct")
    hi = "at the 20-" + UNIT[tf] + " high" if d is not None and d <= 0 else (
        f"{d:.1f}% under 20-{UNIT[tf]} high" if d is not None else "no 20-bar high")
    parts = [f"{f['close_vs_ema9']} EMA9", f["ema_order"], f.get("hh_hl_3") or "fewer than 3 bars", hi]
    if tf == "H1" and f.get("pos_in_day_range_pct") is not None:
        parts.append(f"{f['pos_in_day_range_pct']:.0f}% of the day's range")
    if f.get("partial_last_bar"):
        parts.append("this week still open")
    return ", ".join(parts)


def frame_summary(tf, f):
    """The labelled form ("W: above EMA9, ...") used in the name-level summary."""
    return f"{tf}: {frame_text(tf, f)}"


# ------------------------------------------------------------------------------------------ build
def _not_served(reason):
    return {"served": False, "complete": False, "gaps": list(FRAMES), "reason": reason,
            **{tf: {"served": False, "reason": reason, "summary": f"NOT SERVED ({reason})"} for tf in FRAMES},
            "summary": f"MTF NOT SERVED: {reason}"}


def build_name(t, doc, run_date, export_close=None):
    if doc is None:
        return _not_served(f"no bars file for {t} (mtf_bars/{t}.json)")
    if doc.get("unserved"):
        return _not_served("the courier declared it unserved (FMP returned no bars)")
    daily, h1 = _clean(doc.get("daily")), _clean(doc.get("h1"))
    rolled_dropped = 0
    if not h1 and doc.get("m15"):
        h1, rolled_dropped = rollup_hourly(_clean(doc.get("m15")))
    dropped = sum(1 for b in daily if b["date"][:10] > run_date) + sum(1 for b in h1 if b["date"][:10] > run_date)
    daily = [b for b in daily if b["date"][:10] <= run_date]
    h1 = [b for b in h1 if b["date"][:10] <= run_date]
    if not daily and not h1:
        return _not_served("the bars file holds no usable bars")
    run = dt.date.fromisoformat(run_date)
    row = {}
    stale = None
    if daily:
        age = (run - dt.date.fromisoformat(daily[-1]["date"][:10])).days
        if age > STALE_DAYS:
            stale = f"last daily bar {daily[-1]['date']} is {age} days before the run -- stale, not a reading"
    if stale:
        row["W"] = {"served": False, "reason": stale}
        row["D"] = {"served": False, "reason": stale}
    else:
        wk = weekly(daily)
        # A week that is still open on the run date is a partial bar: it is the latest reading, but the
        # higher-high / higher-low test reads only completed weeks.
        partial = bool(wk) and wk[-1]["week"] == "{}-W{:02d}".format(*run.isocalendar()[:2])
        row["W"] = frame(wk, "W", completed=wk[:-1] if partial else wk)
        if partial and row["W"].get("served"):
            row["W"]["partial_last_bar"] = True
        row["D"] = frame(daily, "D")
    if h1:
        age = (run - dt.date.fromisoformat(h1[-1]["date"][:10])).days
        row["H1"] = ({"served": False, "reason": f"last 1-hour bar {h1[-1]['date']} is {age} days before the run -- stale"}
                     if age > STALE_DAYS else frame(h1, "H1"))
    else:
        row["H1"] = {"served": False, "reason": "no 1-hour bars"}
    if row["D"].get("served") and isinstance(export_close, (int, float)) and export_close > 0:
        c = row["D"]["close"]
        row["D"]["export_close"] = export_close
        row["D"]["close_matches_export"] = abs(c / export_close - 1) <= CLOSE_TOL
    missing = [tf for tf in FRAMES if not row[tf].get("served")]
    # PM 2026-11-03: a name missing one timeframe SHOWS the others, the missing one labelled as a gap -- it is
    # served if any frame is; `complete` says all three are, `gaps` names the ones that are not. A frame with no
    # reading is never invented, and a name with no frame at all is still NOT SERVED (declared).
    row["served"] = len(missing) < len(FRAMES)
    row["complete"] = not missing
    row["gaps"] = missing
    row["frames_served"] = [tf for tf in FRAMES if tf not in missing]
    row["reason"] = ("; ".join(f"{tf} not served: {row[tf].get('reason')}" for tf in missing) or None)
    if dropped:
        row["dropped_future_bars"] = dropped
    if rolled_dropped:
        row["m15_bars_not_used"] = rolled_dropped
    for tf in FRAMES:                       # the packet / claims board / tier-2 packets read THIS, label added by them
        row[tf]["summary"] = frame_text(tf, row[tf])
    row["summary"] = " | ".join(frame_summary(tf, row[tf]) for tf in FRAMES)
    return row


def _load_grid(path, run_date):
    """The precomputed grid, or a hard stop: a stale / broken grid must send the conductor to the courier
    fallback loudly, never feed the seats a quietly wrong reading."""
    def stop(why):
        print(f"mtf: {why} -- use the courier fallback", file=sys.stderr)
        raise SystemExit(2)
    try:
        g = _load(path)
    except (ValueError, OSError, SystemExit) as e:
        stop(f"grid {path} unreadable ({e})")
    if g.get("schema") != "mtf_grid.v1" or not isinstance(g.get("names"), dict):
        stop(f"grid {path} is not mtf_grid.v1")
    if str(g.get("run_date"))[:10] != run_date:
        stop(f"grid {path} is for run date {g.get('run_date')}, this run is {run_date} -- stale")
    return g


def cmd_build(a):
    p4 = _load(a.phase4)
    room = list(p4.get("deliberation_set") or [])
    if not room:
        sys.exit("mtf: phase4 has no deliberation_set -- refusing to write an empty grid")
    if getattr(a, "grid", None):
        g = _load_grid(a.grid, a.date)
        names = {t: (g["names"].get(t) or _not_served(f"{t} is not in the fetched grid ({len(g['names'])} names; fetched {g.get('generated_at')})"))
                 for t in room}
        _write_grid_out(a, room, names, extra={"source": "mtf_grid.json", "grid_generated_at": g.get("generated_at"),
                                               "grid_manifest_sha256": g.get("sha256_of_names")})
        return
    ex = _load(a.export, {}) if a.export else {}
    closes = {r.get("ticker"): r.get("entry") for r in (ex.get("daily_list") or []) if isinstance(r, dict)}
    names = {}
    for t in room:
        p = os.path.join(a.bars, f"{t}.json")
        doc = None
        if os.path.exists(p):
            try:
                doc = _load(p)
            except (ValueError, OSError) as e:
                names[t] = _not_served(f"bars file unreadable: {e}")
                continue
        names[t] = build_name(t, doc, a.date, closes.get(t))
    extra = sorted(f[:-5] for f in (os.listdir(a.bars) if os.path.isdir(a.bars) else [])
                   if f.endswith(".json") and f[:-5] not in names)
    _write_grid_out(a, room, names, extra={"bars_files_not_in_room": extra})


def _write_grid_out(a, room, names, extra=None):
    extra = extra or {}
    mism = sorted(t for t, r in names.items() if r.get("D", {}).get("close_matches_export") is False)
    out = {"schema": SCHEMA, "date": a.date, "frames": list(FRAMES),
           "rule": "R39: every room name has a row; a frame without enough bars is NOT SERVED, never a neutral reading",
           "names": names,
           "measurement": {"room": len(room),
                           "served": sum(1 for r in names.values() if r["served"]),
                           "complete": sum(1 for r in names.values() if r.get("complete")),
                           "partial": sum(1 for r in names.values() if r["served"] and not r.get("complete")),
                           "partial_names": sorted(t for t, r in names.items() if r["served"] and not r.get("complete")),
                           "not_served": sum(1 for r in names.values() if not r["served"]),
                           "not_served_names": sorted(t for t, r in names.items() if not r["served"]),
                           "close_mismatch_vs_export": mism, **extra}}
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    m = out["measurement"]
    print(f"wrote {a.out}: {m['room']} room names, {m['complete']} complete, {m['partial']} with a gap"
          + (f" ({' '.join(m['partial_names'])})" if m["partial_names"] else "")
          + f", {m['not_served']} NOT SERVED"
          + (f" ({' '.join(m['not_served_names'])})" if m["not_served_names"] else "")
          + (f"; close differs from the export on {' '.join(mism)}" if mism else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="mtf_bars/ + phase4.json + export -> mtf.json (W / D / H1 grid per room name)")
    b.add_argument("--bars", default="mtf_bars", help="directory of <TICKER>.json bar files from the courier")
    b.add_argument("--phase4", default="phase4.json")
    b.add_argument("--export", default="aqe_daily_export.json", help="cross-checks the last daily close per name")
    b.add_argument("--date", required=True, help="run date YYYY-MM-DD; bars dated after it are dropped")
    b.add_argument("--out", default="mtf.json")
    b.add_argument("--grid", default=None, help="mtf_grid.json from the daily AQE run: take the room's rows from it instead of from --bars")
    b.set_defaults(fn=cmd_build)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
