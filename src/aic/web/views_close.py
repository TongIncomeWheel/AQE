"""S12 -- Market Close Brief view (mobile-first, NiceGUI).

Spec §14.16. Triggered at 04:00 SGT (16:00 ET). Web equivalent of the Telegram
message. Surfaces: session P&L, EOD positions, trail events that triggered,
SRM grade deltas, IBKR updates (copy-to-clipboard).

Route: /brief/close
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import ui

from src.aic.web import components, theme
from src.aic.web.brief_data import MarketCloseBrief, compose_close

SGT = ZoneInfo("Asia/Singapore")


def render_close() -> None:
    brief: MarketCloseBrief = compose_close()
    ts = _parse_ts(brief.timestamp_sgt)

    components.page_header(
        "AEGIS · CLOSE BRIEF",
        regime=brief.regime,
        vix=brief.vix,
        capital_usd=None,                # capital shown via session-P&L cards below
        market_phase="MARKET CLOSE (US 16:00 ET)",
        timestamp_sgt=ts,
    )

    # ---- Session P&L KPI strip
    with ui.row().classes("items-stretch gap-2 w-full aegis-stack mt-2").style(
        "flex-wrap: wrap;"
    ):
        components.kpi(
            "SESSION P&L",
            _money(brief.session_pnl_usd),
            color=_pnl_colour(brief.session_pnl_usd),
        )
        components.kpi("REALISED", _money(brief.realised_pnl_usd))
        components.kpi("UNREALISED", _money(brief.unrealised_pnl_usd),
                       color=_pnl_colour(brief.unrealised_pnl_usd))
        components.kpi("Q2 CUM", _money(brief.q2_cumulative_realised))
        components.kpi("API COST", f"${brief.api_cost_today_usd:.2f}",
                       color=theme.TEXT_DIM)

    # ---- EOD positions
    components.section(
        "POSITION EOD",
        f"{len(brief.eod_positions)} open at close · SL distance audited",
    )
    headers = ("TICKER", "CLOSE", "SL", "TIER", "STATUS")
    rows = []
    row_classes = []
    for p in brief.eod_positions:
        cls = "row-near" if p.near_sl else ""
        emoji = "⚠️" if p.near_sl else "✅"
        rows.append((
            p.ticker,
            _fmt(p.close, 2),
            _fmt(p.sl, 2),
            f"T{p.tier}" if p.tier is not None else "—",
            f"{emoji} {'NEAR' if p.near_sl else 'OK'}",
        ))
        row_classes.append(cls)
    components.mono_table(
        headers, rows, num_columns=(1, 2),
        row_classes=row_classes,
        empty_message="No open positions to review.",
    )

    # ---- Trail events
    components.section(
        "TRAIL EVENTS TODAY",
        f"{len(brief.trail_events)} stop adjustments triggered",
    )
    if brief.trail_events:
        te_rows = []
        for ev in brief.trail_events:
            te_rows.append((
                ev.ticker,
                f"Tier {ev.new_tier}" if ev.new_tier is not None else "—",
                _fmt(ev.old_sl, 2),
                _fmt(ev.new_sl, 2),
            ))
        components.mono_table(
            ("TICKER", "NEW TIER", "OLD SL", "NEW SL"),
            te_rows, num_columns=(2, 3),
        )
    else:
        with ui.card().classes("w-full"):
            ui.label("No trail tier transitions today.").style(
                f"color: {theme.TEXT_DIM};"
            )

    # ---- SRM delta
    components.section("SRM DELTA")
    if brief.srm_delta:
        for d in brief.srm_delta:
            arrow = "⬆" if d.direction == "UPGRADE" else "⬇"
            colour = theme.GREEN if d.direction == "UPGRADE" else theme.RED
            ui.html(
                f'<div class="aegis-mono" style="color:{colour};font-size:11px">'
                f'{d.etf}: {d.from_grade} → {d.to_grade} {arrow} ({d.direction.lower()})'
                f'</div>'
            )
    else:
        with ui.card().classes("w-full"):
            ui.label("No sector grade changes today.").style(
                f"color: {theme.TEXT_DIM};"
            )

    # ---- IBKR updates required
    components.section(
        "⚡ IBKR UPDATES REQUIRED",
        "Tap a row to copy the order string to clipboard",
    )
    if brief.ibkr_updates:
        with ui.card().classes("w-full").style("padding: 10px 14px;"):
            for u in brief.ibkr_updates:
                components.copy_line(u.label, u.payload)
    else:
        with ui.card().classes("w-full"):
            ui.label("No IBKR adjustments needed.").style(
                f"color: {theme.TEXT_DIM};"
            )

    ui.html(
        f'<div class="aegis-mono" style="margin-top:10px;color:{theme.TEXT_DIM};font-size:11px">'
        f'PTJ auto-runs at 04:30 SGT.'
        f'</div>'
    )

    components.brief_footer("close")


def _parse_ts(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(tz=SGT)


def _fmt(v, ndigits: int = 2, suffix: str = "") -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{ndigits}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ("−" if v < 0 else " ")
    return f"{sign}${abs(v):,.0f}"


def _pnl_colour(v: float | None) -> str:
    if v is None or v == 0:
        return theme.TEXT_PRIMARY
    return theme.GREEN if v > 0 else theme.RED
