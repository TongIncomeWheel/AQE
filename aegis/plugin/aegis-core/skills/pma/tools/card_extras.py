#!/usr/bin/env python3
"""card_extras.py -- code-built, information-only extras for the Cards and the brief (PM 2026-11-05).

  1. the weekly / daily / hourly STRIP on every card, built from mtf.json (swing class, average order, distance to the latest swing high);
  2. the MOMENTUM setup flag and its count over the slate (weekly AND daily HH/HL, daily close within 2% of the latest daily swing high);
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
    parts = [swing_plain(f.get("swing_class"))]
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


def momentum(mtf_row):
    """(flag, why) from mtf.json's code-built flag; (None, '') when the row has none (an older grid)."""
    m = (mtf_row or {}).get("momentum") if isinstance(mtf_row, dict) else None
    if not isinstance(m, dict):
        return None, ""
    return bool(m.get("flag")), "; ".join(m.get("reasons") or [])


def momentum_summary(mtf_names, tickers):
    """'0 of 12 slate names ...' -- counts only names whose mtf row carries the flag; says so when none do (older grid)."""
    have = [t for t in tickers if momentum((mtf_names or {}).get(t))[0] is not None]
    if not have:
        return None
    hit = [t for t in have if momentum(mtf_names[t])[0]]
    return {"n": len(have), "hit": hit, "text": f"{len(hit)} of {len(have)} slate names show the momentum setup (weekly and daily higher highs and higher lows, daily close within 2% of the latest daily swing high)"
            + (": " + ", ".join(hit) if hit else "") + ". Information only: not a gate, not a vote."}


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
