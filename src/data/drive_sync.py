"""Google Drive sync — export the daily scan to one AQE folder.

Single target directory under G:\\My Drive\\Trading Strategy\\:
  AQE/  → aqe_daily_export.json  (scan + SRM combined, overwritten each run)

The committee reads this one file. SRM grading is embedded as the export's
`srm` / `srm_gics` / `srm_signals` sections, so there is no separate SRM file.
The pre-trade journal (open positions, closed trades) is written to the local
OUTPUT_DIR only — it is intentionally NOT published to Drive.

Each run overwrites the same filename so the Drive folder never clutters.
Google Drive for Desktop syncs automatically to cloud.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.analyzer.ptrs import compute_ptrs
from src.data.sector_mapper import ETF_TO_NAME, load_sector_map
from src.engines.srm import GICS_ETFS, get_sector_health, grade_all_sectors
from src.scanner.betas import load_betas
from src.scanner.levels import load_elder_history, load_trade_levels

from src.data.paths import OUTPUT_DIR, PROJECT_ROOT  # single source of truth

# --- Drive directory (local mount path) — single AQE folder ---
DRIVE_ROOT = Path(r"G:\My Drive\Trading Strategy")
DRIVE_EXPORT_DIR = DRIVE_ROOT / "AQE"

# --- Drive path for cloud REST API (relative to My Drive root) ---
CLOUD_AQE_PATH = "Trading Strategy/AQE"

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


def _build_srm_gics() -> tuple[list[dict], dict]:
    """Full 11-sector SRM grading with trend data.

    Returns (srm_gics_array, srm_signals_dict).
    srm_gics: one row per sector (sorted DEPLOY→AVOID) with grade, sh_value,
              roc20, roc5, divergence, above_sma20, sh_trend, grade_trend.
    srm_signals: {deploy, hold, turning, watch, avoid, blocked} ETF lists.
    """
    import pandas as pd
    from src.data.paths import PANEL_DAILY as panel_path

    empty_signals = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}

    if not panel_path.exists():
        return [], empty_signals
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "close"])
    panel = panel[panel["ticker"].isin(GICS_ETFS)]
    if panel.empty:
        return [], empty_signals

    graded = grade_all_sectors(panel, trend_days=10)
    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}

    # Ensure all 11 sectors present (NO_DATA fallback for missing)
    rows = []
    for etf in GICS_ETFS:
        if etf in graded:
            info = graded[etf]
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": info.get("grade", "WATCH"),
                "sh_value": info.get("sh", 0),
                "roc20": info.get("roc20", 0.0),
                "roc5": info.get("roc5", 0.0),
                "divergence": info.get("divergence", 0.0),
                "above_sma20": info.get("above_sma20", False),
                "sh_trend": info.get("sh_trend", []),
                "grade_trend": info.get("grade_trend", []),
            })
        else:
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": "NO_DATA",
                "sh_value": -5,
                "roc20": 0.0,
                "roc5": 0.0,
                "divergence": 0.0,
                "above_sma20": False,
                "sh_trend": [],
                "grade_trend": [],
            })

    rows.sort(key=lambda r: grade_order.get(r["grade"], 3))

    # Build srm_signals summary
    signals: dict[str, list[str]] = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}
    for r in rows:
        g = r["grade"].lower()
        if g in signals:
            signals[g].append(r["etf"])
        if g == "avoid" or g == "no_data":
            signals["blocked"].append(r["etf"])

    return rows, signals


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

    # Full 11-sector SRM grading (spec §2)
    srm_gics, srm_signals = _build_srm_gics()

    export: dict = {
        "date": sl.get("date", ""),
        "exported_at": now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"),
        "market": "US equities — close-of-day scan",
        "regime": sl.get("regime", {}),
        # Full SRM schema — combined into this one file (no separate SRM file).
        # `srm` is the list the AIC reader + protocols consume; `srm_gics` is
        # kept as an alias for existing callers.
        "srm": srm_gics,
        "srm_gics": srm_gics,
        "srm_signals": srm_signals,
        # Backward compat — derived from computed grades, not shortlist.json
        "srm_deploy": srm_signals.get("deploy", []),
        "srm_avoid": srm_signals.get("avoid", []),
        "top_picks": [],
        "edge_list": [],
        "longlist": [],
        "watchlist": [],
    }

    # ---- Shared helpers (loaded once, used by all four lists) ----
    # PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
    sector_grades = {r["etf"]: {"grade": r["grade"], "sh": r["sh_value"]} for r in srm_gics} if srm_gics else sl.get("srm_detail", {})

    def _ptrs(sc_mom, ticker):
        sh = get_sector_health(ticker, sector_grades)
        r = compute_ptrs(sc_mom, sh)
        v = r.get("ptrs")
        return round(v, 1) if v is not None and v == v else 0.0

    def _floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0),
                   e.get("structure", 0), e.get("mp", 0))

    def _sc_from_engines(eng):
        """SC_MOM = Flow×0.30 + Energy×0.30 + Structure×0.20 + MP×0.20."""
        return round(
            eng.get("flow", 0) * 0.30 + eng.get("energy", 0) * 0.30
            + eng.get("structure", 0) * 0.20 + eng.get("mp", 0) * 0.20, 1
        )

    # Extract regime level for DSL v1.5 dynamic stop width
    regime_level = (sl.get("regime", {}).get("level") or "GREEN").upper()

    sm = load_sector_map()
    betas = load_betas()
    dsl_all = load_trade_levels(betas=betas, regime_level=regime_level)
    elder5 = load_elder_history()
    pe_tickers = {p["ticker"] for p in sl.get("precision_edge", [])}

    # mp_state lookup from scores_daily.parquet — authoritative source.
    # shortlist.json nests mp_state inside "diagnostics" for candidates and
    # omits it entirely from precision_edge, so we derive from the parquet.
    import pandas as pd
    from src.data.paths import SCORES_DAILY as _scores_path
    _mp_states: dict[str, str] = {}
    if _scores_path.exists():
        _sc = pd.read_parquet(_scores_path, columns=["date", "ticker", "mp_state"])
        _sc["date"] = pd.to_datetime(_sc["date"]).dt.normalize()
        _latest = _sc[_sc["date"] == _sc["date"].max()]
        _mp_states = dict(zip(_latest["ticker"], _latest["mp_state"].astype(str)))

    # Top Picks = candidates (PTRS-ranked shortlist) — SAME schema as longlist
    for c in sl.get("candidates", []):
        tk = c["ticker"]
        e = c["engines"]
        d = dsl_all.get(tk, {})
        sc_val = c.get("sc_momentum", 0) or 0
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        export["top_picks"].append({
            "rank": c["rank"],
            "ticker": tk,
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(c.get("sc_momentum_raw", sc_val), 1),
            "ptrs": round(c.get("ptrs", 0), 1),
            "pipe_rank": round(c.get("pipe_rank", 0), 1),
            "floor": floor,
            "disposition": c.get("disposition", ""),
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(tk, c.get("mp_state", "")),
            "entry": c["levels"].get("entry"),
            "stop": c["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_be": d.get("be"),
            "dsl_shares": d.get("shares"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),
            "daily_range_proxy": d.get("daily_range_proxy"),
            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                c.get("pipe_rank", 0), floor, sc_val,
                tk in pe_tickers, tk, sm, sector_grades,
            ),
            "source": "top_picks",
            "pe": tk in pe_tickers,
        })

    # Edge List = Precision Edge — SAME schema as longlist
    for ei, pe in enumerate(sl.get("precision_edge", []), 1):
        eng = pe["engines"]
        tk = pe["ticker"]
        d = dsl_all.get(tk, {})
        pe_sc = pe.get("sc_momentum") or _sc_from_engines(eng)
        pe_raw = pe.get("sc_momentum_raw") or pe_sc
        floor = round(min(eng["flow"], eng["energy"], eng["structure"], eng["mp"]), 1)
        export["edge_list"].append({
            "rank": ei,
            "ticker": tk,
            "sc_momentum": round(pe_sc, 1),
            "sc_momentum_raw": round(pe_raw, 1),
            "ptrs": _ptrs(pe_sc, tk),
            "pipe_rank": round(pe.get("pipe_rank", 0), 1),
            "floor": floor,
            "disposition": pe.get("disposition", ""),
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(eng["flow"], 1),
            "energy": round(eng["energy"], 1),
            "structure": round(eng["structure"], 1),
            "mp": round(eng["mp"], 1),
            "elder": eng["elder"],
            "mp_state": _mp_states.get(tk, pe.get("mp_state", "")),
            "entry": pe["levels"].get("entry"),
            "stop": pe["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_be": d.get("be"),
            "dsl_shares": d.get("shares"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),
            "daily_range_proxy": d.get("daily_range_proxy"),
            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                pe.get("pipe_rank", 0), floor, pe_sc,
                True, tk, sm, sector_grades,
            ),
            "source": "edge_list",
            "pe": True,
        })
    longlist_tickers: set[str] = set()
    sorted_rm = sorted(sl.get("recipe_matches", []),
                       key=lambda rm: (
                           _ptrs(rm.get("sc_momentum", 0) or 0, rm["ticker"]),
                           rm.get("pipe_rank", 0),
                           _floor(rm),
                       ),
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
            "beta_30d": (betas.get(rm["ticker"]) or {}).get(30),
            "beta_60d": (betas.get(rm["ticker"]) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(rm["ticker"], rm.get("mp_state", "")),
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
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),
            "daily_range_proxy": d.get("daily_range_proxy"),
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
                ["_ptrs", "pipe_rank", "_floor"], ascending=[False, False, False]
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
                    "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
                    "flow": round(float(wr.get("flow_100", 0)), 1),
                    "energy": round(float(wr.get("energy_100", 0)), 1),
                    "structure": round(
                        float(wr.get("structure_100", 0)), 1
                    ),
                    "mp": round(float(wr.get("mp_100", 0)), 1),
                    "elder": round(float(wr.get("elder_score", 0)), 1),
                    "mp_state": _mp_states.get(tk, str(wr.get("mp_state", ""))),
                    "dsl_stop": d.get("stop"),
                    "dsl_risk": d.get("risk"),
                    "dsl_tp_1r": d.get("tp_1r"),
                    "dsl_tp_2r": d.get("tp_2r"),
                    "dsl_tp_3r": d.get("tp_3r"),
                    "dsl_be": d.get("be"),
                    "dsl_shares": d.get("shares"),
                    "dsl_rr_pct": d.get("rr_pct"),
                    "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),
            "daily_range_proxy": d.get("daily_range_proxy"),
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

    # ---- Permanent schema validation — BLOCKS export on missing fields ----
    _REQUIRED_FIELDS = [
        "ticker", "sc_momentum", "ptrs", "flow", "energy", "structure",
        "mp", "elder", "entry", "stop",
        "dsl_stop", "dsl_be", "dsl_risk", "dsl_rr_pct", "dsl_shares",
        "dsl_atr_ratio", "atr_14d", "daily_range_proxy",
        "dsl_tp_1r", "dsl_tp_2r", "dsl_tp_3r",
        "beta_30d", "beta_60d", "rr_est", "elder_5d", "mp_state", "pe", "pipe_rank",
        "fib", "floor", "rank_explain",
    ]
    for _tier_name in ("top_picks", "edge_list", "longlist"):
        for _rec in export[_tier_name]:
            _missing = [f for f in _REQUIRED_FIELDS if f not in _rec]
            if _missing:
                raise ValueError(
                    f"SCHEMA VIOLATION: {_tier_name} record "
                    f"'{_rec.get('ticker', '?')}' missing fields: {_missing}"
                )

    return export


def _build_ptj(export: dict, date_str: str) -> dict:
    """Build the Pre-Trade Journal (local-only artifact).

    Combines AQE pipeline data (positions, regime, sector health) with the
    scored lists. Written to the local OUTPUT_DIR only — not published to Drive.
    Manual PM notes are NOT included — the PM appends them via Claude.
    """
    from src.pipeline.position_tracker import load_positions, load_closed

    sgt = ZoneInfo("Asia/Singapore")
    regime = export.get("regime", {})
    positions = load_positions()
    closed = load_closed()

    # Build open positions with latest AQE data
    open_pos = []
    # Quick lookup for longlist/watchlist tickers for sector + scores
    ticker_data: dict[str, dict] = {}
    for tier in ("top_picks", "edge_list", "longlist", "watchlist"):
        for rec in export.get(tier, []):
            ticker_data.setdefault(rec["ticker"], rec)

    for p in positions:
        tk = p["ticker"]
        td = ticker_data.get(tk, {})
        open_pos.append({
            "ticker": tk,
            "qty": p.get("shares", 0),
            "entry": p.get("entry_price", 0),
            "close": p.get("last_close", p.get("entry_price", 0)),
            "sl": p.get("current_stop", 0),
            "tier": p.get("current_tier", 1),
            "current_r": p.get("current_r", 0),
            "pnl_usd": p.get("pnl_dollars", 0),
            "days_held": p.get("days_held", 0),
            "be_triggered": p.get("be_triggered", False),
            "flow": td.get("flow", p.get("current_flow", 0)),
            "tp_warning": p.get("tp_warning", False),
            "alerts": p.get("alerts", []),
            "entry_date": p.get("entry_date", ""),
        })

    # Recent closed trades (last 30 days)
    recent_closed = []
    cutoff = str((datetime.now(sgt) - __import__("datetime").timedelta(days=30)).date())
    for c in closed:
        if c.get("exit_date", "") >= cutoff:
            recent_closed.append({
                "ticker": c.get("ticker"),
                "entry": c.get("entry_price"),
                "exit": c.get("exit_price"),
                "exit_date": c.get("exit_date"),
                "final_r": c.get("final_r", 0),
                "pnl_usd": round(
                    (c.get("exit_price", 0) - c.get("entry_price", 0))
                    * c.get("shares", 0), 2
                ) if c.get("exit_price") and c.get("entry_price") else 0,
                "exit_reason": c.get("exit_reason", ""),
            })

    total_unrealised = sum(p.get("pnl_usd") or 0 for p in open_pos)
    total_realised_30d = sum(c.get("pnl_usd") or 0 for c in recent_closed)

    return {
        "version": "2.1-auto",
        "snapshot_date": date_str,
        "generated_at": datetime.now(sgt).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "regime": {
            "level": regime.get("level", ""),
            "vix": regime.get("vix"),
            "hurst": regime.get("hurst"),
            "max_new_size": regime.get("max_new_size", ""),
        },
        "capital": {
            "base": 70_000,
            "risk_pct": 0.03,
            "risk_budget": 2100,
        },
        "open_positions": open_pos,
        "closed_trades_30d": recent_closed,
        "pipeline_top_picks": [
            {"ticker": r["ticker"], "sc_momentum": r["sc_momentum"],
             "ptrs": r["ptrs"], "disposition": r.get("disposition", "")}
            for r in export.get("top_picks", [])
        ],
        "srm_signals": export.get("srm_signals", {}),
        "metrics": {
            "open_count": len(open_pos),
            "open_unrealised": round(total_unrealised, 2),
            "closed_30d_count": len(recent_closed),
            "realised_30d": round(total_realised_30d, 2),
        },
        "summary": export.get("summary", {}),
    }


def _write_file(directory: Path, filename: str, content: str) -> str | None:
    """Write a file to a local directory. Returns path or None if dir missing."""
    if not directory.exists():
        return None
    path = directory / filename
    if path.exists():
        path.unlink()
    path.write_text(content, encoding="utf-8")
    return str(path)


def _upload_file(filename: str, content: str, folder_path: str) -> dict:
    """Upload via Drive REST API. Returns result dict."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            return gdrive_uploader.upload_or_replace(
                filename, content, mime="application/json",
                folder_path=folder_path,
            )
        return {"ok": False, "reason": "not configured"}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"uploader error: {exc}"}


def export_to_drive(shortlist: dict | None = None) -> dict:
    """Build the combined export JSON and publish it to the AQE Drive folder.

    Publishes ONE file, overwriting it each run so the folder never clutters:
      AQE/aqe_daily_export.json — scan + SRM combined (the committee's read)

    written via:
      - Local OUTPUT_DIR (always)
      - Local Drive mount G:\\My Drive\\Trading Strategy\\AQE (if present)
      - Drive REST API (if OAuth configured)

    The pre-trade journal (positions) is written to the local OUTPUT_DIR only —
    it is intentionally NOT published to Drive. The old SRM Daily and AEGIS
    Trade Journal folders are no longer written.

    Returns dict with status and per-file results.
    """
    export = build_export(shortlist)
    if not export:
        return {"status": "skipped", "reason": "No shortlist data"}

    date_str = export.get("date", "unknown")
    written: list[str] = []
    drive_results: list[dict] = []

    # ---- 1. AQE export ----
    aqe_content = json.dumps(export, indent=2)
    local_aqe = OUTPUT_DIR / EXPORT_FILENAME
    if local_aqe.exists():
        local_aqe.unlink()
    local_aqe.write_text(aqe_content, encoding="utf-8")
    written.append(str(local_aqe))

    result = _write_file(DRIVE_EXPORT_DIR, EXPORT_FILENAME, aqe_content)
    if result:
        written.append(result)
    r = _upload_file(EXPORT_FILENAME, aqe_content, CLOUD_AQE_PATH)
    drive_results.append({"file": EXPORT_FILENAME, "target": "AQE", **r})
    if r.get("ok"):
        written.append(f"gdrive:AQE/{EXPORT_FILENAME}")

    # ---- 2. Pre-Trade Journal — LOCAL ONLY (never published to Drive) ----
    # Positions/closed trades stay on the local machine. The old SRM Daily and
    # AEGIS Trade Journal Drive folders are no longer written; SRM grading now
    # rides inside the combined AQE export above.
    ptj = _build_ptj(export, date_str)
    ptj_filename = f"aegis_trade_journal_{date_str}"
    ptj_content = json.dumps(ptj, indent=2)
    ptj_local = OUTPUT_DIR / ptj_filename
    if ptj_local.exists():
        ptj_local.unlink()
    ptj_local.write_text(ptj_content, encoding="utf-8")
    written.append(str(ptj_local))

    # Status: ok if anything beyond local OUTPUT_DIR was written
    drive_written = [w for w in written if "G:\\" in w or "gdrive:" in w]
    status = "ok" if drive_written else "partial"
    reason = None
    if status == "partial":
        reason = (
            "Drive not published. Local mount not found and "
            "cloud OAuth env vars not set."
        )

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
