"""AQE Pricer — mechanical intraday entry & stop calculator (recommend-only).

Turns the EOD export + live intraday 5-min bars into an operative stop (3-gate
validated), a momentum-conditioned entry zone, a TP ladder, size, and an IBKR
bracket spec. Pure deterministic math (no AI / no AIC) — the optional
paste-to-AIC block is only for the user to reaffirm a decision.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Pricer", page_icon=":triangular_ruler:",
                   layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, load_export  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.intraday.plan import intraday_plan, rank_plans  # noqa: E402
from src.intraday.run_plan import build_rec_lookup  # noqa: E402
from src.intraday import config as IC  # noqa: E402


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_bars(ticker: str, interval: str) -> list[dict]:
    """Intraday bars for one ticker (cached 5 min). [] on failure."""
    try:
        from src.data.fmp_client import FMPClient
        return FMPClient().get_intraday_bars(ticker, interval=interval)
    except Exception:  # noqa: BLE001
        return []


def _zone_txt(z: dict) -> str:
    if not z or z.get("kind") == "stand_down":
        return "—"
    return f"{z.get('low')}–{z.get('high')} ({z.get('kind')})"


def _aic_text(plans: list[dict], lvl) -> str:
    enters = [p for p in plans if p["action"] in ("ENTER", "CAUTION")]
    if not enters:
        return "No actionable intraday setups — all names stand down."
    parts = []
    for p in enters:
        op = p.get("operative_stop") or {}
        parts.append(
            f"{p['ticker']} {p['state']} (IMS {p.get('ims')}): entry "
            f"{_zone_txt(p['entry_zone'])}, stop {op.get('price')} "
            f"({op.get('stop_pct')}%), TP {_tp2(p)}, {p.get('shares')} sh, "
            f"R:R {p.get('rr')}")
    return (f"AQE intraday read ({lvl} regime). " + " | ".join(parts)
            + ". Recommend entry decision + size per PTRS × regime; "
              "AQE/Pricer makes no call (mechanical levels only).")


def _tp2(p: dict):
    ladder = p.get("tp_ladder") or []
    if len(ladder) >= 2:
        return ladder[1]["price"]
    return ladder[0]["price"] if ladder else None


st.title("AQE Pricer — intraday entry & stop")
st.caption(
    "Mechanical & recommend-only. Operative stop = tightest level passing all 3 "
    "charter gates (ATR ≥ 1, R:R-TP2 ≥ 2, regime stop-% ceiling); entry zone is "
    "momentum-conditioned and never chases past max-chase. **No AI** — paste the "
    "summary to your AIC only to reaffirm."
)

export = load_export() or {}
if not export:
    st.warning("No AQE export found. Run the daily pipeline + export first "
               "(Scanner → 📤 Export), then reload this page.")
    st.stop()

regime = export.get("regime") or {}
lvl = regime.get("level") if isinstance(regime, dict) else regime
st.caption(f"Regime **{lvl or '—'}** · stop ceiling **{IC.regime_stop_ceiling(regime)}%** "
           f"· risk **${IC.RISK_BUDGET:,.0f}** (3%)")

recs_all = build_rec_lookup(
    export, ["held", "top_picks", "edge_list", "longlist", "watchlist", "elder_list"])
if not recs_all:
    st.info("Export has no tickers to price.")
    st.stop()

all_tickers = sorted(recs_all)
default_sel = [t for t in all_tickers
               if recs_all[t].get("source") in ("held", "top_picks", "edge_list")]

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    sel = st.multiselect("Tickers to price", all_tickers,
                         default=default_sel or all_tickers[:8],
                         help="Defaults to held + top picks + precision-edge.")
with c2:
    risk = st.number_input("Risk $/trade", value=float(IC.RISK_BUDGET), step=100.0)
with c3:
    interval = st.selectbox("Bars", ["5min", "15min", "1min"], index=0)

if st.button("Compute intraday plans", type="primary", disabled=not sel):
    plans, missing = [], []
    prog = st.progress(0.0, text="Fetching intraday bars…")
    for i, tk in enumerate(sel, 1):
        bars = _fetch_bars(tk, interval)
        if not bars:
            missing.append(tk)
        else:
            plans.append(intraday_plan(recs_all[tk], bars, regime=regime,
                                       risk_budget=risk))
        prog.progress(i / len(sel), text=f"Priced {tk} ({i}/{len(sel)})")
    prog.empty()
    st.session_state["pricer_plans"] = rank_plans(plans)
    st.session_state["pricer_missing"] = missing

plans = st.session_state.get("pricer_plans")
if plans:
    rows = []
    for p in plans:
        op = p.get("operative_stop") or {}
        rows.append({
            "Ticker": p["ticker"], "IMS": p.get("ims"), "State": p["state"],
            "Action": p["action"], "Entry zone": _zone_txt(p["entry_zone"]),
            "Stop": op.get("price"), "Stop %": op.get("stop_pct"),
            "TP2": _tp2(p), "R:R": p.get("rr"), "Shares": p.get("shares"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Stale-export guard: flag names whose EOD entry is far from the live bar.
    stale = []
    for p in plans:
        rec = recs_all.get(p["ticker"], {})
        e, px = rec.get("entry"), (p.get("momentum") or {}).get("price")
        if e and px and abs(px - e) / e > 0.15:
            stale.append(f"{p['ticker']} (entry {e} vs live {px})")
    if stale:
        st.warning("⚠️ Export looks stale for: " + ", ".join(stale)
                   + " — structural anchors may be off; rerun the pipeline.")

    st.markdown("##### IBKR bracket specs (recommend-only)")
    for p in plans:
        spec = p.get("ibkr_spec")
        with st.expander(f"{p['ticker']} — {p['state']} · {p['action']}"):
            st.write(p["verdict"])
            if spec:
                st.code(
                    f"{spec['symbol']}: BUY {spec['quantity']} @ "
                    f"{spec['order_type']} {spec['entry']} | "
                    f"stop {spec['stop']} | TP {spec['take_profit']}",
                    language=None)
            mom = p.get("momentum") or {}
            st.caption(
                f"VWAP {mom.get('vwap')} · pos {mom.get('vwap_pos_atr')} ATR · "
                f"OR break {mom.get('or_break')} · RVOL pace {mom.get('rvol_pace')} "
                f"· ext {mom.get('ext_r')}R · as of {mom.get('as_of')}")

    st.markdown("##### Paste-to-AIC summary")
    st.text_area("Copy this into the AIC to reaffirm (optional):",
                 _aic_text(plans, lvl), height=140)

    missing = st.session_state.get("pricer_missing") or []
    if missing:
        st.caption(f"No intraday bars returned for: {', '.join(missing)}")
else:
    st.info("Pick tickers and click **Compute intraday plans**.")
