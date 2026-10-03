"""Alert digest emailer — HTTP (Resend) primary, Gmail SMTP fallback.

HF Spaces block outbound SMTP, so the in-app 15-min poller emails via Resend's
HTTPS REST API (works from HF). The GitHub Actions backstop can use either —
Resend if its key is set, else Gmail SMTP. Pick automatically.

Layout (PM ruling): grouped by alert type, ranked by SC_MOM within a group, with
HELD names floated to the very top. Compact, scannable, each row carries a
one-line "engage AIC via Claude" prompt.

Secrets:
    RESEND_API_KEY      Resend API key (HTTP path — preferred, works on HF)
    AQE_ALERT_FROM      sender, default "AQE Alerts <onboarding@resend.dev>"
    AQE_ALERT_TO        recipient, default ash.tzl@gmail.com
    AQE_SMTP_USER/PASSWORD   Gmail SMTP fallback (GitHub Actions only)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

DEFAULT_TO = "ash.tzl@gmail.com"
DEFAULT_FROM = "AQE Alerts <onboarding@resend.dev>"

# Sections in render order. HELD floats above all of these.
# Ordered by WHAT IT ASKS OF YOU, not by event name — the digest is read top
# down under time pressure, so the sections descend from "act" to "context".
# Held risk floats above everything in its own block (see _compose).
_SECTIONS = [
    ("BOS",           "🚀 BROKE OUT — cleared its structural level", "#0a66cc"),
    ("NEAR_BREAKOUT", "👀 APPROACHING BREAKOUT — climbing into the level", "#7a5af0"),
    ("NEAR_TARGET",   "🎯 APPROACHING FIRST TARGET", "#0a8a3a"),
    ("NEAR_STOP",     "🛑 APPROACHING STOP", "#d33"),
    ("MOVE",          "📈 MOVING — reference only, no entry claim", "#777"),
]
# Held-only events, shown inside the HELD block rather than as sections.
_HELD_EVENTS = ("VETO_HELD", "NEAR_STOP")
# Intraday reads are CONTEXT on whatever fired — never their own alert. They
# are unproven thresholds (see alerts/intraday.py), so they annotate a line
# that earned its place some other way rather than generating email of their own.
_SIGNATURE_LABEL = {
    "COIL": "COIL — tight and holding its highs",
    "THRUST": "THRUST — expanding on volume, pressing the high",
    "FAILED_PUSH": "FAILED PUSH — wide day, sold into the low",
}


def _cfg() -> dict:
    pw = os.environ.get("AQE_SMTP_PASSWORD")
    if pw:
        pw = pw.replace(" ", "").strip()
    return {
        "resend_key": os.environ.get("RESEND_API_KEY"),
        "from": os.environ.get("AQE_ALERT_FROM") or DEFAULT_FROM,
        "to": os.environ.get("AQE_ALERT_TO") or os.environ.get("AQE_SMTP_USER") or DEFAULT_TO,
        "smtp_user": os.environ.get("AQE_SMTP_USER") or DEFAULT_TO,
        "smtp_pw": pw,
        "smtp_host": os.environ.get("AQE_SMTP_HOST") or "smtp.gmail.com",
        "smtp_port": int(os.environ.get("AQE_SMTP_PORT") or 465),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["resend_key"] or c["smtp_pw"])


def _fmt(v, dp=2):
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Body building
# ---------------------------------------------------------------------------

def _rec_lookup(export: dict) -> dict:
    out: dict = {}
    for tier in ("held_positions", "daily_list", "_radar_pool"):
        for r in export.get(tier) or []:
            out.setdefault(r.get("ticker"), r)
    return out


def _sc(rec: dict):
    v = rec.get("sc_momentum_raw")
    if v is None:
        v = rec.get("sc_momentum")
    try:
        return float(v)
    except (TypeError, ValueError):
        return -1.0


def _rr_struct(rec: dict):
    """Per-name R:R from the structural bracket (bracket.rr, else nearest target's r)."""
    b = rec.get("bracket") or {}
    if b.get("rr") is not None:
        return b.get("rr")
    tgts = b.get("targets") or []
    if tgts and isinstance(tgts[0], dict):
        return tgts[0].get("r")
    return None


def _bracket_str(rec: dict) -> str:
    """Compact structural bracket for the AIC line: stop (type) + TP ladder + R:R,
    or 'no valid bracket'."""
    b = rec.get("bracket") or {}
    if not b or not b.get("valid"):
        return "no valid bracket"
    _tps = "/".join(_fmt(t.get("price")) for t in (b.get("targets") or [])[:3]) or "—"
    return (f"stop {_fmt(b.get('stop'))} ({b.get('stop_type') or '—'}) "
            f"TP {_tps} (R:R {_fmt(b.get('rr'), 2)})")


def _aic_line(tk: str, rec: dict, t: dict) -> str:
    g = rec.get
    base = (f"AIC — {tk} ({'HELD' if t['is_held'] else t.get('source')}): "
            f"{t['label']} @ live {t['live_px']}. "
            f"SC {_fmt(g('sc_momentum'), 1)}/raw {_fmt(g('sc_momentum_raw'), 1)} · "
            f"MP {g('mp_state') or '—'} · "
            f"Flow {_fmt(g('flow'), 0)} En {_fmt(g('energy'), 0)} "
            f"St {_fmt(g('structure'), 0)} MP {_fmt(g('mp'), 0)} Eld {_fmt(g('elder'), 1)} · "
            f"{_bracket_str(rec)} · β30d {_fmt(g('beta_30d'), 2)} · "
            f"sector {g('gics_sector') or '—'} {g('gics_gate') or '—'}.")
    # Radar early-move context: flag that this is a WATCHED coil running ahead of
    # its expected ~12-day lead — the detection tag + its conviction label.
    _rad = str(t.get("source") or "")
    if _rad.startswith("radar"):
        if g("premove_setup") and g("premove_conviction_label"):
            base += (f" ⚡ PRE-MOVE radar running EARLY — premove {g('premove_conviction_label')} "
                     f"(detection tag, not a win rate; watched coil, ~12d median lead).")
        elif g("runner_setup") and g("runner_conviction_label"):
            base += (f" ⚡ RUNNER radar — runner {g('runner_conviction_label')} "
                     f"(detection tag, not a win rate).")
    if t["is_held"]:
        base += (f" Trade: entry {_fmt(g('entry'))} qty {g('qty')} "
                 f"SL {_fmt(g('held_sl'))} unreal ${_fmt(g('unreal_usd'), 0)}. "
                 "Advise hold / trim / stop mgmt.")
    else:
        base += " Advise entry decision + size per SC_MOMENTUM x regime. Charter v1.9.2."
    return base


def _build_bodies(triggers: list[dict], export: dict) -> tuple[str, str, str]:
    """Return (subject, plain, html)."""
    rl = _rec_lookup(export)
    now_sgt = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M SGT")
    regime = export.get("regime") or {}
    regime_txt = regime.get("level") if isinstance(regime, dict) else regime
    exp_date = export.get("date") or "?"

    # Bucket: held (any type) floats to a section of its own; rest by type.
    held = [t for t in triggers if t.get("is_held")]
    by_type = {key: [t for t in triggers if not t.get("is_held") and t["level"] == key]
               for key, _, _ in _SECTIONS}

    def _sortkey(t):
        return -_sc(rl.get(t["ticker"], {}))

    held.sort(key=_sortkey)
    for v in by_type.values():
        v.sort(key=_sortkey)

    n = len(triggers)
    counts = {key: len(v) for key, v in by_type.items()}
    # Subject leads with what needs a decision; MOVE is deliberately last and
    # unlabelled-as-urgent because it is a reference, not a signal.
    _bits = [f"{counts['BOS']} broke out"] if counts.get("BOS") else []
    if counts.get("NEAR_BREAKOUT"):
        _bits.append(f"{counts['NEAR_BREAKOUT']} approaching")
    if counts.get("NEAR_TARGET"):
        _bits.append(f"{counts['NEAR_TARGET']} at target")
    if held:
        _bits.insert(0, f"{len(held)} HELD")
    if counts.get("MOVE"):
        _bits.append(f"{counts['MOVE']} moving")
    subject = (f"[AQE] {len({t['ticker'] for t in triggers})} names · "
               + " · ".join(_bits or ["no events"]))

    # ---- plain text ----
    tl = [f"AQE alerts — {now_sgt} · export {exp_date} · regime {regime_txt or '—'}",
          f"{n} alert(s) on {len({t['ticker'] for t in triggers})} names. "
          f"Prices 15-min delayed. Every line shows the move vs last close.", ""]

    def _lists(rec):
        on = [n for n, k in (("LL", "on_longlist"), ("ELD", "on_elder"),
                             ("QS", "on_qs")) if rec.get(k)]
        return "+".join(on) if on else "—"

    def _sig(t):
        """Intraday read as CONTEXT on this line — never its own alert."""
        s = (t.get("intraday") or {}).get("signature")
        return f"  ⟨{_SIGNATURE_LABEL.get(s, s)}⟩" if s else ""

    def _line(t, compact=False):
        """Full block for an actionable event; ONE line for a reference one.

        MOVE is reference-only, so it gets a single row. Giving it the same
        three-line treatment as a break of structure buries the events that
        actually ask something of you — 19 movement lines each carrying a full
        AIC prompt is a wall, not a digest.
        """
        rec = rl.get(t["ticker"], {})
        tag = "★HELD" if t["is_held"] else _lists(rec)
        chg = (f"{t['chg_pct']:+.1f}%" if t.get("chg_pct") is not None else "—")
        head = (f"  {t['ticker']:6} [{tag:8}] {t['live_px']:>9}  {chg:>7} vs COB"
                f" · SC {_fmt(rec.get('sc_momentum_raw') or rec.get('sc_momentum'), 0)}"
                )
        if compact:
            return head + _sig(t)
        return (head
                + f"\n         {t['label']}: {t.get('note') or ''}{_sig(t)}"
                + f"\n         {_aic_line(t['ticker'], rec, t)}")

    if held:
        tl.append(f"★ HELD ({len(held)})")
        tl += [_line(t) for t in held]
        tl.append("")
    for key, title, _ in _SECTIONS:
        if by_type[key]:
            tl.append(f"{title} ({len(by_type[key])})")
            # MOVE is reference-only -> one compact row per name.
            tl += [_line(t, compact=(key == "MOVE")) for t in by_type[key]]
            tl.append("")
    plain = "\n".join(tl)

    # ---- html ----
    def _card(t):
        rec = rl.get(t["ticker"], {})
        held_f = t["is_held"]
        color = "#d00" if held_f else "#0a66cc"
        badge = ("★ HELD" if held_f else (t.get("source") or "").upper())
        sc = _fmt(rec.get("sc_momentum_raw") or rec.get("sc_momentum"), 1)
        return (
            f"<div style='margin:6px 0;padding:8px 10px;border-left:4px solid {color};"
            f"background:#fafafa;border-radius:6px;color:#1a1a1a'>"
            f"<div><span style='background:{color};color:#fff;font-weight:700;font-size:11px;"
            f"padding:1px 7px;border-radius:9px'>{badge}</span> "
            f"<b style='font-size:15px'>{t['ticker']}</b> "
            f"<span style='color:#555;font-size:12px'>SC {sc} "
            f"· {rec.get('mp_state') or '—'} · β30d {_fmt(rec.get('beta_30d'),2)}</span></div>"
            f"<div style='font-size:13px;margin-top:2px'><b>{t['label']}</b> · "
            f"live {t['live_px']} · {t['note']}</div>"
            f"<div style='font-size:11px;color:#666;margin-top:3px;font-family:monospace;"
            f"white-space:pre-wrap'>{_aic_line(t['ticker'], rec, t)}</div></div>"
        )

    hl = [f"<h2 style='margin:0 0 4px'>AQE Trade Entry — {n} alert(s)</h2>",
          f"<p style='color:#555;margin:0 0 10px'><b>{now_sgt}</b> · export <b>{exp_date}</b> "
          f"· regime <b>{regime_txt or '—'}</b> · 15-min delayed · sorted by SC_MOM</p>"]
    if held:
        hl.append(f"<h3 style='color:#d00;margin:12px 0 2px'>★ HELD ({len(held)})</h3>")
        hl += [_card(t) for t in held]
    for key, title, c in _SECTIONS:
        if by_type[key]:
            hl.append(f"<h3 style='color:{c};margin:12px 0 2px'>{title} ({len(by_type[key])})</h3>")
            hl += [_card(t) for t in by_type[key]]
    html = "\n".join(hl)
    return subject, plain, html


# ---------------------------------------------------------------------------
# COMMITTEE LEVELS (PMA) — a new section at the very top of the SAME digest,
# above ★ HELD. Everything below the "existing digest" _build_bodies() call
# in send_digest() stays byte-identical when there are no PMA triggers —
# see tests/test_alert_pma_levels.py's golden heartbeat test.
#
# Card UX rules (AQE Handoff: PMA Live Alerts, 2026-09-30): plain words only
# — never `trade_above`, a trigger id, a JSON key, SC, beta, R:R or the AIC
# line in this section. Colour means one thing each: red = your money
# (HELD), green = a buy condition met, amber = not yet actionable. ACTION
# first (red, then green), then the amber cards — badged CAUTION (a risk
# read on a HELD position) or WATCHING (an entry-side read on a shortlist
# name), never the bare internal word "WARN" (see _pma_group_badge). INFO
# never appears intraday (it's evaluated and ledgered same as any trigger,
# just held for the after-close digest).
# ---------------------------------------------------------------------------

def _pma_dist(current, level):
    """Signed % distance, level relative to current price. Positive means
    the level sits ABOVE current price (still to go); negative means
    current price is already past it (through by)."""
    if level is None or current is None or current == 0:
        return None
    return (level - current) / current * 100


def _pma_stop_word(current, level) -> str:
    """A DOWNSIDE protective level (a stop). Safe while price sits above it
    ("X% away"); once price is AT or THROUGH it, that is a breach, not a
    buffer — said as "BREACHED by X%", never "away". A real production
    email (2026-09-30) showed "Committee stop 149.28 (1.8% away)" while the
    card's own headline said the position had already closed below that
    exact line — this is the fix."""
    if current is None or level is None or current == 0:
        return "—"
    if current > level:
        return f"{(current - level) / current * 100:.1f}% away"
    if current == level:
        return "AT THE LINE"
    return f"BREACHED by {(level - current) / current * 100:.1f}%"


def _pma_level_word(current, level) -> str:
    """The ENTRY trigger level: 'to go' while still below, 'through by'
    once price has already cleared it — the doc's own two example
    phrasings (piece: PK's card)."""
    d = _pma_dist(current, level)
    if d is None:
        return "—"
    return f"{d:.1f}% to go" if d > 0 else f"through by {abs(d):.1f}%"


def _pma_target_word(current, level) -> str:
    """The TARGET level (a profit objective, approached from below): 'away'
    while not yet reached — the doc's own literal example ("Target 185.48
    (5.7% away)") — and 'reached' once price is at or beyond it. Never
    "breach" language; hitting a target is the good outcome, unlike a stop."""
    d = _pma_dist(current, level)
    if d is None:
        return "—"
    if d > 0:
        return f"{d:.1f}% away"
    return "reached" if d == 0 else f"reached, +{abs(d):.1f}% through"


def _pma_number_line(t: dict) -> str:
    live = t.get("live_px")
    items = [f"Now {live}"]
    if t.get("is_held"):
        b_stop = t.get("broker_stop")
        items.append(f"Your stop {b_stop} ({_pma_stop_word(live, b_stop)})"
                     if b_stop is not None else "Your stop — none")
        c_exit = t.get("committee_exit")
        if c_exit is not None:
            items.append(f"Committee stop {c_exit} ({_pma_stop_word(live, c_exit)})")
    else:
        entry = t.get("entry_price")
        if entry is not None:
            items.append(f"Entry {entry} ({_pma_level_word(live, entry)})")
        target = t.get("target_price")
        if target is not None:
            items.append(f"Target {target} ({_pma_target_word(live, target)})")
    return " · ".join(items[:3])


def _pma_levels_line(t: dict) -> str:
    """ACTION cards only — one collapsed line, information only, never sized."""
    if t.get("priority") != "ACTION":
        return ""
    if t.get("is_held"):
        parts = []
        if t.get("committee_exit") is not None:
            parts.append(f"committee exit {t['committee_exit']}")
        if t.get("broker_stop") is not None:
            parts.append(f"broker stop {t['broker_stop']}")
    else:
        parts = []
        if t.get("computed_stop") is not None:
            parts.append(f"stop {t['computed_stop']}")
        targets = t.get("targets") or []
        if targets:
            parts.append("targets " + "/".join(_fmt(p) for p in targets[:3]))
    if not parts:
        return ""
    return "Levels: " + " · ".join(parts) + " — information only, not sized"


def _carried_tag(t: dict) -> str:
    if not t.get("carried"):
        return ""
    day = (t.get("age_sessions") or 0) + 1
    run = t.get("origin_run")
    try:
        run_fmt = datetime.strptime(run, "%Y-%m-%d").strftime("%-d %b")
    except (TypeError, ValueError):
        run_fmt = run or "—"
    return f"set {run_fmt} · day {day} of 3"


# ---- grouping: one card per (ticker, is_held), never two cards saying two
# things about the same position (a real production email, 2026-09-30,
# showed separate "closed below its line" and "near your stops" cards for
# the same USO position — confusing, not two distinct events). Section
# headers replace a flat colour-sorted list so the grouping a reader
# actually needs (act now / good news / keep watching) is explicit, not
# implied by a left border alone.
_PMA_SECTION_ORDER = [
    ("held", "🔴 HELD — needs your attention"),
    ("buy", "🟢 BUY CONDITIONS MET"),
    ("watch", "🟠 WATCHING"),
]


def _pma_group_key(t: dict) -> tuple:
    return (t.get("ticker"), t.get("is_held"))


def _pma_is_buy_condition(t: dict) -> bool:
    return t.get("priority") == "ACTION" and t.get("kind") in ("trade_above", "close_above")


def _pma_group_bucket(group: list[dict]) -> str:
    """Which section a card belongs in. HELD is its own section regardless
    of priority — it's the PM's money, that fact outranks whatever fired."""
    if group[0].get("is_held"):
        return "held"
    if any(_pma_is_buy_condition(t) for t in group):
        return "buy"
    return "watch"


def _pma_group_badge(group: list[dict]) -> tuple[str, str]:
    """Never render the bare internal priority word "WARN" — a real PM
    question (2026-09-30) was whether it meant a risk to their money or
    just an entry setup to watch, and the plain word answers neither. The
    HELD section is risk by construction (it's the PM's own book, and the
    section header already says "needs your attention"), so its WARN
    triggers (near-stop / an unconfirmed intraday touch of the committee's
    exit line) badge as CAUTION. Every non-held WARN trigger in this
    codebase (approaching_entry/approaching_target, a chase line, an
    unconfirmed intraday touch of a buy line) is entry-side, not risk —
    it lives in the WATCHING section, so its badge just says WATCHING."""
    if group[0].get("is_held"):
        label = "ACTION" if any(t.get("priority") == "ACTION" for t in group) else "CAUTION"
        return "#d00", f"HELD · {label}"
    if any(_pma_is_buy_condition(t) for t in group):
        return "#0a8a3a", "BUY CONDITION MET"
    if any(t.get("priority") == "ACTION" for t in group):
        return "#b8860b", "ACTION"
    return "#d9a441", "WATCHING"


def _pma_primary(group: list[dict]) -> dict:
    """The trigger whose headline leads the card: ACTION before WARN, and
    a specific committee trigger before a generic synthesized proximity
    check ("near your stops" says less than "closed under the committee's
    exit line 234.65")."""
    def rank(t):
        is_generic = t.get("kind") in ("near_stops", "approaching_entry", "approaching_target")
        return (0 if t.get("priority") == "ACTION" else 1, 1 if is_generic else 0)
    return sorted(group, key=rank)[0]


def _pma_group_headline(group: list[dict]) -> str:
    primary = _pma_primary(group)
    return f"{primary.get('ticker')} — {primary.get('headline_phrase') or 'level triggered'}"


def _pma_group_sentences(group: list[dict]) -> list[str]:
    """Every distinct committee sentence in the group, primary first, so a
    reader sees ALL the facts PMA gave for this position, not just one.

    Reads `note` before `action`, not the other way round. pma_levels.py
    builds `note` as `action` plus a caveat suffix when one applies (an
    intraday-unconfirmed close_above/close_below: "beyond the line
    intraday, confirms only on the close"; an unconfirmed volume gate) --
    `action` is always the bare committee sentence with no caveat. A real
    production card (2026-09-30, STX) badged WATCHING but its sentence
    still read "HOLD condition met... actionable for your own decision"
    with zero indication it hadn't closed yet, because this used to read
    `action` first and the caveat-bearing `note` was never reached. `note`
    equals `action` whenever no caveat applies, so this changes nothing
    for any trigger that fires clean."""
    primary = _pma_primary(group)
    ordered = [primary] + [t for t in group if t is not primary]
    seen, out = set(), []
    for t in ordered:
        s = (t.get("note") or t.get("action") or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _pma_group_levels_line(group: list[dict]) -> str:
    action_t = next((t for t in group if t.get("priority") == "ACTION"), None)
    return _pma_levels_line(action_t) if action_t else ""


def _pma_group_tag(group: list[dict]) -> str:
    for t in group:
        tag = _carried_tag(t)
        if tag:
            return tag
    return ""


def _pma_group_signature(group: list[dict]) -> str | None:
    """The tape-read context (COIL/THRUST/FAILED_PUSH) if any trigger in
    the group carries one — annotation only, same non-alerting role the
    legacy heartbeat already gives it (see _sig() above)."""
    for t in group:
        sig = (t.get("intraday") or {}).get("signature")
        if sig:
            return sig
    return None


def _pma_card_plain(group: list[dict]) -> str:
    rep = group[0]
    sig = _pma_group_signature(group)
    sig_tag = f"  ⟨{_SIGNATURE_LABEL.get(sig, sig)}⟩" if sig else ""
    lines = [f"  {_pma_group_headline(group)}  [{_pma_group_badge(group)[1]}]{sig_tag}",
            f"    {_pma_number_line(rep)}"]
    for s in _pma_group_sentences(group):
        lines.append(f"    · {s}")
    levels_line = _pma_group_levels_line(group)
    if levels_line:
        lines.append(f"    {levels_line}")
    tag = _pma_group_tag(group)
    if tag:
        lines.append(f"    ({tag})")
    return "\n".join(lines)


def _pma_card_html(group: list[dict]) -> str:
    rep = group[0]
    color, badge = _pma_group_badge(group)
    sentences = _pma_group_sentences(group)
    levels_line = _pma_group_levels_line(group)
    tag = _pma_group_tag(group)
    sig = _pma_group_signature(group)
    sig_html = (f" <span style='color:#888;font-size:10.5px'>"
               f"⟨{_SIGNATURE_LABEL.get(sig, sig)}⟩</span>" if sig else "")
    parts = [
        f"<div style='margin:6px 0;padding:8px 10px;border-left:4px solid {color};"
        f"background:#fafafa;border-radius:6px;color:#1a1a1a;font-size:14px'>",
        f"<div><span style='background:{color};color:#fff;font-weight:700;font-size:11px;"
        f"padding:1px 7px;border-radius:9px'>{badge}</span> ",
        f"<b style='font-size:15px'>{_pma_group_headline(group)}</b>{sig_html}",
    ]
    if tag:
        parts.append(f" <span style='color:#888;font-size:10.5px;background:#eee;"
                     f"padding:1px 6px;border-radius:8px'>{tag}</span>")
    parts.append("</div>")
    parts.append(f"<div style='font-size:13px;margin-top:3px'>{_pma_number_line(rep)}</div>")
    for s in sentences:
        parts.append(f"<div style='font-size:13px;color:#333;margin-top:2px'>"
                     f"Committee: {s}</div>")
    if levels_line:
        parts.append(f"<div style='font-size:11.5px;color:#666;margin-top:3px'>"
                     f"{levels_line}</div>")
    parts.append("</div>")
    return "".join(parts)


def _pma_subject_bits(primaries: list[dict], limit: int = 2) -> str:
    """Two lead items plus a movement tally, e.g. "PK buy line hit · NTRA
    stop order check · +12 names moving" — plain words only."""
    bits = []
    for t in primaries[:limit]:
        bits.append(f"{t.get('ticker')} {t.get('headline_phrase')}")
    rest = len(primaries) - len(bits)
    if rest > 0:
        bits.append(f"+{rest} more")
    return " · ".join(bits)


def _pma_group_sort_key(group: list[dict]):
    """Within a section, an ACTION-carrying group leads a WARN-only one;
    ties broken by ticker so the order is stable run to run."""
    has_action = any(t.get("priority") == "ACTION" for t in group)
    return (0 if has_action else 1, group[0].get("ticker") or "")


def _build_pma_section(pma_triggers: list[dict]) -> tuple[str, str, str]:
    """Returns (subject_bits, plain_block, html_block). Empty strings when
    there is nothing to show — INFO-priority triggers never render here
    (after-close digest only), so an all-INFO cycle reads as "nothing" for
    this section too, exactly like an empty `pma_triggers` list.

    Groups triggers by (ticker, is_held) into one card each, then buckets
    those cards into the three sections above — never a flat list relying
    on left-border colour alone to convey what's urgent vs. informational.
    """
    shown = [t for t in (pma_triggers or []) if t.get("priority") != "INFO"]
    if not shown:
        return "", "", ""

    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for t in shown:
        key = _pma_group_key(t)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(t)
    all_groups = [groups[k] for k in order]

    buckets: dict[str, list[list[dict]]] = {"held": [], "buy": [], "watch": []}
    for g in all_groups:
        buckets[_pma_group_bucket(g)].append(g)
    for bucket in buckets.values():
        bucket.sort(key=_pma_group_sort_key)

    subject_primaries = [_pma_primary(g) for section_key, _ in _PMA_SECTION_ORDER
                         for g in buckets[section_key]]

    plain = ["COMMITTEE LEVELS (PMA)", ""]
    html = ["<h3 style='margin:0 0 6px;color:#333'>COMMITTEE LEVELS (PMA)</h3>"]
    for section_key, title in _PMA_SECTION_ORDER:
        group_list = buckets[section_key]
        if not group_list:
            continue
        plain.append(f"{title} ({len(group_list)})")
        plain += [_pma_card_plain(g) for g in group_list]
        plain.append("")
        html.append(f"<div style='font-weight:700;font-size:13px;color:#555;"
                    f"margin:10px 0 4px'>{title} ({len(group_list)})</div>")
        html += [_pma_card_html(g) for g in group_list]

    return _pma_subject_bits(subject_primaries), "\n".join(plain), "\n".join(html)


# ---------------------------------------------------------------------------
# After-close digest (build brief item 4) — confirmed closes, HOLD
# invalidations and the WATCH list, plus the two small tables. A fresh
# snapshot each time (like every other AQE read), not a replay of the day's
# earlier intraday alerts.
# ---------------------------------------------------------------------------

def _pct(price, level):
    if price is None or level is None or price == 0:
        return None
    return round(abs(price - level) / price * 100, 1)


def build_after_close_digest(pma_doc: dict, quotes: dict) -> tuple[str, str, str]:
    """Returns (subject, plain, html). Never raises; a row with no quote or
    no level just drops out of its table rather than showing a blank."""
    from src.alerts import pma_levels as PMA

    rows = PMA.alertable_rows(pma_doc)
    held_rows = [r for r in rows if r.get("class") == "HELD"]
    shortlist_rows = [r for r in rows if r.get("class") != "HELD"]
    watch = PMA.watch_rows(pma_doc)

    held_table = []
    for r in held_rows:
        price = (quotes.get(r["ticker"]) or {}).get("price")
        if price is None:
            continue
        broker = (r.get("broker_stop") or {}).get("stop")
        c_exit = r.get("committee_exit")
        held_table.append({
            "ticker": r["ticker"], "close": round(price, 2),
            "your_stop_pct": _pct(price, broker), "committee_stop_pct": _pct(price, c_exit),
        })
    held_table.sort(key=lambda x: min(
        [v for v in (x["your_stop_pct"], x["committee_stop_pct"]) if v is not None] or [999]))

    sl_table = []
    for r in shortlist_rows:
        price = (quotes.get(r["ticker"]) or {}).get("price")
        if price is None:
            continue
        levels = r.get("levels") or {}
        entry_trig = next((t for t in r.get("triggers") or []
                           if t.get("priority") == "ACTION"
                           and t.get("kind") in ("trade_above", "close_above")), None)
        entry = entry_trig.get("level") if entry_trig else None
        tp = [p for p in (levels.get("tp") or []) if p is not None]
        target = next((p for p in tp if entry is not None and p > entry), None)
        day = ((r.get("age_sessions") or 0) + 1) if r.get("carried") else 1
        sl_table.append({
            "ticker": r["ticker"], "class": r["class"], "close": round(price, 2),
            "entry_pct": _pct(price, entry), "target_pct": _pct(price, target),
            "set_on": r.get("origin_run"), "day": day,
        })
    sl_table.sort(key=lambda x: x["entry_pct"] if x["entry_pct"] is not None else 999)

    watch_lines = [
        f"  {w.get('ticker'):6} doors={'+'.join(w.get('doors') or [])} "
        f"mp={w.get('mp')} pivot_gap={w.get('pct_from_pivot')}%"
        for w in watch
    ]

    subject = (f"[AQE] After close — {len(held_table)} held, "
              f"{len(sl_table)} on the shortlist, {len(watch)} watch")

    plain_lines = [subject, "", "HELD BOOK vs STOPS (nearest first)"]
    for h in held_table:
        plain_lines.append(
            f"  {h['ticker']:6} close {h['close']:>9}  your stop "
            f"{_fmt(h['your_stop_pct'], 1) if h['your_stop_pct'] is not None else '—'}%  "
            f"committee stop {_fmt(h['committee_stop_pct'], 1) if h['committee_stop_pct'] is not None else '—'}%")
    plain_lines += ["", "SHORTLIST vs ENTRY"]
    for s in sl_table:
        tag = f" (set {s['set_on']}, day {s['day']} of 3)" if s["day"] > 1 else ""
        plain_lines.append(
            f"  {s['ticker']:6} [{s['class']:20}] close {s['close']:>9}  entry "
            f"{_fmt(s['entry_pct'],1) if s['entry_pct'] is not None else '—'}%  "
            f"target {_fmt(s['target_pct'],1) if s['target_pct'] is not None else '—'}%{tag}")
    plain_lines += ["", f"WATCH ({len(watch)}) — digest only, no analyst nominated these"]
    plain_lines += watch_lines
    plain_lines += ["", "DRAFT — PM approval required. Nothing is staged, nothing is armed."]
    plain = "\n".join(plain_lines)

    def _tr(*cells):
        return "<tr>" + "".join(f"<td style='padding:3px 8px;font-size:12.5px'>{c}</td>"
                                for c in cells) + "</tr>"

    html_parts = [f"<h2>{subject}</h2>",
                  "<h3>Held book vs stops (nearest first)</h3>",
                  "<table style='border-collapse:collapse'>",
                  _tr("<b>Ticker</b>", "<b>Close</b>", "<b>Your stop</b>", "<b>Committee stop</b>")]
    for h in held_table:
        html_parts.append(_tr(h["ticker"], h["close"],
                              f"{h['your_stop_pct']}%" if h["your_stop_pct"] is not None else "—",
                              f"{h['committee_stop_pct']}%" if h["committee_stop_pct"] is not None else "—"))
    html_parts.append("</table>")
    html_parts.append("<h3>Shortlist vs entry</h3>")
    html_parts.append("<table style='border-collapse:collapse'>")
    html_parts.append(_tr("<b>Ticker</b>", "<b>Class</b>", "<b>Close</b>", "<b>Entry</b>",
                          "<b>Target</b>", "<b>Set on / day</b>"))
    for s in sl_table:
        tag = f"{s['set_on']}, day {s['day']} of 3" if s["day"] > 1 else "today"
        html_parts.append(_tr(s["ticker"], s["class"], s["close"],
                              f"{s['entry_pct']}%" if s["entry_pct"] is not None else "—",
                              f"{s['target_pct']}%" if s["target_pct"] is not None else "—", tag))
    html_parts.append("</table>")
    html_parts.append(f"<h3>WATCH ({len(watch)}) — digest only</h3>")
    html_parts.append("<ul>" + "".join(f"<li>{w.get('ticker')} — "
                                       f"doors {'+'.join(w.get('doors') or [])}, "
                                       f"mp {w.get('mp')}, pivot gap {w.get('pct_from_pivot')}%</li>"
                                       for w in watch) + "</ul>")
    html_parts.append(_DRAFT_FOOTER_HTML)
    html = "\n".join(html_parts)

    return subject, plain, html


# ---------------------------------------------------------------------------
# AQE handoff D123/R21 (2026-10-02) — condition state-change emails. Only
# called when config.PMA_CONDITIONS_LIVE is true (condition_cycle.py's own
# gate); shadow mode never reaches this function at all. §6: "an email
# goes out only on a change of state" — one call here IS one such change,
# never a per-trigger-touch re-send.
# ---------------------------------------------------------------------------

_CONDITION_STATE_LABEL = {
    "CONDITION_MET": ("🟢 CONDITION MET", "#0a8a3a"),
    "FAILED_PUSH": ("🟠 FAILED PUSH", "#d9a441"),
    "CHASED": ("🟠 CHASED", "#d9a441"),
    "ANALYST_OUT": ("🟠 ANALYST OUT", "#d9a441"),
    "EXIT_LINE_HELD": ("🔴 EXIT LINE", "#d00"),
    "EXIT_LINE_WARN": ("🟠 EXIT LINE", "#d9a441"),
}

# Which scannable category a condition word belongs under (PM ask,
# 2026-10-03: simple labeled lines -- "MA levels... met or bounced",
# "Vwap... hit or not", "Liquidity and volume... met or not with numbers" --
# rather than a flowing paragraph). Keyed off condition_spec.py's own word
# sets so a label never has to be guessed per-row.
_WORD_CATEGORY = {
    "close_above": "Structure", "close_below": "Structure",
    "h1_close_above": "Structure", "h1_close_below": "Structure",
    "trade_above": "Structure", "trade_below": "Structure",
    # reclaim IS the "wicked through then bounced back" read -- same word,
    # the plain text is what actually names the level.
    "reclaim": "Structure", "reject": "Structure", "in_zone": "Structure",
    "vol_x_ge": "Volume", "vol_x_le": "Volume",
    "above_vwap_s": "VWAP", "below_vwap_s": "VWAP",
    "rs_today_gt_spy": "Relative strength",
    "fade_atr_ge": "Extension",
    "clv_ge": "Close location", "clv_le": "Close location",
    "red_bar": "Candle",
}
_RESULT_TAG = {"TRUE": "MET", "FALSE": "NOT MET", "NOT_YET": "WATCHING",
              "UNKNOWN_WORD": "UNKNOWN"}


def _word_category(w: str | None) -> str:
    if w in _WORD_CATEGORY:
        return _WORD_CATEGORY[w]
    from . import condition_spec as _CS
    if w and _CS.is_cob_word(w):
        return "Daily read"
    return "Condition"


def _condition_lines(results: list[tuple[dict, str]]) -> list[str]:
    """One labeled, scannable line per word: '{Category}: {MET/NOT MET/
    WATCHING} — {plain}'. Still the committee's own `plain` text, never the
    raw word name or level (§2.5 house rule: never trade_above/close_below/
    a trigger id in a reader-facing line) -- only a category + verdict
    added in front of it."""
    out = []
    for entry, result in results:
        plain = entry.get("plain")
        if not plain:
            continue
        out.append(f"{_word_category(entry.get('w'))}: {_RESULT_TAG.get(result, result)} "
                   f"— {plain}")
    return out


def _bracket_line(row: dict) -> str | None:
    """Entry/stop/target/R:R for a glance-read bracket line. Entry is the
    committee's own shared buy level; stop/targets come from row['levels']
    — the SAME field the existing trigger-based COMMITTEE LEVELS section
    reads (src/alerts/pma_levels.py), never recomputed here. Omitted
    entirely (never a partial or fabricated bracket) when any one of
    entry/stop/a target above entry is missing."""
    shared = (row.get("conditions") or {}).get("shared") or {}
    entry_level = next((e.get("level") for e in (shared.get("buy") or [])
                       if e.get("level") is not None), None)
    if entry_level is None:
        return None
    levels = row.get("levels") or {}
    stop = levels.get("stop")
    if stop is None:
        return None
    target = next((t for t in (levels.get("tp") or [])
                  if t is not None and t > entry_level), None)
    if target is None:
        return None
    risk = entry_level - stop
    if risk <= 0:
        return None
    rr = (target - entry_level) / risk
    return (f"Bracket: entry {entry_level:.2f} · stop {stop:.2f} · "
           f"target {target:.2f} · R:R {rr:.1f}")


def _entry_readiness_line(primary: str, eval_result: dict) -> str:
    """A STATE, never an instruction. AQE makes no decisions (CLAUDE.md) —
    this reports where the buy condition stands (MET / WATCHING / NOT MET);
    whether to act on it is the PM/AIC's call, made outside this email."""
    if eval_result.get("buy_met"):
        return "Entry readiness: MET"
    if primary == "FAILED_PUSH":
        return "Entry readiness: WATCHING — prior push failed, waiting for the next attempt"
    if eval_result.get("no_shared_buy"):
        n_lit = eval_result.get("n_lit") or 0
        n_counting = eval_result.get("n_counting") or 0
        return f"Entry readiness: WATCHING — {n_lit} of {n_counting} analysts lit"
    return "Entry readiness: WATCHING"


def build_condition_state_body(ticker: str, row: dict, eval_result: dict,
                               fired_states: list[str], live: dict) -> tuple[str, str, str]:
    """Returns (subject, plain, html) for a condition state-change
    notice — built so it can be unit-tested independent of send.

    Line order mirrors a PM ask (2026-10-03) for a scannable, labeled
    structure rather than a flowing paragraph: each committee word as its
    own Category: MET/NOT MET/WATCHING line, the live volume/VWAP numbers
    behind them, chase/exit lines, a bracket summary, then where entry
    readiness stands overall."""
    primary = fired_states[0]
    label, color = _CONDITION_STATE_LABEL.get(primary, (primary, "#777"))
    lit, n_counting = eval_result.get("lit") or [], eval_result.get("n_counting") or 0
    headline = f"{ticker} · {label}"
    if primary == "CONDITION_MET" and n_counting:
        headline += f" · {len(lit)} of {n_counting} analysts"

    lines: list[str] = []
    lines += _condition_lines(eval_result.get("shared_buy_detail") or [])
    lines += _condition_lines(eval_result.get("shared_confirm_detail") or [])

    vol_x = (live.get("vol_x") or {}).get("so_far")
    if vol_x is not None:
        lines.append(f"Live: volume {vol_x:.1f}× normal for the time of day.")
    vwap_info = live.get("vwap") or {}
    if vwap_info.get("vwap") is not None and not vwap_info.get("provisional"):
        h1 = live.get("last_hourly_close")
        side = "Above" if (h1 is not None and h1 > vwap_info["vwap"]) else "Below"
        lines.append(f"Live: {side} today's VWAP {vwap_info['vwap']:.2f}.")

    shared = (row.get("conditions") or {}).get("shared") or {}
    chase = shared.get("chase")
    if chase and chase.get("plain"):
        lines.append(f"Chase line: {chase['plain']}.")
    if eval_result.get("exit_warn") or eval_result.get("exit_hit"):
        ex = eval_result.get("exit_hit") or eval_result.get("exit_warn")
        if ex and ex.get("plain"):
            lines.append(f"Exit line: {ex['plain']}.")

    bracket = _bracket_line(row)
    if bracket:
        lines.append(bracket)
    lines.append(_entry_readiness_line(primary, eval_result))

    subject = f"[AQE] {headline}"
    plain = (f"{headline}\n" + "\n".join(f"- {s}" for s in lines)
            + "\n\nInformation only. Nothing placed, changed, cancelled or sized.")
    html = (f"<div style='border-left:4px solid {color};padding:8px 12px;"
           f"background:#fafafa;border-radius:6px;color:#1a1a1a'>"
           f"<b style='font-size:15px'>{headline}</b>"
           + "".join(f"<div style='font-size:13px;margin-top:3px'>{s}</div>"
                     for s in lines)
           + "<div style='font-size:11px;color:#999;margin-top:6px'>Information only. "
             "Nothing placed, changed, cancelled or sized.</div></div>")
    return subject, plain, html


def send_condition_state_email(ticker: str, row: dict, eval_result: dict,
                               fired_states: list[str], live: dict) -> dict:
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend configured"}
    subject, plain, html = build_condition_state_body(ticker, row, eval_result,
                                                       fired_states, live)
    if cfg["resend_key"]:
        return _send_resend(cfg, subject, plain, html)
    return _send_smtp(cfg, subject, plain, html)


def send_after_close_digest(pma_doc: dict, quotes: dict) -> dict:
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend configured"}
    subject, plain, html = build_after_close_digest(pma_doc, quotes)
    if cfg["resend_key"]:
        return _send_resend(cfg, subject, plain, html)
    return _send_smtp(cfg, subject, plain, html)


def send_stale_pma_notice(reason: str) -> dict:
    """The one-per-day notice when the PMA file is missing or from a
    session other than today — never a silent skip. Sent standalone, not
    folded into the regular digest, since there is nothing else to show."""
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend configured"}
    subject = "[AQE] PMA levels are stale — not being watched today"
    plain = (f"{subject}\n\n{reason}\n\n"
            "The heartbeat alerts below (MOVE/BOS/NEAR_*) are unaffected.\n\n"
            "DRAFT — PM approval required. Nothing is staged, nothing is armed.")
    html = (f"<h3 style='color:#b8860b'>{subject}</h3><p>{reason}</p>"
           "<p style='color:#666'>The heartbeat alerts (MOVE/BOS/NEAR_*) are unaffected.</p>"
           "<p style='color:#999;font-size:11px'>DRAFT — PM approval required. "
           "Nothing is staged, nothing is armed.</p>")
    if cfg["resend_key"]:
        return _send_resend(cfg, subject, plain, html)
    return _send_smtp(cfg, subject, plain, html)


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def _send_resend(cfg: dict, subject: str, plain: str, html: str) -> dict:
    import requests
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {cfg['resend_key']}",
                     "Content-Type": "application/json"},
            json={"from": cfg["from"], "to": [cfg["to"]],
                  "subject": subject, "html": html, "text": plain},
            timeout=20)
        if resp.status_code in (200, 201):
            return {"ok": True, "to": cfg["to"], "via": "resend"}
        return {"ok": False, "reason": f"resend HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"resend error: {type(exc).__name__}: {exc}"}


def _send_smtp(cfg: dict, subject: str, plain: str, html: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["smtp_user"]
    msg["To"] = cfg["to"]
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=30, context=ctx) as s:
            s.login(cfg["smtp_user"], cfg["smtp_pw"])
            s.sendmail(cfg["smtp_user"], [cfg["to"]], msg.as_string())
        return {"ok": True, "to": cfg["to"], "via": "smtp"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"smtp error: {type(exc).__name__}: {exc}"}


_DRAFT_FOOTER_PLAIN = "\nDRAFT — PM approval required. Nothing is staged, nothing is armed.\n"
_DRAFT_FOOTER_HTML = ("<p style='color:#999;font-size:11px;margin-top:14px'>"
                     "DRAFT — PM approval required. Nothing is staged, nothing is armed.</p>")


def send_digest(triggers: list[dict], export: dict,
                pma_triggers: list[dict] | None = None) -> dict:
    """Send the digest. Resend if its key is set, else Gmail SMTP. Never raises.

    `pma_triggers` prepends the COMMITTEE LEVELS (PMA) section above the
    existing heartbeat digest. With no PMA triggers (the default), subject/
    plain/html are IDENTICAL to before this section existed — no footer, no
    empty heading, nothing — see tests/test_alert_pma_levels.py's golden
    heartbeat test.
    """
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend (set RESEND_API_KEY or AQE_SMTP_PASSWORD)"}
    pma_subject, pma_plain, pma_html = _build_pma_section(pma_triggers or [])
    if not triggers and not pma_subject:
        return {"ok": False, "reason": "no actionable triggers "
                                       "(INFO-only PMA activity waits for the after-close digest)"}
    subject, plain, html = _build_bodies(triggers, export) if triggers else (
        "[AQE] 0 names · no heartbeat events", "", "")

    if pma_subject:
        subject = f"[AQE] PMA: {pma_subject} · {subject.removeprefix('[AQE] ')}"
        plain = pma_plain + plain + _DRAFT_FOOTER_PLAIN
        html = pma_html + html + _DRAFT_FOOTER_HTML

    if cfg["resend_key"]:
        return _send_resend(cfg, subject, plain, html)
    return _send_smtp(cfg, subject, plain, html)


def send_test() -> dict:
    """Fire a one-off test digest so the PM can verify the email backend."""
    sample = [
        {"ticker": "TEST1", "source": "longlist", "is_held": False,
         "level": "BUY_ZONE", "label": "Hit buy price",
         "level_price": 101.5, "live_px": 101.6,
         "note": "today's range [100.40–102.10] crossed buy 101.50 (live 101.60)"},
        {"ticker": "ODFL", "source": "held", "is_held": True,
         "level": "NEAR_STOP", "label": "Approaching stop (SL)",
         "level_price": 230.0, "live_px": 235.0, "note": "2.2% above stop 230.00"},
    ]
    export = {"date": "TEST", "regime": {"level": "TEST"},
              "daily_list": [{"ticker": "TEST1", "sc_momentum": 78, "sc_momentum_raw": 78,
                            "mp_state": "STRONG", "flow": 82, "energy": 70,
                            "structure": 62, "mp": 60, "elder": 8, "beta_30d": 1.4,
                            "bracket": {"price": 100.0, "price_source": "eod_close",
                                        "stop": 96.5, "stop_type": "swing_low_1",
                                        "stop_atr_dist": 1.1, "risk": 3.5, "risk_pct": 3.5,
                                        "targets": [{"type": "resistance", "price": 108.0,
                                                     "r": 3.3, "atr_dist": 2.3}],
                                        "rr": 3.3, "valid": True, "invalid_reason": None},
                            "gics_sector": "XLK", "gics_gate": "PASS"}],
              "held_positions": [{"ticker": "ODFL", "sc_momentum": 62,
                                  "mp_state": "BUILDING", "entry": 239.45, "qty": 65,
                                  "held_sl": 230, "unreal_usd": 317, "beta_30d": 1.17,
                                  "bracket": {"price": 239.45, "stop": 228.0,
                                              "stop_type": "swing_low_1", "risk": 11.45,
                                              "targets": [], "rr": None, "valid": True,
                                              "invalid_reason": None}}]}
    return send_digest(sample, export)
