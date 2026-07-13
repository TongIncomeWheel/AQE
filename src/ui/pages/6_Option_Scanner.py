"""AQE Universe Option Scanner — a filterable theta scanner for the income wheel.

Sweeps the whole AQE universe for cash-secured puts worth selling (data from Alpaca's
free option-chain snapshot — IV + greeks + quotes, one call per name, no throttle).
Reads the nightly sweep `output/options_scan.json`; you filter it live (annualised
yield / delta band / DTE / POP / cushion). Recommend-only — AQE computes the numbers,
the AIC decides + sizes. Can also run an on-demand sweep on a typed ticker subset.
"""

from __future__ import annotations

import os
import sys
import json
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Option Scanner", page_icon=":ok:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, table_with_copy, OUTPUT_DIR  # noqa: E402

require_login()

import pandas as pd  # noqa: E402
from src.options import config as OC  # noqa: E402

SCAN_FILE = OUTPUT_DIR / "options_scan.json"

st.title("🎯 Universe Option Scanner — CSP theta")
st.caption("Cash-secured puts across the AQE universe · Alpaca-fed · recommend-only "
           "(AQE computes numbers; the AIC decides + sizes).")


def _load_scan() -> dict | None:
    if SCAN_FILE.exists():
        try:
            return json.loads(SCAN_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ── On-demand sweep (subset — the full universe sweep is the nightly job) ────
with st.expander("↻ Run a scan now (on-demand)", expanded=False):
    have_keys = bool(os.environ.get(OC.ALPACA_KEY_ID_ENV) and
                     os.environ.get(OC.ALPACA_SECRET_ENV))
    if not have_keys:
        st.info(f"Set **{OC.ALPACA_KEY_ID_ENV}** + **{OC.ALPACA_SECRET_ENV}** as "
                "deploy secrets to enable live scans. The nightly job writes "
                "`options_scan.json` unattended once they're set.")
    subset = st.text_input("Tickers (comma list; blank = full universe — slower)", "")
    c1, c2, c3 = st.columns(3)
    dmin = c1.number_input("DTE min", 1, 365, OC.UNIVERSE_DTE_MIN)
    dmax = c2.number_input("DTE max", 1, 365, OC.UNIVERSE_DTE_MAX)
    if c3.button("Run scan", disabled=not have_keys, use_container_width=True):
        from src.options.universe_scan import scan_universe, write_scan
        tk = [t.strip().upper() for t in subset.split(",") if t.strip()] or None
        with st.spinner("Scanning… (full universe ≈ a few minutes)"):
            blob = scan_universe(tickers=tk, dte_min=int(dmin), dte_max=int(dmax),
                                 log=lambda *_: None)
            write_scan(blob, str(SCAN_FILE))
        st.success(f"Scanned — {blob['candidates_count']} candidates. Reloading…")
        st.rerun()

scan = _load_scan()
if not scan:
    st.warning("No scan yet. Run one above, or wait for the nightly job to write "
               "`output/options_scan.json`.")
    st.stop()

rows = scan.get("candidates", [])
st.caption(f"Sweep for **{scan.get('generated_for')}** · DTE "
           f"{scan.get('dte_window')} · {scan.get('candidates_count')} candidates "
           f"across {len({r['ticker'] for r in rows})} names "
           f"({scan.get('priced')}/{scan.get('universe_size')} priced).")

if not rows:
    st.info("Sweep ran but no CSP cleared the filters.")
    st.stop()

df = pd.DataFrame(rows)

# ── Live filters ────────────────────────────────────────────────────────────
st.sidebar.header("Filters")
ay_min = st.sidebar.slider("Min annualised yield %", 0, 200, 20) / 100.0
d_lo, d_hi = st.sidebar.slider("Delta band |Δ|", 0.0, 1.0,
                               (OC.CSP_DELTA_MIN, OC.CSP_DELTA_MAX), 0.01)
pop_min = st.sidebar.slider("Min POP (not assigned) %", 0, 100, 60) / 100.0
cush_min = st.sidebar.slider("Min downside cushion %", 0, 50, 0) / 100.0
dte_lo, dte_hi = st.sidebar.slider("DTE", 0, 365,
                                   tuple(scan.get("dte_window", [20, 50])))
names = sorted(df["ticker"].unique())
pick = st.sidebar.multiselect("Tickers (blank = all)", names, [])

f = df.copy()
f = f[(f["annual_yield"].fillna(0) >= ay_min) &
      (f["abs_delta"].fillna(0).between(d_lo, d_hi)) &
      (f["pop_not_assigned"].fillna(0) >= pop_min) &
      (f["downside_cushion"].fillna(-9) >= cush_min) &
      (f["dte"].between(dte_lo, dte_hi))]
if pick:
    f = f[f["ticker"].isin(pick)]
f = f.sort_values("annual_yield", ascending=False)

st.subheader(f"{len(f)} matches")
cols = ["ticker", "strike", "dte", "abs_delta", "credit_per_contract", "annual_yield",
        "pop_not_assigned", "downside_cushion", "breakeven", "theta_credit_day",
        "collateral", "iv"]
show = f[[c for c in cols if c in f.columns]].rename(columns={
    "abs_delta": "delta", "credit_per_contract": "credit", "annual_yield": "ann_yield",
    "pop_not_assigned": "pop_safe", "downside_cushion": "cushion",
    "theta_credit_day": "theta/day"})
table_with_copy(show, key="universe_csp")

if len(f):
    b = f.iloc[0]
    st.success(f"Top: **SELL {b['ticker']} {b['strike']:.0f}P {int(b['dte'])}DTE** — "
               f"${b['credit_per_contract']:.0f} credit, {b['annual_yield']*100:.0f}% "
               f"annualised, {b['pop_not_assigned']*100:.0f}% not-assigned, breakeven "
               f"{b['breakeven']:.2f}. Numbers only — the AIC sizes/decides.")
