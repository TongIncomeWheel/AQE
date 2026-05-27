"""S11 -- Market Open Brief view (mobile-first, NiceGUI).

Spec §14.15. Triggered at 21:30 SGT. Web equivalent of the Telegram message.
Focus: overnight gaps vs prior close, active brackets the PM must confirm in
IBKR, and any open-related priority actions (gap-down near SL, RED regime).

Route: /brief/open
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import ui

from src.aic.web import components, theme
from src.aic.web.brief_data import MarketOpenBrief, compose_open

SGT = ZoneInfo("Asia/Singapore")


def render_open() -> None:
    brief: MarketOpenBrief = compose_open()
    ts = _parse_ts(brief.timestamp_sgt)

    components.page_header(
        "AEGIS · MARKET OPEN",
        regime=brief.regime,
        vix=brief.vix,
        capital_usd=brief.capital_usd,
        market_phase="MARKET OPEN (US 09:30 ET)",
        timestamp_sgt=ts,
    )

    # ---- Overnight gaps
    components.section(
        "OVERNIGHT GAPS",
        f"Previous close → today's open · {len(brief.gaps)} positions",
    )
    headers = ("TICKER", "PREV", "OPEN", "Δ$", "Δ%", "SL", "STATUS")
    rows = []
    row_classes = []
    for g in brief.gaps:
        cls = ""
        emoji = "—"
        label = g.status.replace("_", " ")
        if g.status == "NEAR_SL":
            cls = "row-near"
            emoji = "⚠️"
        elif g.status == "GAP_UP":
            emoji = "✅"
        elif g.status == "GAP_DOWN":
            emoji = "▼"
            if g.gap_pct is not None and g.gap_pct < -2.0:
                cls = "row-near"
        elif g.status == "FLAT":
            emoji = "━"
        rows.append((
            g.ticker,
            _fmt(g.prev_close, 2),
            _fmt(g.open_price, 2),
            _fmt(g.gap_dollars, 2),
            _fmt(g.gap_pct, 2, "%"),
            _fmt(g.sl, 2),
            f"{emoji} {label}",
        ))
        row_classes.append(cls)
    components.mono_table(
        headers, rows,
        num_columns=(1, 2, 3, 4, 5),
        row_classes=row_classes,
        empty_message="No open positions to check for gaps.",
    )

    # ---- Active brackets
    components.section(
        "BRACKETS ACTIVE",
        "Confirm each is placed in IBKR before US open",
    )
    bracket_headers = ("TICKER", "LIMIT", "STOP", "NOTE")
    bracket_rows = []
    for b in brief.brackets:
        bracket_rows.append((
            b.ticker,
            _fmt(b.limit_price, 2),
            _fmt(b.stop_price, 2),
            b.note or "—",
        ))
    components.mono_table(
        bracket_headers, bracket_rows,
        num_columns=(1, 2),
        empty_message="No brackets queued in pipeline_state.",
    )

    # ---- Priority actions
    components.section("⚡ PRIORITY")
    components.priority_list(brief.priority_actions)

    components.brief_footer("open")


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
