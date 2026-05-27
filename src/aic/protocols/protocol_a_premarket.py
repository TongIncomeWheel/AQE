"""Protocol A -- Pre-market brief (09:00 SGT / 01:00 ET).

Reads the AQE daily export, audits open positions vs structural stops, runs
the regime check, surfaces new AQE candidates not already in the pipeline,
and assembles the brief dict the delivery layer pushes via Telegram +
web (S02).

Pure Python orchestration -- no LLM calls. Voice deliberation only fires in
Protocol B (when the PM advances a name from the pre-market priority list).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.aic.alfred.orchestrator import (
    StopOutAssessment,
    assess_combined_stopout,
    check_universe_cap,
    classify_regime,
)
from src.aic.data.aqe_reader import (
    DEFAULT_EXPORT_PATH,
    load_export,
)
from src.aic.state import AICStateDB


NEAR_SL_PCT = 3.0          # within 3% -> WARN
BREACH_PCT = 1.0           # within 1% (or below) -> 🔴
PTRS_GATE = 65


@dataclass
class StopAuditRow:
    ticker: str
    close: float | None
    sl: float | None
    distance_pct: float | None
    status: str             # "OK" | "NEAR" | "BREACH"


@dataclass
class PreMarketBrief:
    timestamp_sgt: str
    regime: str
    vix: float
    dynamic_capital_usd: float
    stop_audit: list[StopAuditRow]
    stopout: StopOutAssessment
    universe: dict[str, Any]
    srm_summary: dict[str, Any]
    pipeline_x_aqe: list[dict[str, Any]]
    new_aqe_candidates: list[dict[str, Any]]
    priority_actions: list[str]
    notes: list[str] = field(default_factory=list)


def run_pre_market(
    vix: float,
    dynamic_capital_usd: float,
    open_positions: list[dict],
    export_path: Path | str = DEFAULT_EXPORT_PATH,
    db: AICStateDB | None = None,
) -> PreMarketBrief:
    db = db or AICStateDB()
    export = load_export(export_path)

    regime = classify_regime(vix)

    # ---- Stop audit
    stop_audit: list[StopAuditRow] = []
    open_by_ticker = {p.get("ticker"): p for p in open_positions if p.get("ticker")}
    for tkr, p in open_by_ticker.items():
        close = _f(p.get("close") or p.get("last") or p.get("price"))
        sl = _f(p.get("stop") or p.get("sl"))
        dist = None
        status = "OK"
        if close and sl and close > 0:
            dist = (close - sl) / close * 100.0
            if dist <= BREACH_PCT or close <= sl:
                status = "BREACH"
            elif dist <= NEAR_SL_PCT:
                status = "NEAR"
        stop_audit.append(StopAuditRow(
            ticker=tkr, close=close, sl=sl,
            distance_pct=round(dist, 2) if dist is not None else None,
            status=status,
        ))

    # ---- Combined stop-out (no new candidate yet -- pass zeros)
    stopout = assess_combined_stopout(
        open_positions=open_positions,
        proposed_entry=0, proposed_stop=0, proposed_shares=0,
        dynamic_capital_usd=dynamic_capital_usd,
    )

    # ---- Universe + SRM snapshot
    pipeline_count = db.active_pipeline_count()
    universe = {
        **check_universe_cap(pipeline_count).__dict__,
    }
    srm_summary = {
        "deploy": export.get("srm_deploy") or [],
        "avoid": export.get("srm_avoid") or [],
        "table": export.get("srm") or [],
    }

    # ---- Pipeline × AQE cross-reference (read-only)
    pipeline_rows = db.list_pipeline()
    longlist_lookup = {
        e.get("ticker"): e
        for e in (export.get("longlist") or [])
        if isinstance(e, dict)
    }
    pipeline_x_aqe = []
    for row in pipeline_rows:
        aqe = longlist_lookup.get(row["ticker"])
        pipeline_x_aqe.append({
            "ticker": row["ticker"],
            "status": row["status"],
            "sc_mom": row.get("sc_momentum"),
            "ptrs_cached": row.get("ptrs"),
            "aqe_pipe_rank": (aqe or {}).get("pipe_rank"),
            "aqe_sc_mom": (aqe or {}).get("sc_momentum"),
            "aqe_sector": (aqe or {}).get("gics_sector"),
            "aqe_srm_grade": _grade_for(srm_summary["table"], (aqe or {}).get("gics_sector")),
        })

    # ---- New AQE names not already in pipeline
    pipeline_tickers = {r["ticker"] for r in pipeline_rows}
    new_aqe: list[dict[str, Any]] = []
    for e in (export.get("longlist") or []):
        tk = e.get("ticker")
        if tk and tk not in pipeline_tickers:
            new_aqe.append({
                "ticker": tk,
                "sc_momentum": e.get("sc_momentum"),
                "pipe_rank": e.get("pipe_rank"),
                "gics_sector": e.get("gics_sector"),
                "rr_est": e.get("rr_est"),
            })

    # ---- Priority actions
    priorities: list[str] = []
    near_or_breach = [r for r in stop_audit if r.status in ("NEAR", "BREACH")]
    for r in near_or_breach:
        priorities.append(
            f"{r.ticker} {r.status.lower()} stop (dist {r.distance_pct}%) -- watch at open."
        )
    if regime == "RED":
        priorities.append("REGIME RED: no new entries. Position management only.")
    elif regime == "ORANGE":
        priorities.append("REGIME ORANGE: no new entries. Manage positions only.")
    if universe.get("at_cap"):
        priorities.append("Universe cap reached (10/10). Kill a name before advancing new.")
    if stopout.breaches_5pct:
        priorities.append(
            f"Combined stop-out {stopout.combined_pct:.2f}% > 5% threshold. Elder review required."
        )
    for nc in new_aqe[:3]:
        priorities.append(
            f"{nc['ticker']} new in AQE (SC {nc['sc_momentum']}). Advance to deliberation?"
        )

    return PreMarketBrief(
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        regime=regime,
        vix=vix,
        dynamic_capital_usd=dynamic_capital_usd,
        stop_audit=stop_audit,
        stopout=stopout,
        universe=universe,
        srm_summary=srm_summary,
        pipeline_x_aqe=pipeline_x_aqe,
        new_aqe_candidates=new_aqe,
        priority_actions=priorities,
    )


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _grade_for(srm_table: list, etf: str | None) -> str | None:
    if not etf or not srm_table:
        return None
    for row in srm_table:
        if isinstance(row, dict) and row.get("etf") == etf:
            return row.get("grade")
    return None
