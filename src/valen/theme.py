"""VALEN visual rendering — dark card panels, colour-coded pills and tables,
matching the VIV System webapp's own Situational Awareness card (the
reference the PM asked this to match, 2026-09-27) rather than plain
Streamlit widgets.

Same blindness rule as card.py: no pandas, no file access, no engine
imports — every function here is a pure string-building function of the
dicts card.py already extracts from the artifact. Streamlit pages inject
`CSS` once and then call these functions inside `st.markdown(html,
unsafe_allow_html=True)`.

Deliberately a single, permanently dark theme (no light-mode variant) —
the VIV webapp itself has no light mode; this is a considered match, not
an oversight.
"""

from __future__ import annotations

import html as _html

# ---------------------------------------------------------------------------
# Design tokens — one place, so the palette can be tuned without hunting
# through every f-string below.
# ---------------------------------------------------------------------------
_BG = "#0d0d11"
_CARD_BG = "#15151b"
_TILE_BG = "#1a1a21"
_BORDER = "#282830"
_BORDER_SOFT = "#1e1e25"
_TEXT = "#e9e9ec"
_TEXT_MUTED = "#8b8b95"
_GOLD = "#d9a441"
_GREEN = "#4ade80"
_RED = "#f87171"
_GREY = "#6b6b76"

_STANCE_STYLE = {
    "RISK_ON": ("RISK ON", _GREEN, "rgba(74,222,128,0.14)", "rgba(74,222,128,0.35)"),
    "NEUTRAL": ("NEUTRAL", _GOLD, "rgba(217,164,65,0.14)", "rgba(217,164,65,0.35)"),
    "RISK_OFF": ("RISK OFF", _RED, "rgba(248,113,113,0.14)", "rgba(248,113,113,0.35)"),
}
_STATE_STYLE = {
    "LEADING": (_GREEN, "LEADING"),
    "OFF_THE_FLOOR": (_GOLD, "OFF THE FLOOR"),
    "NEITHER": (_GREY, "—"),
}

CSS = f"""
<style>
.valen-root {{ color: {_TEXT}; }}
.valen-card {{
  background: {_CARD_BG}; border: 1px solid {_BORDER}; border-radius: 10px;
  padding: 18px 22px; margin-bottom: 14px;
}}
.valen-header {{ display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; }}
.valen-title {{ font-size: 13px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: {_TEXT_MUTED}; }}
.valen-pill {{ display: inline-block; padding: 4px 14px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  white-space: nowrap; }}
.valen-headline {{ border-left: 3px solid {_GOLD}; background: rgba(217,164,65,0.06);
  padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 14px; line-height: 1.55;
  color: {_TEXT}; margin-bottom: 2px; }}
.valen-sowhat {{ font-size: 12.5px; color: {_TEXT_MUTED}; margin: 6px 2px 0 2px; }}
.valen-grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.valen-col-label {{ font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: {_GOLD}; margin-bottom: 8px; padding-bottom: 6px;
  border-bottom: 1px solid {_BORDER}; }}
.valen-row {{ display: flex; justify-content: space-between; align-items: baseline;
  padding: 5px 0; font-size: 13px; border-bottom: 1px solid {_BORDER_SOFT}; gap: 10px; }}
.valen-row:last-child {{ border-bottom: none; }}
.valen-row-label {{ color: {_TEXT_MUTED}; }}
.valen-row-value {{ font-variant-numeric: tabular-nums; text-align: right;
  white-space: nowrap; }}
.valen-ok {{ color: {_GREEN}; }}
.valen-fail {{ color: {_RED}; }}
.valen-muted {{ color: {_GREY}; }}
.valen-stat {{ background: {_TILE_BG}; border: 1px solid {_BORDER}; border-radius: 8px;
  padding: 9px 12px; margin-bottom: 8px; }}
.valen-stat:last-child {{ margin-bottom: 0; }}
.valen-stat-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
  color: {_TEXT_MUTED}; margin-bottom: 3px; }}
.valen-stat-value {{ font-size: 19px; font-weight: 700; color: {_TEXT};
  font-variant-numeric: tabular-nums; }}
.valen-stat-sub {{ font-size: 11px; color: {_GOLD}; margin-left: 6px; }}
.valen-stat-unavail {{ font-size: 12px; color: {_GREY}; font-style: italic; }}
.valen-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.valen-table th {{ text-align: right; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.05em; color: {_GOLD}; padding: 6px 8px; border-bottom: 1px solid {_BORDER}; }}
.valen-table th:first-child, .valen-table td:first-child {{ text-align: left; }}
.valen-table td {{ padding: 5px 8px; border-bottom: 1px solid {_BORDER_SOFT}; color: {_TEXT};
  text-align: right; font-variant-numeric: tabular-nums; }}
.valen-table tr:hover td {{ background: rgba(255,255,255,0.02); }}
.valen-rank {{ color: {_GREY}; width: 22px; }}
.valen-name {{ color: {_TEXT}; text-align: left !important; }}
.valen-pos {{ color: {_GREEN}; }}
.valen-neg {{ color: {_RED}; }}
.valen-bullet-list {{ margin: 0; padding-left: 0; list-style: none; }}
.valen-bullet-list li {{ font-size: 13px; line-height: 1.5; color: {_TEXT};
  padding: 5px 0 5px 14px; position: relative; }}
.valen-bullet-list li::before {{ content: "—"; position: absolute; left: 0; color: {_GOLD}; }}
.valen-caption {{ font-size: 12px; color: {_TEXT_MUTED}; margin-top: 6px; }}
.valen-explainer {{ font-size: 10.5px; color: {_GREY}; line-height: 1.4; margin-top: 2px; }}

/* ---- cockpit instruments: gauges, LEDs, the stance dial ------------- */
.valen-dial-wrap {{ display: flex; flex-direction: column; align-items: center;
  padding: 4px 0 10px 0; }}
.valen-dial-word {{ font-size: 22px; font-weight: 800; letter-spacing: 0.03em;
  margin-top: -34px; }}
.valen-dial-caption {{ font-size: 11px; color: {_TEXT_MUTED}; margin-top: 2px;
  text-transform: uppercase; letter-spacing: 0.05em; }}
.valen-dial-history {{ font-size: 10.5px; color: {_GREY}; margin-top: 6px;
  text-align: center; }}

.valen-led-item {{ padding: 6px 0; border-bottom: 1px solid {_BORDER_SOFT}; }}
.valen-led-item:last-child {{ border-bottom: none; }}
.valen-led-row {{ display: flex; justify-content: space-between; align-items: center;
  gap: 10px; }}
.valen-led-label {{ display: flex; align-items: center; gap: 8px; color: {_TEXT_MUTED};
  font-size: 12.5px; }}
.valen-led-dot {{ width: 9px; height: 9px; border-radius: 50%; flex: none;
  box-shadow: 0 0 6px currentColor; }}
.valen-led-dot.valen-ok {{ background: {_GREEN}; color: {_GREEN}; }}
.valen-led-dot.valen-fail {{ background: {_RED}; color: {_RED}; }}
.valen-led-dot.valen-muted {{ background: {_GREY}; color: transparent; box-shadow: none; }}
.valen-led-value {{ font-size: 12.5px; font-variant-numeric: tabular-nums;
  color: {_TEXT}; white-space: nowrap; }}

.valen-gauge {{ padding: 10px 0; }}
.valen-gauge:not(:last-child) {{ border-bottom: 1px solid {_BORDER_SOFT}; }}
.valen-gauge-head {{ display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 6px; gap: 10px; }}
.valen-gauge-label {{ font-size: 12px; color: {_TEXT_MUTED}; }}
.valen-gauge-tag {{ font-size: 11px; color: {_GREY}; }}
.valen-gauge-value {{ font-size: 15px; font-weight: 700; color: {_TEXT};
  font-variant-numeric: tabular-nums; white-space: nowrap; }}
.valen-gauge-value .valen-stat-sub {{ margin-left: 4px; }}
.valen-light-housing {{ background: #0a0a0d; border: 1px solid {_BORDER}; border-radius: 6px;
  padding: 5px 4px; display: flex; flex-direction: row; gap: 4px; flex: none; }}
.valen-light-bulb {{ width: 11px; height: 11px; border-radius: 50%; background: #222228;
  opacity: 0.25; }}

/* ---- Parts 2-6: funnel, setup tags, doctrine blocks --------------- */
.valen-funnel-row {{ margin-bottom: 10px; }}
.valen-funnel-row:last-child {{ margin-bottom: 0; }}
.valen-funnel-head {{ display: flex; justify-content: space-between; font-size: 12.5px;
  margin-bottom: 4px; }}
.valen-funnel-label {{ color: {_TEXT_MUTED}; }}
.valen-funnel-count {{ color: {_TEXT}; font-weight: 700; font-variant-numeric: tabular-nums; }}
.valen-funnel-track {{ height: 10px; background: {_TILE_BG}; border-radius: 5px;
  overflow: hidden; }}
.valen-funnel-fill {{ height: 100%; background: {_GOLD}; border-radius: 5px; }}
.valen-tag {{ display: inline-block; font-size: 10px; font-weight: 600;
  letter-spacing: 0.02em; padding: 2px 8px; border-radius: 5px; margin: 2px 4px 2px 0;
  background: {_TILE_BG}; border: 1px solid {_BORDER}; color: {_GOLD}; white-space: nowrap; }}
.valen-flag-pill {{ display: inline-block; font-size: 10px; padding: 2px 8px;
  border-radius: 999px; margin: 2px 4px 2px 0; background: rgba(248,113,113,0.12);
  border: 1px solid rgba(248,113,113,0.35); color: {_RED}; white-space: nowrap; }}
.valen-doctrine {{ border-left: 3px solid {_BORDER}; padding: 6px 14px; margin-bottom: 12px;
  color: {_TEXT_MUTED}; font-size: 12.5px; line-height: 1.6; }}
.valen-doctrine:last-child {{ margin-bottom: 0; }}
.valen-doctrine b {{ color: {_TEXT}; }}
.valen-empty {{ font-size: 12.5px; color: {_GREY}; font-style: italic; padding: 4px 0; }}

/* ---- GEX Traffic Light ---------------------------------------------- */
.valen-tlight-wrap {{ display: flex; align-items: center; gap: 16px; padding: 6px 0; }}
.valen-tlight-housing {{ background: #0a0a0d; border: 1px solid {_BORDER}; border-radius: 8px;
  padding: 8px 6px; display: flex; flex-direction: column; gap: 6px; flex: none; }}
.valen-tlight-bulb {{ width: 20px; height: 20px; border-radius: 50%; background: #222228;
  opacity: 0.25; }}
.valen-tlight-bulb.lit-red {{ background: {_RED}; opacity: 1; box-shadow: 0 0 10px {_RED}; }}
.valen-tlight-bulb.lit-amber {{ background: {_GOLD}; opacity: 1; box-shadow: 0 0 10px {_GOLD}; }}
.valen-tlight-bulb.lit-green {{ background: {_GREEN}; opacity: 1; box-shadow: 0 0 10px {_GREEN}; }}
.valen-tlight-body {{ flex: 1; min-width: 0; }}
.valen-tlight-headline {{ font-size: 15px; font-weight: 700; margin-bottom: 3px; }}
.valen-tlight-commentary {{ font-size: 13px; color: {_TEXT}; line-height: 1.5; }}
.valen-tlight-levels {{ font-size: 11.5px; color: {_TEXT_MUTED}; margin-top: 5px;
  font-variant-numeric: tabular-nums; }}
</style>
"""


def _esc(v) -> str:
    return _html.escape(str(v))


def _fmt(v, suffix: str = "", nd: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}{suffix}"
    return _esc(v)


def _pct_class(v) -> str:
    if v is None:
        return ""
    return "valen-pos" if v > 0 else ("valen-neg" if v < 0 else "")


# ---------------------------------------------------------------------------
# Gauge band definitions — the handbook's own frozen thresholds
# (src/valen/spec.py), never invented ones. Each entry: (lo, hi, bands,
# tick_labels) where bands is [(band_lo, band_hi, color), ...] covering
# [lo, hi] and tick_labels are the values printed under the track.
# ---------------------------------------------------------------------------
_ATR_LO, _ATR_HI = 0.0, 8.0
_ATR_BANDS = [(0.0, 6.0, _GREEN), (6.0, 8.0, _RED)]
_ATR_TICKS = [0.0, 6.0, 8.0]

_VIX_LO, _VIX_HI = 0.5, 1.3
_VIX_BANDS = [(0.5, 0.82, _GREEN), (0.82, 1.00, _GOLD), (1.00, 1.3, _RED)]
_VIX_TICKS = [0.5, 0.82, 1.0, 1.3]

_PCT100_LO, _PCT100_HI = 0.0, 100.0
_PCT100_BANDS = [(0.0, 20.0, "#5aa9e6"), (20.0, 80.0, _GREY), (80.0, 100.0, "#e6a15a")]
_PCT100_TICKS = [0.0, 20.0, 80.0, 100.0]

_RATIO_LO, _RATIO_HI = 0.0, 3.0
# spec.MOVER_RATIO_SELLERS_BELOW = 0.50 / MOVER_RATIO_BUYERS_ABOVE = 2.00:
# sellers hold control under 0.50, buyers over 2.00, and the band between
# is BALANCED -- neither side. It was painted green and captioned "Buyers
# have control" (PM caught 0.76 reading green, 2026-10-05); the checklist's
# 1.00 pass line is a different handbook row, not this instrument's edge.
_RATIO_BANDS = [(0.0, 0.5, _RED), (0.5, 2.0, _GREY), (2.0, 3.0, _GREEN)]
_RATIO_TICKS = [0.0, 0.5, 2.0, 3.0]

# Crown-sourced gauges (macro cockpit, 2026-10-02) — crown/spec.py's own
# frozen CTA_FLIP_RISK_LO/HI (0.20/0.40) breakpoints, transcribed as the
# 0-100 scale the gauge primitive already renders in. Breadth range and
# dispersion reuse pct_0_100's own 20/80 bands under their own kind names
# (never literally "pct_0_100") so each can carry its OWN explainer text —
# two gauges sharing a `kind` would also share one explainer, which is
# exactly the trap _LED_EXPLAINER's by-label keying exists to avoid.
_CTA_LO, _CTA_HI = 0.0, 100.0
_CTA_BANDS = [(0.0, 20.0, _GREEN), (20.0, 40.0, _GREY), (40.0, 100.0, _RED)]
_CTA_TICKS = [0.0, 20.0, 40.0, 100.0]

_GAUGE_KIND = {
    "atr_multiple": (_ATR_LO, _ATR_HI, _ATR_BANDS, _ATR_TICKS, ""),
    "vix_vix3m": (_VIX_LO, _VIX_HI, _VIX_BANDS, _VIX_TICKS, ""),
    "pct_0_100": (_PCT100_LO, _PCT100_HI, _PCT100_BANDS, _PCT100_TICKS, "%"),
    "mover_ratio": (_RATIO_LO, _RATIO_HI, _RATIO_BANDS, _RATIO_TICKS, ""),
    "breadth_range_pct": (_PCT100_LO, _PCT100_HI, _PCT100_BANDS, _PCT100_TICKS, "%"),
    "dispersion_pct": (_PCT100_LO, _PCT100_HI, _PCT100_BANDS, _PCT100_TICKS, "%"),
    "cta_crowding_pct": (_CTA_LO, _CTA_HI, _CTA_BANDS, _CTA_TICKS, "%"),
}

# One-liners answering a standing PM question (2026-10-01): what does this
# instrument actually measure, and what does the number mean? Gauges are
# keyed by `kind` (the same reading applies at every window a kind is used
# at, e.g. the 5-day and 10-day mover ratios); LED checklist rows are keyed
# by their exact label since two rows can share a `kind` (e.g. "bool") while
# measuring completely different things.
_GAUGE_EXPLAINER = {
    "atr_multiple": ("How many 14-day ATRs price sits above its own 50-day "
                     "average — a stretch gauge. 6+ is historically "
                     "overextended; a pause or pullback gets more likely."),
    "vix_vix3m": ("Spot VIX ÷ the 3-month VIX. Below ~0.82 = calm; above "
                 "1.00 means near-term fear is pricier than long-term "
                 "(backwardation) — a stress signal, not a trade trigger."),
    "pct_0_100": ("% of the wide ($2B+) market trading above its own 40-day "
                 "average. Under 20% = washed out/oversold; over 80% = "
                 "euphoric/overbought."),
    "mover_ratio": ("4%+ up-days ÷ 4%+ down-days over the window. Above "
                   "2.00 = buyers have had control; below 0.50 = sellers have; "
                   "between = balanced, neither side in charge. (The checklist "
                   "1.00 pass line is a separate, looser test.)"),
    "breadth_range_pct": ("Where the average stock (RSP/SPY) sits in its own "
                         "12-month range — Crown's heartbeat read, before any "
                         "individual stock. Near 0% = bottom of the range "
                         "(often where a narrowing phase is exhausted); near "
                         "100% = top (often late, not early)."),
    "dispersion_pct": ("How much more individual stocks are moving than the "
                      "index, as a percentile of its own history (Crown). "
                      "Over 80% = the index is hiding what single names are "
                      "doing; under 20% = stocks are moving together and "
                      "selection stops paying."),
    "cta_crowding_pct": ("Share of the 18 markets Crown tracks where trend-"
                        "following funds are already at a crowded extreme. "
                        "Over 40% = a lot of money leaning the same way — "
                        "fragile, not confident; under 20% = a clean trend."),
}

# One-line read for whichever of `kind`'s own frozen bands (above) the
# current value falls in, keyed by that band's own colour (so a kind with
# two bands gets two lines, one with three gets three — never invented).
# PM ask (2026-10-03): "every indicator... a singular visual like a traffic
# light for one glance read" — the same bulb-housing + one-liner GEX's
# traffic light already uses (`traffic_light_html`), given to every other
# single-value instrument. Deliberately NOT forced into red/amber/green:
# pct_0_100/breadth_range_pct/dispersion_pct are "neutral vs extreme" reads
# where EITHER extreme deserves a look, not a danger/safe call, so their
# bulbs stay the handbook's own blue/grey/orange rather than a misleading
# red light on what might be a constructive oversold setup.
_GAUGE_COMMENTARY = {
    "atr_multiple": {
        _GREEN: "Normal stretch from the 50-day average.",
        _RED: "Overextended above the 50-day average — a pause or pullback is more likely.",
    },
    "vix_vix3m": {
        _GREEN: "Calm — near-term fear priced below long-term.",
        _GOLD: "Uncertainty building — term structure flattening.",
        _RED: "Stressed — near-term fear pricier than long-term (backwardation).",
    },
    "pct_0_100": {
        "#5aa9e6": "Oversold — washed out, often near a bottom.",
        _GREY: "Neutral — nothing extreme.",
        "#e6a15a": "Overbought — euphoric, often late rather than early.",
    },
    "mover_ratio": {
        _RED: "Sellers have control.",
        _GREY: "Balanced — neither buyers nor sellers in control.",
        _GREEN: "Buyers have control.",
    },
    "breadth_range_pct": {
        "#5aa9e6": "Near the bottom of its 12-month range.",
        _GREY: "Mid-range — nothing extreme.",
        "#e6a15a": "Near the top of its range — often late, not early.",
    },
    "dispersion_pct": {
        "#5aa9e6": "Stocks moving together — selection isn't paying right now.",
        _GREY: "Normal dispersion.",
        "#e6a15a": "Stocks diverging sharply — the index is hiding real moves underneath.",
    },
    "cta_crowding_pct": {
        _GREEN: "A clean trend — positioning isn't crowded.",
        _GREY: "Some crowding building.",
        _RED: "Crowded — a lot of trend-following money leaning the same way, fragile.",
    },
}

_LED_EXPLAINER = {
    "Today's count green": ("More $2B+ stocks closed up 4%+ today than closed "
                            "down 4%+ — one session only, not a trend."),
    "5-day count (1.00+ to pass)": ("The same 4%+ up/down ratio as the gauge "
                                    "below, over the last 5 sessions; 1.00 or "
                                    "higher passes this line."),
    "Monthly big risers (25%+ up-count)": ("How many $2B+ stocks jumped 25%+ "
                                           "over the last 21 sessions — real "
                                           "momentum breadth, not one-day noise."),
    "Net High/Net Low (8d vs 20d)": ("New 52-week highs minus new lows, "
                                     "smoothed two ways; green = the faster "
                                     "(8-day) average is above the slower "
                                     "(20-day) one — breakouts are being "
                                     "rewarded, not sold."),
}

_TREND_EXPLAINER = (
    "● = price is above both its 10- and 20-period average (day for "
    "Daily, week for Weekly) with the fast above the slow — a confirmed "
    "trend. Rising 5d adds: also above its own 5-day average AND that "
    "average is climbing — the earliest read on a fresh turn.")


def _bulb_gauge_html(label: str, value, kind: str, flag=None, tag: str | None = None) -> str:
    """One cockpit instrument as a glance-read light: a small bulb housing
    (one bulb per distinct colour `kind`'s own frozen bands define, lit for
    whichever band `value` falls in) plus a one-line read of what that band
    means — the exact visual language the GEX traffic light already
    established (`traffic_light_html`), given to every other single-value
    instrument on the page (PM ask, 2026-10-03: "every indicator... a
    singular visual like a traffic light for one glance read" — this
    replaced the earlier banded-track-with-pointer gauge entirely, not just
    alongside it). `kind` looks up the handbook's own frozen bands; an
    unrecognised kind falls back to a plain stat line rather than guessing
    a scale. Carries the one-line explainer (what this measures) under
    every instrument too — a standing PM ask (2026-10-01) answered once per
    `kind` rather than making a reader infer it from the label alone.

    `tag` (optional) is a small muted word next to the label for a reading
    whose CATEGORY varies run to run (e.g. CTA's "mixed"/"risk_on" bias,
    breadth's "narrowing"/"widening" regime) — the label itself stays
    stable so `kind`-keyed explainers above still apply."""
    tag_html = f' <span class="valen-gauge-tag">({_esc(tag)})</span>' if tag else ""
    explainer = _GAUGE_EXPLAINER.get(kind)
    explainer_html = f'<div class="valen-explainer">{_esc(explainer)}</div>' if explainer else ""
    if value is None:
        return (f'<div class="valen-gauge"><div class="valen-gauge-head">'
               f'<span class="valen-gauge-label">{_esc(label)}{tag_html}</span>'
               f'<span class="valen-stat-unavail">not shown</span></div>'
               f'{explainer_html}</div>')
    spec = _GAUGE_KIND.get(kind)
    flag_html = ' <span class="valen-stat-sub">⚠</span>' if flag else ""
    if spec is None:
        return (f'<div class="valen-gauge"><div class="valen-gauge-head">'
               f'<span class="valen-gauge-label">{_esc(label)}{tag_html}</span>'
               f'<span class="valen-gauge-value">{_fmt(value)}{flag_html}</span></div>'
               f'{explainer_html}</div>')
    _lo, _hi, bands, _ticks, suffix = spec

    # One bulb per DISTINCT band colour, in the order the bands are defined
    # — a 2-band kind (atr_multiple) gets 2 bulbs, a 3-band kind gets 3,
    # never a fixed 3-slot red/amber/green that would misrepresent a kind
    # whose bands aren't that shape.
    colors_in_order: list[str] = []
    for _b_lo, _b_hi, c in bands:
        if c not in colors_in_order:
            colors_in_order.append(c)
    active_color = colors_in_order[0] if colors_in_order else _GREY
    for b_lo, b_hi, c in bands:
        if b_lo <= float(value) <= b_hi:
            active_color = c
            break
    bulbs = "".join(
        f'<div class="valen-light-bulb" style="background:{c};'
        + ('opacity:1;box-shadow:0 0 6px ' + c if c == active_color else 'opacity:0.25')
        + '"></div>'
        for c in colors_in_order
    )
    commentary = _GAUGE_COMMENTARY.get(kind, {}).get(active_color)
    commentary_html = (f'<div class="valen-tlight-commentary" style="margin-top:4px">'
                       f'{_esc(commentary)}</div>' if commentary else "")

    return (
        f'<div class="valen-gauge"><div class="valen-gauge-head">'
        f'<span class="valen-gauge-label">{_esc(label)}{tag_html}</span>'
        f'<span class="valen-gauge-value">{_fmt(value)}{suffix}{flag_html}</span></div>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-top:4px">'
        f'<div class="valen-light-housing">{bulbs}</div></div>'
        f'{commentary_html}{explainer_html}</div>'
    )


def _led_row_html(label: str, status: str, value, flag=None,
                  display: str | None = None) -> str:
    """One checklist line: a coloured LED dot (pass/fail/not-shown) plus the
    reading it's judging — the pass/fail-lights read of the handbook's own
    six-row "market checklist", replacing a flat text row. Carries a
    one-line explainer (what this measures, what the number means) keyed by
    the row's own label, since two rows can share a `kind` ("bool") while
    reading completely different things."""
    explainer = _LED_EXPLAINER.get(label)
    explainer_html = f'<div class="valen-explainer">{_esc(explainer)}</div>' if explainer else ""
    if status != "OK":
        return (f'<div class="valen-led-item"><div class="valen-led-row">'
               f'<span class="valen-led-label">'
               f'<span class="valen-led-dot valen-muted"></span>{_esc(label)}</span>'
               f'<span class="valen-led-value" style="color:{_GREY}">not shown</span></div>'
               f'{explainer_html}</div>')
    ok = bool(flag) if flag is not None else bool(value)
    dot_cls = "valen-ok" if ok else "valen-fail"
    shown = display if display is not None else _fmt(value)
    return (f'<div class="valen-led-item"><div class="valen-led-row">'
           f'<span class="valen-led-label">'
           f'<span class="valen-led-dot {dot_cls}"></span>{_esc(label)}</span>'
           f'<span class="valen-led-value">{shown}</span></div>{explainer_html}</div>')


_DIAL_ZONES = [
    ("RISK_OFF", "M 20 100 A 80 80 0 0 1 60 30.72", _RED, 150),
    ("NEUTRAL", "M 60 30.72 A 80 80 0 0 1 140 30.72", _GOLD, 90),
    ("RISK_ON", "M 140 30.72 A 80 80 0 0 1 180 100", _GREEN, 30),
]


def _dial_history_markers_svg(history_dots: list[dict]) -> str:
    """Slim radial tick marks crossing the dial's coloured band, showing
    where the stance sat 1 and 5 sessions ago (card.dial_history_dots()) —
    a PM ask (2026-10-02) to compare today's needle against recent history
    without leaving the gauge. Two earlier passes (a plain dot, then a
    filled circle with a digit crammed inside) both read as clutter on a
    small instrument; a thin white tick — the same device a real
    speedometer uses for a memory point — plus a tiny label just outside
    the band is the sleeker version PM feedback asked for. Ticks cross the
    band at radius 72-90 (the needle only runs center->62, well short of
    it); two ticks landing in the SAME zone are spread a few degrees apart
    rather than fully overlapping."""
    if not history_dots:
        return ""
    import math
    zone_by_key = {z[0]: z for z in _DIAL_ZONES}
    by_zone: dict[str, list[dict]] = {}
    for d in history_dots:
        by_zone.setdefault(d["stance"], []).append(d)
    parts = []
    for zone_key, dots in by_zone.items():
        zinfo = zone_by_key.get(zone_key)
        if not zinfo:
            continue
        _, _, _color, base_angle = zinfo
        spread = 11.0
        start = base_angle - spread * (len(dots) - 1) / 2
        for i, d in enumerate(dots):
            angle = start + i * spread
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            x1, y1 = 100 + 72 * cos_a, 100 - 72 * sin_a
            x2, y2 = 100 + 90 * cos_a, 100 - 90 * sin_a
            lx, ly = 100 + 98 * cos_a, 100 - 98 * sin_a
            tag = d.get("tag") or (d.get("label") or "?")[:2]
            title = f'{_esc(d["label"])}: {_esc(d["stance"].replace("_", " "))}'
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#fff" stroke-width="2" stroke-linecap="round" '
                f'opacity="0.9"><title>{title}</title></line>'
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'dominant-baseline="central" font-size="7.5" font-weight="700" '
                f'letter-spacing="0.03em" fill="{_TEXT_MUTED}">{_esc(tag)}'
                f'<title>{title}</title></text>')
    return "".join(parts)


def _dial_history_caption_html(history_dots: list[dict]) -> str:
    """Plain-text legend under the dial, same facts as the hover titles on
    the markers above — a static render (export, screenshot) never shows a
    hover tooltip, so the comparison must also be readable without one."""
    if not history_dots:
        return ""
    bits = " &nbsp; ".join(
        f"○ {_esc(d['label'])}: {_esc(d['stance'].replace('_', ' '))}"
        for d in history_dots)
    return f'<div class="valen-dial-history">{bits}</div>'


def stance_gauge_html(banner: dict, history_dots: list[dict] | None = None) -> str:
    """The cockpit centrepiece: a three-zone semicircular dial (RISK OFF /
    NEUTRAL / RISK ON) with a needle over the current zone. The stance is
    categorical by the handbook's own design (piece 01: "it flips when a
    rule is met", never a continuous score), so the needle points at the
    current zone's centre rather than implying false precision.

    `history_dots` (optional, card.dial_history_dots()) adds slim radial
    tick marks for where the stance sat 1 and 5 sessions ago, so today's
    needle reads against recent history at a glance instead of a separate
    table."""
    stance_key = (banner.get("word") or "").replace(" ", "_")
    zones = _DIAL_ZONES
    known = stance_key in {z[0] for z in zones}
    arcs = "".join(
        f'<path d="{path}" fill="none" stroke="{color if known else _GREY}" '
        f'stroke-width="16" stroke-opacity="{1.0 if stance_key == key else 0.28}"/>'
        for key, path, color, _angle in zones
    )
    if known:
        import math
        _, _, needle_color, angle = next(z for z in zones if z[0] == stance_key)
        rad = math.radians(angle)
        nx = 100 + 62 * math.cos(rad)
        ny = 100 - 62 * math.sin(rad)
        needle = (f'<line x1="100" y1="100" x2="{nx:.1f}" y2="{ny:.1f}" '
                 f'stroke="{needle_color}" stroke-width="3" stroke-linecap="round"/>'
                 f'<circle cx="100" cy="100" r="6" fill="{needle_color}"/>')
        word_color = needle_color
    else:
        needle = f'<circle cx="100" cy="100" r="6" fill="{_GREY}"/>'
        word_color = _GREY
    markers = _dial_history_markers_svg(history_dots or [])
    label = banner.get("word") or "NOT SHOWN"
    svg = (f'<svg viewBox="0 0 200 108" width="220" height="119">{arcs}{markers}{needle}</svg>')
    return (f'<div class="valen-dial-wrap">{svg}'
           f'<div class="valen-dial-word" style="color:{word_color}">{_esc(label)}</div>'
           f'<div class="valen-dial-caption">Stance</div>'
           f'{_dial_history_caption_html(history_dots or [])}</div>')


def part_header_html(number: str, title: str, subtitle: str) -> str:
    """The handbook's own "Part N of 6" section banner — used once per Part
    on the page to keep the UX sequenced the way the handbook itself
    sequences it (Weather -> Neighbourhood -> House -> When to walk in ->
    After you move in -> Keeping the roof on)."""
    return (
        '<div class="valen-root"><div class="valen-card" style="padding-bottom:10px">'
        f'<div class="valen-header"><span class="valen-title">Part {_esc(number)} of 6 — '
        f'{_esc(title)}</span></div>'
        f'<div class="valen-caption" style="margin:0">{_esc(subtitle)}</div>'
        '</div></div>'
    )


def traffic_light_html(gex: dict) -> str:
    """The GEX Traffic Light — a physical-looking three-bulb housing (red/
    amber/green, only the current one lit) plus the one-line commentary.
    Never renders a sizing number — that's quoted doctrine in the page
    itself, not a field this reads (AQE makes no decisions, no sizing).

    "Can't assign red/amber/green" and "can't say anything" are different
    facts (a real SPY session, 2026-10-01: regime/walls computed fine from
    real options data, no flip found in the strike band so no light) — the
    UNAVAILABLE branch still renders `dealer_read` (gex.py's plain-English
    support/resistance/regime sentence) and whatever of price/walls came
    through, all bulbs unlit, rather than reducing a partial real read to
    just the bare reason string."""
    if not gex or gex.get("status") != "OK":
        reason = (gex or {}).get("reason") or "not computed"
        dealer_read = (gex or {}).get("dealer_read")
        read_html = (f'<div class="valen-tlight-commentary">{_esc(dealer_read)}</div>'
                    if dealer_read else "")
        bits = []
        if gex and gex.get("price") is not None:
            bits.append(f'{_esc(gex.get("ticker"))} {_fmt(gex.get("price"))}')
        if gex and gex.get("put_wall") is not None:
            bits.append(f'put wall {_fmt(gex.get("put_wall"))}')
        if gex and gex.get("call_wall") is not None:
            bits.append(f'call wall {_fmt(gex.get("call_wall"))}')
        levels_html = (f'<div class="valen-tlight-levels">{" · ".join(bits)}</div>'
                      if bits else "")
        return (f'<div class="valen-tlight-wrap">'
               f'<div class="valen-tlight-housing">'
               f'<div class="valen-tlight-bulb"></div>'
               f'<div class="valen-tlight-bulb"></div>'
               f'<div class="valen-tlight-bulb"></div></div>'
               f'<div class="valen-tlight-body"><div class="valen-tlight-headline" '
               f'style="color:{_GREY}">GEX not shown</div>'
               f'<div class="valen-tlight-commentary">{_esc(reason)}</div>'
               f'{read_html}{levels_html}</div></div>')

    light = gex.get("light")
    lit_cls = {"RED": "lit-red", "AMBER": "lit-amber", "GREEN": "lit-green"}.get(light, "")
    color = {"RED": _RED, "AMBER": _GOLD, "GREEN": _GREEN}.get(light, _GREY)
    bulbs = "".join(
        f'<div class="valen-tlight-bulb {lit_cls if key == light else ""}"></div>'
        for key in ("RED", "AMBER", "GREEN")
    )
    levels = (f'{_esc(gex.get("ticker"))} {_fmt(gex.get("price"))} · flip {_fmt(gex.get("flip"))}'
             + (f' · call wall {_fmt(gex.get("call_wall"))}' if gex.get("call_wall") is not None else '')
             + (f' · put wall {_fmt(gex.get("put_wall"))}' if gex.get("put_wall") is not None else ''))
    dealer_read = gex.get("dealer_read")
    read_html = (f'<div class="valen-tlight-commentary">{_esc(dealer_read)}</div>'
                if dealer_read else "")
    return (f'<div class="valen-tlight-wrap">'
           f'<div class="valen-tlight-housing">{bulbs}</div>'
           f'<div class="valen-tlight-body">'
           f'<div class="valen-tlight-headline" style="color:{color}">{_esc(light)}</div>'
           f'<div class="valen-tlight-commentary">{_esc(gex.get("commentary"))}</div>'
           f'{read_html}'
           f'<div class="valen-tlight-levels">{levels}</div></div></div>')


def stance_header_html(banner: dict) -> str:
    """`banner` = card.stance_banner(valen)'s return shape."""
    status = banner.get("status", "UNAVAILABLE")
    stance_key = (banner.get("word") or "").replace(" ", "_")
    label, color, bg, border = _STANCE_STYLE.get(
        stance_key, ("NOT SHOWN", _GREY, "rgba(107,107,118,0.14)", "rgba(107,107,118,0.3)"))
    reason = banner.get("reason")
    pill = (f'<span class="valen-pill" style="color:{color};background:{bg};'
           f'border:1px solid {border}">{_esc(label)}</span>')
    reason_html = (f'<div class="valen-caption">{_esc(reason)}</div>' if reason else "")
    return (f'<div class="valen-header"><span class="valen-title">'
           f'\U0001f9ed Situational Awareness</span>{pill}</div>{reason_html}')


def headline_banner_html(headline_text: str, so_what: str | None) -> str:
    so_what_html = f'<div class="valen-sowhat">{_esc(so_what)}</div>' if so_what else ""
    return f'<div class="valen-headline">{_esc(headline_text)}</div>{so_what_html}'


def trend_checklist_html(trend_rows_: list[dict], breadth_rows_: list[dict]) -> str:
    rows_html = []
    for r in trend_rows_:
        sym = r.get("symbol")
        if r.get("basis") == "unavailable":
            rows_html.append(
                f'<div class="valen-row"><span class="valen-row-label">{_esc(sym)}</span>'
                f'<span class="valen-row-value valen-muted">not on panel</span></div>')
            continue
        marks = []
        for label, key in (("Daily", "daily_buy_signal"), ("Weekly", "weekly_buy_signal"),
                          ("Rising 5d", "above_rising_5d")):
            v = r.get(key)
            if v is None:
                continue
            cls = "valen-ok" if v else "valen-fail"
            marks.append(f'<span class="{cls}">{"●" if v else "○"} {label}</span>')
        basis_tag = " (live)" if r.get("basis") == "live" else ""
        rows_html.append(
            f'<div class="valen-row"><span class="valen-row-label">{_esc(sym)} '
            f'{_fmt(r.get("last_price"))}{basis_tag}</span>'
            f'<span class="valen-row-value">{" &nbsp; ".join(marks)}</span></div>')
    checklist_html = "".join(
        _led_row_html(row["label"], row["status"], row.get("value"),
                     flag=row.get("flag"), display=row.get("display"))
        for row in breadth_rows_ if row.get("section") == "checklist"
    )
    return (f'<div class="valen-col-label">Trend &amp; checklist</div>'
           f'{"".join(rows_html)}'
           f'<div class="valen-explainer" style="margin-bottom:8px">{_esc(_TREND_EXPLAINER)}</div>'
           f'<div class="valen-col-label" style="margin-top:12px">Market checklist</div>'
           f'{checklist_html}')


def instruments_html(extension_rows_: list[dict], breadth_rows_: list[dict] | None = None) -> str:
    """The four-plus tracked instruments (VIX/VIX3M, SPY/QQQ ATR multiples,
    T2108, the 5-day/10-day mover ratio) as glance-read bulb lights — a
    one-line commentary replacing the earlier banded-track gauge's pointer-
    on-a-scale read. `breadth_rows_` is optional so existing callers/tests
    that only pass extension rows keep working; instrument-section breadth
    rows are appended when given."""
    rows = list(extension_rows_)
    if breadth_rows_:
        rows += [r for r in breadth_rows_ if r.get("section") == "instrument"]
    gauges = "".join(
        _bulb_gauge_html(row["label"], row.get("value"), row.get("kind"), row.get("flag"),
                         row.get("tag"))
        for row in rows
    )
    return f'<div class="valen-col-label">Instruments</div>{gauges}'


def _tag_pills_html(items: list[str], empty_word: str = "none") -> str:
    if not items:
        return f'<span class="valen-stat-unavail">{_esc(empty_word)}</span>'
    return "".join(f'<span class="valen-tag">{_esc(t)}</span>' for t in items)


def macro_cockpit_html(gauge_rows: list[dict], divergence: dict, cot: dict) -> str:
    """"Macro cockpit" — a new Part 1 sub-section (PM ask, 2026-10-02: "how
    Crown and VALEN can be combined... more cockpit illustration within
    VALEN's structure," answered "all 5," placed as "a new sub-section
    inside Part 1"). Every reading here is Crown's own, read-only, given
    VALEN's gauge/LED/tag face — the exact pattern GEX's traffic light
    already established; this module computes nothing Crown doesn't
    already compute. All five share Crown's own top-level status
    (crown_cockpit.crown_status_ok()), so a fully degraded Crown run shows
    ONE banner here, not five separate "not shown" placeholders."""
    gauges_shown = any(r.get("value") is not None for r in gauge_rows)
    if not gauges_shown and divergence.get("status") != "OK" and cot.get("status") != "OK":
        reason = divergence.get("reason") or cot.get("reason") or "not computed"
        return (
            '<div class="valen-col-label">Macro cockpit — Crown Macro</div>'
            '<div class="valen-explainer" style="margin-bottom:8px">Five Crown Macro '
            'readings given a VALEN gauge/LED/tag face — breadth range, trend-fund '
            'crowding, dispersion, divergence checks, and COT crowding. Crown '
            'computes these independently of VALEN; VALEN only visualizes them.</div>'
            f'<div class="valen-stat-unavail">Crown macro not shown — {_esc(reason)}</div>')

    gauges_html = "".join(
        _bulb_gauge_html(r["label"], r.get("value"), r.get("kind"), r.get("flag"), r.get("tag"))
        for r in gauge_rows)

    div_ok = divergence.get("status") == "OK"
    div_value = (f'{divergence.get("count")} of {divergence.get("total")}' if div_ok
                else "not shown")
    div_types = _tag_pills_html(
        [t.replace("_", " ") for t in (divergence.get("types_fired") or [])]
    ) if div_ok else ""
    div_html = (
        '<div class="valen-stat"><div class="valen-stat-label">Divergence checks lit</div>'
        f'<div class="valen-stat-value">{_esc(div_value)}</div>'
        + (f'<div style="margin-top:6px">{div_types}</div>' if div_ok else '')
        + '<div class="valen-explainer">How many of Crown’s 8 independent '
          'divergence checks (RSI, cross-asset, VIX, breadth, positioning and '
          'more) are lit right now. One alone is a straw; several agreeing is '
          'what the handbook calls a pile of them.</div></div>')

    cot_ok = cot.get("status") == "OK"
    cot_html = (
        '<div class="valen-stat"><div class="valen-stat-label">COT — crowded positioning</div>'
        + (f'<div style="margin-top:2px"><span class="valen-gauge-tag">Crowded long: </span>'
           f'{_tag_pills_html(cot.get("crowded_long") or [])}</div>'
           f'<div style="margin-top:4px"><span class="valen-gauge-tag">Crowded short: </span>'
           f'{_tag_pills_html(cot.get("crowded_short") or [])}</div>'
           if cot_ok else '<div class="valen-stat-unavail">not shown</div>')
        + '<div class="valen-explainer">Which futures markets large speculators are '
          'already crowded into, straight from cftc.gov — at least three days old '
          'by the time it lands here, so it never times anything, only shows where '
          'the crowd already is.</div></div>')

    return (
        '<div class="valen-col-label">Macro cockpit — Crown Macro</div>'
        '<div class="valen-explainer" style="margin-bottom:8px">Five Crown Macro '
        'readings given a VALEN gauge/LED/tag face — Crown computes these '
        'independently of VALEN; VALEN only visualizes them.</div>'
        f'{gauges_html}{div_html}{cot_html}')


def what_would_change_html(watch_for: list[str]) -> str:
    if not watch_for:
        return ('<div class="valen-col-label">What would change it</div>'
               '<div class="valen-stat-unavail">Not shown — depends on whole-market '
               'breadth.</div>')
    items = "".join(f"<li>{_esc(line)}</li>" for line in watch_for)
    return (f'<div class="valen-col-label">What would change it</div>'
           f'<ul class="valen-bullet-list">{items}</ul>')


def _history_arrow(now, past) -> str:
    if now is None or past is None:
        return ""
    if now > past:
        return " ↑"
    if now < past:
        return " ↓"
    return " →"


def history_html(rows: list[dict]) -> str:
    """"Is the weather turning?" — current vs 5-sessions/21-sessions-ago,
    independently recomputed from price history each time (never a stored
    snapshot — see card.history_rows()/history.py), so the turning-point
    read is available from day one with no backfill wait."""
    if not rows:
        return ""
    body = []
    for r in rows:
        label, kind = r.get("label"), r.get("kind")
        now_v, d5, d1m = r.get("now"), r.get("5d_ago"), r.get("1mo_ago")
        if kind == "word":
            now_s = _esc(str(now_v).replace("_", " ")) if now_v else "—"
            d5_s = _esc(str(d5).replace("_", " ")) if d5 else "—"
            d1m_s = _esc(str(d1m).replace("_", " ")) if d1m else "—"
            flag5 = (' <span class="valen-stat-sub">⚠</span>'
                    if d5 and now_v and d5 != now_v else "")
            flag1m = (' <span class="valen-stat-sub">⚠</span>'
                      if d1m and now_v and d1m != now_v else "")
            body.append(f'<tr><td class="valen-name">{_esc(label)}</td>'
                       f'<td>{now_s}</td><td>{d5_s}{flag5}</td><td>{d1m_s}{flag1m}</td></tr>')
        else:
            body.append(f'<tr><td class="valen-name">{_esc(label)}</td>'
                       f'<td>{_fmt(now_v)}</td>'
                       f'<td>{_fmt(d5)}{_history_arrow(now_v, d5)}</td>'
                       f'<td>{_fmt(d1m)}{_history_arrow(now_v, d1m)}</td></tr>')
    return (
        '<div class="valen-col-label">Is the weather turning?</div>'
        '<div class="valen-explainer" style="margin-bottom:8px">Each column is '
        'independently recomputed from price history, not a stored snapshot — '
        'available from day one, no backfill wait. ⚠ on Stance/Trend regime '
        'marks a point where the read differed from today’s. Arrows on numbers '
        'show direction only (↑ higher / ↓ lower than today) — AQE makes '
        'no call on which way is better. GEX has no history here: its read is a '
        'snapshot of today’s options open interest, which isn’t retained.</div>'
        '<table class="valen-table"><tr><th></th><th>Now</th><th>5d ago</th>'
        f'<th>1mo ago</th></tr>{"".join(body)}</table>')


def neighbourhood_html(lines: list[str], status: str, reason: str | None) -> str:
    if not lines:
        msg = "No group cleared a leadership read today." if status == "OK" else (
            reason or "Group read unavailable.")
        return (f'<div class="valen-col-label">The neighbourhood</div>'
               f'<div class="valen-stat-unavail">{_esc(msg)}</div>')
    items = "".join(f"<li>{_esc(line)}</li>" for line in lines)
    return (f'<div class="valen-col-label">The neighbourhood</div>'
           f'<ul class="valen-bullet-list">{items}</ul>')


_THEME_READ_STYLE = {
    "BOTH_LISTS": (_GREEN, "BOTH LISTS"),
    "WEEK_ONLY": (_GOLD, "WEEK ONLY"),
    "MONTH_ONLY": (_GOLD, "MONTH ONLY"),
    "NOT_IN_THEME": (_GREY, "—"),
}


def _theme_rank_cell(pct, rank, top_n: int) -> str:
    """Return % plus its rank on that list; a top-N rank is gold + bold so
    the eye finds the marked rows without reading a single number."""
    if pct is None:
        return '<td>—</td>'
    marked = rank is not None and rank <= top_n
    tag = (f' <span style="color:{_GOLD};font-weight:700">#{rank}</span>' if marked
           else f' <span style="color:{_TEXT_MUTED}">#{rank}</span>' if rank else '')
    return f'<td class="{_pct_class(pct)}">{_fmt(pct, "%")}{tag}</td>'


def theme_leaders_table_html(rows: list[dict], limit: int | None = None) -> str:
    """Piece 02's rule made visible: every group gets its rank on the
    1-week list and the 1-month list, the top 5 on each marked, and a
    one-word read of which list(s) it is on. In-theme groups lead the
    table. Today's since-open move is context, last column. Shows every
    group (no cap) unless `limit` is passed."""
    from . import card as _card
    from . import spec as _S
    top_n = _S.THEME_TOP_N
    ranked = _card.theme_reads(rows, top_n)
    if limit:
        ranked = ranked[:limit]
    if not ranked:
        return '<div class="valen-empty">No group read today.</div>'
    body = []
    for r in ranked:
        color, label = _THEME_READ_STYLE.get(r["theme_read"], (_GREY, "—"))
        body.append(
            f'<tr><td class="valen-name">{_esc(r.get("display_name"))}</td>'
            f'<td style="color:{color};font-weight:600;font-size:11px;'
            f'text-transform:uppercase;text-align:left" '
            f'title="{_esc(r["theme_read_text"])}">{_esc(label)}</td>'
            + _theme_rank_cell(r.get("ret_1w_pct"), r.get("rank_1w"), top_n)
            + _theme_rank_cell(r.get("ret_1m_pct"), r.get("rank_1m"), top_n)
            + f'<td class="{_pct_class(r.get("since_open_pct"))}">'
            f'{_fmt(r.get("since_open_pct"), "%")}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th>Group</th>'
        '<th style="text-align:left">In-theme?</th>'
        '<th>1 Week (rank)</th><th>1 Month (rank)</th><th>Today, from open</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table>')


def rotation_table_html(rows: list[dict], limit: int = 15) -> str:
    """Sorted by thrust, with the honesty column (% off 52-week high) and
    the LEADING / OFF_THE_FLOOR state front and centre."""
    ranked = sorted((r for r in rows if r.get("thrust") is not None),
                    key=lambda r: r["thrust"], reverse=True)[:limit]
    body = []
    for i, r in enumerate(ranked, 1):
        state = r.get("rotation_state") or "NEITHER"
        color, label = _STATE_STYLE.get(state, (_GREY, state))
        body.append(
            f'<tr><td class="valen-rank">{i}</td>'
            f'<td class="valen-name">{_esc(r.get("display_name"))}</td>'
            f'<td class="{_pct_class(r.get("thrust"))}">{_fmt(r.get("thrust"), "%")}</td>'
            f'<td class="{_pct_class(r.get("ret_1m_pct"))}">'
            f'{_fmt(r.get("ret_1m_pct"), "%")}</td>'
            f'<td>{_fmt(r.get("pct_off_52w_high"), "%")}</td>'
            f'<td style="color:{color};font-weight:600;font-size:11px;'
            f'text-transform:uppercase">{_esc(label)}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th></th><th>Group</th>'
        '<th>Thrust</th><th>1 Month</th><th>% off 52w high</th><th>State</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')


# ---------------------------------------------------------------------------
# Parts 2-6 (pieces 04-20) — 2026-09-30. Reuses the existing table/pill/LED
# vocabulary above rather than inventing a new widget per piece.
# ---------------------------------------------------------------------------

def relative_strength_table_html(rows: list[dict], limit: int = 15) -> str:
    """Piece 04 — ranked by rs_rank_pct, LEADER/IN-LINE/LAGGARD colour-coded."""
    if not rows:
        return '<div class="valen-empty">No relative-strength read today.</div>'
    lead_color = {"LEADER": _GREEN, "LAGGARD": _RED, "IN-LINE": _GREY}
    body = []
    for i, r in enumerate(rows[:limit], 1):
        color = lead_color.get(r.get("rs_leadership"), _GREY)
        body.append(
            f'<tr><td class="valen-rank">{i}</td>'
            f'<td class="valen-name">{_esc(r.get("ticker"))}</td>'
            f'<td>{_fmt(r.get("rs_rank_pct"))}</td>'
            f'<td style="color:{color};font-weight:600;font-size:11px">'
            f'{_esc(r.get("rs_leadership") or "—")}</td>'
            f'<td>{_fmt(r.get("pipe_rank"))}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th></th><th>Ticker</th>'
        '<th>RS rank</th><th>Leadership</th><th>Pipe rank</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')


def funnel_html(stages: list[dict]) -> str:
    """Piece 05 — survivors at each narrowing stage, bar width relative to
    the first (widest) stage."""
    if not stages:
        return '<div class="valen-empty">Funnel not shown.</div>'
    base = next((s["count"] for s in stages if s.get("count")), None) or 1
    rows = []
    for s in stages:
        count = s.get("count")
        if count is None:
            rows.append(
                f'<div class="valen-funnel-row"><div class="valen-funnel-head">'
                f'<span class="valen-funnel-label">{_esc(s["stage"])}</span>'
                f'<span class="valen-funnel-count" style="color:{_GREY}">'
                f'{_esc(s.get("reason", "not shown"))}</span></div></div>')
            continue
        pct = max(2.0, min(100.0, count / base * 100))
        rows.append(
            f'<div class="valen-funnel-row"><div class="valen-funnel-head">'
            f'<span class="valen-funnel-label">{_esc(s["stage"])}</span>'
            f'<span class="valen-funnel-count">{count}</span></div>'
            f'<div class="valen-funnel-track"><div class="valen-funnel-fill" '
            f'style="width:{pct:.1f}%"></div></div></div>')
    return "".join(rows)


def no_buy_html(rows: list[dict], limit: int = 12) -> str:
    """Piece 07 — candidates carrying 1+ no-buy flags, worst first."""
    if not rows:
        return '<div class="valen-empty">No candidate trips a no-buy flag today.</div>'
    body = []
    for r in rows[:limit]:
        pills = "".join(f'<span class="valen-flag-pill">{_esc(f["label"])}</span>'
                        for f in r["flags"])
        body.append(
            f'<div class="valen-row" style="align-items:flex-start">'
            f'<span class="valen-row-label" style="min-width:52px">{_esc(r["ticker"])}</span>'
            f'<span class="valen-row-value" style="text-align:left;white-space:normal">'
            f'{pills}</span></div>')
    more = len(rows) - limit
    more_html = (f'<div class="valen-caption">+{more} more candidate(s) flagged — '
                f'full list in the export.</div>' if more > 0 else "")
    return "".join(body) + more_html


def house_setups_html(rows: list[dict], limit: int | None = None) -> str:
    """Parts 08-12 — every setup tag a ticker carries, as pills. Every
    tagged name shows (no cap) unless `limit` is passed."""
    if not rows:
        return '<div class="valen-empty">No setup pattern flagged today.</div>'
    body = []
    for r in (rows[:limit] if limit else rows):
        tags = "".join(f'<span class="valen-tag" title="{_esc(t["detail"])}">'
                       f'{_esc(t["name"])}</span>' for t in r["setups"])
        body.append(
            f'<div class="valen-row" style="align-items:flex-start">'
            f'<span class="valen-row-label" style="min-width:52px">{_esc(r["ticker"])}</span>'
            f'<span class="valen-row-value" style="text-align:left;white-space:normal">'
            f'{tags}</span></div>')
    more = len(rows) - limit
    more_html = (f'<div class="valen-caption">+{more} more.</div>' if more > 0 else "")
    return "".join(body) + more_html


def entries_table_html(rows: list[dict], limit: int = 15) -> str:
    """Piece 13 — trigger, volume, stop, read in that fixed order."""
    if not rows:
        return '<div class="valen-empty">No candidate has a recognised entry trigger today.</div>'
    body = []
    for r in rows[:limit]:
        vol = r.get("volume_confirmed")
        vol_html = ('<span class="valen-ok">✓</span>' if vol is True
                   else ('<span class="valen-fail">✗</span>' if vol is False
                        else '<span class="valen-muted">—</span>'))
        valid = r.get("bracket_valid")
        stop_html = (_fmt(r.get("stop")) if valid else
                    f'<span class="valen-muted" title="{_esc(r.get("invalid_reason") or "")}">'
                    f'no valid stop</span>')
        body.append(
            f'<tr><td class="valen-name">{_esc(r["ticker"])}</td>'
            f'<td style="text-align:left">{_esc(r.get("trigger"))}</td>'
            f'<td>{vol_html}</td><td>{stop_html}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th>Ticker</th><th>Trigger</th>'
        '<th>Volume</th><th>Stop</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')


def stop_breaches_html(rows: list[dict]) -> str:
    """Piece 16 — a fact, never a decision: which held positions are
    already through their own stop."""
    breached = [r for r in rows if r.get("status") == "OK" and r.get("breached")]
    if not breached:
        return '<div class="valen-empty">No held position is through its stop.</div>'
    items = "".join(
        f'<li>{_esc(r["ticker"])} — live {_fmt(r["live_px"])} vs stop {_fmt(r["held_sl"])}</li>'
        for r in breached)
    return f'<ul class="valen-bullet-list">{items}</ul>'


def held_facts_table_html(rows: list[dict]) -> str:
    """Pieces 17-19's facts — never the trim/trail/add call itself."""
    if not rows:
        return '<div class="valen-empty">No open positions.</div>'
    body = []
    for r in rows:
        r_mult = (f'{_fmt(r["r_multiple"])}<span class="valen-stat-sub">approx</span>'
                 if r.get("r_multiple") is not None else "—")
        body.append(
            f'<tr><td class="valen-name">{_esc(r["ticker"])}</td>'
            f'<td>{_fmt(r.get("unreal_usd"), nd=0)}</td>'
            f'<td>{r_mult}</td>'
            f'<td class="{_pct_class(r.get("dist_from_stop_pct"))}">'
            f'{_fmt(r.get("dist_from_stop_pct"), "%")}</td>'
            f'<td>{_fmt(r.get("days_held"), nd=0)}</td></tr>')
    return (
        '<table class="valen-table"><thead><tr><th>Ticker</th><th>Unrealised $</th>'
        '<th>R (approx)</th><th>Dist. from stop</th><th>Days held</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>')


def streak_html(streak: dict) -> str:
    """Piece 20's context fact — never the sizing rule (that's quoted
    doctrine, see doctrine_html)."""
    if streak.get("status") != "OK":
        return (f'<div class="valen-empty">Streak not shown — '
               f'{_esc(streak.get("reason", "unavailable"))}.</div>')
    color = _RED if streak["direction"] == "LOSS" else (
        _GREEN if streak["direction"] == "WIN" else _GREY)
    return (f'<div class="valen-stat"><div class="valen-stat-label">Current streak</div>'
           f'<div class="valen-stat-value" style="color:{color}">'
           f'{streak["streak"]} {streak["direction"]}'
           f'<span class="valen-stat-sub">of last {streak["n_considered"]} closed</span>'
           f'</div></div>')


def doctrine_html(entries: list[tuple[str, str]]) -> str:
    """Pieces 14/15/20's actual sizing rule, and piece 21 — the handbook's
    own words, quoted, never computed. `entries` is a list of (heading,
    body) pairs the page supplies."""
    blocks = "".join(
        f'<div class="valen-doctrine"><b>{_esc(h)}</b> — {_esc(b)}</div>'
        for h, b in entries)
    return blocks
