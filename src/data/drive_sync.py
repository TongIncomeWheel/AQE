"""Google Drive sync — export daily outputs to local Drive mount.

Writes aqe_daily_export.json to G:\\My Drive\\Trading Strategy\\AQE\\
(Google Drive for Desktop syncs automatically to cloud).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.analyzer.ptrs import compute_ptrs
from src.data.sector_mapper import ETF_TO_NAME, load_sector_map
from src.engines.srm import GICS_ETFS, get_sector_health, grade_all_sectors
from src.scanner.betas import load_betas
from src.scanner.levels import load_elder_history, load_trade_levels

from src.data.paths import OUTPUT_DIR, PROJECT_ROOT  # single source of truth

DRIVE_EXPORT_DIR = Path(r"G:\My Drive\Trading Strategy\AQE")
EXPORT_FILENAME = "aqe_daily_export.json"


def _rank_explain(pipe_rank: float, floor: float, sc_mom: float,
                  pe_qualified: bool, ticker: str,
                  sm: dict, sector_grades: dict) -> str:
    """1-liner explaining why a ticker sits at its rank."""
    parts: list[str] = []
    pr = pipe_rank or 0
    fl = floor or 0
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
    if pr <= 0:
        parts.append(f"Floor {fl:.0f} sorts")
    elif fl >= 70 and pr < 70:
        parts.append(f"engines strong (Floor {fl:.0f})")
    elif fl < 45 and pr > 0:
        parts.append(f"Floor {fl:.0f} drags")
    etf = sm.get(ticker, "")
    grade = sector_grades.get(etf, {}).get("grade", "")
    if grade == "DEPLOY":
        parts.append("sector DEPLOY")
    elif grade == "AVOID":
        parts.append("sector AVOID")
    return "; ".join(parts) if parts else ""


def _build_srm_table() -> list[dict]:
    """SRM grade + 10-day SH/grade trend for every GICS sector (tabulated).

    Recomputed from the cached price panel so the committee sees a trend, not
    a one-day snapshot. One row per sector, sorted DEPLOY -> AVOID.
    """
    import pandas as pd
    from src.data.paths import PANEL_DAILY as panel_path

    if not panel_path.exists():
        return []
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "close"])
    panel = panel[panel["ticker"].isin(GICS_ETFS)]
    if panel.empty:
        return []

    graded = grade_all_sectors(panel, trend_days=10)
    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}
    rows = [
        {
            "etf": etf,
            "sector": ETF_TO_NAME.get(etf, etf),
            "grade": info.get("grade", "WATCH"),
            "sh": info.get("sh", 0),
            "roc20": info.get("roc20", 0.0),
            "roc5": info.get("roc5", 0.0),
            "above_sma20": info.get("above_sma20", False),
            "sh_trend": info.get("sh_trend", []),
            "grade_trend": info.get("grade_trend", []),
        }
        for etf, info in graded.items()
    ]
    rows.sort(key=lambda r: grade_order.get(r["grade"], 3))
    return rows


def build_export(shortlist: dict | None = None) -> dict:
    """Build export from shortlist.json + scores_daily.parquet.

    Contains top_picks, edge_list, longlist, and watchlist.
    Every ticker is tagged with source (longlist / watchlist) and pe status.
    """
    if shortlist is None:
        sl_path = OUTPUT_DIR / "shortlist.json"
        if not sl_path.exists():
            return {}
        shortlist = json.loads(sl_path.read_text(encoding="utf-8"))

    sl = shortlist
    sgt = ZoneInfo("Asia/Singapore")
    now_sgt = datetime.now(sgt)
    export: dict = {
        "date": sl.get("date", ""),
        "exported_at": now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"),
        "market": "US equities — close-of-day scan",
        "regime": sl.get("regime", {}),
        "srm_deploy": sl.get("srm_summary", {}).get("DEPLOY", []),
        "srm_avoid": sl.get("srm_summary", {}).get("AVOID", []),
        "srm": _build_srm_table(),
        "top_picks": [],
        "edge_list": [],
        "longlist": [],
        "watchlist": [],
    }

    # Top Picks = candidates (PTRS-ranked shortlist)
    for c in sl.get("candidates", []):
        export["top_picks"].append({
            "rank": c["rank"],
            "ticker": c["ticker"],
            "sc_momentum": round(c.get("sc_momentum", 0), 1),
            "ptrs": round(c.get("ptrs", 0), 1),
            "disposition": c.get("disposition", ""),
            "flow": round(c["engines"]["flow"], 1),
            "energy": round(c["engines"]["energy"], 1),
            "structure": round(c["engines"]["structure"], 1),
            "mp": round(c["engines"]["mp"], 1),
            "elder": c["engines"]["elder"],
            "entry": c["levels"].get("entry"),
            "stop": c["levels"].get("stop"),
        })

    # Edge List = Precision Edge
    def _sc_from_engines(eng):
        """SC_MOM = Flow×0.30 + Energy×0.30 + Structure×0.20 + MP×0.20."""
        return round(
            eng.get("flow", 0) * 0.30 + eng.get("energy", 0) * 0.30
            + eng.get("structure", 0) * 0.20 + eng.get("mp", 0) * 0.20, 1
        )

    for pe in sl.get("precision_edge", []):
        eng = pe["engines"]
        pe_sc = pe.get("sc_momentum") or _sc_from_engines(eng)
        pe_raw = pe.get("sc_momentum_raw") or pe_sc
        export["edge_list"].append({
            "ticker": pe["ticker"],
            "disposition": pe.get("disposition", ""),
            "sc_momentum": round(pe_sc, 1),
            "sc_momentum_raw": round(pe_raw, 1),
            "flow": round(eng["flow"], 1),
            "energy": round(eng["energy"], 1),
            "structure": round(eng["structure"], 1),
            "mp": round(eng["mp"], 1),
            "elder": eng["elder"],
            "entry": pe["levels"].get("entry"),
            "stop": pe["levels"].get("stop"),
        })

    # PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
    sector_grades = sl.get("srm_detail", {})

    def _ptrs(sc_mom, ticker):
        sh = get_sector_health(ticker, sector_grades)
        r = compute_ptrs(sc_mom, sh)
        v = r.get("ptrs")
        return round(v, 1) if v is not None and v == v else 0.0

    # Longlist = recipe matches (sorted by pipe_rank desc, floor tiebreak)
    def _floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0),
                   e.get("structure", 0), e.get("mp", 0))

    sm = load_sector_map()
    betas = load_betas()
    # Pass betas so high-β tickers get β-adjusted initial stops (DSL v2.1)
    dsl_all = load_trade_levels(betas=betas)
    elder5 = load_elder_history()
    pe_tickers = {p["ticker"] for p in sl.get("precision_edge", [])}
    longlist_tickers: set[str] = set()
    sorted_rm = sorted(sl.get("recipe_matches", []),
                       key=lambda rm: (rm.get("pipe_rank", 0), _floor(rm)),
                       reverse=True)
    for i, rm in enumerate(sorted_rm, 1):
        e = rm["engines"]
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        sc_val = rm.get("sc_momentum", 0) or 0
        longlist_tickers.add(rm["ticker"])
        d = dsl_all.get(rm["ticker"], {})
        export["longlist"].append({
            "rank": i,
            "ticker": rm["ticker"],
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(rm.get("sc_momentum_raw", sc_val), 1),
            "ptrs": _ptrs(sc_val, rm["ticker"]),
            "pipe_rank": round(rm.get("pipe_rank", 0), 1),
            "floor": floor,
            "beta_60d": (betas.get(rm["ticker"]) or {}).get(60),
            "beta_30d": (betas.get(rm["ticker"]) or {}).get(30),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": rm.get("mp_state", ""),
            "entry": rm["levels"].get("entry"),
            "stop": rm["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_be": d.get("be"),
            "dsl_shares": d.get("shares"),
            "dsl_rr_pct": d.get("rr_pct"),
            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(rm["ticker"]),
            "rank_explain": _rank_explain(
                rm.get("pipe_rank", 0), floor, sc_val,
                rm.get("pe_qualified", False), rm["ticker"],
                sm, sector_grades,
            ),
            "source": "longlist",
            "pe": bool(rm.get("pe_qualified")),
        })

    # --- Watchlist: full universe above raw SC_MOM >= 70 ---
    import pandas as pd
    from src.data.paths import SCORES_DAILY as scores_path

    if scores_path.exists():
        wl_df = pd.read_parquet(scores_path)
        wl_df["date"] = pd.to_datetime(wl_df["date"]).dt.normalize()
        wl_latest = wl_df["date"].max()
        wl_df = wl_df[wl_df["date"] == wl_latest].copy()

        raw_col = (
            "sc_momentum_raw"
            if "sc_momentum_raw" in wl_df.columns
            else "sc_momentum"
        )
        wl_mask = wl_df[raw_col] >= 70
        _exclude = set(GICS_ETFS) | {"SPY"}
        wl_mask &= ~wl_df["ticker"].isin(_exclude)
        wl_df = wl_df[wl_mask].copy()

        if not wl_df.empty:
            for c in (
                "pipe_rank", "flow_100", "energy_100",
                "structure_100", "mp_100",
            ):
                if c in wl_df.columns:
                    wl_df[c] = pd.to_numeric(
                        wl_df[c], errors="coerce"
                    ).fillna(0)
            wl_df["_floor"] = wl_df[
                ["flow_100", "energy_100", "structure_100", "mp_100"]
            ].min(axis=1)

            # Vectorized PTRS
            wl_sh = wl_df["ticker"].map(
                lambda t: sector_grades.get(sm.get(t, ""), {}).get("sh", 0)
            )
            wl_df["_ptrs"] = (
                wl_df["sc_momentum"].fillna(0) + wl_sh.fillna(0)
            ).round(1)

            wl_df = wl_df.sort_values(
                ["pipe_rank", "_floor"], ascending=[False, False]
            ).reset_index(drop=True)

            for wi, (_, wr) in enumerate(wl_df.iterrows(), 1):
                tk = wr["ticker"]
                d = dsl_all.get(tk, {})
                wfl = round(float(wr["_floor"]), 1)
                wsc = float(wr.get("sc_momentum", 0)) or 0
                wpr = float(wr.get("pipe_rank", 0))
                export["watchlist"].append({
                    "rank": wi,
                    "ticker": tk,
                    "sc_momentum": round(wsc, 1),
                    "sc_momentum_raw": round(
                        float(wr.get(raw_col, wsc)), 1
                    ),
                    "ptrs": round(float(wr["_ptrs"]), 1),
                    "pipe_rank": round(wpr, 1),
                    "floor": wfl,
                    "beta_60d": (betas.get(tk) or {}).get(60),
                    "beta_30d": (betas.get(tk) or {}).get(30),
                    "flow": round(float(wr.get("flow_100", 0)), 1),
                    "energy": round(float(wr.get("energy_100", 0)), 1),
                    "structure": round(
                        float(wr.get("structure_100", 0)), 1
                    ),
                    "mp": round(float(wr.get("mp_100", 0)), 1),
                    "elder": round(float(wr.get("elder_score", 0)), 1),
                    "dsl_stop": d.get("stop"),
                    "dsl_risk": d.get("risk"),
                    "dsl_tp_1r": d.get("tp_1r"),
                    "dsl_tp_2r": d.get("tp_2r"),
                    "dsl_tp_3r": d.get("tp_3r"),
                    "dsl_be": d.get("be"),
                    "dsl_shares": d.get("shares"),
                    "dsl_rr_pct": d.get("rr_pct"),
                    "rr_est": d.get("rr_est"),
                    "fib": d.get("fib"),
                    "elder_5d": elder5.get(tk),
                    "rank_explain": _rank_explain(
                        wpr, wfl, wsc, tk in pe_tickers, tk,
                        sm, sector_grades,
                    ),
                    "source": "watchlist",
                    "pe": tk in pe_tickers,
                    "on_longlist": tk in longlist_tickers,
                })

    export["summary"] = {
        "top_picks_count": len(export["top_picks"]),
        "edge_count": len(export["edge_list"]),
        "longlist_count": len(export["longlist"]),
        "watchlist_count": len(export["watchlist"]),
    }

    return export


def export_to_drive(shortlist: dict | None = None) -> dict:
    """Build export JSON and publish it.

    Three publishing paths, in order of preference:
      1. ALWAYS: write the JSON to the local OUTPUT_DIR so the rest of AQE
         can read it (Scanner, Math Lab, AIC, etc.).
      2. IF G:\\My Drive\\... is mounted (local Windows PC with Google Drive
         Desktop), write the JSON to that mount -- Drive sync handles the
         upload automatically.
      3. IF the Google Drive OAuth env vars are set (HF / Streamlit Cloud /
         any Linux container), upload via the Drive REST API. Same target
         folder by name as the desktop sync uses.

    Paths 2 and 3 are independent and both can run on the same call -- the
    local PC could push to both its local mount AND the cloud Drive folder
    if the user wants that.

    Returns dict with status, the local + remote paths/file_ids touched, and
    a `reason` string when something didn't run.
    """
    export = build_export(shortlist)
    if not export:
        return {"status": "skipped", "reason": "No shortlist data"}

    date_str = export.get("date", "unknown")
    content = json.dumps(export, indent=2)
    written: list[str] = []
    drive_results: list[dict] = []

    # Path 1: Always write locally — erase then write for clean overwrite
    local_path = OUTPUT_DIR / EXPORT_FILENAME
    if local_path.exists():
        local_path.unlink()
    local_path.write_text(content, encoding="utf-8")
    written.append(str(local_path))

    # Path 2: Local Drive mount (Windows PC only)
    if DRIVE_EXPORT_DIR.exists():
        drive_path = DRIVE_EXPORT_DIR / EXPORT_FILENAME
        if drive_path.exists():
            drive_path.unlink()
        drive_path.write_text(content, encoding="utf-8")
        written.append(str(drive_path))

    # Path 3: Drive REST API (cloud-friendly)
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            result = gdrive_uploader.upload_or_replace(
                EXPORT_FILENAME, content, mime="application/json",
            )
            drive_results.append(result)
            if result.get("ok"):
                written.append(f"gdrive:{result.get('file_id', '?')}")
    except Exception as exc:                                                    # noqa: BLE001
        drive_results.append({"ok": False, "reason": f"uploader error: {exc}"})

    # Status: ok if anything beyond the local file was written
    status = "ok" if len(written) > 1 else "partial"
    reason = None
    if status == "partial":
        if not DRIVE_EXPORT_DIR.exists():
            reason = (
                "Drive not published. Local mount not found at "
                f"{DRIVE_EXPORT_DIR} and cloud OAuth env vars not set."
            )
        else:
            reason = "Drive mount not found"

    return {
        "status": status,
        "date": date_str,
        "exported_at": export.get("exported_at", ""),
        "written": written,
        "drive_api_results": drive_results,
        **({"reason": reason} if reason else {}),
    }


# Legacy — keep for backward compat
def sync_to_drive(files: list[Path] | None = None) -> dict:
    """Export daily JSON to Google Drive (via local mount)."""
    return export_to_drive()
