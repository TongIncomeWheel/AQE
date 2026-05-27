"""Telegram delivery client -- pushes briefs + alerts to PM.

Per spec §14.26: Standard Telegram Bot API. `sendMessage` with HTML parse_mode
for bold/italic. Retry 3x at 30s intervals on transient failure; on persistent
failure, log to local alert log and surface on next dashboard open.

This module is import-safe even without credentials -- the actual send is
gated on `is_subsystem_ready("telegram")`. If credentials are missing, calls
are logged to stdout (and to the local alert log) but do not raise.

LIVE BEHAVIOUR depends on `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in
`src/aic/config/credentials.py` being populated by the PM.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import requests

from src.aic.config import get_credential, is_subsystem_ready


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALERT_LOG = PROJECT_ROOT / "src" / "aic" / "state" / "telegram_alerts.log.jsonl"

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 10


def _log_alert(payload: dict) -> None:
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({**payload,
                            "logged_at": datetime.now().isoformat(timespec="seconds")}) + "\n")


def send_message(
    text: str,
    *,
    priority: str = "normal",       # normal | high | critical (per spec §14.26)
    parse_mode: str = "HTML",
) -> dict:
    """Send a Telegram message. Returns {ok: bool, status: ..., ...}.

    If credentials are not yet populated, the message is logged to
    `state/telegram_alerts.log.jsonl` and a non-raising result is returned
    so the rest of the scheduler keeps running.
    """
    payload = {"text": text, "priority": priority, "parse_mode": parse_mode}

    if not is_subsystem_ready("telegram"):
        _log_alert({**payload, "delivery": "skipped (credentials missing)"})
        return {"ok": False, "status": "credentials_missing"}

    bot = get_credential("TELEGRAM_BOT_TOKEN")
    chat = get_credential("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot}/sendMessage"
    data = {"chat_id": chat, "text": text, "parse_mode": parse_mode}

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(url, data=data, timeout=HTTP_TIMEOUT_SECONDS)
            if r.ok:
                return {"ok": True, "status": r.status_code, "telegram": r.json()}
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:                              # noqa: BLE001
            last_err = e
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SLEEP_SECONDS)

    _log_alert({**payload, "delivery": f"failed after {MAX_RETRIES} attempts", "error": str(last_err)})
    return {"ok": False, "status": "failed", "error": str(last_err)}
