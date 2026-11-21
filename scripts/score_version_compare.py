"""Old-vs-new list membership for the SAME date: the first-run report for the score-version cutover (conductor 2026-11-21).

Reads a scores frame that carries both calculations side by side and applies the same gates to each:
  * `scores_daily.parquet` after the switch: live columns vs `<field>_legacy` columns.
  * the research extract (`aqe_research_extract_v2_*.parquet`): old columns vs `_v2` columns (`--new-suffix _v2 --old-suffix ""`).
Gates (data/active_recipe.json, unchanged by the PM): the Aggregate Longlist (SC_MOM >= sc_mom_min, Flow, Energy, Structure, MP >= their minimums, Elder >= elder_min) and the
standalone Elder list (Elder >= 8). Output: counts, overlap, and the names ADDED and DROPPED by the new calculation. Read-only; prints JSON; `--out` writes it too.

    python -m scripts.score_version_compare [--scores PATH] [--date YYYY-MM-DD] [--old-suffix _legacy] [--new-suffix ""] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ELDER_LIST_MIN = 8
# gate field -> the column stem under each suffix (mp_100's v2 twin is named mp_score_v2)
FIELDS = {"sc": "sc_momentum", "flow": "flow_100", "energy": "energy_100", "structure": "structure_100", "mp": "mp_100", "elder": "elder_score"}
V2_NAME = {"mp_100": "mp_score_v2"}


def _col(stem: str, suffix: str) -> str:
    if suffix == "_v2":
        return V2_NAME.get(stem, stem + "_v2")
    return stem + suffix


def recipe() -> dict:
    return json.loads((ROOT / "data" / "active_recipe.json").read_text(encoding="utf-8"))["longlist"]


def members(df: pd.DataFrame, suffix: str, rec: dict | None = None) -> dict[str, set]:
    """{'longlist': {...}, 'elder': {...}} for one date's rows, using the columns under `suffix` (a NaN input never passes a gate)."""
    rec = rec or recipe()
    c = {k: df[_col(v, suffix)] for k, v in FIELDS.items()}
    ll = ((c["sc"] >= rec["sc_mom_min"]) & (c["flow"] >= rec["flow_min"]) & (c["energy"] >= rec["energy_min"]) & (c["structure"] >= rec["structure_min"])
          & (c["mp"] >= rec["mp_min"]) & (c["elder"] >= rec["elder_min"]))
    el = c["elder"] >= ELDER_LIST_MIN
    return {"longlist": set(df.loc[ll, "ticker"]), "elder": set(df.loc[el, "ticker"])}


def compare(df: pd.DataFrame, date, old_suffix: str, new_suffix: str, rec: dict | None = None) -> dict:
    d = pd.Timestamp(date).normalize()
    day = df[pd.to_datetime(df["date"]).dt.normalize() == d]
    if day.empty:
        raise SystemExit(f"no rows for {d.date()}")
    old, new = members(day, old_suffix, rec), members(day, new_suffix, rec)
    out = {"date": str(d.date()), "rows": int(len(day)), "old_columns": old_suffix or "live", "new_columns": new_suffix or "live"}
    for name in ("longlist", "elder"):
        o, n = old[name], new[name]
        out[name] = {"old_count": len(o), "new_count": len(n), "in_both": len(o & n), "overlap_of_old_pct": round(100.0 * len(o & n) / len(o), 1) if o else None,
                     "added_by_new": sorted(n - o), "dropped_by_new": sorted(o - n)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--old-suffix", default="_legacy")
    ap.add_argument("--new-suffix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    path = Path(a.scores) if a.scores else ROOT / "data" / "scores_daily.parquet"
    cols = ["date", "ticker"] + [_col(v, s) for v in FIELDS.values() for s in {a.old_suffix, a.new_suffix}]
    df = pd.read_parquet(path, columns=cols)
    date = a.date or pd.to_datetime(df["date"]).max()
    res = compare(df, date, a.old_suffix, a.new_suffix)
    txt = json.dumps(res, indent=1)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
