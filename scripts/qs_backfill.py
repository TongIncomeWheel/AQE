"""QS backfill — give the engine just enough memory to be honest on day one.

QS reads two things it cannot compute from today alone:

  `qs_persist`   how many of the PRIOR 5 sessions the name also qualified.
                 With no history every name reads 0, lands in the `0-1`
                 persist band, and the whole book prices a notch low — while
                 the output looks completely normal. That is the failure this
                 script exists to prevent.

  regime cell    trend_200 / vol_60 against expanding terciles. The tercile
                 boundaries are fitted on prior days, so a series with no
                 history classifies as `unclassified`, and an unclassified
                 regime has no measured base rate for conviction to work from.

MINIMUM BY DESIGN (PM ruling 2026-08-04). This deliberately does NOT rebuild
years of history. Persistence looks back 5 sessions, so ~15 gives a full
window plus slack; the regime series needs more to fit a tercile, and it is
cheap because it is one index, not one series per ticker.

    python -m scripts.qs_backfill              # default, ~15 sessions of hits
    python -m scripts.qs_backfill --days 30    # more slack
    python -m scripts.qs_backfill --dry-run    # report, write nothing

SURVIVORSHIP NOTE, stated rather than hidden: history is replayed against
TODAY'S universe membership, because point-in-time membership is not stored.
A name that dropped out of the universe last week is absent from last week's
replayed cross-section. The effect is small at this depth and self-corrects
forward as real daily runs accumulate, but it is why this is a floor for
`qs_persist` and not a research dataset.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.paths import PANEL_DAILY, SCORES_DAILY   # noqa: E402
from src.data import qs_store                          # noqa: E402
from src.data.sector_mapper import load_sector_map     # noqa: E402
from src.engines import qs_daily as QD                 # noqa: E402
from src.engines import qs_engine as E                 # noqa: E402
from src.engines import qs_fields as F                 # noqa: E402

DEFAULT_DAYS = 15


def backfill(days: int = DEFAULT_DAYS, dry_run: bool = False) -> dict:
    if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
        return {"ok": False, "reason": "panel/scores parquet missing — "
                                       "run the daily pipeline first"}
    book, cal = QD.load_config()
    sector_map = load_sector_map() or {}

    panel = pd.read_parquet(PANEL_DAILY,
                            columns=["date", "ticker", "close", "volume"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    scores = pd.read_parquet(SCORES_DAILY)
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

    # --- regime series: computed over ALL available history, not just `days`.
    # The terciles are expanding, so a short series would classify almost
    # everything as unclassified. It is one index — cheap regardless of depth.
    print("[qs-backfill] Building the equal-weight index + regime series...")
    per, regime_df = F.compute_all(panel, sector_map=sector_map)
    classified = int((regime_df["regime_cell"] != "unclassified").sum())
    print(f"  {len(regime_df)} sessions | {classified} classified "
          f"| {len(regime_df) - classified} unclassified (insufficient history)")
    if not dry_run:
        qs_store.upsert_regime_series(regime_df.reset_index().rename(
            columns={"index": "date"}))

    # --- hits: only the recent window persistence actually reads.
    common = sorted(set(scores["date"].unique()) & set(panel["date"].unique()))
    target = common[-days:] if days else common
    if not target:
        return {"ok": False, "reason": "no overlapping panel/scores dates"}
    print(f"[qs-backfill] Replaying {len(target)} sessions "
          f"({pd.Timestamp(target[0]).date()} -> {pd.Timestamp(target[-1]).date()})")

    written, skipped = 0, 0
    for d in target:
        asof = pd.Timestamp(d)
        elig = set(QD.eligible_tickers(panel, asof))
        day = scores[scores["date"] == asof].copy()
        if day.empty or not elig:
            skipped += 1
            continue
        fields_today = per[per["date"] == asof]
        day = day.merge(fields_today.drop(columns=["date"]), on="ticker",
                        how="left")
        day = day[day["ticker"].isin(elig)]
        if day.empty:
            skipped += 1
            continue

        # Only recipe_hits + lens_total are stored, so the expensive parts of
        # a full run (vetoes, probability, conviction, levels, why) are skipped
        # entirely — persistence reads nothing else.
        day = E.score_lenses(day)
        hits = E.count_recipe_hits(day, book["recipes"])
        rows = pd.DataFrame({
            "date": asof, "ticker": day["ticker"].to_numpy(),
            "recipe_hits": hits, "lens_total": day["lens_total"].to_numpy(),
            "eligible": True,
        })
        if not dry_run:
            written += qs_store.upsert_daily_hits(rows)
        else:
            written += len(rows)
        qs_days = int((hits >= qs_store.QS_DAY_MIN_HITS).sum())
        print(f"  {asof.date()}  eligible {len(day):>4}  "
              f"QS-qualifying {qs_days:>4}")

    status = qs_store.store_status() if not dry_run else {}
    return {"ok": True, "sessions": len(target) - skipped, "skipped": skipped,
            "rows": written, "regime_sessions": len(regime_df),
            "regime_classified": classified, "dry_run": dry_run,
            "status": status}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help=f"sessions of recipe_hits to replay (default {DEFAULT_DAYS}; "
                         "persistence only reads 5)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen, write nothing")
    a = ap.parse_args()

    print("=" * 68)
    print("  QS BACKFILL — minimum memory so day one is honest")
    print("=" * 68)
    r = backfill(days=a.days, dry_run=a.dry_run)
    print("-" * 68)
    if not r["ok"]:
        print(f"  FAILED: {r['reason']}")
        sys.exit(1)
    print(f"  Sessions replayed : {r['sessions']} ({r['skipped']} skipped)")
    print(f"  Hit rows written  : {r['rows']:,}")
    print(f"  Regime sessions   : {r['regime_sessions']} "
          f"({r['regime_classified']} classified)")
    if r["dry_run"]:
        print("  DRY RUN — nothing written.")
    else:
        st = r["status"]
        print(f"  Stored coverage   : {st.get('hits_dates')} sessions "
              f"({st.get('hits_from')} -> {st.get('hits_to')})")
        ready = st.get("persist_ready")
        print(f"  persist_ready     : {ready}"
              + ("" if ready else
                 "   <-- qs_persist will read low until 5 sessions exist"))
    print("=" * 68)


if __name__ == "__main__":
    main()
