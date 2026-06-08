"""AQE Trade Entry Menu — Page 4 of the multi-page app.

The live cockpit for the alert engine. Every monitored ticker (longlist /
watchlist / Precision Edge / held) is shown with its 15-min-delayed price and its
distance to every key level (entry, near-stop, TP1/2/3, RVol, MA, Fib). The
background poller emails a digest when a level is hit; this page lets you see the
live picture on demand, fire a manual cycle, and send a test email.

Prices here are pulled live from FMP (15-min delayed on the Starter plan) only
when you open/refresh the page — the recurring email poll runs in the background.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Trade Entry Menu", page_icon=":bell:",
                   layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, load_export  # noqa: E402

require_login()

from src.alerts import config as C  # noqa: E402
from src.alerts import emailer  # noqa: E402
from src.alerts.engine import evaluate, monitored, in_market_window  # noqa: E402

st.title("Trade Entry Menu")
st.caption(
    "Live 15-min-delayed levels for longlist / watchlist / PE / held names. "
    "The background poller emails you a digest (with an AIC engagement prompt) "
    f"every {C.ALERT_MINUTES} min during US market hours when a level is hit."
)

export = load_export() or {}
if not export:
    st.info("No export found yet. Run the daily pipeline on the **Scanner** page first.")
    st.stop()

mon = monitored(export)
if not mon:
    st.warning("No monitored tickers in the current export.")
    st.stop()

# --- status row ---------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Monitored", len(mon))
c2.metric("Held", sum(1 for m in mon if m["is_held"]))
c3.metric("Market window", "OPEN" if in_market_window() else "closed")
c4.metric("Email", "ready" if emailer.is_configured() else "no SMTP secret")

try:
    from src.ui.alert_job import last_cycle
    lc = last_cycle()
    if lc:
        st.caption(
            f"Last background cycle: {lc.get('ran_at','?')} — "
            f"checked {lc.get('checked','?')}, new {lc.get('new_triggers','?')}, "
            f"emailed {lc.get('emailed')}"
            + (f" · {lc.get('reason')}" if lc.get('reason') else "")
        )
except Exception:  # noqa: BLE001
    pass

# --- controls -----------------------------------------------------------
b1, b2, _ = st.columns([1, 1, 4])
do_refresh = b1.button("🔄 Refresh live levels", type="primary")
do_test = b2.button("✉️ Send test email")

if do_test:
    res = emailer.send_test()
    if res.get("ok"):
        st.success(f"Test email sent to {res.get('to')}.")
    else:
        st.error(f"Test email failed: {res.get('reason')}")

# --- live evaluation (on demand) ---------------------------------------
if "tem_quotes" not in st.session_state or do_refresh:
    with st.spinner("Fetching 15-min quotes from FMP…"):
        try:
            from src.data.fmp_client import FMPClient
            st.session_state["tem_quotes"] = FMPClient().get_quotes(
                [m["ticker"] for m in mon])
        except Exception as exc:  # noqa: BLE001
            st.session_state["tem_quotes"] = {}
            st.error(f"Quote fetch failed: {exc}")

quotes = st.session_state.get("tem_quotes") or {}
if not quotes:
    st.info("No live quotes loaded yet. Click **Refresh live levels** "
            "(needs FMP_API_KEY set on the Space).")
    st.stop()


def _pct(a, b):
    try:
        return (float(a) / float(b) - 1) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


rows = []
hot = []
for m in mon:
    tk, rec, is_held = m["ticker"], m["record"], m["is_held"]
    q = quotes.get(tk)
    if not q or q.get("price") is None:
        continue
    live = float(q["price"])
    stop = rec.get("held_sl") if is_held else rec.get("dsl_stop")
    tp1 = rec.get("held_tp1") if is_held else rec.get("dsl_tp_1r")
    trigs = evaluate(tk, m["source"], is_held, rec, q)
    rvol = None
    if q.get("volume") and q.get("avg_volume"):
        try:
            rvol = round(float(q["volume"]) / float(q["avg_volume"]), 2)
        except (TypeError, ValueError, ZeroDivisionError):
            rvol = None
    rows.append({
        "ticker": tk,
        "src": "HELD" if is_held else m["source"],
        "live": round(live, 2),
        "entry": rec.get("entry"),
        "stop": stop,
        "to_stop_%": round(_pct(live, stop), 1) if stop else None,
        "TP1": tp1,
        "RVol": rvol,
        "MP": rec.get("mp_state"),
        "SC": rec.get("sc_momentum"),
        "PTRS": rec.get("ptrs"),
        "alerts": ", ".join(t["label"] for t in trigs) or "—",
    })
    for t in trigs:
        hot.append(t)

# --- hot list (anything triggering right now) --------------------------
st.subheader(f"🔔 Triggering now ({len({t['ticker'] for t in hot})} tickers)")
if hot:
    for t in hot:
        tag = "🔴 HELD" if t["is_held"] else f"🔵 {t['source']}"
        lp = f" @ {t['level_price']}" if t.get("level_price") is not None else ""
        st.markdown(f"- **{t['ticker']}** {tag} — **{t['label']}**{lp} "
                    f"· live {t['live_px']} · {t['note']}")
else:
    st.caption("No levels triggering at the current 15-min prices.")

# --- full monitor table -------------------------------------------------
st.subheader("All monitored tickers")
st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(
    f"Tolerances — near-stop ≤{C.NEAR_STOP_PCT:.0f}% · breakout +{C.BREAKOUT_PCT:.0f}% · "
    f"MA ±{C.MA_TOL_PCT:.1f}% · Fib ±{C.FIB_TOL_PCT:.1f}% · RVol ≥{C.RVOL_SPIKE:.1f}×. "
    "Override via AQE_ALERT_* env vars."
)
