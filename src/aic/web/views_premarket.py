"""S02 -- Pre-Market Brief view (mobile-first, NiceGUI).

Renders the web equivalent of the Telegram message described in spec §14.6b.
Backed by `brief_data.compose_premarket()` which delegates to the existing
`protocol_a_premarket.run_pre_market()`.

Route: /brief/premarket
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import ui

from src.aic.web import components, theme
from src.aic.web.brief_data import compose_premarket

SGT = ZoneInfo("Asia/Singapore")


def render_premarket() -> None:
    brief = compose_premarket()

    # Convert ISO timestamp -> datetime for the header
    ts = _parse_ts(brief.timestamp_sgt)
    pipeline_count = brief.universe.get("count")
    pipeline_cap = brief.universe.get("cap", 10)
    cash_estimate = _cash_estimate(brief.dynamic_capital_usd, brief.stop_audit)

    components.page_header(
        "AEGIS · PRE-MARKET BRIEF",
        regime=brief.regime,
        vix=brief.vix,
        capital_usd=brief.dynamic_capital_usd,
        cash_usd=cash_estimate,
        pipeline_count=pipeline_count,
        pipeline_cap=pipeline_cap,
        market_phase="PRE-MARKET (US 01:00 ET)",
        timestamp_sgt=ts,
    )

    # ---- STOP AUDIT
    components.section(
        "STOP AUDIT",
        f"Open positions reviewed vs structural SL · {len(brief.stop_audit)} rows",
    )
    headers = ("#", "TICKER", "CLOSE", "SL", "DIST %", "STATUS")
    rows = []
    row_classes = []
    for i, r in enumerate(brief.stop_audit, 1):
        cls = ""
        if r.status == "NEAR":
            cls = "row-near"
        elif r.status == "BREACH":
            cls = "row-breach"
        emoji = theme.STATUS_EMOJI.get(r.status, "·")
        rows.append((
            str(i),
            r.ticker,
            _fmt(r.close, 2),
            _fmt(r.sl, 2),
            _fmt(r.distance_pct, 1, "%"),
            f"{emoji} {r.status}",
        ))
        row_classes.append(cls)
    components.mono_table(
        headers, rows, num_columns=(0, 2, 3, 4),
        row_classes=row_classes,
        empty_message="No open positions tracked in data/open_positions.json.",
    )

    so = brief.stopout
    bar_colour = theme.RED if so.breaches_5pct else theme.GREEN
    ui.html(
        f'<div class="aegis-mono" style="margin-top:8px;color:{bar_colour}">'
        f'Combined stop-out risk: ${so.combined_usd:,.0f} '
        f'({so.combined_pct:.2f}% of capital) '
        f'{"⚠️ ELDER REVIEW" if so.breaches_5pct else "✅"}'
        f'</div>'
    )

    # ---- SRM bands
    components.section("SECTOR ROTATION — SRM v3.0")
    srm_table = brief.srm_summary.get("table") or []
    if srm_table:
        components.srm_bands(srm_table)
    else:
        with ui.card().classes("w-full"):
            ui.label("SRM table missing from export — run daily pipeline.") \
                .style(f"color: {theme.TEXT_DIM};")

    # ---- Pipeline × AQE cross reference
    components.section(
        "PIPELINE × AQE CROSS-REFERENCE",
        f"{len(brief.pipeline_x_aqe)} pipeline names aligned to AQE longlist",
    )
    pxa_headers = ("TICKER", "STATUS", "SC_MOM", "PTRS", "AQE RANK", "SECTOR", "SRM")
    pxa_rows = []
    pxa_classes = []
    for r in brief.pipeline_x_aqe:
        pxa_rows.append((
            r["ticker"],
            r["status"] or "—",
            _fmt(r.get("aqe_sc_mom") or r.get("sc_mom"), 1),
            _fmt(r.get("ptrs_cached"), 1),
            f"#{r.get('aqe_pipe_rank')}" if r.get("aqe_pipe_rank") else "—",
            r.get("aqe_sector") or "—",
            (r.get("aqe_srm_grade") or "—"),
        ))
        pxa_classes.append("")
    components.mono_table(
        pxa_headers, pxa_rows,
        num_columns=(2, 3, 4),
        row_classes=pxa_classes,
        empty_message="No pipeline names yet -- advance candidates from S04.",
    )

    # ---- New in AQE today
    components.section(
        "NEW IN AQE TODAY",
        f"Names on AQE longlist not yet in pipeline · {len(brief.new_aqe_candidates)} candidates",
    )
    new_headers = ("TICKER", "SC_MOM", "AQE RANK", "SECTOR", "R/R EST")
    new_rows = []
    for nc in brief.new_aqe_candidates[:10]:
        new_rows.append((
            nc["ticker"],
            _fmt(nc.get("sc_momentum"), 1),
            f"#{nc.get('pipe_rank')}" if nc.get("pipe_rank") else "—",
            nc.get("gics_sector") or "—",
            _fmt(nc.get("rr_est"), 2, "x"),
        ))
    components.mono_table(
        new_headers, new_rows, num_columns=(1, 2, 4),
        empty_message="Nothing new on the AQE longlist today.",
    )

    # ---- Priority actions
    components.section("⚡ PRIORITY ACTIONS")
    components.priority_list(brief.priority_actions)

    # ---- Footer
    components.brief_footer("premarket")


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


def _cash_estimate(capital_usd: float, stop_audit) -> float | None:
    # Best-effort cash estimate from stop_audit rows that carry qty+entry.
    # `stop_audit` is a list of StopAuditRow which doesn't expose qty/entry --
    # so we cannot compute exactly. Return None to suppress the KPI.
    _ = capital_usd, stop_audit
    return None
