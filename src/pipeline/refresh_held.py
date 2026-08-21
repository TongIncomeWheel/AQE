"""Held-book-only refresh — fast, targeted incident-response path.

The full daily pipeline pulls the ~800-name scan universe from FMP before it
does anything else (~15-20 min, entirely FMP-bound) — and that pull is a
single point of failure for the held book too, even though the held book is
usually a dozen names or fewer. 2026-08-21: a transient FMP connection drop at
ticker 358/820 took the whole run down, and the held-book refresh bundled
inside it went down with it.

This module refreshes ONLY what the held book needs and nothing else:

  1. The PTJ journal itself (src.data.ptj — carries the 2026-08-21 monotonic
     guard, so a stale fetch here can't regress what's already published).
  2. Fresh price bars for the held tickers ONLY (src.data.panel_builder.
     pull_tickers) — ~10 FMP calls instead of ~800, low failure surface, and
     merges into the existing panel rather than replacing it.
  3. A full score recompute (src.scanner.score_runner.build_scores) — pure
     computation over the (now held-freshened) cached panel, no FMP calls.
     Runs for every ticker in the panel, not just held names, because several
     engines (Pipeline Rank, RS leadership, sector RRG) are cross-sectional
     and need the full universe's distribution to score anyone correctly.
  4. A full export rebuild (src.data.drive_sync.export_to_drive) — again pure
     computation from cached parquet + shortlist.json. daily_list/lens_ranking
     are whatever the last full pipeline run produced; held_positions/
     held_book are freshly recomputed from steps 1-3.
  5. Publish the two artifacts that actually changed to GitHub.

Safe to run standalone, any time, without touching FMP quota for the ~790
names nobody holds. Exception/error-management path: when the full pipeline
is down, degraded, or you just need the held book right now, this is the
button — not a 20-minute all-or-nothing re-run.

Run:
    python -m src.pipeline.refresh_held
"""

from __future__ import annotations

import sys


def refresh_held() -> dict:
    from src.data import ptj

    print("[refresh_held] Step 1: PTJ journal refresh...")
    held = ptj.refresh_held_positions()
    status = ptj.ptj_status()
    print(f"  {len(held)} held position(s), status={status}")
    if status == "stale_fetch_rejected":
        cache = ptj.load_ptj_cache()
        print(f"  [WARN] this run's own fetch was rejected as stale — kept "
              f"the already-published book instead: {cache.get('rejected_fetch')}")
    elif status != "live":
        print(f"  [WARN] status={status} — not a fresh fetch this run, "
              f"proceeding with whatever is cached")

    tickers = sorted({p.get("ticker") for p in held
                      if p.get("ticker") and p.get("type", "STK") == "STK"})
    if not tickers:
        print("  No held equity tickers — nothing to price or score.")
        return {"ok": True, "held_count": len(held), "tickers": [],
                "priced": None, "export": None, "github": None}

    print(f"[refresh_held] Step 2: price pull for {len(tickers)} held "
          f"ticker(s): {tickers}")
    from src.data.panel_builder import pull_tickers
    from src.data.universe import BENCHMARK
    # SPY is a hard dependency for scoring (RS-vs-SPY, beta, excess return —
    # mp.compute/structure.compute/health.compute/readiness.compute all take
    # spy_daily). On a container with no persisted panel (a fresh GitHub
    # Actions runner, unlike the HF Space's warm local disk) the panel would
    # otherwise contain ONLY the held tickers, spy_daily would come back
    # empty, and every held ticker's score computation would fail silently —
    # discovered 2026-08-21 when this produced a scores_daily.parquet with 0
    # rows and no warning anywhere.
    pull_result = pull_tickers(sorted(set(tickers) | {BENCHMARK}))
    if pull_result.get("failed"):
        print(f"  [WARN] {len(pull_result['failed'])} held ticker(s) failed "
              f"to price this run: {pull_result['failed']} — scoring will "
              f"run on whatever bars are already cached for them")

    print("[refresh_held] Step 3: recompute scores...")
    from src.scanner.score_runner import build_scores
    build_scores()

    from src.data.paths import SCORES_DAILY
    import pandas as _pd
    scored_tickers: set = set()
    if SCORES_DAILY.exists():
        scored_tickers = set(_pd.read_parquet(SCORES_DAILY, columns=["ticker"])["ticker"])
    unscored = sorted(set(tickers) - scored_tickers)
    if unscored:
        print(f"  [WARN] {len(unscored)} held ticker(s) have NO score row "
              f"after this run: {unscored} — their export fields will read "
              f"null. Usually too little price history (<60 bars) or a "
              f"per-ticker engine failure; check the [score] lines above.")

    print("[refresh_held] Step 4: rebuild export (held block + scores "
          "refreshed; daily_list/lens_ranking unchanged from the last full "
          "run)...")
    from src.data.drive_sync import export_to_drive
    export_result = export_to_drive()

    print("[refresh_held] Step 5: publish to GitHub...")
    from src.data import github_sync
    gh_result = github_sync.publish_daily_outputs(
        names=("aqe_daily_export.json", "held_positions.json"))
    if gh_result.get("ok"):
        print(f"  GitHub: {gh_result.get('written')} file(s) published")
    else:
        print(f"  [WARN] GitHub publish: {gh_result.get('reason')}")

    return {"ok": True, "held_count": len(held), "tickers": tickers,
            "priced": pull_result, "export": export_result, "github": gh_result}


if __name__ == "__main__":
    result = refresh_held()
    sys.exit(0 if result.get("ok") else 1)
