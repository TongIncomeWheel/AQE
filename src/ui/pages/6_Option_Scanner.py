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


# ── Run a scan (full universe → Drive, or a local subset) ───────────────────
with st.expander("↻ Run a scan", expanded=True):
    have_keys = bool(os.environ.get(OC.ALPACA_KEY_ID_ENV) and
                     os.environ.get(OC.ALPACA_SECRET_ENV))
    if not have_keys:
        st.info(f"Set **{OC.ALPACA_KEY_ID_ENV}** + **{OC.ALPACA_SECRET_ENV}** as "
                "deploy secrets to enable live scans.")
    subset = st.text_input("Subset tickers (comma list; used by the local button)", "")
    c1, c2 = st.columns(2)
    dmin = c1.number_input("DTE min", 1, 365, OC.UNIVERSE_DTE_MIN)
    dmax = c2.number_input("DTE max", 1, 365, OC.UNIVERSE_DTE_MAX)
    b1, b2 = st.columns(2)
    run_full = b1.button("🚀 Run full scan → Drive", disabled=not have_keys,
                         use_container_width=True,
                         help="Sweep the whole AQE universe and overwrite the single "
                              "CSP file in the Drive folder.")
    run_sub = b2.button("Run subset (local only)",
                        disabled=not have_keys or not subset.strip(),
                        use_container_width=True)
    if run_full or run_sub:
        from src.options.universe_scan import (scan_universe, write_scan,
                                               export_scan_to_drive)
        tk = ([t.strip().upper() for t in subset.split(",") if t.strip()]
              if run_sub else None)
        with st.spinner("Scanning… full universe ≈ a few minutes"):
            blob = scan_universe(tickers=tk, dte_min=int(dmin), dte_max=int(dmax),
                                 log=lambda *_: None)
            if run_full:
                res = export_scan_to_drive(blob, str(SCAN_FILE))
                dr = res["drive"]
                if dr.get("ok"):
                    st.success(f"Scanned {blob['candidates_count']} candidates → Drive "
                               f"({'replaced' if dr.get('replaced') else 'created'} "
                               f"`{OC.CSP_SCAN_FILENAME}`).")
                else:
                    st.warning(f"Scanned {blob['candidates_count']} — saved locally; "
                               f"Drive upload failed: {dr.get('reason')}")
            else:
                write_scan(blob, str(SCAN_FILE))
                st.success(f"Scanned {blob['candidates_count']} candidates (local).")
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

# ── Live filters (triage a long list) ───────────────────────────────────────
st.sidebar.header("Filters")
d_lo, d_hi = st.sidebar.slider("Delta band |Δ|", 0.0, 1.0,
                               (OC.CSP_DELTA_MIN, OC.CSP_DELTA_MAX), 0.01,
                               help="Short-put delta. Lower = further OTM / safer.")
pop_min = st.sidebar.slider("Min POP % (prob. of profit)", 0, 100, 70,
                            help="P(finish above breakeven) — keep the premium.") / 100.0
dist_min = st.sidebar.slider("Min distance to strike %", 0, 40, 0,
                             help="How far OTM the strike sits below spot.") / 100.0
ay_min = st.sidebar.slider("Min annualised yield %", 0, 200, 20) / 100.0
cush_min = st.sidebar.slider("Min downside cushion %", 0, 50, 0,
                             help="Spot vs breakeven (strike − credit).") / 100.0
_slot = int(OC.CAPITAL / OC.MAX_POSITIONS)
cap_max = st.sidebar.number_input(
    "Max collateral $ / contract (0 = no cap)", 0, 500_000, 0, step=500,
    help=f"Cash-secured = strike × 100. One of {OC.MAX_POSITIONS} slots ≈ ${_slot:,}.")
dte_lo, dte_hi = st.sidebar.slider("DTE", 0, 365,
                                   tuple(scan.get("dte_window", [20, 50])))
names = sorted(df["ticker"].unique())
pick = st.sidebar.multiselect("Tickers (blank = all)", names, [])

f = df.copy()
f = f[(f["annual_yield"].fillna(0) >= ay_min) &
      (f["abs_delta"].fillna(0).between(d_lo, d_hi)) &
      (f.get("pop", pd.Series(0, index=f.index)).fillna(0) >= pop_min) &
      (f.get("distance_to_strike_pct", pd.Series(0, index=f.index)).fillna(0) >= dist_min) &
      (f["downside_cushion"].fillna(-9) >= cush_min) &
      (f["dte"].between(dte_lo, dte_hi))]
if cap_max:
    f = f[f["collateral"].fillna(0) <= cap_max]
if pick:
    f = f[f["ticker"].isin(pick)]
f = f.sort_values("annual_yield", ascending=False)

st.subheader(f"{len(f)} matches")
# Build a display frame with percentages as numeric %-scaled columns (sortable).
disp = pd.DataFrame({"ticker": f["ticker"], "strike": f["strike"], "dte": f["dte"]})
if "abs_delta" in f.columns:
    disp["delta"] = f["abs_delta"].round(3)
for label, src in [("dist_to_strike_%", "distance_to_strike_pct"), ("POP_%", "pop"),
                   ("not_assigned_%", "pop_not_assigned"), ("ann_yield_%", "annual_yield"),
                   ("cushion_%", "downside_cushion"), ("iv_%", "iv")]:
    if src in f.columns:
        disp[label] = (f[src] * 100).round(1)
for label, src in [("credit$", "credit_per_contract"), ("breakeven", "breakeven"),
                   ("theta/day", "theta_credit_day"), ("collateral", "collateral")]:
    if src in f.columns:
        disp[label] = f[src]
table_with_copy(disp, key="universe_csp")

if len(f):
    b = f.iloc[0]
    st.success(f"Top: **SELL {b['ticker']} {b['strike']:.0f}P {int(b['dte'])}DTE** — "
               f"${b['credit_per_contract']:.0f} credit, {b['annual_yield']*100:.0f}% "
               f"annualised, {b['pop_not_assigned']*100:.0f}% not-assigned, breakeven "
               f"{b['breakeven']:.2f}. Numbers only — the AIC sizes/decides.")
