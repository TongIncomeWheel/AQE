"""Shared utilities for the multi-page Streamlit app.

Contains: path constants, data loaders, formatting helpers, onboarding,
subprocess runner. Imported by the Scanner, Charts and Trade Entry,
MA Scanner, and Option Scanner pages.

IMPORTANT: No st.* calls at module-level. All Streamlit calls must be
inside functions that pages call explicitly, so st.set_page_config()
can run first in each page file.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.paths import (
    DATA_DIR,
    OUTPUT_DIR,
    EXPORT_JSON,
    PANEL_DAILY,
    SCORES_DAILY,
    SPY_DAILY,
)


# ---------------------------------------------------------------------------
# Cloud / read-only mode detection
# ---------------------------------------------------------------------------

def is_cloud_mode() -> bool:
    """Read-only deployment detector.

    Returns True when the heavy parquet caches are absent — typically because
    we're running on Streamlit Cloud and the daily pipeline (which writes the
    parquets) lives on the user's local PC. In that mode the UI reads
    everything it needs from `output/aqe_daily_export.json` (small, committed)
    instead of `data/scores_daily.parquet` (137MB, gitignored).
    """
    return not SCORES_DAILY.exists()


# Fields renamed in the export, old name -> new name. Applied on READ so an
# archived or in-flight export written before the rename still renders. One
# direction only: the writer emits the new name, nothing writes the old one.
_LEGACY_FIELD_ALIASES = {"rvol": "day_vol"}


def _apply_legacy_aliases(export: dict) -> dict:
    for key in ("daily_list", "held_positions", "lens_ranking",
                "longlist", "elder_list"):
        for row in export.get(key) or []:
            if not isinstance(row, dict):
                continue
            for old, new in _LEGACY_FIELD_ALIASES.items():
                if new not in row and old in row:
                    row[new] = row[old]
    return export


def load_export(allow_drive: bool = False) -> dict | None:
    """Load `output/aqe_daily_export.json` (the canonical cloud-mode source).

    `allow_drive` adds a Drive fallback. OFF by default because the AQE Scanner
    calls this on every render and a REST round-trip per render is a bad trade.
    Pages that read the export as CONTEXT — the Option Scanner joining ATR and
    sector onto a CSP list — pass True behind their own cache: the container's
    output/ is wiped by every deploy and sleep, so local-only means those
    columns silently vanish on a fresh container.
    """
    if EXPORT_JSON.exists():
        try:
            with open(EXPORT_JSON) as f:
                return _apply_legacy_aliases(json.load(f))
        except Exception:  # noqa: BLE001
            pass
    if not allow_drive:
        return None
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(EXPORT_JSON.name)
            if txt:
                return _apply_legacy_aliases(json.loads(txt))
    except Exception:  # noqa: BLE001
        pass
    return None


def percent_column_config(df) -> dict:
    """Display config that renders percentage columns WITH a % sign.

    Values stay numeric so the grid still sorts and filters correctly — a
    formatted string would sort lexically ("100" before "9"). Streamlit's
    NumberColumn applies the suffix at render time only.

    Recognises the naming convention used across the export:
      *_pct / *_pc   a percentage        -> "12.3%"
      *_pts          percentage POINTS   -> "+26 pts"   (a gap between two
                                            percentages, not a percentage)
      *_ann          annualised decimal  -> scaled x100 and shown as a percent
    """
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001
        return {}
    cfg = {}
    for c in getattr(df, "columns", []):
        name = str(c)
        try:
            if not pd.api.types.is_numeric_dtype(df[c]):
                continue
        except Exception:  # noqa: BLE001
            continue
        if name.endswith("_pts"):
            cfg[c] = st.column_config.NumberColumn(name, format="%+.0f pts")
        elif name.endswith(("_pct", "_pc")):
            cfg[c] = st.column_config.NumberColumn(name, format="%.1f%%")
        elif name.endswith("_ann"):
            # Stored as a decimal (0.18 = 18%) — see the field glossary.
            cfg[c] = st.column_config.NumberColumn(name, format="%.1f%%")
    return cfg


# Preferred display order for the grade-like columns, so a filter list reads
# best-to-worst rather than alphabetically (AVOID, DEPLOY, HOLD...).
_FACET_ORDER = {
    "DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4, "NO_DATA": 5,
    "LEADING": 0, "IMPROVING": 1, "WEAKENING": 2, "LAGGING": 3,
    "TAILWIND": 0, "NEUTRAL": 1, "CAUTION": 2, "HEADWIND": 3,
    "PASS": 0, "BLOCKED": 4,
}


def facet_filters(df, *, key: str, facets: list, hide: list | None = None):
    """Column-wise pick-lists above a table, returning the filtered frame.

    The free-text box on `table_with_copy` answers "find X". This answers the
    other question — "show me only the DEPLOY sectors that are also LEADING" —
    which on a 35-row grid is the difference between reading it and scanning it.

    `facets` is a list of (label, column) pairs. A column may be HIDDEN (name
    starting with "_"): the RRG phrase shown in the table is prose like
    "Leading · Deepening in", which is useless to pick from, so the row carries
    `_rrg_q` = LEADING and the filter offers that instead. `hide` names extra
    helper columns to drop before display.

    Nothing selected means no filter on that column — the default view is the
    whole table, not an empty one.
    """
    import streamlit as st

    if df is None or len(df) == 0:
        return df
    view = df
    cols = st.columns(len(facets))
    for (label, col), slot in zip(facets, cols):
        if col not in df.columns:
            continue
        opts = sorted({str(v) for v in df[col].dropna().tolist() if str(v).strip()
                       and str(v) != "—"},
                      key=lambda v: (_FACET_ORDER.get(v.upper(), 99), v))
        if not opts:
            continue
        with slot:
            picked = st.multiselect(label, opts, default=[],
                                    key=f"{key}_facet_{col}",
                                    placeholder=f"All {label.lower()}")
        if picked:
            view = view[view[col].astype(str).isin(picked)]
    if len(view) != len(df):
        st.caption(f"{len(view)} / {len(df)} rows")
    drop = [c for c in (list(hide or []) + [c for _, c in facets])
            if c.startswith("_") and c in view.columns]
    return view.drop(columns=drop) if drop else view


def table_with_copy(df, *, key: str, label: str = "📋 Copy for AIC",
                    caption: str | None = None, filterable: bool = True,
                    column_config: dict | None = None,
                    pin_first: bool = True) -> None:
    """Render a dataframe + an in-table filter + a one-click copy block.

    `st.dataframe` is sortable but NOT filterable, so we add a free-text filter
    box above every table: a row is kept if ANY cell contains the query
    (case-insensitive substring). The copy block then copies the FILTERED view —
    what you see is what you paste into Claude. Set filterable=False to suppress
    the box (e.g. for tiny 1–2 row tables).

    Streamlit's `st.code` has a built-in copy-to-clipboard icon, so we stash the
    (filtered) table as TSV inside a small expander. Used for every data table.
    """
    import streamlit as st

    view = df
    if filterable and df is not None and len(df) > 0:
        q = st.text_input(
            "Filter rows", key=f"{key}_filter",
            placeholder="🔎 filter — type to match across all columns…",
            label_visibility="collapsed",
        )
        if q and q.strip():
            q_low = q.strip().lower()
            try:
                mask = df.astype(str).apply(
                    lambda col: col.str.lower().str.contains(q_low, na=False, regex=False))
                view = df[mask.any(axis=1)]
                st.caption(f"{len(view)} / {len(df)} rows match “{q.strip()}”")
            except Exception:  # noqa: BLE001 — filtering never blocks the table
                view = df

    # Percentage columns render with a % sign unless the caller overrides.
    if column_config is None:
        try:
            column_config = percent_column_config(view)
        except Exception:  # noqa: BLE001 — formatting never blocks the table
            column_config = None
    # FREEZE THE FIRST COLUMN. These grids are 90+ columns wide; scrolling right
    # to read a score loses the ticker it belongs to, which makes the whole row
    # unreadable (PM: "i cant see the ticker as i scroll across"). The first
    # column is the identifier on every table here — ticker, sector or basket —
    # so pinning it is a property of the layout, not a per-table decision.
    _cfg = dict(column_config or {})
    if pin_first and view is not None and len(getattr(view, "columns", [])):
        _first = view.columns[0]
        if _cfg.get(_first) is None:
            try:
                _cfg[_first] = st.column_config.Column(str(_first), pinned=True)
            except TypeError:
                # `pinned` arrived in Streamlit 1.42. An older runtime loses the
                # frozen column rather than the whole page.
                pass
    st.dataframe(view, use_container_width=True, hide_index=True,
                 column_config=_cfg or None)
    try:
        if view is None or len(view) == 0:
            return
        tsv = view.to_csv(sep="\t", index=False)
    except Exception:  # noqa: BLE001
        return
    with st.expander(label, expanded=False):
        if caption:
            st.caption(caption)
        st.code(tsv, language=None)   # the ⧉ icon copies the filtered table


# ---------------------------------------------------------------------------
# App login gate
# ---------------------------------------------------------------------------

APP_PASSWORD_ENV = "AQE_APP_PASSWORD"


def require_login() -> None:
    """Password-gate the whole app at the front door.

    The Hugging Face Space is public, so we lock the UI behind a single
    password. This protects *viewing and operating* the app — it deliberately
    does NOT touch the Drive write path, so a scheduled 9am job that runs
    `daily_orchestrator` directly (Claude dispatch, cron, or an app call) keeps
    working unattended.

    The gate is active only when ``AQE_APP_PASSWORD`` is set in the environment
    (an HF Space secret). Locally the var is unset, so the app opens with no
    friction. Auth is per browser session (``st.session_state``), shared across
    all pages, so the user signs in once.

    Call this at the top of every page, right after ``st.set_page_config`` and
    before any other rendering or data loading. When not authenticated it
    renders the sign-in form and halts the page with ``st.stop()``.
    """
    import hmac
    import os

    import streamlit as st

    # Start the HF keep-alive pinger + daily scheduler once per process (no-ops
    # locally). Placed here because every page calls require_login() right after
    # set_page_config.
    try:
        from src.ui.keepalive import start_keepalive
        start_keepalive()
        from src.ui.daily_job import start_daily_job
        start_daily_job()
        from src.ui.alert_job import start_alert_job
        start_alert_job()
    except Exception:  # noqa: BLE001
        pass

    expected = os.environ.get(APP_PASSWORD_ENV)
    if not expected:
        return  # no password configured -> app is open (local use)
    if st.session_state.get("aqe_authenticated"):
        return  # already signed in this session

    st.title("AQE — sign in")
    st.caption("This deployment is password-protected.")
    pw = st.text_input("Password", type="password", key="_aqe_login_pw")
    if st.button("Sign in", type="primary"):
        if hmac.compare_digest(pw or "", expected):
            st.session_state["aqe_authenticated"] = True
            st.session_state.pop("_aqe_login_pw", None)  # don't retain plaintext
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

CAPITAL = 70_000
RISK_PCT = 0.03
RISK_BUDGET = CAPITAL * RISK_PCT  # 2100

ETF_NAMES = {
    "XLK": "Technology", "XLC": "Comm Services", "XLY": "Consumer Discr",
    "XLP": "Consumer Staples", "XLF": "Financials", "XLV": "Healthcare",
    "XLI": "Industrials", "XLE": "Energy", "XLU": "Utilities",
    "XLRE": "Real Estate", "XLB": "Materials",
}


# ---------- data loading ----------

def file_hash(p: Path) -> str:
    if not p.exists():
        return "missing"
    s = p.stat()
    return f"{s.st_mtime_ns}:{s.st_size}"


def load_shortlist() -> dict | None:
    """Load the daily pipeline shortlist JSON."""
    path = OUTPUT_DIR / "shortlist.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_active_recipe() -> dict:
    """Load active_recipe.json (dual format: longlist + precision)."""
    path = DATA_DIR / "active_recipe.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def load_json(filename: str) -> dict | list | None:
    """Load a JSON file from data/ directory."""
    path = DATA_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


# ---------- subprocess runner ----------

def run_module_streaming(module: str, label: str, progress_placeholder, status_placeholder) -> int:
    """Run `python -m <module>` and stream stdout to a Streamlit placeholder."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", module],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    buf: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        buf.append(line.rstrip())
        progress_placeholder.code("\n".join(buf[-20:]))
    rc = proc.wait()
    now_sgt = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S SGT")
    if rc == 0:
        status_placeholder.success(f"{label} finished — {now_sgt}")
    else:
        status_placeholder.error(f"{label} exited with code {rc}. Last output:\n" + "\n".join(buf[-5:]))
    return rc


# ---------- formatting helpers ----------

def fmt_pct(x: float) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "---"
    return f"{x * 100:.1f}%"


def fmt_num(x: float, spec: str) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "---"
    return format(x, spec)
