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
_SECTIONS = [
    ("BUY_ZONE", "🟢 Hit buy price / buy zone", "#0a8a3a"),
    ("BREAKOUT", "🚀 Breakout (fresh)", "#0a66cc"),
    ("NEAR_STOP", "🛑 Approaching stop", "#d33"),
]


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
    for tier in ("held_positions", "edge_list", "top_picks", "longlist", "watchlist"):
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


def _aic_line(tk: str, rec: dict, t: dict) -> str:
    g = rec.get
    base = (f"AIC — {tk} ({'HELD' if t['is_held'] else t.get('source')}): "
            f"{t['label']} @ live {t['live_px']}. "
            f"SC {_fmt(g('sc_momentum'), 1)}/raw {_fmt(g('sc_momentum_raw'), 1)} · "
            f"PTRS {_fmt(g('ptrs'), 1)} · MP {g('mp_state') or '—'} · "
            f"Flow {_fmt(g('flow'), 0)} En {_fmt(g('energy'), 0)} "
            f"St {_fmt(g('structure'), 0)} MP {_fmt(g('mp'), 0)} Eld {_fmt(g('elder'), 1)} · "
            f"DSL stop {_fmt(g('dsl_stop'))} buy {_fmt(g('dsl_be'))} "
            f"TP {_fmt(g('dsl_tp_1r'))}/{_fmt(g('dsl_tp_2r'))}/{_fmt(g('dsl_tp_3r'))} "
            f"(rr_est {_fmt(g('rr_est'), 2)}) · β {_fmt(g('beta_30d'), 2)} · "
            f"sector {g('gics_sector') or '—'} {g('gics_gate') or '—'}.")
    if t["is_held"]:
        base += (f" Trade: entry {_fmt(g('entry'))} qty {g('qty')} "
                 f"SL {_fmt(g('held_sl'))} unreal ${_fmt(g('unreal_usd'), 0)}. "
                 "Advise hold / trim / stop mgmt.")
    else:
        base += " Advise entry decision + size per PTRS × regime. Charter v1.9.2."
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
    subject = (f"[AQE] {len({t['ticker'] for t in triggers})} names · "
               f"{counts['BUY_ZONE']} buy · {counts['BREAKOUT']} breakout · "
               f"{counts['NEAR_STOP']} near-stop"
               + (f" · {len(held)} HELD" if held else ""))

    # ---- plain text ----
    tl = [f"AQE Trade Entry — {now_sgt} · export {exp_date} · regime {regime_txt or '—'}",
          f"{n} alert(s). Prices 15-min delayed. Sorted by SC_MOM within each group.", ""]

    def _line(t):
        rec = rl.get(t["ticker"], {})
        tag = "★HELD" if t["is_held"] else (t.get("source") or "")
        return (f"  {t['ticker']:6} [{tag}] SC {_fmt(rec.get('sc_momentum_raw') or rec.get('sc_momentum'), 1)} "
                f"PTRS {_fmt(rec.get('ptrs'), 1)} {rec.get('mp_state') or ''} · "
                f"live {t['live_px']} · {t['note']}\n      {_aic_line(t['ticker'], rec, t)}")

    if held:
        tl.append(f"★ HELD ({len(held)})")
        tl += [_line(t) for t in held]
        tl.append("")
    for key, title, _ in _SECTIONS:
        if by_type[key]:
            tl.append(f"{title} ({len(by_type[key])})")
            tl += [_line(t) for t in by_type[key]]
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
            f"<span style='color:#555;font-size:12px'>SC {sc} · PTRS {_fmt(rec.get('ptrs'),1)} "
            f"· {rec.get('mp_state') or '—'} · β {_fmt(rec.get('beta_30d'),2)}</span></div>"
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


def send_digest(triggers: list[dict], export: dict) -> dict:
    """Send the digest. Resend if its key is set, else Gmail SMTP. Never raises."""
    cfg = _cfg()
    if not (cfg["resend_key"] or cfg["smtp_pw"]):
        return {"ok": False, "reason": "no email backend (set RESEND_API_KEY or AQE_SMTP_PASSWORD)"}
    if not triggers:
        return {"ok": False, "reason": "no triggers"}
    subject, plain, html = _build_bodies(triggers, export)
    if cfg["resend_key"]:
        return _send_resend(cfg, subject, plain, html)
    return _send_smtp(cfg, subject, plain, html)


def send_test() -> dict:
    """Fire a one-off test digest so the PM can verify the email backend."""
    sample = [
        {"ticker": "TEST1", "source": "longlist", "is_held": False,
         "level": "BUY_ZONE", "label": "Hit buy price / in buy zone",
         "level_price": 101.5, "live_px": 100.8, "note": "at/under buy 101.50"},
        {"ticker": "ODFL", "source": "held", "is_held": True,
         "level": "NEAR_STOP", "label": "Approaching stop (SL)",
         "level_price": 230.0, "live_px": 235.0, "note": "2.2% above stop 230.00"},
    ]
    export = {"date": "TEST", "regime": {"level": "TEST"},
              "longlist": [{"ticker": "TEST1", "sc_momentum": 78, "sc_momentum_raw": 78,
                            "ptrs": 64, "mp_state": "STRONG", "flow": 82, "energy": 70,
                            "structure": 62, "mp": 60, "elder": 8, "beta_30d": 1.4,
                            "dsl_stop": 95, "dsl_be": 101.5, "dsl_tp_1r": 103,
                            "dsl_tp_2r": 106, "dsl_tp_3r": 109, "rr_est": 2.1,
                            "gics_sector": "XLK", "gics_gate": "PASS"}],
              "held_positions": [{"ticker": "ODFL", "sc_momentum": 62, "ptrs": 58,
                                  "mp_state": "BUILDING", "entry": 239.45, "qty": 65,
                                  "held_sl": 230, "unreal_usd": 317, "beta_30d": 1.17,
                                  "dsl_stop": 228, "dsl_be": 240}]}
    return send_digest(sample, export)
