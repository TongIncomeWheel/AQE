"""VALEN Dashboard — the VIV System's Situational Awareness card, ported
into AQE (Part 1: Weather, pieces 01-03). Full scope, sources and the two
constraints this had to resolve: docs/AQE_VALEN_DASHBOARD_PROPOSAL.md.

The page owns no maths. Every number comes from `src.valen`; the nightly
read is cached to `output/valen_dashboard.json` (Step 6i of the daily
pipeline) so a reload is free, same pattern as the Crown Macro page.

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

from src.ui.shared import require_login  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.data.paths import PANEL_DAILY, PANEL_WEEKLY  # noqa: E402
from src.valen import card as C  # noqa: E402
from src.valen import live as L  # noqa: E402
from src.valen.daily import load_valen, run_valen, write_artifacts  # noqa: E402

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

# ── stance banner ────────────────────────────────────────────────────────
banner = C.stance_banner(valen)
status_fn = {"OK": st.success, "DEGRADED": st.warning,
            "UNAVAILABLE": st.error}.get(banner["status"], st.info)
status_fn(f"**Stance: {banner['word']}**"
          + (f" — {banner['reason']}" if banner.get("reason") else ""))

st.markdown(f"### {C.headline(valen)}")

fresh = C.freshness(valen)
st.caption(f"As of {fresh.get('as_of') or valen.get('exported_at') or '—'} "
          f"· basis: {fresh.get('basis', 'eod')}")

# ── three columns: weather / neighbourhood / what would change it ─────────
col_weather, col_neighborhood, col_change = st.columns(3)

with col_weather:
    st.subheader("The weather")
    regime = display_trend.get("regime") or "—"
    st.metric("Regime", regime.replace("_", " "))
    for row in display_trend.get("rows", {}).values():
        sym = row.get("symbol")
        if row.get("basis") == "unavailable":
            st.caption(f"{sym}: not on the panel yet")
            continue
        marks = []
        if row.get("daily_buy_signal") is not None:
            marks.append(("Daily", row["daily_buy_signal"]))
        if row.get("weekly_buy_signal") is not None:
            marks.append(("Weekly", row["weekly_buy_signal"]))
        if row.get("above_rising_5d") is not None:
            marks.append(("Rising 5d", row["above_rising_5d"]))
        line = " · ".join(f"{'✅' if ok else '❌'} {label}"
                              for label, ok in marks)
        basis_tag = " (live)" if row.get("basis") == "live" else ""
        st.markdown(f"**{sym}** {row.get('last_price', '—')}{basis_tag} — {line}")

with col_neighborhood:
    st.subheader("Extension")
    for row in C.extension_rows({**valen, "extension": display_ext}):
        val = row.get("value")
        if val is None:
            st.caption(f"{row['label']}: —")
            continue
        flag = "⚠️" if row.get("flag") else ""
        st.markdown(f"**{row['label']}:** {val} {flag}")
    ctx = valen.get("curated_panel_context") or {}
    if ctx.get("status") == "OK":
        st.caption(
            f"AQE's own curated universe ({ctx['n']} names): "
            f"{ctx['pct_above_20d']}% above their 20-day line. "
            "**Not T2108** — that needs the full market; this is context "
            "on AQE's own screened names only.")

with col_change:
    st.subheader("What would change it")
    watch = C.watch_for_lines(valen)
    if watch:
        for line in watch:
            st.markdown(f"- {line}")
    else:
        st.caption("Not shown — depends on whole-market breadth (Phase 2).")

# ── caveats ──────────────────────────────────────────────────────────────
caveats = C.caveats(valen)
if caveats:
    with st.expander("⚠️ What this read cannot see yet", expanded=True):
        for c in caveats:
            st.markdown(f"- {c}")

# ── breadth (honest absence, Phase 1) ───────────────────────────────────
with st.expander("The four instruments (whole-market breadth)"):
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
