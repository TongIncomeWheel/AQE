"""VALEN Dashboard — the VIV System's 21-piece handbook, ported into AQE
end to end (2026-09-30), sequenced the way the handbook's own roadmap page
sequences it: Weather -> Neighbourhood -> House -> When to walk in ->
After you move in -> Keeping the roof on. Full scope, sources and the
piece-by-piece reconciliation: docs/AQE_VALEN_DASHBOARD_PROPOSAL.md.

The page owns no maths and no presentation logic — every number comes
from `src.valen.card`, every pixel from `src.valen.theme` (a deliberately
custom-styled dark card, matching the VIV webapp's own Situational
Awareness card rather than plain Streamlit widgets — the PM's explicit
ask, overriding CLAUDE.md's general "no fancy visuals" default for this
one page). Parts 2-6 (`src.valen.selection`/`house`/`execution`/
`management`) read fields AQE's own engines already stamp onto
`daily_list`/`held_positions` — no new scoring, no new FMP calls, except
piece 20's closed-trade streak (`src.data.trade_history`, a read-only
reader over the existing Aegis trade journal).

Two pieces are deliberately NOT here: piece 06 ("the earnings staircase" —
fundamentals growth) needs an FMP integration AQE has never built and
wasn't added in this pass; piece 21 ("progress over perfection") is the
PM's own practice, not something software can compute or display.

**AQE still makes no decisions and no sizing (CLAUDE.md).** Every reading
below is a FACT (a price, a flag, a rank, an R-multiple), never a
recommendation — pieces 14, 15 and 20's actual sizing/limit RULES ship as
quoted handbook doctrine in the UI, visibly attributed, never as a number
this page or the export computed. The nightly read is cached to
`output/valen_dashboard.json` (Step 6i writes Part 1, Step 8a-1b adds
Parts 2-6 once the day's export exists) so a reload is free.

Live refresh (market hours): click-to-pull, never auto-polling — same
house pattern as the "Refresh live levels" button on the Charts & Trade
Entry page. A live pull recomputes trend + the index/VIX legs of
extension for THIS page render only; it never overwrites the nightly
artifact on disk, and Parts 2-6 always stay at their last nightly read
(none of them are a per-click computation).
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
    "The VIV System's 21 building blocks, in the handbook's own order: "
    "Weather, Neighbourhood, House, When to walk in, After you move in, "
    "Keeping the roof on."
)

# ── run / load — same idiom as the Crown Macro page ────────────────────────
left, right = st.columns([1, 3])
with left:
    go = st.button("▶️ Run VALEN read", use_container_width=True, type="primary")
with right:
    st.caption("Reads the same daily panel every AQE engine reads (SPY/QQQ "
               "bars, the Cboe VIX complex, today's scored export). Cached "
               "to `output/valen_dashboard.json` — a reload is free.")

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
        st.caption("Market is open. Live refresh does not touch breadth, "
                   "rotation, or Parts 2-6 — those stay at last night's read.")
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


def _part_header(n: str, title: str, subtitle: str) -> None:
    st.markdown(T.part_header_html(n, title, subtitle), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# PART 1 — WEATHER (pieces 01-03) — read the market first
# ═══════════════════════════════════════════════════════════════════════
_part_header("1", "Weather", "Is the market paying for breakouts right now?")

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

caveats = C.caveats(valen)
if caveats:
    with st.expander("⚠️ What this read cannot see yet", expanded=True):
        for c in caveats:
            st.markdown(f"- {c}")

gr = valen.get("groups") or {}
if gr.get("status") == "OK":
    st.markdown('<div class="valen-root">', unsafe_allow_html=True)
    tl_rows = C.theme_leaders_table(valen)
    rot_rows = C.rotation_table(valen)

    st.markdown(
        '<div class="valen-card">'
        '<div class="valen-header"><span class="valen-title">Theme Leaders — piece 02</span></div>'
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
        '<div class="valen-header"><span class="valen-title">Rotation — piece 03</span></div>'
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

with st.expander("The four instruments — raw values"):
    for row in breadth_rows_data:
        if row["status"] == "OK":
            st.markdown(f"**{row['label']}:** {row['value']}")
        else:
            st.caption(f"{row['label']}: UNAVAILABLE — {row.get('reason', '')}")

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

# ═══════════════════════════════════════════════════════════════════════
# PART 2 — NEIGHBOURHOOD · SELECTION (pieces 04, 05, 07)
# ═══════════════════════════════════════════════════════════════════════
_part_header("2", "Neighbourhood — selection",
            "Buy what is already outperforming, narrowed to one focus list, "
            "checked against the trades we refuse to take.")

sel = C.selection_block(valen)

st.markdown(
    '<div class="valen-root"><div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">Relative strength — piece 04</span></div>'
    + T.relative_strength_table_html(sel["relative_strength"]) + '</div></div>',
    unsafe_allow_html=True)
if sel["relative_strength"]:
    with st.expander("📋 Copy for AIC — Relative strength"):
        rs_df = pd.DataFrame(sel["relative_strength"])
        table_with_copy(rs_df, key="valen_rs")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown(
        '<div class="valen-root"><div class="valen-card">'
        '<div class="valen-header"><span class="valen-title">The funnel — piece 05</span></div>'
        + T.funnel_html(sel["funnel"]) + '</div></div>',
        unsafe_allow_html=True)
with col_b:
    st.markdown(
        '<div class="valen-root"><div class="valen-card">'
        '<div class="valen-header"><span class="valen-title">The no-buy list — piece 07</span></div>'
        '<div class="valen-caption" style="margin-bottom:8px">Candidates tripping 1+ '
        'refusal flags — a red flag here doesn\'t remove a name from the longlist/Elder/'
        'QS lenses, it\'s a separate, additive read.</div>'
        + T.no_buy_html(sel["no_buy_list"]) + '</div></div>',
        unsafe_allow_html=True)

st.caption("Piece 06 (\"the earnings staircase\" — fundamentals growth) is not built: "
          "AQE has never pulled income-statement/estimates data from FMP.")

# ═══════════════════════════════════════════════════════════════════════
# PART 3 — HOUSE (pieces 08-12)
# ═══════════════════════════════════════════════════════════════════════
_part_header("3", "House — the setups",
            "Which chart patterns we buy, and what each must show.")

house = C.house_block(valen)
st.markdown(
    '<div class="valen-root"><div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">Setups flagged today</span></div>'
    '<div class="valen-caption" style="margin-bottom:8px">08 VCP · 09 Momentum breakout / '
    'high tight flag · 10 Undercut and rally · 11 Episodic pivot (technical fingerprint '
    'only — no catalyst feed) · 12 Exhaustion risk (a warning on longs, never a short call).'
    '</div>' + T.house_setups_html(house["setups"]) + '</div></div>',
    unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PART 4 — WHEN TO WALK IN (pieces 13-16)
# ═══════════════════════════════════════════════════════════════════════
_part_header("4", "When to walk in",
            "The trigger, the size, the limits and the stop.")

execu = C.execution_block(valen)
st.markdown(
    '<div class="valen-root"><div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">How we enter — piece 13</span></div>'
    '<div class="valen-caption" style="margin-bottom:8px">Trigger, then volume '
    'confirmation, then the stop bracket_engine already computed — checked in that order, '
    'exactly like the handbook.</div>' + T.entries_table_html(execu["entries"]) + '</div>'
    '<div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">Cutting losers — piece 16</span></div>'
    '<div class="valen-caption" style="margin-bottom:8px">A fact, never a decision: which '
    'held positions are already through their own stop.</div>'
    + T.stop_breaches_html(execu["stop_breaches"]) + '</div></div>',
    unsafe_allow_html=True)

with st.expander("Sizing is arithmetic (14) & The three limits (15) — quoted, not computed"):
    st.caption("AQE's charter forbids computing a size or a position limit. The "
              "handbook's own words, quoted for reference — this is the PM/AIC's "
              "own arithmetic to do, every time:")
    st.markdown(
        "> **Sizing is arithmetic** — decide what you can lose first (your risk "
        "budget), the share count follows from that and the stop distance. Never "
        "the other way round.\n\n"
        "> **The three limits** — one trade, all trades together, and total money "
        "in the market. Set all three before you place anything.\n\n"
        "— *The VIV System*, pieces 14–15")

# ═══════════════════════════════════════════════════════════════════════
# PART 5 — AFTER YOU MOVE IN (pieces 17-19)
# ═══════════════════════════════════════════════════════════════════════
_part_header("5", "After you move in",
            "Take profit while the stock is still going up, trail the rest, "
            "add only when it proves itself again.")

mgmt = C.management_block(valen)
st.markdown(
    '<div class="valen-root"><div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">Held-position facts — pieces 17–19</span></div>'
    '<div class="valen-caption" style="margin-bottom:8px">Facts only — R-multiple is an '
    'APPROXIMATION using the current stop (AQE keeps no frozen entry-time risk). The '
    'trim/trail/add call itself is always the PM/AIC\'s.</div>'
    + T.held_facts_table_html(mgmt["held_facts"]) + '</div></div>',
    unsafe_allow_html=True)
if mgmt["held_facts"]:
    with st.expander("📋 Copy for AIC — Held-position facts"):
        hf_df = pd.DataFrame(mgmt["held_facts"])
        table_with_copy(hf_df, key="valen_held_facts")

with st.expander("Trim into strength (17), trail the rest (18), adds and pyramids (19) "
                 "— quoted, not computed"):
    st.markdown(
        "> **Trim into strength** — take some profit while the stock is still going up, "
        "not after it rolls over.\n\n"
        "> **Trail the rest** — one moving average, daily closes only.\n\n"
        "> **Adds and pyramids** — add to a winner only when it proves itself again, "
        "never to average down.\n\n"
        "— *The VIV System*, pieces 17–19")

# ═══════════════════════════════════════════════════════════════════════
# PART 6 — KEEPING THE ROOF ON (pieces 20-21)
# ═══════════════════════════════════════════════════════════════════════
_part_header("6", "Keeping the roof on",
            "Cut size in a losing streak, decided in advance — and staying in the game.")

st.markdown(
    '<div class="valen-root"><div class="valen-card">'
    '<div class="valen-header"><span class="valen-title">Streak — piece 20</span></div>'
    '<div class="valen-caption" style="margin-bottom:8px">The fact only — from the '
    'closed-trade journal. The size-cut RULE itself is quoted below, never computed.'
    '</div>' + T.streak_html(mgmt["streak"]) + '</div></div>',
    unsafe_allow_html=True)

with st.expander("Cutting size in a losing streak (20) — quoted, not computed"):
    st.markdown(
        "> Decided in advance, so it never has to be argued about mid-streak: "
        "cut size after a run of losses, by a rule you set before the streak "
        "started, not in the middle of it.\n\n"
        "— *The VIV System*, piece 20")

st.caption("Piece 21 (\"progress over perfection\") is the PM's own practice, not "
          "something a scanner can compute or display — it's intentionally not "
          "represented here.")
