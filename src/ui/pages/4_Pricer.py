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

with st.expander("IBKR bracket spec (paste-ready)"):
    st.json(out.get("ibkr_spec") or {})

with st.expander("Full pricer output"):
    st.json(out)
