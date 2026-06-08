"""Gmail-SMTP digest emailer for the live alert engine.

One email per poll cycle, grouped by ticker. Each ticker section shows the live
AQE engine read AND a ready-to-paste "engage AIC via Claude" prompt — the PM's
2-system feedback loop (AQE pings the level; the PM takes the prompt to the AIC
committee via Claude). No AI is built into AQE itself.

Secrets (HF + GitHub):
    AQE_SMTP_USER       sender Gmail address       (default ash.tzl@gmail.com)
    AQE_SMTP_PASSWORD   Gmail App Password (16 ch)  REQUIRED — no password, no send
    AQE_ALERT_TO        recipient                   (default = AQE_SMTP_USER)
    AQE_SMTP_HOST/PORT  override                     (default smtp.gmail.com:465)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

DEFAULT_USER = "ash.tzl@gmail.com"


def _cfg() -> dict:
    user = os.environ.get("AQE_SMTP_USER") or DEFAULT_USER
    # Gmail shows App Passwords as "abcd efgh ijkl mnop" — strip spaces so a
    # verbatim paste still authenticates.
    pw = os.environ.get("AQE_SMTP_PASSWORD")
    if pw:
        pw = pw.replace(" ", "").strip()
    return {
        "user": user,
        "password": pw or None,
        "to": os.environ.get("AQE_ALERT_TO") or user,
        "host": os.environ.get("AQE_SMTP_HOST") or "smtp.gmail.com",
        "port": int(os.environ.get("AQE_SMTP_PORT") or 465),
    }


def is_configured() -> bool:
    return bool(_cfg()["password"])


def _fmt(v, dp=2):
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "—"


def _aic_prompt(tk: str, source: str, is_held: bool, rec: dict,
                levels: list[dict], live: float) -> str:
    """The copy-paste block the PM hands to the AIC via Claude."""
    hit = ", ".join(f"{t['label']}" for t in levels)
    g = rec.get
    lines = [
        f"AIC — {tk} ({'HELD' if is_held else source}) live alert.",
        f"Levels hit: {hit}. Live 15-min px {_fmt(live)}.",
        (f"AQE read: SC_MOM {_fmt(g('sc_momentum'), 1)} | PTRS {_fmt(g('ptrs'), 1)} "
         f"| MP {g('mp_state') or '—'} | Flow {_fmt(g('flow'), 0)} "
         f"Energy {_fmt(g('energy'), 0)} Struct {_fmt(g('structure'), 0)} "
         f"MP {_fmt(g('mp'), 0)} | Elder {_fmt(g('elder'), 1)} "
         f"| RVol {_fmt(g('rvol'), 1)} | RS20 {_fmt(g('rs_spy_20d'), 1)}."),
        (f"Sector {g('gics_sector') or '—'} gate {g('gics_gate') or '—'} "
         f"(corr {_fmt(g('sector_corr'), 2)}/{g('sector_corr_class') or '—'}) "
         f"| β30 {_fmt(g('beta_30d'), 2)} β60 {_fmt(g('beta_60d'), 2)}."),
        (f"DSL: stop {_fmt(g('dsl_stop'))} BE {_fmt(g('dsl_be'))} "
         f"1R {_fmt(g('dsl_risk'))} | TP {_fmt(g('dsl_tp_1r'))}/"
         f"{_fmt(g('dsl_tp_2r'))}/{_fmt(g('dsl_tp_3r'))}."),
    ]
    if is_held:
        lines.append(
            f"Trade: entry {_fmt(g('entry'))} qty {g('qty')} "
            f"SL {_fmt(g('held_sl'))} TP {_fmt(g('held_tp1'))}/{_fmt(g('held_tp2'))} "
            f"unreal ${_fmt(g('unreal_usd'), 0)}.")
        ask = "Advise: hold / trim / stop management given the level hit."
    else:
        ask = "Advise: entry decision + size per PTRS × regime."
    lines.append(f"Charter v1.9.2. {ask}")
    return "\n".join(lines)


def _build_bodies(triggers: list[dict], export: dict) -> tuple[str, str]:
    """Return (plain_text, html) for the digest."""
    # ticker -> record lookup across all tiers + held
    rec_lookup: dict[str, dict] = {}
    for tier in ("held_positions", "edge_list", "top_picks", "longlist", "watchlist"):
        for r in export.get(tier) or []:
            rec_lookup.setdefault(r.get("ticker"), r)

    # group triggers by ticker, preserving order of first appearance
    by_tk: dict[str, list[dict]] = {}
    for t in triggers:
        by_tk.setdefault(t["ticker"], []).append(t)

    now_sgt = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M SGT")
    regime = (export.get("regime") or {})
    regime_txt = regime.get("level") if isinstance(regime, dict) else regime

    txt = [f"AQE Trade Entry alerts — {now_sgt}  (regime: {regime_txt or '—'})",
           f"{len(by_tk)} ticker(s), {len(triggers)} new level(s). "
           f"Prices are 15-min delayed (FMP).", ""]
    html = [
        f"<h2>AQE Trade Entry alerts</h2>",
        f"<p><b>{now_sgt}</b> · regime <b>{regime_txt or '—'}</b> · "
        f"{len(by_tk)} ticker(s), {len(triggers)} new level(s) · "
        f"<i>prices 15-min delayed</i></p>",
    ]

    for tk, levels in by_tk.items():
        rec = rec_lookup.get(tk, {})
        is_held = bool(levels[0].get("is_held"))
        source = levels[0].get("source")
        live = levels[0].get("live_px")
        tag = "HELD" if is_held else source

        # plain text
        txt.append(f"━━ {tk}  [{tag}]  live {_fmt(live)} ━━")
        for t in levels:
            lp = f" @ {_fmt(t['level_price'])}" if t.get("level_price") is not None else ""
            txt.append(f"  • {t['label']}{lp} — {t['note']}")
        txt.append("")
        txt.append("  ▼ Engage AIC (copy-paste to Claude):")
        for ln in _aic_prompt(tk, source, is_held, rec, levels, live).splitlines():
            txt.append(f"  {ln}")
        txt.append("")

        # html
        rows = "".join(
            f"<li><b>{t['label']}</b>"
            f"{(' @ ' + _fmt(t['level_price'])) if t.get('level_price') is not None else ''}"
            f" — <span style='color:#555'>{t['note']}</span></li>"
            for t in levels
        )
        prompt = _aic_prompt(tk, source, is_held, rec, levels, live)
        color = "#b00" if is_held else "#06c"
        html.append(
            f"<div style='margin:14px 0;padding:10px;border-left:4px solid {color};"
            f"background:#fafafa'>"
            f"<h3 style='margin:0 0 4px'>{tk} "
            f"<span style='font-size:12px;color:{color}'>[{tag}]</span> "
            f"<span style='font-size:12px;color:#888'>live {_fmt(live)}</span></h3>"
            f"<ul style='margin:6px 0'>{rows}</ul>"
            f"<details open><summary style='cursor:pointer;color:{color}'>"
            f"Engage AIC (copy to Claude)</summary>"
            f"<pre style='white-space:pre-wrap;background:#f0f0f0;padding:8px;"
            f"font-size:12px;border-radius:4px'>{prompt}</pre></details></div>"
        )

    return "\n".join(txt), "\n".join(html)


def send_digest(triggers: list[dict], export: dict) -> dict:
    """Send the alert digest. Returns {ok, reason?}. Never raises."""
    cfg = _cfg()
    if not cfg["password"]:
        return {"ok": False, "reason": "AQE_SMTP_PASSWORD not set"}
    if not triggers:
        return {"ok": False, "reason": "no triggers"}

    n_tk = len({t["ticker"] for t in triggers})
    subject = f"[AQE] {n_tk} ticker(s) hit key levels — {len(triggers)} alert(s)"
    plain, html = _build_bodies(triggers, export)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=ctx) as s:
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["user"], [cfg["to"]], msg.as_string())
        return {"ok": True, "to": cfg["to"], "tickers": n_tk}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def send_test() -> dict:
    """Fire a one-off test email so the PM can verify SMTP setup from the UI."""
    sample = [{
        "ticker": "TEST", "source": "watchlist", "is_held": False,
        "level": "RVOL", "label": "RVol spike 2.5×", "level_price": None,
        "live_px": 100.0, "note": "this is a configuration test",
    }]
    export = {"regime": {"level": "TEST"}, "watchlist": [{
        "ticker": "TEST", "sc_momentum": 75, "ptrs": 60, "mp_state": "STRONG",
        "dsl_stop": 95, "dsl_be": 101.5, "dsl_risk": 3, "entry": 100,
    }]}
    return send_digest(sample, export)
