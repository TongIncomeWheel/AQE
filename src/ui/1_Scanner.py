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
from src.engines.srm import GICS_ETFS
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
        st.divider()
        st.caption(
            "**Auto-refresh**: screens the full US equity market — mcap ≥ $2B, "
            "10-day avg volume ≥ 1.5M, US primary listing (NASDAQ/NYSE). "
            "Size + liquidity + listing only — **no trend filter**, so a "
            "pulled-back name stays eligible and each list applies its own "
            "trend view. Runs automatically at 06:00 SGT (Tue–Sat). Use the "
            "button below to trigger manually."
        )
        if st.button("Refresh universe now", type="primary",
                      use_container_width=True, key="universe_refresh_btn"):
            from src.data.universe import build_universe
            with st.spinner("Screening US equities (mcap / volume / listing)..."):
                result = build_universe()
            if result.get("status") == "ok":
                st.success(
                    f"Universe refreshed: **{result['total']}** tickers "
                    f"(+{result['added']} new / -{result['removed']} dropped / "
                    f"={result['kept']} kept)"
                    + (" — saved to Drive" if result.get("drive_ok") else "")
                )
                _universe_status.clear()
                st.rerun()
            else:
                st.error(f"Universe refresh failed: {result.get('reason', result)}")

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
    """PTRS for any ticker (ad-hoc scorer) = SC_MOM verbatim.

    The legacy Sector-Health (+SH) term is DROPPED (PM ruling, AIC Charter
    Amendment v2.8, 2026-07) — must match the daily_list/held_positions PTRS
    (drive_sync.py's `_ptrs()`) bit-for-bit, or the ad-hoc scorer silently
    shows the PM a different PTRS than the live feed for the same ticker.
    `ticker`/`sector_grades` kept for call-site compatibility (unused).
    """
    result = compute_ptrs(sc_mom, 0.0)
    ptrs = result.get("ptrs")
    return round(ptrs, 1) if ptrs is not None and ptrs == ptrs else 0.0


@st.cache_data(ttl=600, show_spinner=False)
def _load_sector_sh_map() -> dict[str, int]:
    """Return {ticker: SH_value} for every ticker in sector_map.json."""
    sm = load_sector_map()  # {ticker: 'XLK', ...}
    return sm  # we'll resolve SH at call time


def _vectorized_ptrs(df: pd.DataFrame, sector_grades: dict) -> pd.Series:
    """PTRS for a full DataFrame = SC_MOM verbatim (vectorized).

    The legacy Sector-Health (+SH) term is DROPPED (PM ruling, AIC Charter
    Amendment v2.8, 2026-07) — see `_quick_ptrs`. `sector_grades` kept for
    call-site compatibility (unused).
    """
    return df["sc_momentum"].fillna(0).round(1)


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
            _fc1, _fc2 = st.columns([3, 2])
            with _fc1:
                _sel_etfs = st.multiselect(
                    "Sectors to plot", _etf_opts, default=_etf_opts,
                    key="rrg_sector_filter",
                    help="Trim the RRG to just the sectors you want when it gets "
                         "crowded. The dotted tail traces each sector's last 5 days "
                         "(direction of travel); the dot is today.",
                )
            with _fc2:
                _rrg_dir_filter = st.selectbox(
                    "RRG filter", ["All", "Positive", "Negative",
                                   "LEADING", "IMPROVING", "WEAKENING", "LAGGING"],
                    key="rrg_sector_dir_filter",
                    help="Positive = LEADING + IMPROVING quadrants. "
                         "Negative = WEAKENING + LAGGING. Or pick a single quadrant.",
                )

            _pts = [p for p in _all_pts if p[0] in _sel_etfs] or _all_pts

            _POS_QUADS = {"LEADING", "IMPROVING"}
            _NEG_QUADS = {"WEAKENING", "LAGGING"}
            if _rrg_dir_filter == "Positive":
                _q_map = {e: d.get("rrg_quadrant", "") for e, d in srm_detail.items()}
                _pts = [p for p in _pts if _q_map.get(p[0]) in _POS_QUADS] or _pts
            elif _rrg_dir_filter == "Negative":
                _q_map = {e: d.get("rrg_quadrant", "") for e, d in srm_detail.items()}
                _pts = [p for p in _pts if _q_map.get(p[0]) in _NEG_QUADS] or _pts
            elif _rrg_dir_filter in ("LEADING", "IMPROVING", "WEAKENING", "LAGGING"):
                _q_map = {e: d.get("rrg_quadrant", "") for e, d in srm_detail.items()}
                _pts = [p for p in _pts if _q_map.get(p[0]) == _rrg_dir_filter] or _pts

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
        _tc1, _tc2 = st.columns([3, 2])
        with _tc1:
            _sel_b = st.multiselect(
                "Baskets to plot", _b_opts, default=_b_opts,
                key="rrg_thematic_filter",
                format_func=lambda b: _basket_short.get(b, b),
                help="Trim the thematic RRG when crowded. The dotted tail traces each "
                     "basket's last 5 days (direction of travel); the dot is today.",
            )
        with _tc2:
            _rrg_theme_dir = st.selectbox(
                "RRG filter", ["All", "Positive", "Negative",
                               "LEADING", "IMPROVING", "WEAKENING", "LAGGING"],
                key="rrg_thematic_dir_filter",
                help="Positive = LEADING + IMPROVING quadrants. "
                     "Negative = WEAKENING + LAGGING. Or pick a single quadrant.",
            )

        _tpts = [p for p in _all_tpts if p[0] in _sel_b] or _all_tpts

        _POS_Q = {"LEADING", "IMPROVING"}
        _NEG_Q = {"WEAKENING", "LAGGING"}
        if _rrg_theme_dir == "Positive":
            _tq = {b: d.get("rrg_quadrant", "") for b, d in _thematic.items()}
            _tpts = [p for p in _tpts if _tq.get(p[0]) in _POS_Q] or _tpts
        elif _rrg_theme_dir == "Negative":
            _tq = {b: d.get("rrg_quadrant", "") for b, d in _thematic.items()}
            _tpts = [p for p in _tpts if _tq.get(p[0]) in _NEG_Q] or _tpts
        elif _rrg_theme_dir in ("LEADING", "IMPROVING", "WEAKENING", "LAGGING"):
            _tq = {b: d.get("rrg_quadrant", "") for b, d in _thematic.items()}
            _tpts = [p for p in _tpts if _tq.get(p[0]) == _rrg_theme_dir] or _tpts

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
            "Why": _d.get("grade_path", "—"),
            "Breadth %": _d.get("breadth_pct"),
            "Pattern": _d.get("pattern") or "—",
            "Pattern stage": _d.get("pattern_stage") or "—",
            "Capped at parent": _d.get("parent_capped_grade", "---"),
            "Parent": f'{_d.get("parent_gics", "—")} ({_d.get("parent_grade", "—")})',
            "Rotation (RRG)": _rrg_phrase(_d.get("rrg_quadrant"), _d.get("rrg_direction")),
            "20d%": _fmt(_d.get("roc20"), "+.1f"),
            "5d%": _fmt(_d.get("roc5"), "+.1f"),
            "Coverage": _d.get("coverage", "—"),
        })
    table_with_copy(pd.DataFrame(_trows), key="thematic_table")
    st.caption(
        "**Why** — which rule produced the grade. *trend* = the 20-day road "
        "(roc20 > 5%) · *acceleration* = the 5-day road (≥ +6% in a week, ≥ 5 pts "
        "ahead of the 20-day pace) · *recovery* = above its 20D SMA and thrusting, "
        "but the month is still net negative · *narrow* = the index said DEPLOY and "
        "breadth said no.  \n"
        "**Breadth %** — how many constituents are above their OWN 20D SMA. An "
        "equal-weight index can be carried by one name; this is the check on that. "
        "Under 60% a DEPLOY is demoted to HOLD.  \n"
        "**Capped at parent** — what the grade WOULD be under the old parent-GICS "
        "cap, kept for reference. The cap is no longer applied: with XLK on HOLD it "
        "made a +13% theme and a flat one read identically.  \n"
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
        """Per-name R:R from the structural bracket (bracket.rr, else nearest
        target's r)."""
        b = r.get("bracket") or {}
        if b.get("rr") is not None:
            return b.get("rr")
        tgts = b.get("targets") or []
        if tgts and isinstance(tgts[0], dict):
            return tgts[0].get("r")
        return None

    def _tp_price(r: dict, i: int):
        tgts = (r.get("bracket") or {}).get("targets") or []
        return tgts[i].get("price") if i < len(tgts) and isinstance(tgts[i], dict) else None

    def _build_cloud_lookups(export: dict) -> tuple[dict, dict, dict]:
        betas: dict[str, dict] = {}
        dsl: dict[str, dict] = {}
        elder5: dict[str, list] = {}
        # daily_list is the single collapsed AQE list; fall back to the legacy
        # longlist/elder_list keys for older exports.
        rows = list(export.get("daily_list") or [])
        if not rows:
            for key in ("longlist", "elder_list"):
                rows.extend(export.get(key) or [])
        for r in rows:
            tk = r.get("ticker")
            if not tk or tk in dsl:
                continue
            betas[tk] = {30: r.get("beta_30d"), 60: r.get("beta_60d")}
            _b = r.get("bracket") or {}
            dsl[tk] = {
                "entry": r.get("entry"),
                "stop": _b.get("stop"),
                "risk": _b.get("risk"),
                "stop_type": _b.get("stop_type"),
                "tp_1r": _tp_price(r, 0),
                "tp_2r": _tp_price(r, 1),
                "tp_3r": _tp_price(r, 2),
                "rr_pct": _b.get("risk_pct"),
                "stop_atr_dist": _b.get("stop_atr_dist"),
                "rr_est": _rr_from_record(r),
                "bracket": _b,
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

_dq = _ex.get("data_quality") or {}
if _dq.get("flagged_count"):
    _dq_held = [f for f in _dq["flagged"] if f.get("tier") == "held_positions"]
    _dq_daily = [f for f in _dq["flagged"] if f.get("tier") == "daily_list"]
    with st.expander(
        f"⚠️ Data quality: {_dq['flagged_count']} record(s) have a null core field "
        f"despite being scored" + (f" — {len(_dq_held)} on HELD positions" if _dq_held else ""),
        expanded=bool(_dq_held),
    ):
        st.caption(
            "These tickers made it into the feed via full scoring, so a null here "
            "is a real data gap (thin price history, an FMP gap, a degenerate "
            "calc) — not a 'nothing detected' state. Don't read a blank cell "
            "below as confirmed zero/absent."
        )
        if _dq_held:
            st.markdown("**Held positions:**")
            for _f in _dq_held:
                st.markdown(f"- `{_f['ticker']}` — missing: {', '.join(_f['null_fields'])}")
        if _dq_daily:
            st.markdown("**Daily list:**")
            for _f in _dq_daily:
                st.markdown(f"- `{_f['ticker']}` — missing: {', '.join(_f['null_fields'])}")

_EXPORT_COL_ORDER = [
    "rank", "ticker", "source", "pe", "on_longlist", "on_elder", "on_qs",
    # QS read, flattened from the nested `qs` block so it sorts/filters/copies
    # like any other column (the full block stays on the row for the cards).
    # QS, ordered as the decision reads: is it a pick -> what are the odds ->
    # what drove them -> where do I trade it -> anything against it.
    "qs_conviction", "qs_state", "qs_signal",
    "qs_p_pct", "qs_n", "qs_edge_pts",   # p is never shown without n (STEP 8)
    "qs_hits_of40", "qs_persist_of5", "qs_lens_of10",
    "qs_target_2atr", "qs_give_up_2atr", "qs_usual_days", "qs_dip_pct",
    "qs_vetoes", "qs_extrapolated", "qs_not_listed",
    "gics_sector", "gics_sector_name", "gics_gate", "sector_corr", "sector_corr_class",
    "sc_momentum", "sc_momentum_raw", "ptrs", "pipe_rank", "floor",
    "flow", "energy", "structure", "mp", "mp_state", "elder", "elder_5d",
    "beta_30d", "beta_60d", "day_vol", "rs_spy_20d", "sma_distance_pct",
    "pattern", "pattern_stage", "pattern_trigger", "pattern_fit",
    "pattern_days",
    "vol_30d_ann_pct", "knn_prob_pct",
    "entry", "atr_14d",
    # THE BRACKET — structural stop + targets (mechanical DSL/TP retired)
    "bracket", "held", "rank_explain",
    # Enrichment Spec v2.0
    "rs_down_day_20d", "rs_leadership", "setup_state",
    "breakout_conviction", "breakout_grade", "breakout_pattern", "breakout_bar_date",
    "atr_caution", "beta_data_error", "malformed_bracket",
    "beta_60d_capped", "dsl_atr_ratio_floored",
    "elder_pattern", "ecx_vwap_pos", "ecx_vwap_slope", "ecx_vol_trend",
    "ecx_vol_above20d", "ecx_up_dn_ratio", "ecx_vcp_label", "ecx_vcp_tight",
    "ecx_exhaustion",
]


def _flatten_qs(edf):
    """Expand the nested `qs` block into flat qs_* columns for the grid.

    The grid drops nested objects, so without this the whole QS read would
    vanish from the table (and from the TSV the AIC gets pasted). The full
    nested block stays on the row and is what the cards render from.

    qs_p / qs_target_2atr describe the +/-2xATR OBJECTIVE, not the structural
    bracket — the column names carry `2atr` so the two level sets stay
    distinguishable at a glance in a wide table.
    """
    if "qs" not in edf.columns:
        return edf

    def g(q, *path, default=None):
        cur = q
        for k in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
        return default if cur is None else cur

    qs = edf["qs"]
    # Names follow the spec's own vocabulary wherever it has one: recipe_hits,
    # qs_persist, lens_total, conviction, state, vetoes, p, edge.
    edf["qs_conviction"] = qs.apply(lambda q: g(q, "conviction"))
    edf["qs_state"] = qs.apply(lambda q: g(q, "state", "code", default=""))
    edf["qs_signal"] = qs.apply(lambda q: g(q, "signal", default=""))
    # Column NAMES carry the scale; VALUES stay numeric so the grid still sorts
    # and the sliders still compare. Bare decimals (0.71 beside 0.264) and bare
    # integers (17 beside 4) read as four similar numbers when they are two
    # different stages of one calculation:
    #   hits + persist + lens  ->  pick a calibration bucket  ->  p, n
    #   p - today's market base rate                          ->  edge
    # Formatting them as strings ("17/40") would fix the confusion and break
    # sorting — "17/40" sorts before "4/40" lexically — so the scale goes in
    # the header instead.
    edf["qs_p_pct"] = qs.apply(
        lambda q: (lambda p: None if p is None else round(p * 100, 1))(
            g(q, "odds", "p")))
    # SPEC RULE (STEP 8 / §4.4): a probability is NEVER shown without the
    # analogue count behind it. p alone hides whether it came from 700 historical
    # look-alikes or 17, which is the difference between a read and a rumour.
    edf["qs_n"] = qs.apply(lambda q: g(q, "odds", "n_analogues"))
    # In percentage POINTS, not a decimal: edge is the gap between two
    # percentages, so "+26" cannot be misread as a probability of 0.26.
    edf["qs_edge_pts"] = qs.apply(
        lambda q: (lambda e: None if e is None else round(e * 100, 1))(
            g(q, "odds", "edge")))
    edf["qs_hits_of40"] = qs.apply(lambda q: g(q, "engine", "recipe_hits"))
    edf["qs_persist_of5"] = qs.apply(lambda q: g(q, "engine", "qs_persist"))
    edf["qs_lens_of10"] = qs.apply(lambda q: g(q, "engine", "lens_total"))
    # `_2atr` is deliberate and NOT spec vocabulary: the spec calls these
    # target / give_up, but in this table they sit beside the structural
    # bracket's TP1/TP2, and an unqualified "target" column would invite
    # reading qs_p as the odds of hitting a bracket target. It is not.
    edf["qs_target_2atr"] = qs.apply(lambda q: g(q, "objective", "target_2atr"))
    edf["qs_give_up_2atr"] = qs.apply(lambda q: g(q, "objective", "give_up_2atr"))
    edf["qs_usual_days"] = qs.apply(lambda q: g(q, "path", "usual_days"))
    edf["qs_dip_pct"] = qs.apply(lambda q: g(q, "path", "typical_dip_pct"))
    edf["qs_vetoes"] = qs.apply(
        lambda q: ", ".join(g(q, "vetoes", default=[]) or []))
    # One honesty flag, kept because it changes how the number should be READ:
    # an extrapolated row was scored from OUTSIDE the population the odds were
    # measured on, so its p is a read-across rather than a measured analogue.
    edf["qs_extrapolated"] = qs.apply(
        lambda q: bool(g(q, "odds", "extrapolated", default=False)))
    # WHY a scored name is not on the QS list. Four separate rules all produce
    # on_qs=False, so without this a high-conviction name sitting off the list
    # reads as a bug rather than a rule.
    edf["qs_not_listed"] = qs.apply(
        lambda q: g(q, "not_listed_reason", default="") or "")
    # Deliberately NOT columns: the calibration cell key ("8+|6-7|4-5"), the
    # bucket kind, the five individual lens scores, the 16 raw components,
    # matched_recipes, p_test. They are engine mechanics — they say HOW the
    # number was reached, not what it is, and a grid of them is unreadable.
    # All of it is still in the daily file and on the QS card, so nothing is
    # lost for audit or for answering "why is this name here".
    return edf


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
    export JSON. elder_context is flattened to ecx_* columns.
    """
    if not records:
        return pd.DataFrame()
    edf = pd.DataFrame(records)
    edf = _flatten_elder_context(edf)
    edf = _flatten_qs(edf)
    if "elder_5d" in edf.columns:
        edf["elder_5d"] = edf["elder_5d"].apply(
            lambda v: ",".join(str(int(x)) for x in v) if isinstance(v, list)
            else ("" if v is None else v)
        )
    # Drop any remaining nested (list/dict) columns — they clutter the grid.
    _nested = [c for c in edf.columns
               if edf[c].apply(lambda v: isinstance(v, (list, dict))).any()]
    edf = edf.drop(columns=_nested, errors="ignore")
    # Fields the export stores as a DECIMAL fraction but which are percentages
    # (vol_30d_ann 0.18 = 18%, knn_prob 0.62 = 62%). Scaled here, in the display
    # frame only, so the % suffix the grid adds is truthful. The export JSON is
    # untouched — readers there still get the documented decimal.
    for _c, _new in (("vol_30d_ann", "vol_30d_ann_pct"),
                     ("knn_prob", "knn_prob_pct")):
        if _c in edf.columns:
            edf[_new] = pd.to_numeric(edf[_c], errors="coerce") * 100
            edf = edf.drop(columns=[_c])
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


def _render_held_book(hb: dict):
    """Portfolio Hedge Layer (§4C) — beta-adj book exposure + gap-scenario losses.
    Display-only facts (same blob the AIC reads from the export)."""
    if not hb:
        return
    st.markdown("**Portfolio Hedge Layer (§4C) — book exposure**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Beta-adj exp (β30d)", f"${hb.get('beta_adj_exposure_usd', 0):,.0f}")
    m2.metric("$ / 1% gap (β30d)", f"${hb.get('loss_per_1pct_gap_usd', 0):,.0f}")
    m3.metric("Portfolio β30d", f"{hb.get('nav_weighted_beta_30d', 0):.2f}")
    m4.metric("Portfolio β60d", f"{hb.get('nav_weighted_beta_60d', 0):.2f}",
              help="Charter v2.1 §6.4 portfolio gate window (hard 2.0 / soft 1.8).")
    m5.metric("Total exposure", f"${hb.get('total_exposure_usd', 0):,.0f}")
    _sw = {k: v for k, v in (hb.get("sector_weights") or {}).items() if v}
    if _sw:
        st.caption("Sector weights: " + " · ".join(
            f"{k} **{v:.1f}%**" for k, v in sorted(_sw.items(), key=lambda x: -x[1])))
    _gs30 = hb.get("gap_scenarios") or {}
    _gs60 = hb.get("gap_scenarios_60d") or {}
    if _gs30 or _gs60:
        _grows = [{"Gap": lbl,
                   "Est. book loss (β30d)": f"${(_gs30.get(key) or {}).get('est_book_loss_usd', 0):,.0f}",
                   "Est. book loss (β60d)": f"${(_gs60.get(key) or {}).get('est_book_loss_usd', 0):,.0f}"}
                  for lbl, key in (("3%", "gap_3pct"), ("5%", "gap_5pct"),
                                   ("7%", "gap_7pct"), ("10%", "gap_10pct"))]
        st.dataframe(pd.DataFrame(_grows), use_container_width=False, hide_index=True)
    st.caption(f"as of {hb.get('as_of', '—')} · {hb.get('position_count', 0)} positions "
               "· both β windows shown (AQE makes no gate call — Charter v2.1 §6.4 gate = "
               "β60d) · hedge payout (Alpaca) assembled by Alfred")


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
        "mp_state", "elder", "beta_30d", "beta_60d", "day_vol", "rs_spy_20d",
        "sma_distance_pct", "sector_corr", "atr_14d", "bracket", "notes",
    ]
    _hdf = pd.DataFrame(_held)
    _hcols = [c for c in _HELD_COLS if c in _hdf.columns]
    _hcols += [c for c in _hdf.columns if c not in _hcols and not c.startswith("_")]
    table_with_copy(_hdf[_hcols], key="held_table")
    _render_held_book(_ex.get("held_book"))
    st.divider()
elif _ex.get("held_positions_status") not in (None, "live"):
    st.warning(
        f"⚠️ Held positions came back **empty** and the PTJ status is "
        f"`{_ex.get('held_positions_status')}` — this run could NOT confirm a live "
        "read from the trade journal on Drive. An empty table here does NOT mean "
        "your book is flat. Re-run the pipeline (or check Drive access) before "
        "trusting a zero-held read."
    )
    st.divider()


# ---------------------------------------------------------------------------
# 3. THE daily list — ONE list, membership as columns (PM ruling 2026-08-04).
# Longlist / Elder (≥8) / QS are LENSES on this single list (`on_longlist`,
# `on_elder`, `on_qs`), never parallel lists. Filters below select which lens,
# which sector/thematic, and the level thresholds.
# ---------------------------------------------------------------------------
st.subheader("Daily list")
active_recipe = sl.get("active_recipe", {})
st.caption(
    "**ONE list — Longlist, Elder and QS are columns on it, not separate lists.** "
    "`on_longlist` = SC_MOM > 64 AND PTRS ≥ 60 AND Elder ≥ 7 (the sliders default to "
    "exactly that, and the export/alerts fire off the same set — what you see == what "
    "fires). `on_elder` = also Elder ≥ 8. `on_qs` = cleared the Quiet Strength engine's "
    "emit rule. A name can carry any combination; **tick QS alone to see what the new "
    "lens is adding.** `elder_pattern` + `elder_context` ride on every row. "
    f"Aggregate recipe: {_recipe_label(active_recipe)}."
)
_qs_status = _ex.get("qs_status", "not_run")
if _qs_status == "error":
    st.warning(
        "⚠️ **QS did not run for this export** — an empty QS column here means "
        "nothing was CHECKED, not that nothing qualified. See the pipeline log."
    )
elif _qs_status == "not_run":
    st.info("QS has not run yet for this export — run the daily pipeline once to "
            "populate the QS column.")

# QS market line, ABOVE the table. Spec §4.3: "Market first — it can cancel the
# day." A STAND_DOWN regime empties the QS list by design, so without this a
# screen full of high-conviction names carrying on_qs=False looks broken rather
# than obeying a rule.
_qsm = _ex.get("qs_market") or {}
if _qsm.get("description"):
    _avg = _qsm.get("avg_stock_hits_target")
    _avg_txt = (
        f" The average stock reaches its target **{_avg:.0%}** of the time in "
        f"this weather."
        if _avg is not None else
        " This regime has **no measured base rate** — conviction falls back to "
        "the all-market 54.8%.")
    _colour = _qsm.get("colour", "GREY")
    _icon = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}.get(_colour, "⚪")
    _line = (f"{_icon} **QS market read — {_colour}: {_qsm['description']}.**"
             f"{_avg_txt} {_qsm.get('action', '')}  \n"
             f"`{_qsm.get('regime_code', '')}`")
    # A WARNING, never a filter (PM ruling 2026-08-04). Regime shapes every
    # row's `edge` through the base rate it sets — it does not remove names.
    _note = ("  \n_Regime is a warning, not a filter — no name is removed from "
             "the list because of it._")
    (st.error if _colour == "RED" else
     st.warning if _colour == "AMBER" else st.info)(_line + _note)

    with st.expander("How today's regime was calculated, and how it ranks",
                     expanded=False):
        _in = _qsm.get("inputs") or {}
        if _in.get("trend_200") is not None:
            _tb = _in.get("trend_boundaries") or [None, None]
            _vb = _in.get("vol_boundaries") or [None, None]
            _fmt = lambda v: "—" if v is None else f"{v:+.3f}"
            st.markdown(
                f"**Two inputs, each bucketed into thirds.**\n\n"
                f"| Input | Today | Tercile cut-points | Lands in |\n"
                f"|---|---|---|---|\n"
                f"| **TREND** — {_in.get('trend_200_meaning','')} | "
                f"`{_in['trend_200']:+.4f}` | "
                f"`{_fmt(_tb[0])}` / `{_fmt(_tb[1])}` | "
                f"**T{int(_in['trend_tercile']) if _in.get('trend_tercile') else '?'}** |\n"
                f"| **VOL** — {_in.get('vol_60_meaning','')} | "
                f"`{_in['vol_60']:.4f}` | "
                f"`{_fmt(_vb[0])}` / `{_fmt(_vb[1])}` | "
                f"**V{int(_in['vol_tercile']) if _in.get('vol_tercile') else '?'}** |\n"
            )
            st.caption(_in.get("method", ""))
        _grid = _qsm.get("regime_grid") or []
        if _grid:
            st.markdown("**All 10 regimes, ranked by measured base rate** — "
                        "the colour is backtested, not an opinion. Today is ★.")
            st.dataframe(
                pd.DataFrame([{
                    "": "★" if g["is_today"] else "",
                    "rank": g["rank"],
                    "colour": g["colour"],
                    "regime": g["cell"],
                    "market description": g["description"],
                    "avg stock hits target %": (
                        None if g["avg_stock_hits_target"] is None
                        else round(g["avg_stock_hits_target"] * 100, 1)),
                    "book stance": g["book_stance"],
                } for g in _grid]),
                use_container_width=True, hide_index=True)
            st.caption(
                "The **book stance** is a judgement word from the frozen recipe "
                "book; the **colour** is the measured hit rate. They disagree "
                "more often than you'd expect — T1V3 reads DEFENSIVE "
                "(\"bear weather\") but measured 61.3%, better than the "
                "all-market base, while T3V3 reads PRESS but measured 44.6%. "
                "Where they differ, the colour is the one with evidence behind it."
            )

# The Signals table = the single collapsed `daily_list` (watchlist ∪ elder ∪
# ledger, each row flagged on_longlist/on_elder/in_ledger). Legacy exports that
# still carry `longlist` fall back to it.
_ll_recs = _ex.get("daily_list")
if _ll_recs is None:
    _ll_recs = _ex.get("longlist") or []
if _ll_recs:
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1.4])
    # Slider defaults ARE the longlist definition — same source as the export
    # membership (src/longlist_screen.py). What you see == what fires.
    from src.longlist_screen import MIN_SC, MIN_PTRS, MIN_ELDER
    _min_sc = f1.slider("Min SC_MOM", 0, 100, MIN_SC, key="sig_sc")
    _min_ptrs = f2.slider("Min PTRS", 0, 100, MIN_PTRS, key="sig_ptrs")
    _min_elder = f3.slider("Min Elder", 0, 10, MIN_ELDER, key="sig_elder")
    _mp_opts = sorted({(r.get("mp_state") or "").strip()
                       for r in _ll_recs if (r.get("mp_state") or "").strip()})
    _mp_sel = f4.multiselect("MP state", _mp_opts, default=_mp_opts, key="sig_mp")

    # ---- QS sliders. All default to 0 = no QS filtering, so the list behaves
    # exactly as before until you reach for one. A row that QS never scored is
    # EXCLUDED once any of these is raised above 0 — "no QS read" is not the
    # same as "scored zero", and silently keeping unscored names would make a
    # QS filter look like it had found something it hadn't.
    q1, q2, q3 = st.columns([1, 1, 1])
    _min_conv = q1.slider(
        "Min QS conviction", 0, 5, 0, key="sig_qsconv",
        help="QS conviction 0-5. 0 = no filter. Note conviction 0 also means "
             "VETOED-and-shown, so 1+ hides struck names.")
    _min_qs_p = q2.slider(
        "Min QS probability %", 0, 100, 0, key="sig_qsp",
        help="Odds of reaching the QS objective (+2xATR14 within 20 sessions). "
             "The market's own average is on the QS card — a probability only "
             "means something against that base.")
    _min_qs_lens = q3.slider(
        "Min QS lens total", 0.0, 10.0, 0.0, step=0.5, key="sig_qslens",
        help="Mean of the five lens scores (structure, coil, quiet momentum, "
             "flow, leadership). The 'how strong is the profile' read, before "
             "the calibration turns it into odds.")

    # LENS membership — checkboxes, so every list is visible at once and
    # ticking two is one click each rather than a dropdown round-trip.
    # Nothing ticked = show everything. Ticks are OR'd: Longlist + Elder shows
    # names on either, not only names on both.
    # 'In ledger' is GONE: it meant runner_setup OR premove_setup, i.e. pure
    # Signal Radar, which is retired. A filter for a dead lens is worse than no
    # filter — it implies the lens is still telling you something.
    st.caption("**Lists** — tick any combination (nothing ticked = all names)")
    _LENS_BOXES = [
        ("Longlist", "sig_f_ll", None),
        ("Elder ≥8", "sig_f_el", None),
        ("QS", "sig_f_qs", None),
        ("QS only", "sig_f_qso",
         "On QS and on NEITHER Longlist nor Elder — what the third lens is "
         "adding on its own."),
        ("Held", "sig_f_held", None),
    ]
    _lens_cols = st.columns(len(_LENS_BOXES))
    _lens_sel = [
        label for (label, key, hlp), col in zip(_LENS_BOXES, _lens_cols)
        if col.checkbox(label, key=key, help=hlp)
    ]
    _sec_opts = sorted({(r.get("gics_sector_name") or r.get("gics_sector") or "—")
                        for r in _ll_recs})
    _sec_sel = st.multiselect("Sector", _sec_opts, default=_sec_opts,
                              key="sig_sector")
    _th_opts = sorted({(r.get("thematic_basket") or "—") for r in _ll_recs})
    _th_sel = st.multiselect("Thematic basket", _th_opts, default=_th_opts,
                             key="sig_thematic") if len(_th_opts) > 1 else _th_opts

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
        if _sec_sel:
            sec = (r.get("gics_sector_name") or r.get("gics_sector") or "—")
            if sec not in _sec_sel:
                return False
        if _th_sel and (r.get("thematic_basket") or "—") not in _th_sel:
            return False

        # QS thresholds. Any of these above 0 means the user is filtering ON
        # QS, so a row QS never scored cannot qualify — absence of a read is
        # not a low read, and keeping unscored names would pad the result with
        # names the filter never actually examined.
        if _min_conv or _min_qs_p or _min_qs_lens:
            _q = r.get("qs")
            if not _q:
                return False
            if (_q.get("conviction") or 0) < _min_conv:
                return False
            _p = (_q.get("odds") or {}).get("p")
            if _min_qs_p and (_p is None or _p * 100 < _min_qs_p):
                return False
            _lt = (_q.get("engine") or {}).get("lens_total")
            if _min_qs_lens and (_lt is None or _lt < _min_qs_lens):
                return False

        if _lens_sel:
            _qs_only = (r.get("on_qs") and not r.get("on_longlist")
                        and not r.get("on_elder"))
            hit = (("Longlist" in _lens_sel and r.get("on_longlist"))
                   or ("Elder ≥8" in _lens_sel and r.get("on_elder"))
                   or ("QS" in _lens_sel and r.get("on_qs"))
                   or ("QS only" in _lens_sel and _qs_only)
                   or ("Held" in _lens_sel and r.get("held")))
            if not hit:
                return False
        return True

    _filtered = sorted([r for r in _ll_recs if _keep(r)],
                       key=lambda r: (r.get("ptrs") or 0), reverse=True)
    _n_el = sum(1 for r in _filtered if r.get("on_elder"))
    _n_qs = sum(1 for r in _filtered if r.get("on_qs"))
    _n_qso = sum(1 for r in _filtered if r.get("on_qs")
                 and not r.get("on_longlist") and not r.get("on_elder"))
    _n_scored = sum(1 for r in _filtered if r.get("qs"))
    st.markdown(f"**{len(_filtered)}** names match "
                f"({_n_el} Elder≥8 · {_n_qs} on QS, {_n_qso} QS-only · "
                f"{_n_scored} carry a QS read)")
    _held_here = [r.get("ticker") for r in _filtered if r.get("held")]
    if _held_here:
        st.caption(f"🔵 **{len(_held_here)} held**: {', '.join(_held_here)}")
    _list_summary(_filtered)
    table_with_copy(_export_table(_filtered), key="ll_table")

    # ---- QS cards, rendered from the export ALONE (src/engines/qs_card.py).
    # The renderer cannot open a file or call an engine, so anything shown here
    # is provably in the daily JSON — which is what makes "rebuild the card for
    # X" work for the AIC as well as the screen.
    _qs_rows = [r for r in _filtered if r.get("qs")]
    if _qs_rows:
        with st.expander(f"QS cards ({len(_qs_rows)})", expanded=False):
            st.caption(
                "Read the market line first — it can cancel the day. "
                "**OBJECTIVE** is the ±2×ATR14 yardstick the probability was "
                "measured against; **LEVELS** is AQE's structural bracket — what "
                "you'd actually trade. They are different numbers answering "
                "different questions, so the probability never refers to a "
                "bracket target."
            )
            try:
                from src.engines.qs_card import render_market, render_card
                st.code(render_market(_ex.get("qs_market") or {}), language=None)
                _cards = sorted(
                    _qs_rows,
                    key=lambda r: ((r.get("qs") or {}).get("rank") or 10**6))
                _pick = st.multiselect(
                    "Show cards for", [r["ticker"] for r in _cards],
                    default=[r["ticker"] for r in _cards[:5]], key="qs_cards_pick")
                for _r in _cards:
                    if _r["ticker"] in _pick:
                        st.code(render_card(_r, _ex.get("qs_market") or {}),
                                language=None)
            except Exception as _exc:  # noqa: BLE001
                st.caption(f"card renderer unavailable: {_exc}")

    _earn = sorted({c["ticker"] for c in sl.get("candidates", [])
                    if c.get("diagnostics", {}).get("earn_warning")
                    and c.get("ticker") in {r.get("ticker") for r in _ll_recs}})
    if _earn:
        st.warning(f"Earnings within 5 days: {', '.join(_earn)}")
else:
    st.info("No longlist in the export yet — run the daily pipeline + export.")

st.divider()

# ---------------------------------------------------------------------------
# 3b. Detect Lens Segment — every scored name ordered by how many lenses agree.
# Replaces the old Signal Radar section (PM ruling 2026-07-28: Signal Radar's
# runner/premove detection tags are expired). Unweighted reading aid (PM build
# order, 2026-07-16): sort only, nothing is cut/capped/eliminated. The full
# per-name data stays in the Signals table above; this is "where do I start
# reading."
# ---------------------------------------------------------------------------
_lens_ranking = _ex.get("lens_ranking") or {}
if _lens_ranking.get("ranked"):
    st.subheader(f"Detect Lens Segment ({_lens_ranking.get('count', 0)})")
    st.caption(
        "Ranked by count of lenses reading **strong**: "
        + ", ".join(_lens_ranking.get("lens_set", [])) + ". "
        "UNWEIGHTED — sort only, nothing is filtered or eliminated. `--` = no "
        "data (absence is never agreement), not a low score. A reading aid, "
        "not a prediction — whether more lenses agreeing is actually better "
        "is untested."
    )
    _lens_rows = []
    for _r in _lens_ranking["ranked"]:
        _lens = _r.get("lens") or {}
        _row = {"rank": _r.get("rank"), "ticker": _r.get("ticker"),
                "positive": _r.get("positive"), "warnings": _r.get("warnings")}
        for _lane in _lens_ranking.get("lens_set", []):
            _row[_lane] = _lens.get(_lane, "--")
        _lens_rows.append(_row)
    table_with_copy(pd.DataFrame(_lens_rows), key="lens_ranking_table")
elif _ex:
    st.info(
        "No lens_ranking in this export yet — run the daily pipeline once to "
        "generate it."
    )

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
        f"Stop {_fmt(lv.get('stop'), '.2f')} ({lv.get('stop_type') or '—'}) · "
        f"TP {_fmt(lv.get('tp_1r'), '.2f')}/{_fmt(lv.get('tp_2r'), '.2f')}/{_fmt(lv.get('tp_3r'), '.2f')} · "
        f"R:R {_fmt(lv.get('rr_est'), '.1f')} · stop {_fmt(lv.get('stop_atr_dist'), '.2f')}×ATR · "
        f"beta {_fmt(r.get('beta_60d'), '.2f')}",
        f"Sector: {sector_name} ({etf}) {grade} · RRG {rrg_q} · Macro {macro_f} · Gate {entry_gate}",
        f"Regime: VIX {_fmt(vix, '.1f')} ({regime_lvl}) · "
        f"PipeRank {_fmt(r.get('pipe_rank'), '.1f')}"
        + (f"  [FIP spike-excluded, {r.get('fip_window_effective', 252)}d window]"
           if r.get("fip_spike_excluded") else ""),
        "Advise: entry decision + size per PTRS x regime. Charter v1.9.3.",
    ]
    return "\n".join(lines)


def _adhoc_export_record(r: dict, idx: int, sm: dict, sector_grades: dict) -> dict:
    """Shape an ad-hoc score result into the EXPORT record schema, so it renders
    through the same `_export_table()` as the Longlist/Elder tables → identical
    columns (PTRS, GICS gate, sector_corr, RVOL/RS/SMA, the elder_pattern +
    ecx_* context block, and the DSG-18 structural levels/targets).
    """
    from src.data.drive_sync import _v21_record_fields, _subcomponents, _new_engine_fields

    tk = r["ticker"]
    lv = r.get("levels") or {}            # already the shape _v21_record_fields reads
    sc = r.get("sc_momentum")
    raw = r.get("sc_momentum_raw")
    ptrs = _quick_ptrs(sc, tk, sector_grades) if sc is not None else None

    # Per-ticker lookup feeding _v21_record_fields (same keys the pipeline builds).
    lk = {
        "day_vol": {tk: r.get("day_vol")},
        "rs": {tk: r.get("rs_spy_20d")},
        "sma": {tk: r.get("sma_distance_pct")},
        "ma": {tk: r.get("ma") or {}},
        "vol30": {tk: r.get("vol_30d_ann")},
        "beta252": {tk: r.get("beta_252d")},
        "corr": {},        # 60d sector-corr needs parent-ETF bars — not fetched ad-hoc
        "thematic": {},     # basket grades need the pipeline; basket names still tag
        "held": set(),
    }
    # _v21_record_fields already gives gics/thematic/fib/MA + a bracket + the
    # structure_shift read (same function every tier calls). Its OWN bracket
    # recompute has no volume-validation though (that's a post-hoc pass in
    # build_export) — adhoc.py already computed + volume-stamped its own
    # bracket via the SAME bracket_engine functions, so it overrides below.
    v21 = _v21_record_fields(tk, lv, lk, sm, sector_grades)
    if r.get("bracket"):
        v21["bracket"] = r["bracket"]

    rec = {
        "rank": idx, "ticker": tk, "source": "adhoc", "pe": False,
        "sc_momentum": sc, "sc_momentum_raw": raw, "ptrs": ptrs,
        "pipe_rank": r.get("pipe_rank"),
        "flow": r.get("flow"), "energy": r.get("energy"),
        "structure": r.get("structure"), "mp": r.get("mp"),
        "mp_state": r.get("mp_state"),
        "elder": r.get("elder"), "elder_5d": r.get("elder_5d"),
        "beta_30d": r.get("beta_30d"), "beta_60d": r.get("beta_60d"),
        "entry": lv.get("entry"),
        # bracket comes from **v21 (_v21_record_fields, volume-stamp override above).
        "rank_explain": _rank_explain(r.get("pipe_rank"), None, sc or 0,
                                      False, tk, sm, sector_grades),
        "elder_pattern": r.get("elder_pattern"),
        "elder_context": r.get("elder_context"),
        **v21,
        # Same suite as daily_list/held_positions (PM ruling): engine
        # subcomponents, gate breakdown, momentum acceleration, divergence,
        # pin bar / inside bar, smart-money CHoCH+kNN, Health. adhoc.py's `r`
        # already carries every raw column these two functions read — same
        # code, zero duplicated extraction logic.
        "subcomponents": _subcomponents(r),
        **_new_engine_fields(r),
        "sc_m_gates": r.get("sc_m_gates"), "sc_m_gate_detail": r.get("sc_m_gate_detail"),
        "sc_p_gates": r.get("sc_p_gates"), "sc_p_gate_detail": r.get("sc_p_gate_detail"),
        "hl_score": r.get("hl_score"), "hl_state": r.get("hl_state"),
    }
    return rec


_adhoc_results = st.session_state.get("adhoc_results")
if _adhoc_results:
    _ok = [r for r in _adhoc_results if not r.get("error")]
    _err = [r for r in _adhoc_results if r.get("error")]

    if _ok:
        st.caption(
            "Full longlist schema — the SAME columns as the Longlist / Elder tables "
            "(PTRS, GICS gate, sector_corr, RVOL, RS vs SPY, SMA-distance, "
            "elder_pattern + ecx_* context, structural levels/targets, DSL/TP/Fib). "
            "As-of = the latest bar scored — may be fresher than the tables above. "
            "`source` = adhoc; sector_corr is blank (needs the parent-ETF panel)."
        )
        _sm_adhoc = load_sector_map()
        _adhoc_recs = [_adhoc_export_record(r, i, _sm_adhoc, _sector_grades)
                       for i, r in enumerate(_ok, 1)]

        # ---- QS read for each typed ticker, so an ad-hoc lookup is the SAME
        # analysis as a daily_list row. If the name is already on today's list
        # we reuse its export block (that one is a genuine in-cohort read);
        # otherwise we score it against today's eligible cohort as a
        # read-across, flagged extrapolated.
        _qs_market_adhoc, _qs_notes = _ex.get("qs_market") or {}, []
        _dl_by_tk = {r.get("ticker"): r for r in (_ex.get("daily_list") or [])}
        for _rec, _raw in zip(_adhoc_recs, _ok):
            _tk = _rec["ticker"]
            _on_list = _dl_by_tk.get(_tk) or {}
            if _on_list.get("qs"):
                _rec["qs"] = _on_list["qs"]
                _rec["on_qs"] = bool(_on_list.get("on_qs"))
                continue
            try:
                from src.engines.qs_daily import score_adhoc
                _res = score_adhoc(_raw)
                if _res.get("ok"):
                    _rec["qs"] = _res["qs"]
                    _rec["on_qs"] = False
                    if not _qs_market_adhoc:
                        _qs_market_adhoc = _res.get("market") or {}
                    _miss = (_res.get("coverage") or {}).get("recipe_inputs_missing")
                    if _miss:
                        _qs_notes.append((_tk, _miss))
                else:
                    _qs_notes.append((_tk, [f"not scored: {_res.get('reason')}"]))
            except Exception as _exc:  # noqa: BLE001
                _qs_notes.append((_tk, [f"error: {_exc}"]))

        table_with_copy(_export_table(_adhoc_recs), key="adhoc_table")

        if any(r.get("qs") for r in _adhoc_recs):
            st.caption(
                "**QS on an ad-hoc name is a READ-ACROSS, not a measured "
                "probability.** The ticker is placed onto today's eligible "
                "cohort's curve without joining it, so no universe name moves — "
                "but an ad-hoc name sits outside the population the odds were "
                "measured on (it need not even be in the universe). Every "
                "ad-hoc row is flagged `extrapolated`. A name already on "
                "today's list reuses its real in-cohort read instead."
            )
        for _tk, _miss in _qs_notes:
            st.warning(
                f"**{_tk}** — QS inputs missing: `{', '.join(_miss)}`. A missing "
                f"field fails its condition, so recipe hits are UNDERSTATED and "
                f"the probability reads low. Treat this name's QS score as a "
                f"floor, not a verdict."
            )

        _qs_cards_adhoc = [r for r in _adhoc_recs if r.get("qs")]
        if _qs_cards_adhoc:
            with st.expander(f"QS cards — ad-hoc ({len(_qs_cards_adhoc)})",
                             expanded=False):
                try:
                    from src.engines.qs_card import render_market, render_card
                    if _qs_market_adhoc:
                        st.code(render_market(_qs_market_adhoc), language=None)
                    for _r in _qs_cards_adhoc:
                        st.code(render_card(_r, _qs_market_adhoc), language=None)
                except Exception as _exc:  # noqa: BLE001
                    st.caption(f"card renderer unavailable: {_exc}")

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
