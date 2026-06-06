"""Shared utilities for the multi-page Streamlit app.

Contains: path constants, data loaders, formatting helpers, onboarding,
subprocess runner. Imported by Page 1 (Scanner), Page 2 (Math Lab),
and Page 3 (Positions).

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


def load_export() -> dict | None:
    """Load `output/aqe_daily_export.json` (the canonical cloud-mode source)."""
    if not EXPORT_JSON.exists():
        return None
    with open(EXPORT_JSON) as f:
        return json.load(f)

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

def run_module_streaming(module: str, label: str, progress_placeholder, status_placeholder,
                         extra_env: dict | None = None) -> int:
    """Run `python -m <module>` and stream stdout to a Streamlit placeholder.

    extra_env -- optional env vars merged into the subprocess environment for
        this run only (e.g. the AQE_WRITE_TOKEN that authorizes the pipeline's
        Drive export on the public Space). Never mutates the parent process.
    """
    import os
    from datetime import datetime
    from zoneinfo import ZoneInfo

    env = os.environ.copy()
    if extra_env:
        env.update({k: v for k, v in extra_env.items() if v is not None})

    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", module],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
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
