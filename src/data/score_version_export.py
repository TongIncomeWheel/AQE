"""Score-version blocks for the daily export (PM 2026-11-21 cutover): `score_version`, `score_exclusions`, and the `<field>_legacy` values on every row.

Reads the scores cache and the build's diagnostics file; adds only NEW keys. Loud, never silent: an unreadable cache, a mixed or unstamped cache, or a build with no
diagnostics is reported in the block, never passed over.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from src.engines import score_version as SV

EARN_TREATMENT = ("A name with no earnings report date known on/after the bar is scored WITHOUT the earnings component and the Structure total is rescaled to the same 0-100 range: "
                  "structure_100 = (rs_spy + rs_accel + base + position + resist + weekly) / 85 x 100, i.e. the usual total/95 x 100 scaled by 95/(95-10), where 10 is the earnings "
                  "component's maximum. Every composite that rolls up Structure (sc_momentum, sc_position, the gates) follows. A missing value is never credited as good and never "
                  "shrinks the lists; the row is flagged earn_data: 'missing'.")
LEGACY_RETENTION_NOTE = ("kept beside the live value for at least 4 weeks after the cutover so the change can be compared and rolled back; under v1 each legacy field "
                         "equals its live field")


def _py(v):
    """JSON-safe python value: NaN -> None, numpy scalars -> python."""
    if v is None:
        return None
    if hasattr(v, "item"):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def load_context(scores_path: Path | None = None) -> dict:
    from src.data.paths import SCORES_DAILY
    path = scores_path or SCORES_DAILY
    ctx = {"active": SV.active(), "source": SV.source(), "cutover_date": SV.cutover_date(), "rows": {}, "versions": [], "problem": None, "diag": None, "legacy_columns": [],
           "status": "live", "reason": None}
    if not path.exists():
        ctx.update(status="error", reason=f"{path.name} missing", problem=f"{path.name} missing")
        return ctx
    import pyarrow.parquet as pq
    names = pq.read_schema(path).names
    ctx["legacy_columns"] = [c for c in names if c.endswith(SV.LEGACY)]
    if SV.VERSION_COLUMN in names:
        vers = pd.read_parquet(path, columns=[SV.VERSION_COLUMN])[SV.VERSION_COLUMN].dropna().astype(str).unique().tolist()
        ctx["versions"] = sorted(vers)
        ctx["problem"] = SV.cache_problem(pd.DataFrame({SV.VERSION_COLUMN: vers}))
    else:
        ctx["problem"] = SV.cache_problem(pd.DataFrame({"x": [0]}))                       # no stamp: the reason text for a pre-switch cache
    if ctx["legacy_columns"]:
        d = pd.read_parquet(path, columns=["date"])["date"]
        latest = pd.to_datetime(d).max()
        cols = ["ticker"] + ([SV.VERSION_COLUMN] if SV.VERSION_COLUMN in names else []) + (["earn_data"] if "earn_data" in names else []) + ctx["legacy_columns"]
        df = pd.read_parquet(path, columns=cols, filters=[("date", "==", latest)])
        for rec in df.to_dict("records"):
            ctx["rows"][rec.pop("ticker")] = {k: _py(v) for k, v in rec.items()}
    dp = path.with_name("score_diagnostics_v2.json")
    try:
        ctx["diag"] = json.loads(dp.read_text(encoding="utf-8")) if dp.exists() else None
    except (OSError, ValueError):
        ctx["diag"] = None
    return ctx


def blocks(ctx: dict) -> tuple[dict, dict]:
    """(`score_version`, `score_exclusions`) for the export."""
    sv = {"status": ctx["status"], "reason": ctx["reason"], "version": ctx["active"], "source": ctx["source"], "cutover_date": ctx["cutover_date"],
          "legacy_suffix": SV.LEGACY, "legacy_fields": sorted(c[:-len(SV.LEGACY)] for c in ctx["legacy_columns"]), "legacy_note": LEGACY_RETENTION_NOTE,
          "scores_cache": {"versions": ctx["versions"], "problem": ctx["problem"]},
          "meaning": ("v1 = the old calculation is live. v2 = the corrected calculation is live (PM 2026-11-21): sub-components, engine scores, composites, Pipeline Rank, BQ, Elder "
                      "and the gates that read them. A mixed or unknown version is a data_quality failure, never a quiet default."),
          "rollback": f"set {SV.ENV_VAR}=v1 or data/score_version.json version=v1; both calculations are computed in the same pass"}
    diag = ctx.get("diag")
    missing = (diag or {}).get("earn_data_missing")
    sv["earn_data"] = {
        "treatment": EARN_TREATMENT,
        "missing_count": None if missing is None else len(missing),
        "tickers": None if missing is None else sorted(missing),
        "by_reason": None if missing is None else {why: {"count": sum(1 for v in missing.values() if v == why), "tickers": sorted(t for t, v in missing.items() if v == why)}
                                                   for why in sorted(set(missing.values()))},
        "no_history_count": None if missing is None else sum(1 for v in missing.values() if v == "no earnings history at all"),
        "no_next_date_count": None if missing is None else sum(1 for v in missing.values() if v == "no next report date scheduled yet"),
        "note": ("each such row carries earn_data: 'missing' (informational under v1: the live score still uses the old default credit there). The two causes are counted apart: "
                 "'no earnings history at all' (funds, new listings) and 'no next report date scheduled yet' (a real company between a report and its next date being published). "
                 "A calendar outage shows as a jump in no_next_date_count, never as a quiet rescale."),
    }
    unscorable = (diag or {}).get("v2_unscorable")
    live = ctx["active"] == "v2"
    if unscorable is None:
        ex = {"status": "unknown", "reason": "no score diagnostics beside the scores cache (built before the switch, or the diagnostics write failed): the exclusion list is NOT KNOWN, not empty",
              "applies_now": live}
    else:
        by_reason: dict = {}
        for t, why in sorted(unscorable.items()):
            by_reason.setdefault(why, []).append(t)
        ex = {"status": "live", "applies_now": live, "total": len(unscorable),
              "basis": ("GENUINE failures only: names for which the corrected calculation cannot form any score on the last bar (a required input other than earnings is unavailable; NaN, never a default credit). "
                        "A missing earnings history is NOT an exclusion: see score_version.earn_data. "
                        + ("They are EXCLUDED from every list and from daily_list." if live else "Under v1 they are still scored on the old calculation; this is the list the cutover WOULD exclude.")),
              "by_reason": {why: {"count": len(ts), "tickers": ts} for why, ts in by_reason.items()},
              "scores_built_with": (diag or {}).get("score_version"), "diagnostics_generated_at": (diag or {}).get("generated_at")}
    return sv, ex


def attach_legacy(rows: list[dict], ctx: dict) -> int:
    """Add `<field>_legacy` (and `score_version`) from the latest scores row to each row of a ticker-keyed list. Returns how many rows got them."""
    n = 0
    for r in rows or []:
        lr = ctx["rows"].get((r or {}).get("ticker"))
        if lr:
            r.update(lr)
            n += 1
    return n
