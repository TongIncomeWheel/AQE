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
    table_with_copy,
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


def _export_file_info():
    """(bytes, caption) for the local export JSON, or None if absent.

    `export_to_drive()` writes this local working copy on every run *before*
    attempting the Drive upload, so it exists even when Drive auth is broken
    ("Local only"). This powers the download-to-browser fallback.
    """
    p = OUTPUT_DIR / "aqe_daily_export.json"
    if not p.exists():
        return None
    try:
        raw = p.read_bytes()
    except Exception:  # noqa: BLE001
        return None
    when = "unknown"
    try:
        import json as _json
        meta = _json.loads(raw)
        when = meta.get("exported_at") or meta.get("date") or "unknown"
    except Exception:  # noqa: BLE001
        pass
    return raw, f"exported {when} · {len(raw) / 1024:.0f} KB"

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
        from src.data.persist import (
            save_snapshot, load_snapshot, snapshot_status,
            build_snapshot_bytes, restore_snapshot_bytes,
        )

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

        # ---- Local-PC fallback (works when Drive auth is down) ----
        st.divider()
        st.caption("**Local PC fallback** — save/restore the snapshot via your "
                   "browser, no Google Drive needed.")
        if st.button("📦 Build snapshot for download", use_container_width=True,
                     help="Zip the runtime parquets + export in memory so you "
                          "can download it to your PC. Drive-independent."):
            with st.spinner("Building snapshot…"):
                _b = build_snapshot_bytes()
            if _b.get("ok"):
                st.session_state["_snap_blob"] = _b["blob"]
                st.session_state["_snap_caption"] = (
                    f"{len(_b['files'])} files · {_b['bytes'] / 1e6:.1f} MB · "
                    f"built {_b['saved_at']}")
            else:
                st.session_state.pop("_snap_blob", None)
                st.error(_b.get("reason"))
        if st.session_state.get("_snap_blob"):
            st.download_button(
                "⬇️ Download snapshot .zip",
                data=st.session_state["_snap_blob"],
                file_name="aqe_state_snapshot.zip",
                mime="application/zip",
                use_container_width=True,
            )
            st.caption(f"Ready · {st.session_state.get('_snap_caption', '')}")

        _snap_up = st.file_uploader(
            "Restore from a snapshot .zip on your PC", type=["zip"],
            key="snap_upload",
            help="Upload a previously downloaded aqe_state_snapshot.zip to "
                 "restore the panel/scores/export without re-running the pipeline.")
        if _snap_up is not None and st.button(
                "📥 Restore from this file", use_container_width=True):
            with st.spinner("Restoring snapshot…"):
                _r = restore_snapshot_bytes(_snap_up.getvalue())
            if _r.get("ok"):
                st.cache_data.clear()
                st.success(f"Restored {_r['count']} files. Reloading…")
                st.rerun()
            else:
                st.error(f"Restore failed: {_r.get('reason')}")

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

    # ---- Export + local-download fallback (all modes) ----------------
    st.markdown("**📤 Export**")
    if st.button("Build export → Drive", use_container_width=True,
                 help="Rebuild aqe_daily_export.json, save the local working "
                      "copy, and upload to the pinned Google Drive folder when "
                      "Drive OAuth is healthy."):
        from src.data.drive_sync import export_to_drive
        with st.spinner("Building export…"):
            st.session_state["_export_result"] = export_to_drive()

    _xr = st.session_state.get("_export_result")
    if _xr:
        _xs = _xr.get("status")
        if _xs == "ok":
            st.success(f"Saved to Drive ✓ — {_xr.get('exported_at') or _xr.get('date')}")
        elif _xs == "partial":
            st.warning("Drive upload failed — local copy saved. Use **Download "
                       "export JSON** below as the fallback.")
            st.caption(f"Reason: {_xr.get('reason')}")
        else:
            st.info(_xr.get("reason", "Nothing to export yet."))

    # Always-available browser download — the fallback when Drive sync is down.
    _xi = _export_file_info()
    st.download_button(
        "⬇️ Download export JSON",
        data=(_xi[0] if _xi else b""),
        file_name="aqe_daily_export.json",
        mime="application/json",
        use_container_width=True,
        disabled=_xi is None,
        help="Save aqe_daily_export.json to your computer (your browser asks "
             "where to put it). Works even when Google Drive sync is broken — "
             "it's the exact file that would be pushed to Drive.",
    )
    st.caption(_xi[1] if _xi else
               "No export file yet — build it above or run the daily pipeline.")

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


def _rrg_phrase(quadrant: str | None, direction: str | None) -> str:
    """Explicit RRG state: combine quadrant + motion into one phrase that says
    exactly what is entering/exiting which quadrant, e.g. 'Exiting LEADING'.

    ENTERING = just crossed into this quadrant; DEEPENING = rotating further from
    the SPY=100 center (rotation strengthening); EXITING = rotating back toward
    center (rotation fading, about to leave); STABLE = holding position.
    """
    q = (quadrant or "").upper()
    if not q or q in ("---", "NO_DATA", "—"):
        return "—"
    verb = {
        "ENTERING": "Entering",
        "DEEPENING": "Deepening in",
        "EXITING": "Exiting",
        "STABLE": "Holding in",
    }.get((direction or "").upper(), "In")
    return f"{verb} {q}"


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
    if sup is None and tgt is None:
        return "---"
    if tgt is None:                        # flat export carries supports only
        return _fmt(sup, ".2f")
    return f"{_fmt(sup, '.2f')} / {_fmt(tgt, '.2f')}"


def _nested_fib_from_export(r: dict) -> dict | None:
    """Rebuild the nested fib shape the UI helpers expect from the flat export
    fib_* fields (the export schema was flattened in DSG-18)."""
    rets = {}
    for _key, _suffix in (("0.236", "236"), ("0.382", "382"), ("0.5", "500"),
                          ("0.618", "618"), ("0.786", "786")):
        _v = r.get(f"fib_{_suffix}")
        if _v is not None:
            rets[_key] = _v
    if not rets and r.get("fib_swing_low") is None:
        return None
    return {
        "swing_low": r.get("fib_swing_low"),
        "swing_high": r.get("fib_swing_high"),
        "retracements": rets,
        "extensions": {},
    }


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


@st.cache_data(ttl=600, show_spinner=False)
def _rrg_tail_backfill(_hash: str) -> tuple[dict, dict]:
    """({etf: tail}, {basket: tail}) computed live from the price panel.

    Back-fill for the RRG charts when shortlist.json predates the tail feature
    (no `rrg_history`): the tail is a deterministic function of the panel, so we
    recompute it on demand instead of forcing a full pipeline rerun. Empty when
    the panel isn't present (e.g. a cold Streamlit container).
    """
    sector_tails: dict[str, list] = {}
    basket_tails: dict[str, list] = {}
    try:
        if not PANEL_DAILY.exists():
            return sector_tails, basket_tails
        import numpy as np
        from src.engines import srm

        panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "close"])
        panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
        spy = (panel[panel["ticker"] == "SPY"].sort_values("date")["close"]
               .astype(float).to_numpy())
        if spy.size:
            for _etf in srm.GICS_ETFS:
                _d = panel[panel["ticker"] == _etf].sort_values("date")
                if not _d.empty:
                    sector_tails[_etf] = srm.compute_rrg_tail(
                        _d["close"].astype(float).to_numpy(), spy)
        # Baskets: reuse the canonical grader (it already emits rrg_history);
        # parent-grade capping is irrelevant to the tail, so pass {}.
        try:
            _baskets = srm.grade_thematic_baskets(panel, {})
            basket_tails = {k: (v.get("rrg_history") or [])
                            for k, v in _baskets.items()}
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    return sector_tails, basket_tails


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
# Back-fill RRG tails from the panel when shortlist.json predates the feature.
_sector_tail_bf, _basket_tail_bf = _rrg_tail_backfill(
    file_hash(PANEL_DAILY) if PANEL_DAILY.exists() else "none")
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

            _all_pts = []
            for _etf, _d in srm_detail.items():
                _r = _d.get("rrg_rs_ratio")
                _m = _d.get("rrg_rs_momentum")
                if _r is not None and _m is not None:
                    _hist = _d.get("rrg_history") or _sector_tail_bf.get(_etf) or []
                    _all_pts.append((_etf, _r, _m, _d.get("entry_gate", "WATCH"),
                                     _d.get("rrg_direction", "STABLE"), _hist))

            _etf_opts = [p[0] for p in _all_pts]
            _sel_etfs = st.multiselect(
                "Sectors to plot", _etf_opts, default=_etf_opts,
                key="rrg_sector_filter",
                help="Trim the RRG to just the sectors you want when it gets "
                     "crowded. The dotted tail traces each sector's last 5 days "
                     "(direction of travel); the dot is today.",
            )
            _pts = [p for p in _all_pts if p[0] in _sel_etfs] or _all_pts

            if _pts:
                _ratios = ([p[1] for p in _pts]
                           + [h["rs_ratio"] for p in _pts for h in p[5]])
                _moms = ([p[2] for p in _pts]
                         + [h["rs_momentum"] for p in _pts for h in p[5]])
                _pad = max(1.5, (max(_ratios) - min(_ratios)) * 0.2,
                           (max(_moms) - min(_moms)) * 0.2)
                _xlo = min(min(_ratios), 98) - _pad
                _xhi = max(max(_ratios), 102) + _pad
                _ylo = min(min(_moms), 98) - _pad
                _yhi = max(max(_moms), 102) + _pad

                _fig, _ax = plt.subplots(figsize=(5.4, 2.1))

                _ax.fill_between([100, _xhi], 100, _yhi, alpha=0.06, color="#2ca02c")
                _ax.fill_between([_xlo, 100], 100, _yhi, alpha=0.06, color="#1f77b4")
                _ax.fill_between([100, _xhi], _ylo, 100, alpha=0.06, color="#ff7f0e")
                _ax.fill_between([_xlo, 100], _ylo, 100, alpha=0.06, color="#d62728")

                _ax.axhline(100, color="#888", lw=0.7, ls="--", alpha=0.5)
                _ax.axvline(100, color="#888", lw=0.7, ls="--", alpha=0.5)

                _lbl = dict(fontsize=6, alpha=0.35, weight="bold")
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

                for _etf, _r, _m, _gate, _ddir, _hist in _pts:
                    _c = _gc.get(_gate, "#555")
                    if len(_hist) >= 2:                       # 5-day tail
                        _hx = [h["rs_ratio"] for h in _hist]
                        _hy = [h["rs_momentum"] for h in _hist]
                        _ax.plot(_hx, _hy, ls=":", lw=0.9, color=_c,
                                 alpha=0.55, zorder=4)
                        _ax.scatter(_hx[0], _hy[0], s=5, color=_c,
                                    alpha=0.4, zorder=4)     # tail origin
                    _ax.scatter(_r, _m, color=_c, s=28, zorder=5,
                                edgecolors="white", linewidth=0.6)
                    _ax.annotate(
                        _etf + _dir_arrow.get(_ddir, ""),
                        (_r, _m), textcoords="offset points",
                        xytext=(4, 3), fontsize=5, fontweight="bold", color=_c,
                    )

                _ax.set_xlabel("RS-Ratio vs SPY", fontsize=6)
                _ax.set_ylabel("RS-Momentum", fontsize=6)
                _ax.set_title("Relative Rotation Graph", fontsize=7, fontweight="bold", pad=3)
                _ax.set_xlim(_xlo, _xhi)
                _ax.set_ylim(_ylo, _yhi)
                _ax.tick_params(labelsize=5)
                _fig.tight_layout(pad=0.5)
                st.pyplot(_fig, use_container_width=False)
                plt.close(_fig)

                # Legend: ticker → sector name + asterisk meaning
                _leg = " · ".join(
                    f"**{_etf}** {_sector_label(_etf)}"
                    + ("\\*" if _dir_arrow.get(_ddir, "") else "")
                    for _etf, _r, _m, _gate, _ddir, _hist in sorted(_pts)
                )
                st.caption(_leg)
                st.caption(
                    "Dotted **tail = last 5 days' path** (small dot = 5 days ago, "
                    "big dot = today). \\* = sector just **entering** its quadrant "
                    "(a fresh rotation). Axes are normalised to SPY = 100: right of "
                    "centre = outperforming, above centre = momentum improving."
                )

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
                    ("Gold", "GLD", "gld_direction", "gld_roc5"),
                    ("Copper", "CPER", "cper_direction", "cper_roc5"),
                    ("Oil", "USO", "uso_direction", "uso_roc5"),
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
                # Copper/Gold ratio — the headline growth+rates tell (Druckenmiller)
                _cg_dir = _mw.get("copper_gold_direction", "FLAT")
                if _cg_dir != "FLAT":
                    _cg_roc = _mw.get("copper_gold_roc5", 0.0)
                    _cg_ar = _arrows.get(_cg_dir, "▸")
                    _cg_tag = ("reflation / risk-on" if _cg_dir == "RISING"
                               else "deflation / risk-off")
                    st.markdown(
                        f"**Copper/Gold:** {_cg_ar} {_cg_dir} ({_cg_roc:+.1f}%) "
                        f"— *{_cg_tag}*"
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
            "Rotation (RRG)": _rrg_phrase(d.get("rrg_quadrant"), d.get("rrg_direction")),
            "Macro": d.get("macro_headwind_flag", "---"),
            "Gate": d.get("entry_gate", "---"),
            "20d%": _fmt(roc20, "+.1f"),
            "5d%": _fmt(roc5, "+.1f"),
        }
        srm_rows.append(row)
    df_srm = pd.DataFrame(srm_rows)
    table_with_copy(df_srm, key="srm_table")
    st.caption(
        "**Rotation (RRG)** vs SPY: *Entering* = just crossed into that quadrant · "
        "*Deepening in* = rotating further out (strengthening) · *Exiting* = "
        "rotating back toward centre (fading, about to leave) · *Holding in* = stable. "
        "Quadrants: LEADING (strong & rising) · IMPROVING (weak but rising) · "
        "WEAKENING (strong but falling) · LAGGING (weak & falling)."
    )
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

# ---------------------------------------------------------------------------
# 2b. Thematic Rotation — the SAME SRM/RRG method on deterministic basket
#     constituent sets (a context/sentiment layer, SEPARATE from GICS sectors).
# ---------------------------------------------------------------------------
st.subheader("Thematic Rotation")
st.caption(
    "Catalyst baskets graded by the SRM method (equal-weight constituent index, "
    "capped at the parent GICS grade). A context/sentiment read — these names are "
    "**not** added to the scan universe."
)

_thematic = sl.get("thematic_baskets", {})
if _thematic:
    _basket_short = {
        "Infra_Power": "InfraPwr", "Space_eVTOL": "Space",
        "AI_Infrastructure": "AI-Infra", "Semiconductors": "Semis",
        "Cybersecurity": "Cyber", "Defense_Tech": "Defense",
        "Crypto_Digital": "Crypto",
    }
    _grade_color = {
        "DEPLOY": "#2ca02c", "HOLD": "#1f9e5a", "TURNING": "#ff7f0e",
        "WATCH": "#d4a017", "AVOID": "#d62728", "NO_DATA": "#999999",
    }

    _t_has_rrg = any(d.get("rrg_rs_ratio") is not None for d in _thematic.values())
    if _t_has_rrg:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _all_tpts = []
        for _b, _d in _thematic.items():
            _r = _d.get("rrg_rs_ratio")
            _m = _d.get("rrg_rs_momentum")
            if _r is not None and _m is not None:
                _hist = _d.get("rrg_history") or _basket_tail_bf.get(_b) or []
                _all_tpts.append((_b, _r, _m, _d.get("grade", "NO_DATA"),
                                  _d.get("rrg_direction", "STABLE"), _hist))

        _b_opts = [p[0] for p in _all_tpts]
        _sel_b = st.multiselect(
            "Baskets to plot", _b_opts, default=_b_opts,
            key="rrg_thematic_filter",
            format_func=lambda b: _basket_short.get(b, b),
            help="Trim the thematic RRG when crowded. The dotted tail traces each "
                 "basket's last 5 days (direction of travel); the dot is today.",
        )
        _tpts = [p for p in _all_tpts if p[0] in _sel_b] or _all_tpts

        if _tpts:
            _ratios = ([p[1] for p in _tpts]
                       + [h["rs_ratio"] for p in _tpts for h in p[5]])
            _moms = ([p[2] for p in _tpts]
                     + [h["rs_momentum"] for p in _tpts for h in p[5]])
            _pad = max(1.5, (max(_ratios) - min(_ratios)) * 0.2,
                       (max(_moms) - min(_moms)) * 0.2)
            _xlo, _xhi = min(min(_ratios), 98) - _pad, max(max(_ratios), 102) + _pad
            _ylo, _yhi = min(min(_moms), 98) - _pad, max(max(_moms), 102) + _pad

            _fig, _ax = plt.subplots(figsize=(5.4, 2.1))
            _ax.fill_between([100, _xhi], 100, _yhi, alpha=0.06, color="#2ca02c")
            _ax.fill_between([_xlo, 100], 100, _yhi, alpha=0.06, color="#1f77b4")
            _ax.fill_between([100, _xhi], _ylo, 100, alpha=0.06, color="#ff7f0e")
            _ax.fill_between([_xlo, 100], _ylo, 100, alpha=0.06, color="#d62728")
            _ax.axhline(100, color="#888", lw=0.7, ls="--", alpha=0.5)
            _ax.axvline(100, color="#888", lw=0.7, ls="--", alpha=0.5)

            _lbl = dict(fontsize=6, alpha=0.35, weight="bold")
            _ax.text(_xhi - _pad * 0.15, _yhi - _pad * 0.15, "LEADING",
                     ha="right", va="top", color="#2ca02c", **_lbl)
            _ax.text(_xlo + _pad * 0.15, _yhi - _pad * 0.15, "IMPROVING",
                     ha="left", va="top", color="#1f77b4", **_lbl)
            _ax.text(_xhi - _pad * 0.15, _ylo + _pad * 0.15, "WEAKENING",
                     ha="right", va="bottom", color="#ff7f0e", **_lbl)
            _ax.text(_xlo + _pad * 0.15, _ylo + _pad * 0.15, "LAGGING",
                     ha="left", va="bottom", color="#d62728", **_lbl)

            _dir_arrow = {"ENTERING": " *", "DEEPENING": "", "EXITING": "", "STABLE": ""}
            for _b, _r, _m, _grade, _ddir, _hist in _tpts:
                _c = _grade_color.get(_grade, "#555")
                if len(_hist) >= 2:                          # 5-day tail
                    _hx = [h["rs_ratio"] for h in _hist]
                    _hy = [h["rs_momentum"] for h in _hist]
                    _ax.plot(_hx, _hy, ls=":", lw=0.9, color=_c,
                             alpha=0.55, zorder=4)
                    _ax.scatter(_hx[0], _hy[0], s=5, color=_c,
                                alpha=0.4, zorder=4)         # tail origin
                _ax.scatter(_r, _m, color=_c, s=28, zorder=5,
                            edgecolors="white", linewidth=0.6)
                _ax.annotate(
                    _basket_short.get(_b, _b) + _dir_arrow.get(_ddir, ""),
                    (_r, _m), textcoords="offset points",
                    xytext=(4, 3), fontsize=5, fontweight="bold", color=_c,
                )

            _ax.set_xlabel("RS-Ratio vs SPY", fontsize=6)
            _ax.set_ylabel("RS-Momentum", fontsize=6)
            _ax.set_title("Thematic Relative Rotation Graph", fontsize=7,
                          fontweight="bold", pad=3)
            _ax.set_xlim(_xlo, _xhi)
            _ax.set_ylim(_ylo, _yhi)
            _ax.tick_params(labelsize=5)
            _fig.tight_layout(pad=0.5)
            st.pyplot(_fig, use_container_width=False)
            plt.close(_fig)
            st.caption(
                "Dot color = basket grade: green DEPLOY/HOLD · amber TURNING/WATCH · "
                "red AVOID · grey NO_DATA. Dotted **tail = last 5 days' path** "
                "(small dot = 5 days ago, big dot = today). \\* = basket just "
                "**entering** its quadrant. Axes normalised to SPY = 100."
            )

    # ── Thematic Table ──
    _grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3,
                    "AVOID": 4, "NO_DATA": 5}
    _trows = []
    for _b, _d in sorted(_thematic.items(),
                         key=lambda x: _grade_order.get(x[1].get("grade", "NO_DATA"), 5)):
        _trows.append({
            "Basket": _b.replace("_", " "),
            "Grade": _d.get("grade", "---"),
            "Raw": _d.get("raw_grade", "---"),
            "Parent": f'{_d.get("parent_gics", "—")} ({_d.get("parent_grade", "—")})',
            "Rotation (RRG)": _rrg_phrase(_d.get("rrg_quadrant"), _d.get("rrg_direction")),
            "20d%": _fmt(_d.get("roc20"), "+.1f"),
            "5d%": _fmt(_d.get("roc5"), "+.1f"),
            "Coverage": _d.get("coverage", "—"),
        })
    table_with_copy(pd.DataFrame(_trows), key="thematic_table")
    st.caption(
        "**Rotation (RRG)** vs SPY: *Entering* = just crossed into that quadrant · "
        "*Deepening in* = rotating further out (strengthening) · *Exiting* = "
        "rotating back toward centre (fading, about to leave) · *Holding in* = stable."
    )
else:
    st.info(
        "No thematic basket grades yet — run the daily pipeline to populate "
        "thematic rotation (grades + RRG)."
    )

# PTRS context — used by longlist and watchlist tables below
# PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
_sector_grades = sl.get("srm_detail", {})
_sector_map_raw = load_sector_map()  # {ticker: 'XLK'} for rank explainer

if CLOUD_MODE:
    # Re-hydrate the per-ticker level / beta / elder lookups from the export
    # JSON so the read-only deploy never touches the 137MB parquet files.
    _export = load_export() or {}

    def _rr_from_record(r: dict):
        """Per-name R:R for the display tables. `rr_est` was removed from the
        export (duplicate of structural_targets); derive it from the structural
        fields instead — optimal_stop's R:R to TP2, else the nearest structural
        target's R:R."""
        opt = r.get("optimal_stop")
        if isinstance(opt, dict) and opt.get("rr_tp2") is not None:
            return opt.get("rr_tp2")
        tgts = r.get("structural_targets") or []
        if tgts and isinstance(tgts[0], dict):
            return tgts[0].get("rr")
        return None

    def _build_cloud_lookups(export: dict) -> tuple[dict, dict, dict]:
        betas: dict[str, dict] = {}
        dsl: dict[str, dict] = {}
        elder5: dict[str, list] = {}
        rows = []
        for key in ("longlist", "elder_list"):   # the two AQE lists
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
                "rr_est": _rr_from_record(r),
                "fib":    _nested_fib_from_export(r),
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
    "coil_entry", "max_chase_tp2", "max_chase_tp3", "rr_tp2_at_coil", "rr_tp3_at_coil",
    "optimal_stop", "optimal_stop_exists", "structural_targets", "held", "rank_explain",
    "elder_pattern", "ecx_vwap_pos", "ecx_vwap_slope", "ecx_vol_trend",
    "ecx_vol_above20d", "ecx_up_dn_ratio", "ecx_vcp_label", "ecx_vcp_tight",
    "ecx_exhaustion",
]


def _flatten_elder_context(edf):
    """Expand the nested elder_context dict into readable ecx_* columns."""
    if "elder_context" not in edf.columns:
        return edf

    def g(ctx, *path):
        cur = ctx
        for k in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    ctxs = edf["elder_context"]
    edf["ecx_vwap_pos"] = ctxs.apply(lambda c: g(c, "vwap_5d", "position"))
    edf["ecx_vwap_slope"] = ctxs.apply(lambda c: g(c, "vwap_5d", "slope_5d"))
    edf["ecx_vol_trend"] = ctxs.apply(lambda c: g(c, "volume", "vol_trend_5d"))
    edf["ecx_vol_above20d"] = ctxs.apply(lambda c: g(c, "volume", "vol_above_20d_avg"))
    edf["ecx_up_dn_ratio"] = ctxs.apply(lambda c: g(c, "volume", "up_bar_vol_ratio"))
    edf["ecx_vcp_label"] = ctxs.apply(lambda c: g(c, "vcp", "vcp_label"))
    edf["ecx_vcp_tight"] = ctxs.apply(lambda c: g(c, "vcp", "vcp_tightness_pct"))
    edf["ecx_exhaustion"] = ctxs.apply(lambda c: g(c, "exhaustion_check", "exhaustion_flag"))
    return edf.drop(columns=["elder_context"])


def _export_table(records):
    """Clean, readable DataFrame of export records (scalar columns only).

    Nested objects (structural_levels/targets, optimal_stop, fib) and all-empty
    columns are dropped so the grid stays tidy — full nested data lives in the
    export JSON / the Pricer. elder_context is flattened to ecx_* columns.
    """
    if not records:
        return pd.DataFrame()
    edf = pd.DataFrame(records)
    edf = _flatten_elder_context(edf)
    if "elder_5d" in edf.columns:
        edf["elder_5d"] = edf["elder_5d"].apply(
            lambda v: ",".join(str(int(x)) for x in v) if isinstance(v, list)
            else ("" if v is None else v)
        )
    # Drop any remaining nested (list/dict) columns — they clutter the grid.
    _nested = [c for c in edf.columns
               if edf[c].apply(lambda v: isinstance(v, (list, dict))).any()]
    edf = edf.drop(columns=_nested, errors="ignore")
    # Order by the curated list, then any extras; drop all-empty columns.
    cols = [c for c in _EXPORT_COL_ORDER if c in edf.columns]
    cols += [c for c in edf.columns if c not in cols]
    edf = edf[cols].dropna(axis=1, how="all")
    return edf


def _list_summary(records):
    """Compact count-by-Sector + count-by-Sector-Corr-class line for a list."""
    if not records:
        return
    from collections import Counter
    _sec = Counter((r.get("gics_sector_name") or r.get("gics_sector") or "—")
                   for r in records)
    _corr = Counter((r.get("sector_corr_class") or "—") for r in records)
    st.caption("📊 **By sector:** "
               + " · ".join(f"{k} **{v}**" for k, v in _sec.most_common()))
    st.caption("🔗 **By sector-corr:** "
               + " · ".join(f"{k} **{v}**" for k, v in _corr.most_common()))


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
        "coil_entry", "optimal_stop", "notes",
    ]
    _hdf = pd.DataFrame(_held)
    _hcols = [c for c in _HELD_COLS if c in _hdf.columns]
    _hcols += [c for c in _hdf.columns if c not in _hcols and not c.startswith("_")]
    table_with_copy(_hdf[_hcols], key="held_table")
    st.divider()


# ---------------------------------------------------------------------------
# 3. Longlist — THE one list (PM v1.1). Filter with the sliders below.
# ---------------------------------------------------------------------------
st.subheader("Longlist")
active_recipe = sl.get("active_recipe", {})
st.caption(
    "The single AQE list (no more watchlist / PE / Elder sub-lists). Flags per row: "
    "`on_longlist` = passed the full recipe (engine floors + Elder ≥ 7); `pe` = "
    "Precision-Edge. `elder_pattern` + `elder_context` (VWAP/volume/VCP/exhaustion, "
    "Instruction v1.1) ride on every row. Filter with the sliders — e.g. Min Elder = 8 "
    f"reproduces the old Elder list. Aggregate recipe: {_recipe_label(active_recipe)}."
)

_ll_recs = _ex.get("longlist") or []
if _ll_recs:
    f1, f2, f3, f4, f5, f6 = st.columns([1, 1, 1, 1.4, 1, 1])
    _min_sc = f1.slider("Min SC_MOM", 0, 100, 70, key="sig_sc")
    _min_ptrs = f2.slider("Min PTRS", 0, 100, 0, key="sig_ptrs")
    _min_elder = f3.slider("Min Elder", 0, 10, 0, key="sig_elder")
    _mp_opts = sorted({(r.get("mp_state") or "").strip()
                       for r in _ll_recs if (r.get("mp_state") or "").strip()})
    _mp_sel = f4.multiselect("MP state", _mp_opts, default=_mp_opts, key="sig_mp")
    _ll_only = f5.checkbox("Qualified only", key="sig_ll",
                           help="on_longlist = passed the full recipe")
    _pe_only = f6.checkbox("PE only", key="sig_pe")

    def _keep(r: dict) -> bool:
        if (r.get("sc_momentum_raw") or r.get("sc_momentum") or 0) < _min_sc:
            return False
        if (r.get("ptrs") or 0) < _min_ptrs:
            return False
        if (r.get("elder") or 0) < _min_elder:
            return False
        if _mp_sel:
            ms = (r.get("mp_state") or "").strip()
            if ms and ms not in _mp_sel:
                return False
        if _ll_only and not r.get("on_longlist"):
            return False
        if _pe_only and not r.get("pe"):
            return False
        return True

    _filtered = sorted([r for r in _ll_recs if _keep(r)],
                       key=lambda r: (r.get("ptrs") or 0), reverse=True)
    _n_ll = sum(1 for r in _filtered if r.get("on_longlist"))
    _n_pe = sum(1 for r in _filtered if r.get("pe"))
    st.markdown(f"**{len(_filtered)}** names match "
                f"({_n_ll} qualified · {_n_pe} PE)")
    _list_summary(_filtered)
    table_with_copy(_export_table(_filtered), key="ll_table")

    _earn = sorted({c["ticker"] for c in sl.get("candidates", [])
                    if c.get("diagnostics", {}).get("earn_warning")
                    and c.get("ticker") in {r.get("ticker") for r in _ll_recs}})
    if _earn:
        st.warning(f"Earnings within 5 days: {', '.join(_earn)}")
else:
    st.info("No longlist in the export yet — run the daily pipeline + export.")

st.divider()

# ---------------------------------------------------------------------------
# 3b. Elder list — STANDALONE. Sole criterion: Elder ≥ 8 (strong-breakout catcher)
# ---------------------------------------------------------------------------
st.subheader("Elder list")
st.caption(
    "**Standalone list — the only criterion is Elder Impulse ≥ 8** on the last "
    "close (nothing else). This is where strong breakouts show up before they pass "
    "the longlist screens. `elder_5d` (the 5-day running Elder) + `elder_context` "
    "ride on every row, same as the longlist."
)
_elder_recs = _ex.get("elder_list") or []
if _elder_recs:
    st.markdown(f"**{len(_elder_recs)}** name(s) at Elder ≥ 8 today")
    _list_summary(_elder_recs)
    table_with_copy(_export_table(_elder_recs), key="elder_table")
elif _ex:
    st.info("No names at Elder ≥ 8 on the last close today.")
else:
    st.info("Elder list needs the export JSON — run the daily pipeline + export.")

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
        f"PipeRank {_fmt(r.get('pipe_rank'), '.1f')}"
        + (f"  [FIP spike-excluded, {r.get('fip_window_effective', 252)}d window]"
           if r.get("fip_spike_excluded") else ""),
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
        table_with_copy(pd.DataFrame(_adhoc_rows), key="adhoc_table")

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
