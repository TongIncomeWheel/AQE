"""Single source of truth for AQE data + output directories.

Defaults to project-relative `data/` and `output/`. Honours environment
variables `AQE_DATA_DIR` and `AQE_OUTPUT_DIR` for deployments where the
working dir is read-only (Hugging Face Spaces persistent storage at `/data`,
Docker volumes, etc).

Usage:

    from src.data.paths import DATA_DIR, OUTPUT_DIR
    PANEL = DATA_DIR / "panel_daily.parquet"

Local development:
    DATA_DIR   -> <project>/data
    OUTPUT_DIR -> <project>/output

Hugging Face Spaces with persistent storage:
    set AQE_DATA_DIR=/data  in Space variables
    set AQE_OUTPUT_DIR=/data/output  (or any sub-path)

Any other host with mounted persistent disk: set the env vars to whatever
the mount path is, and AQE will read/write there without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(env_var: str, default: Path) -> Path:
    """Return env-var override if set, else default. Always create the dir."""
    override = os.environ.get(env_var)
    p = Path(override).expanduser().resolve() if override else default
    p.mkdir(parents=True, exist_ok=True)
    return p


DATA_DIR: Path = _resolve("AQE_DATA_DIR", PROJECT_ROOT / "data")
OUTPUT_DIR: Path = _resolve("AQE_OUTPUT_DIR", PROJECT_ROOT / "output")


# Convenience constants used across the codebase.
PANEL_DAILY = DATA_DIR / "panel_daily.parquet"
PANEL_WEEKLY = DATA_DIR / "panel_weekly.parquet"
SPY_DAILY = DATA_DIR / "spy_daily.parquet"
SCORES_DAILY = DATA_DIR / "scores_daily.parquet"

SHORTLIST_PATH = OUTPUT_DIR / "shortlist.json"
EXPORT_JSON = OUTPUT_DIR / "aqe_daily_export.json"
DASHBOARD_PATH = OUTPUT_DIR / "dashboard.txt"


if __name__ == "__main__":
    # Quick diagnostic.
    print("PROJECT_ROOT :", PROJECT_ROOT)
    print("DATA_DIR     :", DATA_DIR,
          "(override active)" if os.environ.get("AQE_DATA_DIR") else "")
    print("OUTPUT_DIR   :", OUTPUT_DIR,
          "(override active)" if os.environ.get("AQE_OUTPUT_DIR") else "")
    print()
    print(f"  PANEL_DAILY  = {PANEL_DAILY} exists={PANEL_DAILY.exists()}")
    print(f"  PANEL_WEEKLY = {PANEL_WEEKLY} exists={PANEL_WEEKLY.exists()}")
    print(f"  SPY_DAILY    = {SPY_DAILY} exists={SPY_DAILY.exists()}")
    print(f"  SCORES_DAILY = {SCORES_DAILY} exists={SCORES_DAILY.exists()}")
    print(f"  SHORTLIST    = {SHORTLIST_PATH} exists={SHORTLIST_PATH.exists()}")
    print(f"  EXPORT_JSON  = {EXPORT_JSON} exists={EXPORT_JSON.exists()}")
