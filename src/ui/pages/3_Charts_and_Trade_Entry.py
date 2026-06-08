"""AQE Charts + Trade Entry — the combined cockpit (Page 3).

Left (majority): the price chart for the selected ticker — EOD candles + 20/50/100/200
MAs + the live 15-min-delayed price (forming candle + line) + the DSL buy/stop/TP
zones + the "bought @" overlay for held names + the AQE engine numbers.

Right rail: the Trade Entry Menu. A toggle flips it between **Cards** (alerts grouped
by category: Entry-pullback / Approaching-stop / Breakout / Key-levels) and **Latest**
(one chronological mixed feed). Every alert is a button — click it to load that ticker
into the chart on the left. ★ HELD names lead and flash.

Emails are sent every 15 min by the in-app poller via Resend (HTTPS); this page is the live
read + the history GitHub logs to Drive.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Charts + Trade Entry",
                   page_icon=":chart_with_upwards_trend:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, load_export  # noqa: E402

require_login()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from src.data.paths import PANEL_DAILY  # noqa: E402
from src.alerts.engine import evaluate, monitored, in_market_window  # noqa: E402

if not PANEL_DAILY.exists():
    st.info("Price panel not found. Run the daily pipeline on the **Scanner** page first.")
    st.stop()


@st.cache_data(ttl=900, show_spinner=False)
def _load_panel(_hash: str) -> pd.DataFrame:
    df = pd.read_parquet(
        PANEL_DAILY, columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


panel = _load_panel(str(PANEL_DAILY.stat().st_mtime_ns))
panel_tickers = set(panel["ticker"].unique())

export = load_export() or {}
held_positions = export.get("held_positions") or []
held_lookup = {h.get("ticker"): h for h in held_positions if h.get("ticker")}

cat_sets = {
    "Top picks": {r.get("ticker") for r in (export.get("top_picks") or [])},
    "PE": {r.get("ticker") for r in (export.get("edge_list") or [])},
    "Longlist": {r.get("ticker") for r in (export.get("longlist") or [])},
    "Watchlist": {r.get("ticker") for r in (export.get("watchlist") or [])},
    "Held": set(held_lookup.keys()),
}
rec_lookup: dict[str, dict] = {}
for _tier in ("top_picks", "edge_list", "longlist", "watchlist"):
    for _rec in (export.get(_tier) or []):
        rec_lookup.setdefault(_rec.get("ticker"), {**_rec, "_tier": _tier})
for _h in held_positions:
    rec_lookup.setdefault(_h.get("ticker"), {**_h, "_tier": "held"})

if not rec_lookup:
    st.info("No tickers in today's export yet. Run the daily pipeline on the Scanner page.")
    st.stop()

mon = monitored(export)


# ---------------------------------------------------------------------------
# Card / button styling
# ---------------------------------------------------------------------------
st.markdown("""<style>
@keyframes aqepulse{0%,100%{box-shadow:0 0 0 0 rgba(208,0,0,0);}
  50%{box-shadow:0 0 0 4px rgba(208,0,0,.20);}}
.aqe-day{display:inline-block;font-weight:700;font-size:12px;margin:10px 0 4px;
  color:#fff;background:#334;padding:2px 10px;border-radius:11px;}
.aqe-rowmeta{font-size:11px;color:#888;margin:-4px 0 6px 2px;}
/* held alert buttons flash red */
div[data-testid="stButton"] button[kind="primary"]{
  background:#d33;border-color:#d33;animation:aqepulse 1.5s ease-in-out infinite;}
</style>""", unsafe_allow_html=True)

_LEVEL_SHORT = {
    # Current engine levels (the only three that fire post-43f2761).
    "BUY_ZONE": "Hit buy price", "BREAKOUT": "Breakout", "NEAR_STOP": "Near stop",
    # Legacy names — kept so old entries in the 36h history still render nicely.
    "ENTRY_PULLBACK": "Pullback→buy", "ENTRY_BREAKOUT": "Breakout",
    "TP1": "TP1", "TP2": "TP2", "TP3": "TP3", "RVOL": "RVol",
    "MA_20": "MA20", "MA_50": "MA50", "MA_100": "MA100", "MA_200": "MA200",
    "FIB_0.382": "Fib .382", "FIB_0.5": "Fib .5", "FIB_0.618": "Fib .618",
}


def _short(level: str) -> str:
    return _LEVEL_SHORT.get(level, level)


# Selection state — the single source of truth for which ticker is charted.
_default = export["top_picks"][0].get("ticker") if export.get("top_picks") else None
if _default not in panel_tickers:
    _default = next(iter(sorted(rec_lookup)), None)
st.session_state.setdefault("sel_ticker", _default)


def _chart(tk: str):
    """Rail button callback — load a ticker into the chart."""
    st.session_state["sel_ticker"] = tk


def _rec_from_adhoc(a: dict) -> dict:
    """Shape an ad-hoc score_tickers() result like an export record so the chart
    panel + DSL zones render identically for off-list tickers. PTRS/RVol/RS/sector
    need the full pipeline, so they stay null (shown as — and noted)."""
    lv = a.get("levels") or {}
    be, stop = lv.get("be"), lv.get("stop")
    bracket = (be - stop) if (be is not None and stop is not None) else None

    def _rr(tp):
        if tp is not None and bracket and bracket > 0:
            return round((tp - be) / bracket, 2)
        return None

    return {
        "_tier": "ad-hoc (freshly scored)", "_adhoc": True, "_as_of": a.get("as_of"),
        "sc_momentum": a.get("sc_momentum"), "sc_momentum_raw": a.get("sc_momentum_raw"),
        "ptrs": None,
        "flow": a.get("flow"), "energy": a.get("energy"),
        "structure": a.get("structure"), "mp": a.get("mp"),
        "elder": a.get("elder"), "mp_state": a.get("mp_state"),
        "beta_30d": a.get("beta_30d"), "beta_60d": a.get("beta_60d"),
        "pipe_rank": a.get("pipe_rank"),
        "rvol": None, "rs_spy_20d": None, "sma_distance_pct": None,
        "gics_sector": None, "gics_sector_name": None, "gics_gate": None,
        "dsl_be": be, "dsl_stop": stop, "dsl_risk": lv.get("risk"),
        "dsl_tp_1r": lv.get("tp_1r"), "dsl_tp_2r": lv.get("tp_2r"),
        "dsl_tp_3r": lv.get("tp_3r"),
        "dsl_atr_ratio": lv.get("dsl_atr_ratio"), "atr_14d": lv.get("atr14"),
        "rr_tp1": _rr(lv.get("tp_1r")), "rr_tp2": _rr(lv.get("tp_2r")),
        "rr_tp3": _rr(lv.get("tp_3r")),
        "fib": lv.get("fib"),
    }


st.title("Charts + Trade Entry")

left, right = st.columns([3, 1.35], gap="medium")

# ===========================================================================
# RIGHT RAIL — Trade Entry Menu (rendered first so clicks resolve before chart)
# ===========================================================================
with right:
    st.markdown("#### 🔔 Trade Entry")
    mkt = "🟢 OPEN" if in_market_window() else "⚪ closed"
    st.caption(f"US market {mkt} · {len(mon)} monitored · "
               f"{sum(1 for m in mon if m['is_held'])} held · emails every 15 min (Resend)")

    # In-app email self-test — verify RESEND_API_KEY end-to-end without GitHub.
    with st.expander("📧 Email setup / test", expanded=False):
        from src.alerts import emailer as _EM  # noqa: E402
        _cfg = _EM._cfg()
        if _cfg["resend_key"]:
            st.caption(f"✅ Resend key set · sending to **{_cfg['to']}**")
        elif _cfg["smtp_pw"]:
            st.caption(f"✅ SMTP fallback set · sending to **{_cfg['to']}**")
        else:
            st.caption("⚠️ No email backend — set **RESEND_API_KEY** in HF "
                       "Settings → Variables and secrets, then restart the Space.")
        if st.button("Send test email now", use_container_width=True,
                     disabled=not _EM.is_configured()):
            with st.spinner("Sending test digest…"):
                _res = _EM.send_test()
            if _res.get("ok"):
                st.success(f"Sent via {_res.get('via')} to {_res.get('to')} — "
                           "check your inbox (and spam).")
            else:
                st.error(f"Failed: {_res.get('reason')}")

    # Quotes power BOTH views — fetch once on first load, cache, manual refresh.
    _need = "tem_quotes" not in st.session_state
    _refresh = st.button("🔄 Refresh live levels", use_container_width=True)
    if _need or _refresh:
        with st.spinner("Fetching 15-min quotes…"):
            try:
                from src.data.fmp_client import FMPClient
                st.session_state["tem_quotes"] = FMPClient().get_quotes(
                    [m["ticker"] for m in mon])
            except Exception as exc:  # noqa: BLE001
                st.session_state["tem_quotes"] = {}
                st.error(f"Quote fetch failed: {exc}")
    quotes = st.session_state.get("tem_quotes") or {}

    from datetime import datetime as _dt  # noqa: E402
    from zoneinfo import ZoneInfo as _ZI  # noqa: E402

    def _qt(q):
        ts = q.get("ts")
        try:
            return (_dt.fromtimestamp(int(ts), _ZI("Asia/Singapore")).strftime("%H:%M")
                    if ts else None)
        except Exception:  # noqa: BLE001
            return None

    # Evaluate every monitored ticker once → live triggers (with quote time).
    live_trigs = []
    for m in mon:
        q = quotes.get(m["ticker"])
        if not q or q.get("price") is None:
            continue
        _t = _qt(q)
        for t in evaluate(m["ticker"], m["source"], m["is_held"], m["record"], q):
            t["pull"] = _t
            try:
                t["_when"] = int(q.get("ts") or 0)
            except (TypeError, ValueError):
                t["_when"] = 0
            live_trigs.append(t)

    view = st.radio("View", ["Latest", "Cards"], horizontal=True,
                    label_visibility="collapsed")

    # ---- Latest: live triggers + logged history, chronological (newest first) ----
    if view == "Latest":
        items = []
        for t in live_trigs:
            lp = f" @{t['level_price']}" if t.get("level_price") is not None else ""
            items.append({"tk": t["ticker"], "held": bool(t["is_held"]),
                          "lbl": f"{_short(t['level'])}{lp}",
                          "time": (t.get("pull") or "live"), "when": t.get("_when") or 0})
        try:
            from src.alerts import state as _S
            for e in _S.recent_history(36):
                try:
                    w = int(_dt.fromisoformat(e.get("ts_utc")).timestamp())
                except Exception:  # noqa: BLE001
                    w = 0
                items.append({"tk": e.get("ticker"), "held": bool(e.get("is_held")),
                              "lbl": _short(e.get("level", "")),
                              "time": (e.get("ts_sgt") or "")[11:16], "when": w})
        except Exception:  # noqa: BLE001
            pass
        items.sort(key=lambda x: x["when"], reverse=True)

        if not items:
            if not quotes:
                st.caption("Hit **Refresh live levels** to pull quotes.")
            else:
                st.caption("Nothing triggering now, and nothing logged in 36h.")
        else:
            st.caption(f"{len(items)} highlights · newest first")
            for i, it in enumerate(items):
                star = "★ " if it["held"] else ""
                st.button(f"{star}{it['tk']} · {it['lbl']} · {it['time']}",
                          key=f"l_{i}", use_container_width=True,
                          type="primary" if it["held"] else "secondary",
                          on_click=_chart, args=(it["tk"],))

    # ---- Cards: pick a category, see just those triggers (no scrolling) ----
    # Buckets mirror the THREE actionable levels the engine now emits
    # (BUY_ZONE / BREAKOUT / NEAR_STOP) — same grouping as the email digest.
    else:
        cat = {"buy": [], "breakout": [], "sl": []}
        for t in live_trigs:
            lv = t.get("level", "")
            bucket = ("buy" if lv == "BUY_ZONE"
                      else "breakout" if lv == "BREAKOUT"
                      else "sl" if lv == "NEAR_STOP" else None)
            if bucket:
                cat[bucket].append(t)
        for b in cat.values():
            b.sort(key=lambda t: (not t.get("is_held"), t.get("ticker")))

        _LABELS = [("🟢 Hit buy price", "buy"), ("🚀 Breakout", "breakout"),
                   ("🛑 Approaching stop", "sl")]
        opts = [f"{title} ({len(cat[b])})" for title, b in _LABELS]
        pick = st.selectbox("Category", opts, label_visibility="collapsed")
        b = _LABELS[opts.index(pick)][1]
        items = cat[b]

        if not quotes:
            st.caption("Hit **Refresh live levels** to pull quotes.")
        elif not items:
            st.caption("Nothing triggering in this category.")
        for i, t in enumerate(items):
            star = "★ " if t["is_held"] else ""
            lp = f" @{t['level_price']}" if t.get("level_price") is not None else ""
            st.button(f"{star}{t['ticker']} · {_short(t['level'])}{lp} · {t['live_px']}",
                      key=f"c_{b}_{i}", use_container_width=True,
                      type="primary" if t["is_held"] else "secondary",
                      on_click=_chart, args=(t["ticker"],))

# ===========================================================================
# LEFT — the chart
# ===========================================================================
with left:
    # Filters that scope the dropdown to manageable subsets (mobile list mgmt).
    with st.expander("Filters", expanded=False):
        fa, fb = st.columns([1, 2])
        category = fa.selectbox("List", ["All", "Top picks", "PE", "Longlist",
                                         "Watchlist", "Held"])
        mp_filter = fb.multiselect("MP state", ["STRONG", "BUILDING", "FADING"], default=[])
        g1, g2, g3 = st.columns(3)
        sc_min = g1.slider("Raw SC ≥", 0, 100, 0, step=5)
        ptrs_min = g2.slider("PTRS ≥", 0, 100, 0, step=5)
        pr_min = g3.slider("PipeRank ≥", 0, 100, 0, step=5)

    def _keep(tk: str) -> bool:
        if category != "All" and tk not in cat_sets.get(category, set()):
            return False
        r = rec_lookup.get(tk, {})
        if sc_min and (r.get("sc_momentum_raw") or r.get("sc_momentum") or 0) < sc_min:
            return False
        if ptrs_min and (r.get("ptrs") or 0) < ptrs_min:
            return False
        if pr_min and (r.get("pipe_rank") or 0) < pr_min:
            return False
        if mp_filter and str(r.get("mp_state") or "") not in mp_filter:
            return False
        return True

    listed = sorted(tk for tk in rec_lookup if _keep(tk))

    def _label(tk: str) -> str:
        return f"⭐ {tk} (held)" if tk in held_lookup else tk

    s1, s2, s3, s4 = st.columns([1.3, 1.6, 1, 1])
    search = s1.text_input("🔎 Ticker", value="", placeholder="any symbol",
                           label_visibility="collapsed").strip().upper()
    # Dropdown defaults to the current selection; include it even if filtered out.
    cur = st.session_state["sel_ticker"]
    dd_opts = listed if cur in listed else ([cur] + listed if cur in panel_tickers else listed)
    if not dd_opts:
        dd_opts = sorted(rec_lookup)
    dd_idx = dd_opts.index(cur) if cur in dd_opts else 0
    sel_dd = s2.selectbox("Pick", dd_opts, index=dd_idx, format_func=_label,
                          label_visibility="collapsed")
    if search and search != cur:
        if search in panel_tickers:
            st.session_state["sel_ticker"] = search
        else:
            st.warning(f"No price history for **{search}** (not in the panel).")
    elif sel_dd != cur:
        st.session_state["sel_ticker"] = sel_dd

    lookback = s3.slider("Bars", 60, 500, 250, step=10, label_visibility="collapsed")
    show_live = s4.toggle("Live", value=True, help="Stamp the 15-min price on the chart")

    sel = st.session_state["sel_ticker"]
    rec = rec_lookup.get(sel)
    held = held_lookup.get(sel)

    # Ad-hoc scoring — any ticker not in today's export can be scored on demand
    # (same engine path as the Scanner's Ad-hoc Scorer). Cached per session.
    adhoc_cache = st.session_state.setdefault("chart_adhoc", {})
    if rec is None:
        if sel in adhoc_cache:
            rec = _rec_from_adhoc(adhoc_cache[sel])
        else:
            ac1, ac2 = st.columns([3, 1])
            ac1.caption(f"**{sel}** isn't in today's lists — not scored in the export.")
            if ac2.button("🧮 Calculate", use_container_width=True, key="adhoc_calc"):
                with st.spinner(f"Scoring {sel} from FMP…"):
                    try:
                        from src.scanner.adhoc import score_tickers
                        _res = score_tickers([sel])
                    except Exception as exc:  # noqa: BLE001
                        _res = [{"ticker": sel, "error": str(exc)}]
                if _res and not _res[0].get("error"):
                    adhoc_cache[sel] = _res[0]
                    st.rerun()
                else:
                    st.error(f"Could not score {sel}: "
                             f"{_res[0].get('error') if _res else 'unknown error'}")

    g = panel[panel["ticker"] == sel].sort_values("date").reset_index(drop=True)
    if g.empty or len(g) < 2:
        st.warning(f"No price history for {sel}.")
        st.stop()

    for w in (20, 50, 100, 200):
        g[f"ma{w}"] = g["close"].rolling(w).mean()
    disp = g.tail(lookback).copy()
    disp["_forming"] = False
    _avg_vol = float(np.nanmean(g["volume"].tail(20))) if len(g) >= 5 else None
    if not _avg_vol or _avg_vol <= 0:
        _avg_vol = None
    _sofar_vol = _proj_vol = _sess_frac = None

    # --- live 15-min price: forming candle + marker ---
    live_px = None
    live_time = None
    if show_live:
        try:
            from datetime import datetime as _dt
            from zoneinfo import ZoneInfo as _ZI
            _q = (st.session_state.get("tem_quotes") or {}).get(sel)
            if not _q:
                from src.data.fmp_client import FMPClient
                _q = (FMPClient().get_quotes([sel]) or {}).get(sel)
            if _q and _q.get("price"):
                live_px = float(_q["price"])
                _ts = _q.get("ts")
                if _ts:
                    _et = _dt.fromtimestamp(int(_ts), _ZI("America/New_York"))
                    live_time = _dt.fromtimestamp(int(_ts), _ZI("Asia/Singapore")).strftime("%Y-%m-%d %H:%M SGT")
                    et_date = pd.Timestamp(_et.date())
                    last_bar = pd.Timestamp(disp["date"].iloc[-1]).normalize()
                    if et_date > last_bar and _q.get("day_high") and _q.get("day_low"):
                        # FMP's forming-candle volume is CUMULATIVE-so-far, so mid-session
                        # it reads far below the completed full-day history bars (always
                        # "looks low"). Pace-project to a full-day estimate via the fraction
                        # of the 9:30–16:00 ET regular session elapsed (volume + ts are both
                        # 15-min delayed, so the ratio is self-consistent). <10% elapsed →
                        # don't extrapolate. Drives the RVOL readout under the chart.
                        _sofar_vol = float(_q.get("volume") or 0)
                        _smin = _et.hour * 60 + _et.minute - (9 * 60 + 30)
                        _sess_frac = max(0.0, min(1.0, _smin / 390.0))
                        _proj_vol = (_sofar_vol / _sess_frac
                                     if _sess_frac >= 0.10 else None)
                        _cl = g["close"].tolist() + [live_px]
                        _row = {"date": et_date, "open": _q.get("open") or live_px,
                                "high": max(float(_q["day_high"]), live_px),
                                "low": min(float(_q["day_low"]), live_px),
                                "close": live_px, "volume": _sofar_vol, "_forming": True}
                        for _w in (20, 50, 100, 200):
                            _row[f"ma{_w}"] = (float(np.mean(_cl[-_w:]))
                                               if len(_cl) >= _w else np.nan)
                        disp = pd.concat([disp, pd.DataFrame([_row])], ignore_index=True)
        except Exception:  # noqa: BLE001
            pass

    _MA_COLORS = {20: "#F0A500", 50: "#3BA3FF", 100: "#B36BFF", 200: "#FF5C8A"}
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.78, 0.22])
    fig.add_trace(go.Candlestick(
        x=disp["date"], open=disp["open"], high=disp["high"], low=disp["low"],
        close=disp["close"], name=sel, increasing_line_color="#26A69A",
        decreasing_line_color="#EF5350"), row=1, col=1)
    for w, color in _MA_COLORS.items():
        fig.add_trace(go.Scatter(x=disp["date"], y=disp[f"ma{w}"], name=f"MA{w}",
                                 line=dict(width=1.3, color=color), connectgaps=True),
                      row=1, col=1)
    # Volume: completed full-day bars + a 20d-avg reference line. The forming
    # candle is drawn as its own bar so the realized-so-far volume (solid) and the
    # pace-projected full-day cap (faded outline) are distinct and comparable to
    # the completed bars — see the RVOL caption under the chart.
    _hist = disp[~disp["_forming"].astype(bool)]
    vol_colors = np.where(_hist["close"] >= _hist["open"], "#26A69A", "#EF5350")
    fig.add_trace(go.Bar(x=_hist["date"], y=_hist["volume"], name="Volume",
                         marker_color=vol_colors, opacity=0.6), row=2, col=1)
    if _avg_vol:
        fig.add_hline(y=_avg_vol, line=dict(color="#AAAAAA", width=1, dash="dot"),
                      annotation_text=f"20d avg {_avg_vol/1e6:.1f}M",
                      annotation_position="top left", row=2, col=1)
    if _sofar_vol is not None:
        _fdate = disp["date"].iloc[-1]
        _fup = bool(live_px is not None
                    and live_px >= float(disp["open"].iloc[-1] or live_px))
        _fcol = "#26A69A" if _fup else "#EF5350"
        fig.add_trace(go.Bar(x=[_fdate], y=[_sofar_vol], name="Vol so far",
                             marker_color=_fcol, opacity=0.95), row=2, col=1)
        if _proj_vol and _proj_vol > _sofar_vol:
            fig.add_trace(go.Bar(x=[_fdate], y=[_proj_vol - _sofar_vol],
                                 base=[_sofar_vol], name="Vol (proj. full-day)",
                                 marker_color=_fcol, opacity=0.18,
                                 marker_line=dict(color=_fcol, width=1)),
                          row=2, col=1)

    # --- DSL buy/stop/TP zones ---
    _be = rec.get("dsl_be") if rec else None
    _stop = rec.get("dsl_stop") if rec else None
    _tps = ([(rec.get("dsl_tp_1r"), "TP1"), (rec.get("dsl_tp_2r"), "TP2"),
             (rec.get("dsl_tp_3r"), "TP3")] if rec else [])
    if _be and _stop:
        fig.add_hrect(y0=_stop, y1=_be, line_width=0, fillcolor="#EF5350",
                      opacity=0.12, row=1, col=1)
        fig.add_hline(y=_stop, line=dict(color="#EF5350", width=1.2, dash="dash"),
                      annotation_text=f"Stop {_stop:.2f}",
                      annotation_position="top left", row=1, col=1)
        fig.add_hline(y=_be, line=dict(color="#FFD24A", width=1.6),
                      annotation_text=f"Buy {_be:.2f}",
                      annotation_position="top left", row=1, col=1)
        _prev = _be
        for _tp, _lab in _tps:
            if _tp and _prev:
                fig.add_hrect(y0=_prev, y1=_tp, line_width=0, fillcolor="#26A69A",
                              opacity=0.09, row=1, col=1)
                fig.add_hline(y=_tp, line=dict(color="#26A69A", width=1, dash="dot"),
                              annotation_text=f"{_lab} {_tp:.2f}",
                              annotation_position="top left", row=1, col=1)
                _prev = _tp

    # --- held "bought @" overlay ---
    _ent = held.get("entry") if held else None
    _hsl = held.get("held_sl") if held else None
    if _ent:
        fig.add_hline(y=_ent, line=dict(color="#FFFFFF", width=1.8, dash="dot"),
                      annotation_text=f"Bought {_ent:.2f}",
                      annotation_position="bottom left", row=1, col=1)
    if _hsl:
        fig.add_hline(y=_hsl, line=dict(color="#FF8C00", width=1.2, dash="dashdot"),
                      annotation_text=f"Held SL {_hsl:.2f}",
                      annotation_position="bottom left", row=1, col=1)
    if live_px:
        fig.add_hline(y=live_px, line=dict(color="#00E5FF", width=1.5, dash="dot"),
                      annotation_text=f"Live {live_px:.2f}",
                      annotation_position="right", row=1, col=1)

    # Single y-range covering candles + every drawn level (linear scale).
    _allv = [v for v in ([_stop, _be, _ent, _hsl, live_px] + [t for t, _ in _tps]) if v]
    if _allv:
        _ylo = min([float(disp["low"].min())] + _allv)
        _yhi = max([float(disp["high"].max())] + _allv)
        _pad = (_yhi - _ylo) * 0.04 or 1.0
        fig.update_yaxes(range=[_ylo - _pad, _yhi + _pad], row=1, col=1)

    fig.update_layout(template="plotly_dark", height=640, barmode="overlay",
                      margin=dict(l=10, r=10, t=24, b=10),
                      xaxis_rangeslider_visible=False, showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                  xanchor="left", x=0),
                      hovermode="x unified")
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    if live_px:
        _eod = pd.Timestamp(g["date"].iloc[-1]).date()
        _mv = (f" ({((live_px / float(g['close'].iloc[-1]) - 1) * 100):+.1f}% vs close)"
               if float(g["close"].iloc[-1]) else "")
        st.caption(f"🔵 Live **{live_px:.2f}**{_mv} as of {live_time or '—'} "
                   f"(15-min delayed) · last EOD bar {_eod}")

    # Volume confirmation — projected full-day RVOL so a breakout on below-average
    # pace is flagged BEFORE buying (the raw forming bar is only cumulative-so-far).
    if _sofar_vol is not None and _avg_vol:
        _now_x = _sofar_vol / _avg_vol
        if _proj_vol:
            _rvol = _proj_vol / _avg_vol
            _flag = ("🟢 above-avg pace" if _rvol >= 1.0
                     else "🔴 BELOW-avg pace — weak breakout confirmation")
            st.caption(
                f"📊 Vol so far **{_sofar_vol/1e6:.2f}M** "
                f"({_sess_frac*100:.0f}% of session, {_now_x:.2f}× avg so far) · "
                f"on pace for **~{_proj_vol/1e6:.2f}M** · projected RVOL "
                f"**{_rvol:.2f}× 20d-avg** ({_avg_vol/1e6:.2f}M) — {_flag}")
        else:
            st.caption(f"📊 Vol so far **{_sofar_vol/1e6:.2f}M** — too early in the "
                       "session to project full-day volume reliably.")

    if held:
        _e, _lp, _u, _q2 = (held.get("entry"), held.get("live_px"),
                            held.get("unreal_usd"), held.get("qty"))
        _mv = f"{((_lp / _e - 1) * 100):+.1f}%" if (_e and _lp) else "—"
        _u_s = f"${_u:,.0f}" if _u is not None else "—"
        st.info(f"📌 **HELD** — bought **{_e}** × {_q2} on {held.get('trade_date','?')} · "
                f"live {_lp} ({_mv}) · unrealised {_u_s} · held SL {held.get('held_sl')}")

    if rec and _be and _stop:
        _risk_pct = (_be - _stop) / _be * 100
        # TP prices are dynamic (scale with the β-adjusted 1R). The TP ladder is
        # fixed R-multiples, so R:R-to-each-TP is a constant by construction —
        # we show % move (which IS per-ticker) and the dynamic rr_est (reward to
        # the Fib-1.618 extension ÷ risk) as the real per-name R:R.
        _segs = [f"🟥 Stop **{_stop:.2f}** (−{_risk_pct:.1f}%)", f"🟨 Buy **{_be:.2f}**"]
        for _tp, _lab in _tps:
            if _tp:
                _p = (_tp - _be) / _be * 100
                _segs.append(f"🟩 {_lab} **{_tp:.2f}** (+{_p:.1f}%)")
        _est = rec.get("rr_est")
        if _est is not None:
            _segs.append(f"🎯 R:R **{_est}** (to Fib 1.618)")
        st.caption("  ·  ".join(_segs))

    # --- AQE numbers ---
    last = g.iloc[-1]
    st.subheader(f"{sel} — AQE numbers")
    if rec and rec.get("_adhoc"):
        st.caption(f"🧮 **Freshly scored** on the latest FMP bar ({rec.get('_as_of')}) "
                   "— full engine suite, but PTRS / RVol / RS / sector need the daily "
                   "pipeline so they show as —.")
    else:
        _asof = export.get("exported_at") or export.get("date") or "last run"
        st.caption(f"📅 Engine read **as of {_asof}** (end-of-day, last pipeline run) — "
                   "these are NOT intraday; only the price / Live line moves during the day.")
    if rec is None:
        st.caption("Not in today's lists (top_picks / edge / longlist / watchlist).")
    else:
        st.caption(f"Source tier: **{rec.get('_tier')}** · sector "
                   f"{rec.get('gics_sector') or '—'} "
                   f"({rec.get('gics_sector_name') or '—'}) · "
                   f"gate {rec.get('gics_gate') or '—'}")

    def _f(v, spec=".2f"):
        return "—" if v is None or (isinstance(v, float) and v != v) else format(v, spec)

    r = rec or {}
    _scc = r.get("sc_momentum")
    _scr = r.get("sc_momentum_raw")
    _gated = (_scc is not None and _scr is not None and float(_scr) > float(_scc))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Last close", _f(float(last["close"])))
    m1.metric("SC_MOM", _f(_scc, ".1f"),
              delta=(f"raw {float(_scr):.1f}" if _gated else None), delta_color="off",
              help="Gate-capped composite. **49 = a gate failed** (Elder/Flow/Energy/"
                   "Structure/MP under threshold) so the composite is hard-capped at "
                   "49.0; the true uncapped score shows as 'raw'. End-of-day, from the "
                   "last pipeline run.")
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
        d4.metric("R:R (Fib 1.618)", _f(r.get("rr_est"), ".2f"),
                  help="The per-ticker R:R = reward to the Fib-1.618 extension ÷ 1R "
                       "risk. This is the DYNAMIC one. The TP1/2/3 ladder is fixed "
                       "R-multiples (+1R/+2R/+3R), so its R:R is a constant 1/2/3 for "
                       "every name by design — the TP *prices* vary because 1R is "
                       "β-adjusted, but the ratio doesn't.")
        d4.metric("ATR(14d)", _f(r.get("atr_14d")))
