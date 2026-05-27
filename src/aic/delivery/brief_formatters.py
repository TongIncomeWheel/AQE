"""Telegram (plain-text + emoji) formatters for the three daily briefs.

Spec §14.6a / §14.15 / §14.16. Each formatter takes the *same* dataclass that
the web view consumes (compose_premarket / compose_open / compose_close from
`src.aic.web.brief_data`) and turns it into the compressed mobile-friendly
text format the PM reads in Telegram.

Web view + Telegram thus stay in lock-step -- one composer, two presenters.

Spec §14.6a constraints applied here:
  - Max 40 lines per Telegram message.
  - ⚠️ for any position within 3% of SL.
  - 🔴 for SL breach.
  - Always include the link to the full web view at bottom.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.aic.protocols.protocol_a_premarket import PreMarketBrief
from src.aic.web.brief_data import MarketCloseBrief, MarketOpenBrief

SGT = ZoneInfo("Asia/Singapore")

WEB_BASE_URL = "aegis.local"   # spec §14.6a / §14.15 / §14.16 trailer

REGIME_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}


# ---------------------------------------------------------------------------
# S02 -- Pre-Market Brief
# ---------------------------------------------------------------------------

def format_premarket_telegram(brief: PreMarketBrief, max_lines: int = 40) -> str:
    lines: list[str] = []
    ts = _parse_ts(brief.timestamp_sgt)
    lines.append(f"{REGIME_EMOJI.get(brief.regime,'·')} AEGIS PRE-MARKET")
    lines.append(f"{ts.strftime('%a %d %b · %H:%M SGT')}")
    lines.append("")
    lines.append(f"REGIME: {brief.regime} VIX {brief.vix:.2f}")
    lines.append(f"CAPITAL: ${brief.dynamic_capital_usd:,.0f}")
    lines.append("")

    # Stops -- top 5 by ticker (no P&L on the dataclass yet)
    lines.append("STOPS ─────────────────")
    if brief.stop_audit:
        for r in brief.stop_audit[:5]:
            mark = _stop_mark(r.status)
            sl_str = f"{r.sl:.2f}" if r.sl is not None else "—"
            dist_str = (
                f"{r.distance_pct:+.1f}%" if r.distance_pct is not None else "—"
            )
            lines.append(f"{mark} {r.ticker:5} SL {sl_str:>7} {dist_str:>6}")
    else:
        lines.append("(no open positions)")

    so = brief.stopout
    risk_mark = "⚠️" if so.breaches_5pct else "✅"
    lines.append(f"RISK: ${so.combined_usd:,.0f} ({so.combined_pct:.1f}%) {risk_mark}")
    lines.append("")

    # SRM bands
    lines.append("SRM ────────────────────")
    deploy = [r.get("etf") for r in (brief.srm_summary.get("table") or [])
              if isinstance(r, dict) and (r.get("grade") or "").upper() == "DEPLOY"]
    hold = [r.get("etf") for r in (brief.srm_summary.get("table") or [])
            if isinstance(r, dict) and (r.get("grade") or "").upper() == "HOLD"]
    avoid = [r.get("etf") for r in (brief.srm_summary.get("table") or [])
             if isinstance(r, dict) and (r.get("grade") or "").upper() == "AVOID"]
    if deploy:
        lines.append(f"▲ DEPLOY  {' '.join(filter(None, deploy[:4]))}")
    if hold:
        lines.append(f"━ HOLD    {' '.join(filter(None, hold[:5]))}")
    if avoid:
        lines.append(f"▼ AVOID   {' '.join(filter(None, avoid[:4]))}")
    if not (deploy or hold or avoid):
        lines.append("(SRM unavailable)")
    lines.append("")

    # Pipeline cross-ref
    pcount = brief.universe.get("count", 0)
    pcap = brief.universe.get("cap", 10)
    lines.append(f"PIPELINE [{pcount}/{pcap}] ────────")
    for r in brief.pipeline_x_aqe[:4]:
        sc = r.get("aqe_sc_mom") or r.get("sc_mom") or 0
        ptrs = r.get("ptrs_cached") or 0
        try:
            sc_str = f"{float(sc):.0f}"
        except (TypeError, ValueError):
            sc_str = "—"
        try:
            ptrs_str = f"{float(ptrs):.0f}"
        except (TypeError, ValueError):
            ptrs_str = "—"
        lines.append(
            f"{r['ticker']:5} {r.get('status','—'):6} "
            f"SC{sc_str} PTRS{ptrs_str} ✅"
        )
    if not brief.pipeline_x_aqe:
        lines.append("(empty)")
    lines.append("")

    # New in AQE
    if brief.new_aqe_candidates:
        lines.append("NEW IN AQE ─────────────")
        for nc in brief.new_aqe_candidates[:3]:
            sc = nc.get("sc_momentum") or 0
            try:
                sc_str = f"{float(sc):.0f}"
            except (TypeError, ValueError):
                sc_str = "—"
            sector = nc.get("gics_sector") or ""
            lines.append(f"{nc['ticker']:5} SC{sc_str} {sector} ✅")
        lines.append("")

    # Actions
    if brief.priority_actions:
        lines.append("⚡ ACTIONS")
        for i, a in enumerate(brief.priority_actions[:5], 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    # Footer link (always last)
    lines.append(f"→ {WEB_BASE_URL}/brief/premarket")

    return _truncate(lines, max_lines)


# ---------------------------------------------------------------------------
# S11 -- Market Open Brief
# ---------------------------------------------------------------------------

def format_open_telegram(brief: MarketOpenBrief, max_lines: int = 40) -> str:
    lines: list[str] = []
    ts = _parse_ts(brief.timestamp_sgt)
    lines.append("📈 AEGIS MARKET OPEN")
    lines.append(f"{ts.strftime('%a %d %b · %H:%M SGT / 09:30 ET')}")
    lines.append("")
    lines.append(f"REGIME: {REGIME_EMOJI.get(brief.regime,'·')} {brief.regime} VIX {brief.vix:.2f}")
    lines.append("")

    lines.append("OVERNIGHT GAPS")
    if brief.gaps:
        for g in brief.gaps[:6]:
            mark = "✅"
            note = ""
            if g.status == "NEAR_SL":
                mark = "⚠️"
                note = f" SL {g.sl:.2f} in range" if g.sl else " near SL"
            elif g.status == "GAP_DOWN":
                mark = "▼"
                note = " gap down"
            elif g.status == "GAP_UP":
                mark = "✅"
                note = " gap up"
            elif g.status == "FLAT":
                mark = "━"
                note = " no gap"
            prev = f"{g.prev_close:.2f}" if g.prev_close is not None else "—"
            opn = f"{g.open_price:.2f}" if g.open_price is not None else "—"
            gap_d = f" {g.gap_dollars:+.2f}" if g.gap_dollars is not None else ""
            lines.append(f"{mark} {g.ticker:5} {prev:>7} → {opn:>7}{gap_d}{note}")
    else:
        lines.append("(no positions to check)")
    lines.append("")

    if brief.brackets:
        lines.append("BRACKETS ACTIVE (confirm in IBKR)")
        for b in brief.brackets[:6]:
            lim = f"{b.limit_price:.2f}" if b.limit_price is not None else "—"
            stp = f"{b.stop_price:.2f}" if b.stop_price is not None else "—"
            lines.append(f"□ {b.ticker:5} LMT {lim:>7} STP {stp:>7}")
        lines.append("")

    if brief.priority_actions:
        lines.append("⚡ PRIORITY")
        for i, a in enumerate(brief.priority_actions[:5], 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    lines.append(f"→ {WEB_BASE_URL}/brief/open")
    return _truncate(lines, max_lines)


# ---------------------------------------------------------------------------
# S12 -- Market Close Brief
# ---------------------------------------------------------------------------

def format_close_telegram(brief: MarketCloseBrief, max_lines: int = 40) -> str:
    lines: list[str] = []
    ts = _parse_ts(brief.timestamp_sgt)
    lines.append("📉 AEGIS CLOSE BRIEF")
    lines.append(f"{ts.strftime('%a %d %b · %H:%M SGT / 16:00 ET')}")
    lines.append("")

    sess = brief.session_pnl_usd
    real = brief.realised_pnl_usd
    unr = brief.unrealised_pnl_usd
    sess_str = _money(sess)
    real_str = _money(real)
    unr_str = _money(unr)
    lines.append(f"SESSION: {sess_str} (Unreal {unr_str}, Realised {real_str})")
    if brief.q2_cumulative_realised is not None:
        lines.append(f"Q2 CUMULATIVE: {_money(brief.q2_cumulative_realised)}")
    lines.append("")

    lines.append("POSITION EOD")
    if brief.eod_positions:
        for p in brief.eod_positions[:6]:
            mark = "⚠️" if p.near_sl else "✅"
            close = f"{p.close:.2f}" if p.close is not None else "—"
            sl = f"{p.sl:.2f}" if p.sl is not None else "—"
            tier = f"(T{p.tier})" if p.tier is not None else ""
            note = " — STILL NEAR. Review." if p.near_sl else ""
            lines.append(f"{mark} {p.ticker:5} {close:>7} SL {sl:>7} {tier}{note}")
    else:
        lines.append("(no positions)")
    lines.append("")

    if brief.trail_events:
        lines.append("TRAIL EVENTS TODAY")
        for ev in brief.trail_events[:5]:
            old = f"{ev.old_sl:.2f}" if ev.old_sl is not None else "—"
            new = f"{ev.new_sl:.2f}" if ev.new_sl is not None else "—"
            tier = f" Tier {ev.new_tier}" if ev.new_tier is not None else ""
            lines.append(f"🔼 {ev.ticker} →{tier}. SL: ${old} → ${new}")
        lines.append("")

    if brief.srm_delta:
        lines.append("SRM DELTA")
        for d in brief.srm_delta[:5]:
            arrow = "⬆" if d.direction == "UPGRADE" else "⬇"
            lines.append(f"{d.etf}: {d.from_grade} → {d.to_grade} {arrow} ({d.direction.lower()})")
        lines.append("")

    if brief.ibkr_updates:
        lines.append("⚡ IBKR UPDATES REQUIRED")
        for i, u in enumerate(brief.ibkr_updates[:5], 1):
            lines.append(f"{i}. {u.label} [copy: {u.payload}]")
        lines.append("")

    lines.append("PTJ auto-runs at 04:30 SGT.")
    lines.append(f"→ {WEB_BASE_URL}/brief/close")
    return _truncate(lines, max_lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(tz=SGT)


def _stop_mark(status: str) -> str:
    return {"OK": "✅", "NEAR": "⚠️", "BREACH": "🔴"}.get(status, "·")


def _money(v: float | None) -> str:
    if v is None:
        return "$0"
    sign = "+" if v > 0 else ("−" if v < 0 else " ")
    return f"{sign}${abs(v):,.0f}"


def _truncate(lines: list[str], max_lines: int) -> str:
    if len(lines) <= max_lines:
        return "\n".join(lines)
    keep = lines[: max_lines - 2]
    keep.append("...")
    keep.append(lines[-1])      # always retain the web link footer
    return "\n".join(keep)
