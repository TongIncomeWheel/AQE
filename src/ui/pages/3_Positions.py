"""Aegis Quant Engine -- Position Manager.

Live portfolio dashboard. Reads open_positions.json for position data
and enriches each ticker with live engine scores from scores_daily.parquet.

Shows levels, risk, engine health, and actionable trade-management advice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Positions", page_icon=":briefcase:", layout="wide")

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import (
    CAPITAL,
    DATA_DIR,
    ETF_NAMES,
    RISK_BUDGET,
    RISK_PCT,
    file_hash,
    is_cloud_mode,
)
from src.data.panel_builder import PANEL_DAILY
from src.scanner.score_runner import SCORES_DAILY

st.title("Position Manager")

# Positions need the parquets and the open_positions.json (gitignored, lives
# only on the local PC). The page is therefore desktop-only on the cloud
# deploy unless the user uploads open_positions.json via Universe upload (not
# supported today). Keep it disabled in cloud mode to avoid leaking position
# data and to keep the cloud's ephemeral RAM lean.
if is_cloud_mode():
    st.info(
        "Position Manager is desktop-only. It reads `data/open_positions.json` "
        "which lives on your local PC (gitignored) and enriches each ticker with "
        "scores from the panel + score parquets. Open the desktop AQE app for "
        "this page."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(val, spec: str = ".2f") -> str:
    if val is None:
        return "---"
    if isinstance(val, float) and val != val:
        return "---"
    return format(val, spec)


def _sector_label(etf: str) -> str:
    return ETF_NAMES.get(etf, etf)


def _load_latest_scores(tickers: list[str]) -> dict[str, dict]:
    """Return {ticker: {col: val}} for the most recent date in scores_daily."""
    if not SCORES_DAILY.exists():
        return {}
    df = pd.read_parquet(SCORES_DAILY)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    latest = df.loc[df["ticker"].isin(tickers)]
    if latest.empty:
        return {}
    latest_date = latest["date"].max()
    latest = latest.loc[latest["date"] == latest_date]
    return {row["ticker"]: row.to_dict() for _, row in latest.iterrows()}


def _load_latest_prices(tickers: list[str]) -> dict[str, dict]:
    """Return {ticker: {close, high, low, volume}} from panel_daily."""
    if not PANEL_DAILY.exists():
        return {}
    df = pd.read_parquet(PANEL_DAILY)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    sub = df.loc[df["ticker"].isin(tickers)]
    if sub.empty:
        return {}
    latest_date = sub["date"].max()
    sub = sub.loc[sub["date"] == latest_date]
    return {row["ticker"]: row.to_dict() for _, row in sub.iterrows()}


def _advice(pos: dict, scores: dict) -> tuple[str, str, str]:
    """Return (action, colour, explanation) for a position."""
    ticker = pos["ticker"]
    close = pos.get("close", 0)
    stop = pos.get("stop", 0)
    entry = pos.get("entry", 0)
    t1r = pos.get("target_1r", 0)
    t2r = pos.get("target_2r", 0)
    t3r = pos.get("target_3r", 0)
    be = pos.get("be_trigger", 0)
    pnl_r = pos.get("pnl_r", 0) or 0
    grade = pos.get("srm_grade", "")
    decel = pos.get("srm_note", "")

    # Engine scores from latest data
    sc = scores.get(ticker, {})
    flow = sc.get("flow_100", None)
    energy = sc.get("energy_100", None)
    structure = sc.get("structure_100", None)
    mp = sc.get("mp_100", None)
    elder = sc.get("elder_score", None)

    # Option positions -- simplified
    if pos.get("type") == "option":
        return "MONITOR", "blue", f"CSP position in {_sector_label(pos.get('sector_etf', ''))} ({grade}). Monitor assignment risk."

    reasons = []

    # Price vs levels — escalating trail (only the highest level fires)
    if stop and close and close <= stop:
        return "EXIT", "red", f"Price ${close:.2f} is at or below stop ${stop:.2f}. Close immediately."

    if t3r and close and close >= t3r:
        return "RUNNER", "green", (
            f"Price ${close:.2f} has reached +3R target ${t3r:.2f}. "
            f"Trail stop to +2R (${t2r:.2f}) and let the runner ride."
        )

    if t2r and close and close >= t2r:
        reasons.append(f"Price in +2R/+3R zone. Trail stop to +1R (${t1r:.2f}).")
    elif t1r and close and close >= t1r:
        reasons.append(f"Above +1R. Trail stop to breakeven (${entry:.2f}).")
    elif be and close and close >= be:
        reasons.append(f"Above BE trigger (${be:.2f}). Move stop to breakeven (${entry:.2f}).")

    # Sector health
    if grade == "AVOID":
        reasons.append(f"Sector {_sector_label(pos.get('sector_etf', ''))} graded AVOID -- headwinds.")
    elif grade == "TURNING":
        reasons.append(f"Sector graded TURNING -- weakening, watch for deterioration.")
    if decel == "DECEL":
        reasons.append("Sector decelerating (5d momentum fading).")

    # Engine health
    engine_warns = []
    if flow is not None and flow < 50:
        engine_warns.append(f"Flow weak ({flow:.0f})")
    if energy is not None and energy < 40:
        engine_warns.append(f"Energy fading ({energy:.0f})")
    if structure is not None and structure < 40:
        engine_warns.append(f"Structure breaking ({structure:.0f})")
    if mp is not None and mp < 40:
        engine_warns.append(f"MP deteriorating ({mp:.0f})")
    if elder is not None and elder < 5:
        engine_warns.append(f"Elder impulse weak ({elder:.0f})")

    if engine_warns:
        reasons.append("Engine warnings: " + ", ".join(engine_warns) + ".")

    # Distance to stop
    if stop and close and entry:
        dist_stop_pct = (close - stop) / close * 100
        if dist_stop_pct < 3:
            reasons.append(f"Only {dist_stop_pct:.1f}% above stop -- tight.")

    # Overall assessment
    if not reasons:
        if pnl_r > 0.5:
            return "HOLD", "green", f"Position healthy at +{pnl_r:.2f}R. All engines nominal. Hold and let it work."
        else:
            return "HOLD", "green", "Position within normal range. No action needed. Let the trade develop."

    n_warns = len(engine_warns)
    if grade == "AVOID" or n_warns >= 3:
        action = "TIGHTEN"
        colour = "orange"
    elif close and t1r and close >= t1r:
        action = "TRAIL"
        colour = "blue"
    elif close and be and close >= be:
        action = "PROTECT"
        colour = "blue"
    elif n_warns >= 2 or grade == "TURNING":
        action = "WATCH"
        colour = "orange"
    else:
        action = "HOLD"
        colour = "green"

    return action, colour, " ".join(reasons)


# ---------------------------------------------------------------------------
# Load positions
# ---------------------------------------------------------------------------

positions_path = DATA_DIR / "open_positions.json"
if not positions_path.exists():
    st.info("No open_positions.json found. Add positions via your Google Sheet or create the file manually.")
    st.stop()

with open(positions_path) as f:
    positions = json.load(f)

if not positions:
    st.info("No open positions tracked.")
    st.stop()

stock_positions = [p for p in positions if p.get("type") != "option"]
option_positions = [p for p in positions if p.get("type") == "option"]
all_tickers = [p["ticker"] for p in positions if p.get("ticker")]

# ---------------------------------------------------------------------------
# Load live engine scores & prices
# ---------------------------------------------------------------------------

scores = _load_latest_scores(all_tickers)
prices = _load_latest_prices(all_tickers)

# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

st.subheader("Portfolio Overview")

total_risk = sum(
    (p.get("r_size", 0) or 0) * (p.get("shares", 0) or 0)
    for p in stock_positions
)
total_pnl = sum(p.get("pnl_dollars", 0) or 0 for p in stock_positions)
total_exposure = sum(
    (p.get("close", 0) or 0) * (p.get("shares", 0) or 0)
    for p in stock_positions
)

ov1, ov2, ov3, ov4 = st.columns(4)
with ov1:
    st.metric("Open Positions", f"{len(stock_positions)} stocks" + (f" + {len(option_positions)} options" if option_positions else ""))
with ov2:
    st.metric("Total Open P&L", f"${total_pnl:+,.0f}")
with ov3:
    st.metric("Total Risk at Stop", f"${total_risk:,.0f}")
with ov4:
    exposure_pct = total_exposure / CAPITAL * 100 if CAPITAL else 0
    st.metric("Gross Exposure", f"{exposure_pct:.0f}% of capital")

# Sector breakdown
sectors = {}
for p in stock_positions:
    etf = p.get("sector_etf", "???")
    sectors.setdefault(etf, []).append(p["ticker"])
sector_str = " | ".join(
    f"**{_sector_label(etf)}:** {', '.join(tks)}"
    for etf, tks in sectors.items()
)
st.markdown(f"Sector exposure: {sector_str}")

st.divider()

# ---------------------------------------------------------------------------
# Position table
# ---------------------------------------------------------------------------

st.subheader("Position Grid")

rows = []
for p in stock_positions:
    t = p["ticker"]
    sc = scores.get(t, {})
    rows.append({
        "Ticker": t,
        "Entry": _fmt(p.get("entry"), ".2f"),
        "Now": _fmt(p.get("close"), ".2f"),
        "Stop": _fmt(p.get("stop"), ".2f"),
        "+1R": _fmt(p.get("target_1r"), ".2f"),
        "+2R": _fmt(p.get("target_2r"), ".2f"),
        "+3R": _fmt(p.get("target_3r"), ".2f"),
        "QTY": _fmt(p.get("shares"), ".0f"),
        "P&L R": _fmt(p.get("pnl_r"), "+.2f"),
        "P&L $": _fmt(p.get("pnl_dollars"), "+,.0f"),
        "Flow": _fmt(sc.get("flow_100"), ".0f"),
        "Energy": _fmt(sc.get("energy_100"), ".0f"),
        "Struct": _fmt(sc.get("structure_100"), ".0f"),
        "MP": _fmt(sc.get("mp_100"), ".0f"),
        "Elder": _fmt(sc.get("elder_score"), ".1f"),
        "Sector": f"{_sector_label(p.get('sector_etf', ''))} ({p.get('srm_grade', '')})",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# Options table
if option_positions:
    st.subheader("Options")
    opt_rows = []
    for p in option_positions:
        opt_rows.append({
            "Ticker": p["ticker"],
            "Detail": p.get("option_detail", ""),
            "Mark": _fmt(p.get("close"), ".2f"),
            "Sector": f"{_sector_label(p.get('sector_etf', ''))} ({p.get('srm_grade', '')})",
        })
    st.dataframe(pd.DataFrame(opt_rows), use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Per-position action cards
# ---------------------------------------------------------------------------

st.subheader("Trade Management")

for p in stock_positions:
    t = p["ticker"]
    sc = scores.get(t, {})
    action, colour, explanation = _advice(p, scores)

    # Header
    pnl_r = p.get("pnl_r", 0) or 0
    pnl_str = f"+{pnl_r:.2f}R" if pnl_r >= 0 else f"{pnl_r:.2f}R"
    grade_str = p.get("srm_grade", "")
    decel_tag = " DECEL" if p.get("srm_note") == "DECEL" else ""
    sector = _sector_label(p.get("sector_etf", ""))

    st.markdown(f"### {t} | {sector} ({grade_str}{decel_tag}) | {pnl_str}")

    # Action badge
    if colour == "red":
        st.error(f"**{action}** -- {explanation}")
    elif colour == "orange":
        st.warning(f"**{action}** -- {explanation}")
    elif colour == "blue":
        st.info(f"**{action}** -- {explanation}")
    else:
        st.success(f"**{action}** -- {explanation}")

    # Levels bar
    lv1, lv2, lv3, lv4, lv5, lv6 = st.columns(6)
    with lv1:
        st.metric("Entry", _fmt(p.get("entry"), ".2f"))
    with lv2:
        st.metric("Stop", _fmt(p.get("stop"), ".2f"))
    with lv3:
        st.metric("BE Trigger", _fmt(p.get("be_trigger"), ".2f"))
    with lv4:
        st.metric("+1R", _fmt(p.get("target_1r"), ".2f"))
    with lv5:
        st.metric("+2R", _fmt(p.get("target_2r"), ".2f"))
    with lv6:
        st.metric("+3R", _fmt(p.get("target_3r"), ".2f"))

    # Engine gauges
    eng_data = [
        ("Flow", sc.get("flow_100")),
        ("Energy", sc.get("energy_100")),
        ("Structure", sc.get("structure_100")),
        ("MP", sc.get("mp_100")),
        ("Elder", sc.get("elder_score")),
    ]
    eng_cols = st.columns(len(eng_data))
    for col, (name, val) in zip(eng_cols, eng_data):
        with col:
            if val is not None and not (isinstance(val, float) and val != val):
                top = 10.0 if name == "Elder" else 100.0
                ratio = float(val) / top
                ratio = min(max(ratio, 0.0), 1.0)
                st.progress(ratio, text=f"{name}  {val:.1f}")
            else:
                st.caption(f"{name}: ---")

    # Risk metrics
    r_size = p.get("r_size", 0) or 0
    shares = p.get("shares", 0) or 0
    close = p.get("close", 0) or 0
    stop = p.get("stop", 0) or 0
    risk_at_stop = (close - stop) * shares if close and stop and shares else 0
    dist_stop = (close - stop) / close * 100 if close and stop else 0

    rm1, rm2, rm3, rm4 = st.columns(4)
    with rm1:
        st.metric("Risk to stop", f"${risk_at_stop:,.0f}")
    with rm2:
        st.metric("Dist to stop", f"{dist_stop:.1f}%")
    with rm3:
        if p.get("target_3r") and close:
            upside = (p["target_3r"] - close) / close * 100
            st.metric("Upside to +3R", f"{upside:.1f}%")
        else:
            st.metric("Upside to +3R", "---")
    with rm4:
        position_val = close * shares
        st.metric("Position value", f"${position_val:,.0f}")

    st.markdown("---")

# Options management
for p in option_positions:
    action, colour, explanation = _advice(p, scores)
    st.markdown(f"### {p['ticker']} | {p.get('option_detail', '')} | {_sector_label(p.get('sector_etf', ''))}")
    st.info(f"**{action}** -- {explanation}")
    st.markdown("---")

# ---------------------------------------------------------------------------
# Portfolio risk summary
# ---------------------------------------------------------------------------

st.subheader("Portfolio Risk Summary")

total_risk_at_stop = sum(
    ((p.get("close", 0) or 0) - (p.get("stop", 0) or 0)) * (p.get("shares", 0) or 0)
    for p in stock_positions
    if p.get("close") and p.get("stop") and p.get("shares")
)
worst_case_pct = total_risk_at_stop / CAPITAL * 100 if CAPITAL else 0

pr1, pr2, pr3 = st.columns(3)
with pr1:
    st.metric("Total risk if all stop", f"${total_risk_at_stop:,.0f}")
with pr2:
    st.metric("% of capital at risk", f"{worst_case_pct:.1f}%")
with pr3:
    max_risk = RISK_PCT * len(stock_positions) * 100
    st.metric("Max planned risk", f"{max_risk:.0f}% ({len(stock_positions)} x 3%)")

if worst_case_pct > 20:
    st.error(
        f"Total open risk is {worst_case_pct:.1f}% of capital. "
        f"This exceeds 20%. Consider reducing exposure."
    )
elif worst_case_pct > 15:
    st.warning(
        f"Total open risk is {worst_case_pct:.1f}% of capital. "
        f"Approaching caution zone."
    )
else:
    st.success(
        f"Total open risk is {worst_case_pct:.1f}% of capital. "
        f"Within normal range."
    )
