#!/usr/bin/env python3
"""valen_entries: the mechanical VALEN ENTRIES table on the Cards page (PM 2026-11-19, via the conductor).

Straight from the AQE export, no committee involvement, no verdict, no sizing, no "buy": levels and flags only.
  1. Setups graded TRIGGERED or READY (setup, status, pivot, stop) on every daily_list name and held name.
  2. Undercut-and-rally rows: unr_status MET (reclaim day) or SETUP (undercut, reclaim day is next): support line, last close, close vs line,
     and a flag when the last close is more than 5% above the line.
  3. Two columns: AQE-listed (Longlist / Elder / QS / none) and whether the name is also on the committee's slate.
R41 stands: Valen's no-buy list and the piece-12 parabolic / failed-leader risk warnings are NEVER printed here.
If setups_status is not live the page shows a loud banner, never a silently empty table.
"""
from __future__ import annotations

import html

ENTRY_STATUSES = ("TRIGGERED", "READY")
UNR_STATUSES = ("MET", "SETUP")
EXTENDED_PCT = 5.0
RISK_PIECES = {"12"}          # R41: parabolic / failed leader are long-only risk warnings, never printed on a ticket-selection surface


def _lists(r: dict) -> str:
    w = [n for k, n in (("on_longlist", "Longlist"), ("on_elder", "Elder"), ("on_qs", "QS")) if r.get(k)]
    return ", ".join(w) if w else "none"


def collect(export: dict, slate_tickers) -> dict:
    """-> {"status": {...}, "live": bool, "setups": [...], "unr": [...], "n_names": int}. Pure; never raises on a missing field."""
    slate = set(slate_tickers or [])
    rows, seen = [], set()
    for r in list(export.get("daily_list") or []) + list(export.get("held_positions") or []):
        t = r.get("ticker")
        if t and t not in seen:
            seen.add(t); rows.append(r)
    st = export.get("setups_status")
    st = st if isinstance(st, dict) else {}
    live = st.get("status") == "live"
    setups, unr = [], []
    for r in rows:
        t = r["ticker"]
        base = {"ticker": t, "aqe": _lists(r), "slate": t in slate, "held": bool(r.get("held") or r.get("qty"))}
        for g in r.get("setups") or []:
            if isinstance(g, dict) and str(g.get("piece")) not in RISK_PIECES and g.get("status") in ENTRY_STATUSES:
                setups.append(dict(base, setup=g.get("setup"), status=g.get("status"), pivot=g.get("pivot"), stop=g.get("stop")))
        us = r.get("unr_status")
        if us in UNR_STATUSES:
            lvl, close = r.get("unr_level"), r.get("last_close")
            pct = round((close / lvl - 1) * 100, 1) if isinstance(lvl, (int, float)) and lvl and isinstance(close, (int, float)) else None
            unr.append(dict(base, status=us, level=lvl, close=close, pct=pct, extended=bool(pct is not None and pct > EXTENDED_PCT),
                            as_of=r.get("unr_as_of"), note=r.get("unr_note")))
    setups.sort(key=lambda x: (x["status"] != "TRIGGERED", x["ticker"], str(x["setup"])))
    unr.sort(key=lambda x: (x["status"] != "MET", x["ticker"]))
    return {"status": st, "live": live, "setups": setups, "unr": unr, "n_names": len(rows),
            "unr_as_of": (export.get("unr_summary") or {}).get("as_of")}


def _num(v, f="{:.2f}"):
    return f.format(v) if isinstance(v, (int, float)) else "&mdash;"


def render(export: dict, slate_tickers, E=html.escape) -> tuple[str, str, int]:
    """-> (banner html, tables html, entry count). The banner is printed OUTSIDE the collapsed block so it cannot be missed; the tables go inside it."""
    c = collect(export, slate_tickers)
    out, banner = [], ""
    if not c["live"]:
        st = c["status"] or {}
        banner = (f'<p class="banner bad"><b>VALEN SETUPS NOT LIVE</b> &mdash; setups_status is {E(str(st.get("status") or "missing"))}'
                   f'{(": " + E(str(st.get("reason")))) if st.get("reason") else ""}. The tables below may be incomplete or empty; read nothing into an empty row.</p>')
    sl = lambda x: "Yes" if x["slate"] else "No"
    tk = lambda x: f"<b>{E(x['ticker'])}</b>" + (" <span class='sub'>held</span>" if x["held"] else "")
    head1 = "<tr><th>Ticker</th><th>Setup</th><th>Status</th><th>Pivot</th><th>Stop</th><th>AQE-listed</th><th>On the committee slate</th></tr>"
    body1 = "".join(f"<tr><td>{tk(x)}</td><td>{E(str(x['setup']))}</td><td>{E(x['status'])}</td><td>{_num(x['pivot'])}</td><td>{_num(x['stop'])}</td>"
                    f"<td>{E(x['aqe'])}</td><td>{sl(x)}</td></tr>" for x in c["setups"]) or '<tr><td colspan="7">No setup is graded TRIGGERED or READY today.</td></tr>'
    out.append(f'<h4>Setups graded TRIGGERED or READY ({len(c["setups"])})</h4><div class="tbl"><table class="lst sortable"><thead>{head1}</thead><tbody>{body1}</tbody></table></div>')
    head2 = ("<tr><th>Ticker</th><th>Undercut and rally</th><th>Support line</th><th>Last close</th><th>Close vs line</th>"
             f"<th>&gt;{EXTENDED_PCT:g}% above the line</th><th>AQE-listed</th><th>On the committee slate</th></tr>")
    lab = {"MET": "MET (reclaim day)", "SETUP": "SETUP (reclaim day is next)"}
    body2 = "".join(f"<tr><td>{tk(x)}</td><td>{lab[x['status']]}</td><td>{_num(x['level'])}</td><td>{_num(x['close'])}</td>"
                    f"<td>{_num(x['pct'], '{:+.1f}%')}</td><td>{'Extended' if x['extended'] else ''}</td><td>{E(x['aqe'])}</td><td>{sl(x)}</td></tr>"
                    for x in c["unr"]) or '<tr><td colspan="8">No name is U&amp;R MET or SETUP at the last close.</td></tr>'
    out.append(f'<h4>Undercut and rally, MET or SETUP ({len(c["unr"])})</h4><div class="tbl"><table class="lst sortable"><thead>{head2}</thead><tbody>{body2}</tbody></table></div>')
    out.append(f'<p class="sub">Levels and flags straight from the AQE export (last close {E(str(c["unr_as_of"] or "date not stated"))}); {c["n_names"]} names checked. '
               'No verdict, no sizing: a setup is a measured shape, not a call.</p>')
    return banner, "".join(out), len(c["setups"]) + len(c["unr"])
