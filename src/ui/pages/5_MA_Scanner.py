"""MA Proximity Scanner — stocks near key moving averages.

Shows all US stocks (>$1B market cap) within ±10% of their 20/50/100/200
SMA, with consecutive-day streak counts. Updated daily by the pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.shared import require_login, table_with_copy

st.set_page_config(page_title="AQE — MA Scanner", layout="wide")
require_login()

st.title("MA Proximity Scanner")
st.caption("US stocks >$1B within ±10% of key moving averages")

PROXIMITY_PCT = 10.0


# ── Load data ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _load_scan():
    from src.scanner.ma_scanner import load_latest_scan
    return load_latest_scan()


df = _load_scan()

if df.empty:
    st.warning(
        "No MA scan data yet. Run the daily pipeline or click **Run MA Scan** below."
    )
    if st.button("Run MA Scan", type="primary"):
        with st.spinner("Running MA scan (this pulls bars from FMP — may take several minutes on first run)..."):
            from src.scanner.ma_scanner import run_ma_scan
            result = run_ma_scan()
            if result.get("ok"):
                st.success(f"Scan complete — {result['stats']['near_any_ma']} stocks near at least one MA")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Scan failed: {result.get('reason')}")
    st.stop()


# ── Summary metrics ─────────────────────────────────────────────────────
scan_date = df["date"].max()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Scan Date", scan_date.strftime("%Y-%m-%d") if pd.notna(scan_date) else "—")
c2.metric("Near SMA20", int(df["near_sma20"].sum()))
c3.metric("Near SMA50", int(df["near_sma50"].sum()))
c4.metric("Near SMA100", int(df["near_sma100"].sum()))
c5.metric("Near SMA200", int(df["near_sma200"].sum()))

# Re-upload the already-computed scan to Drive — no FMP re-pull.
_ub, _um = st.columns([1, 3])
if _ub.button("⬆️ Upload to Drive", use_container_width=True,
              help="Re-publish the CURRENT scan (data/ma_scan.parquet) to the Drive "
                   "folder as aqe_ma_scan.json — no re-pull, near-instant."):
    from src.scanner.ma_scanner import republish_ma_scan
    with st.spinner("Uploading aqe_ma_scan.json to Drive…"):
        _r = republish_ma_scan()
    if _r.get("ok"):
        _um.success(f"Uploaded **aqe_ma_scan.json** → Drive "
                    f"({'replaced' if _r.get('replaced') else 'created'}).")
    else:
        _um.warning(f"Upload: {_r.get('reason')}")

st.divider()

# ── Filters ─────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    ma_filter = st.multiselect(
        "Show stocks near",
        ["SMA20", "SMA50", "SMA100", "SMA200"],
        default=["SMA50", "SMA100", "SMA200"],
    )

with col_f2:
    side_filter = st.selectbox("Side", ["Both", "ABOVE", "BELOW"])

with col_f3:
    max_dist = st.slider("Max distance from MA (%)", 1.0, 10.0, 10.0, 0.5)

with col_f4:
    min_days = st.number_input("Min days near", min_value=0, max_value=200, value=0)

col_f5, col_f6 = st.columns(2)
with col_f5:
    _sectors = sorted(df["sector"].dropna().unique()) if "sector" in df.columns else []
    sector_filter = st.multiselect("Sector", _sectors, default=[], key="ma_sector_filter",
                                   help="Leave empty for all sectors")
with col_f6:
    primary_only = st.checkbox("Primary listings only", value=True,
                               help="Exclude preferred shares, units, class-B duplicates")
    aqe_only = st.checkbox("AQE universe only", value=False)

# ── Apply filters ───────────────────────────────────────────────────────
filtered = df.copy()

ma_map = {"SMA20": 20, "SMA50": 50, "SMA100": 100, "SMA200": 200}
if ma_filter:
    periods = [ma_map[m] for m in ma_filter]
    mask = pd.Series(False, index=filtered.index)
    for p in periods:
        near_col = f"near_sma{p}"
        dist_col = f"dist_sma{p}"
        days_col = f"days_near_{p}"
        side_col = f"side_sma{p}"

        p_mask = filtered[near_col] & (filtered[dist_col].abs() <= max_dist)
        if min_days > 0:
            p_mask = p_mask & (filtered[days_col] >= min_days)
        if side_filter != "Both":
            p_mask = p_mask & (filtered[side_col] == side_filter)
        mask = mask | p_mask
    filtered = filtered[mask]

if primary_only and "ticker" in filtered.columns:
    _has_dash = filtered["ticker"].str.contains("-", na=False)
    filtered = filtered[~_has_dash]

if sector_filter and "sector" in filtered.columns:
    filtered = filtered[filtered["sector"].isin(sector_filter)]

if aqe_only and "in_aqe" in filtered.columns:
    filtered = filtered[filtered["in_aqe"]]

# ── Format display table ────────────────────────────────────────────────
if filtered.empty:
    st.info("No stocks match the current filters.")
    st.stop()

display_cols = ["ticker", "name", "close", "market_cap", "sector"]
for p in [20, 50, 100, 200]:
    display_cols.extend([
        f"sma_{p}", f"dist_sma{p}", f"side_sma{p}", f"days_near_{p}",
    ])
display_cols.append("ma_near_count")
if "in_aqe" in filtered.columns:
    display_cols.append("in_aqe")

available = [c for c in display_cols if c in filtered.columns]
show = filtered[available].copy()

# Format market cap
if "market_cap" in show.columns:
    show["market_cap"] = show["market_cap"].apply(
        lambda x: f"${x/1e9:.1f}B" if pd.notna(x) and x >= 1e9
        else (f"${x/1e6:.0f}M" if pd.notna(x) else "—")
    )

# Rename for display
rename = {
    "ma_near_count": "MAs Near",
    "in_aqe": "AQE",
    "market_cap": "Mkt Cap",
}
for p in [20, 50, 100, 200]:
    rename[f"sma_{p}"] = f"SMA{p}"
    rename[f"dist_sma{p}"] = f"Dist{p}%"
    rename[f"side_sma{p}"] = f"Side{p}"
    rename[f"days_near_{p}"] = f"Days{p}"

show = show.rename(columns={k: v for k, v in rename.items() if k in show.columns})

# Sort by most MAs near, then by closest distance to any MA
sort_col = "MAs Near" if "MAs Near" in show.columns else show.columns[0]
show = show.sort_values(sort_col, ascending=False).reset_index(drop=True)

st.subheader(f"{len(show)} stocks matching filters")
table_with_copy(show, key="ma_scan")

# ── Breakdown by MA ─────────────────────────────────────────────────────
st.divider()
st.subheader("Breakdown by MA")

for p in [20, 50, 100, 200]:
    near_col = f"near_sma{p}"
    dist_col = f"dist_sma{p}"
    days_col = f"days_near_{p}"
    side_col = f"side_sma{p}"

    if near_col not in df.columns:
        continue

    near = df[df[near_col]].copy()
    if near.empty:
        continue

    with st.expander(f"SMA {p} — {len(near)} stocks within ±{PROXIMITY_PCT}%", expanded=False):
        above = near[near[side_col] == "ABOVE"]
        below = near[near[side_col] == "BELOW"]

        ca, cb = st.columns(2)
        ca.metric("Above", len(above))
        cb.metric("Below", len(below))

        # Top 20 closest to MA (smallest absolute distance)
        closest = near.nsmallest(20, dist_col, keep="first")
        sub_cols = ["ticker", "name", "close", f"sma_{p}", dist_col, side_col, days_col, "sector"]
        sub_avail = [c for c in sub_cols if c in closest.columns]
        st.caption(f"Top 20 closest to SMA{p}")
        st.dataframe(closest[sub_avail], use_container_width=True, hide_index=True)

        # Longest streaks
        longest = near.nlargest(20, days_col, keep="first")
        st.caption(f"Top 20 longest streaks near SMA{p}")
        st.dataframe(longest[sub_avail], use_container_width=True, hide_index=True)

# ── Refresh button ──────────────────────────────────────────────────────
st.divider()
with st.expander("Manual refresh"):
    st.caption("Re-run the MA scan (pulls latest bars from FMP)")
    if st.button("Refresh MA Scan"):
        with st.spinner("Running..."):
            from src.scanner.ma_scanner import run_ma_scan
            result = run_ma_scan()
            if result.get("ok"):
                st.success(f"Done — {result['stats']['near_any_ma']} stocks near at least one MA")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Failed: {result.get('reason')}")
