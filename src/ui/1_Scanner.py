"""AQE Scanner — Page 1 of the multi-page Streamlit app.

Morning dashboard: regime context, sector health, Precision Edge signals,
and aggregate longlist. Reads shortlist.json only.

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
    require_login,
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

# Password gate — halts here with a sign-in form until authenticated when
# AQE_APP_PASSWORD is set (public Space). No-op locally.
require_login()

st.title("AQE Scanner")

# ---------------------------------------------------------------------------
# Daily auto-run status bar (08:30 SGT, Tue–Sat)
# ---------------------------------------------------------------------------
try:
    from src.ui.daily_job import last_run_status, next_run_hint
    _lr = last_run_status()
    if _lr is None:
        st.info(f"⏱️ Auto-run scheduled {next_run_hint()}. No run recorded yet.")
    elif _lr.get("status") == "success":
        _picks = _lr.get("top_picks")
        _pk = f" · {_picks} top picks" if _picks is not None else ""
        st.success(
            f"✅ Last auto-run {_lr.get('finished_at', '?')} — pushed to Drive"
            f"{_pk}. Next: {next_run_hint()}."
        )
    else:
        _why = _lr.get("reason") or f"exit code {_lr.get('rc', '?')}"
        st.warning(
            f"⚠️ Last auto-run {_lr.get('finished_at', _lr.get('started_at','?'))} "
            f"FAILED ({_why}). Next: {next_run_hint()}."
        )
except Exception:  # noqa: BLE001
    pass

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
            f"Running on **{host_label}**. First pipeline run pulls 2yr of "
            "bars from FMP (~2 min). Subsequent runs are incremental. "
            "If FMP quota caps mid-run, run again to pull remaining tickers."
        )

        # Diagnostic panel: shows env-var presence (NEVER the values) and
        # effective storage paths. Most cloud setup mistakes are visible here
        # at a glance.
        with st.expander("Cloud diagnostics", expanded=not FMP_KEY_SET):
            # Env vars AQE cares about.
            # Keys with valid coded defaults show ✅ even when unset.
            _HAS_DEFAULT = {
                "AQE_DATA_DIR": str(DATA_DIR),
                "AQE_OUTPUT_DIR": str(OUTPUT_DIR),
                "GDRIVE_FOLDER_ID": "(pinned in code)",
            }
            _REQUIRED = (
                "FMP_API_KEY", "AQE_APP_PASSWORD",
                "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
                "GOOGLE_OAUTH_REFRESH_TOKEN",
            )
            _OPTIONAL_WITH_DEFAULT = ("AQE_DATA_DIR", "AQE_OUTPUT_DIR",
                                      "GDRIVE_FOLDER_ID", "GDRIVE_FOLDER_PATH")
            env_rows = []
            for key in (*_REQUIRED, *_OPTIONAL_WITH_DEFAULT):
                val = _os.environ.get(key)
                if val:
                    if key == "AQE_APP_PASSWORD":
                        masked = "set"
                    else:
                        masked = (val[:4] + "..." + val[-4:]) if len(val) > 12 else "set"
                    env_rows.append(("✅ " + key, masked))
                elif key in _HAS_DEFAULT:
                    env_rows.append(("✅ " + key, f"default: {_HAS_DEFAULT[key]}"))
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
        pipeline_btn_label = "Bootstrap + run daily pipeline (~2 min)"
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

    with st.expander("💾 Daily Persist", expanded=False):
        from src.data.persist import save_snapshot, load_snapshot, snapshot_status

        _snap = snapshot_status()
        if _snap:
            st.caption(f"Last saved: **{_snap.get('saved_at', '?')}** · "
                       f"{len(_snap.get('files', []))} files · "
                       f"{(_snap.get('bytes', 0) / 1e6):.1f} MB")
        else:
            st.caption("No snapshot on Drive yet.")

        pc1, pc2 = st.columns(2)
        if pc1.button("💾 Save run", use_container_width=True,
                      help="Zip the current panel/scores/export to Drive."):
            with st.spinner("Saving snapshot to Drive…"):
                _r = save_snapshot()
            if _r.get("ok"):
                st.success(f"Saved {len(_r.get('files', []))} files "
                           f"({(_r.get('bytes', 0) / 1e6):.1f} MB).")
            else:
                st.error(f"Save failed: {_r.get('reason')}")
        if pc2.button("📥 Load run", use_container_width=True,
                      help="Restore the last saved run — skips the full pipeline."):
            with st.spinner("Restoring snapshot from Drive…"):
                _r = load_snapshot()
            if _r.get("ok"):
                st.cache_data.clear()
                st.success(f"Restored {_r.get('count')} files "
                           f"(saved {_r.get('saved_at')}). Reloading…")
                st.rerun()
            else:
                st.error(f"Load failed: {_r.get('reason')}")
        st.caption("Persists the runtime parquets + export so a merge/restart "
                   "skips the full AQE re-run.")

    with st.expander("Universe", expanded=False):
        @st.cache_data(ttl=300, show_spinner=False)
        def _universe_status():
            from src.data.universe import get_drive_universe_status, load_universe
            info = get_drive_universe_status()
            if info:
                return {"source": "Drive", **info}
            try:
                n = len(load_universe(include_benchmark=False))
            except Exception:  # noqa: BLE001
                n = 0
            return {"source": "local", "name": "universe.txt", "count": n, "modified": None}

        _u = _universe_status()
        _when = (_u.get("modified") or "")[:10] or "—"
        st.caption(
            f"📋 **{_u['count']} tickers** · `{_u['name']}` · updated {_when} "
            f"· {_u['source']}"
        )
        csv_file = st.file_uploader(
            "Upload screener CSV (overwrites the Drive universe file)",
            type=["csv"],
            help="CSV with a 'Symbol' column (e.g. TradingView screener export). "
                 "Written to the dedicated universe folder in Drive.",
        )
        if csv_file is not None:
            if st.button("Apply universe", type="secondary", use_container_width=True):
                from src.data.universe import upload_universe

                result = upload_universe(csv_file)
                msg = (f"Universe updated: {result['count']} tickers "
                       f"(was {result['previous_count']})")
                if result.get("drive_ok"):
                    st.success(msg + " — saved to Drive ✓")
                else:
                    st.warning(msg + f" — Drive save failed: {result.get('drive_reason')}")
                _universe_status.clear()
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
                "to refresh against live FMP data (~2 min)."
            )
        else:
            st.warning(
                "**Cold start.** The price + score caches haven't been built yet "
                "on this Streamlit container.\n\n"
                "Open the sidebar and click **Bootstrap + run daily pipeline**. "
                "First run pulls 2yr of bars from FMP (~2 min); the page will "
                "refresh automatically when it finishes. If FMP quota caps "
                "mid-run, click again to pull remaining tickers."
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
    # ── Visual panels: RRG scatter + Macro weather (above the table) ──
    _has_rrg = any(
        d.get("rrg_rs_ratio") is not None for d in srm_detail.values()
    )
    if _has_rrg:
        _rrg_col, _macro_col = st.columns([3, 2])

        # ── RRG Scatter Plot (left) ──
        with _rrg_col:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            _pts = []
            for _etf, _d in srm_detail.items():
                _r = _d.get("rrg_rs_ratio")
                _m = _d.get("rrg_rs_momentum")
                if _r is not None and _m is not None:
                    _pts.append((_etf, _r, _m, _d.get("entry_gate", "WATCH"),
                                 _d.get("rrg_direction", "STABLE")))

            if _pts:
                _ratios = [p[1] for p in _pts]
                _moms = [p[2] for p in _pts]
                _pad = max(1.5, (max(_ratios) - min(_ratios)) * 0.2,
                           (max(_moms) - min(_moms)) * 0.2)
                _xlo = min(min(_ratios), 98) - _pad
                _xhi = max(max(_ratios), 102) + _pad
                _ylo = min(min(_moms), 98) - _pad
                _yhi = max(max(_moms), 102) + _pad

                _fig, _ax = plt.subplots(figsize=(5.5, 4.2))

                _ax.fill_between([100, _xhi], 100, _yhi, alpha=0.06, color="#2ca02c")
                _ax.fill_between([_xlo, 100], 100, _yhi, alpha=0.06, color="#1f77b4")
                _ax.fill_between([100, _xhi], _ylo, 100, alpha=0.06, color="#ff7f0e")
                _ax.fill_between([_xlo, 100], _ylo, 100, alpha=0.06, color="#d62728")

                _ax.axhline(100, color="#888", lw=0.7, ls="--", alpha=0.5)
                _ax.axvline(100, color="#888", lw=0.7, ls="--", alpha=0.5)

                _lbl = dict(fontsize=9, alpha=0.35, weight="bold")
                _ax.text(_xhi - _pad * 0.15, _yhi - _pad * 0.15, "LEADING",
                         ha="right", va="top", color="#2ca02c", **_lbl)
                _ax.text(_xlo + _pad * 0.15, _yhi - _pad * 0.15, "IMPROVING",
                         ha="left", va="top", color="#1f77b4", **_lbl)
                _ax.text(_xhi - _pad * 0.15, _ylo + _pad * 0.15, "WEAKENING",
                         ha="right", va="bottom", color="#ff7f0e", **_lbl)
                _ax.text(_xlo + _pad * 0.15, _ylo + _pad * 0.15, "LAGGING",
                         ha="left", va="bottom", color="#d62728", **_lbl)

                _gc = {"PASS": "#2ca02c", "WATCH": "#ff7f0e",
                       "CAUTION": "#d62728", "BLOCKED": "#7f0000"}
                _dir_arrow = {"ENTERING": " *", "DEEPENING": "", "EXITING": "", "STABLE": ""}

                for _etf, _r, _m, _gate, _ddir in _pts:
                    _c = _gc.get(_gate, "#555")
                    _ax.scatter(_r, _m, color=_c, s=70, zorder=5,
                                edgecolors="white", linewidth=0.8)
                    _ax.annotate(
                        _etf + _dir_arrow.get(_ddir, ""),
                        (_r, _m), textcoords="offset points",
                        xytext=(6, 4), fontsize=7, fontweight="bold", color=_c,
                    )

                _ax.set_xlabel("RS-Ratio vs SPY", fontsize=8)
                _ax.set_ylabel("RS-Momentum", fontsize=8)
                _ax.set_title("Relative Rotation Graph", fontsize=10, fontweight="bold", pad=6)
                _ax.set_xlim(_xlo, _xhi)
                _ax.set_ylim(_ylo, _yhi)
                _ax.tick_params(labelsize=7)
                _fig.tight_layout(pad=1.0)
                st.pyplot(_fig, use_container_width=True)
                plt.close(_fig)

        # ── Macro Weather + Gate Summary (right) ──
        with _macro_col:
            _mw = sl.get("macro_weather", {})
            if _mw:
                st.markdown("##### Macro Weather")
                _instr = [
                    ("Rates", "TLT", "tlt_direction", "tlt_roc5"),
                    ("Dollar", "UUP", "uup_direction", "uup_roc5"),
                    ("Credit", "HYG", "hyg_direction", "hyg_roc5"),
                    ("Breadth", "IWM", "iwm_direction", "iwm_roc5"),
                ]
                _arrows = {"RISING": "**▲**", "FALLING": "**▼**", "FLAT": "▸"}
                _md_rows = []
                for _lbl, _tk, _dk, _rk in _instr:
                    _dir = _mw.get(_dk, "FLAT")
                    _roc = _mw.get(_rk, 0.0)
                    _ar = _arrows.get(_dir, "▸")
                    _md_rows.append(f"| {_lbl} ({_tk}) | {_ar} {_dir} | {_roc:+.1f}% |")
                st.markdown(
                    "| Instrument | Direction | 5d ROC |\n"
                    "| :--- | :---: | ---: |\n"
                    + "\n".join(_md_rows)
                )
                _desc = _mw.get("regime_description", "")
                if _desc:
                    st.caption(_desc)
            else:
                st.info("Macro weather data not available — run the pipeline.")

            # Gate summary
            _gate_counts: dict[str, int] = {}
            for _d in srm_detail.values():
                _g = _d.get("entry_gate", "WATCH")
                _gate_counts[_g] = _gate_counts.get(_g, 0) + 1
            st.markdown("##### Entry Gate")
            _gate_parts = []
            for _gk in ("PASS", "WATCH", "CAUTION", "BLOCKED"):
                _gn = _gate_counts.get(_gk, 0)
                if _gn > 0:
                    _gate_parts.append(f"{_gk}: **{_gn}**")
            st.markdown(" · ".join(_gate_parts) if _gate_parts else "No gate data")

            # Legend
            st.caption("Dot color = entry gate: green PASS · orange WATCH · red CAUTION/BLOCKED")

    # ── SRM Table ──
    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}
    srm_rows = []
    for etf, d in sorted(srm_detail.items(), key=lambda x: grade_order.get(x[1].get("grade", "WATCH"), 3)):
        roc20 = d.get("roc20", 0)
        roc5 = d.get("roc5", 0)
        row = {
            "Sector": _sector_label(etf),
            "Grade": d.get("grade", "---"),
            "Action state": d.get("trend_state", "---"),
            "RRG": d.get("rrg_quadrant", "---"),
            "RRG Dir": d.get("rrg_direction", "---"),
            "Macro": d.get("macro_headwind_flag", "---"),
            "Gate": d.get("entry_gate", "---"),
            "20d%": _fmt(roc20, "+.1f"),
            "5d%": _fmt(roc5, "+.1f"),
        }
        srm_rows.append(row)
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
            betas[tk] = {30: r.get("beta_30d"), 60: r.get("beta_60d")}
            dsl[tk] = {
                "entry": r.get("entry"),
                "stop": r.get("dsl_stop"),
                "risk": r.get("dsl_risk"),
                "tp_1r": r.get("dsl_tp_1r"),
                "tp_2r": r.get("dsl_tp_2r"),
                "tp_3r": r.get("dsl_tp_3r"),
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
# GICS sector gaps — the RAG-maintenance panel. Lists universe tickers with no
# sector mapping (blank gics_sector) and probes FMP so the PM can fill them.
# ---------------------------------------------------------------------------
with st.expander("🗂️ GICS sector gaps (RAG maintenance)", expanded=False):
    from src.data.sector_mapper import (
        get_sector_map_gaps, probe_profiles, add_sector_mappings,
    )
    _gaps = get_sector_map_gaps()
    if not _gaps:
        st.success("No sector-map gaps — every universe ticker has a GICS ETF. ✓")
    else:
        st.caption(
            f"**{len(_gaps)} ticker(s)** have a blank GICS sector. Fill them in the "
            "canonical `sector_map.json` (the RAG). Plain list below; click **Probe "
            "FMP** to get each name's sector/industry + a suggested ETF."
        )
        st.code(" ".join(_gaps), language=None)

        if st.button("Probe FMP for these blanks", key="sector_probe_btn",
                     disabled=(CLOUD_MODE and not FMP_KEY_SET)):
            with st.spinner(f"Fetching FMP profiles for {len(_gaps)} ticker(s)…"):
                st.session_state["_sector_probe"] = probe_profiles(_gaps)

        _probe = st.session_state.get("_sector_probe")
        if _probe:
            _pdf = pd.DataFrame(_probe)
            st.dataframe(_pdf, use_container_width=True, hide_index=True)

            # Paste-ready JSON of the auto-mappable rows (FMP sector → ETF).
            _auto = {r["ticker"]: r["suggested_etf"] for r in _probe if r["suggested_etf"]}
            _manual = [r["ticker"] for r in _probe if not r["suggested_etf"]]
            if _auto:
                st.caption(f"✅ {len(_auto)} auto-mappable — paste into `sector_map.json`:")
                import json as _json
                st.code(_json.dumps(_auto, indent=2, sort_keys=True), language="json")
                if not CLOUD_MODE:
                    if st.button(f"Merge {len(_auto)} into sector_map.json",
                                 key="sector_merge_btn"):
                        add_sector_mappings(_auto)
                        st.success(f"Merged {len(_auto)} mappings. "
                                   "Re-run the pipeline + export to publish to Drive.")
                        st.session_state.pop("_sector_probe", None)
                        st.rerun()
            if _manual:
                st.caption(
                    f"⚠️ {len(_manual)} need a manual ETF call (FMP sector didn't map "
                    "cleanly — e.g. 'Commercial services' → XLK):"
                )
                st.code(" ".join(_manual), language=None)

# ---------------------------------------------------------------------------
# Export-driven tables: the sections below render the EXACT export records
# (the AIC schema), so the screen always matches the JSON the committee reads.
# Out-of-scope fields (disposition, dsl_shares, atr_1h, …) are absent from the
# export, so they simply don't appear.
# ---------------------------------------------------------------------------
_ex = load_export() or {}

_EXPORT_COL_ORDER = [
    "rank", "ticker", "source", "pe", "on_longlist",
    "gics_sector", "gics_sector_name", "gics_gate", "sector_corr", "sector_corr_class",
    "sc_momentum", "sc_momentum_raw", "ptrs", "pipe_rank", "floor",
    "flow", "energy", "structure", "mp", "mp_state", "elder", "elder_5d",
    "beta_30d", "beta_60d", "rvol", "rs_spy_20d", "sma_distance_pct",
    "entry", "stop", "dsl_stop", "dsl_risk", "dsl_rr_pct",
    "dsl_atr_ratio", "atr_14d", "dsl_tp_1r", "dsl_tp_2r", "dsl_tp_3r",
    "rr_est", "rr_tp1", "rr_tp2", "rr_tp3", "held", "fib", "rank_explain",
]


def _export_table(records):
    """DataFrame of export records with the full uniform schema, ordered."""
    if not records:
        return pd.DataFrame()
    edf = pd.DataFrame(records)
    if "elder_5d" in edf.columns:
        edf["elder_5d"] = edf["elder_5d"].apply(
            lambda v: ",".join(str(int(x)) for x in v) if isinstance(v, list)
            else ("" if v is None else v)
        )
    if "fib" in edf.columns:
        edf["fib"] = edf["fib"].apply(
            lambda v: "✓" if isinstance(v, dict) else ("" if v is None else v)
        )
    cols = [c for c in _EXPORT_COL_ORDER if c in edf.columns]
    cols += [c for c in edf.columns if c not in cols]
    return edf[cols]


# ---------------------------------------------------------------------------
# Held positions (from the daily PTJ) — the trade + AQE's current engine read
# ---------------------------------------------------------------------------
_held = _ex.get("held_positions") or []
if _held:
    st.subheader(f"Held positions ({len(_held)})")
    st.caption(
        "From the latest trade journal (PTJ) on Drive. `entry`/`qty`/`held_sl`/"
        "`unreal_usd` = your trade; `sc_momentum`/`mp_state`/`flow…`/`dsl_*` = "
        "what the engine says about it now."
    )
    _HELD_COLS = [
        "ticker", "qty", "entry", "live_px", "unreal_usd", "held_sl", "held_tp1",
        "held_tp2", "trade_date", "ptj_sector", "gics_gate",
        "sc_momentum", "ptrs", "pipe_rank", "flow", "energy", "structure", "mp",
        "mp_state", "elder", "beta_30d", "beta_60d", "rvol", "rs_spy_20d",
        "sma_distance_pct", "sector_corr", "dsl_stop", "dsl_tp_1r",
        "dsl_tp_2r", "dsl_tp_3r", "dsl_atr_ratio", "atr_14d",
        "rr_tp1", "rr_tp2", "rr_tp3", "notes",
    ]
    _hdf = pd.DataFrame(_held)
    _hcols = [c for c in _HELD_COLS if c in _hdf.columns]
    _hcols += [c for c in _hdf.columns if c not in _hcols and not c.startswith("_")]
    st.dataframe(_hdf[_hcols], use_container_width=True, hide_index=True)
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
    pe_rows = []
    for i, sig in enumerate(pe_signals, 1):
        ticker = sig.get("ticker", "")
        eng = sig.get("engines", {})
        lvl = sig.get("levels", {})
        sc_val = sig.get("sc_momentum") or round(
            eng.get("flow", 0) * 0.30 + eng.get("energy", 0) * 0.30
            + eng.get("structure", 0) * 0.20 + eng.get("mp", 0) * 0.20, 1
        )
        floor = min(eng.get("flow", 0), eng.get("energy", 0),
                    eng.get("structure", 0), eng.get("mp", 0))
        ptrs_val = _quick_ptrs(sc_val, ticker, _sector_grades)
        dsl = _dsl.get(ticker, {})
        pe_rows.append({
            "#": i,
            "Ticker": ticker,
            "Sector": _ticker_sector(ticker),
            "Score": _fmt(sc_val, ".1f"),
            "Raw": _fmt(sig.get("sc_momentum_raw", sc_val), ".1f"),
            "PTRS": _fmt(ptrs_val, ".1f"),
            "PipeRk": _fmt(sig.get("pipe_rank"), ".1f"),
            "Floor": _fmt(floor, ".1f"),
            "Beta30": _fmt((_betas.get(ticker) or {}).get(30), ".2f"),
            "Beta60": _fmt((_betas.get(ticker) or {}).get(60), ".2f"),
            "Flow": _fmt(eng.get("flow"), ".0f"),
            "Energy": _fmt(eng.get("energy"), ".0f"),
            "Struct": _fmt(eng.get("structure"), ".0f"),
            "MP": _fmt(eng.get("mp"), ".0f"),
            "Elder": _fmt(eng.get("elder"), ".1f"),
            "Elder5d": _elder5_str(_elder5.get(ticker)),
            "Entry": _fmt(dsl.get("entry", lvl.get("entry")), ".2f"),
            "DSL": _fmt(dsl.get("stop", lvl.get("stop")), ".2f"),
            "TP 1/2/3": _tp_str(dsl, lvl),
            "Distance to SL (%)": _fmt(dsl.get("rr_pct"), ".1f"),
            "R/R": _fmt(dsl.get("rr_est"), ".1f"),
            "ATR Width": _fmt(dsl.get("dsl_atr_ratio"), ".2f"),
            "Fib": _fib_str(dsl.get("fib")),
        })
    st.dataframe(_export_table(_ex.get("edge_list")), use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# 4. Longlist (Aggregate + PE)
# ---------------------------------------------------------------------------
st.subheader("Longlist")

active_recipe = sl.get("active_recipe", {})
recipe_str = _recipe_label(active_recipe)
st.caption(f"Aggregate recipe: {recipe_str}")
st.caption(
    "Full export schema (exactly what AIC receives). DSL bracket: "
    "`dsl_stop` = SL, `dsl_tp_1r/2r/3r` = targets, `rr_tp1/2/3` = R:R to each, "
    "`dsl_atr_ratio` = stop width in ATRs."
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
            "Score": _fmt(rm.get("sc_momentum"), ".1f"),
            "Raw": _fmt(rm.get("sc_momentum_raw"), ".1f"),
            "PTRS": _fmt(ptrs_val, ".1f"),
            "PipeRk": _fmt(rm.get("pipe_rank"), ".1f"),
            "Floor": _fmt(floor, ".1f"),
            "Beta30": _fmt((_betas.get(ticker) or {}).get(30), ".2f"),
            "Beta60": _fmt((_betas.get(ticker) or {}).get(60), ".2f"),
            "Flow": _fmt(eng.get("flow"), ".0f"),
            "Energy": _fmt(eng.get("energy"), ".0f"),
            "Struct": _fmt(eng.get("structure"), ".0f"),
            "MP": _fmt(eng.get("mp"), ".0f"),
            "Elder": _fmt(eng.get("elder"), ".1f"),
            "Elder5d": _elder5_str(_elder5.get(ticker)),
            "Entry": _fmt(dsl.get("entry", lvl.get("entry")), ".2f"),
            "DSL": _fmt(dsl.get("stop", lvl.get("stop")), ".2f"),
            "TP 1/2/3": _tp_str(dsl, lvl),
            "Distance to SL (%)": _fmt(dsl.get("rr_pct"), ".1f"),
            "R/R": _fmt(dsl.get("rr_est"), ".1f"),
            "ATR Width": _fmt(dsl.get("dsl_atr_ratio"), ".2f"),
            "Fib": _fib_str(dsl.get("fib")),
        })

    st.dataframe(_export_table(_ex.get("longlist")), use_container_width=True, hide_index=True)

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
            "Beta60": _fmt((_betas.get(ticker) or {}).get(60), ".2f"),
                "Flow": _fmt(float(row.get("flow_100", 0)), ".0f"),
                "Energy": _fmt(float(row.get("energy_100", 0)), ".0f"),
                "Struct": _fmt(float(row.get("structure_100", 0)), ".0f"),
                "MP": _fmt(float(row.get("mp_100", 0)), ".0f"),
                "Elder": _fmt(float(row.get("elder_score", 0)), ".1f"),
                "Elder5d": _elder5_str(_elder5.get(ticker)),
                "Entry": _fmt(dsl.get("entry"), ".2f"),
                "DSL": _fmt(dsl.get("stop"), ".2f"),
                "TP 1/2/3": _tp_str(dsl),
                "Distance to SL (%)": _fmt(dsl.get("rr_pct"), ".1f"),
                "R/R": _fmt(dsl.get("rr_est"), ".1f"),
                "ATR Width": _fmt(dsl.get("dsl_atr_ratio"), ".2f"),
                "Fib": _fib_str(dsl.get("fib")),
            })

        _wl_recs = [r for r in (_ex.get("watchlist") or [])
                    if (r.get("sc_momentum_raw") or 0) >= scan_threshold]
        st.dataframe(_export_table(_wl_recs), use_container_width=True, hide_index=True)
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

def _aic_blurb(r: dict, regime: dict, srm_detail: dict, sector_grades: dict) -> str:
    """Build a ready-to-paste AIC deliberation prompt from an ad-hoc score result."""
    tk = r["ticker"]
    lv = r.get("levels") or {}
    sc = r.get("sc_momentum")
    raw = r.get("sc_momentum_raw")
    gate = "PASS" if r.get("gate_pass") else "CAPPED"

    sm = load_sector_map()
    etf = sm.get(tk, "")
    sector_name = ETF_TO_NAME.get(etf, etf) if etf else "Unknown"
    sd = srm_detail.get(etf, {})
    grade = sd.get("grade", "—")
    rrg_q = sd.get("rrg_quadrant", "—")
    macro_f = sd.get("macro_headwind_flag", "—")
    entry_gate = sd.get("entry_gate", "—")

    ptrs = _quick_ptrs(sc, tk, sector_grades) if sc is not None else 0.0

    regime_lvl = regime.get("level", "—")
    vix = regime.get("vix", 0)

    lines = [
        f"AIC — {tk} (ad-hoc scan, {r.get('as_of', '?')}):",
        f"SC {_fmt(sc, '.1f')}/raw {_fmt(raw, '.1f')} gate {gate} · "
        f"PTRS {_fmt(ptrs, '.1f')} · MP {r.get('mp_state') or '—'}",
        f"Flow {_fmt(r.get('flow'), '.0f')} · Energy {_fmt(r.get('energy'), '.0f')} · "
        f"Structure {_fmt(r.get('structure'), '.0f')} · MP {_fmt(r.get('mp'), '.0f')} · "
        f"Elder {_fmt(r.get('elder'), '.1f')} (5d: {_elder5_str(r.get('elder_5d'))}) · "
        f"BQ {_fmt(r.get('bq'), '.0f')}",
        f"DSL stop {_fmt(lv.get('stop'), '.2f')} · "
        f"TP {_fmt(lv.get('tp_1r'), '.2f')}/{_fmt(lv.get('tp_2r'), '.2f')}/{_fmt(lv.get('tp_3r'), '.2f')} · "
        f"R:R {_fmt(lv.get('rr_est'), '.1f')} · ATR ratio {_fmt(lv.get('dsl_atr_ratio'), '.2f')} · "
        f"beta {_fmt(r.get('beta_60d'), '.2f')}",
        f"Sector: {sector_name} ({etf}) {grade} · RRG {rrg_q} · Macro {macro_f} · Gate {entry_gate}",
        f"Regime: VIX {_fmt(vix, '.1f')} ({regime_lvl}) · "
        f"PipeRank {_fmt(r.get('pipe_rank'), '.1f')}",
        "Advise: entry decision + size per PTRS x regime. Charter v1.9.3.",
    ]
    return "\n".join(lines)


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
                "Beta60": _fmt(r.get("beta_60d"), ".2f"),
                "Entry": _fmt(lv.get("entry"), ".2f"),
                "DSL": _fmt(lv.get("stop"), ".2f"),
                "TP 1/2/3": _tp_str(lv),
                "Distance to SL (%)": _fmt(lv.get("rr_pct"), ".1f"),
                "R/R": _fmt(lv.get("rr_est"), ".1f"),
                "ATR Width": _fmt(lv.get("dsl_atr_ratio"), ".2f"),
                "Fib": _fib_str(lv.get("fib")),
            })
        st.dataframe(pd.DataFrame(_adhoc_rows), use_container_width=True, hide_index=True)

        # AIC deliberation blurbs — one per scored ticker
        st.markdown("##### AIC Deliberation Prompt")
        st.caption("Copy and paste to AIC (Claude) for entry deliberation.")
        _regime = sl.get("regime", {})
        _srm_d = sl.get("srm_detail", {})
        for r in _ok:
            _blurb = _aic_blurb(r, _regime, _srm_d, _sector_grades)
            st.code(_blurb, language=None)

    for r in _err:
        st.warning(f"**{r['ticker']}** — {r['error']}")
