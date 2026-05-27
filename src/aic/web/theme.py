"""Aegis design system -- spec §14.1 colour palette + typography ported to CSS.

The committee charter has an exact palette; we expose it as Python constants
(used by inline Tailwind class strings) and as a single CSS block that the
NiceGUI app injects on startup. Keeping it isolated means every brief screen
references the same tokens, and we never re-pick "what was the regime green
again?" by hand.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Token constants (spec §14.1) -- imported by views for inline styling.
# ---------------------------------------------------------------------------

BG_BASE = "#080B10"
BG_SURFACE_0 = "#0D1117"
BG_SURFACE_1 = "#111820"
BG_SURFACE_2 = "#161E2A"

BORDER_DIM = "#1A2436"
BORDER_HI = "#253550"

AMBER = "#F0A500"
AMBER_DIM = "#7A5200"
GOLD = "#FFD060"

GREEN = "#22C55E"
GREEN_DARK = "#14532D"
YELLOW = "#F59E0B"
ORANGE = "#F97316"
RED = "#F43F5E"
RED_DARK = "#881337"

CELL_DELIB = "#F0A500"
CELL_RISK = "#22D3EE"
CELL_DESIGN = "#A78BFA"
CELL_ALFRED = "#60A5FA"

TEXT_PRIMARY = "#E2E8F0"
TEXT_DIM = "#8392A5"
TEXT_MUTED = "#3D4F63"


REGIME_COLOURS = {
    "GREEN": GREEN,
    "YELLOW": YELLOW,
    "ORANGE": ORANGE,
    "RED": RED,
}

# Emoji indicators -- exactly what the spec calls for in Telegram + web view.
REGIME_EMOJI = {
    "GREEN": "🟢",
    "YELLOW": "🟡",
    "ORANGE": "🟠",
    "RED": "🔴",
}

STATUS_EMOJI = {
    "OK": "✅",
    "NEAR": "⚠️",
    "BREACH": "🔴",
    "DEPLOY": "▲",
    "HOLD": "━",
    "TURNING": "↗",
    "WATCH": "◇",
    "AVOID": "▼",
}


# ---------------------------------------------------------------------------
# Global CSS -- injected once on app start (see web/app.py).
# ---------------------------------------------------------------------------

GLOBAL_CSS = f"""
:root {{
  --bg-base:       {BG_BASE};
  --bg-surface-0:  {BG_SURFACE_0};
  --bg-surface-1:  {BG_SURFACE_1};
  --bg-surface-2:  {BG_SURFACE_2};
  --border-dim:    {BORDER_DIM};
  --border-hi:     {BORDER_HI};
  --amber:         {AMBER};
  --amber-dim:     {AMBER_DIM};
  --gold:          {GOLD};
  --green:         {GREEN};
  --yellow:        {YELLOW};
  --orange:        {ORANGE};
  --red:           {RED};
  --text-primary:  {TEXT_PRIMARY};
  --text-dim:      {TEXT_DIM};
  --text-muted:    {TEXT_MUTED};
  --font-mono:     'JetBrains Mono', 'Courier New', monospace;
  --font-sans:     'Inter', 'Segoe UI', sans-serif;
}}

html, body {{
  background: var(--bg-base) !important;
  color: var(--text-primary);
  font-family: var(--font-sans);
}}

/* NiceGUI overrides */
.q-card, .nicegui-card {{
  background: var(--bg-surface-0) !important;
  border: 1px solid var(--border-dim);
  border-radius: 10px;
}}
.q-card--bordered {{ border-color: var(--border-dim) !important; }}

.aegis-mono {{ font-family: var(--font-mono); letter-spacing: 0.01em; }}
.aegis-label {{
  font-size: 9px; letter-spacing: 0.12em;
  color: var(--text-dim); text-transform: uppercase;
}}
.aegis-value {{ font-size: 16px; font-weight: 600; }}
.aegis-kpi-big {{ font-size: 22px; font-weight: 700; }}
.aegis-section-h {{
  font-size: 11px; letter-spacing: 0.18em; color: var(--text-dim);
  text-transform: uppercase; margin-top: 18px; margin-bottom: 6px;
}}

/* Regime badge variants */
.aegis-badge {{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  font-family: var(--font-mono); font-weight: 600; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  border: 1px solid var(--border-dim); background: var(--bg-surface-1);
}}
.aegis-badge--green  {{ color: var(--green);  border-color: var(--green);  background: {GREEN}22; }}
.aegis-badge--yellow {{ color: var(--yellow); border-color: var(--yellow); background: {YELLOW}22; animation: aegis-pulse 2.4s infinite; }}
.aegis-badge--orange {{ color: var(--orange); border-color: var(--orange); background: {ORANGE}22; animation: aegis-pulse 1.8s infinite; }}
.aegis-badge--red    {{ color: var(--red);    border-color: var(--red);    background: {RED}22;    animation: aegis-pulse 1.2s infinite; }}

.aegis-pill {{
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-family: var(--font-mono); font-size: 10px;
  letter-spacing: 0.05em; border: 1px solid var(--border-dim);
  background: var(--bg-surface-1); color: var(--text-dim);
}}
.aegis-pill--ok    {{ color: var(--green);  border-color: {GREEN}55;  }}
.aegis-pill--near  {{ color: var(--yellow); border-color: {YELLOW}88; background: {YELLOW}11; }}
.aegis-pill--breach{{ color: var(--red);    border-color: {RED}88;    background: {RED}11; }}
.aegis-pill--deploy{{ color: var(--green);  border-color: {GREEN}55; }}
.aegis-pill--hold  {{ color: var(--text-dim); }}
.aegis-pill--avoid {{ color: var(--red);    border-color: {RED}55; }}
.aegis-pill--watch {{ color: var(--gold);   border-color: {GOLD}55; }}

/* Stop audit table */
.aegis-table {{
  width: 100%; border-collapse: collapse;
  font-family: var(--font-mono); font-size: 11px;
}}
.aegis-table th {{
  text-align: left; font-weight: 500; color: var(--text-dim);
  padding: 6px 8px; border-bottom: 1px solid var(--border-dim);
  text-transform: uppercase; letter-spacing: 0.08em; font-size: 9px;
}}
.aegis-table td {{
  padding: 6px 8px; border-bottom: 1px solid {BORDER_DIM}55;
  color: var(--text-primary); white-space: nowrap;
}}
.aegis-table tr.row-near td   {{ background: {YELLOW}0d; }}
.aegis-table tr.row-breach td {{ background: {RED}10; color: var(--red); }}
.aegis-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

/* Pulse animation for warning regimes */
@keyframes aegis-pulse {{
  0%, 100% {{ opacity: 1; }}
  50%      {{ opacity: 0.55; }}
}}

/* Mobile (spec §14.24, 390px iPhone 14 baseline) */
@media (max-width: 480px) {{
  .aegis-table {{ font-size: 10.5px; }}
  .aegis-table th, .aegis-table td {{ padding: 5px 6px; }}
  .aegis-kpi-big {{ font-size: 18px; }}
  .aegis-stack {{ flex-direction: column !important; }}
  .aegis-hide-mobile {{ display: none !important; }}
}}

/* Footer link bar */
.aegis-footer {{
  margin-top: 24px; padding: 12px 16px;
  background: var(--bg-surface-1); border-top: 1px solid var(--border-dim);
  color: var(--text-dim); font-size: 11px;
  display: flex; gap: 14px; flex-wrap: wrap; justify-content: space-between;
}}
.aegis-footer a {{ color: var(--gold); text-decoration: none; }}
.aegis-footer a:hover {{ text-decoration: underline; }}
"""


def regime_badge_class(regime: str) -> str:
    """Return the Tailwind/custom class for the given regime tier."""
    return f"aegis-badge aegis-badge--{regime.lower()}"


def status_pill_class(status: str) -> str:
    """Return the pill class for OK / NEAR / BREACH / DEPLOY / HOLD / AVOID / WATCH."""
    return f"aegis-pill aegis-pill--{status.lower()}"
