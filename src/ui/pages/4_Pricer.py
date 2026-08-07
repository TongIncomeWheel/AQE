"""AQE Pricer — a bracket CALCULATOR for any ticker, in or out of the universe.

REINSTATED AS ITS OWN PAGE (PM ruling 2026-08-06). The Pricer was folded into
Charts & Trade Entry during the bracket consolidation, which buried it: that
page is built around a name you PICK FROM THE DAILY LIST, so the one thing the
Pricer is for — pricing a name AQE never scored — was reachable only by first
finding it on a list it is not on.

WHAT IT IS NOT. Not a screen, not a recommendation, not a sizing tool. It
computes levels and shows its working; the AIC decides and sizes. `plan.py`
gates to ENTER / STAND_DOWN — this deliberately does not, so it never blanks on
a name just because the name is unremarkable.

Every number comes from src/intraday/pricer.price_ticker — the SAME engine the
intraday plan uses. This page is a keyboard and a table; it owns no maths.
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

from src.ui.shared import require_login, table_with_copy, load_export  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

st.title("📐 AQE Pricer")
st.caption(
    "Entry / stop / targets for **any** ticker — including names outside the AQE "
    "universe. Recommend-only: AQE computes the levels, the AIC sizes and decides."
)


@st.cache_data(ttl=600, show_spinner=False)
def _daily_bars(ticker: str, years: int = 2) -> pd.DataFrame | None:
    """Daily bars: the local panel first, then FMP.

    Panel first because it is free and already current for universe names; FMP
    only for the names the panel does not carry, which is exactly the case this
    page exists to serve.
    """
    try:
        from src.data.paths import PANEL_DAILY
        if PANEL_DAILY.exists():
            pan = pd.read_parquet(
                PANEL_DAILY,
                columns=["date", "ticker", "open", "high", "low", "close", "volume"])
            g = pan[pan["ticker"] == ticker].sort_values("date")
            if len(g) >= 60:
                return g.reset_index(drop=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data.fmp_client import FMPClient
        today = date.today()
        bars = FMPClient().get_daily_bars(
            ticker, from_date=today - timedelta(days=365 * years), to_date=today)
        return bars if bars is not None and len(bars) else None
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not fetch bars for **{ticker}** ({type(exc).__name__}: {exc}).")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _export_record(ticker: str) -> dict | None:
    """The AQE record for a name that IS on the daily list, else None.

    Its absence is not an error — pricing an unscored name is the point — but
    when it exists the Pricer uses AQE's own precomputed levels rather than
    re-deriving them, so the two can never disagree.
    """
    ex = load_export(allow_drive=True) or {}
    for r in (ex.get("daily_list") or []):
        if r.get("ticker") == ticker:
            return r
    return None


c1, c2 = st.columns([2, 1])
tk = c1.text_input("Ticker", value="", placeholder="e.g. AAPL, SNDK, anything")\
       .strip().upper()
risk = c2.number_input("Risk budget $", 0, 100_000, 2100, step=100,
                       help="3% of a $70K base — the house rule. Used only to "
                            "show share count; AQE never sizes for you.")

if not tk:
    st.info("Enter a ticker. Names on the AQE daily list use their precomputed "
            "levels; anything else is computed live from daily bars.")
    st.stop()

bars = _daily_bars(tk)
if bars is None or len(bars) < 30:
    st.error(f"**No usable daily bars for {tk}.** Need at least 30; the panel "
             "does not carry it and FMP returned nothing. Nothing is guessed — "
             "check the symbol.")
    st.stop()

rec = _export_record(tk)
try:
    from src.intraday.pricer import price_ticker
    out = price_ticker(tk, rec, bars5=None, bars1h=None, daily_df=bars,
                       regime=None, risk_budget=float(risk))
except Exception as exc:  # noqa: BLE001
    st.error(f"Pricer failed for {tk}: {type(exc).__name__}: {exc}")
    st.stop()

if out.get("error"):
    st.error(f"{tk}: {out['error']}")
    st.stop()

st.success(f"**{tk}** — {'on the AQE daily list' if out.get('in_universe') else 'NOT in the AQE universe (levels computed live from bars)'}")

# ── The bracket, as one line you can read across ────────────────────────────
_stop = (out.get("operative_stop") or {}).get("price")
_tp = out.get("tp") or {}
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Entry", f"{out['entry']:.2f}")
m2.metric("Stop", f"{_stop:.2f}" if _stop else "—")
m3.metric("Risk / share", f"{out.get('risk'):.2f}" if out.get("risk") else "—")
m4.metric("TP1 / TP2", f"{_tp.get('tp1', 0):.2f} / {_tp.get('tp2', 0):.2f}")
m5.metric("ATR14", f"{out['atr_14d']:.2f}")

if out.get("risk"):
    _sh = int(float(risk) // float(out["risk"])) if float(out["risk"]) > 0 else 0
    st.caption(f"At a ${float(risk):,.0f} risk budget that is **{_sh:,} shares** "
               f"(= budget ÷ risk-per-share). AQE shows the arithmetic; it does "
               "not decide the size.")

# NOTES ARE NOT DECORATION — they are the reasons the bracket is what it is
# (stop beyond the regime ceiling, R:R short of 2.0, levels computed live).
for _n in out.get("notes") or []:
    st.warning(_n)

# ── Candidate stops, so the chosen one can be argued with ───────────────────
if out.get("candidates"):
    st.subheader("Candidate stops")
    st.caption("Every level considered, best first. The operative stop is the "
               "tightest VALID one — seeing the runners-up is what makes it a "
               "calculator rather than an oracle.")
    table_with_copy(pd.DataFrame(out["candidates"]), key="pricer_candidates")

if out.get("structural_tps"):
    st.subheader("Structural targets")
    table_with_copy(pd.DataFrame(out["structural_tps"]), key="pricer_tps")

# ── VOLATILITY PROFILE — the per-ticker exit layer ──────────────────────────
# Runs on demand, not on the daily pipeline: it is a per-candidate deep dive on
# a name already surfaced, which is exactly how the PM said he would use it
# ("i will only use it during bracketing anyway"). ~2,500 windows, well under a
# second vectorised.
st.subheader("Volatility profile — this stock's own 3-month history")
st.caption(
    "Simulates the trade thousands of times using only **this stock's** past: "
    "buy at the next open, hold ~1 quarter, repeat from every day. It answers a "
    "DIFFERENT question from QS — not *is this a good pick* (QS's calibrated "
    "probability) but *does this name's own record support a move of this size, "
    "and what stop would have survived*. "
    "**Percentiles are historical FREQUENCY, not probability** — “70th "
    "percentile” means *exceeded 30% of the time in the past*, not a 30% chance "
    "next quarter. Additive context; it does not replace the bracket above."
)

@st.cache_data(ttl=43200, show_spinner=False)      # 12h — history barely moves
def _profile_bars(ticker: str, years: int = 10) -> "pd.DataFrame | None":
    """TEN YEARS of daily bars, for the profile only.

    The panel holds ~2 years — plenty for a bracket, THIN for percentiles: it
    yields a few hundred overlapping windows against the ~2,500 the method
    assumes, and a corridor drawn from a short sample is a corridor drawn from
    one market regime. So the profile gets its own deeper pull (one FMP call,
    cached 12h) rather than quietly reusing a shorter history and reporting the
    percentiles as if nothing were different.
    """
    try:
        from src.data.fmp_client import FMPClient
        today = date.today()
        b = FMPClient().get_daily_bars(
            ticker, from_date=today - timedelta(days=365 * years + 30),
            to_date=today)
        return b if b is not None and len(b) else None
    except Exception:  # noqa: BLE001
        return None


_vp_on = st.checkbox("Compute volatility profile", value=True, key="pricer_vp",
                     help="Pulls 10 years of daily bars (one FMP call, cached "
                          "12h). The panel's ~2 years is too short for a "
                          "percentile corridor worth quoting.")
if _vp_on:
    from src.engines import vol_profile as VP
    _vp_bars = _profile_bars(tk)
    if _vp_bars is None or len(_vp_bars) < len(bars):
        # Deeper history unavailable — say so and fall back, rather than
        # silently profiling on 2 years and calling it a 10-year corridor.
        if _vp_bars is None:
            st.caption("10-year pull unavailable — profiling on the bars loaded "
                       "above. Percentiles from a shorter history describe fewer "
                       "market regimes; read them accordingly.")
        _vp_bars = bars
    else:
        st.caption(f"Profiling **{len(_vp_bars):,} daily bars** "
                   f"(~{len(_vp_bars)/252:.0f} years).")
    _prof = VP.profile(_vp_bars)
    if not _prof:
        st.warning(
            f"**Not enough history for a profile of {tk}.** It needs "
            f"{VP.HOLD_SESSIONS + VP.MIN_WINDOWS}+ daily bars to place a "
            "percentile worth quoting; this name has "
            f"{len(_vp_bars)}. Nothing is extrapolated from a short sample.")
    else:
        _cz = _prof["c2c"]["corridor_full"]["usable_zone"]
        _tp2_pct = ((_tp.get("tp2") or 0) / out["entry"] - 1) if out.get("entry") else None
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Usable target zone",
                  f"{_cz[0]*100:.1f}% – {_cz[1]*100:.1f}%")
        v2.metric("Suggested PT1 / PT2",
                  f"{_prof['pt1_pct']*100:.1f}% / {_prof['pt2_pct']*100:.1f}%")
        v3.metric("PT1 reached (past)", f"{_prof['pt1_frequency_full']*100:.0f}%",
                  help="Historical frequency across all windows — NOT a forward "
                       "probability.")
        v4.metric("Own-history stop",
                  (f"{_prof['recommended_stop_pct']*100:.0f}% → "
                   f"{_prof['recommended_stop_price']:.2f}")
                  if _prof.get("recommended_stop_pct") else "NONE")

        if not _prof.get("recommended_stop_pct"):
            st.warning(f"**No survivable stop found.** {_prof.get('recommended_stop_reason')} "
                       "— this name's path is too rough for a stop at this target. "
                       "Widen it, lower the standard, or reconsider the trade. "
                       "AQE will not invent a number to fill the box.")
        else:
            st.caption(
                f"Stop survival {_prof['recommended_stop_survival']*100:.0f}% on the "
                "STRICTER of full-history vs trailing-36m — the tightest distance "
                f"where {VP.STOP_SURVIVAL_TARGET:.0%} of eventual winners were still "
                "held. Median dip before the winning touch: "
                f"{(_prof.get('median_pre_hit_dip') or 0)*100:.1f}%; typically "
                f"{_prof.get('median_sessions_to_pt1') or '—'} sessions to PT1.")

        # THE VERDICT ON THE BRACKET'S OWN TP2 — the line the committee reads.
        if _tp2_pct is not None:
            _v = VP.verdict(_prof, _tp2_pct)
            _msg = (f"**TP2 at {_tp2_pct*100:+.1f}% vs this stock's own corridor: "
                    f"{_v['verdict']}** — {_v['reason']}.")
            (st.success if _v["verdict"] == "OK" else st.warning)(_msg)
            st.caption("Where this DISAGREES with the bracket above, the "
                       "disagreement is information for the committee, not a "
                       "bug to reconcile.")

        _cap = _prof["c2c"].get("corridor_36m") or {}
        if _cap.get("capped_by_full_history"):
            st.caption("⚠️ The trailing-36m window suggested a HIGHER target and "
                       "was capped at the full-history figure. A stronger recent "
                       "window may make a target more comfortable; it never "
                       "justifies a bigger one.")

        with st.expander("Stop-survival curve + percentiles"):
            _sc = _prof.get("stop_survival_curve") or {}
            if _sc:
                table_with_copy(pd.DataFrame(
                    [{"stop %": f"{k*100:.0f}%",
                      "survival (full)": round(v, 3),
                      "survival (36m)": (_prof.get("stop_survival_curve_36m") or {}).get(k)}
                     for k, v in sorted(_sc.items())]), key="vp_curve",
                    pin_first=False)
            st.write("**Close-to-close** (governs TARGETS)", _prof["c2c"]["percentiles"])
            st.write("**High-to-low** (governs STOPS — never swapped)",
                     _prof["h2l"]["percentiles"])

with st.expander("IBKR bracket spec (paste-ready)"):
    st.json(out.get("ibkr_spec") or {})

with st.expander("Full pricer output"):
    st.json(out)
