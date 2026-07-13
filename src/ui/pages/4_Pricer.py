"""AQE Pricer — a pure bracket CALCULATOR (no recommendation, no decision).

Type in ANY ticker (universe or not). For each, it pulls daily + 5-day hourly +
5-min bars and computes a full bracket — entry, the best operative stop from the
FIB / MA / DSL / coil / swing menu, a TP ladder, R:R and size — plus the live
intraday momentum as reference. It NEVER blanks and makes NO call; paste the
numbers to the AIC to decide.
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

from src.ui.shared import require_login, load_export, table_with_copy  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.intraday.pricer import price_ticker  # noqa: E402
from src.intraday.run_plan import build_rec_lookup  # noqa: E402
from src.intraday import config as IC  # noqa: E402


@st.cache_data(ttl=300, show_spinner=False)
def _intraday(ticker: str, interval: str) -> list[dict]:
    try:
        from src.data.fmp_client import FMPClient
        return FMPClient().get_intraday_bars(ticker, interval=interval)
    except Exception:  # noqa: BLE001
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def _daily(ticker: str):
    try:
        from src.data.fmp_client import FMPClient
        frm = (date.today() - timedelta(days=400)).isoformat()
        df = FMPClient().get_daily_bars(ticker, from_date=frm)
        return df if df is not None and not df.empty else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# AQE engine scores on the priced ticker (A/B) — surface, don't recompute.
# Priority: (1) the AQE export record (last run, surfaced) → (2) scores_daily
# (scored last run but not on the daily_list) → (3) compute live via the ad-hoc
# engine suite for a symbol NOT in AQE. The FIRST hit wins, so an AQE name is
# never re-scored — only a genuinely non-AQE ticker triggers a live calc.
# ---------------------------------------------------------------------------
_SCORE_KEYS = (
    "sc_momentum", "sc_momentum_raw", "ptrs", "flow", "energy", "structure",
    "mp", "elder", "bq", "pipe_rank", "mp_state", "gics_sector", "gics_gate",
    "thematic_basket", "thematic_grade", "rs_spy_20d", "rvol", "beta_30d",
    "sma_distance_pct", "vol_30d_ann",
)


@st.cache_data(ttl=3600, show_spinner=False)
def _scores_daily_latest() -> dict:
    """{ticker: row-dict} for the latest date in scores_daily.parquet (AQE's last
    run's full scored set). Empty in cloud mode when the parquet is absent."""
    try:
        from src.data.paths import SCORES_DAILY
        if not SCORES_DAILY.exists():
            return {}
        df = pd.read_parquet(SCORES_DAILY)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        latest = df[df["date"] == df["date"].max()]
        return {r["ticker"]: r.to_dict() for _, r in latest.iterrows()}
    except Exception:  # noqa: BLE001
        return {}


def _num_or_none(v, ndp=1):
    try:
        if v is None or (isinstance(v, float) and v != v):
            return None
        return round(float(v), ndp)
    except (TypeError, ValueError):
        return v if isinstance(v, str) else None


def _scores_from_rec(rec: dict) -> dict:
    """A — pull the score fields straight off the AQE export record (no recompute)."""
    return {k: rec.get(k) for k in _SCORE_KEYS}


def _scores_from_scores_daily(row: dict) -> dict:
    """A (ext) — map a scores_daily row to the canonical score keys. GICS/thematic/
    RS aren't in scores_daily (added at export time), so they stay None here."""
    sc = _num_or_none(row.get("sc_momentum"))
    return {
        "sc_momentum": sc, "sc_momentum_raw": _num_or_none(row.get("sc_momentum_raw")),
        "ptrs": sc,  # PTRS = engine score (Sector-Health adj dropped, PM ruling)
        "flow": _num_or_none(row.get("flow_100")), "energy": _num_or_none(row.get("energy_100")),
        "structure": _num_or_none(row.get("structure_100")), "mp": _num_or_none(row.get("mp_100")),
        "elder": _num_or_none(row.get("elder_score")), "bq": _num_or_none(row.get("bq_100")),
        "pipe_rank": _num_or_none(row.get("pipe_rank")),
        "mp_state": (str(row["mp_state"]) if row.get("mp_state") is not None
                     and str(row.get("mp_state")) != "nan" else None),
        "gics_sector": None, "gics_gate": None, "thematic_basket": None,
        "thematic_grade": None, "rs_spy_20d": None, "rvol": None, "beta_30d": None,
        "sma_distance_pct": None, "vol_30d_ann": None,
    }


def _scores_from_live(s: dict) -> dict:
    """B — map a live score_tickers() result to the canonical score keys."""
    sc = s.get("sc_momentum")
    return {
        "sc_momentum": sc, "sc_momentum_raw": s.get("sc_momentum_raw"), "ptrs": sc,
        "flow": s.get("flow"), "energy": s.get("energy"), "structure": s.get("structure"),
        "mp": s.get("mp"), "elder": s.get("elder"), "bq": s.get("bq"),
        "pipe_rank": s.get("pipe_rank"), "mp_state": s.get("mp_state") or None,
        "gics_sector": None, "gics_gate": None, "thematic_basket": None, "thematic_grade": None,
        "rs_spy_20d": s.get("rs_spy_20d"), "rvol": s.get("rvol"),
        "beta_30d": s.get("beta_30d"), "sma_distance_pct": s.get("sma_distance_pct"),
        "vol_30d_ann": s.get("vol_30d_ann"),
    }


def _resolve_scores(tk: str, rec: dict | None, allow_live: bool = True) -> tuple[dict | None, str]:
    """Return (scores, source_label). Checks AQE's last run FIRST; only computes
    live for a symbol genuinely not in AQE."""
    if rec and rec.get("sc_momentum") is not None:
        return _scores_from_rec(rec), "AQE last run (export)"
    row = _scores_daily_latest().get(tk)
    if row is not None:
        return _scores_from_scores_daily(row), "AQE last run (scores_daily)"
    if allow_live:
        try:
            from src.scanner.adhoc import score_tickers
            r = score_tickers([tk])
            if r and not r[0].get("error"):
                return _scores_from_live(r[0]), "computed live (not in AQE)"
        except Exception:  # noqa: BLE001
            pass
    return None, "unavailable"


st.title("AQE Pricer — bracket calculator")
st.caption(
    "Pure calculator (no recommendation). For any ticker it computes the best "
    "entry/stop/TP from the **FIB · MA · DSL · coil · swing** menu across daily + "
    "5-day hourly + 5-min bars, with the live momentum as reference. Never blanks; "
    "you/the AIC make the call."
)

export = load_export() or {}
regime = export.get("regime") or {}
lvl = regime.get("level") if isinstance(regime, dict) else regime
st.caption(f"Regime **{lvl or '—'}** · stop ceiling **{IC.regime_stop_ceiling(regime)}%**")

recs_all = build_rec_lookup(export, ["held", "daily_list"]) if export else {}
universe = sorted(recs_all)
default_sel = [t for t in universe
               if recs_all[t].get("source") == "held"
               or recs_all[t].get("in_ledger") or recs_all[t].get("on_elder")]

c1, c2 = st.columns([2, 2])
with c1:
    typed = st.text_input("Type any tickers (comma/space separated)",
                          placeholder="e.g. NVDA, ASML, ANY-SYMBOL",
                          help="Priced even if not in the AQE universe — levels are "
                               "computed live from daily bars.")
with c2:
    picked = st.multiselect("…or pick from the export", universe, default=default_sel)

cc1, cc2 = st.columns([1, 1])
with cc1:
    st.caption("No sizing — AIC sizes; AQE shows levels only.")
with cc2:
    interval = st.selectbox(
        "Calc bars (momentum read)",
        ["5min", "15min", "30min", "1hour", "4hour", "1min"], index=0,
        help="Timeframe for the momentum/VWAP read. The bracket also uses daily "
             "structure + 5-day hourly swing candidates regardless of this pick.")

typed_list = [t.strip().upper() for t in typed.replace(",", " ").split() if t.strip()]
tickers = list(dict.fromkeys(typed_list + list(picked)))   # de-dup, keep order

if st.button("Calculate brackets", type="primary", disabled=not tickers):
    results, missing = [], []
    prog = st.progress(0.0, text="Pricing…")
    for i, tk in enumerate(tickers, 1):
        b5 = _intraday(tk, interval)
        b1 = _intraday(tk, "1hour")
        ddf = _daily(tk)
        if not b5 and ddf is None:
            missing.append(tk)
        else:
            _rec = recs_all.get(tk)
            _p = price_ticker(tk, _rec, b5, b1, ddf, regime=regime)
            # A/B — attach AQE engine scores (surfaced from the last run, or
            # computed live only if the ticker isn't in AQE at all).
            _sc, _src = _resolve_scores(tk, _rec)
            _p["scores"] = _sc or {}
            _p["score_source"] = _src
            results.append(_p)
        prog.progress(i / len(tickers), text=f"Priced {tk} ({i}/{len(tickers)})")
    prog.empty()
    st.session_state["pricer_results"] = [r for r in results if not r.get("error")]
    st.session_state["pricer_missing"] = missing

def _aic_block(p: dict) -> str:
    """Per-ticker, fact-only calculated summary to paste into the AIC.

    Captures everything computed — no judgement, no recommendation."""
    op = p["operative_stop"]
    rng = p.get("range_5d") or {}
    mom = p.get("momentum") or {}
    cand = "; ".join(
        f"{c['basis']}@{c['price']} (ATR×{c['atr_ratio']}, R:R{c['rr_tp2']}, "
        f"{c['stop_pct']}%)" for c in (p.get("candidates") or [])) or "none below entry"
    stp = "; ".join(f"{t['type']}@{t['price']} ({t['rr']}R)"
                    for t in (p.get("structural_tps") or [])) or "none"
    notes = "; ".join(p.get("notes") or []) or "none"
    ec = p.get("elder_context") or {}
    ec_line = ""
    if ec:
        vw = ec.get("vwap_5d", {})
        vo = ec.get("volume", {})
        vc = ec.get("vcp", {})
        ex = ec.get("exhaustion_check", {})
        ec_line = (
            f"\nelder_pattern={ec.get('elder_pattern')} | "
            f"VWAP5d={vw.get('value')} {vw.get('position')} slope {vw.get('slope_5d')} | "
            f"vol_trend={vo.get('vol_trend_5d')} up/dn={vo.get('up_bar_vol_ratio')} "
            f"above20d={vo.get('vol_above_20d_avg')} | "
            f"VCP {vc.get('vcp_label')} tight {vc.get('vcp_tightness_pct')}% "
            f"(base {vc.get('base_range_pct')}% / cur {vc.get('current_range_pct_5d')}%) | "
            f"exhaustion={ex.get('exhaustion_flag')}")
    sc = p.get("scores") or {}
    src = p.get("score_source") or "n/a"
    scores_line = (
        f"AQE scores [{src}]: SC_MOM={sc.get('sc_momentum')} raw={sc.get('sc_momentum_raw')} "
        f"PTRS={sc.get('ptrs')} | Flow={sc.get('flow')} Energy={sc.get('energy')} "
        f"Structure={sc.get('structure')} MP={sc.get('mp')} Elder={sc.get('elder')} "
        f"BQ={sc.get('bq')} | PipeRank={sc.get('pipe_rank')} mp_state={sc.get('mp_state')} | "
        f"GICS={sc.get('gics_sector')}/{sc.get('gics_gate')} "
        f"thematic={sc.get('thematic_basket')}({sc.get('thematic_grade')}) | "
        f"RS_SPY20d={sc.get('rs_spy_20d')} RVOL={sc.get('rvol')} beta30d={sc.get('beta_30d')} "
        f"SMA50d%={sc.get('sma_distance_pct')} vol30d_ann={sc.get('vol_30d_ann')}\n"
    )
    return (
        f"AQE Pricer — {p['ticker']} ({lvl} regime) — CALCULATED FACTS (no view):\n"
        f"universe={'yes' if p['in_universe'] else 'typed'} | price={p['price']} | "
        f"ATR14d={p['atr_14d']} | 5d_range={rng.get('low')}-{rng.get('high')}\n"
        f"{scores_line}"
        f"entry={p['entry']} | coil_entry={p['coil_entry']} | "
        f"operative_stop={op['price']} (basis={op['basis']}, risk={p['risk']}, "
        f"ATR×={op.get('atr_ratio')}, R:R_TP2={op.get('rr_tp2')}, "
        f"stop%={op.get('stop_pct')}, within_ceiling={op.get('within_ceiling')})\n"
        f"TP1={p['tp']['tp1']} (+1R) | TP2={p['tp']['tp2']} (+2R) | "
        f"TP3={p['tp']['tp3']} (+3R)\n"
        f"structural_TPs: {stp}\n"
        f"candidate_stops: {cand}\n"
        f"momentum(reference): IMS={p.get('ims')} state={p.get('state')} | "
        f"VWAP={mom.get('vwap')} pos={mom.get('vwap_pos_atr')}ATR "
        f"slope_up={mom.get('vwap_slope_up')} | OR_break={mom.get('or_break')} "
        f"(OR {mom.get('or_low')}-{mom.get('or_high')}) | "
        f"RVOL_pace={mom.get('rvol_pace')} | accel={mom.get('accel_atr_per_bar')} | "
        f"higher_lows={mom.get('higher_lows')} | ext={mom.get('ext_r')}R | "
        f"as_of={mom.get('as_of')}\n"
        f"notes: {notes}"
        f"{ec_line}\n"
        f"IBKR(recommend-only): BUY LMT {p['entry']} | "
        f"stop {op['price']} | TP {p['tp']['tp2']}"
    )


results = st.session_state.get("pricer_results")
if results:
    _SRC_TAG = {"AQE last run (export)": "AQE", "AQE last run (scores_daily)": "AQE·sd",
                "computed live (not in AQE)": "live", "unavailable": "—"}
    rows = []
    for p in results:
        op = p["operative_stop"]
        rng = p.get("range_5d") or {}
        ec = p.get("elder_context") or {}
        sc = p.get("scores") or {}
        rows.append({
            "Ticker": p["ticker"], "Univ": "✓" if p["in_universe"] else "typed",
            "Src": _SRC_TAG.get(p.get("score_source"), p.get("score_source")),
            "Price": p["price"],
            # AQE engine read (surfaced from the last run, or computed for non-AQE)
            "SC_MOM": sc.get("sc_momentum"), "PTRS": sc.get("ptrs"),
            "Flow": sc.get("flow"), "Energy": sc.get("energy"),
            "Struct": sc.get("structure"), "MP": sc.get("mp"),
            "Elder": sc.get("elder"), "Pipe": sc.get("pipe_rank"),
            "GICS": sc.get("gics_sector"), "Gate": sc.get("gics_gate"),
            "RS20d": sc.get("rs_spy_20d"),
            "5d Range": f"{rng.get('low')}–{rng.get('high')}" if rng else "—",
            "Entry": p["entry"], "Stop": op["price"], "Basis": op["basis"],
            "Stop %": op.get("stop_pct"), "Risk": p["risk"], "Coil": p["coil_entry"],
            "TP1": p["tp"]["tp1"], "TP2": p["tp"]["tp2"], "TP3": p["tp"]["tp3"],
            "IMS": p.get("ims"), "State": p.get("state"),
            "Pattern": p.get("elder_pattern"),
            "VWAP": (ec.get("vwap_5d") or {}).get("position"),
            "VolTrend": (ec.get("volume") or {}).get("vol_trend_5d"),
            "VCP": (ec.get("vcp") or {}).get("vcp_label"),
            "Exh": (ec.get("exhaustion_check") or {}).get("exhaustion_flag"),
        })
    table_with_copy(pd.DataFrame(rows), key="pricer_main")
    st.caption("**Src** = where the AQE scores came from: **AQE** (last-run export) · "
               "**AQE·sd** (last-run scores_daily) · **live** (not in AQE — scored on "
               "the fly) · **—** (unavailable). Stop = tightest level from the "
               "FIB/MA/DSL/swing menu. TP1/2/3 = mechanical +1/2/3R off the stop; "
               "structural targets per name below. **No decision implied — facts only.**")

    # (C) One-click copy of EVERY priced ticker's full fact block for the AIC.
    st.markdown("**📋 Copy ALL priced tickers (full facts) for the AIC**")
    st.code("\n\n".join(_aic_block(p) for p in results), language=None)

    for p in results:
        op = p["operative_stop"]
        with st.expander(f"{p['ticker']} — stop {op['price']} ({op['basis']}) · "
                         f"state {p.get('state')}"):
            _sc = p.get("scores") or {}
            if _sc.get("sc_momentum") is not None:
                st.caption(
                    f"**AQE read** [{p.get('score_source')}]: SC_MOM **{_sc.get('sc_momentum')}** · "
                    f"PTRS **{_sc.get('ptrs')}** · Flow {_sc.get('flow')} · Energy {_sc.get('energy')} · "
                    f"Struct {_sc.get('structure')} · MP {_sc.get('mp')} · Elder {_sc.get('elder')} · "
                    f"Pipe {_sc.get('pipe_rank')}"
                    + (f" · {_sc.get('gics_sector')}/{_sc.get('gics_gate')}"
                       if _sc.get('gics_sector') else ""))
            else:
                st.caption(f"**AQE read**: unavailable ({p.get('score_source')}) — "
                           "bracket/levels only.")
            if p.get("notes"):
                st.warning(" · ".join(p["notes"]))
            st.markdown("**Candidate levels (FIB / MA / DSL / swing — below entry)**")
            if p["candidates"]:
                table_with_copy(pd.DataFrame([
                    {"Basis": c["basis"], "Price": c["price"], "Risk": c["risk"],
                     "ATR×": c["atr_ratio"], "R:R-TP2": c["rr_tp2"],
                     "Stop %": c["stop_pct"], "ATR≥1": c["gate_atr"],
                     "R:R≥2": c["gate_rr"], "≤ceiling": c["within_ceiling"]}
                    for c in p["candidates"]]), key=f"cand_{p['ticker']}")
            else:
                st.caption("No structural support below entry — used the ATR fallback stop.")
            if p["structural_tps"]:
                st.markdown("**Structural take-profit targets (reference)**")
                table_with_copy(pd.DataFrame(p["structural_tps"]),
                                key=f"stp_{p['ticker']}")
            st.markdown("**📋 Copy this ticker for the AIC (facts only)**")
            st.code(_aic_block(p), language=None)

    missing = st.session_state.get("pricer_missing") or []
    if missing:
        st.caption(f"No price data for: {', '.join(missing)}")
else:
    st.info("Type tickers and/or pick from the export, then **Calculate brackets**.")
