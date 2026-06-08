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

# --- alert card styling -------------------------------------------------
st.markdown("""<style>
.aqe-card{border-radius:8px;padding:8px 12px;margin:6px 0;background:#f7f9fc;
  border-left:5px solid #06c;}
.aqe-card.held{border-left-color:#d00;background:#fff5f5;
  animation:aqepulse 1.5s ease-in-out infinite;}
@keyframes aqepulse{0%,100%{box-shadow:0 0 0 0 rgba(208,0,0,0);}
  50%{box-shadow:0 0 0 5px rgba(208,0,0,.20);}}
.aqe-top{display:flex;align-items:center;gap:8px;}
.aqe-badge{color:#fff;font-weight:700;font-size:11px;padding:1px 8px;border-radius:10px;}
.aqe-tkr{font-weight:700;font-size:16px;}
.aqe-time{margin-left:auto;color:#888;font-size:12px;font-variant-numeric:tabular-nums;}
.aqe-level{font-weight:600;margin-top:3px;}
.aqe-detail{color:#555;font-size:12px;}
.aqe-day{font-weight:700;font-size:14px;margin:14px 0 2px;color:#333;}
.aqe-line{padding:5px 8px;margin:4px 0;border-radius:6px;background:#f4f6fa;
  border-left:4px solid #0a66cc;font-size:13px;}
.aqe-line.held{border-left-color:#d00;background:#fff2f2;
  animation:aqepulse 1.5s ease-in-out infinite;}
.aqe-line .lbadge{color:#fff;font-weight:700;font-size:10px;padding:0 6px;
  border-radius:9px;margin-right:6px;}
.aqe-line .ltkr{font-weight:700;}
.aqe-line .lpx{color:#555;}
.aqe-line .lnote{color:#888;font-size:11px;margin-top:1px;}
</style>""", unsafe_allow_html=True)

_LEVEL_ACCENT = {
    "ENTRY_PULLBACK": "#0a8a3a", "ENTRY_BREAKOUT": "#0a66cc",
    "NEAR_STOP": "#d33", "TP1": "#0a8a0a", "TP2": "#0a8a0a", "TP3": "#0a8a0a",
    "RVOL": "#8a4fc0",
}


def _accent(level: str) -> str:
    if level.startswith("MA_") or level.startswith("FIB_"):
        return "#0a8a8a"
    return _LEVEL_ACCENT.get(level, "#0a66cc")


def _card_html(e: dict, time_str: str) -> str:
    held = bool(e.get("is_held"))
    if held:
        badge = '<span class="aqe-badge" style="background:#d00">★ HELD</span>'
    else:
        src = (e.get("source") or "").upper()
        badge = f'<span class="aqe-badge" style="background:#0a66cc">{src}</span>'
    lp = e.get("level_price")
    lp_txt = f" @ {lp}" if lp is not None else ""
    return (
        f'<div class="aqe-card {"held" if held else ""}">'
        f'<div class="aqe-top">{badge}'
        f'<span class="aqe-tkr">{e.get("ticker")}</span>'
        f'<span class="aqe-time">{time_str}</span></div>'
        f'<div class="aqe-level" style="color:{_accent(e.get("level",""))}">'
        f'{e.get("label")}{lp_txt}</div>'
        f'<div class="aqe-detail">live {e.get("live_px")} · {e.get("note") or ""}</div>'
        f'</div>'
    )


def _line_html(t: dict) -> str:
    """Compact one-liner for a 2×2 category quadrant."""
    held = bool(t.get("is_held"))
    if held:
        badge = '<span class="lbadge" style="background:#d00">★HELD</span>'
    else:
        badge = (f'<span class="lbadge" style="background:#0a66cc">'
                 f'{(t.get("source") or "").upper()}</span>')
    lp = t.get("level_price")
    lp_txt = f" @ {lp}" if lp is not None else ""
    return (
        f'<div class="aqe-line {"held" if held else ""}">'
        f'{badge}<span class="ltkr">{t.get("ticker")}</span> '
        f'<span class="lpx">{t.get("label")}{lp_txt} · live {t.get("live_px")}</span>'
        f'<div class="lnote">{t.get("note") or ""}</div></div>'
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
import os as _os  # noqa: E402
_on_hf = bool(_os.environ.get("SPACE_HOST") or _os.environ.get("SPACE_ID"))
c1, c2, c3, c4 = st.columns(4)
c1.metric("Monitored", len(mon))
c2.metric("Held", sum(1 for m in mon if m["is_held"]))
c3.metric("Market window", "OPEN" if in_market_window() else "closed")
c4.metric("Email engine", "GitHub Actions" if _on_hf
          else ("local SMTP" if emailer.is_configured() else "no SMTP secret"))
if _on_hf:
    st.caption(
        "📧 Emails are sent by the **GitHub Actions** poller (every 15 min in US "
        "market hours) — HF blocks outbound SMTP, so the app itself can't email. "
        "This page is the live cockpit + the alert history that GitHub logs to Drive."
    )

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
        reason = str(res.get("reason"))
        if "unreachable" in reason or "Errno 101" in reason or "timed out" in reason:
            st.warning(
                "HF Spaces **block outbound email (SMTP)** — emails can't be sent "
                "from this app. That's expected: the **GitHub Actions backstop** "
                "sends all alert emails (its runners allow SMTP). Test it there: "
                "**Actions → AQE live alerts → Run workflow → tick `test`**."
            )
        else:
            st.error(f"Test email failed: {reason}")

# --- persistent 36-hour alert feed (always on screen) ------------------
st.subheader("📜 Alerts — last 36 hours")
try:
    from src.alerts import state as _S
    feed = _S.recent_history(36)
except Exception as exc:  # noqa: BLE001
    feed = []
    st.caption(f"history unavailable: {exc}")

if feed:
    st.caption(f"{len(feed)} alert(s) fired in the last 36h "
               f"across {len({e.get('ticker') for e in feed})} ticker(s). "
               "Newest day first; times are SGT.")

    from datetime import datetime as _dt

    def _day_key(e):
        return (e.get("ts_sgt") or "")[:10]  # 'YYYY-MM-DD'

    def _day_label(key):
        try:
            return _dt.strptime(key, "%Y-%m-%d").strftime("%a %d %b %Y")
        except ValueError:
            return key or "—"

    def _hhmm(e):
        s = e.get("ts_sgt") or ""
        return (s[11:16] + " SGT") if len(s) >= 16 else s

    # feed is already newest-first; preserve that order while grouping by day.
    days: list[str] = []
    for e in feed:
        k = _day_key(e)
        if k not in days:
            days.append(k)

    for k in days:
        day_rows = [e for e in feed if _day_key(e) == k]
        html = [f'<div class="aqe-day">{_day_label(k)} · {len(day_rows)} alert(s)</div>']
        html += [_card_html(e, _hhmm(e)) for e in day_rows]
        st.markdown("\n".join(html), unsafe_allow_html=True)
else:
    st.caption(
        "No alerts logged yet. The history fills as the 15-min background poller "
        "(or the GitHub Actions backstop) fires level alerts during US market hours. "
        "Use the GitHub **AQE live alerts → Run workflow → force** to seed it now."
    )

st.divider()

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

# --- live cockpit: 2×2 category cards ----------------------------------
st.subheader(f"🔔 Triggering now ({len({t['ticker'] for t in hot})} tickers)")

# Bucket each live trigger into one of the four quadrants.
cat = {"entry": [], "breakout": [], "sl": [], "key": []}
for t in hot:
    lv = t.get("level", "")
    if lv == "ENTRY_PULLBACK":
        cat["entry"].append(t)
    elif lv == "ENTRY_BREAKOUT":
        cat["breakout"].append(t)
    elif lv == "NEAR_STOP":
        cat["sl"].append(t)
    else:  # MA_*, FIB_*, TP1/2/3, RVOL
        cat["key"].append(t)
for bucket in cat.values():
    bucket.sort(key=lambda t: (not t.get("is_held"), t.get("ticker")))


def _quad(col, icon, title, items):
    with col:
        with st.container(border=True):
            st.markdown(f"**{icon} {title}** · {len(items)}")
            if items:
                st.markdown("\n".join(_line_html(t) for t in items),
                            unsafe_allow_html=True)
            else:
                st.caption("— none —")


_r1 = st.columns(2)
_quad(_r1[0], "🎯", "Entry — pullback to buy zone", cat["entry"])
_quad(_r1[1], "🛑", "Approaching stop (SL)", cat["sl"])
_r2 = st.columns(2)
_quad(_r2[0], "🚀", "Breakout above trigger", cat["breakout"])
_quad(_r2[1], "📍", "Key levels hit (MA / Fib / TP / RVol)", cat["key"])

# --- full monitor table -------------------------------------------------
st.subheader("All monitored tickers")
st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(
    f"Tolerances — near-stop ≤{C.NEAR_STOP_PCT:.0f}% · breakout +{C.BREAKOUT_PCT:.0f}% · "
    f"MA ±{C.MA_TOL_PCT:.1f}% · Fib ±{C.FIB_TOL_PCT:.1f}% · RVol ≥{C.RVOL_SPIKE:.1f}×. "
    "Override via AQE_ALERT_* env vars."
)
