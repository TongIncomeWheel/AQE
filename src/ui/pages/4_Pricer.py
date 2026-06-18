"""AQE Pricer — a pure bracket CALCULATOR (no recommendation, no decision).

Type in ANY ticker (universe or not). For each, it pulls daily + 5-day hourly +
5-min bars and computes a full bracket — entry, the best operative stop from the
FIB / MA / DSL / coil / swing menu, a TP ladder, R:R and size — plus the live
intraday momentum as reference. It NEVER blanks and makes NO call; paste the
numbers to the AIC to decide.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Pricer", page_icon=":triangular_ruler:",
                   layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, load_export, table_with_copy  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.intraday.pricer import price_ticker  # noqa: E402
from src.intraday.run_plan import build_rec_lookup  # noqa: E402
from src.intraday import config as IC  # noqa: E402


@st.cache_data(ttl=300, show_spinner=False)
def _intraday(ticker: str, interval: str) -> list[dict]:
    try:
        from src.data.fmp_client import FMPClient
        return FMPClient().get_intraday_bars(ticker, interval=interval)
    except Exception:  # noqa: BLE001
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def _daily(ticker: str):
    try:
        from src.data.fmp_client import FMPClient
        frm = (date.today() - timedelta(days=400)).isoformat()
        df = FMPClient().get_daily_bars(ticker, from_date=frm)
        return df if df is not None and not df.empty else None
    except Exception:  # noqa: BLE001
        return None


st.title("AQE Pricer — bracket calculator")
st.caption(
    "Pure calculator (no recommendation). For any ticker it computes the best "
    "entry/stop/TP from the **FIB · MA · DSL · coil · swing** menu across daily + "
    "5-day hourly + 5-min bars, with the live momentum as reference. Never blanks; "
    "you/the AIC make the call."
)

export = load_export() or {}
regime = export.get("regime") or {}
lvl = regime.get("level") if isinstance(regime, dict) else regime
st.caption(f"Regime **{lvl or '—'}** · stop ceiling **{IC.regime_stop_ceiling(regime)}%** "
           f"· risk **${IC.RISK_BUDGET:,.0f}** (3%)")

recs_all = build_rec_lookup(
    export, ["held", "top_picks", "edge_list", "longlist", "watchlist", "elder_list"]
) if export else {}
universe = sorted(recs_all)
default_sel = [t for t in universe
               if recs_all[t].get("source") in ("held", "top_picks", "edge_list")]

c1, c2 = st.columns([2, 2])
with c1:
    typed = st.text_input("Type any tickers (comma/space separated)",
                          placeholder="e.g. NVDA, ASML, ANY-SYMBOL",
                          help="Priced even if not in the AQE universe — levels are "
                               "computed live from daily bars.")
with c2:
    picked = st.multiselect("…or pick from the export", universe, default=default_sel)

cc1, cc2 = st.columns([1, 1])
with cc1:
    risk = st.number_input("Risk $/trade", value=float(IC.RISK_BUDGET), step=100.0)
with cc2:
    interval = st.selectbox(
        "Calc bars (momentum read)",
        ["5min", "15min", "30min", "1hour", "4hour", "1min"], index=0,
        help="Timeframe for the momentum/VWAP read. The bracket also uses daily "
             "structure + 5-day hourly swing candidates regardless of this pick.")

typed_list = [t.strip().upper() for t in typed.replace(",", " ").split() if t.strip()]
tickers = list(dict.fromkeys(typed_list + list(picked)))   # de-dup, keep order

if st.button("Calculate brackets", type="primary", disabled=not tickers):
    results, missing = [], []
    prog = st.progress(0.0, text="Pricing…")
    for i, tk in enumerate(tickers, 1):
        b5 = _intraday(tk, interval)
        b1 = _intraday(tk, "1hour")
        ddf = _daily(tk)
        if not b5 and ddf is None:
            missing.append(tk)
        else:
            results.append(price_ticker(tk, recs_all.get(tk), b5, b1, ddf,
                                        regime=regime, risk_budget=risk))
        prog.progress(i / len(tickers), text=f"Priced {tk} ({i}/{len(tickers)})")
    prog.empty()
    st.session_state["pricer_results"] = [r for r in results if not r.get("error")]
    st.session_state["pricer_missing"] = missing

def _aic_block(p: dict) -> str:
    """Per-ticker, fact-only calculated summary to paste into the AIC.

    Captures everything computed — no judgement, no recommendation."""
    op = p["operative_stop"]
    rng = p.get("range_5d") or {}
    mom = p.get("momentum") or {}
    cand = "; ".join(
        f"{c['basis']}@{c['price']} (ATR×{c['atr_ratio']}, R:R{c['rr_tp2']}, "
        f"{c['stop_pct']}%)" for c in (p.get("candidates") or [])) or "none below entry"
    stp = "; ".join(f"{t['type']}@{t['price']} ({t['rr']}R)"
                    for t in (p.get("structural_tps") or [])) or "none"
    notes = "; ".join(p.get("notes") or []) or "none"
    return (
        f"AQE Pricer — {p['ticker']} ({lvl} regime) — CALCULATED FACTS (no view):\n"
        f"universe={'yes' if p['in_universe'] else 'typed'} | price={p['price']} | "
        f"ATR14d={p['atr_14d']} | 5d_range={rng.get('low')}-{rng.get('high')}\n"
        f"entry={p['entry']} | coil_entry={p['coil_entry']} | "
        f"operative_stop={op['price']} (basis={op['basis']}, risk={p['risk']}, "
        f"ATR×={op.get('atr_ratio')}, R:R_TP2={op.get('rr_tp2')}, "
        f"stop%={op.get('stop_pct')}, within_ceiling={op.get('within_ceiling')})\n"
        f"TP1={p['tp']['tp1']} (+1R) | TP2={p['tp']['tp2']} (+2R) | "
        f"TP3={p['tp']['tp3']} (+3R) | shares={p['shares']}\n"
        f"structural_TPs: {stp}\n"
        f"candidate_stops: {cand}\n"
        f"momentum(reference): IMS={p.get('ims')} state={p.get('state')} | "
        f"VWAP={mom.get('vwap')} pos={mom.get('vwap_pos_atr')}ATR "
        f"slope_up={mom.get('vwap_slope_up')} | OR_break={mom.get('or_break')} "
        f"(OR {mom.get('or_low')}-{mom.get('or_high')}) | "
        f"RVOL_pace={mom.get('rvol_pace')} | accel={mom.get('accel_atr_per_bar')} | "
        f"higher_lows={mom.get('higher_lows')} | ext={mom.get('ext_r')}R | "
        f"as_of={mom.get('as_of')}\n"
        f"notes: {notes}\n"
        f"IBKR(recommend-only): BUY {p['shares']} LMT {p['entry']} | "
        f"stop {op['price']} | TP {p['tp']['tp2']}"
    )


results = st.session_state.get("pricer_results")
if results:
    rows = []
    for p in results:
        op = p["operative_stop"]
        rng = p.get("range_5d") or {}
        rows.append({
            "Ticker": p["ticker"], "Univ": "✓" if p["in_universe"] else "typed",
            "Price": p["price"],
            "5d Range": f"{rng.get('low')}–{rng.get('high')}" if rng else "—",
            "Entry": p["entry"], "Stop": op["price"], "Basis": op["basis"],
            "Stop %": op.get("stop_pct"), "Risk": p["risk"], "Coil": p["coil_entry"],
            "TP1": p["tp"]["tp1"], "TP2": p["tp"]["tp2"], "TP3": p["tp"]["tp3"],
            "Shares": p["shares"], "IMS": p.get("ims"), "State": p.get("state"),
        })
    table_with_copy(pd.DataFrame(rows), key="pricer_main")
    st.caption("Stop = tightest level from the FIB/MA/DSL/swing menu (full metrics "
               "per name below). TP1/2/3 = mechanical +1/2/3R off the stop; "
               "structural targets per name. **No decision implied — facts only.**")

    for p in results:
        op = p["operative_stop"]
        with st.expander(f"{p['ticker']} — stop {op['price']} ({op['basis']}) · "
                         f"{p['shares']} sh · state {p.get('state')}"):
            if p.get("notes"):
                st.warning(" · ".join(p["notes"]))
            st.markdown("**Candidate levels (FIB / MA / DSL / swing — below entry)**")
            if p["candidates"]:
                table_with_copy(pd.DataFrame([
                    {"Basis": c["basis"], "Price": c["price"], "Risk": c["risk"],
                     "ATR×": c["atr_ratio"], "R:R-TP2": c["rr_tp2"],
                     "Stop %": c["stop_pct"], "ATR≥1": c["gate_atr"],
                     "R:R≥2": c["gate_rr"], "≤ceiling": c["within_ceiling"]}
                    for c in p["candidates"]]), key=f"cand_{p['ticker']}")
            else:
                st.caption("No structural support below entry — used the ATR fallback stop.")
            if p["structural_tps"]:
                st.markdown("**Structural take-profit targets (reference)**")
                table_with_copy(pd.DataFrame(p["structural_tps"]),
                                key=f"stp_{p['ticker']}")
            st.markdown("**📋 Copy this ticker for the AIC (facts only)**")
            st.code(_aic_block(p), language=None)

    missing = st.session_state.get("pricer_missing") or []
    if missing:
        st.caption(f"No price data for: {', '.join(missing)}")
else:
    st.info("Type tickers and/or pick from the export, then **Calculate brackets**.")
