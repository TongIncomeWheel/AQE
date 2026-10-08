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

# Human-facing wording only. The state NAMES (the dict keys) are the
# handoff's own vocabulary and ride in the condition ledger PMA's scorecard
# reads cross-repo, so they stay as they are; what a PM sees in the inbox
# is sharpened here (PM feedback 2026-10-03: "what is exit line held? what
# is analyst out?"). EXIT_LINE_HELD vs _WARN splits on whether the row is
# a position actually HELD (class == "HELD") -- not on hourly-vs-daily
# close, which the body's own "Exit line:" sentence states separately.
_CONDITION_STATE_LABEL = {
    "CONDITION_MET": ("🟢 BUY CONDITIONS MET", "#0a8a3a"),
    # Was "PUSH FAILED" -- PM 2026-10-03: "if it failed there must be a
    # reason why we're still watching it." It IS still watched: the state
    # machine re-enters CONDITION_MET on the next qualifying hourly close,
    # so the label says what happened, and the card's summary line says
    # what would put it back in play.
    "FAILED_PUSH": ("🟠 BACK UNDER THE LEVEL — breakout didn't hold", "#d9a441"),
    "CHASED": ("🟠 EXTENDED — past the chase line", "#d9a441"),
    # ANALYST_OUT and EXIT_LINE_WARN are deliberately absent: neither is a
    # card of its own (PM 2026-10-03) -- condition_cycle filters both out
    # before cards are built. An invalidated seat shows as ✗ on the
    # Analysts line; an exit line on a name the PM doesn't hold isn't news.
    "EXIT_LINE_HELD": ("🔴 EXIT LINE CROSSED — HELD POSITION", "#d00"),
    # PM 2026-10-07: did the daily-reference undercut-and-rally happen today?
    "UNR_ARMED": ("🟡 U&R SETUP FORMING — wait for the entry signal", "#b8860b"),
    "UNR_TRIGGER": ("🟢 U&R ENTRY SIGNAL — 15-min candle closed above VWAP", "#0a8a3a"),
    "UNR_FAILED": ("🟠 U&R FAILED — under the stop", "#d9a441"),
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
# PM 2026-10-03: "each criteria in the card can have a simple tick or X."
# ◌ (not ✗) for NOT_YET -- the data isn't ready, the condition hasn't failed.
_RESULT_TAG = {"TRUE": "✓ MET", "FALSE": "✗ NOT MET", "NOT_YET": "◌ WATCHING",
              "UNKNOWN_WORD": "? UNKNOWN"}
_DIGEST_SHORT = {"UNR_ARMED": "U&R SETUP", "UNR_TRIGGER": "U&R ENTRY", "UNR_FAILED": "U&R FAILED", "CONDITION_MET": "BUY MET", "FAILED_PUSH": "BACK UNDER",
                 "CHASED": "EXTENDED", "EXIT_LINE_HELD": "EXIT HELD"}
_DISCLAIMER = "Information only. Nothing placed, changed, cancelled or sized."


def _word_category(w: str | None) -> str:
    if w in _WORD_CATEGORY:
        return _WORD_CATEGORY[w]
    from . import condition_spec as _CS
    if w and _CS.is_cob_word(w):
        return "Daily read"
    return "Condition"


def _word_plain(entry: dict) -> str:
    """Plain English for a word that arrived without `plain` -- PMA's
    per-seat words do (2026-10-03), the shared ones don't. PMA's own
    `plain` is always preferred when present; this is AQE's reading of
    condition_spec.py's vocabulary, never a raw word name in the inbox."""
    if entry.get("plain"):
        return entry["plain"]
    from .condition_evaluator import entry_level
    w = entry.get("w") or "condition"
    lv = entry_level(entry)
    x = entry.get("x")
    L = f"{lv:.2f}" if lv is not None else "the level"
    X = f"{float(x):g}" if isinstance(x, (int, float)) else None
    table = {
        "close_above": f"daily close above {L}", "close_below": f"daily close below {L}",
        "h1_close_above": f"hourly close above {L}", "h1_close_below": f"hourly close below {L}",
        "trade_above": f"trades above {L}", "trade_below": f"trades below {L}",
        "reclaim": f"dips under then reclaims {L}", "reject": f"pokes above then rejects {L}",
        "in_zone": f"pulls back into the zone near {L}",
        "vol_x_ge": f"volume ≥{X}× normal for the time of day" if X else "volume above normal",
        "vol_x_le": f"volume ≤{X}× normal for the time of day" if X else "volume below normal",
        "above_vwap_s": "holds above today's VWAP",
        "below_vwap_s": (f"{X} hourly closes below today's VWAP" if X
                         else "an hourly close below today's VWAP"),
        "rs_today_gt_spy": "outperforming SPY today",
        "fade_atr_ge": f"fades ≥{X} ATR off the high" if X else "fades off the high",
        "clv_ge": f"closes in the upper part of its range (CLV ≥{X})" if X else "closes near the high",
        "clv_le": f"closes in the lower part of its range (CLV ≤{X})" if X else "closes near the low",
        "red_bar": "closes red on the day",
        "choch_bearish": "bearish CHoCH on the daily (COB)",
        "ma_above": "above its moving average (COB)",
        "age_ge": f"setup at least {X} sessions old (COB)" if X else "setup age (COB)",
        "elder_ge": f"Elder impulse ≥{X} (COB)" if X else "Elder impulse (COB)",
        "elder_le": f"Elder impulse ≤{X} (COB)" if X else "Elder impulse (COB)",
    }
    if w in table:
        return table[w]
    if w.startswith("elder_"):
        return f"{w.replace('_', ' ')} (COB)"
    return w.replace("_", " ")


def _condition_lines(results: list[tuple[dict, str]]) -> list[str]:
    """One labeled, scannable line per word: '{Category}: {MET/NOT MET/
    WATCHING} — {plain}'. Still the committee's own `plain` text, never the
    raw word name or level (§2.5 house rule: never trade_above/close_below/
    a trigger id in a reader-facing line) -- only a category + verdict
    added in front of it."""
    out = []
    for entry, result in results:
        out.append(f"{_word_category(entry.get('w'))}: {_RESULT_TAG.get(result, result)} "
                   f"— {_word_plain(entry)}")
    return out


_MARK = {"TRUE": "✓", "FALSE": "✗", "NOT_YET": "◌", "UNKNOWN_WORD": "?"}


def _voice_lines(row: dict, eval_result: dict) -> list[str]:
    """One line per voice with ITS OWN criteria marked pass/fail -- the
    PM's chosen alternative (2026-10-03) to a live committee: PMA logs
    what each seat is looking for (`conditions.analysts[].buy/confirm/
    wrong`), AQE marks each word ✓/✗/◌ every cycle. Highest-conviction
    seats first, capped by config.CONDITION_CARD_MAX_SEATS; the rest fold
    into one '+N more' line with their overall marks."""
    from . import config as C
    detail = eval_result.get("analyst_detail") or {}
    if not detail:
        return []
    meta = {a.get("seat"): a for a in (row.get("conditions") or {}).get("analysts") or []}
    lit, wrong = set(eval_result.get("lit") or []), set(eval_result.get("wrong_lit") or [])

    def overall(seat: str) -> str:
        return "✗" if seat in wrong else ("✓" if seat in lit else "◌")

    seats = [s for s, d in detail.items() if (d or {}).get("counts", True)]
    seats.sort(key=lambda s: -(_n_or(meta.get(s, {}).get("conviction"), 0)))
    cap = max(1, C.CONDITION_CARD_MAX_SEATS)
    shown, rest = seats[:cap], seats[cap:]

    def bucket(name: str, results: list) -> str | None:
        if not results:
            return None
        words = ", ".join(f"{_MARK.get(r, '?')} {_word_plain(e)}" for e, r in results)
        return f"{name} {words}"

    lines = []
    for s in shown:
        d = detail[s]
        conv = meta.get(s, {}).get("conviction")
        tag = f" ({conv:g})" if isinstance(conv, (int, float)) else ""
        parts = [p for p in (bucket("buy", d.get("buy") or []),
                             bucket("confirm", d.get("confirm") or []),
                             bucket("wrong", d.get("wrong") or [])) if p]
        lines.append(f"{overall(s)} {s}{tag} — " + " · ".join(parts))
    if rest:
        lines.append("+" + f"{len(rest)} more: " + " · ".join(f"{overall(s)} {s}" for s in rest))
    return lines


def _n_or(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _effective_entry(row: dict) -> float | None:
    """The line the buy is judged against. Shared buy words are ALL-must-be-
    true, so when the committee ships several h1-close-above levels (real
    file, 2026-10-05: NTNX [72.75, 71.08], ZETA [32.01, 32.8]) the entry is
    the HIGHEST one -- price has to clear every line. Reading the first
    listed level (as this used to) put the entry below the true trigger and
    mis-stated every R."""
    from .condition_evaluator import entry_level as _lvl
    shared = (row.get("conditions") or {}).get("shared") or {}
    lv = [x for x in (_lvl(e) for e in (shared.get("buy") or [])
                      if (e or {}).get("w") in ("h1_close_above", "close_above",
                                                "trade_above"))
          if x is not None]
    if not lv:
        lv = [x for x in (_lvl(e) for e in (shared.get("buy") or [])) if x is not None]
    return max(lv) if lv else None


def _ema_lines(live: dict) -> list[str]:
    """EMA8 / EMA20 on the 15-min and daily charts (PM 2026-10-06). Figures
    only: where each average sits, how far spot is from it, which is on top,
    and which way each is pointing. Nothing here is a condition or a signal.
    A timeframe without enough history is left out, never faked."""
    ema = live.get("ema") or {}
    out = []
    for key, label in (("m15", "15-min"), ("daily", "daily")):
        r = ema.get(key)
        if not r:
            continue
        out.append(
            f"EMA {label}: EMA8 {r['ema8']:.2f} (spot {r['spot_vs_8_pct']:+.1f}%) · "
            f"EMA20 {r['ema20']:.2f} (spot {r['spot_vs_20_pct']:+.1f}%) · "
            f"8 {r['stack']} 20 · EMA8 {r['slope8']}, EMA20 {r['slope20']}")
    return out


def _session_lines(live: dict) -> list[str]:
    """U&R intraday reference figures (PM 2026-10-06, from the PM's U&R
    write-up): the opening-range high, the low of the day, and whether the
    hourly closes have just reclaimed (or lost) VWAP. FIGURES ONLY -- none of
    it feeds buy_met. Each line is left out when its data isn't there."""
    px = live.get("price")
    out = []
    orr = live.get("opening_range")
    if orr and px:
        hi, lo = orr["high"], orr["low"]
        if px > hi:
            where = f"spot {(px / hi - 1) * 100:.1f}% above the opening-range high"
        elif px < lo:
            where = f"spot {(1 - px / lo) * 100:.1f}% below the opening-range low"
        else:
            where = "spot inside the opening range"
        out.append(f"Opening range (first 15 min): high {hi:.2f} · low {lo:.2f} — {where}")
    day_lo, day_hi = live.get("day_low"), live.get("day_high")
    if day_lo and px:
        tail = f" · high of day {day_hi:.2f}" if day_hi else ""
        out.append(f"Low of day {day_lo:.2f}{tail} — spot {(px / day_lo - 1) * 100:.1f}% "
                   "above the low of day")
    vw = (live.get("vwap") or {})
    closes = live.get("hourly_closes") or []
    if vw.get("vwap") is not None and not vw.get("provisional") and len(closes) >= 2:
        v = vw["vwap"]
        if closes[-1] > v and closes[-2] <= v:
            out.append(f"VWAP {v:.2f}: reclaimed — the last hourly close is back above it "
                       "after closing below")
        elif closes[-1] <= v and closes[-2] > v:
            out.append(f"VWAP {v:.2f}: lost — the last hourly close fell back under it")
        elif closes[-1] > v and any(c <= v for c in closes[:-1]):
            out.append(f"VWAP {v:.2f}: holding above after an earlier close below it today")
    return out


def _spot_line(row: dict, live: dict) -> str | None:
    """Where price is NOW against the entry line -- the number the card
    never showed (PM 2026-10-06: "it doesn't give the spot price")."""
    px = live.get("price")
    if px is None:
        return None
    entry = _effective_entry(row)
    if entry is None or entry <= 0:
        return f"Spot {px:.2f}"
    pct = (px / entry - 1.0) * 100.0
    if px >= entry:
        return f"Spot {px:.2f} · {pct:.1f}% above the entry line {entry:.2f}"
    return (f"Spot {px:.2f} · {abs(pct):.1f}% BELOW the entry line {entry:.2f} "
            "— not at the entry right now")


def _rr_gate() -> float:
    try:
        from src.engines.bracket_engine import RR_MIN
        return float(RR_MIN)
    except Exception:  # noqa: BLE001
        return 2.0


def _bracket_line(row: dict) -> list[str]:
    """Entry / stop / the whole target ladder, each target with its OWN R
    measured from the entry line, then one verdict line on R:R to TP2.

    PM 2026-10-06: "the TP displayed is completely nonsense as all of them
    are R:R under 1... some even 0.2." Cause: this used to print the FIRST
    target above entry. In the committee file TP1 is the nearest level --
    often equal to the entry itself (GTLB 50.67/50.67, HPE 70.29/70.29) or a
    few tenths of an R away (NTNX 74.42 vs entry 72.75 = 0.4R) -- while the
    file's own rr_to_tp2 is measured to the SECOND target. So the ladder is
    shown whole, TP1/TP2/TP3 by their position in the file, and the headline
    R:R is to TP2, the same yardstick bracket_engine's gate uses. A target
    at or under the entry says so instead of being skipped. Empty list
    (never a partial or fabricated bracket) when entry/stop/targets are
    missing or the stop is not below the entry."""
    entry = _effective_entry(row)
    levels = row.get("levels") or {}
    stop = _n_or(levels.get("stop"), None)
    tps = [t for t in (levels.get("tp") or [])]
    tps = [_n_or(t, None) for t in tps]
    if entry is None or stop is None or not any(t is not None for t in tps):
        return []
    risk = entry - stop
    if risk <= 0:
        return []
    parts, rr_by_idx = [], {}
    for i, t in enumerate(tps, 1):
        if t is None:
            continue
        r = (t - entry) / risk
        rr_by_idx[i] = r
        if t <= entry + 1e-9:
            parts.append(f"TP{i} {t:.2f} (at/below entry — no room)")
        else:
            parts.append(f"TP{i} {t:.2f} ({r:.1f}R)")
    head = (f"Bracket: entry {entry:.2f} · stop {stop:.2f} (risk {risk:.2f}) · "
            + " · ".join(parts))
    idx = 2 if 2 in rr_by_idx else (max(rr_by_idx) if rr_by_idx else None)
    out = [head]
    if idx is not None:
        r = rr_by_idx[idx]
        gate = _rr_gate()
        if r < 1.0:
            verdict = "under 1R — the stop is wider than the move to that target"
        elif r < gate:
            verdict = f"below the {gate:.1f} gate"
        else:
            verdict = f"clears the {gate:.1f} gate"
        out.append(f"R:R to TP{idx} {r:.1f} — {verdict}")
    if levels.get("gates_clear") is False:
        out.append("Committee levels: the AQE bracket gates are not all clear for this name.")
    return out


def _entry_readiness_line(primary: str, eval_result: dict) -> str:
    """A STATE, never an instruction. AQE makes no decisions (CLAUDE.md) —
    this reports where the buy condition stands (MET / WATCHING / NOT MET);
    whether to act on it is the PM/AIC's call, made outside this email."""
    if eval_result.get("buy_met"):
        return "Entry readiness: ✓ MET"
    if primary == "FAILED_PUSH":
        return ("Entry readiness: ◌ WATCHING — re-qualifies on the next hourly close "
                "back above the level")
    if eval_result.get("no_shared_buy"):
        n_lit = eval_result.get("n_lit") or 0
        n_counting = eval_result.get("n_counting") or 0
        return f"Entry readiness: ◌ WATCHING — {n_lit} of {n_counting} analysts lit"
    return "Entry readiness: ◌ WATCHING"


def _analysts_line(eval_result: dict) -> str | None:
    """'Analysts: ✓ minervini · ✓ oneil · ✗ raschke (invalidated) · ◌ weis'.
    ✓ = that seat's own buy+confirm words are all true right now; ✗ = its
    own 'wrong' word fired (the former ANALYST OUT, now a mark on the card
    rather than an alert of its own); ◌ = neither yet. Seats come from the
    row's own analyst roster (counting seats only) plus whatever is lit."""
    lit = list(eval_result.get("lit") or [])
    wrong = list(eval_result.get("wrong_lit") or [])
    detail = eval_result.get("analyst_detail") or {}
    roster = [s for s, d in detail.items() if (d or {}).get("counts", True)]
    seats = roster + [s for s in lit + wrong if s not in roster]
    if not seats:
        return None
    marks = []
    for s in seats:
        if s in wrong:
            marks.append(f"✗ {s} (invalidated)")
        elif s in lit:
            marks.append(f"✓ {s}")
        else:
            marks.append(f"◌ {s}")
    return "Analysts: " + " · ".join(marks)


def _first_unmet_category(eval_result: dict) -> str | None:
    for entry, result in ((eval_result.get("shared_buy_detail") or [])
                          + (eval_result.get("shared_confirm_detail") or [])):
        if result != "TRUE":
            return _word_category(entry.get("w"))
    return None


def _card_summary(primary: str, row: dict, eval_result: dict,
                  live: dict | None = None) -> str | None:
    """The one plain sentence under the headline, built from the card's own
    numbers (PM 2026-10-03: the one-liner under each example card read
    clearer than the card itself). Never a recommendation."""
    from .condition_evaluator import entry_level as _lvl
    shared = (row.get("conditions") or {}).get("shared") or {}
    buy_level = _effective_entry(row)
    spot = (live or {}).get("price")
    n_lit, n_counting = eval_result.get("n_lit") or 0, eval_result.get("n_counting") or 0
    if primary == "CONDITION_MET":
        seats = f" — {n_lit} of {n_counting} analyst seats lit" if n_counting else ""
        return f"All buy conditions met{seats}."
    if primary == "UNR_TRIGGER":
        return "A 15-min candle closed above VWAP on a U&R candidate — Valen's entry trigger."
    if primary == "UNR_FAILED":
        return "Spot is under the low of day that was the stop at the trigger — the U&R failed."
    if primary == "UNR_ARMED":
        armed = ((live or {}).get("unr") or {}).get("armed") or []
        if armed:
            h = armed[0]
            return (f"Undercut {h['name']} {h['level']:.2f} (low {h['low']:.2f}) — a reclaim-day "
                    "candidate. Entry is the first 15-min candle that closes above VWAP.")
        return "A daily support level was undercut — a reclaim-day candidate."
    if primary == "FAILED_PUSH" and spot is not None and buy_level is not None and spot >= buy_level:
        # PM 2026-10-07 (CAT): spot 0.7% ABOVE the line was headed "BACK UNDER
        # THE LEVEL". The buy turned off because a CONFIRM lapsed, not because
        # price fell back -- say that.
        unmet = _first_unmet_category(eval_result)
        what = f"{unmet} confirm" if unmet else "a confirm"
        return (f"Price is still above {buy_level:.2f} (spot {spot:.2f}) but {what} "
                f"is not there. Still watched: it re-qualifies when it confirms again.")
    if primary == "FAILED_PUSH":
        cleared = f"Cleared {buy_level:.2f}" if buy_level is not None else "Cleared the buy level"
        unmet = _first_unmet_category(eval_result)
        tail = f" — {unmet} confirm never came" if unmet else ""
        back = f" back above {buy_level:.2f}" if buy_level is not None else " back above the level"
        # Why it's still on the list: the state machine re-enters BUY
        # CONDITIONS MET on the next qualifying hourly close.
        now = (f" Spot is {spot:.2f}." if spot is not None else "")
        return (f"{cleared}, then fell back under{tail}.{now} "
                f"Still watched: it re-qualifies on the next hourly close{back}.")
    if primary == "CHASED":
        lvl = _lvl(shared.get("chase") or {})
        where = f" {lvl:.2f}" if lvl is not None else ""
        met = "Buy conditions met" if eval_result.get("buy_met") else "Buy conditions not met"
        return f"{met}, but price already ran past the chase line{where}."
    if primary == "EXIT_LINE_HELD":
        ex = eval_result.get("exit_hit") or eval_result.get("exit_warn") or {}
        how = ("DAILY close confirmed" if eval_result.get("exit_hit")
               else "an hourly close so far")
        val = ex.get("value")
        at = f" {val:.2f}" if isinstance(val, (int, float)) else ""
        return f"A position you hold: {how} below the committee exit line{at}."
    return None


def _state_label(primary: str, row: dict, eval_result: dict, live: dict) -> tuple[str, str]:
    label, color = _CONDITION_STATE_LABEL.get(primary, (primary, "#777"))
    spot, entry = live.get("price"), _effective_entry(row)
    if primary == "FAILED_PUSH" and spot is not None and entry is not None and spot >= entry:
        return ("🟠 CONFIRMATION LOST — price still above the line", "#d9a441")
    return label, color


def _unr_line(unr: dict, spot: float | None) -> str:
    """The daily half: which support level was undercut and where spot is now
    against it. The reclaim is a tick, not a requirement (PM 2026-10-09)."""
    st = (unr or {}).get("status")
    if st == "ARMED":
        armed = unr["armed"]
        a0 = armed[0]
        more = f" +{len(armed) - 1} more" if len(armed) > 1 else ""
        pct = a0.get("spot_pct")
        if a0.get("reclaimed"):
            where = f"spot is back above it ✓ (+{pct:.1f}%)" if pct is not None else "spot is back above it ✓"
        else:
            where = (f"spot is {abs(pct):.1f}% under it, not reclaimed yet ◌"
                     if pct is not None else "spot is under it, not reclaimed yet ◌")
        when = "" if a0["when"] == "today" else f" {a0['when']}"
        return (f"U&R candidate — undercut {a0['name']} {a0['level']:.2f}{when}"
                f" (low {a0['low']:.2f}){more}; {where}")
    if st == "NOT_MET":
        return f"U&R ✗ NOT MET — {unr.get('reason') or 'no support level undercut'}"
    return f"U&R ◌ not checked — {(unr or {}).get('reason') or 'no data'}"


def _trigger_line(live: dict) -> str | None:
    """Valen's entry: a candle closes above VWAP after the wait below it.
    Built on 15-min bars (his chart is 5-min; the feed is 15-min, delayed)."""
    t = live.get("vwap_trigger") or {}
    st = t.get("state")
    if st == "TRIGGERED":
        return (f"Trigger ✓ — a 15-min candle closed above VWAP {t['vwap']:.2f} "
                f"at {t['at']} (entry ref {t['entry']:.2f})")
    if st == "ABOVE":
        return f"Trigger ◌ above VWAP {t['vwap']:.2f} since the open — no dip to reclaim"
    if st == "WAIT":
        return f"Trigger ◌ wait — below VWAP {t['vwap']:.2f}"
    if st == "NOT_READY":
        return "Trigger ◌ waiting for the first 15-min bars"
    return None


def _stop_volume_line(unr: dict, spot: float | None) -> str | None:
    """Stop = low of day, and his two volume marks (pullback dry, reclaim day
    above average). Marks only: they never decide MET."""
    bits = []
    stop = (unr or {}).get("stop")
    if stop is not None:
        pct = f" ({(1 - stop / spot) * 100:.1f}% under spot)" if spot else ""
        bits.append(f"Stop = low of day {stop:.2f}{pct}")
    v = (unr or {}).get("volume") or {}
    vb = []
    if v.get("pullback_dry") is not None:
        vb.append(f"pullback dry {'✓' if v['pullback_dry'] else '✗'}")
    if v.get("reclaim_x") is not None:
        vb.append(f"reclaim {v['reclaim_x']:.1f}× {'✓' if v.get('reclaim_ok') else '✗'}")
    if vb:
        bits.append("volume: " + ", ".join(vb))
    return " · ".join(bits) if bits else None


_SHORT_CAT = {"Structure": "price", "Volume": "volume", "VWAP": "VWAP",
              "Relative strength": "RS", "Daily read": "daily read"}


def _buy_line(row: dict, eval_result: dict, fired_states: list[str], live: dict) -> str | None:
    """One line: the committee/AQE buy conditions as marks, plus the entry line."""
    words = ((eval_result.get("shared_buy_detail") or [])
             + (eval_result.get("shared_confirm_detail") or []))
    n_counting = eval_result.get("n_counting") or 0
    shared = (row.get("conditions") or {}).get("shared") or {}
    if not words and not n_counting:
        return None                                    # a pure exit-only held row
    default = " (AQE default)" if row.get("aqe_default") else ""
    ok = bool(eval_result.get("buy_met"))
    # PM 2026-10-08: "✗ NOT MET" while every word was still pending (the first
    # hourly candle isn't complete until 10:30) read as a failure. Pending is
    # WATCHING; only a word that actually evaluated false is NOT MET.
    any_false = any(r == "FALSE" for _e, r in words)
    pending = (not any_false) and any(r == "NOT_YET" for _e, r in words)
    head = f"Buy conditions{default} " + ("✓ MET" if ok else ("◌ WATCHING" if pending else "✗ NOT MET"))
    bits = []
    if words:
        merged: dict[str, str] = {}        # one mark per category: any FALSE -> ✗,
        for e, r in words:                  # all TRUE -> ✓, else still pending
            cat = _SHORT_CAT.get(_word_category(e.get("w")), _word_category(e.get("w")).lower())
            prev = merged.get(cat)
            if prev is None:
                merged[cat] = r
            elif "FALSE" in (prev, r):
                merged[cat] = "FALSE"
            elif prev == "TRUE" and r == "TRUE":
                merged[cat] = "TRUE"
            else:
                merged[cat] = "NOT_YET"
        bits = [f"{cat} {_MARK.get(r, '?')}" for cat, r in merged.items()]
    elif shared.get("no_shared_buy") and n_counting:
        bits.append(f"{eval_result.get('n_lit') or 0} of {n_counting} analysts lit")
    entry, spot = _effective_entry(row), live.get("price")
    if entry is not None:
        tail = f"entry {entry:.2f}"
        if spot is not None:
            tail += f" (spot {(spot / entry - 1) * 100:+.1f}%)"
        bits.append(tail)
    return head + (" — " + " · ".join(bits) if bits else "")


def _fmt_levels(unr: dict) -> str | None:
    lv = (unr or {}).get("levels") or []
    if not lv:
        return None
    hit = {h["name"] for h in (unr.get("armed") or [])}
    return "Levels: " + " · ".join(f"{'▼' if x['name'] in hit else ''}{x['name']} {x['level']:.2f}"
                                   for x in lv)


def _reference_lines(row: dict, live: dict) -> list[str]:
    """The 'UnR reference' block: plain numbers only, one short line each."""
    out = []
    lv = _fmt_levels(live.get("unr"))
    if lv:
        out.append(lv + "   (▼ = undercut recently)")
    today = []
    orr = live.get("opening_range")
    if orr:
        today.append(f"open-range {orr['high']:.2f}/{orr['low']:.2f}")
    if live.get("day_low") is not None:
        today.append(f"low {live['day_low']:.2f}")
    if live.get("day_high") is not None:
        today.append(f"high {live['day_high']:.2f}")
    vw = live.get("vwap") or {}
    if vw.get("vwap") is not None and not vw.get("provisional"):
        bits = []
        spot = live.get("price")
        if spot is not None:
            bits.append("spot above" if spot > vw["vwap"] else "spot below")
        closes = live.get("hourly_closes") or []
        if len(closes) >= 2:
            if closes[-1] > vw["vwap"] >= closes[-2]:
                bits.append("hourly close reclaimed it")
            elif closes[-1] <= vw["vwap"] < closes[-2]:
                bits.append("hourly close lost it")
        today.append(f"VWAP {vw['vwap']:.2f}" + (f" ({', '.join(bits)})" if bits else ""))
    if today:
        out.append("Today: " + " · ".join(today))
    ema, parts = live.get("ema") or {}, []
    for key, lab in (("m15", "15m"), ("daily", "daily")):
        r = ema.get(key)
        if r:
            parts.append(f"{lab} {r['ema8']:.2f}/{r['ema20']:.2f}")
    if parts:
        out.append("EMA 8/20: " + " · ".join(parts))
    misc = []
    vol_x = (live.get("vol_x") or {}).get("so_far")
    if vol_x is not None:
        misc.append(f"volume {vol_x:.1f}×")
    el = live.get("elder") or {}
    if el.get("elder_live") is not None:
        misc.append(f"Elder {el['elder_live']}/10 {el.get('impulse_live') or ''}".rstrip())
    chase = ((row.get("conditions") or {}).get("shared") or {}).get("chase")
    from .condition_evaluator import entry_level as _lvl
    cl = _lvl(chase) if chase else None
    if cl is not None:
        misc.append(f"chase line {cl:.2f}")
    if misc:
        out.append(" · ".join(misc))
    return out


_PLAIN_LEVEL = {"EMA9": "9-day average", "EMA21": "21-day average", "Swing low": "recent low",
                "Trendline": "rising trendline", "Gap": "gap support"}


def _plain_level(name: str) -> str:
    return _PLAIN_LEVEL.get(name, name)


def _setup_text(a0: dict) -> str:
    """What happened on the daily chart, in words."""
    nm, lvl = _plain_level(a0["name"]), a0["level"]
    when = "" if a0["when"] == "today" else f" {a0['when']}"
    dip = f"Dipped below the {nm} ({lvl:.2f}){' today' if a0['when'] == 'today' else when}"
    if a0.get("reclaimed"):
        return dip + " and is back above it ✓"
    pct = a0.get("spot_pct")
    return dip + (f"; price is still {abs(pct):.1f}% under it" if pct is not None else "")


def _volume_plain(unr: dict) -> str | None:
    """Only the watch-outs; silence-with-a-tick when volume is fine."""
    v = (unr or {}).get("volume") or {}
    bad = []
    if v.get("reclaim_ok") is False and v.get("reclaim_x") is not None:
        bad.append(f"buying volume only {v['reclaim_x']:.1f}× normal")
    if v.get("pullback_dry") is False:
        bad.append("the pullback ran on heavy volume")
    if bad:
        return "Watch: " + "; ".join(bad)
    if v.get("reclaim_ok") or v.get("pullback_dry"):
        return "Volume confirms ✓"
    return None


def _nearby_levels(unr: dict, spot: float | None) -> str | None:
    """Support levels within 8% of price, in plain names. A gap 40% away is
    not a reference anyone needs."""
    lv = (unr or {}).get("levels") or []
    if not lv or not spot:
        return None
    near = [x for x in lv if abs(x["level"] / spot - 1.0) <= 0.08]
    if not near:
        return None
    return "Nearby levels: " + " · ".join(f"{_plain_level(x['name'])} {x['level']:.2f}" for x in near)


def _stop_text(unr: dict, spot: float | None, conditional: bool) -> str | None:
    stop = (unr or {}).get("stop")
    if stop is None:
        return None
    pct = f", {(1 - stop / spot) * 100:.1f}% below price" if spot else ""
    return (f"Stop would be {stop:.2f} (today's low){pct}" if conditional
            else f"Stop: {stop:.2f} (today's low){pct}")


_CLASS_LABEL = {"ADVANCE": "ADVANCE", "HOLD_FOR_CONDITIONS": "HOLD FOR CONDITIONS",
                "HELD": "HELD", "WATCH": "WATCH"}


def _who(row: dict) -> str:
    if row.get("aqe_default"):
        return "AQE default criteria"
    return f"Committee ({_CLASS_LABEL.get(row.get('class'), row.get('class') or 'book')})"


def _short_word(entry: dict) -> str:
    """One committee condition in plain words (never the raw word name)."""
    from .condition_evaluator import entry_level as _lvl
    w, lv, x = entry.get("w"), _lvl(entry), entry.get("x")
    L = f"{lv:.2f}" if lv is not None else "the level"
    X = f"{float(x):g}" if isinstance(x, (int, float)) else None
    table = {
        "h1_close_above": f"hourly close above {L}", "close_above": f"daily close above {L}",
        "trade_above": f"trades above {L}", "above_vwap_s": "holds above VWAP",
        "vol_x_ge": f"volume at least {X}× normal" if X else "volume above normal",
        "rs_today_gt_spy": "beating SPY today",
    }
    if w in table:
        return table[w]
    return _word_plain({k: v for k, v in entry.items() if k != "plain"})


def _word_detail(entry: dict, live: dict) -> str:
    """The live number that says how far a condition is from being met."""
    from .condition_evaluator import entry_level as _lvl
    w, spot, lv = entry.get("w"), live.get("price"), _lvl(entry)
    if w in ("h1_close_above", "close_above", "trade_above") and spot is not None and lv:
        pct = (spot / lv - 1) * 100
        return f" (price {spot:.2f}, {abs(pct):.1f}% {'above' if pct >= 0 else 'below'})"
    if w == "vol_x_ge":
        vx = (live.get("vol_x") or {}).get("so_far")
        if vx is not None:
            return f" (now {vx:.1f}×)"
    return ""


def _committee_block(row: dict, eval_result: dict, live: dict) -> list[str]:
    """The committee's (or AQE-default) entry / hold-for conditions, one plain
    line per condition with a tick, plus the exit line for a held name and the
    committee's stop and target. PM 2026-10-09: the U&R card had dropped these.
    Facts and levels only."""
    out = []
    words = ((eval_result.get("shared_buy_detail") or [])
             + (eval_result.get("shared_confirm_detail") or []))
    n_counting = eval_result.get("n_counting") or 0
    n_true = sum(1 for _e, r in words if r == "TRUE")
    who = _who(row)
    if words:
        state = "all met ✓" if eval_result.get("buy_met") else f"{n_true} of {len(words)} met"
        out.append(f"{who}: {state}")
        seen = set()
        for e, r in words:
            line = f"{_MARK.get(r, '?')} {_short_word(e)}{_word_detail(e, live)}"
            if line not in seen:
                seen.add(line)
                out.append(line)
    elif n_counting:
        out.append(f"{who}: {eval_result.get('n_lit') or 0} of {n_counting} analysts lit")
    for ex in ((row.get("conditions") or {}).get("exits") or [])[:1]:
        if ex.get("plain"):
            out.append(f"Exit line: {ex['plain']}")
    bs = _bracket_short(row)
    if bs:
        out.append(("AQE " if row.get("aqe_default") else "Committee ") + bs[0].lower() + bs[1:])
    return out


def _committee_tag(row: dict, eval_result: dict) -> str:
    words = ((eval_result.get("shared_buy_detail") or [])
             + (eval_result.get("shared_confirm_detail") or []))
    if not words:
        return ""
    n_true = sum(1 for _e, r in words if r == "TRUE")
    return f" · {_who(row)}: {n_true} of {len(words)} met"


def _bracket_short(row: dict) -> str | None:
    """Committee/AQE stop and the one target that matters (TP2), with its
    reward as a multiple of the risk."""
    entry = _effective_entry(row)
    levels = row.get("levels") or {}
    stop = _n_or(levels.get("stop"), None)
    tps = [_n_or(t, None) for t in (levels.get("tp") or [])]
    if entry is None or stop is None or entry - stop <= 0:
        return None
    idx = 2 if len(tps) >= 2 and tps[1] is not None else next(
        (i for i in range(len(tps), 0, -1) if tps[i - 1] is not None), None)
    if idx is None:
        return None
    t = tps[idx - 1]
    return f"Stop {stop:.2f} · target {t:.2f} (reward {(t - entry) / (entry - stop):.1f}× the risk)"


def _build_compact_card(ticker: str, row: dict, eval_result: dict,
                        fired_states: list[str], live: dict) -> dict:
    """PM 2026-10-09: "not executive and actionable ... verbal vomit". The
    answer first, in plain English: the state, the entry, the stop and the risk
    to it, then why, then only the watch-outs. Facts and levels, never a
    recommendation."""
    unr = live.get("unr") or {}
    spot = live.get("price")
    px = f" ${spot:.2f}" if spot is not None else ""
    held = " · HELD" if row.get("class") == "HELD" else ""
    armed = (unr.get("armed") or [None])[0]

    if any(x.startswith("UNR_") for x in fired_states):
        t = live.get("vwap_trigger") or {}
        if "UNR_FAILED" in fired_states:
            stop = eval_result.get("unr_stop")
            lines = [f"Price {f'{spot:.2f} ' if spot is not None else ''}fell under the stop"
                     + (f" ({stop:.2f})" if stop is not None else "")
                     + " that was set at the entry signal"]
            lines += _committee_block(row, eval_result, live)
            return {"headline": f"{ticker}{px} · 🟠 U&R FAILED{held}", "color": "#d9a441",
                    "summary": None, "lines": lines}
        lines = []
        if "UNR_TRIGGER" in fired_states:
            head, color = "🟢 U&R ENTRY SIGNAL", "#0a8a3a"
            if t.get("state") == "TRIGGERED":
                lines.append(f"A 15-min candle closed above VWAP at {t['at']} "
                             f"(price {t['entry']:.2f})")
            st = _stop_text(unr, spot, conditional=False)
        else:
            head, color = "🟡 U&R SETUP FORMING", "#b8860b"
            if t.get("state") == "ABOVE":
                lines.append("Price has held above VWAP since the open, so no entry signal yet")
            elif t.get("state") == "WAIT" and t.get("vwap") is not None:
                lines.append(f"Entry signal comes when a 15-min candle closes above VWAP ({t['vwap']:.2f})")
            else:
                lines.append("Waiting for the first 15-min candles")
            st = _stop_text(unr, spot, conditional=True)
        if st:
            lines.append(st)
        if armed:
            lines.append(_setup_text(armed))
        vol = _volume_plain(unr)
        if vol:
            lines.append(vol)
        lines += _committee_block(row, eval_result, live)
        near = _nearby_levels(unr, spot)
        if near:
            lines.append(near)
        return {"headline": f"{ticker}{px} · {head}{held}", "color": color,
                "summary": None, "lines": lines}

    # a buy-condition / extension / exit card: the state leads
    primary = fired_states[0]
    label, color = _state_label(primary, row, eval_result, live)
    lines = []
    if primary == "EXIT_LINE_HELD":
        ex = eval_result.get("exit_hit") or eval_result.get("exit_warn") or {}
        lines.append(ex.get("plain") or "held position through its exit line")
    elif primary == "CHASED":
        from .condition_evaluator import entry_level as _lvl
        cl = _lvl(((row.get("conditions") or {}).get("shared") or {}).get("chase") or {})
        lines.append(f"Price is past the chase line{f' ({cl:.2f})' if cl is not None else ''}")
    lines += _committee_block(row, eval_result, live)
    if armed:
        lines.append("U&R setup forming: " + _setup_text(armed)[0].lower() + _setup_text(armed)[1:])
    else:
        lines.append("U&R: no setup")
    default = " · AQE default criteria" if row.get("aqe_default") else ""
    return {"headline": f"{ticker}{px} · {label}{held}{default}", "color": color,
            "summary": None, "lines": lines}


def build_condition_card(ticker: str, row: dict, eval_result: dict,
                         fired_states: list[str], live: dict) -> dict:
    """Dispatch on config.CONDITION_CARD_STYLE ("compact" default / "full")."""
    from . import config as C
    if (C.CONDITION_CARD_STYLE or "compact") == "full":
        return _build_full_card(ticker, row, eval_result, fired_states, live)
    return _build_compact_card(ticker, row, eval_result, fired_states, live)


def _build_full_card(ticker: str, row: dict, eval_result: dict,
                     fired_states: list[str], live: dict) -> dict:
    """The previous long, word-by-word card. One card = {headline, color, summary, lines}. Line order (PM ask,
    2026-10-03): the one-sentence summary, each committee word as its own
    'Category: ✓/✗/◌ — plain' line, the Analysts ✓/✗ line, the live
    volume/VWAP numbers, chase/exit lines, the bracket, entry readiness."""
    primary = fired_states[0]
    label, color = _state_label(primary, row, eval_result, live)
    lit, n_counting = eval_result.get("lit") or [], eval_result.get("n_counting") or 0
    spot = live.get("price")
    at = f" @ {spot:.2f}" if spot is not None else ""
    headline = f"{ticker}{at} · {label}"
    if primary == "CONDITION_MET" and n_counting:
        headline += f" · {len(lit)} of {n_counting} analysts"
    if row.get("aqe_default"):
        # Said on every such card: these are AQE's own default criteria
        # (condition_defaults.py), not committee words.
        headline += " · AQE default criteria"

    lines: list[str] = []
    spot_line = _spot_line(row, live)
    if spot_line:
        lines.append(spot_line)
    lines += _condition_lines(eval_result.get("shared_buy_detail") or [])
    lines += _condition_lines(eval_result.get("shared_confirm_detail") or [])
    analysts = _analysts_line(eval_result)
    if analysts:
        lines.append(analysts)
    lines += [f"  {v}" for v in _voice_lines(row, eval_result)]

    vol_x = (live.get("vol_x") or {}).get("so_far")
    if vol_x is not None:
        lines.append(f"Live: volume {vol_x:.1f}× normal for the time of day.")
    vwap_info = live.get("vwap") or {}
    if vwap_info.get("vwap") is not None and not vwap_info.get("provisional"):
        h1 = live.get("last_hourly_close")
        side = "Above" if (h1 is not None and h1 > vwap_info["vwap"]) else "Below"
        lines.append(f"Live: {side} today's VWAP {vwap_info['vwap']:.2f}.")
    lines += _ema_lines(live)
    lines += _session_lines(live)
    # Live Elder (PM 2026-10-04): the nightly 0-10 score re-run with the
    # live price as today's close -- provisional until the bell, so it is
    # shown beside the last completed session's own score.
    el = live.get("elder") or {}
    if el.get("elder_live") is not None:
        prev = (f" — {el['elder_prev']} at last close" if el.get("elder_prev") is not None else "")
        arrow = ""
        if el.get("elder_prev") is not None:
            d = el["elder_live"] - el["elder_prev"]
            arrow = " ▲" if d > 0 else (" ▼" if d < 0 else " =")
        lines.append(f"Live: Elder impulse {el['elder_live']}/10 {el.get('impulse_live') or ''}"
                     f"{arrow} (provisional){prev}.")

    shared = (row.get("conditions") or {}).get("shared") or {}
    chase = shared.get("chase")
    if chase and chase.get("plain"):
        lines.append(f"Chase line: {chase['plain']}.")
    # exit_hit = a DAILY close below the committee's exit level (the §5
    # definition of the exit actually being hit); exit_warn = only an
    # HOURLY close below it so far. Said in words -- the headline's
    # held/not-held split is a different axis and must not be read as this.
    if eval_result.get("exit_hit") and eval_result["exit_hit"].get("plain"):
        lines.append(f"Exit line: {eval_result['exit_hit']['plain']} — "
                     "DAILY close below it (confirmed).")
    elif eval_result.get("exit_warn") and eval_result["exit_warn"].get("plain"):
        lines.append(f"Exit line: {eval_result['exit_warn']['plain']} — "
                     "hourly close below it, not yet a daily close.")

    lines += _bracket_line(row)
    # A pure exit-only row (no shared buy words, no analysts) is a HELD
    # position with nothing prospective to enter -- "Entry readiness:
    # WATCHING" on an EXIT LINE notice would misname what's actually going
    # on. Shown only when the row carries an actual entry side to read.
    has_entry_side = bool(shared.get("buy")) or bool(
        (row.get("conditions") or {}).get("analysts"))
    if has_entry_side:
        lines.append(_entry_readiness_line(primary, eval_result))

    return {"headline": headline, "color": color,
            "summary": _card_summary(primary, row, eval_result, live), "lines": lines}


def _card_plain(card: dict) -> str:
    head = card["headline"] + (f"\n{card['summary']}" if card.get("summary") else "")
    return head + "\n" + "\n".join(f"- {s}" for s in card["lines"])


def _card_html(card: dict) -> str:
    summary = (f"<div style='font-size:13px;margin-top:2px;color:#444'>"
               f"<i>{card['summary']}</i></div>" if card.get("summary") else "")
    return (f"<div style='border-left:4px solid {card['color']};padding:8px 12px;"
            f"background:#fafafa;border-radius:6px;color:#1a1a1a;margin-bottom:10px'>"
            f"<b style='font-size:15px'>{card['headline']}</b>{summary}"
            + "".join(f"<div style='font-size:13px;margin-top:3px'>{s}</div>"
                      for s in card["lines"])
            + "</div>")


def build_condition_state_body(ticker: str, row: dict, eval_result: dict,
                               fired_states: list[str], live: dict) -> tuple[str, str, str]:
    """(subject, plain, html) for ONE card as a standalone notice — kept so
    a single card stays unit-testable on its own; the live path sends
    `build_condition_digest` (one email per 15-min cycle)."""
    card = build_condition_card(ticker, row, eval_result, fired_states, live)
    subject = f"[AQE] {card['headline']}"
    plain = _card_plain(card) + f"\n\n{_DISCLAIMER}"
    html = (_card_html(card)
            + f"<div style='font-size:11px;color:#999;margin-top:6px'>{_DISCLAIMER}</div>")
    return subject, plain, html


_HELD_HEAD = {
    "near_stop": ("🟠 NEAR YOUR STOP — HELD POSITION", "#d9a441"),
    "near_target": ("🟢 NEAR FIRST TARGET — HELD POSITION", "#0a8a3a"),
    "exit_cross": ("🔴 COMMITTEE EXIT LINE — HELD POSITION", "#d00"),
    "veto": ("🔴 QS VETO — HELD POSITION", "#d00"),
    "order": ("🔴 STOP ORDER CHECK — HELD POSITION", "#d00"),
    "other": ("🟠 HELD POSITION", "#d9a441"),
}


def _held_kind(ev: dict) -> str:
    lvl, kind = ev.get("level") or "", ev.get("kind") or ""
    if lvl == "NEAR_STOP" or kind == "near_stops":
        return "near_stop"
    if lvl == "NEAR_TARGET" or kind == "approaching_target":
        return "near_target"
    if lvl == "VETO_HELD":
        return "veto"
    if kind in ("close_below", "trade_below"):
        return "exit_cross"
    if kind in ("no_stop_order", "order_config"):
        return "order"
    return "other"


def build_held_card(ev: dict) -> dict:
    """One held-position event as a card, same {headline, color, summary,
    lines} shape as a condition card so both ride ONE digest (PM 2026-10-06:
    held names must stay monitored, inside the single card mail -- not a
    second email). `ev` is an engine/PMA trigger dict for a HELD name; every
    number on the card comes from it, nothing is recomputed or invented.
    A fact about a position, never an instruction."""
    k = _held_kind(ev)
    label, color = _HELD_HEAD[k]
    px = ev.get("live_px")
    at = f" @ {px:.2f}" if px is not None else ""
    headline = f"{ev.get('ticker')}{at} · {label}"

    lines: list[str] = []
    chg = ev.get("chg_pct")
    if px is not None:
        lines.append(f"Spot {px:.2f}" + (f" · {chg:+.1f}% on the day" if chg is not None else ""))

    def _gap_above(level):  # % spot sits above a level
        return (px / level - 1.0) * 100.0 if (px and level) else None

    b_stop, c_exit = ev.get("broker_stop"), ev.get("committee_exit")
    lp = ev.get("level_price")
    summary = None
    if k == "near_stop":
        stop_lv = b_stop if b_stop is not None else lp
        if stop_lv is not None:
            g = _gap_above(stop_lv)
            tail = f" — spot is {g:.1f}% above it" if g is not None else ""
            lines.append(f"Your stop: {stop_lv:.2f}{tail}")
        if c_exit is not None:
            g = _gap_above(c_exit)
            tail = (f" — spot is {abs(g):.1f}% {'above' if g >= 0 else 'below'} it"
                    if g is not None else "")
            lines.append(f"Committee exit: {c_exit:.2f}{tail}")
        summary = "Price is close to a stop on a position you hold."
    elif k == "near_target":
        if lp is not None:
            g = (1 - px / lp) * 100.0 if px else None
            lines.append(f"First target: {lp:.2f}" + (f" — {g:.1f}% away" if g is not None else ""))
        summary = "Price is close to the first target on a position you hold."
    elif k == "exit_cross":
        daily = ev.get("priority") != "WARN"
        if lp is not None:
            lines.append(f"Committee exit line: {lp:.2f} — "
                         + ("DAILY close below it (confirmed)" if daily
                            else "beyond the line intraday, confirms only on the close"))
        if b_stop is not None:
            lines.append(f"Your broker stop: {b_stop:.2f}")
        summary = ("A daily close under the committee's exit line on a position you hold."
                   if daily else
                   "Price is through the committee's exit line intraday on a position you hold.")
    elif k == "veto":
        summary = ev.get("note") or "A QS veto fired on a position you hold."
    elif k == "order":
        summary = ev.get("action") or ev.get("note")
    else:
        summary = ev.get("action") or ev.get("note")

    action = (ev.get("action") or "").strip()
    if action and action != summary and k in ("near_stop", "exit_cross", "near_target"):
        lines.append(action)
    return {"headline": headline, "color": color, "summary": summary, "lines": lines}


def build_condition_digest(cards: list[tuple], now_et,
                           held_events: list[dict] | None = None) -> tuple[str, str, str]:
    """ONE email per 15-min cycle (PM 2026-10-03: no per-ticker alerts).
    `cards` = [(ticker, row, eval_result, fired_states, live), ...] — every
    name whose state changed this cycle, each rendered as its own card
    under one subject and one footer."""
    from . import config as C
    held_events = held_events or []
    compact = (C.CONDITION_CARD_STYLE or "compact") != "full"
    # A name that is ONLY a U&R candidate (no trigger, no buy/exit state) is one
    # line, not a card -- 16 candidates at the open must not be 16 cards.
    rows = [c for c in cards if compact and c[3] == ["UNR_ARMED"]]
    full = [c for c in cards if c not in rows]
    rank = {"UNR_TRIGGER": 0, "UNR_FAILED": 1}
    full.sort(key=lambda c: min(rank.get(x, 2) for x in c[3]))
    built = [build_condition_card(*c) for c in full]
    counts: dict[str, int] = {}
    for _t, _r, _e, states, _l in cards:
        key = _DIGEST_SHORT.get(states[0], states[0])
        counts[key] = counts.get(key, 0) + 1
    # Held-position events ride the SAME mail, after the condition cards.
    built += [build_held_card(ev) for ev in held_events]
    if held_events:
        counts["HELD"] = len(held_events)
    tally = " · ".join(f"{k} {v}" for k, v in counts.items())
    stamp = now_et.strftime("%H:%M ET")
    n = len(cards) + len(held_events)
    subject = f"[AQE] {stamp} conditions · {n} card{'s' if n != 1 else ''} · {tally}"
    header = f"{stamp} · {n} name{'s' if n != 1 else ''} changed state this cycle"

    row_text = [_candidate_row(c) for c in rows]
    rows_head = (f"U&R setups forming ({len(rows)}) — entry signal = a 15-min candle closing above VWAP"
                 if rows else "")
    plain = (header + "\n\n" + "\n\n".join(_card_plain(c) for c in built)
             + (("\n\n" if built else "") + rows_head + "\n" + "\n".join(f"- {t}" for t in row_text)
                if rows else "")
             + f"\n\n{_DISCLAIMER}")
    html = (f"<div style='font-size:12px;color:#666;margin-bottom:8px'>{header}</div>"
            + "".join(_card_html(c) for c in built)
            + ((f"<div style='border-left:4px solid #b8860b;padding:8px 12px;background:#fafafa;"
                f"border-radius:6px;color:#1a1a1a;margin-bottom:10px'><b style='font-size:14px'>"
                f"{rows_head}</b>"
                + "".join(f"<div style='font-size:13px;margin-top:3px'>{t}</div>" for t in row_text)
                + "</div>") if rows else "")
            + f"<div style='font-size:11px;color:#999;margin-top:4px'>{_DISCLAIMER}</div>")
    return subject, plain, html


def _candidate_row(c: tuple) -> str:
    """One plain line for a name that is only a setup forming."""
    ticker, _row, _ev, _states, live = c
    unr, spot = live.get("unr") or {}, live.get("price")
    px = f" ${spot:.2f}" if spot is not None else ""
    armed = unr.get("armed") or []
    if armed:
        a0 = armed[0]
        state = "back above it ✓" if a0.get("reclaimed") else "still under it"
        what = f"dipped below the {_plain_level(a0['name'])} ({a0['level']:.2f}), {state}"
    else:
        what = "dipped below a support level"
    stop = f"; stop would be {unr['stop']:.2f}" if unr.get("stop") is not None else ""
    return f"🟡 {ticker}{px} — {what}{stop}{_committee_tag(c[1], c[2])}"


def send_condition_digest(cards: list[tuple], now_et,
                          held_events: list[dict] | None = None) -> dict:
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend configured"}
    if not cards and not held_events:
        return {"ok": False, "reason": "no cards this cycle"}
    subject, plain, html = build_condition_digest(cards, now_et, held_events)
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
