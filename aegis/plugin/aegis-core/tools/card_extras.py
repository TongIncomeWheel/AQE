#!/usr/bin/env python3
"""card_extras.py -- code-built, information-only extras for the Cards and the brief (PM 2026-11-05).

  1. the weekly / daily / hourly STRIP on every card, built from mtf.json (swing class, average order, distance to the latest swing high);
  2. the UPTREND structure (weekly AND daily HH/HL) with the daily close's distance from the latest daily swing high in daily ranges (ATR), banded by ATR_NEAR / ATR_FAR;
  3. the U&R reference: one line on each card and a table for the brief, from the AQE export's unr_status / unr_level / unr_note.

None of it is a gate, a vote input or a verdict change (R1). A missing fact is said, never filled: no mtf row = no strip claim; no U&R fields =
"not in this export". Plain words only (no raw field names), so the cards' plain-words gate passes.

CLI:  card_extras.py unr-table --export aqe_daily_export.json --consensus consensus.json [--held-from-export] --date YYYY-MM-DD --out unr_table.md
"""
from __future__ import annotations

import argparse
import json
import sys

SWING_WORDS = {"HH": "higher highs", "LH": "lower highs", "EH": "equal highs", "HL": "higher lows", "LL": "lower lows", "EL": "equal lows"}
FRAME_NAME = {"W": "Weekly", "D": "Daily", "H1": "Hourly"}
UNIT = {"W": "week", "D": "day", "H1": "hour"}
FAR_ABOVE_LINE_PCT = 5.0       # PM 2026-11-05: a last close more than this far above the U&R support line = "no useful U&R reference"


def swing_plain(cls):
    if not cls:
        return "no clear swing structure"
    if "/" in cls:
        a, b = cls.split("/")
        return f"{SWING_WORDS[a]} and {SWING_WORDS[b]}"
    a, b = cls.split(" but ")
    return f"{SWING_WORDS[a]} but {SWING_WORDS[b]}"


def frame_plain(tf, f):
    """One frame in plain words: 'Weekly: higher highs and higher lows; fast average above slow; 0.5% above the last swing high.'"""
    name = FRAME_NAME[tf]
    if not isinstance(f, dict) or not f.get("served"):
        return f"{name}: not served"
    parts = [swing_plain(f.get("swing_class")) if "swing_class" in f else "swing structure not computed in this grid (older mtf.json)"]
    parts.append({"9>21": "fast average above slow", "9<21": "fast average below slow", "9=21": "fast and slow averages level"}.get(f.get("ema_order"), "averages not read"))
    d = (f.get("swing") or {}).get("close_vs_swing_high_pct")
    if d is not None:
        parts.append("at the last swing high" if d == 0 else f"{abs(d):.1f}% {'above' if d > 0 else 'under'} the last swing high")
    return f"{name}: " + "; ".join(parts) + "."


def strip_html(mtf_row, E=lambda s: s):
    """The three-frame strip for one name. '' when mtf.json has no row for it (no claim)."""
    if not isinstance(mtf_row, dict):
        return ""
    if not mtf_row.get("served"):
        return f'<p class="mtf"><b>Trend frames:</b> not served ({E(str(mtf_row.get("reason") or "no reason given"))}).</p>'
    return '<p class="mtf"><b>Trend frames.</b> ' + " ".join(E(frame_plain(tf, mtf_row.get(tf))) for tf in ("W", "D", "H1")) + "</p>"


# PM 2026-11-05: the PM rejected a fixed 2% ("random and overly tight"). Distance from the latest confirmed daily swing high is read in
# daily ranges (ATR): (daily close - swing high) / atr_14d, positive = above. These two edges are the ONLY place the bands are defined;
# the PM picks the final numbers. They label data, they are not a gate or a vote (R1).
ATR_NEAR = 1.0      # inside +/- this many daily ranges of the swing high = "at the pivot"; further under = "below"
ATR_FAR = 3.0       # above the swing high by more than ATR_NEAR and up to this = "extended"; beyond it = "far extended"
BAND_AT, BAND_EXT, BAND_FAR, BAND_BELOW = "at the pivot", "extended", "far extended", "below the pivot"


def atr_band(dist_atr):
    if dist_atr is None:
        return None
    if dist_atr < -ATR_NEAR:
        return BAND_BELOW
    if dist_atr <= ATR_NEAR:
        return BAND_AT
    return BAND_EXT if dist_atr <= ATR_FAR else BAND_FAR


def atr_distance(mtf_row, export_row):
    """The daily close vs the latest confirmed daily swing high, in daily ranges (ATR) from the export's atr_14d. None when any input is missing
    (never filled)."""
    D = (mtf_row or {}).get("D") if isinstance(mtf_row, dict) else None
    sw = (D or {}).get("swing") or {}
    sh = (sw.get("last_swing_high") or {}).get("price")
    close = (D or {}).get("close")
    atr = (export_row or {}).get("atr_14d") if isinstance(export_row, dict) else None
    if not all(isinstance(x, (int, float)) for x in (sh, close, atr)) or atr <= 0 or sh <= 0:
        return None
    d = (close - sh) / atr
    pct = (close / sh - 1) * 100
    way = "at" if abs(d) < 0.05 else ("above" if d > 0 else "under")
    text = ("at the last swing high" if way == "at" else f"{abs(d):.1f} daily ranges (ATR) {way} the last swing high") + f" ({pct:+.1f}%), {atr_band(d)}"
    return {"atr_dist": round(d, 2), "pct": round(pct, 2), "band": atr_band(d), "text": text, "atr": atr}


def momentum(mtf_row, export_row=None):
    """(flag, why). flag = weekly AND daily swing structure are both higher highs / higher lows (mtf.json's code-built structure flag;
    None when the row has none, an older grid). why = the distance from the daily swing high in daily ranges, as data, when it can be read."""
    m = (mtf_row or {}).get("momentum") if isinstance(mtf_row, dict) else None
    if not isinstance(m, dict):
        return None, ""
    ad = atr_distance(mtf_row, export_row)
    if not m.get("flag"):
        return False, "; ".join(m.get("reasons") or [])
    return True, ("weekly and daily higher highs and higher lows; " + ad["text"]) if ad else "weekly and daily higher highs and higher lows; distance from the swing high not readable"


def trend_pill_text(mtf_row, export_row):
    """Text for the pill on a card: the structure and the ATR distance as data. '' when the structure is not weekly+daily HH/HL."""
    f, why = momentum(mtf_row, export_row)
    if not f:
        return ""
    ad = atr_distance(mtf_row, export_row)
    return f"Uptrend, {ad['band']} ({ad['atr_dist']:+.1f} ATR)" if ad else "Uptrend structure"


def momentum_summary(mtf_names, tickers, rows=None):
    """Counts over the slate: weekly+daily HH/HL names by band. Only names whose mtf row carries the flag are counted; None when none do."""
    have = [t for t in tickers if momentum((mtf_names or {}).get(t))[0] is not None]
    if not have:
        return None
    hit = [t for t in have if momentum(mtf_names[t])[0]]
    bands = {}
    for t in hit:
        ad = atr_distance(mtf_names[t], (rows or {}).get(t))
        bands.setdefault(ad["band"] if ad else "distance not readable", []).append(f"{t} {ad['atr_dist']:+.1f}" if ad else t)
    parts = [f"{k}: {', '.join(v)}" for k, v in bands.items()]
    return {"n": len(have), "hit": hit, "bands": bands, "text": f"{len(hit)} of {len(have)} slate names have weekly and daily higher highs and higher lows"
            + (" (distance of the daily close from the latest daily swing high in daily ranges, ATR; at the pivot = within " + f"{ATR_NEAR:g}, extended = {ATR_NEAR:g} to {ATR_FAR:g} above, far extended = over {ATR_FAR:g} above). " + "; ".join(parts) if hit else "")
            + ". Information only: not a gate, not a vote."}


# ------------------------------------------------------------------------------------------------ U&R
def unr_ref(row, close=None):
    """The U&R reference for one export row. close = the last completed close (the export's `entry`)."""
    row = row or {}
    st = row.get("unr_status")
    lvl = row.get("unr_level")
    c = close if close is not None else row.get("entry")
    pct = round((c / lvl - 1) * 100, 1) if isinstance(c, (int, float)) and isinstance(lvl, (int, float)) and lvl > 0 else None
    out = {"status": st, "level": lvl, "close": c, "pct_vs_line": pct, "note": row.get("unr_note"), "useful": None}
    if st in ("MET", "SETUP") and pct is not None:
        out["useful"] = pct <= FAR_ABOVE_LINE_PCT           # a line far under the price is not a reference to trade against
    return out


def unr_tag(row, close=None):
    """One plain line for a card. Data, not a condition."""
    if not isinstance(row, dict) or "unr_status" not in row:
        return "U&R: not in this export."
    u = unr_ref(row, close)
    st = u["status"]
    if st == "MET":
        if u["useful"] is False:
            return f"U&R: reclaim day on the support line {u['level']:g}, but the last close is {u['pct_vs_line']:.1f}% above it: no useful U&R reference."
        return f"U&R: reclaim day. Support line {u['level']:g}; the last close is {u['pct_vs_line']:+.1f}% from it."
    if st == "SETUP":
        return f"U&R: setup forming. Undercut {u['level']:g} and still under it at the last close; the reclaim day is the next session."
    if st == "NO":
        return "U&R: none. No shallow dip under a support level in the last 3 sessions."
    if st == "NA":
        return "U&R: not checked; too little price history."
    return "U&R: not read."


def unr_table_md(rows, order, date_label=None, held=()):
    """Markdown table for the brief. rows = {ticker: export row}; order = [(ticker, committee label)]."""
    head = ("U&R = a daily support level (swing low, trendline, 9/21-day average) was undercut by a shallow dip and the last completed session"
            + (f" ({date_label})" if date_label else "")
            + " closed back above it. MET = that reclaim day. The level is shown as data, not as a condition. A last close more than "
            + f"{FAR_ABOVE_LINE_PCT:g}% above the line is flagged: no useful U&R reference.")
    lines = [head, "", "| Ticker | Committee | U&R | Support line | Last close | Close vs line | Reference |", "|---|---|---|---|---|---|---|"]
    n_met, flagged = 0, []
    for t, label in order:
        r = rows.get(t)
        if r is None or "unr_status" not in r:
            lines.append(f"| {t} | {label} | not in export | - | - | - | - |")
            continue
        u = unr_ref(r)
        if u["status"] == "MET":
            n_met += 1
        ref = "-"
        if u["useful"] is False:
            ref = "no useful U&R reference"; flagged.append(t)
        elif u["useful"]:
            ref = "line is near enough to use"
        lines.append(f"| {t} | {label} | {u['status']} | {u['level'] if u['level'] is not None else '-'} | {u['close'] if u['close'] is not None else '-'} | "
                     f"{('%+.1f%%' % u['pct_vs_line']) if u['pct_vs_line'] is not None else '-'} | {ref} |")
    lines += ["", f"Read: {n_met} of {len(order)} names are on a U&R reclaim day."
              + (f" No useful U&R reference (close more than {FAR_ABOVE_LINE_PCT:g}% above the line): {', '.join(flagged)}." if flagged else "")
              + " Information only: no gate, no verdict change."]
    return "\n".join(lines) + "\n"


def cmd_unr_table(a):
    ex = json.load(open(a.export))
    rows = {r["ticker"]: r for r in (ex.get("daily_list") or [])}
    for h in ex.get("held_positions") or []:
        rows.setdefault(h["ticker"], h)
    order = []
    try:
        cons = json.load(open(a.consensus))
        for c in cons:
            if c.get("status") == "NOT_SLATED":
                continue                     # the table is for the slate (and the book), not for every name the room looked at
            lab = f"{c.get('verdict')}" + (f" ({c.get('status')})" if c.get("status") else "")
            order.append((c["ticker"], lab))
    except (OSError, ValueError) as e:
        sys.exit(f"card_extras: consensus unreadable: {e}")
    seen = {t for t, _ in order}
    order += [(h["ticker"], "HELD") for h in ex.get("held_positions") or [] if h["ticker"] not in seen]
    md = unr_table_md(rows, order, a.date)
    open(a.out, "w").write(md)
    print(f"wrote {a.out}: {len(order)} names")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("unr-table", help="the code-built U&R table for the brief")
    u.add_argument("--export", default="aqe_daily_export.json"); u.add_argument("--consensus", default="consensus.json")
    u.add_argument("--date", default=None); u.add_argument("--out", default="unr_table.md")
    u.set_defaults(fn=cmd_unr_table)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
