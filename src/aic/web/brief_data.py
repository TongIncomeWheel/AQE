"""Brief view-model composers shared between web routes and Telegram formatters.

For S02 we delegate to the existing `protocol_a_premarket.run_pre_market`.
For S11 (market open) and S12 (market close) we compose lightweight dataclasses
here so the web view and Telegram push pull from a single source.

All composers degrade gracefully when:
  - the AQE export hasn't been written yet (FileNotFoundError -> empty brief)
  - open_positions.json doesn't exist (empty stop audit)
  - the AIC SQLite is empty (zero pipeline rows)

That degradation matters for UAT: the PM can open the web app without first
running a full pipeline + populating SQLite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.aic.alfred.orchestrator import (
    StopOutAssessment,
    assess_combined_stopout,
    classify_regime,
)
from src.aic.data.aqe_reader import DEFAULT_EXPORT_PATH, load_export
from src.aic.protocols.protocol_a_premarket import (
    PreMarketBrief,
    StopAuditRow,
    run_pre_market,
)
from src.aic.state import AICStateDB

SGT = ZoneInfo("Asia/Singapore")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OPEN_POSITIONS_PATH = PROJECT_ROOT / "data" / "open_positions.json"
DEFAULT_CAPITAL_USD = 70_000.0     # spec §1 / Charter §11 baseline
DEFAULT_VIX = 18.0                  # neutral default if no live VIX cached


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_open_positions() -> list[dict]:
    if not OPEN_POSITIONS_PATH.exists():
        return []
    try:
        data = json.loads(OPEN_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        # Map-of-ticker form
        return [{"ticker": k, **(v if isinstance(v, dict) else {})}
                for k, v in data.items()]
    if isinstance(data, list):
        return data
    return []


def _safe_load_export(path: Path | str = DEFAULT_EXPORT_PATH) -> dict:
    try:
        return load_export(path)
    except FileNotFoundError:
        return {}


def _vix_from_export(export: dict, fallback: float = DEFAULT_VIX) -> float:
    """AQE export records the VIX under several possible keys; we try them all."""
    for k in ("vix", "vix_close", "vix_last"):
        v = export.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    regime = export.get("regime")
    if isinstance(regime, dict):
        for k in ("vix", "vix_close"):
            v = regime.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
    return fallback


def _capital_from_export(export: dict, fallback: float = DEFAULT_CAPITAL_USD) -> float:
    for k in ("capital_usd", "dynamic_capital", "capital"):
        v = export.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return fallback


def _cash_estimate(capital: float, open_positions: list[dict]) -> float:
    """Estimate cash = capital - sum(qty * entry) for open equity positions."""
    invested = 0.0
    for p in open_positions:
        try:
            invested += float(p.get("qty", 0)) * float(p.get("entry", 0))
        except (TypeError, ValueError):
            continue
    return max(0.0, capital - invested)


# ---------------------------------------------------------------------------
# S02 -- Pre-market brief composer (thin wrapper around the existing protocol)
# ---------------------------------------------------------------------------

def compose_premarket() -> PreMarketBrief:
    export = _safe_load_export()
    vix = _vix_from_export(export)
    capital = _capital_from_export(export)
    open_pos = _load_open_positions()

    if not export:
        # No pipeline run yet -- return an empty-but-valid brief so the UI renders.
        return PreMarketBrief(
            timestamp_sgt=datetime.now(tz=SGT).isoformat(timespec="seconds"),
            regime=classify_regime(vix),
            vix=vix,
            dynamic_capital_usd=capital,
            stop_audit=[],
            stopout=assess_combined_stopout([], 0, 0, 0, capital),
            universe={"count": 0, "cap": 10, "at_cap": False, "warning": False,
                      "message": "No pipeline state yet."},
            srm_summary={"deploy": [], "avoid": [], "table": []},
            pipeline_x_aqe=[],
            new_aqe_candidates=[],
            priority_actions=["AQE export not found -- run daily pipeline to populate."],
            notes=["Brief composed without AQE export (empty state)."],
        )

    return run_pre_market(
        vix=vix,
        dynamic_capital_usd=capital,
        open_positions=open_pos,
    )


# ---------------------------------------------------------------------------
# S11 -- Market Open Brief
# ---------------------------------------------------------------------------

@dataclass
class GapRow:
    ticker: str
    prev_close: float | None
    open_price: float | None
    gap_dollars: float | None
    gap_pct: float | None
    sl: float | None
    near_sl: bool
    status: str       # "GAP_UP" | "GAP_DOWN" | "FLAT" | "NEAR_SL"


@dataclass
class BracketRow:
    ticker: str
    limit_price: float | None
    stop_price: float | None
    note: str = ""


@dataclass
class MarketOpenBrief:
    timestamp_sgt: str
    regime: str
    vix: float
    capital_usd: float
    gaps: list[GapRow]
    brackets: list[BracketRow]
    priority_actions: list[str]
    notes: list[str] = field(default_factory=list)


GAP_FLAT_THRESHOLD_PCT = 0.10        # |gap| < 0.1% counts as flat
NEAR_SL_PCT = 2.0                     # within 2% of SL after gap -> alert (spec §14.15)


def compose_open(db: AICStateDB | None = None) -> MarketOpenBrief:
    db = db or AICStateDB()
    export = _safe_load_export()
    vix = _vix_from_export(export)
    capital = _capital_from_export(export)
    open_pos = _load_open_positions()
    regime = classify_regime(vix)

    # ---- Overnight gaps
    gaps: list[GapRow] = []
    for p in open_pos:
        prev = _f(p.get("prev_close") or p.get("close"))
        opx = _f(p.get("open") or p.get("open_price") or p.get("last"))
        sl = _f(p.get("stop") or p.get("sl"))
        gap_d = gap_p = None
        status = "FLAT"
        near_sl = False
        if prev and opx and prev > 0:
            gap_d = opx - prev
            gap_p = gap_d / prev * 100.0
            if abs(gap_p) < GAP_FLAT_THRESHOLD_PCT:
                status = "FLAT"
            elif gap_p > 0:
                status = "GAP_UP"
            else:
                status = "GAP_DOWN"
        if opx and sl and sl > 0:
            dist = (opx - sl) / opx * 100
            if dist <= NEAR_SL_PCT:
                near_sl = True
                status = "NEAR_SL"
        gaps.append(GapRow(
            ticker=p.get("ticker") or "?",
            prev_close=prev, open_price=opx,
            gap_dollars=round(gap_d, 2) if gap_d is not None else None,
            gap_pct=round(gap_p, 2) if gap_p is not None else None,
            sl=sl, near_sl=near_sl, status=status,
        ))

    # ---- Active brackets pulled from AIC pipeline_state
    brackets: list[BracketRow] = []
    for row in db.list_pipeline():
        if row.get("status") != "BRACKET":
            continue
        brackets.append(BracketRow(
            ticker=row["ticker"],
            limit_price=_f(row.get("bracket_entry")),
            stop_price=_f(row.get("bracket_stop")),
            note=row.get("session_notes") or "",
        ))

    # ---- Priority actions
    priorities: list[str] = []
    for g in gaps:
        if g.status == "NEAR_SL":
            priorities.append(
                f"{g.ticker} gap-down within {NEAR_SL_PCT}% of SL "
                f"({g.sl:.2f}). Watch close."
            )
        elif g.status == "GAP_DOWN" and g.gap_pct is not None and g.gap_pct < -2.0:
            priorities.append(
                f"{g.ticker} gap-down {g.gap_pct:.1f}% -- review at open."
            )
    for b in brackets:
        priorities.append(
            f"Confirm {b.ticker} bracket in IBKR "
            f"(LMT {b.limit_price or '—'}, STP {b.stop_price or '—'})."
        )
    if regime == "RED":
        priorities.insert(0, "REGIME RED: no new entries. Manage positions only.")

    return MarketOpenBrief(
        timestamp_sgt=datetime.now(tz=SGT).isoformat(timespec="seconds"),
        regime=regime,
        vix=vix,
        capital_usd=capital,
        gaps=gaps,
        brackets=brackets,
        priority_actions=priorities,
    )


# ---------------------------------------------------------------------------
# S12 -- Market Close Brief
# ---------------------------------------------------------------------------

@dataclass
class EodPositionRow:
    ticker: str
    close: float | None
    sl: float | None
    tier: int | None
    near_sl: bool


@dataclass
class TrailEvent:
    ticker: str
    new_tier: int | None
    old_sl: float | None
    new_sl: float | None


@dataclass
class SRMDeltaRow:
    etf: str
    from_grade: str
    to_grade: str
    direction: str          # "UPGRADE" | "DOWNGRADE"


@dataclass
class IbkrUpdate:
    label: str              # human-readable line
    payload: str            # copy-to-clipboard string


@dataclass
class MarketCloseBrief:
    timestamp_sgt: str
    regime: str
    vix: float
    session_pnl_usd: float | None
    realised_pnl_usd: float | None
    unrealised_pnl_usd: float | None
    q2_cumulative_realised: float | None
    eod_positions: list[EodPositionRow]
    trail_events: list[TrailEvent]
    srm_delta: list[SRMDeltaRow]
    ibkr_updates: list[IbkrUpdate]
    api_cost_today_usd: float
    notes: list[str] = field(default_factory=list)


def compose_close(
    session_id: str | None = None,
    db: AICStateDB | None = None,
) -> MarketCloseBrief:
    db = db or AICStateDB()
    export = _safe_load_export()
    vix = _vix_from_export(export)
    open_pos = _load_open_positions()

    # ---- EOD positions
    eod: list[EodPositionRow] = []
    for p in open_pos:
        close = _f(p.get("close") or p.get("last"))
        sl = _f(p.get("stop") or p.get("sl"))
        tier = p.get("tier") or p.get("dsg10_tier")
        try:
            tier_i = int(tier) if tier is not None else None
        except (TypeError, ValueError):
            tier_i = None
        near = False
        if close and sl and close > 0:
            near = (close - sl) / close * 100 < 3.0
        eod.append(EodPositionRow(
            ticker=p.get("ticker") or "?",
            close=close, sl=sl, tier=tier_i, near_sl=near,
        ))

    # ---- Trail events / SRM delta come from the position tracker + SRM trend.
    # Both are stubbed here; the protocol-D layer will hook them as the AQE
    # close-pipeline matures. For UAT we synthesise from any "trail" / "srm_delta"
    # keys the position file might carry.
    trail_events = _trail_events_from_positions(open_pos)
    srm_delta = _srm_delta_from_export(export)

    # ---- IBKR updates from trail events (copy-to-clipboard format)
    ibkr_updates: list[IbkrUpdate] = []
    for ev in trail_events:
        if ev.new_sl is not None:
            payload = f"TRAIL {ev.ticker} STP {ev.new_sl:.2f}"
            ibkr_updates.append(IbkrUpdate(
                label=f"{ev.ticker}: change SL "
                      f"{ev.old_sl:.2f} → {ev.new_sl:.2f}"
                      if ev.old_sl is not None
                      else f"{ev.ticker}: set SL {ev.new_sl:.2f}",
                payload=payload,
            ))

    api_cost = db.session_cost_usd(session_id) if session_id else 0.0

    return MarketCloseBrief(
        timestamp_sgt=datetime.now(tz=SGT).isoformat(timespec="seconds"),
        regime=classify_regime(vix),
        vix=vix,
        session_pnl_usd=_aggregate_unrealised(open_pos),
        realised_pnl_usd=None,
        unrealised_pnl_usd=_aggregate_unrealised(open_pos),
        q2_cumulative_realised=None,
        eod_positions=eod,
        trail_events=trail_events,
        srm_delta=srm_delta,
        ibkr_updates=ibkr_updates,
        api_cost_today_usd=round(api_cost, 4),
        notes=[],
    )


def _trail_events_from_positions(open_pos: list[dict]) -> list[TrailEvent]:
    events: list[TrailEvent] = []
    for p in open_pos:
        trail = p.get("trail_event")
        if not isinstance(trail, dict):
            continue
        events.append(TrailEvent(
            ticker=p.get("ticker") or "?",
            new_tier=_i(trail.get("new_tier")),
            old_sl=_f(trail.get("old_sl")),
            new_sl=_f(trail.get("new_sl")),
        ))
    return events


def _srm_delta_from_export(export: dict) -> list[SRMDeltaRow]:
    deltas: list[SRMDeltaRow] = []
    for d in (export.get("srm_delta") or []):
        if not isinstance(d, dict):
            continue
        fg = (d.get("from_grade") or d.get("from") or "").upper()
        tg = (d.get("to_grade") or d.get("to") or "").upper()
        if not (fg and tg):
            continue
        order = ["AVOID", "TURNING", "WATCH", "HOLD", "DEPLOY"]
        try:
            direction = "UPGRADE" if order.index(tg) > order.index(fg) else "DOWNGRADE"
        except ValueError:
            direction = "UPGRADE"
        deltas.append(SRMDeltaRow(
            etf=d.get("etf") or "?",
            from_grade=fg, to_grade=tg, direction=direction,
        ))
    return deltas


def _aggregate_unrealised(open_pos: list[dict]) -> float | None:
    total = 0.0
    n = 0
    for p in open_pos:
        try:
            qty = float(p.get("qty", 0))
            entry = float(p.get("entry", 0))
            close = float(p.get("close", p.get("last", 0)))
        except (TypeError, ValueError):
            continue
        if qty and entry and close:
            total += (close - entry) * qty
            n += 1
    return round(total, 2) if n else None


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
