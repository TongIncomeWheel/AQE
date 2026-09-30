"""VALEN Dashboard — the VIV System's Situational Awareness card, ported
into AQE (Part 1: Weather, pieces 01-03). Full scope, sources and the two
constraints this had to resolve: docs/AQE_VALEN_DASHBOARD_PROPOSAL.md.

The page owns no maths and, as of 2026-09-27, no presentation logic either
— every number comes from `src.valen.card`, every pixel from
`src.valen.theme` (a deliberately custom-styled dark card, matching the
VIV webapp's own Situational Awareness card rather than plain Streamlit
widgets — the PM's explicit ask, overriding CLAUDE.md's general "no fancy
visuals" default for this one page). The nightly read is cached to
`output/valen_dashboard.json` (Step 6i of the daily pipeline) so a reload
is free, same pattern as the Crown Macro page.

Live refresh (market hours): click-to-pull, never auto-polling — same
house pattern as the "Refresh live levels" button on the Charts & Trade
Entry page. A live pull recomputes trend + the index/VIX legs of
extension for THIS page render only; it never overwrites the nightly
artifact on disk, and whole-market breadth always stays at its last
nightly read (that computation is not a per-click operation).

**Reading, not sizing.** The one-word stance is a market READING — same
category as AQE's `regime` field. AQE makes no decisions and no sizing
(CLAUDE.md). The handbook's own "what I do with each answer" guidance is
shown below as quoted doctrine, visibly attributed, so the PM/AIC still
makes every sizing call.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="VALEN Dashboard", page_icon=":compass:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, table_with_copy  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.data.paths import PANEL_DAILY, PANEL_WEEKLY  # noqa: E402
from src.valen import card as C  # noqa: E402
from src.valen import live as L  # noqa: E402
from src.valen import theme as T  # noqa: E402
from src.valen.daily import load_valen, run_valen, write_artifacts  # noqa: E402

st.markdown(T.CSS, unsafe_allow_html=True)

st.title(":compass: VALEN Dashboard")
st.caption(
    "The VIV System's Situational Awareness card — market trend, extension "
    "and rotation, read before any chart. Part 1 (Weather) of the handbook; "
    "everything downstream (setups, entries, management) stays where AQE "
    "already builds it — the Signals table, brackets and DETECT layer."
)

# ── run / load — same idiom as the Crown Macro page ────────────────────────
left, right = st.columns([1, 3])
with left:
    go = st.button("▶️ Run VALEN read", use_container_width=True, type="primary")
with right:
    st.caption("Reads the same daily panel every AQE engine reads (SPY/QQQ "
               "bars, the Cboe VIX complex). Cached to "
               "`output/valen_dashboard.json` — a reload is free.")

if go:
    with st.spinner("Reading the market…"):
        try:
            valen = run_valen()
            write_artifacts(valen)
        except Exception as exc:  # noqa: BLE001
            st.error(f"VALEN run failed: {exc}")
            valen = load_valen()
else:
    valen = load_valen()

if not valen:
    st.info("No VALEN read yet. Press **Run VALEN read** above.")
    st.stop()

# ── live refresh (market hours) ─────────────────────────────────────────────
market_open = L.market_is_open()
lc1, lc2 = st.columns([1, 3])
with lc1:
    live_disabled = not market_open
    live_click = st.button(
        "\U0001f504 Refresh live (trend + VIX)", use_container_width=True,
        disabled=live_disabled,
        help=("Pull a live SPY/QQQ/VIX quote now and recompute trend + "
              "extension for this view only — never overwrites the nightly "
              "read." if market_open else
              "Market is closed — showing the last nightly read."))
with lc2:
    if market_open:
        st.caption("Market is open. Live refresh does not touch breadth or "
                   "rotation — those stay at last night's read.")
    else:
        st.caption("Market is closed. Live refresh is available 09:45–16:15 ET.")

if live_click:
    with st.spinner("Pulling a live quote…"):
        df = pd.read_parquet(
            PANEL_DAILY, columns=["date", "ticker", "open", "high", "low", "close"])
        live_out = L.pull_live(PANEL_DAILY, PANEL_WEEKLY,
                               df[df["ticker"].isin(("SPY", "QQQ"))])
    if live_out is None:
        st.warning("Live quote pull failed or returned nothing — showing the "
                  "last nightly read.")
    else:
        st.session_state["valen_live"] = live_out

live = st.session_state.get("valen_live")
display_trend = (live or {}).get("trend") or valen.get("trend")
display_ext = (live or {}).get("extension") or valen.get("extension")
if live:
    st.caption(f"\U0001f7e2 Live as of {live['pulled_at']} "
              f"(quotes: {', '.join(live['quotes_used']) or 'none'})")

# ── the card ─────────────────────────────────────────────────────────────
banner = C.stance_banner(valen)
pe = valen.get("plain_english") or {}
fresh = C.freshness(valen)

breadth_rows_data = C.breadth_rows(valen)

card_html = (
    '<div class="valen-root"><div class="valen-card">'
    + T.stance_header_html(banner)
    + T.stance_gauge_html(banner)
    + T.headline_banner_html(C.headline(valen), pe.get("so_what"))
    + f'<div class="valen-caption">As of {fresh.get("as_of") or valen.get("exported_at") or "—"} '
      f'· basis: {fresh.get("basis", "eod")} · regime: '
      f'{C.regime_word(valen).replace("_", " ")}</div>'
    + '<div class="valen-grid2" style="margin-top:16px">'
    + f'<div>{T.trend_checklist_html(C.trend_rows({**valen, "trend": display_trend}), breadth_rows_data)}</div>'
    + f'<div>{T.instruments_html(C.extension_rows({**valen, "extension": display_ext}), breadth_rows_data)}</div>'
    + '</div>'
    + '<div class="valen-grid2" style="margin-top:16px">'
    + f'<div>{T.what_would_change_html(C.watch_for_lines(valen))}</div>'
    + f'<div>{T.neighbourhood_html(C.neighbourhood_lines(valen), (valen.get("groups") or {}).get("status"), (valen.get("groups") or {}).get("reason"))}</div>'
    + '</div>'
    + '</div></div>'
)
st.markdown(card_html, unsafe_allow_html=True)

ctx = valen.get("curated_panel_context") or {}
if ctx.get("status") == "OK":
    st.caption(
        f"AQE's own curated universe ({ctx['n']} names): "
        f"{ctx['pct_above_20d']}% above their 20-day line. "
        "**Not T2108** — that needs the full market; this is context "
        "on AQE's own screened names only.")

# ── caveats ──────────────────────────────────────────────────────────────
caveats = C.caveats(valen)
if caveats:
    with st.expander("⚠️ What this read cannot see yet", expanded=True):
        for c in caveats:
            st.markdown(f"- {c}")

# ── Theme Leaders + Rotation — pieces 02/03, the full group read ──────────
gr = valen.get("groups") or {}
if gr.get("status") == "OK":
    st.markdown('<div class="valen-root">', unsafe_allow_html=True)
    tl_rows = C.theme_leaders_table(valen)
    rot_rows = C.rotation_table(valen)

    st.markdown(
        '<div class="valen-card">'
        '<div class="valen-header"><span class="valen-title">Theme Leaders</span></div>'
        '<div class="valen-caption" style="margin-bottom:10px">Every group, ranked three '
        'ways at once. On both lists = real leadership. Strong this week, absent on the '
        'month = new money arriving. Strong month, fading week = a leader resting or '
        'ending.</div>' + T.theme_leaders_table_html(tl_rows) + '</div>',
        unsafe_allow_html=True)
    with st.expander("📋 Copy for AIC — Theme Leaders"):
        tl_df = pd.DataFrame([
            {"Group": r["display_name"], "Since Open %": r.get("since_open_pct"),
             "1 Week %": r.get("ret_1w_pct"), "1 Month %": r.get("ret_1m_pct")}
            for r in tl_rows
        ]).sort_values("1 Week %", ascending=False)
        table_with_copy(tl_df, key="valen_theme_leaders")

    st.markdown(
        '<div class="valen-card">'
        '<div class="valen-header"><span class="valen-title">Rotation</span></div>'
        '<div class="valen-caption" style="margin-bottom:10px">Sorted by thrust (this '
        "week's push). % off 52-week high is the honesty column: LEADING means strong "
        'and near highs; OFF THE FLOOR means the same strong numbers but still 15-25% '
        'below highs — a bounce, not leadership.</div>'
        + T.rotation_table_html(rot_rows) + '</div>',
        unsafe_allow_html=True)
    with st.expander("📋 Copy for AIC — Rotation"):
        rot_df = pd.DataFrame([
            {"Group": r["display_name"], "Thrust": r.get("thrust"),
             "1 Month %": r.get("ret_1m_pct"), "% off 52w high": r.get("pct_off_52w_high"),
             "State": r.get("rotation_state"), "Parent sector": r.get("parent_gics")}
            for r in rot_rows
        ])
        table_with_copy(rot_df, key="valen_rotation")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.caption(f"Theme Leaders / Rotation not shown — {gr.get('reason') or 'group read unavailable'}.")

# ── the four instruments, raw values (for anyone who wants the numbers
# behind the checklist tiles above) ─────────────────────────────────────
with st.expander("The four instruments — raw values"):
    for row in C.breadth_rows(valen):
        if row["status"] == "OK":
            st.markdown(f"**{row['label']}:** {row['value']}")
        else:
            st.caption(f"{row['label']}: UNAVAILABLE — {row.get('reason', '')}")

# ── quoted doctrine — NEVER computed, NEVER exported; see module docstring ──
with st.expander("What the handbook does with each stance — quoted, not computed"):
    st.caption(
        "AQE computes the stance as a market reading only. Sizing is always "
        "the PM/AIC's call — this is the VIV System's own guidance, quoted "
        "for reference:")
    st.markdown(
        "> **RISK ON** — the full playbook.\n\n"
        "> **NEUTRAL** — half size, take profit sooner, only the best "
        "setups.\n\n"
        "> **RISK OFF** — the best work you can do is build the "
        "watchlist.\n\n"
        "— *The VIV System*, piece 01")
