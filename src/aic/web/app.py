"""AIC NiceGUI app -- entrypoint for the three daily briefs.

Routes:
    /                  index (links to all three briefs + Telegram preview)
    /brief/premarket   S02 -- Pre-Market Brief
    /brief/open        S11 -- Market Open Brief
    /brief/close       S12 -- Market Close Brief
    /telegram/premarket  -- raw text preview (S02 Telegram format)
    /telegram/open       -- raw text preview (S11)
    /telegram/close      -- raw text preview (S12)

Mobile-first layout per spec §14.24. Designed for iPhone 14 (390px) but scales
up gracefully to desktop.

Launch:
    run_aic_web.bat
    python -m src.aic.web.app
"""

from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui

from src.aic.web import DEFAULT_PORT, theme
from src.aic.web.components import brief_footer, page_header
from src.aic.web.views_close import render_close
from src.aic.web.views_open import render_open
from src.aic.web.views_premarket import render_premarket

SGT = ZoneInfo("Asia/Singapore")


# ---------------------------------------------------------------------------
# Global CSS + viewport + favicon (one-time setup)
# ---------------------------------------------------------------------------

ui.add_head_html(
    '<meta name="viewport" content="width=device-width, initial-scale=1, '
    'maximum-scale=1, viewport-fit=cover">',
    shared=True,
)
ui.add_head_html(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700&'
    'family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">',
    shared=True,
)
ui.add_css(theme.GLOBAL_CSS, shared=True)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _page_shell(content_renderer) -> None:
    """Common mobile-first shell. Sets dark + max-width 720 column."""
    ui.query("body").style(
        f"background:{theme.BG_BASE}; color:{theme.TEXT_PRIMARY}; "
        f"margin:0; padding:0; min-height:100vh;"
    )
    with ui.column().classes("w-full").style(
        f"max-width: 720px; margin: 0 auto; padding: 14px 12px; "
        f"font-family: var(--font-sans);"
    ):
        content_renderer()


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@ui.page("/")
def index_page() -> None:
    def render() -> None:
        page_header(
            "AEGIS INVESTMENT COMMITTEE",
            regime="GREEN",
            vix=None,
            capital_usd=None,
            market_phase="HOME",
            timestamp_sgt=datetime.now(tz=SGT),
        )
        with ui.card().classes("w-full mt-2").style("padding: 14px;"):
            ui.html(
                f'<div class="aegis-section-h">DAILY BRIEFS</div>'
                f'<div style="color:{theme.TEXT_DIM};font-size:12px;margin-bottom:10px">'
                f'Mobile-first views. Same data the Telegram bot pushes.</div>'
            )
            _link_row("/brief/premarket", "Pre-Market Brief (S02)",
                      "09:00 SGT · stop audit, SRM, pipeline x AQE, new candidates")
            _link_row("/brief/open", "Market Open Brief (S11)",
                      "21:30 SGT · overnight gaps, active brackets, priority items")
            _link_row("/brief/close", "Market Close Brief (S12)",
                      "04:00 SGT · session P&L, EOD audit, trail events, IBKR updates")

        with ui.card().classes("w-full mt-2").style("padding: 14px;"):
            ui.html(
                f'<div class="aegis-section-h">TELEGRAM PREVIEWS</div>'
                f'<div style="color:{theme.TEXT_DIM};font-size:12px;margin-bottom:10px">'
                f"Plain-text view of what'll land in the bot.</div>"
            )
            _link_row("/telegram/premarket", "Pre-Market (text)", "compressed mobile view")
            _link_row("/telegram/open", "Market Open (text)", "compressed mobile view")
            _link_row("/telegram/close", "Market Close (text)", "compressed mobile view")

        brief_footer("index")
    _page_shell(render)


def _link_row(href: str, title: str, sub: str) -> None:
    with ui.row().classes("items-center w-full").style(
        f"padding: 10px 12px; margin-bottom: 6px; "
        f"background: {theme.BG_SURFACE_1}; "
        f"border: 1px solid {theme.BORDER_DIM}; border-radius: 8px;"
    ):
        with ui.column().classes("gap-0").style("flex: 1 1 auto;"):
            ui.html(
                f'<a href="{href}" style="color:{theme.GOLD};text-decoration:none;'
                f'font-weight:600;font-family:var(--font-mono);font-size:13px">{title}</a>'
            )
            ui.html(
                f'<div style="color:{theme.TEXT_DIM};font-size:11px">{sub}</div>'
            )
        ui.html(
            f'<a href="{href}" style="color:{theme.AMBER};'
            f'font-family:var(--font-mono);font-size:11px">OPEN →</a>'
        )


# ---------------------------------------------------------------------------
# Brief routes (web views)
# ---------------------------------------------------------------------------

@ui.page("/brief/premarket")
def premarket_page() -> None:
    _page_shell(render_premarket)


@ui.page("/brief/open")
def open_page() -> None:
    _page_shell(render_open)


@ui.page("/brief/close")
def close_page() -> None:
    _page_shell(render_close)


# ---------------------------------------------------------------------------
# Telegram text previews (raw <pre> rendering)
# ---------------------------------------------------------------------------

@ui.page("/telegram/premarket")
def telegram_premarket() -> None:
    from src.aic.delivery.brief_formatters import format_premarket_telegram
    from src.aic.web.brief_data import compose_premarket
    _render_telegram_preview(
        "PRE-MARKET (S02) — Telegram preview",
        format_premarket_telegram(compose_premarket()),
    )


@ui.page("/telegram/open")
def telegram_open() -> None:
    from src.aic.delivery.brief_formatters import format_open_telegram
    from src.aic.web.brief_data import compose_open
    _render_telegram_preview(
        "MARKET OPEN (S11) — Telegram preview",
        format_open_telegram(compose_open()),
    )


@ui.page("/telegram/close")
def telegram_close() -> None:
    from src.aic.delivery.brief_formatters import format_close_telegram
    from src.aic.web.brief_data import compose_close
    _render_telegram_preview(
        "MARKET CLOSE (S12) — Telegram preview",
        format_close_telegram(compose_close()),
    )


def _render_telegram_preview(title: str, text: str) -> None:
    def render() -> None:
        page_header(title, regime="GREEN", vix=None,
                    capital_usd=None, market_phase="TELEGRAM PREVIEW",
                    timestamp_sgt=datetime.now(tz=SGT))
        with ui.card().classes("w-full mt-2").style("padding: 14px;"):
            ui.html(
                f'<pre style="background:{theme.BG_SURFACE_1};padding:14px;'
                f'border-radius:8px;font-family:var(--font-mono);'
                f'font-size:12px;color:{theme.TEXT_PRIMARY};'
                f'border:1px solid {theme.BORDER_DIM};'
                f'white-space:pre-wrap;line-height:1.5">{_escape(text)}</pre>'
            )
            with ui.row().classes("mt-2 gap-2"):
                btn = ui.button("Copy text", icon="content_copy").props("flat")
                safe = text.replace("`", "\\`").replace("$", "\\$")
                btn.on(
                    "click",
                    js_handler=f"() => navigator.clipboard.writeText(`{safe}`)",
                )
                ui.button("Back", icon="arrow_back",
                          on_click=lambda: ui.navigate.to("/")).props("flat")
        brief_footer("index")
    _page_shell(render)


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;")
              .replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main(port: int = DEFAULT_PORT, host: str = "0.0.0.0", show: bool = True) -> None:
    ui.run(
        title="Aegis Investment Committee",
        host=host, port=port, dark=True, show=show, reload=False,
        favicon="🛡️",
    )


if __name__ in {"__main__", "__mp_main__"}:
    port = DEFAULT_PORT
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    main(port=port)
