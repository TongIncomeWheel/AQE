"""Daily Pipeline Orchestrator — produces a scored shortlist each morning.

Steps:
1. Incremental bar pull (only new bars since last run)
2. Stage 1: Pipeline Rank for full universe (cheap — daily bars only)
3. Stage 2: Full scoring for top-50 candidates
4. SRM sector grading
5. Regime detection (VIX + Hurst)
6. PTRS computation with context modifiers
7. Output: shortlist JSON + text dashboard

Run:
    python -m src.pipeline.daily_orchestrator
    or double-click run_daily.bat
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.earnings import load_earnings, pull_earnings_calendar, save_earnings
from src.data.fmp_client import FMPClient, FMPError
from src.data.paths import (
    DATA_DIR,
    OUTPUT_DIR,
    PANEL_DAILY,
    PANEL_WEEKLY,
    SPY_DAILY,
    SHORTLIST_PATH,
    DASHBOARD_PATH,
)
from src.data.universe import load_universe
from src.engines import pipeline_rank, srm
from src.engines.srm import GICS_ETFS, TICKER_TO_SECTOR, grade_all_sectors, get_sector_health, GRADE_TO_SH
from src.data.sector_mapper import load_sector_map, ETF_TO_NAME
from src.analyzer.ptrs import compute_ptrs, classify_vix_regime
from src.analyzer.regime import compute_regime

STAGE2_MAX = 50
PIPE_RANK_CUTOFF = 60
SIGNAL_MAX_AGE = 2          # only show picks where cross-up fired within last N trading days


def run_daily(run_date: date | None = None, skip_pull: bool = False) -> dict:
    """Execute the full daily pipeline. Returns the shortlist dict."""
    run_date = run_date or date.today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[daily] AQE Daily Pipeline - {run_date}")
    print("=" * 60)

    # Step 0a: Restore universe from Drive if container has no local copy
    # (HF containers have ephemeral filesystems — this recovers the universe
    # from the last Drive backup so we don't need a full FMP screener pull)
    try:
        from src.data.universe import restore_universe_from_drive
        if restore_universe_from_drive():
            print("[daily] Step 0a: Restored universe.txt from Drive")
    except Exception as exc:
        print(f"  [WARN] Drive universe restore: {exc}")

    # Step 0b: Pull the latest held-positions journal (PTJ) from Drive so the
    # export can flag held names and attach the engine's read on them.
    try:
        from src.data.ptj import refresh_held_positions
        _held = refresh_held_positions()
        print(f"[daily] Step 0b: Held positions from PTJ — {len(_held)}")
    except Exception as exc:
        print(f"  [WARN] PTJ fetch: {exc}")

    # Step 0: Universe is a FIXED, manually-curated list (the "fishing net").
    # Auto-refresh from the FMP screener is intentionally disabled — it ballooned
    # the list to ~1800 tickers. To change the universe, overwrite universe.txt
    # (or universe.csv) in the Drive folder, or use the app's Universe Upload.

    # Step 1: Load cached data (incremental pull handled by panel_builder)
    if not skip_pull:
        print("[daily] Step 1: Incremental bar pull...")
        _incremental_pull(run_date)
    else:
        print("[daily] Step 1: Skipping pull (--no-pull)")

    panel = pd.read_parquet(PANEL_DAILY)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    spy = pd.read_parquet(SPY_DAILY) if SPY_DAILY.exists() else panel[panel["ticker"] == "SPY"]
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()

    # Step 1b: Refresh earnings calendar
    print("[daily] Step 1b: Earnings calendar refresh...")
    try:
        earnings_cal = pull_earnings_calendar()
        save_earnings(earnings_cal)
        print(f"  {len(earnings_cal)} tickers with upcoming earnings dates")
    except Exception as exc:
        print(f"  [WARN] Earnings pull failed: {exc}")
        earnings_cal = load_earnings()

    # Step 1c: Rebuild the full-universe score cache if it lags the panel.
    # The watchlist and the recipe / Precision Edge screens all read
    # scores_daily.parquet; without this they would screen against stale
    # scores whenever the pull advanced the panel since the last score build.
    print("[daily] Step 1c: Score cache refresh...")
    try:
        from src.scanner.score_runner import SCORES_DAILY, build_scores

        panel_latest = panel["date"].max()
        scores_latest = None
        if SCORES_DAILY.exists():
            _sd_dates = pd.read_parquet(SCORES_DAILY, columns=["date"])
            if not _sd_dates.empty:
                scores_latest = pd.to_datetime(_sd_dates["date"]).max().normalize()
        if scores_latest is None or scores_latest < panel_latest:
            _have = scores_latest.date() if scores_latest is not None else "none"
            print(f"  Scores ({_have}) behind panel ({panel_latest.date()}) — rebuilding...")
            build_scores()
        else:
            print(f"  Score cache already current ({scores_latest.date()}) — skip rebuild")
    except Exception as exc:
        print(f"  [WARN] Score cache refresh failed: {exc}")

    # Step 2: Pipeline Rank — screen full universe
    print("[daily] Step 2: Pipeline Rank screening...")
    t0 = time.time()
    ranked = _pipeline_rank_screen(panel, run_date)
    print(f"  {len(ranked)} tickers ranked in {time.time() - t0:.1f}s")
    print(f"  {sum(1 for _, r, _ in ranked if r >= PIPE_RANK_CUTOFF)} pass cutoff ({PIPE_RANK_CUTOFF})")

    rank_lookup = {t: (r, fip) for t, r, fip in ranked}
    top_tickers = [t for t, r, _ in ranked if r >= PIPE_RANK_CUTOFF][:STAGE2_MAX]

    # Step 3: Full scoring for top candidates
    print(f"[daily] Step 3: Full scoring for top {len(top_tickers)} candidates...")
    scores = _full_scoring(panel, top_tickers, run_date, earnings_cal=earnings_cal)
    print(f"  {len(scores)} candidates scored")

    # Step 3b: Persist scores + earnings to SQLite
    try:
        from src.data.db import init_db, upsert_scores, upsert_earnings, upsert_srm
        init_db()
        if scores:
            score_df = pd.DataFrame(scores)
            score_df["date"] = str(run_date)
            upsert_scores(score_df)
        if earnings_cal:
            upsert_earnings(earnings_cal)
    except Exception as exc:
        print(f"  [WARN] SQLite persist: {exc}")

    # Step 4: SRM sector grading
    print("[daily] Step 4: SRM sector grading...")
    sector_grades = _compute_srm(panel)
    print(f"  Grades: {_summarize_grades(sector_grades)}")
    try:
        for etf, info in sector_grades.items():
            upsert_srm(etf, run_date, info.get("grade", "UNKNOWN"), info.get("sh", 0))
    except Exception:
        pass

    # Step 5: Regime detection
    print("[daily] Step 5: Regime detection...")
    regime = _compute_regime(spy)
    print(f"  VIX regime: {regime['vix_regime']} | Hurst: {regime['hurst']:.3f} ({regime['hurst_regime']})")

    # Step 6: PTRS + disposition
    print("[daily] Step 6: PTRS computation...")
    vix = regime.get("vix", 18.0)
    candidates = _compute_ptrs_all(scores, sector_grades, vix, regime)
    candidates.sort(key=lambda c: c.get("ptrs", 0), reverse=True)

    # Step 6b: BC layer (if outcome data exists)
    outcome_path = DATA_DIR / "optimizer_results.json"
    if outcome_path.exists():
        try:
            from src.backtest.confidence import batch_confidence
            # Load outcomes from the scores (which contain DSL R data)
            scores_path = DATA_DIR / "scores_daily.parquet"
            if scores_path.exists():
                outcome_db = pd.read_parquet(scores_path)
                if "dsl_r_realized" not in outcome_db.columns:
                    outcome_db = pd.DataFrame()
            else:
                outcome_db = pd.DataFrame()

            if not outcome_db.empty:
                bc_results = batch_confidence(candidates, outcome_db)
                for c, bc in zip(candidates, bc_results):
                    if bc is not None:
                        c["bc_score"] = bc.score
                        c["bc_tier"] = bc.tier
                        c["bc_modifier"] = bc.modifier
                    else:
                        c["bc_score"] = None
                        c["bc_tier"] = "INSUFFICIENT"
                        c["bc_modifier"] = 0.0
        except Exception:
            pass

    # Filter: only FULL/HALF/QUARTER dispositions
    shortlist = [c for c in candidates if c["disposition"] in ("FULL", "HALF", "QUARTER")]
    print(f"  {len(shortlist)} candidates pass disposition filter")

    # Step 6b-signal: Keep only fresh signals (cross-up within last 3 trading days)
    # The backtest edge is from the signal day. Stale picks = no edge.
    pre_filter = len(shortlist)
    shortlist = _filter_fresh_signals(shortlist)
    shortlist.sort(key=lambda c: c.get("ptrs", 0), reverse=True)
    print(f"  {len(shortlist)} with fresh signal (last {SIGNAL_MAX_AGE} trading days)")
    if len(shortlist) < pre_filter:
        print(f"  Removed {pre_filter - len(shortlist)} stale picks (cross-up > {SIGNAL_MAX_AGE}d ago)")

    # Step 6c: Recipe signal matches — screen full scored universe
    print("[daily] Step 6c: Recipe signal match screen...")
    recipe_matches, active_recipe = _recipe_match_screen()
    shortlist_tickers = {c["ticker"] for c in shortlist}
    for rm in recipe_matches:
        rm["on_shortlist"] = rm["ticker"] in shortlist_tickers
        pr, fip = rank_lookup.get(rm["ticker"], (0.0, 0.0))
        rm["pipe_rank"] = round(pr, 1)
        rm["fip_quality"] = round(fip, 1)
    # Sort by Pipeline Rank (OOS IC=+0.030), then Floor (OOS IC=+0.005)
    def _floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0), e.get("structure", 0), e.get("mp", 0))
    recipe_matches.sort(key=lambda rm: (rm.get("pipe_rank", 0), _floor(rm)), reverse=True)
    new_from_recipe = sum(1 for rm in recipe_matches if not rm["on_shortlist"])
    print(f"  {len(recipe_matches)} tickers pass longlist recipe | {new_from_recipe} not on Pipeline Rank shortlist")

    # Step 6d: Precision Edge screen — sub-component deep-dive
    print("[daily] Step 6d: Precision Edge screen...")
    precision_matches, precision_recipe = _precision_edge_screen()
    precision_tickers = {pm["ticker"] for pm in precision_matches}
    # Tag shortlist candidates that pass precision
    for c in shortlist:
        c["precision"] = c["ticker"] in precision_tickers
    n_prec = sum(1 for c in shortlist if c["precision"])
    print(f"  {len(precision_matches)} tickers pass Precision Edge | {n_prec} also on shortlist")

    # Step 7: Output
    print("[daily] Step 7: Output...")
    output = _build_output(run_date, regime, sector_grades, shortlist, recipe_matches,
                           active_recipe, precision_matches, precision_recipe,
                           rank_lookup=rank_lookup)
    _write_outputs(output)
    print(f"  Shortlist: {SHORTLIST_PATH}")
    print(f"  Dashboard: {DASHBOARD_PATH}")

    # Step 8: Export to Google Drive
    try:
        from src.data.drive_sync import export_to_drive
        drive_result = export_to_drive()
        if drive_result["status"] == "ok":
            print(f"  Drive export: {drive_result['date']} -> {len(drive_result['written'])} locations")
        elif drive_result["status"] == "partial":
            print(f"  Drive export: local only ({drive_result['reason']})")
        else:
            print(f"  Drive export: skipped ({drive_result.get('reason', 'unknown')})")
    except Exception as exc:
        print(f"  [WARN] Drive export failed: {exc}")

    print("=" * 60)
    print(f"[daily] Done. {len(shortlist)} candidates on today's shortlist.")

    return output


def _incremental_pull(run_date: date) -> None:
    """Pull only bars newer than what's cached."""
    try:
        from src.data.panel_builder import build_panel
        build_panel()
    except Exception as exc:
        print(f"  [WARN] Panel pull had errors: {exc}")


def _pipeline_rank_screen(panel: pd.DataFrame, run_date: date) -> list[tuple[str, float, float]]:
    """Run Pipeline Rank on all tickers, return sorted (ticker, rank, fip_quality) tuples."""
    results = []
    tickers = [t for t in panel["ticker"].unique() if t not in GICS_ETFS and t != "SPY"]

    for ticker in tickers:
        grp = panel[panel["ticker"] == ticker].sort_values("date").reset_index(drop=True)
        if len(grp) < 252:
            continue
        try:
            pr = pipeline_rank.compute(grp)
            if pr.empty:
                continue
            last_rank = pr["pipe_rank"].iloc[-1]
            last_fip = pr["fip_quality"].iloc[-1]
            if pd.notna(last_rank):
                results.append((ticker, float(last_rank), float(last_fip) if pd.notna(last_fip) else 0.0))
        except Exception:
            continue

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _full_scoring(
    panel: pd.DataFrame,
    tickers: list[str],
    run_date: date,
    earnings_cal: dict[str, str] | None = None,
) -> list[dict]:
    """Run full engine suite on selected tickers, return latest scores."""
    from src.engines import bq, elder, energy, flow, k39, mp, scoring, structure
    from src.engines.utils import atr

    spy = pd.read_parquet(SPY_DAILY) if SPY_DAILY.exists() else panel[panel["ticker"] == "SPY"]
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()

    weekly = pd.read_parquet(PANEL_WEEKLY) if PANEL_WEEKLY.exists() else pd.DataFrame()
    if not weekly.empty:
        weekly["date"] = pd.to_datetime(weekly["date"]).dt.normalize()

    daily_groups = {t: g.sort_values("date").reset_index(drop=True)
                    for t, g in panel.groupby("ticker", sort=False) if t in tickers}
    weekly_groups = {}
    if not weekly.empty:
        weekly_groups = {t: g.sort_values("date").reset_index(drop=True)
                        for t, g in weekly.groupby("ticker", sort=False) if t in tickers}

    scores = []
    for ticker in tickers:
        d = daily_groups.get(ticker)
        if d is None or len(d) < 60:
            continue
        w = weekly_groups.get(ticker, pd.DataFrame())

        try:
            flow_df = flow.compute(d)
            energy_df = energy.compute(d)
            mp_df = mp.compute(d, spy_daily=spy)
            structure_df = structure.compute(
                d, spy_daily=spy, weekly=w,
                earnings_cal=earnings_cal, ticker=ticker,
            )
            elder_df = elder.compute(d)
            bq_df = bq.compute(d)
            k39_gate_s, k39_val = k39.compute_k39_gate(w, d["date"])

            sc_m = scoring.compute(
                flow_score=flow_df["flow_100"],
                energy_score=energy_df["energy_100"],
                structure_score=structure_df["structure_100"],
                mp_score=mp_df["mp_score"],
                elder_score=elder_df["elder_score"],
            )
            sc_m_raw = scoring.compute_raw(
                flow_score=flow_df["flow_100"],
                energy_score=energy_df["energy_100"],
                structure_score=structure_df["structure_100"],
                mp_score=mp_df["mp_score"],
            )
            sc_p = scoring.compute_position(
                flow_score=flow_df["flow_100"],
                energy_score=energy_df["energy_100"],
                structure_score=structure_df["structure_100"],
                mp_score=mp_df["mp_score"],
                bq_score=bq_df["bq_100"],
                k39_gate=k39_gate_s,
            )
            sc_p_raw = scoring.compute_position_raw(
                flow_score=flow_df["flow_100"],
                energy_score=energy_df["energy_100"],
                structure_score=structure_df["structure_100"],
                mp_score=mp_df["mp_score"],
                bq_score=bq_df["bq_100"],
            )
            atr14 = atr(d["high"].astype(float), d["low"].astype(float), d["close"].astype(float), n=14)

            from src.data.earnings import days_to_earnings, earn_proximity_score
            earn_days = days_to_earnings(ticker, run_date, earnings_cal or {})
            earn_sc = earn_proximity_score(earn_days)

            scores.append({
                "ticker": ticker,
                "sc_momentum": float(sc_m.iloc[-1]),
                "sc_momentum_raw": float(sc_m_raw.iloc[-1]),
                "sc_position": float(sc_p.iloc[-1]),
                "sc_position_raw": float(sc_p_raw.iloc[-1]),
                "flow_100": float(flow_df["flow_100"].iloc[-1]),
                "energy_100": float(energy_df["energy_100"].iloc[-1]),
                "structure_100": float(structure_df["structure_100"].iloc[-1]),
                "mp_100": float(mp_df["mp_score"].iloc[-1]),
                "elder_score": float(elder_df["elder_score"].iloc[-1]),
                "bq_100": float(bq_df["bq_100"].iloc[-1]),
                "mp_state": str(mp_df["mp_state"].iloc[-1]),
                "close": float(d["close"].iloc[-1]),
                "atr14": float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else 0.0,
                "earn_days": earn_days,
                "earn_score": earn_sc,
            })
        except Exception:
            continue

    return scores


def _compute_srm(panel: pd.DataFrame, trend_days: int = 10) -> dict:
    """Grade all sectors using SRM.

    trend_days=10 adds sh_trend + grade_trend (10-bar history) so PTRS
    context and the export JSON show momentum direction, not just today's grade.
    """
    return grade_all_sectors(panel, trend_days=trend_days)


def _compute_regime(spy: pd.DataFrame) -> dict:
    """Get VIX regime + Hurst exponent."""
    spy_sorted = spy.sort_values("date")
    closes = spy_sorted["close"].values

    # Use last close as VIX proxy if no real VIX data
    # In production this would call FMP quote for ^VIX
    vix = 18.0  # default; will be overridden by FMP quote when available
    try:
        client = FMPClient()
        vix_resp = client._get_json(
            "https://financialmodelingprep.com/stable/quote",
            {"symbol": "^VIX", "apikey": client.config.api_key}
        )
        if isinstance(vix_resp, list) and vix_resp:
            vix = float(vix_resp[0].get("price", 18.0))
        elif isinstance(vix_resp, dict) and "price" in vix_resp:
            vix = float(vix_resp["price"])
    except Exception:
        pass

    return compute_regime(closes, vix, lookback=60)


def _compute_ptrs_all(
    scores: list[dict],
    sector_grades: dict,
    vix: float,
    regime: dict,
) -> list[dict]:
    """Compute PTRS for all scored candidates.

    PTRS = SC_MOMENTUM + SH (sector health only).
    Regime/VIX handles macro sizing separately — no double penalty.
    """
    candidates = []
    for s in scores:
        ticker = s["ticker"]
        sh = get_sector_health(ticker, sector_grades)

        ptrs_result = compute_ptrs(
            engine_score=s["sc_momentum"],
            sh=sh,
        )

        candidate = {**s, **ptrs_result}
        dyn_map = load_sector_map()
        candidate["sector"] = TICKER_TO_SECTOR.get(ticker, dyn_map.get(ticker, "UNKNOWN"))
        candidate["sector_grade"] = _get_grade_for_ticker(ticker, sector_grades)
        candidates.append(candidate)

    return candidates


def _get_grade_for_ticker(ticker: str, sector_grades: dict) -> str:
    """Look up sector grade for a ticker."""
    sector_etf = TICKER_TO_SECTOR.get(ticker)
    if sector_etf is None:
        dyn_map = load_sector_map()
        sector_etf = dyn_map.get(ticker)
    if sector_etf and sector_etf in sector_grades:
        return sector_grades[sector_etf].get("grade", "UNKNOWN")
    return "UNKNOWN"


def _summarize_grades(sector_grades: dict) -> str:
    """One-line summary of sector grades."""
    deploy = [k for k, v in sector_grades.items() if v.get("grade") == "DEPLOY"]
    avoid = [k for k, v in sector_grades.items() if v.get("grade") == "AVOID"]
    parts = []
    if deploy:
        names = [f"{ETF_TO_NAME.get(e, e)} ({e})" for e in deploy]
        parts.append(f"DEPLOY: {', '.join(names)}")
    if avoid:
        names = [f"{ETF_TO_NAME.get(e, e)} ({e})" for e in avoid]
        parts.append(f"AVOID: {', '.join(names)}")
    if not parts:
        parts.append("All HOLD/TURNING/WATCH")
    return " | ".join(parts)


def _recipe_match_screen() -> tuple[list[dict], dict]:
    """Screen full scored universe against active recipe filters (longlist)."""
    recipe_path = DATA_DIR / "active_recipe.json"
    scores_path = DATA_DIR / "scores_daily.parquet"

    if not recipe_path.exists() or not scores_path.exists():
        return [], {}

    with open(recipe_path) as f:
        raw = json.load(f)

    # Support dual format: use longlist section if present, else flat
    recipe = raw.get("longlist", raw)

    df = pd.read_parquet(scores_path)
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    latest_df = df[df["date"] == latest].copy()

    mask = pd.Series(True, index=latest_df.index)
    if recipe.get("sc_mom_min", 0) > 0:
        mask &= latest_df["sc_momentum"] >= recipe["sc_mom_min"]
    if recipe.get("flow_min", 0) > 0:
        mask &= latest_df["flow_100"] >= recipe["flow_min"]
    if recipe.get("energy_min", 0) > 0:
        mask &= latest_df["energy_100"] >= recipe["energy_min"]
    if recipe.get("structure_min", 0) > 0:
        mask &= latest_df["structure_100"] >= recipe["structure_min"]
    if recipe.get("mp_min", 0) > 0:
        mask &= latest_df["mp_100"] >= recipe["mp_min"]
    if recipe.get("elder_min", 0) > 0 and "elder_score" in latest_df.columns:
        mask &= latest_df["elder_score"] >= recipe["elder_min"]
    phase = recipe.get("phase_filter", "ANY")
    if phase != "ANY" and "mp_state" in latest_df.columns:
        if phase == "BUILDING":
            mask &= latest_df["mp_state"] == "BUILDING"
        elif phase == "BUILDING+STRONG":
            mask &= latest_df["mp_state"].isin(["BUILDING", "STRONG"])
    if recipe.get("squeeze_min", 0) > 0 and "squeeze_score" in latest_df.columns:
        mask &= latest_df["squeeze_score"] >= recipe["squeeze_min"]
    if recipe.get("fip_min", 0) > 0 and "fip_quality" in latest_df.columns:
        mask &= latest_df["fip_quality"] >= recipe["fip_min"]

    matches = latest_df[mask].sort_values("sc_momentum", ascending=False)

    result = []
    for _, row in matches.iterrows():
        result.append({
            "ticker": row["ticker"],
            "sc_momentum": float(row["sc_momentum"]),
            "sc_momentum_raw": float(row.get("sc_momentum_raw", row["sc_momentum"])),
            "flow_100": float(row.get("flow_100", 0)),
            "energy_100": float(row.get("energy_100", 0)),
            "structure_100": float(row.get("structure_100", 0)),
            "mp_100": float(row.get("mp_100", 0)),
            "elder_score": float(row.get("elder_score", 0)),
            "mp_state": str(row.get("mp_state", "")),
            "close": float(row.get("close", 0)),
            "atr14": float(row.get("atr14", 0)),
            "squeeze_score": float(row.get("squeeze_score", 0)),
        })

    return result, recipe


def _watchlist_screen(exclude_tickers: set[str]) -> list[dict]:
    """Screen scored universe for near-miss tickers (Longlist B).

    These are structurally ready setups where timing (Elder/gates) hasn't
    confirmed at daily close — but intraday price action could trigger an
    entry.  Uses sc_momentum_raw (ungated) so gate-suppressed tickers still
    surface when their raw weighted average is strong.

    Thresholds are deliberately relaxed relative to the main longlist:
        Raw SC_MOM >= 68  (vs gated 75 on A-list)
        Flow     >= 55    (vs 80)
        Energy   >= 50    (vs 64)
        Structure >= 45   (vs 60)
        MP       >= 45    (vs 60)
        Elder    — no gate (timing unconfirmed is the whole point)
    """
    scores_path = DATA_DIR / "scores_daily.parquet"
    recipe_path = DATA_DIR / "active_recipe.json"

    if not scores_path.exists():
        return []

    df = pd.read_parquet(scores_path)
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    latest_df = df[df["date"] == latest].copy()

    # Load watchlist recipe if it exists in active_recipe.json
    wl_cfg = {}
    if recipe_path.exists():
        with open(recipe_path) as f:
            raw = json.load(f)
        wl_cfg = raw.get("watchlist", {})

    # Thresholds — override from config or use defaults
    sc_raw_min = wl_cfg.get("sc_raw_min", 68)
    flow_min   = wl_cfg.get("flow_min", 55)
    energy_min = wl_cfg.get("energy_min", 50)
    struct_min = wl_cfg.get("structure_min", 45)
    mp_min     = wl_cfg.get("mp_min", 45)

    # Use sc_momentum_raw (ungated) — the whole point is catching gate-suppressed tickers
    raw_col = "sc_momentum_raw" if "sc_momentum_raw" in latest_df.columns else "sc_momentum"
    mask = latest_df[raw_col] >= sc_raw_min
    mask &= latest_df["flow_100"] >= flow_min
    mask &= latest_df["energy_100"] >= energy_min
    mask &= latest_df["structure_100"] >= struct_min
    mask &= latest_df["mp_100"] >= mp_min

    matches = latest_df[mask].sort_values(raw_col, ascending=False)

    # Load main longlist recipe for gap analysis
    main_recipe = {}
    if recipe_path.exists():
        with open(recipe_path) as f:
            raw = json.load(f)
        main_recipe = raw.get("longlist", raw)

    result = []
    for _, row in matches.iterrows():
        ticker = row["ticker"]
        if ticker in exclude_tickers:
            continue  # already on A-list

        # Gap analysis: which A-list gates does this ticker fail, and by how much?
        gaps = []
        sc_gated = float(row.get("sc_momentum", 0))
        sc_raw = float(row.get("sc_momentum_raw", row.get("sc_momentum", 0)))
        a_sc_min = main_recipe.get("sc_mom_min", 75)
        a_flow = main_recipe.get("flow_min", 80)
        a_energy = main_recipe.get("energy_min", 64)
        a_struct = main_recipe.get("structure_min", 60)
        a_mp = main_recipe.get("mp_min", 60)
        a_elder = main_recipe.get("elder_min", 7)

        flow_val = float(row.get("flow_100", 0))
        energy_val = float(row.get("energy_100", 0))
        struct_val = float(row.get("structure_100", 0))
        mp_val = float(row.get("mp_100", 0))
        elder_val = float(row.get("elder_score", 0))

        if sc_gated < a_sc_min:
            gaps.append(f"SC {sc_gated:.0f}<{a_sc_min}")
        if flow_val < a_flow:
            gaps.append(f"Flow {flow_val:.0f}<{a_flow}")
        if energy_val < a_energy:
            gaps.append(f"Energy {energy_val:.0f}<{a_energy}")
        if struct_val < a_struct:
            gaps.append(f"Struct {struct_val:.0f}<{a_struct}")
        if mp_val < a_mp:
            gaps.append(f"MP {mp_val:.0f}<{a_mp}")
        if elder_val < a_elder:
            gaps.append(f"Elder {elder_val:.0f}<{a_elder}")

        result.append({
            "ticker": ticker,
            "sc_momentum": sc_gated,
            "sc_momentum_raw": sc_raw,
            "flow_100": flow_val,
            "energy_100": energy_val,
            "structure_100": struct_val,
            "mp_100": mp_val,
            "elder_score": elder_val,
            "mp_state": str(row.get("mp_state", "")),
            "close": float(row.get("close", 0)),
            "atr14": float(row.get("atr14", 0)),
            "gaps": gaps,
            "gap_count": len(gaps),
        })

    # Sort: fewest gaps first (closest to A-list), then by raw SC descending
    result.sort(key=lambda r: (r["gap_count"], -r["sc_momentum_raw"]))
    return result


def _precision_edge_screen() -> tuple[list[dict], dict]:
    """Screen scored universe against Precision Edge sub-component filters.

    The Precision Edge recipe goes deeper than aggregate engine scores —
    it checks the individual sub-components that the full-search optimizer
    identified as having the strongest win-rate correlation.

    Each sub-component is an independent mathematical voice:
      roc_zscore  (Energy)   — momentum abnormality, 2sigma+ = breakout
      k39_value   (Scoring)  — composite K39 gate confirmed
      pr_rsi_score (PipeRank) — RSI vs peer universe
      rel_mom_score (Scoring) — relative momentum trend strength
    """
    recipe_path = DATA_DIR / "active_recipe.json"
    scores_path = DATA_DIR / "scores_daily.parquet"

    if not recipe_path.exists() or not scores_path.exists():
        return [], {}

    with open(recipe_path) as f:
        raw = json.load(f)

    # Handle both new dual-recipe format and legacy flat format
    precision = raw.get("precision", {})
    if not precision:
        return [], {}
    subcomp = precision.get("subcomp_filters", {})
    if not subcomp:
        return [], {}

    df = pd.read_parquet(scores_path)
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    latest_df = df[df["date"] == latest].copy()

    # Apply SC cross-up minimum (signals must have crossed above 50)
    sc_min = precision.get("sc_mom_min", 50.0)
    mask = latest_df["sc_momentum"] >= sc_min

    # Apply each sub-component filter
    for col, spec in subcomp.items():
        thresh = spec["threshold"] if isinstance(spec, dict) else spec
        if col in latest_df.columns:
            mask &= latest_df[col] >= thresh

    matches = latest_df[mask].sort_values("sc_momentum", ascending=False)

    result = []
    for _, row in matches.iterrows():
        # Collect sub-component values with engine labels
        subcomp_values = {}
        for col, spec in subcomp.items():
            if isinstance(spec, dict):
                subcomp_values[col] = {
                    "value": round(float(row.get(col, 0)), 2),
                    "threshold": spec["threshold"],
                    "engine": spec["engine"],
                    "label": spec["label"],
                    "meaning": spec["meaning"],
                    "pass": bool(row.get(col, 0) >= spec["threshold"]),
                }
            else:
                subcomp_values[col] = {
                    "value": round(float(row.get(col, 0)), 2),
                    "threshold": spec,
                    "pass": bool(row.get(col, 0) >= spec),
                }

        result.append({
            "ticker": row["ticker"],
            "sc_momentum": float(row["sc_momentum"]),
            "sc_momentum_raw": float(row.get("sc_momentum_raw", row["sc_momentum"])),
            "flow_100": float(row.get("flow_100", 0)),
            "energy_100": float(row.get("energy_100", 0)),
            "structure_100": float(row.get("structure_100", 0)),
            "mp_100": float(row.get("mp_100", 0)),
            "elder_score": float(row.get("elder_score", 0)),
            "mp_state": str(row.get("mp_state", "")),
            "close": float(row.get("close", 0)),
            "atr14": float(row.get("atr14", 0)),
            "subcomp_values": subcomp_values,
        })

    return result, precision


def _filter_fresh_signals(candidates: list[dict], max_age: int = SIGNAL_MAX_AGE) -> list[dict]:
    """Keep only candidates with a fresh SC_MOMENTUM cross-up (last N trading days).

    The backtest's edge is measured from the cross-up day.
    Enter 7 days late and the move already happened — no edge left.
    This filter enforces: show only actionable entries.
    """
    scores_path = DATA_DIR / "scores_daily.parquet"
    if not scores_path.exists():
        return candidates  # no history = can't filter, pass through

    scores = pd.read_parquet(scores_path)
    scores["date"] = pd.to_datetime(scores["date"])

    all_dates = sorted(scores["date"].unique())
    if len(all_dates) < max_age + 2:
        return candidates

    # We need max_age+1 days of data to detect cross-ups within the window
    lookback_start = all_dates[-(max_age + 2)]
    latest = all_dates[-1]

    fresh = []
    for c in candidates:
        tk = c["ticker"]
        tk_df = scores[(scores["ticker"] == tk) & (scores["date"] >= lookback_start)]
        tk_df = tk_df.sort_values("date").reset_index(drop=True)

        if "sc_momentum" not in tk_df.columns or len(tk_df) < 2:
            continue

        sc = tk_df["sc_momentum"].values
        dates = tk_df["date"].values

        # Find most recent cross-up above 50
        signal_idx = None
        for i in range(1, len(sc)):
            if sc[i] >= 50.0 and sc[i - 1] < 50.0:
                signal_idx = i

        if signal_idx is None:
            continue  # no cross-up in lookback period → stale

        signal_date = dates[signal_idx]
        signal_sc = float(sc[signal_idx])

        # Age in trading days (how many dates after signal_date up to latest)
        age = sum(1 for d in all_dates if d > signal_date and d <= latest)
        if age > max_age:
            continue  # too old

        current_sc = float(sc[-1])
        # Score must not have collapsed — still above 50 and within 15pts of signal
        if current_sc < 50.0 or current_sc < signal_sc - 15:
            continue  # signal failed or deteriorated badly

        c["signal_date"] = str(signal_date)[:10]
        c["signal_age"] = age
        c["signal_sc"] = round(signal_sc, 1)
        c["sc_direction"] = "RISING" if current_sc >= signal_sc else "fading"
        fresh.append(c)

    return fresh


def _build_output(
    run_date: date,
    regime: dict,
    sector_grades: dict,
    shortlist: list[dict],
    recipe_matches: list[dict] | None = None,
    active_recipe: dict | None = None,
    precision_matches: list[dict] | None = None,
    precision_recipe: dict | None = None,
    rank_lookup: dict | None = None,
) -> dict:
    """Build the final output JSON structure."""
    vix_regime = classify_vix_regime(regime.get("vix", 18.0))

    # Max new entry size based on regime
    if vix_regime == "RED":
        max_new_size = "NONE"
    elif vix_regime == "ORANGE":
        max_new_size = "QUARTER"
    elif vix_regime == "YELLOW":
        max_new_size = "QUARTER"
    else:
        max_new_size = "FULL"

    candidates_out = []
    for i, c in enumerate(shortlist[:15], 1):
        close = c.get("close", 0)
        atr14 = c.get("atr14", 0)
        entry = round(close, 2)
        stop = round(entry - 2 * atr14, 2) if atr14 > 0 else 0
        r_size = round(entry - stop, 2) if stop > 0 else 0
        be_trigger = round(entry + 0.5 * r_size, 2) if r_size > 0 else 0
        target_1r = round(entry + r_size, 2) if r_size > 0 else 0
        target_2r = round(entry + 2 * r_size, 2) if r_size > 0 else 0
        target_3r = round(entry + 3 * r_size, 2) if r_size > 0 else 0
        risk_dollars = round(0.03 * 70_000, 2)
        shares = int(risk_dollars / r_size) if r_size > 0 else 0

        candidates_out.append({
            "rank": i,
            "ticker": c["ticker"],
            "sc_momentum": round(c.get("sc_momentum", 0), 1),
            "sc_momentum_raw": round(c.get("sc_momentum_raw", c.get("sc_momentum", 0)), 1),
            "sc_position": round(c.get("sc_position", 0), 1),
            "ptrs": c.get("ptrs", 0),
            "disposition": c.get("disposition", "REJECT"),
            "mp_state": c.get("mp_state", ""),
            "pipe_rank": round(c.get("pipe_rank", 0), 1),
            "engines": {
                "flow": round(c.get("flow_100", 0), 1),
                "energy": round(c.get("energy_100", 0), 1),
                "structure": round(c.get("structure_100", 0), 1),
                "mp": round(c.get("mp_100", 0), 1),
                "elder": round(c.get("elder_score", 0), 1),
                "bq": round(c.get("bq_100", 0), 1),
            },
            "levels": {
                "entry": entry,
                "stop": stop,
                "r_size": r_size,
                "be_trigger": be_trigger,
                "target_1r": target_1r,
                "target_2r": target_2r,
                "target_3r": target_3r,
                "shares": shares,
                "risk_dollars": risk_dollars,
            },
            "signal": {
                "date": c.get("signal_date", ""),
                "age": c.get("signal_age", 0),
                "sc_at_signal": c.get("signal_sc", 0),
                "direction": c.get("sc_direction", ""),
            },
            "diagnostics": {
                "mp_state": c.get("mp_state", ""),
                "close": round(close, 2),
                "atr14": round(atr14, 3),
                "earn_days": c.get("earn_days"),
                "earn_warning": c.get("earn_days") is not None and c.get("earn_days", 999) <= 5,
            },
            "context": {
                "sector": c.get("sector", "UNKNOWN"),
                "sector_grade": c.get("sector_grade", "UNKNOWN"),
                "sh": c.get("sh", 0),
                "ra": c.get("ra", 0),
                "rl": c.get("rl", 0),
                "cm": c.get("cm", 0),
            },
            "precision_edge": c.get("precision", False),
        })

    # Legacy bucket summary (still used by some sections)
    srm_summary = {}
    for grade in ["DEPLOY", "HOLD", "TURNING", "WATCH", "AVOID"]:
        etfs = [k for k, v in sector_grades.items() if v.get("grade") == grade]
        if etfs:
            srm_summary[grade] = etfs

    # Rich per-sector SRM detail: regime + trend data
    srm_detail = {}
    for etf, gdata in sector_grades.items():
        srm_detail[etf] = {
            "grade": gdata.get("grade", "WATCH"),
            "sh": gdata.get("sh", -5),
            "roc20": round(gdata.get("roc20", 0.0), 2),
            "roc5": round(gdata.get("roc5", 0.0), 2),
            "above_sma20": gdata.get("above_sma20", False),
        }

    # Recipe signal matches with levels
    recipe_out = []
    for rm in (recipe_matches or []):
        close = rm.get("close", 0)
        a14 = rm.get("atr14", 0)
        ent = round(close, 2)
        stp = round(ent - 2 * a14, 2) if a14 > 0 else 0
        rsz = round(ent - stp, 2) if stp > 0 else 0
        recipe_out.append({
            "ticker": rm["ticker"],
            "sc_momentum": round(rm.get("sc_momentum", 0), 1),
            "sc_momentum_raw": round(rm.get("sc_momentum_raw", rm.get("sc_momentum", 0)), 1),
            "pipe_rank": rm.get("pipe_rank", 0),
            "fip_quality": rm.get("fip_quality", 0),
            "engines": {
                "flow": round(rm.get("flow_100", 0), 1),
                "energy": round(rm.get("energy_100", 0), 1),
                "structure": round(rm.get("structure_100", 0), 1),
                "mp": round(rm.get("mp_100", 0), 1),
                "elder": round(rm.get("elder_score", 0), 1),
            },
            "mp_state": rm.get("mp_state", ""),
            "squeeze": round(rm.get("squeeze_score", 0), 1),
            "on_shortlist": rm.get("on_shortlist", False),
            "levels": {
                "entry": ent,
                "stop": stp,
                "r_size": rsz,
                "be_trigger": round(ent + 0.5 * rsz, 2) if rsz > 0 else 0,
                "target_1r": round(ent + rsz, 2) if rsz > 0 else 0,
                "target_2r": round(ent + 2 * rsz, 2) if rsz > 0 else 0,
                "target_3r": round(ent + 3 * rsz, 2) if rsz > 0 else 0,
                "shares": int(2100 / rsz) if rsz > 0 else 0,
                "risk_dollars": 2100.0,
            },
        })

    # PE picks always belong in the longlist — they passed a harder test
    _rl = rank_lookup or {}
    recipe_tickers = {rm["ticker"] for rm in recipe_out}
    for pm in (precision_matches or []):
        if pm["ticker"] not in recipe_tickers:
            close = pm.get("close", 0)
            a14 = pm.get("atr14", 0)
            ent = round(close, 2)
            stp = round(ent - 2 * a14, 2) if a14 > 0 else 0
            rsz = round(ent - stp, 2) if stp > 0 else 0
            pr, fip = _rl.get(pm["ticker"], (0.0, 0.0))
            recipe_out.append({
                "ticker": pm["ticker"],
                "sc_momentum": round(pm.get("sc_momentum", 0), 1),
                "sc_momentum_raw": round(pm.get("sc_momentum_raw", pm.get("sc_momentum", 0)), 1),
                "pipe_rank": round(pr, 1),
                "fip_quality": round(fip, 1),
                "engines": {
                    "flow": round(pm.get("flow_100", 0), 1),
                    "energy": round(pm.get("energy_100", 0), 1),
                    "structure": round(pm.get("structure_100", 0), 1),
                    "mp": round(pm.get("mp_100", 0), 1),
                    "elder": round(pm.get("elder_score", 0), 1),
                },
                "mp_state": pm.get("mp_state", ""),
                "squeeze": 0,
                "on_shortlist": True,
                "pe_qualified": True,
                "levels": {
                    "entry": ent,
                    "stop": stp,
                    "r_size": rsz,
                    "be_trigger": round(ent + 0.5 * rsz, 2) if rsz > 0 else 0,
                    "target_1r": round(ent + rsz, 2) if rsz > 0 else 0,
                    "target_2r": round(ent + 2 * rsz, 2) if rsz > 0 else 0,
                    "target_3r": round(ent + 3 * rsz, 2) if rsz > 0 else 0,
                    "shares": int(2100 / rsz) if rsz > 0 else 0,
                    "risk_dollars": 2100.0,
                },
            })

    # Re-sort full longlist (aggregate + PE) by pipe_rank + floor
    def _out_floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0),
                   e.get("structure", 0), e.get("mp", 0))
    recipe_out.sort(key=lambda rm: (rm.get("pipe_rank", 0), _out_floor(rm)), reverse=True)

    # Build precision edge detail cards
    precision_out = []
    prec_lookup = {pm["ticker"]: pm for pm in (precision_matches or [])}
    for c_out in candidates_out:
        if c_out["precision_edge"] and c_out["ticker"] in prec_lookup:
            pm = prec_lookup[c_out["ticker"]]
            precision_out.append({
                "ticker": c_out["ticker"],
                "levels": c_out["levels"],
                "engines": c_out["engines"],
                "disposition": c_out["disposition"],
                "mp_state": c_out.get("mp_state", ""),
                "pipe_rank": c_out.get("pipe_rank", 0),
                "signal": c_out["signal"],
                "context": c_out["context"],
                "subcomp_values": pm.get("subcomp_values", {}),
            })

    # Also add precision matches NOT on the shortlist (fresh signal already passed Pipeline Rank)
    for pm in (precision_matches or []):
        if pm["ticker"] not in {p["ticker"] for p in precision_out}:
            close = pm.get("close", 0)
            a14 = pm.get("atr14", 0)
            ent = round(close, 2)
            stp = round(ent - 2 * a14, 2) if a14 > 0 else 0
            rsz = round(ent - stp, 2) if stp > 0 else 0
            precision_out.append({
                "ticker": pm["ticker"],
                "levels": {
                    "entry": ent, "stop": stp, "r_size": rsz,
                    "be_trigger": round(ent + 0.5 * rsz, 2) if rsz > 0 else 0,
                    "target_1r": round(ent + rsz, 2) if rsz > 0 else 0,
                    "target_2r": round(ent + 2 * rsz, 2) if rsz > 0 else 0,
                    "target_3r": round(ent + 3 * rsz, 2) if rsz > 0 else 0,
                    "shares": int(2100 / rsz) if rsz > 0 else 0,
                    "risk_dollars": 2100.0,
                },
                "engines": {
                    "flow": round(pm.get("flow_100", 0), 1),
                    "energy": round(pm.get("energy_100", 0), 1),
                    "structure": round(pm.get("structure_100", 0), 1),
                    "mp": round(pm.get("mp_100", 0), 1),
                    "elder": round(pm.get("elder_score", 0), 1),
                },
                "disposition": "CHECK",
                "mp_state": pm.get("mp_state", ""),
                "pipe_rank": round(pm.get("pipe_rank", 0), 1),
                "signal": {},
                "context": {},
                "subcomp_values": pm.get("subcomp_values", {}),
                "note": "Passes Precision Edge but not on fresh-signal shortlist",
            })

    sgt = ZoneInfo("Asia/Singapore")
    return {
        "date": str(run_date),
        "refreshed_at": datetime.now(sgt).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "regime": {
            "vix": regime.get("vix", 18.0),
            "level": vix_regime,
            "hurst": regime.get("hurst", 0.50),
            "trend": regime.get("hurst_regime", "RANDOM"),
            "implication": regime.get("implication", ""),
        },
        "max_new_size": max_new_size,
        "candidates": candidates_out,
        "precision_edge": precision_out,
        "precision_recipe": precision_recipe or {},
        "recipe_matches": recipe_out,
        "active_recipe": active_recipe or {},
        "srm_summary": srm_summary,
        "srm_detail": srm_detail,
        "meta": {
            "total_universe": len(load_universe()),
            "passed_pipeline_rank": len(shortlist),
            "on_shortlist": len(candidates_out),
            "precision_edge_count": len(precision_out),
            "recipe_match_count": len(recipe_out),
        },
    }


def _write_outputs(output: dict) -> None:
    """Write shortlist JSON and text dashboard."""
    with open(SHORTLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    dashboard = _format_dashboard(output)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(dashboard)


def _format_dashboard(output: dict) -> str:
    """Plain-text dashboard for quick review."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  AQE DAILY SHORTLIST - {output['date']}")
    lines.append("=" * 70)

    r = output["regime"]
    lines.append(f"  Regime: VIX {r['vix']:.1f} ({r['level']}) | Hurst {r['hurst']:.3f} ({r['trend']})")
    lines.append(f"  Max new entry size: {output['max_new_size']}")
    lines.append(f"  {r['implication']}")
    lines.append("")

    srm = output.get("srm_summary", {})
    if srm:
        for grade, etfs in srm.items():
            named = [f"{ETF_TO_NAME.get(e, e)} ({e})" for e in etfs]
            lines.append(f"  SRM {grade}: {', '.join(named)}")
        lines.append("")

    # Build set of tickers that pass the active recipe
    recipe_tickers = {rm["ticker"] for rm in output.get("recipe_matches", [])}

    if not output["candidates"]:
        lines.append("  No fresh signals today. All recent cross-ups are older than 3 trading days.")
        lines.append("  This is normal — not every day has a new entry.")
        lines.append("=" * 70)
    else:
        lines.append("-" * 88)
        lines.append(
            f"  {'#':>2} {'Ticker':<6} {'SC_M':>5} {'PTRS':>5} {'Disp':<5} "
            f"{'Flow':>4} {'Enrg':>4} {'Strc':>4} {'MP':>4} {'Eldr':>4} "
            f"{'Sector':<7} {'Rcp':>3} {'Sig':>5} {'Dir':<6}"
        )
        lines.append("-" * 88)

        for c in output["candidates"]:
            eng = c["engines"]
            ctx = c["context"]
            sig = c.get("signal", {})
            rcp = "Y" if c["ticker"] in recipe_tickers else ""
            age = sig.get("age", 0)
            sig_label = "TODAY" if age == 0 else f"{age}d" if age > 0 else ""
            direction = sig.get("direction", "")
            lines.append(
                f"  {c['rank']:>2} {c['ticker']:<6} {c['sc_momentum']:>5.1f} "
                f"{c['ptrs']:>5.1f} {c['disposition']:<5} "
                f"{eng['flow']:>4.0f} {eng['energy']:>4.0f} {eng['structure']:>4.0f} "
                f"{eng['mp']:>4.0f} {eng['elder']:>4.1f} "
                f"{ctx['sector_grade']:<7} {rcp:>3} {sig_label:>5} {direction:<6}"
            )

        lines.append("-" * 88)
        m = output["meta"]
        n_rcp = sum(1 for c in output["candidates"] if c["ticker"] in recipe_tickers)
        lines.append(f"  Fresh signals: {m['on_shortlist']} | Recipe match: {n_rcp} (trade these first)")
        lines.append(f"  Sig = trading days since cross-up | Dir = score RISING or fading since signal")
        lines.append("=" * 88)

    # Precision Edge section
    prec = output.get("precision_edge", [])
    if prec:
        lines.append("")
        lines.append("=" * 70)
        lines.append("  PRECISION EDGE — Sub-Component Deep Dive (37.2% WR backtest)")
        lines.append("  Trades where independent engine voices align")
        lines.append("=" * 70)
        for p in prec:
            lv = p.get("levels", {})
            disp = p.get("disposition", "?")
            ctx = p.get("context", {})
            sector = ctx.get("sector_grade", "?")
            lines.append(f"  {p['ticker']}  |  Disp: {disp}  |  Sector: {sector}")
            if lv.get("r_size", 0) > 0:
                lines.append(
                    f"    Entry: ${lv['entry']:.2f}  Stop: ${lv['stop']:.2f}  "
                    f"R-size: ${lv['r_size']:.2f}  Shares: {lv['shares']}"
                )
                lines.append(
                    f"    BE: ${lv['be_trigger']:.2f}  +1R: ${lv['target_1r']:.2f}  "
                    f"+2R: ${lv['target_2r']:.2f}  +3R: ${lv['target_3r']:.2f}  "
                    f"Risk: ${lv['risk_dollars']:.0f}"
                )
            sc = p.get("subcomp_values", {})
            if sc:
                parts = []
                for col, info in sc.items():
                    if isinstance(info, dict):
                        lbl = info.get("label", col)
                        eng = info.get("engine", "")
                        val = info.get("value", 0)
                        thr = info.get("threshold", 0)
                        parts.append(f"{lbl}={val} ({eng}, need {thr})")
                if parts:
                    lines.append(f"    Voices: {' | '.join(parts)}")
            if p.get("note"):
                lines.append(f"    Note: {p['note']}")
            lines.append("")
        lines.append("=" * 70)

    lines.append("")
    lines.append("=" * 70)
    lines.append("  LONGLIST — Aggregate Entry / Stop / BE / Targets (3% risk, $70K)")
    lines.append("=" * 70)
    lines.append(
        f"  {'Ticker':<6} {'Entry':>8} {'Stop':>8} {'R-size':>7} "
        f"{'BE @':>8} {'+1R':>8} {'+2R':>8} {'+3R':>8} {'Shares':>6}"
    )
    lines.append("-" * 70)
    for c in output["candidates"]:
        lv = c.get("levels", {})
        if not lv or lv.get("r_size", 0) == 0:
            continue
        lines.append(
            f"  {c['ticker']:<6} {lv['entry']:>8.2f} {lv['stop']:>8.2f} {lv['r_size']:>7.2f} "
            f"{lv['be_trigger']:>8.2f} {lv['target_1r']:>8.2f} {lv['target_2r']:>8.2f} "
            f"{lv['target_3r']:>8.2f} {lv['shares']:>6}"
        )
    lines.append("-" * 70)
    lines.append("  Stop = Entry - 2xATR14 | BE trigger = Entry + 0.5R | Targets = Entry + nR")
    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    skip = "--no-pull" in sys.argv
    run_daily(skip_pull=skip)
