"""AQE Scanner — Page 1 of the multi-page Streamlit app.

Morning dashboard: regime context, sector health, Precision Edge signals,
and aggregate longlist. Reads shortlist.json only.
Open positions live on Page 3 (Position Manager).

Launched via run_app.bat. No terminal interaction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import (
    DATA_DIR,
    ETF_NAMES,
    OUTPUT_DIR,
    file_hash,
    is_cloud_mode,
    load_export,
    load_shortlist,
    run_module_streaming,
)


def _writable(p) -> str:
    """Return 'yes' / 'no <reason>' for a path -- used by the cloud diagnostic."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".aqe_write_probe"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return "yes"
    except Exception as exc:
        return f"no ({type(exc).__name__})"
from src.data.panel_builder import PANEL_DAILY
from src.scanner.score_runner import SCORES_DAILY
from src.data.sector_mapper import load_sector_map, ETF_TO_NAME
from src.engines.srm import GICS_ETFS, get_sector_health, GRADE_TO_SH
from src.analyzer.ptrs import compute_ptrs

# ---------------------------------------------------------------------------
# Page config — MUST be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AQE Scanner",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

st.title("AQE Scanner")

# ---------------------------------------------------------------------------
# Sidebar — data refresh only
# ---------------------------------------------------------------------------
CLOUD_MODE = is_cloud_mode()
import os as _os
FMP_KEY_SET = bool(_os.environ.get("FMP_API_KEY"))

# Detect which cloud host we're on so the diagnostic + error messages can be
# precise (HF Space Secrets UI vs Streamlit Cloud Secrets UI live in different
# places and have different gotchas).
def _detect_cloud_host() -> str:
    """Return 'huggingface', 'streamlit', or 'local' based on host env vars."""
    if _os.environ.get("SPACE_ID") or _os.environ.get("SPACE_HOST"):
        return "huggingface"
    if _os.environ.get("STREAMLIT_SERVER_PORT") and CLOUD_MODE:
        return "streamlit"
    return "local"

CLOUD_HOST = _detect_cloud_host() if CLOUD_MODE else "local"

with st.sidebar:
    prog = st.empty()
    stat = st.empty()

    if CLOUD_MODE:
        st.markdown("### Cloud mode")
        host_label = {"huggingface": "Hugging Face Space",
                      "streamlit":   "Streamlit Cloud",
                      "local":       "Cloud (unknown host)"}[CLOUD_HOST]
        st.caption(
            f"Running on **{host_label}**. First pipeline run pulls 6yr of "
            "bars from FMP (~3-5 min). Subsequent runs are incremental."
        )

        # Diagnostic panel: shows env-var presence (NEVER the values) and
        # effective storage paths. Most cloud setup mistakes are visible here
        # at a glance.
        with st.expander("Cloud diagnostics", expanded=not FMP_KEY_SET):
            # Env vars AQE cares about
            env_rows = []
            for key in ("FMP_API_KEY", "AQE_DATA_DIR", "AQE_OUTPUT_DIR",
                        "ANTHROPIC_API_KEY",
                        "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
                        "GOOGLE_OAUTH_REFRESH_TOKEN",
                        "GDRIVE_FOLDER_ID", "GDRIVE_FOLDER_PATH"):
                val = _os.environ.get(key)
                if val:
                    masked = (val[:4] + "..." + val[-4:]) if len(val) > 12 else "set"
                    env_rows.append(("✅ " + key, masked))
                else:
                    env_rows.append(("⚠️ " + key, "(not set)"))
            for k, v in env_rows:
                st.text(f"{k}: {v}")
            st.text("")
            st.text(f"DATA_DIR effective:   {DATA_DIR}")
            st.text(f"OUTPUT_DIR effective: {OUTPUT_DIR}")
            data_writable = _writable(DATA_DIR)
            out_writable = _writable(OUTPUT_DIR)
            st.text(f"DATA_DIR writable:    {data_writable}")
            st.text(f"OUTPUT_DIR writable:  {out_writable}")

            # --- FMP key validation (one-shot test, no pipeline burn) ---
            st.text("")
            st.text("FMP API key (single-call test):")
            if FMP_KEY_SET:
                if st.button("Test FMP key", key="fmp_test_btn",
                             help="One SPY history call. Cheapest possible validation."):
                    with st.spinner("Calling FMP..."):
                        from src.data.fmp_client import test_api_key
                        res = test_api_key()
                        if res.get("ok"):
                            st.success(res["message"])
                        else:
                            st.error(res["message"])
                            if res.get("plan_hint"):
                                st.info(res["plan_hint"])
                else:
                    st.text("  click button above to validate key")
            else:
                st.text("  FMP_API_KEY not set -- can't test")

            # --- Drive sync status ---
            st.text("")
            st.text("Google Drive sync (cloud → your Drive):")
            try:
                from src.data import gdrive_uploader as _gd
                if not _gd.is_libs_installed():
                    st.text("  status: libs not installed (will install on next deploy)")
                elif not _gd.is_configured():
                    st.text("  status: OAuth env vars not set -- see DEPLOY.md")
                else:
                    if st.button("Test Drive credentials",
                                 key="drive_test_btn", help="Mints an access token + reads your Drive identity"):
                        with st.spinner("Validating Drive OAuth..."):
                            res = _gd.test_credentials()
                            if res.get("ok"):
                                st.success(f"Drive OK -- auth'd as {res.get('user', '?')}")
                            else:
                                st.error(f"Drive failed: {res.get('reason')}")
                    else:
                        st.text("  status: configured (click button to validate)")
            except Exception as exc:                                            # noqa: BLE001
                st.text(f"  status: error: {exc}")

        if not FMP_KEY_SET:
            if CLOUD_HOST == "huggingface":
                st.error(
                    "**FMP_API_KEY not detected in this container.**\n\n"
                    "On Hugging Face: open the Space → **Settings** → "
                    "**Variables and secrets** → **New secret** "
                    "(not Variable). Name it exactly `FMP_API_KEY`. Paste "
                    "the value from your local `.env`. Then **restart the "
                    "Space** (Settings → Factory rebuild, or just push any "
                    "commit) before the secret reaches the container."
                )
            else:
                st.error(
                    "FMP_API_KEY is not set. On Streamlit Cloud add it under "
                    "app **Settings → Secrets**. Format: "
                    "`FMP_API_KEY = \"your_key\"`"
                )

    pipeline_btn_label = "Run daily pipeline"
    if CLOUD_MODE and not (PANEL_DAILY.exists() and SCORES_DAILY.exists()):
        pipeline_btn_label = "Bootstrap + run daily pipeline (3-5 min)"
    if st.button(pipeline_btn_label, type="primary", use_container_width=True,
                 disabled=(CLOUD_MODE and not FMP_KEY_SET)):
        run_module_streaming("src.pipeline.daily_orchestrator", "Daily pipeline", prog, stat)
        st.rerun()

    with st.expander("Data Refresh", expanded=False):
        if st.button("Rebuild prices",
                     disabled=(CLOUD_MODE and not FMP_KEY_SET)):
            run_module_streaming("src.data.panel_builder", "Panel builder", prog, stat)
            st.rerun()

        if st.button("Rebuild scores"):
            run_module_streaming("src.scanner.score_runner", "Score runner", prog, stat)
            st.rerun()

    with st.expander("Universe Upload", expanded=False):
        csv_file = st.file_uploader(
            "Upload screener CSV",
            type=["csv"],
            help="CSV with a 'Symbol' column (e.g. TradingView screener export)",
        )
        if csv_file is not None:
            if st.button("Apply universe", type="secondary", use_container_width=True):
                from src.data.universe import upload_universe

                result = upload_universe(csv_file)
                st.success(
                    f"Universe updated: {result['count']} tickers "
                    f"(was {result['previous_count']})"
                )
                st.rerun()

    if not CLOUD_MODE:
        if st.button("Export to Drive", use_container_width=True):
            from src.data.drive_sync import export_to_drive

            result = export_to_drive()
            if result["status"] == "ok":
                ts = result.get("exported_at", result["date"])
                st.success(f"Exported to Drive — {ts}")
            elif result["status"] == "partial":
                st.warning(f"Local only: {result['reason']}")
            else:
                st.error(result.get("reason", "No data"))

# ---------------------------------------------------------------------------
# Onboarding check
# ---------------------------------------------------------------------------
if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
    if CLOUD_MODE:
        # On a freshly-woken Streamlit Cloud container the parquet caches are
        # absent until the first pipeline run rebuilds them. Either the bundled
        # export JSON is good enough to render the read-only view OR the user
        # needs to bootstrap.
        sl_preview = load_shortlist()
        if sl_preview is not None:
            st.info(
                "Showing the latest committed snapshot. "
                "Open the sidebar and click **Bootstrap + run daily pipeline** "
                "to refresh against live FMP data (3-5 min)."
            )
        else:
            st.warning(
                "**Cold start.** The price + score caches haven't been built yet "
                "on this Streamlit container.\n\n"
                "Open the sidebar and click **Bootstrap + run daily pipeline**. "
                "First run pulls 6yr of bars from FMP (~3-5 min); the page will "
                "refresh automatically when it finishes."
            )
            st.stop()
    else:
        st.warning(
            "Price panel or score cache not found. "
            "Open the sidebar and click **Rebuild prices**, then **Rebuild scores** to get started."
        )
        st.stop()

# ---------------------------------------------------------------------------
# Load shortlist
# ---------------------------------------------------------------------------
sl = load_shortlist()
if sl is None:
    if CLOUD_MODE:
        st.info(
            "No shortlist.json yet. Click **Run daily pipeline** in the sidebar "
            "to produce one against live FMP data."
        )
    else:
        st.info("No shortlist.json found. Click **Run daily pipeline** in the sidebar first.")
    st.stop()

# Show refresh timestamp (SGT) — main page + sidebar
_refreshed_at = sl.get("refreshed_at", "")
_ts_display = _refreshed_at or sl.get("date", "—")
st.caption(f"Last refreshed: {_ts_display}")
st.sidebar.caption(f"Data: {_ts_display}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(val, spec: str = ".2f") -> str:
    """Format a numeric value, returning '---' for None/NaN."""
    if val is None:
        return "---"
    if isinstance(val, float) and val != val:
        return "---"
    return format(val, spec)


def _sector_label(etf: str) -> str:
    """Return human-readable sector name, or the ETF ticker as fallback."""
    return ETF_NAMES.get(etf, etf)


def _elder5_str(seq) -> str:
    """Last-5 Elder scores as a compact 'a,b,c,d,e' string (oldest -> newest)."""
    if not seq:
        return "---"
    return ",".join(str(int(v)) for v in seq)


def _tp_str(d: dict, lvl: dict | None = None) -> str:
    """TP ladder +1R / +2R / +3R as a compact string."""
    lvl = lvl or {}
    t1 = d.get("tp_1r", lvl.get("target_1r"))
    t2 = d.get("tp_2r", lvl.get("target_2r"))
    t3 = d.get("tp_3r", lvl.get("target_3r"))
    if t1 is None and t2 is None and t3 is None:
        return "---"
    return " / ".join(_fmt(x, ".2f") for x in (t1, t2, t3))


def _fib_str(fib) -> str:
    """Key Fibonacci levels: 0.618 retracement (support) / 1.618 extension."""
    if not fib:
        return "---"
    sup = fib.get("retracements", {}).get("0.618")
    tgt = fib.get("extensions", {}).get("1.618")
    return f"{_fmt(sup, '.2f')} / {_fmt(tgt, '.2f')}"


@st.cache_data(ttl=600)
def _load_sector_lookup() -> dict[str, str]:
    """Return {ticker: 'Technology', ...} — human sector names for the universe."""
    sm = load_sector_map()
    return {tk: ETF_TO_NAME.get(etf, etf) for tk, etf in sm.items()}


def _ticker_sector(ticker: str) -> str:
    """Look up human-readable sector for a ticker."""
    return _load_sector_lookup().get(ticker, "—")


def _quick_ptrs(sc_mom: float, ticker: str, sector_grades: dict) -> float:
    """Compute PTRS for any ticker: SC_MOM + SH (sector health only)."""
    sh = get_sector_health(ticker, sector_grades)
    result = compute_ptrs(sc_mom, sh)
    ptrs = result.get("ptrs")
    return round(ptrs, 1) if ptrs is not None and ptrs == ptrs else 0.0


@st.cache_data(ttl=600, show_spinner=False)
def _load_sector_sh_map() -> dict[str, int]:
    """Return {ticker: SH_value} for every ticker in sector_map.json."""
    sm = load_sector_map()  # {ticker: 'XLK', ...}
    return sm  # we'll resolve SH at call time


def _vectorized_ptrs(df: pd.DataFrame, sector_grades: dict) -> pd.Series:
    """Compute PTRS for a full DataFrame: SC_MOM + SH (vectorized)."""
    from src.data.sector_mapper import load_sector_map
    sm = load_sector_map()  # {ticker: 'XLE', ...}

    # Map ticker -> sector ETF -> SH value (vectorized)
    sh_series = df["ticker"].map(
        lambda t: sector_grades.get(sm.get(t, ""), {}).get("sh", 0)
    )
    ptrs = df["sc_momentum"].fillna(0) + sh_series.fillna(0)
    return ptrs.round(1)


def _rank_explain(pipe_rank: float, floor: float, sc_mom: float,
                  pe_qualified: bool, ticker: str,
                  sm: dict, sector_grades: dict) -> str:
    """1-liner explaining why a ticker sits at its rank."""
    parts: list[str] = []
    pr = pipe_rank or 0
    fl = floor or 0

    # Primary sort key: Pipeline Rank
    if pr >= 80:
        parts.append(f"PipeRk {pr:.0f} leads")
    elif pr >= 60:
        parts.append(f"PipeRk {pr:.0f}")
    elif pr > 0:
        parts.append(f"PipeRk {pr:.0f} caps rank")
    else:
        parts.append("No PipeRk")

    if pe_qualified:
        parts.append("PE pick")

    # Floor context (tiebreaker / engine strength)
    if pr <= 0:
        parts.append(f"Floor {fl:.0f} sorts")
    elif fl >= 70 and pr < 70:
        parts.append(f"engines strong (Floor {fl:.0f})")
    elif fl < 45 and pr > 0:
        parts.append(f"Floor {fl:.0f} drags")

    # Sector grade when notable
    etf = sm.get(ticker, "")
    grade = sector_grades.get(etf, {}).get("grade", "")
    if grade == "DEPLOY":
        parts.append("sector DEPLOY")
    elif grade == "AVOID":
        parts.append("sector AVOID")

    return "; ".join(parts) if parts else "—"


@st.cache_data(ttl=600, show_spinner=False)
def _load_betas(_hash: str) -> dict[str, dict]:
    """30-day and 60-day rolling beta vs SPY for all tickers (cached).

    Returns {ticker: {30: beta30, 60: beta60}}. See src.scanner.betas.
    """
    from src.scanner.betas import load_betas
    return load_betas()


@st.cache_data(ttl=600, show_spinner=False)
def _compute_dsl_levels(_hash: str) -> dict[str, dict]:
    """DSL stop, TP ladder, Fibonacci levels and estimated R/R per ticker.

    Returns {ticker: {entry, stop, risk, tp_1r, tp_2r, tp_3r, be, shares,
                      rr_pct, rr_est, fib}}. See src.scanner.levels.
    """
    from src.scanner.levels import load_trade_levels
    return load_trade_levels()


@st.cache_data(ttl=600, show_spinner=False)
def _elder_history(_hash: str) -> dict[str, list]:
    """Last 5 Elder Impulse scores per ticker, oldest -> newest."""
    from src.scanner.levels import load_elder_history
    return load_elder_history()


def _recipe_label(recipe: dict) -> str:
    """Build a compact label from recipe thresholds."""
    parts = []
    mapping = [
        ("sc_mom_min", "SC"),
        ("flow_min", "Flow"),
        ("energy_min", "Energy"),
        ("structure_min", "Struct"),
        ("mp_min", "MP"),
        ("elder_min", "Elder"),
    ]
    for key, name in mapping:
        v = recipe.get(key)
        if v is not None and v > 0:
            parts.append(f"{name}>={int(v)}")
    return " | ".join(parts) if parts else recipe.get("name", "Recipe")


# ---------------------------------------------------------------------------
# 1. Regime context bar
# ---------------------------------------------------------------------------
regime = sl.get("regime", {})
c1, c2, c3 = st.columns(3)
with c1:
    vix_val = regime.get("vix", 0)
    st.metric("VIX", _fmt(vix_val, ".1f"), delta=regime.get("level", "---"), delta_color="off")
with c2:
    hurst_val = regime.get("hurst", 0)
    st.metric("Hurst", _fmt(hurst_val, ".2f"), delta=regime.get("trend", "---"), delta_color="off")
with c3:
    st.metric("Max New Size", sl.get("max_new_size", "---"))

st.divider()

# ---------------------------------------------------------------------------
# 2. SRM Sector Health — regime + trend
# ---------------------------------------------------------------------------
st.subheader("SRM Sector Health")

srm_detail = sl.get("srm_detail", {})
if srm_detail:
    # Build table sorted by grade rank
    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}
    srm_rows = []
    for etf, d in sorted(srm_detail.items(), key=lambda x: grade_order.get(x[1].get("grade", "WATCH"), 3)):
        roc20 = d.get("roc20", 0)
        roc5 = d.get("roc5", 0)
        trend = "Accelerating" if roc5 > roc20 / 4 else ("Slowing" if roc5 < 0 else "Steady")
        srm_rows.append({
            "Sector": _sector_label(etf),
            "Grade": d.get("grade", "---"),
            "20d Chg%": _fmt(roc20, "+.1f"),
            "5d Chg%": _fmt(roc5, "+.1f"),
            "Trend": trend,
            "Above SMA20": "Yes" if d.get("above_sma20") else "No",
        })
    df_srm = pd.DataFrame(srm_rows)
    st.dataframe(df_srm, use_container_width=True, hide_index=True)
else:
    # Fallback to legacy bucket summary
    srm = sl.get("srm_summary", {})
    sector_parts = []
    for bucket in ("DEPLOY", "HOLD", "WATCH", "AVOID"):
        tickers = srm.get(bucket, [])
        if tickers:
            names = ", ".join(_sector_label(t) for t in tickers)
            sector_parts.append(f"**{bucket}:** {names}")
    st.markdown(" | ".join(sector_parts))

# PTRS context — used by longlist and watchlist tables below
# PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
_sector_grades = sl.get("srm_detail", {})
_sector_map_raw = load_sector_map()  # {ticker: 'XLK'} for rank explainer

if CLOUD_MODE:
    # Re-hydrate the per-ticker level / beta / elder lookups from the export
    # JSON so the read-only deploy never touches the 137MB parquet files.
    _export = load_export() or {}

    def _build_cloud_lookups(export: dict) -> tuple[dict, dict, dict]:
        betas: dict[str, dict] = {}
        dsl: dict[str, dict] = {}
        elder5: dict[str, list] = {}
        rows = []
        for key in ("top_picks", "edge_list", "longlist", "watchlist"):
            rows.extend(export.get(key) or [])
        for r in rows:
            tk = r.get("ticker")
            if not tk or tk in dsl:
                continue
            betas[tk] = {30: r.get("beta_30d")}
            dsl[tk] = {
                "entry": r.get("entry"),
                "stop": r.get("dsl_stop"),
                "risk": r.get("dsl_risk"),
                "tp_1r": r.get("dsl_tp_1r"),
                "tp_2r": r.get("dsl_tp_2r"),
                "tp_3r": r.get("dsl_tp_3r"),
                "be":    r.get("dsl_be"),
                "shares": r.get("dsl_shares"),
                "rr_pct": r.get("dsl_rr_pct"),
                "dsl_atr_ratio": r.get("dsl_atr_ratio"),
                "rr_est": r.get("rr_est"),
                "fib":    r.get("fib"),
            }
            elder5[tk] = r.get("elder_5d") or []
        return betas, dsl, elder5

    _betas, _dsl, _elder5 = _build_cloud_lookups(_export)
else:
    _betas = _load_betas(file_hash(PANEL_DAILY))  # 30d beta vs SPY (primary display)
    _dsl = _compute_dsl_levels(file_hash(PANEL_DAILY) + ":" + file_hash(SCORES_DAILY))
    _elder5 = _elder_history(file_hash(SCORES_DAILY))  # last 5 Elder scores per ticker

st.divider()

# ---------------------------------------------------------------------------
# 3. Precision Edge
# ---------------------------------------------------------------------------
st.subheader("Precision Edge")

pe_signals = sl.get("precision_edge", [])
pe_recipe = sl.get("precision_recipe", {})
bt = pe_recipe.get("_backtest", {})

if bt:
    st.caption(
        f"Backtest: WR {bt.get('win_rate', 0):.1f}% | "
        f"{bt.get('per_week', 0):.1f} trades/wk | "
        f"Exp {bt.get('expectancy_r', 0):.2f}R | "
        f"{bt.get('trades', 0)} trades | "
        f"{bt.get('period', '')}"
    )

if not pe_signals:
    st.info("No Precision Edge signals today.")
else:
    for sig in pe_signals:
        ticker = sig.get("ticker", "???")
        disp = sig.get("disposition", "---")
        note = sig.get("note", "")
        ctx = sig.get("context", {})
        sector = _sector_label(ctx.get("sector", ""))
        grade = ctx.get("sector_grade", "")
        lvl = sig.get("levels", {})
        eng = sig.get("engines", {})

        # Header line
        header = f"**{ticker}**"
        if sector:
            header += f" | {sector}"
        if grade:
            header += f" ({grade})"
        header += f" | {disp}"
        if note:
            header += f" | {note}"
        st.markdown(header)

        # Levels — two rows of 4 for readability
        r1 = st.columns(4)
        r1[0].metric("Entry", _fmt(lvl.get("entry"), ".2f"))
        r1[1].metric("Stop", _fmt(lvl.get("stop"), ".2f"))
        r1[2].metric("R-size", _fmt(lvl.get("r_size"), ".2f"))
        r1[3].metric("QTY", _fmt(lvl.get("shares"), ".0f"))
        r2 = st.columns(4)
        r2[0].metric("+1R", _fmt(lvl.get("target_1r"), ".2f"))
        r2[1].metric("+2R", _fmt(lvl.get("target_2r"), ".2f"))
        r2[2].metric("+3R", _fmt(lvl.get("target_3r"), ".2f"))
        r2[3].metric("Risk $", _fmt(lvl.get("risk_dollars"), ".0f"))

        # Voice breakdown — sub-component values
        subcomps = sig.get("subcomp_values", {})
        if subcomps:
            parts_sc = []
            for _key, sc in subcomps.items():
                check = "PASS" if sc.get("pass") else "FAIL"
                parts_sc.append(
                    f"{sc.get('label', _key)}: {_fmt(sc.get('value'), '.2f')} "
                    f"vs {_fmt(sc.get('threshold'), '.2f')} "
                    f"[{sc.get('engine', '')}] {check}"
                )
            st.caption(" --- ".join(parts_sc))

        # Engine scores
        eng_parts = []
        for ename in ("flow", "energy", "structure", "mp", "elder"):
            v = eng.get(ename)
            if v is not None:
                eng_parts.append(f"{ename.title()}: {_fmt(v, '.1f')}")
        if eng_parts:
            st.caption("Engines: " + " | ".join(eng_parts))

        st.markdown("---")

st.divider()

# ---------------------------------------------------------------------------
# 4. Longlist (Aggregate + PE)
# ---------------------------------------------------------------------------
st.subheader("Longlist")

active_recipe = sl.get("active_recipe", {})
recipe_str = _recipe_label(active_recipe)
st.caption(f"Aggregate recipe: {recipe_str}")
st.caption(
    "Sorted by Pipeline Rank + Floor | DSL = structural stop | "
    "TP 1/2/3 = +1R/+2R/+3R | R% = risk/price | "
    "Distance to SL = (entry − DSL stop) ÷ entry, expressed as %; how far price must fall before the stop is hit | "
    "ATR Width = (entry − DSL stop) ÷ ATR14; how many average true range units the stop sits below entry "
    "(1.0 = stop is exactly 1 ATR below entry; ≤1.5 tight stop, 2.0 standard, ≥2.0 wide/high-β name) | "
    "R/R = estimated reward ÷ risk: (1.618 Fib extension − entry) ÷ (entry − DSL stop) | "
    "Fib = Fibonacci levels anchored on most recent swing low→high (0.618 retracement / 1.618 extension) | "
    "Elder5d = Elder Impulse score for each of the last 5 trading sessions (1–10 scale, ≥7 = bullish impulse) | "
    "Beta30 = 30-day rolling beta vs SPY (sensitivity to broad market moves; ≥1.5 = high-β, gets wider DSL stop)"
)

# recipe_matches now includes both aggregate qualifiers AND PE picks
recipe_matches = sl.get("recipe_matches", [])
candidates = sl.get("candidates", [])

n_pe = sum(1 for rm in recipe_matches if rm.get("pe_qualified"))
n_agg = len(recipe_matches) - n_pe
st.markdown(f"**{len(recipe_matches)}** qualify today ({n_agg} aggregate, {n_pe} Precision Edge)")

if recipe_matches:
    rows = []
    for i, rm in enumerate(recipe_matches, 1):
        lvl = rm.get("levels", {})
        eng = rm.get("engines", {})
        source = "PE" if rm.get("pe_qualified") else ""
        ticker = rm.get("ticker", "")

        floor = min(eng.get("flow", 0), eng.get("energy", 0),
                    eng.get("structure", 0), eng.get("mp", 0))
        sc_val = rm.get("sc_momentum", 0) or 0
        ptrs_val = _quick_ptrs(sc_val, ticker, _sector_grades)

        dsl = _dsl.get(ticker, {})
        rows.append({
            "#": i,
            "Ticker": ticker,
            "Sector": _ticker_sector(ticker),
            "Source": source,
            "Score": _fmt(rm.get("sc_momentum"), ".1f"),
            "Raw": _fmt(rm.get("sc_momentum_raw"), ".1f"),
            "PTRS": _fmt(ptrs_val, ".1f"),
            "PipeRk": _fmt(rm.get("pipe_rank"), ".1f"),
            "Floor": _fmt(floor, ".1f"),
            "Beta30": _fmt((_betas.get(ticker) or {}).get(30), ".2f"),
            "Flow": _fmt(eng.get("flow"), ".0f"),
            "Energy": _fmt(eng.get("energy"), ".0f"),
            "Struct": _fmt(eng.get("structure"), ".0f"),
            "MP": _fmt(eng.get("mp"), ".0f"),
            "Elder": _fmt(eng.get("elder"), ".1f"),
            "Elder5d": _elder5_str(_elder5.get(ticker)),
            "Entry": _fmt(dsl.get("entry", lvl.get("entry")), ".2f"),
            "DSL": _fmt(dsl.get("stop", lvl.get("stop")), ".2f"),
            "TP 1/2/3": _tp_str(dsl, lvl),
            "Distance to SL": _fmt(dsl.get("rr_pct"), ".1f"),
            "R/R": _fmt(dsl.get("rr_est"), ".1f"),
            "ATR Width": _fmt(dsl.get("dsl_atr_ratio"), ".2f"),
            "Fib": _fib_str(dsl.get("fib")),
            "Why": _rank_explain(
                rm.get("pipe_rank", 0), floor, sc_val,
                rm.get("pe_qualified", False), ticker,
                _sector_map_raw, _sector_grades,
            ),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Earnings warnings
    earn_warned = []
    for c in candidates:
        if c.get("diagnostics", {}).get("earn_warning"):
            earn_warned.append(c["ticker"])
    for rm in recipe_matches:
        t = rm["ticker"]
        # Also check candidates for this ticker
        for c in candidates:
            if c["ticker"] == t and c.get("diagnostics", {}).get("earn_warning") and t not in earn_warned:
                earn_warned.append(t)
    if earn_warned:
        st.warning(f"Earnings within 5 days: {', '.join(earn_warned)}")
else:
    st.info("No tickers qualify for the aggregate longlist today. Review recipe thresholds on Page 2.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Signal Scanner — full universe scan with sector overlay
# ---------------------------------------------------------------------------
st.subheader("Watchlist")
st.caption(
    "Full universe filtered by raw SC_MOM slider. "
    "Sorted by Pipeline Rank + Floor (same as longlist). "
    "Sector summary shows where signals are concentrating today. "
    "DSL / TP 1-2-3 / R/R / Fib / Elder5d columns as per the longlist."
)

@st.cache_data(ttl=300, show_spinner=False)
def _load_latest_scores(_hash: str) -> pd.DataFrame:
    """Load latest-date slice from scores_daily.parquet."""
    df = pd.read_parquet(SCORES_DAILY)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    latest = df["date"].max()
    out = df[df["date"] == latest].copy()
    return out

def _watchlist_from_export(export: dict) -> pd.DataFrame:
    """Construct a `latest_scores`-shaped DataFrame from the export JSON.

    Used in cloud read-only mode where we don't have scores_daily.parquet.
    The export's watchlist + longlist together cover every ticker the local
    scanner would have surfaced.
    """
    seen: set[str] = set()
    rows: list[dict] = []
    for key in ("watchlist", "longlist"):
        for r in (export.get(key) or []):
            tk = r.get("ticker")
            if not tk or tk in seen:
                continue
            seen.add(tk)
            rows.append({
                "ticker": tk,
                "sc_momentum": r.get("sc_momentum"),
                "sc_momentum_raw": r.get("sc_momentum_raw") or r.get("sc_momentum"),
                "flow_100": r.get("flow"),
                "energy_100": r.get("energy"),
                "structure_100": r.get("structure"),
                "mp_100": r.get("mp"),
                "elder_score": r.get("elder"),
                "pipe_rank": r.get("pipe_rank"),
            })
    return pd.DataFrame(rows)


if CLOUD_MODE:
    _wl_export = _export                    # already loaded above
    latest_scores = _watchlist_from_export(_wl_export) if _wl_export else pd.DataFrame()
    _have_scan = not latest_scores.empty
elif SCORES_DAILY.exists():
    scores_hash = file_hash(SCORES_DAILY)
    latest_scores = _load_latest_scores(scores_hash)
    _have_scan = True
else:
    _have_scan = False

if _have_scan:

    # Controls: slider + number box side-by-side
    sc_col1, sc_col2 = st.columns([3, 1])
    with sc_col1:
        scan_threshold = st.select_slider(
            "Raw SC_MOM threshold",
            options=list(range(50, 96)),
            value=70,
            key="scan_threshold",
        )
    with sc_col2:
        st.markdown(f"### {scan_threshold}")
        st.caption("Selected")

    # Filter by raw SC_MOM (use raw if available, else gated)
    raw_col = "sc_momentum_raw" if "sc_momentum_raw" in latest_scores.columns else "sc_momentum"
    scan_mask = latest_scores[raw_col] >= scan_threshold
    # Exclude sector ETFs and SPY
    exclude = set(GICS_ETFS) | {"SPY"}
    scan_mask &= ~latest_scores["ticker"].isin(exclude)

    # Compute floor for sorting, then sort by pipe_rank + floor (same as longlist)
    scan_df = latest_scores[scan_mask].copy()
    for c in ("pipe_rank", "flow_100", "energy_100", "structure_100", "mp_100"):
        if c in scan_df.columns:
            scan_df[c] = pd.to_numeric(scan_df[c], errors="coerce").fillna(0)
    scan_df["_floor"] = scan_df[["flow_100", "energy_100", "structure_100", "mp_100"]].min(axis=1)
    scan_df = scan_df.sort_values(
        ["pipe_rank", "_floor"], ascending=[False, False]
    ).reset_index(drop=True)

    # Sector lookup
    sector_lookup = _load_sector_lookup()

    st.markdown(f"**{len(scan_df)}** tickers with raw SC >= {scan_threshold}")

    # --- Sector summary counter ---
    if not scan_df.empty:
        scan_df["_sector"] = scan_df["ticker"].map(lambda t: sector_lookup.get(t, "Unknown"))
        sector_counts = scan_df["_sector"].value_counts()

        st.markdown("**Sector signal concentration:**")
        sc_parts = []
        for sect, cnt in sector_counts.items():
            sc_parts.append(f"**{sect}**: {cnt}")
        # Display as a wrapped line of bold-count pairs
        st.markdown(" · ".join(sc_parts))

        # Vectorized PTRS for the whole watchlist (fast)
        scan_df["_ptrs"] = _vectorized_ptrs(scan_df, _sector_grades)

        # Build results table
        scan_rows = []
        for i, (_, row) in enumerate(scan_df.iterrows(), 1):
            ticker = row["ticker"]
            dsl = _dsl.get(ticker, {})
            scan_rows.append({
                "#": i,
                "Ticker": ticker,
                "Sector": sector_lookup.get(ticker, "—"),
                "Score": _fmt(float(row["sc_momentum"]), ".1f"),
                "Raw": _fmt(float(row.get("sc_momentum_raw", row["sc_momentum"])), ".1f"),
                "PTRS": _fmt(float(row["_ptrs"]), ".1f"),
                "PipeRk": _fmt(float(row.get("pipe_rank", 0)), ".1f"),
                "Floor": _fmt(float(row["_floor"]), ".1f"),
                "Beta30": _fmt((_betas.get(ticker) or {}).get(30), ".2f"),
                "Flow": _fmt(float(row.get("flow_100", 0)), ".0f"),
                "Energy": _fmt(float(row.get("energy_100", 0)), ".0f"),
                "Struct": _fmt(float(row.get("structure_100", 0)), ".0f"),
                "MP": _fmt(float(row.get("mp_100", 0)), ".0f"),
                "Elder": _fmt(float(row.get("elder_score", 0)), ".1f"),
                "Elder5d": _elder5_str(_elder5.get(ticker)),
                "Entry": _fmt(dsl.get("entry"), ".2f"),
                "DSL": _fmt(dsl.get("stop"), ".2f"),
                "TP 1/2/3": _tp_str(dsl),
                "Distance to SL": _fmt(dsl.get("rr_pct"), ".1f"),
                "R/R": _fmt(dsl.get("rr_est"), ".1f"),
                "ATR Width": _fmt(dsl.get("dsl_atr_ratio"), ".2f"),
                "Fib": _fib_str(dsl.get("fib")),
                "Why": _rank_explain(
                    float(row.get("pipe_rank", 0)), float(row["_floor"]),
                    float(row["sc_momentum"]), False, ticker,
                    _sector_map_raw, _sector_grades,
                ),
            })

        df_scan = pd.DataFrame(scan_rows)
        st.dataframe(df_scan, use_container_width=True, hide_index=True)
    else:
        st.info(f"No tickers above raw SC >= {scan_threshold} today.")
else:
    if CLOUD_MODE:
        st.info(
            "Watchlist data not in the export JSON yet. "
            "Run the daily pipeline locally + push the export to refresh."
        )
    else:
        st.warning("scores_daily.parquet not found. Rebuild scores first.")


# Open positions live on Page 3 (Position Manager) — no duplication here.

st.divider()

# ---------------------------------------------------------------------------
# 6. Ad-hoc Ticker Scorer — score names beyond the uploaded universe
# ---------------------------------------------------------------------------
st.subheader("Ad-hoc Ticker Scorer")

if CLOUD_MODE and not FMP_KEY_SET:
    st.info(
        "Ad-hoc scoring needs FMP. Set **FMP_API_KEY** in Streamlit secrets "
        "(app **Settings -> Secrets**) and reload to enable this section."
    )
    st.stop()

st.caption(
    "Score up to 10 tickers on demand — including names outside your uploaded "
    "universe. Pulls fresh daily bars from FMP and runs the full engine suite "
    "on the latest available bar. Results are display-only — nothing is saved "
    "to the universe or score cache."
)

_adhoc_in = st.text_input(
    "Tickers — comma or space separated, max 10",
    placeholder="e.g.  NVDA, PLTR, COIN",
    key="adhoc_tickers_input",
)

if st.button("Score tickers", type="primary", key="adhoc_score_btn"):
    _seen: list[str] = []
    for _t in _adhoc_in.replace(",", " ").split():
        _t = _t.strip().upper()
        if _t and _t not in _seen:
            _seen.append(_t)
    if not _seen:
        st.warning("Enter at least one ticker.")
        st.session_state.pop("adhoc_results", None)
    else:
        if len(_seen) > 10:
            st.warning(f"{len(_seen)} tickers entered — scoring the first 10.")
        _to_score = _seen[:10]
        with st.spinner(f"Fetching and scoring {len(_to_score)} ticker(s)..."):
            from src.scanner.adhoc import score_tickers
            st.session_state["adhoc_results"] = score_tickers(_to_score)

_adhoc_results = st.session_state.get("adhoc_results")
if _adhoc_results:
    _ok = [r for r in _adhoc_results if not r.get("error")]
    _err = [r for r in _adhoc_results if r.get("error")]

    if _ok:
        st.caption(
            "DSL / TP 1-2-3 / R/R / Fib / Elder5d as per the longlist. "
            "As-of = the latest bar scored — may be fresher than the tables above."
        )
        _adhoc_rows = []
        for r in _ok:
            lv = r.get("levels") or {}
            _adhoc_rows.append({
                "Ticker": r["ticker"],
                "As-of": r.get("as_of", "---"),
                "Score": _fmt(r.get("sc_momentum"), ".1f"),
                "Raw": _fmt(r.get("sc_momentum_raw"), ".1f"),
                "Gate": "PASS" if r.get("gate_pass") else "CAPPED",
                "Flow": _fmt(r.get("flow"), ".0f"),
                "Energy": _fmt(r.get("energy"), ".0f"),
                "Struct": _fmt(r.get("structure"), ".0f"),
                "MP": _fmt(r.get("mp"), ".0f"),
                "Elder": _fmt(r.get("elder"), ".1f"),
                "Elder5d": _elder5_str(r.get("elder_5d")),
                "BQ": _fmt(r.get("bq"), ".0f"),
                "PipeRk": _fmt(r.get("pipe_rank"), ".1f"),
                "Beta30": _fmt(r.get("beta_30d"), ".2f"),
                "Entry": _fmt(lv.get("entry"), ".2f"),
                "DSL": _fmt(lv.get("stop"), ".2f"),
                "TP 1/2/3": _tp_str(lv),
                "Distance to SL": _fmt(lv.get("rr_pct"), ".1f"),
                "R/R": _fmt(lv.get("rr_est"), ".1f"),
                "ATR Width": _fmt(lv.get("dsl_atr_ratio"), ".2f"),
                "Fib": _fib_str(lv.get("fib")),
            })
        st.dataframe(pd.DataFrame(_adhoc_rows), use_container_width=True, hide_index=True)

    for r in _err:
        st.warning(f"**{r['ticker']}** — {r['error']}")
