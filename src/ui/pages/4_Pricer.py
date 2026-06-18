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

from src.ui.shared import require_login, load_export  # noqa: E402

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
    interval = st.selectbox("Momentum bars", ["5min", "15min", "1min"], index=0)

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
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Stop = tightest valid level from the menu (3-gate metrics shown per "
               "name below). TP1/2/3 are mechanical +1/2/3R off the operative stop; "
               "structural targets listed per name. **No decision is implied.**")

    for p in results:
        op = p["operative_stop"]
        with st.expander(f"{p['ticker']} — stop {op['price']} ({op['basis']}) · "
                         f"{p['shares']} sh · state {p.get('state')}"):
            if p.get("notes"):
                st.warning(" · ".join(p["notes"]))
            st.markdown("**Candidate levels (FIB / MA / DSL / swing — below entry)**")
            if p["candidates"]:
                st.dataframe(pd.DataFrame([
                    {"Basis": c["basis"], "Price": c["price"], "Risk": c["risk"],
                     "ATR×": c["atr_ratio"], "R:R-TP2": c["rr_tp2"],
                     "Stop %": c["stop_pct"], "ATR≥1": c["gate_atr"],
                     "R:R≥2": c["gate_rr"], "≤ceiling": c["within_ceiling"]}
                    for c in p["candidates"]]),
                    use_container_width=True, hide_index=True)
            else:
                st.caption("No structural support below entry — used the ATR fallback stop.")
            if p["structural_tps"]:
                st.markdown("**Structural take-profit targets (reference)**")
                st.dataframe(pd.DataFrame(p["structural_tps"]),
                             use_container_width=True, hide_index=True)
            s = p["ibkr_spec"]
            st.code(f"{s['symbol']}: BUY {s['quantity']} @ {s['order_type']} "
                    f"{s['entry']} | stop {s['stop']} | TP {s['take_profit']}",
                    language=None)
            mom = p.get("momentum") or {}
            if mom:
                st.caption(
                    f"Momentum (reference): VWAP {mom.get('vwap')} · pos "
                    f"{mom.get('vwap_pos_atr')} ATR · OR break {mom.get('or_break')} "
                    f"· RVOL pace {mom.get('rvol_pace')} · ext {mom.get('ext_r')}R "
                    f"· as of {mom.get('as_of')}")

    # Paste-to-AIC block (numbers only — no call)
    lines = []
    for p in results:
        op = p["operative_stop"]
        lines.append(
            f"{p['ticker']}: price {p['price']}, entry {p['entry']}, stop {op['price']} "
            f"({op['basis']}, {op.get('stop_pct')}%), coil {p['coil_entry']}, "
            f"TP {p['tp']['tp1']}/{p['tp']['tp2']}/{p['tp']['tp3']}, {p['shares']} sh, "
            f"IMS {p.get('ims')} {p.get('state')}")
    st.markdown("##### Paste-to-AIC (calculated levels — you decide)")
    st.text_area("Copy:", f"AQE Pricer ({lvl} regime):\n" + "\n".join(lines), height=160)

    missing = st.session_state.get("pricer_missing") or []
    if missing:
        st.caption(f"No price data for: {', '.join(missing)}")
else:
    st.info("Type tickers and/or pick from the export, then **Calculate brackets**.")
