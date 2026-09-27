"""VALEN visual rendering — dark card panels, colour-coded pills and tables,
matching the VIV System webapp's own Situational Awareness card (the
reference the PM asked this to match, 2026-09-27) rather than plain
Streamlit widgets.

Same blindness rule as card.py: no pandas, no file access, no engine
imports — every function here is a pure string-building function of the
dicts card.py already extracts from the artifact. Streamlit pages inject
`CSS` once and then call these functions inside `st.markdown(html,
unsafe_allow_html=True)`.

Deliberately a single, permanently dark theme (no light-mode variant) —
the VIV webapp itself has no light mode; this is a considered match, not
an oversight.
"""

from __future__ import annotations

import html as _html

# ---------------------------------------------------------------------------
# Design tokens — one place, so the palette can be tuned without hunting
# through every f-string below.
# ---------------------------------------------------------------------------
_BG = "#0d0d11"
_CARD_BG = "#15151b"
_TILE_BG = "#1a1a21"
_BORDER = "#282830"
_BORDER_SOFT = "#1e1e25"
_TEXT = "#e9e9ec"
_TEXT_MUTED = "#8b8b95"
_GOLD = "#d9a441"
_GREEN = "#4ade80"
_RED = "#f87171"
_GREY = "#6b6b76"

_STANCE_STYLE = {
    "RISK_ON": ("RISK ON", _GREEN, "rgba(74,222,128,0.14)", "rgba(74,222,128,0.35)"),
    "NEUTRAL": ("NEUTRAL", _GOLD, "rgba(217,164,65,0.14)", "rgba(217,164,65,0.35)"),
    "RISK_OFF": ("RISK OFF", _RED, "rgba(248,113,113,0.14)", "rgba(248,113,113,0.35)"),
}
_STATE_STYLE = {
    "LEADING": (_GREEN, "LEADING"),
    "OFF_THE_FLOOR": (_GOLD, "OFF THE FLOOR"),
    "NEITHER": (_GREY, "—"),
}

CSS = f"""
<style>
.valen-root {{ color: {_TEXT}; }}
.valen-card {{
  background: {_CARD_BG}; border: 1px solid {_BORDER}; border-radius: 10px;
  padding: 18px 22px; margin-bottom: 14px;
}}
.valen-header {{ display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; }}
.valen-title {{ font-size: 13px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: {_TEXT_MUTED}; }}
.valen-pill {{ display: inline-block; padding: 4px 14px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  white-space: nowrap; }}
.valen-headline {{ border-left: 3px solid {_GOLD}; background: rgba(217,164,65,0.06);
  padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 14px; line-height: 1.55;
  color: {_TEXT}; margin-bottom: 2px; }}
.valen-sowhat {{ font-size: 12.5px; color: {_TEXT_MUTED}; margin: 6px 2px 0 2px; }}
.valen-grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.valen-col-label {{ font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: {_GOLD}; margin-bottom: 8px; padding-bottom: 6px;
  border-bottom: 1px solid {_BORDER}; }}
.valen-row {{ display: flex; justify-content: space-between; align-items: baseline;
  padding: 5px 0; font-size: 13px; border-bottom: 1px solid {_BORDER_SOFT}; gap: 10px; }}
.valen-row:last-child {{ border-bottom: none; }}
.valen-row-label {{ color: {_TEXT_MUTED}; }}
.valen-row-value {{ font-variant-numeric: tabular-nums; text-align: right;
  white-space: nowrap; }}
.valen-ok {{ color: {_GREEN}; }}
.valen-fail {{ color: {_RED}; }}
.valen-muted {{ color: {_GREY}; }}
.valen-stat {{ background: {_TILE_BG}; border: 1px solid {_BORDER}; border-radius: 8px;
  padding: 9px 12px; margin-bottom: 8px; }}
.valen-stat:last-child {{ margin-bottom: 0; }}
.valen-stat-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
  color: {_TEXT_MUTED}; margin-bottom: 3px; }}
.valen-stat-value {{ font-size: 19px; font-weight: 700; color: {_TEXT};
  font-variant-numeric: tabular-nums; }}
.valen-stat-sub {{ font-size: 11px; color: {_GOLD}; margin-left: 6px; }}
.valen-stat-unavail {{ font-size: 12px; color: {_GREY}; font-style: italic; }}
.valen-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.valen-table th {{ text-align: right; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.05em; color: {_GOLD}; padding: 6px 8px; border-bottom: 1px solid {_BORDER}; }}
.valen-table th:first-child, .valen-table td:first-child {{ text-align: left; }}
.valen-table td {{ padding: 5px 8px; border-bottom: 1px solid {_BORDER_SOFT}; color: {_TEXT};
  text-align: right; font-variant-numeric: tabular-nums; }}
.valen-table tr:hover td {{ background: rgba(255,255,255,0.02); }}
.valen-rank {{ color: {_GREY}; width: 22px; }}
.valen-name {{ color: {_TEXT}; text-align: left !important; }}
.valen-pos {{ color: {_GREEN}; }}
.valen-neg {{ color: {_RED}; }}
.valen-bullet-list {{ margin: 0; padding-left: 0; list-style: none; }}
.valen-bullet-list li {{ font-size: 13px; line-height: 1.5; color: {_TEXT};
  padding: 5px 0 5px 14px; position: relative; }}
.valen-bullet-list li::before {{ content: "—"; position: absolute; left: 0; color: {_GOLD}; }}
.valen-caption {{ font-size: 12px; color: {_TEXT_MUTED}; margin-top: 6px; }}
</style>
"""


def _esc(v) -> str:
    return _html.escape(str(v))


def _fmt(v, suffix: str = "", nd: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}{suffix}"
    return _esc(v)


def _pct_class(v) -> str:
    if v is None:
        return ""
    return "valen-pos" if v > 0 else ("valen-neg" if v < 0 else "")


def stance_header_html(banner: dict) -> str:
    """`banner` = card.stance_banner(valen)'s return shape."""
    status = banner.get("status", "UNAVAILABLE")
    stance_key = (banner.get("word") or "").replace(" ", "_")
    label, color, bg, border = _STANCE_STYLE.get(
        stance_key, ("NOT SHOWN", _GREY, "rgba(107,107,118,0.14)", "rgba(107,107,118,0.3)"))
    reason = banner.get("reason")
    pill = (f'<span class="valen-pill" style="color:{color};background:{bg};'
           f'border:1px solid {border}">{_esc(label)}</span>')
    reason_html = (f'<div class="valen-caption">{_esc(reason)}</div>' if reason else "")
    return (f'<div class="valen-header"><span class="valen-title">'
           f'\U0001f9ed Situational Awareness</span>{pill}</div>{reason_html}')


def headline_banner_html(headline_text: str, so_what: str | None) -> str:
    so_what_html = f'<div class="valen-sowhat">{_esc(so_what)}</div>' if so_what else ""
    return f'<div class="valen-headline">{_esc(headline_text)}</div>{so_what_html}'


def trend_checklist_html(trend_rows_: list[dict], breadth_rows_: list[dict]) -> str:
    rows_html = []
    for r in trend_rows_:
        sym = r.get("symbol")
        if r.get("basis") == "unavailable":
            rows_html.append(
                f'<div class="valen-row"><span class="valen-row-label">{_esc(sym)}</span>'
                f'<span class="valen-row-value valen-muted">not on panel</span></div>')
            continue
        marks = []
        for label, key in (("Daily", "daily_buy_signal"), ("Weekly", "weekly_buy_signal"),
                          ("Rising 5d", "above_rising_5d")):
            v = r.get(key)
            if v is None:
                continue
            cls = "valen-ok" if v else "valen-fail"
            marks.append(f'<span class="{cls}">{"●" if v else "○"} {label}</span>')
        basis_tag = " (live)" if r.get("basis") == "live" else ""
        rows_html.append(
            f'<div class="valen-row"><span class="valen-row-label">{_esc(sym)} '
            f'{_fmt(r.get("last_price"))}{basis_tag}</span>'
            f'<span class="valen-row-value">{" &nbsp; ".join(marks)}</span></div>')
    checklist_html = []
    for row in breadth_rows_:
        if row["status"] == "OK":
            val = row.get("value")
            if isinstance(val, bool):
                cls = "valen-ok" if val else "valen-fail"
                shown = "Green" if val else "Red"
            else:
                cls, shown = "", _fmt(val)
            checklist_html.append(
                f'<div class="valen-row"><span class="valen-row-label">{_esc(row["label"])}'
                f'</span><span class="valen-row-value {cls}">{shown}</span></div>')
        else:
            checklist_html.append(
                f'<div class="valen-row"><span class="valen-row-label valen-muted">'
                f'{_esc(row["label"])}</span><span class="valen-row-value valen-muted">'
                f'not shown</span></div>')
    return (f'<div class="valen-col-label">Trend &amp; checklist</div>'
           f'{"".join(rows_html)}'
           f'<div class="valen-col-label" style="margin-top:12px">Market checklist</div>'
           f'{"".join(checklist_html)}')


def instruments_html(extension_rows_: list[dict]) -> str:
    tiles = []
    for row in extension_rows_:
        val = row.get("value")
        if val is None:
            tiles.append(
                f'<div class="valen-stat"><div class="valen-stat-label">{_esc(row["label"])}'
                f'</div><div class="valen-stat-unavail">not shown</div></div>')
            continue
        flag_html = ('<span class="valen-stat-sub">⚠</span>' if row.get("flag") else "")
        tiles.append(
            f'<div class="valen-stat"><div class="valen-stat-label">{_esc(row["label"])}'
            f'</div><div class="valen-stat-value">{_fmt(val)}{flag_html}</div></div>')
    return f'<div class="valen-col-label">Instruments</div>{"".join(tiles)}'


def what_would_change_html(watch_for: list[str]) -> str:
    if not watch_for:
        return ('<div class="valen-col-label">What would change it</div>'
               '<div class="valen-stat-unavail">Not shown — depends on whole-market '
               'breadth.</div>')
    items = "".join(f"<li>{_esc(line)}</li>" for line in watch_for)
    return (f'<div class="valen-col-label">What would change it</div>'
           f'<ul class="valen-bullet-list">{items}</ul>')


def neighbourhood_html(lines: list[str], status: str, reason: str | None) -> str:
    if not lines:
        msg = "No group cleared a leadership read today." if status == "OK" else (
            reason or "Group read unavailable.")
        return (f'<div class="valen-col-label">The neighbourhood</div>'
               f'<div class="valen-stat-unavail">{_esc(msg)}</div>')
    items = "".join(f"<li>{_esc(line)}</li>" for line in lines)
    return (f'<div class="valen-col-label">The neighbourhood</div>'
           f'<ul class="valen-bullet-list">{items}</ul>')


def theme_leaders_table_html(rows: list[dict], limit: int = 15) -> str:
    """Ranked by 1-week return, colour-coded green/positive red/negative,
    matching the reference's Theme Leaders table exactly."""
    ranked = sorted((r for r in rows if r.get("ret_1w_pct") is not None),
                    key=lambda r: r["ret_1w_pct"], reverse=True)[:limit]
    body = []
    for i, r in enumerate(ranked, 1):
        body.append(
            f'<tr><td class="valen-rank">{i}</td>'
            f'<td class="valen-name">{_esc(r.get("display_name"))}</td>'
            f'<td class="{_pct_class(r.get("since_open_pct"))}">'
            f'{_fmt(r.get("since_open_pct"), "%")}</td>'
            f'<td class="{_pct_class(r.get("ret_1w_pct"))}">'
            f'{_fmt(r.get("ret_1w_pct"), "%")}</td>'
            f'<td class="{_pct_class(r.get("ret_1m_pct"))}">'
            f'{_fmt(r.get("ret_1m_pct"), "%")}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th></th><th>Group</th>'
        '<th>Since Open</th><th>1 Week</th><th>1 Month</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')


def rotation_table_html(rows: list[dict], limit: int = 15) -> str:
    """Sorted by thrust, with the honesty column (% off 52-week high) and
    the LEADING / OFF_THE_FLOOR state front and centre."""
    ranked = sorted((r for r in rows if r.get("thrust") is not None),
                    key=lambda r: r["thrust"], reverse=True)[:limit]
    body = []
    for i, r in enumerate(ranked, 1):
        state = r.get("rotation_state") or "NEITHER"
        color, label = _STATE_STYLE.get(state, (_GREY, state))
        body.append(
            f'<tr><td class="valen-rank">{i}</td>'
            f'<td class="valen-name">{_esc(r.get("display_name"))}</td>'
            f'<td class="{_pct_class(r.get("thrust"))}">{_fmt(r.get("thrust"), "%")}</td>'
            f'<td class="{_pct_class(r.get("ret_1m_pct"))}">'
            f'{_fmt(r.get("ret_1m_pct"), "%")}</td>'
            f'<td>{_fmt(r.get("pct_off_52w_high"), "%")}</td>'
            f'<td style="color:{color};font-weight:600;font-size:11px;'
            f'text-transform:uppercase">{_esc(label)}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th></th><th>Group</th>'
        '<th>Thrust</th><th>1 Month</th><th>% off 52w high</th><th>State</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')
