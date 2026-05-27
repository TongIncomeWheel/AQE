"""Shared NiceGUI components -- regime header, KPI strip, monospace tables, etc.

Every brief (S02 / S11 / S12) is composed from these building blocks so a tweak
to the design system propagates everywhere. All components are mobile-first --
nothing here assumes a > 480px viewport.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from nicegui import ui

from src.aic.web import theme

SGT = ZoneInfo("Asia/Singapore")
ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def page_header(
    title: str,
    *,
    regime: str,
    vix: float | None,
    capital_usd: float | None,
    cash_usd: float | None = None,
    pipeline_count: int | None = None,
    pipeline_cap: int = 10,
    market_phase: str = "",
    timestamp_sgt: datetime | None = None,
) -> None:
    """Persistent header per spec §14.6b / §14.7 -- mobile-first."""
    now = timestamp_sgt or datetime.now(tz=SGT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SGT)
    now_sgt = now.astimezone(SGT)
    now_et = now.astimezone(ET)

    with ui.element("div").classes("w-full mb-2"):
        with ui.row().classes("items-center justify-between w-full gap-2 px-1"):
            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-base font-semibold").style(
                    f"color: {theme.GOLD}; letter-spacing: 0.18em;"
                )
                ui.label(
                    f"{now_sgt.strftime('%a %d %b %Y · %H:%M')} SGT  ·  "
                    f"{now_et.strftime('%H:%M')} ET  ·  {market_phase or ''}"
                ).classes("text-xs").style(f"color: {theme.TEXT_DIM};")
            regime_badge(regime, vix)

        # KPI strip
        with ui.row().classes(
            "items-stretch gap-2 w-full mt-2 aegis-stack"
        ).style("flex-wrap: wrap;"):
            kpi("REGIME",
                f"{theme.REGIME_EMOJI.get(regime, '·')} {regime}",
                color=theme.REGIME_COLOURS.get(regime, theme.TEXT_PRIMARY))
            kpi("VIX",
                f"{vix:.2f}" if vix is not None else "—",
                color=theme.TEXT_PRIMARY)
            kpi("CAPITAL",
                f"${capital_usd:,.0f}" if capital_usd is not None else "—",
                color=theme.GOLD)
            if cash_usd is not None and capital_usd:
                pct = cash_usd / capital_usd * 100 if capital_usd else 0
                kpi("CASH",
                    f"${cash_usd:,.0f}",
                    sub=f"{pct:.1f}%")
            if pipeline_count is not None:
                kpi("PIPELINE",
                    f"{pipeline_count}/{pipeline_cap}",
                    sub=f"{int(pipeline_count / max(pipeline_cap,1) * 100)}% used")


def regime_badge(regime: str, vix: float | None = None) -> None:
    cls = theme.regime_badge_class(regime)
    emoji = theme.REGIME_EMOJI.get(regime, "·")
    vix_str = f" · VIX {vix:.2f}" if vix is not None else ""
    ui.html(f'<span class="{cls}">{emoji} {regime}{vix_str}</span>')


def kpi(label: str, value: str, *, sub: str | None = None, color: str | None = None) -> None:
    with ui.element("div").style(
        f"flex: 1 1 130px; min-width: 110px; padding: 10px 14px; "
        f"background: {theme.BG_SURFACE_1}; border: 1px solid {theme.BORDER_DIM};"
        f"border-radius: 8px;"
    ):
        ui.html(f'<div class="aegis-label">{label}</div>')
        c = color or theme.TEXT_PRIMARY
        ui.html(
            f'<div class="aegis-value aegis-mono" style="color: {c}">{value}</div>'
        )
        if sub:
            ui.html(
                f'<div class="aegis-mono" style="font-size:10px;color:{theme.TEXT_DIM}">{sub}</div>'
            )


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def section(title: str, subtitle: str | None = None) -> None:
    ui.html(f'<div class="aegis-section-h">{title}</div>')
    if subtitle:
        ui.html(
            f'<div class="aegis-mono" style="font-size:10px;color:{theme.TEXT_DIM};'
            f'margin-bottom:6px">{subtitle}</div>'
        )


# ---------------------------------------------------------------------------
# Monospace table -- the spec's bread-and-butter element
# ---------------------------------------------------------------------------

def mono_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    num_columns: Sequence[int] = (),
    row_classes: Sequence[str] | None = None,
    empty_message: str = "No rows.",
) -> None:
    """Render a monospace data table inside an Aegis card.

    `headers`        column titles.
    `rows`           list of string sequences (one per data row).
    `num_columns`    indexes of right-aligned numeric columns.
    `row_classes`    optional per-row CSS class (e.g. "row-near", "row-breach").
    """
    rows_list = list(rows)
    if not rows_list:
        with ui.card().classes("w-full"):
            ui.label(empty_message).style(f"color: {theme.TEXT_DIM};")
        return

    row_classes = list(row_classes or [""] * len(rows_list))
    while len(row_classes) < len(rows_list):
        row_classes.append("")

    th_html = "".join(
        f'<th class="{"num" if i in num_columns else ""}">{h}</th>'
        for i, h in enumerate(headers)
    )
    body_html_parts = []
    for cls, row in zip(row_classes, rows_list):
        tds = "".join(
            f'<td class="{"num" if i in num_columns else ""}">{cell}</td>'
            for i, cell in enumerate(row)
        )
        body_html_parts.append(f'<tr class="{cls}">{tds}</tr>')

    with ui.card().classes("w-full").style("padding: 6px 10px;"):
        ui.html(
            f'<table class="aegis-table">'
            f'<thead><tr>{th_html}</tr></thead>'
            f'<tbody>{"".join(body_html_parts)}</tbody>'
            f'</table>'
        )


# ---------------------------------------------------------------------------
# SRM band display (DEPLOY / HOLD / WATCH / TURNING / AVOID)
# ---------------------------------------------------------------------------

def srm_bands(rows: Sequence[dict]) -> None:
    """Render SRM as horizontal grade bands per spec §14.6b.

    Each row needs `etf` + `grade` (DEPLOY/HOLD/WATCH/TURNING/AVOID) and
    optional `sh` for the bar-fill rendering.
    """
    groups: dict[str, list[dict]] = {
        "DEPLOY": [], "HOLD": [], "WATCH": [], "TURNING": [], "AVOID": [],
    }
    for r in rows:
        g = (r.get("grade") or "").upper()
        if g in groups:
            groups[g].append(r)

    with ui.card().classes("w-full").style("padding: 10px 14px;"):
        for grade, items in groups.items():
            if not items:
                continue
            with ui.row().classes("items-center gap-2 w-full").style("flex-wrap: nowrap;"):
                ui.html(
                    f'<div class="aegis-mono" style="width:78px;'
                    f'color:{_grade_colour(grade)};font-weight:600;font-size:11px;'
                    f'letter-spacing:0.08em">'
                    f'{theme.STATUS_EMOJI.get(grade,"·")} {grade}</div>'
                )
                with ui.row().classes("items-center gap-2").style("flex-wrap: wrap;"):
                    for r in items:
                        ui.html(_srm_chip(r, grade))


def _srm_chip(row: dict, grade: str) -> str:
    etf = row.get("etf", "?")
    sh = row.get("sh")
    fill = ""
    if sh is not None:
        try:
            fill_count = max(1, min(12, int(round((float(sh) + 8) / 16 * 12))))
            fill = " " + "█" * fill_count
        except (TypeError, ValueError):
            fill = ""
    colour = _grade_colour(grade)
    return (
        f'<span class="aegis-mono" style="background:{theme.BG_SURFACE_1};'
        f'border:1px solid {theme.BORDER_DIM};padding:3px 8px;border-radius:4px;'
        f'color:{colour};font-size:10px">{etf}{fill}</span>'
    )


def _grade_colour(grade: str) -> str:
    return {
        "DEPLOY":  theme.GREEN,
        "HOLD":    theme.TEXT_PRIMARY,
        "WATCH":   theme.GOLD,
        "TURNING": theme.YELLOW,
        "AVOID":   theme.RED,
    }.get(grade, theme.TEXT_DIM)


# ---------------------------------------------------------------------------
# Priority actions list
# ---------------------------------------------------------------------------

def priority_list(actions: Sequence[str]) -> None:
    if not actions:
        ui.label("No priority items.").style(f"color: {theme.TEXT_DIM};")
        return
    with ui.card().classes("w-full").style("padding: 10px 14px;"):
        for i, action in enumerate(actions, 1):
            with ui.row().classes("items-start gap-2 w-full"):
                ui.html(
                    f'<span class="aegis-mono" style="color:{theme.AMBER};'
                    f'font-weight:600;min-width:18px">{i}.</span>'
                )
                ui.html(
                    f'<span style="color:{theme.TEXT_PRIMARY};font-size:12px">{action}</span>'
                )


# ---------------------------------------------------------------------------
# Footer with brief navigation
# ---------------------------------------------------------------------------

def brief_footer(current: str) -> None:
    targets = [
        ("premarket", "/brief/premarket", "PRE-MARKET"),
        ("open",      "/brief/open",      "MARKET OPEN"),
        ("close",     "/brief/close",     "MARKET CLOSE"),
    ]
    parts = ['<div class="aegis-footer">']
    parts.append('<div>AEGIS Investment Committee · POC build</div>')
    parts.append('<div>')
    for key, href, label in targets:
        if key == current:
            parts.append(
                f'<span class="aegis-mono" style="color:{theme.GOLD};'
                f'border-bottom:1px solid {theme.GOLD};padding:0 6px">{label}</span> '
            )
        else:
            parts.append(f'<a class="aegis-mono" href="{href}" style="padding:0 6px">{label}</a> ')
    parts.append("</div></div>")
    ui.html("".join(parts))


# ---------------------------------------------------------------------------
# Copy-to-clipboard line (used by S12 IBKR updates)
# ---------------------------------------------------------------------------

def copy_line(label: str, payload: str) -> None:
    safe = payload.replace("'", "\\'")
    with ui.row().classes("items-center gap-2 w-full"):
        ui.html(
            f'<span class="aegis-mono" style="color:{theme.TEXT_PRIMARY};'
            f'font-size:11px">{label}</span>'
        )
        ui.html(
            f'<code style="background:{theme.BG_SURFACE_2};padding:2px 6px;'
            f'border-radius:4px;font-family:var(--font-mono);font-size:10px;'
            f'color:{theme.GOLD}">{payload}</code>'
        )
        btn = ui.button("Copy", icon="content_copy").props("flat dense size=sm")
        btn.on(
            "click",
            js_handler=f"() => navigator.clipboard.writeText('{safe}')",
        )
