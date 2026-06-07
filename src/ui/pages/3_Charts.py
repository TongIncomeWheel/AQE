"""AQE Charts — Page 3 of the multi-page app.

Visualises the daily price action for any scanned ticker so you don't need
TradingView to eyeball what AQE already computed. Candlesticks + 20/50/100/200
moving averages (the only price overlay) + a volume sub-panel, with the
ticker's AQE numbers (scores, beta, DSL bracket, sector) shown alongside.

End-of-day daily bars from the cached price panel. Needs a pipeline run first
(same as Math Lab) so panel_daily.parquet exists in the container.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Charts", page_icon=":chart_with_upwards_trend:",
                   layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, load_export  # noqa: E402

# Password gate — halts with a sign-in form until authenticated (public Space).
require_login()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from src.data.paths import PANEL_DAILY  # noqa: E402

st.title("AQE Charts")

if not PANEL_DAILY.exists():
    st.info(
        "Price panel not found. Open the **Scanner** page and run the daily "
        "pipeline first — charts read the same `panel_daily.parquet` that the "
        "scan builds."
    )
    st.stop()


@st.cache_data(ttl=900, show_spinner=False)
def _load_panel(_hash: str) -> pd.DataFrame:
    df = pd.read_parquet(
        PANEL_DAILY, columns=["date", "ticker", "open", "high", "low", "close", "volume"]
    )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


panel = _load_panel(str(PANEL_DAILY.stat().st_mtime_ns))
tickers = sorted(panel["ticker"].unique().tolist())
if "SPY" in tickers:
    tickers.remove("SPY")

# Build a lookup of each ticker's AQE record from the export (any tier).
export = load_export() or {}
aqe_lookup: dict[str, dict] = {}
for _tier in ("top_picks", "edge_list", "longlist", "watchlist"):
    for _rec in export.get(_tier, []) or []:
        aqe_lookup.setdefault(_rec.get("ticker"), {**_rec, "_tier": _tier})

# Default to the first top pick if present, else first ticker.
_default = None
if export.get("top_picks"):
    _default = export["top_picks"][0].get("ticker")
default_idx = tickers.index(_default) if _default in tickers else 0

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    sel = st.selectbox("Ticker", tickers, index=default_idx)
with c2:
    lookback = st.slider("Bars shown", 60, 500, 250, step=10)
with c3:
    log_y = st.toggle("Log scale", value=False)

g = panel[panel["ticker"] == sel].sort_values("date").reset_index(drop=True)
if g.empty or len(g) < 2:
    st.warning(f"No price history for {sel}.")
    st.stop()

# Moving averages computed on full history, then sliced to the lookback window
# so the lines are populated from the first visible bar.
for w in (20, 50, 100, 200):
    g[f"ma{w}"] = g["close"].rolling(w).mean()

disp = g.tail(lookback).copy()

_MA_COLORS = {20: "#F0A500", 50: "#3BA3FF", 100: "#B36BFF", 200: "#FF5C8A"}

fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
    row_heights=[0.78, 0.22],
)

fig.add_trace(
    go.Candlestick(
        x=disp["date"], open=disp["open"], high=disp["high"],
        low=disp["low"], close=disp["close"], name=sel,
        increasing_line_color="#26A69A", decreasing_line_color="#EF5350",
    ),
    row=1, col=1,
)
for w, color in _MA_COLORS.items():
    fig.add_trace(
        go.Scatter(x=disp["date"], y=disp[f"ma{w}"], name=f"MA{w}",
                   line=dict(width=1.3, color=color), connectgaps=True),
        row=1, col=1,
    )

vol_colors = np.where(disp["close"] >= disp["open"], "#26A69A", "#EF5350")
fig.add_trace(
    go.Bar(x=disp["date"], y=disp["volume"], name="Volume",
           marker_color=vol_colors, opacity=0.6),
    row=2, col=1,
)

fig.update_layout(
    template="plotly_dark", height=720, margin=dict(l=10, r=10, t=30, b=10),
    xaxis_rangeslider_visible=False, showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    hovermode="x unified",
)
# Hide weekend gaps so the daily series is continuous.
fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
fig.update_yaxes(title_text="Price", type="log" if log_y else "linear", row=1, col=1)
fig.update_yaxes(title_text="Vol", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# AQE numbers for the selected ticker (read from the export — the AIC schema)
# ---------------------------------------------------------------------------
rec = aqe_lookup.get(sel)
last = g.iloc[-1]
st.subheader(f"{sel} — AQE numbers")
if rec is None:
    st.caption("Not in today's lists (top_picks / edge / longlist / watchlist).")
else:
    st.caption(f"Source tier: **{rec.get('_tier')}**  ·  "
               f"sector: {rec.get('gics_sector') or '—'} "
               f"({rec.get('gics_sector_name') or '—'})  ·  "
               f"gate: {rec.get('gics_gate') or '—'}")


def _f(v, spec=".2f"):
    return "—" if v is None or (isinstance(v, float) and v != v) else format(v, spec)


r = rec or {}
m1, m2, m3, m4 = st.columns(4)
m1.metric("Last close", _f(float(last["close"])))
m1.metric("SC_MOM", _f(r.get("sc_momentum"), ".1f"))
m1.metric("PTRS", _f(r.get("ptrs"), ".1f"))
m2.metric("Flow", _f(r.get("flow"), ".0f"))
m2.metric("Energy", _f(r.get("energy"), ".0f"))
m2.metric("Structure", _f(r.get("structure"), ".0f"))
m3.metric("MP", _f(r.get("mp"), ".0f"))
m3.metric("Elder", _f(r.get("elder"), ".1f"))
m3.metric("RVOL", _f(r.get("rvol")))
m4.metric("Beta 30 / 60", f"{_f(r.get('beta_30d'))} / {_f(r.get('beta_60d'))}")
m4.metric("RS vs SPY 20d", _f(r.get("rs_spy_20d")))
m4.metric("Dist 50DMA %", _f(r.get("sma_distance_pct")))

if rec is not None:
    st.markdown("**DSL bracket**")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Entry (be)", _f(r.get("dsl_be")))
    d1.metric("Stop", _f(r.get("dsl_stop")))
    d2.metric("TP1", _f(r.get("dsl_tp_1r")))
    d2.metric("TP2", _f(r.get("dsl_tp_2r")))
    d3.metric("TP3", _f(r.get("dsl_tp_3r")))
    d3.metric("ATR ratio", _f(r.get("dsl_atr_ratio")))
    d4.metric("R:R tp1/2/3", f"{_f(r.get('rr_tp1'))} / {_f(r.get('rr_tp2'))} / {_f(r.get('rr_tp3'))}")
    d4.metric("ATR(14d)", _f(r.get("atr_14d")))
