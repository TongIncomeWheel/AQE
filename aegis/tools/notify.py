#!/usr/bin/env python3
"""
notify.py — the Aegis notification emitter (D-45).

One tool, one job: turn an operational event into a clear, one-way phone ping.
Nothing else in the kernel talks to the notification channel.

Doctrine (constitution v4.1):
  - Law 1 (execution boundary): this tool is ORDER-BLIND by construction. It
    places, sizes, arms nothing. It only sends text and checks in with the
    external watchdog.
  - Law 3 (read, never invent) / Failure rule: if a send fails, it SAYS so and
    returns a failed status — it never pretends a ping was delivered.
  - Law 4 (code computes): message construction is deterministic here; no model.

CHANNEL (D-46): the default channel is **cowork** — the PILOT runs on Claude
Cowork, where the emitted message IS the session's output and the scheduled
task's own push notification delivers it to the PM's phone. No third-party
service, nothing to configure. This is the intended pilot path, not a fallback.
The WhatsApp channel and the external watchdog are the POST-MIGRATION (local
box / Kimi) path and are OFF until `AEGIS_NOTIFY_CHANNEL=whatsapp` is set — do
NOT wire them for the Cowork pilot.

Channels (env, never a tracked file — see config/env.example):
  - cowork (default) → message printed as session output → Cowork native push
  - whatsapp (post-migration) → WHATSAPP_* / TWILIO_* env
  - watchdog (post-migration) → WATCHDOG_URL env (e.g. healthchecks.io)

The FAILURE template is deliberately unlike every other message so a page that
matters is never mistaken for a routine green ping (PM ruling, D-45).

CLI:
  notify.py pre_run  --loop premarket --at "16:00 SGT" [--dashboard URL]
  notify.py run_ok   --loop premarket --summary "plan shelved, 4 advanced"
  notify.py run_fail --loop premarket --step "risk-gate check" --last-good "post-market 04:07"
  notify.py healed   --loop post-market --summary "PTJ repull succeeded on attempt 2"
  notify.py alert    --summary "VaR 16.3% of dynCap — under 18% soft cap"
  notify.py --checkin ok            # tell the watchdog we are alive
  notify.py --checkin fail
Add --dry-run (or leave the channel unconfigured) to render without sending.
"""

import os
import sys
import json
import argparse

KINDS = ("pre_run", "run_ok", "run_fail", "healed", "alert")


# ---- message construction (deterministic, law 4) --------------------------

def build(kind, fields):
    """Return (title, body) for a notification kind. Pure string work."""
    loop = fields.get("loop", "system")
    dash = fields.get("dashboard") or fields.get("dashboard_url")
    tail = f"\nOpen: {dash}" if dash else ""

    if kind == "pre_run":
        at = fields.get("at", "soon")
        lastgood = fields.get("last_good")
        lg = f"\nLast run: {lastgood} ✓" if lastgood else ""
        return ("Aegis — heartbeat",
                f"✓ Aegis — {loop} starts in 15 min ({at}). System alive.{lg}{tail}")

    if kind == "run_ok":
        summ = fields.get("summary", "completed clean")
        return ("Aegis — run ok",
                f"✓ Aegis — {loop} ✓  {summ}{tail}")

    if kind == "healed":
        summ = fields.get("summary", "self-healed")
        return ("Aegis — self-healed",
                f"⚠→✓ Aegis self-heal — {loop}: {summ}. No action needed.{tail}")

    if kind == "alert":
        summ = fields.get("summary", "see dashboard")
        return ("Aegis — alert",
                f"▲ Aegis — {summ}{tail}")

    if kind == "run_fail":
        # Deliberately unmistakable (D-45): red, shouty, states the stand-down.
        step = fields.get("step", "an unknown step")
        lastgood = fields.get("last_good", "n/a")
        stand = fields.get("stand_down", "No orders placed — system stood down.")
        return ("AEGIS FAILURE",
                f"🔴 AEGIS FAILURE — {loop} did NOT complete.\n"
                f"Stopped at: {step}. {stand}\n"
                f"Last good run: {lastgood}.{tail}")

    raise ValueError(f"unknown kind: {kind!r} (expected one of {KINDS})")


# ---- channel: WhatsApp one-way (optional) ---------------------------------

def _whatsapp_config():
    """Read channel config from env only. Returns dict or None if unconfigured."""
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")
    to = os.environ.get("WHATSAPP_TO")
    if token and phone_id and to:
        return {"provider": "meta", "token": token, "phone_id": phone_id, "to": to}
    # Twilio-style fallback
    sid = os.environ.get("TWILIO_SID")
    tok = os.environ.get("TWILIO_TOKEN")
    frm = os.environ.get("TWILIO_WHATSAPP_FROM")
    if sid and tok and frm and to:
        return {"provider": "twilio", "sid": sid, "token": tok, "from": frm, "to": to}
    return None


def _channel():
    """Default 'cowork' (pilot). 'whatsapp' is the post-migration local path."""
    return os.environ.get("AEGIS_NOTIFY_CHANNEL", "cowork").lower()


def send(kind, fields, dry_run=False):
    """
    Build and send a notification. Returns a status dict; never raises on a
    delivery problem — it reports it (Failure rule).
    """
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown kind {kind!r}"}
    title, body = build(kind, fields)
    channel = _channel()

    if dry_run:
        print(f"[notify:{kind}] dry-run ({channel})\n{body}\n")
        return {"ok": True, "sent": False, "kind": kind, "title": title,
                "body": body, "channel": channel, "reason": "dry-run"}

    if channel == "cowork":
        # PILOT path: the printed message is the Cowork session's output; the
        # scheduled task's push notification carries it to the PM's phone. This
        # is delivery, not a fallback — no external service is involved.
        print(f"[notify:{kind}] (cowork-native push)\n{body}\n")
        return {"ok": True, "sent": True, "via": "cowork-push", "kind": kind,
                "title": title, "body": body, "channel": "cowork"}

    # channel == "whatsapp" — POST-MIGRATION local path only.
    cfg = _whatsapp_config()
    if cfg is None:
        print(f"[notify:{kind}] whatsapp channel selected but WHATSAPP_*/TWILIO_* unset — printed only\n{body}\n")
        return {"ok": True, "sent": False, "kind": kind, "body": body,
                "channel": "whatsapp", "reason": "whatsapp unconfigured"}
    try:
        import requests  # deferred; only needed when actually sending
        if cfg["provider"] == "meta":
            url = f"https://graph.facebook.com/v20.0/{cfg['phone_id']}/messages"
            r = requests.post(url, timeout=15,
                              headers={"Authorization": f"Bearer {cfg['token']}"},
                              json={"messaging_product": "whatsapp", "to": cfg["to"],
                                    "type": "text", "text": {"body": body}})
        else:  # twilio
            url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
            r = requests.post(url, timeout=15, auth=(cfg["sid"], cfg["token"]),
                              data={"From": cfg["from"], "To": cfg["to"], "Body": body})
        ok = 200 <= r.status_code < 300
        if not ok:
            print(f"[notify:{kind}] SEND FAILED http {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return {"ok": ok, "sent": ok, "kind": kind, "http": r.status_code, "body": body}
    except Exception as e:  # never fabricate success
        print(f"[notify:{kind}] SEND ERROR: {e}", file=sys.stderr)
        return {"ok": False, "sent": False, "kind": kind, "error": str(e), "body": body}


# ---- channel: external dead-man's-switch (optional) -----------------------

def checkin(status="ok"):
    """
    POST-MIGRATION (local box) only: ping the external watchdog so the ABSENCE
    of a check-in becomes the alarm if the box dies. Not used in the Cowork
    pilot (Anthropic runs the infra; liveness comes from the scheduled tasks'
    native completion pushes). No-op with a printed note if WATCHDOG_URL is unset.
    """
    base = os.environ.get("WATCHDOG_URL")
    if not base:
        print("[notify:checkin] WATCHDOG_URL unset — skipped")
        return {"ok": True, "sent": False, "reason": "unconfigured"}
    url = base if status == "ok" else base.rstrip("/") + "/fail"
    try:
        import requests
        r = requests.get(url, timeout=10)
        return {"ok": 200 <= r.status_code < 300, "sent": True, "http": r.status_code}
    except Exception as e:
        print(f"[notify:checkin] ERROR: {e}", file=sys.stderr)
        return {"ok": False, "sent": False, "error": str(e)}


# ---- CLI ------------------------------------------------------------------

def _main(argv=None):
    p = argparse.ArgumentParser(description="Aegis notification emitter (order-blind, D-45)")
    p.add_argument("kind", nargs="?", choices=KINDS)
    p.add_argument("--loop"); p.add_argument("--at"); p.add_argument("--summary")
    p.add_argument("--step"); p.add_argument("--last-good", dest="last_good")
    p.add_argument("--stand-down", dest="stand_down"); p.add_argument("--dashboard")
    p.add_argument("--checkin", choices=("ok", "fail"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    if a.checkin:
        print(json.dumps(checkin(a.checkin), indent=2)); return
    if not a.kind:
        p.error("give a kind or --checkin")
    fields = {k: v for k, v in vars(a).items()
              if k in ("loop", "at", "summary", "step", "last_good", "stand_down", "dashboard") and v}
    print(json.dumps(send(a.kind, fields, dry_run=a.dry_run), indent=2))


if __name__ == "__main__":
    _main()
