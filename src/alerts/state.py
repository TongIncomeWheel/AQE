"""Shared alert dedup state — one trigger fires at most once per trading day.

Both pollers (the in-app 15-min thread and the GitHub Actions backstop) read and
write the SAME state object so they don't double-email. Source of truth is a tiny
JSON on Drive (`aqe_alert_state.json` in the AQE folder); a local mirror in
`output/` is kept for offline/dev. last-writer-wins — at a 15-min cadence with the
two pollers offset, a collision can at worst send one duplicate, never miss one.

State shape: {"date": "YYYY-MM-DD" (US/Eastern), "fired": ["TICKER|LEVEL", ...]}.
On a new trading day the fired set resets automatically.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR

STATE_FILENAME = "aqe_alert_state.json"
LOCAL_STATE = OUTPUT_DIR / STATE_FILENAME
_ET = ZoneInfo("America/New_York")


def today_key() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def fired_key(ticker: str, level: str) -> str:
    return f"{ticker}|{level}"


def load_alert_state() -> dict:
    """Load the shared state — Drive first, then local mirror, then empty."""
    # Drive (shared source of truth)
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(STATE_FILENAME)
            if txt:
                return _ensure_today(json.loads(txt))
    except Exception:  # noqa: BLE001
        pass
    # Local mirror
    try:
        if LOCAL_STATE.exists():
            return _ensure_today(json.loads(LOCAL_STATE.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        pass
    return {"date": today_key(), "fired": []}


def save_alert_state(state: dict) -> None:
    """Persist to local mirror + Drive (both best-effort)."""
    payload = json.dumps(state, indent=2)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_STATE.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(STATE_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def _ensure_today(state: dict) -> dict:
    """Reset the fired set when the trading day rolls over."""
    if not isinstance(state, dict):
        return {"date": today_key(), "fired": []}
    if state.get("date") != today_key():
        return {"date": today_key(), "fired": []}
    state.setdefault("fired", [])
    return state


def is_fired(state: dict, ticker: str, level: str) -> bool:
    return fired_key(ticker, level) in set(state.get("fired") or [])


def mark_fired(state: dict, ticker: str, level: str) -> None:
    k = fired_key(ticker, level)
    if k not in (state.get("fired") or []):
        state.setdefault("fired", []).append(k)


# ---------------------------------------------------------------------------
# Alert history — a rolling log of every fired trigger (for the on-screen feed)
# ---------------------------------------------------------------------------

HISTORY_FILENAME = "aqe_alert_history.json"
LOCAL_HISTORY = OUTPUT_DIR / HISTORY_FILENAME
HISTORY_KEEP_HOURS = 24 * 7  # prune anything older than a week


def load_history() -> list[dict]:
    """Full alert history (newest entries last) — Drive first, then local."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(HISTORY_FILENAME)
            if txt:
                return json.loads(txt) or []
    except Exception:  # noqa: BLE001
        pass
    try:
        if LOCAL_HISTORY.exists():
            return json.loads(LOCAL_HISTORY.read_text(encoding="utf-8")) or []
    except Exception:  # noqa: BLE001
        pass
    return []


def append_history(triggers: list[dict]) -> None:
    """Append newly-fired triggers (timestamped) to the rolling history."""
    if not triggers:
        return
    now_utc = datetime.now(ZoneInfo("UTC"))
    now_sgt = now_utc.astimezone(ZoneInfo("Asia/Singapore"))
    stamped = []
    for t in triggers:
        e = dict(t)
        e["ts_utc"] = now_utc.isoformat(timespec="seconds")
        e["ts_sgt"] = now_sgt.strftime("%Y-%m-%d %H:%M SGT")
        stamped.append(e)

    hist = load_history()
    hist.extend(stamped)

    # Prune entries older than the keep window.
    cutoff = now_utc.timestamp() - HISTORY_KEEP_HOURS * 3600
    pruned = []
    for e in hist:
        try:
            ts = datetime.fromisoformat(e.get("ts_utc")).timestamp()
        except (TypeError, ValueError):
            ts = now_utc.timestamp()  # keep undated entries
        if ts >= cutoff:
            pruned.append(e)

    payload = json.dumps(pruned, indent=2)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_HISTORY.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(HISTORY_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def recent_history(hours: int = 36) -> list[dict]:
    """Triggers fired in the last `hours`, newest first."""
    cutoff = datetime.now(ZoneInfo("UTC")).timestamp() - hours * 3600
    out = []
    for e in load_history():
        try:
            ts = datetime.fromisoformat(e.get("ts_utc")).timestamp()
        except (TypeError, ValueError):
            continue
        if ts >= cutoff:
            out.append(e)
    out.sort(key=lambda e: e.get("ts_utc", ""), reverse=True)
    return out


# ---------------------------------------------------------------------------
# PMA fired state — a SEPARATE dedup set, deliberately NOT the daily-reset
# `fired` set above. A PMA trigger keeps the same id for as long as PMA
# carries the row (up to three sessions, R20.1), so it must alert at most
# once over that whole life, not once per calendar day. The AQE Handoff:
# PMA Live Alerts spec calls this "the life of a trigger."
#
# Shape: {"fired": ["ABBV-cond|close", "WEAT-nostop|2026-09-30", ...]}.
# No "date" field to reset on — pruning is driven entirely by
# `prune_pma_fired(state, live_ids)`, called once per cycle with the BASE
# ids (before any `|variant` suffix) still present in the day's PMA levels
# file. A key whose base id has left the file (the row retired, PASSed, or
# aged out) is dropped; every other key survives regardless of date, so a
# `no_stop_order`/`order_config` key deliberately keyed `id|session_date`
# (they must re-fire once EVERY session, not once ever) still gets pruned
# the day its row finally disappears, exactly like any other key.
# ---------------------------------------------------------------------------

PMA_STATE_FILENAME = "aqe_pma_fired.json"
LOCAL_PMA_STATE = OUTPUT_DIR / PMA_STATE_FILENAME


def load_pma_fired_state() -> dict:
    """Drive first, then local mirror, then empty — same idiom as
    `load_alert_state`, minus the daily reset."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(PMA_STATE_FILENAME)
            if txt:
                data = json.loads(txt)
                if isinstance(data, dict):
                    data.setdefault("fired", [])
                    return data
    except Exception:  # noqa: BLE001
        pass
    try:
        if LOCAL_PMA_STATE.exists():
            data = json.loads(LOCAL_PMA_STATE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("fired", [])
                return data
    except Exception:  # noqa: BLE001
        pass
    return {"fired": []}


def save_pma_fired_state(state: dict) -> None:
    payload = json.dumps(state, indent=2)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_PMA_STATE.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(PMA_STATE_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def is_pma_fired(state: dict, key: str) -> bool:
    return key in set(state.get("fired") or [])


def mark_pma_fired(state: dict, key: str) -> None:
    if key not in (state.get("fired") or []):
        state.setdefault("fired", []).append(key)


def prune_pma_fired(state: dict, live_base_ids: set[str]) -> int:
    """Drop every key whose BASE id (before any `|variant` suffix) is not in
    `live_base_ids` — the row has retired, PASSed, or aged out of the
    three-session window. Returns the number of keys pruned."""
    before = state.get("fired") or []
    kept = [k for k in before if k.split("|", 1)[0] in live_base_ids]
    state["fired"] = kept
    return len(before) - len(kept)


# ---------------------------------------------------------------------------
# Digest batching — a hard floor on email FREQUENCY, separate from trigger
# dedup above. A PM complaint (2026-10-01): alerts arrived too often, "once
# every 15 min in one email, not by individual ticker." The two pollers
# (in-app 15-min thread, GitHub Actions backstop) already dedup which
# TRIGGERS fire via the shared state above, but this module's own docstring
# admits the gap: "a collision can at worst send one duplicate" — last-
# writer-wins on a read-then-write race when both pollers land close
# together. This closes that gap WITHOUT the data-loss a naive "just skip
# the send" fix would cause: a trigger already marked fired above will never
# be evaluated again, so silently dropping its digest would lose it for
# good, the same "never silently empty" failure CLAUDE.md calls out for a
# failed data fetch.
#
# So every fresh trigger is appended to this shared PENDING queue FIRST,
# regardless of whether this cycle is allowed to send. A send is attempted
# only if MIN_DIGEST_GAP_MINUTES have passed since the last SUCCESSFUL send
# (tracked separately, below) — and when it is, it sends the FULL pending
# queue (this cycle's triggers plus anything accumulated from cycles that
# were gated), then clears it. A failed send leaves the queue intact for the
# next cycle to retry. Net effect: every trigger is still emailed exactly
# once, but never more often than the gap allows, and a cycle gated by the
# timer still folds its own content into the next email instead of an
# eleventh near-simultaneous one.
# ---------------------------------------------------------------------------

PENDING_DIGEST_FILENAME = "aqe_pending_digest.json"
LOCAL_PENDING_DIGEST = OUTPUT_DIR / PENDING_DIGEST_FILENAME
LAST_DIGEST_FILENAME = "aqe_last_digest_sent.json"
LOCAL_LAST_DIGEST = OUTPUT_DIR / LAST_DIGEST_FILENAME


def load_pending_digest() -> dict:
    """{"legacy": [...], "pma": [...]} — triggers already dedup'd (fired) but
    not yet emailed. Drive first, then local mirror, then empty."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(PENDING_DIGEST_FILENAME)
            if txt:
                data = json.loads(txt)
                if isinstance(data, dict):
                    data.setdefault("legacy", [])
                    data.setdefault("pma", [])
                    return data
    except Exception:  # noqa: BLE001
        pass
    try:
        if LOCAL_PENDING_DIGEST.exists():
            data = json.loads(LOCAL_PENDING_DIGEST.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("legacy", [])
                data.setdefault("pma", [])
                return data
    except Exception:  # noqa: BLE001
        pass
    return {"legacy": [], "pma": []}


def save_pending_digest(pending: dict) -> None:
    payload = json.dumps(pending, indent=2, default=str)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_PENDING_DIGEST.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(PENDING_DIGEST_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def append_pending_digest(legacy: list[dict], pma: list[dict]) -> dict:
    """Merge this cycle's fresh triggers into the shared pending queue (by
    `level`, the same dedup key already used to fire them — so a trigger
    present in both the queue and this cycle, which should not happen but
    costs nothing to guard, is never double-listed) and persist it.
    Returns the merged queue."""
    pending = load_pending_digest()
    for bucket, new_items in (("legacy", legacy), ("pma", pma)):
        seen = {t.get("level") for t in pending[bucket]}
        for t in new_items or []:
            if t.get("level") not in seen:
                pending[bucket].append(t)
                seen.add(t.get("level"))
    save_pending_digest(pending)
    return pending


def clear_pending_digest() -> None:
    save_pending_digest({"legacy": [], "pma": []})


def load_last_digest_sent() -> datetime | None:
    """UTC timestamp of the last SUCCESSFUL digest send, or None if there
    has never been one (or today's hasn't reset — see `seconds_since_last_
    digest`, which treats None as "send allowed")."""
    text = None
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            text = gdrive_uploader.download_text(LAST_DIGEST_FILENAME)
    except Exception:  # noqa: BLE001
        pass
    if not text:
        try:
            if LOCAL_LAST_DIGEST.exists():
                text = LOCAL_LAST_DIGEST.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    if not text:
        return None
    try:
        data = json.loads(text)
        return datetime.fromisoformat(data["sent_at_utc"])
    except Exception:  # noqa: BLE001
        return None


def mark_digest_sent(now_utc: datetime) -> None:
    payload = json.dumps({"sent_at_utc": now_utc.isoformat()}, indent=2)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_LAST_DIGEST.write_text(payload, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            gdrive_uploader.upload_or_replace(LAST_DIGEST_FILENAME, payload,
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def seconds_since_last_digest(now_utc: datetime) -> float:
    """A very large number (never gates) when there is no prior send."""
    last = load_last_digest_sent()
    if last is None:
        return float("inf")
    return (now_utc - last).total_seconds()
