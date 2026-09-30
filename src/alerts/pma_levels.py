"""PMA committee levels — read the file the PMA committee publishes each
morning and evaluate it against live quotes. See `AQE Handoff: PMA Live
Alerts` (docs/handoff/aqe_handoff_pma_live_alerts_2026-09-30.md) for the
full spec this module implements.

Alerts only. Nothing here places, changes, cancels or sizes an order —
every trigger this module returns is a plain-language FACT about a level
the committee already set; the PM's own broker stop is always the stop
an email calls "your stop" (guardrail, never AQE's own read).

`evaluate_pma` is pure (row + quote + three explicit time flags in, a
list of trigger dicts out) — the same discipline `src/alerts/engine.py`'s
own `evaluate()` already follows, so both are unit-testable without a
clock or a network call. The cycle loop (dedup against `pma_fired`,
history, ledger, email) lives in engine.py, mirroring the existing
MOVE/BOS loop rather than duplicating it here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.alerts import config as C

_ET = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Plain-word headline phrases, one per trigger kind — the emailer's
# COMMITTEE LEVELS section must never show `trade_above`, a trigger id or
# any other JSON key (build-brief "card UX" rule), so the phrase is fixed
# here, next to the kind it describes, rather than re-derived later from a
# generic dict.
_HEADLINE_PHRASE = {
    "trade_above": "trading through a line",
    "trade_below": "trading through a line",
    "close_above": "closed above its line",
    "close_below": "closed below its line",
    "within_atr_of": "near its stop",
    "no_stop_order": "has no stop order",
    "order_config": "stop order needs a check",
}
_SYNTH_HEADLINE_PHRASE = {
    "Near your stops": "near your stops",
    "Approaching entry": "approaching its buy line",
    "Approaching target": "approaching its target",
}


def _n(v):
    try:
        f = float(v)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Loading + freshness
# ---------------------------------------------------------------------------

def load_pma_levels(path: str | None = None) -> tuple[dict | None, str | None]:
    """The PMA levels file. Local checkout first (the fast path on the
    GitHub Actions backstop, which re-clones `main` every run so its local
    copy is always current); the GitHub contents API otherwise (the HF
    Space's own path — `aegis/output/**` never triggers a redeploy, see the
    handoff doc, so its local checkout is frozen at whatever `main` looked
    like at the last real code deploy and must be fetched fresh instead).

    No new credential: reuses `src.data.github_sync`'s existing
    `GITHUB_TOKEN` (already an HF Space secret and a GitHub Actions secret
    with Contents:read+write on this repo) rather than a separate
    `AQE_GH_TOKEN` — see the handoff's own "still open" item on this.

    Returns (doc, reason) — doc is None with a reason on any miss; never
    raises.
    """
    rel_path = path or C.PMA_LEVELS_PATH
    today = datetime.now(_ET).date().isoformat()

    local_path = PROJECT_ROOT / rel_path
    try:
        if local_path.exists():
            doc = json.loads(local_path.read_text(encoding="utf-8"))
            if doc.get("session") == today:
                return doc, None
    except Exception:  # noqa: BLE001
        pass

    try:
        from src.data import github_sync
        if not github_sync.is_configured():
            return None, "no fresh local file and no GitHub credential configured"
        result = github_sync.get_file(rel_path)
        if not result.get("ok"):
            return None, result.get("reason") or "github fetch failed"
        return json.loads(result["text"]), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def is_fresh(doc: dict, now_et: datetime) -> bool:
    """True iff the file's own `session` is today's New York date. A file
    from any other session (the committee hasn't run yet, or the fetch
    returned an old copy) is stale — act on it never, notice it once."""
    if not doc:
        return False
    return doc.get("session") == now_et.date().isoformat()


def is_first_cycle_of_session(now_et: datetime) -> bool:
    """True for the first poll of the day — the window from market-open-gate
    to one cadence later. `no_stop_order`/`order_config` fire only here."""
    mins = now_et.hour * 60 + now_et.minute
    open_mins = C.MARKET_OPEN[0] * 60 + C.MARKET_OPEN[1]
    return open_mins <= mins < open_mins + C.ALERT_MINUTES


def is_final_cycle_of_session(now_et: datetime) -> bool:
    """True from 16:00 ET — the last cycle inside the 16:15 window where a
    `close_above`/`close_below` trigger's ACTION confirms for real."""
    mins = now_et.hour * 60 + now_et.minute
    return mins >= 16 * 60


# ---------------------------------------------------------------------------
# Row/ticker helpers
# ---------------------------------------------------------------------------

def alertable_rows(doc: dict) -> list[dict]:
    """Every row that can ever alert — WATCH is digest-only (R17) and a
    `not_structured_yet` row carries no triggers by construction, so both
    fall out naturally rather than needing a separate skip list."""
    return [r for r in (doc.get("rows") or [])
           if r.get("class") != "WATCH" and r.get("triggers")]


def watch_rows(doc: dict) -> list[dict]:
    return [r for r in (doc.get("rows") or []) if r.get("class") == "WATCH"]


def pma_tickers(doc: dict) -> set[str]:
    """Every non-WATCH ticker — added to the quote fetch regardless of
    `in_alert_universe` (the committee picked them, not AQE's own gate)."""
    return {r.get("ticker") for r in (doc.get("rows") or [])
           if r.get("class") != "WATCH" and r.get("ticker")}


def held_broker_stop_tickers(doc: dict) -> set[str]:
    """Tickers carrying a `broker_stop` — the legacy engine's own held-name
    NEAR_STOP is suppressed for these so the PM never gets two stop alerts
    quoting two different numbers."""
    return {r.get("ticker") for r in (doc.get("rows") or [])
           if r.get("class") == "HELD" and r.get("broker_stop") and r.get("ticker")}


def live_base_ids(doc: dict) -> set[str]:
    """Every trigger id currently in the file, PLUS the synthetic
    `{ticker}-nearstops` / `{ticker}-entry` bases the proximity alerts key
    off (see `_synthesized_proximity_alerts`) — the pruning frontier for
    `state.prune_pma_fired`. A key whose base id isn't in this set belongs
    to a row that has retired, PASSed, or aged out."""
    ids = set()
    for r in alertable_rows(doc):
        ticker = r.get("ticker")
        for t in r.get("triggers") or []:
            if t.get("id"):
                ids.add(t["id"])
        if r.get("class") == "HELD":
            ids.add(f"{ticker}-nearstops")
        else:
            has_entry = any(
                t.get("priority") == "ACTION"
                and t.get("kind") in ("trade_above", "close_above")
                for t in r.get("triggers") or [])
            if has_entry:
                ids.add(f"{ticker}-entry")
    return ids


# ---------------------------------------------------------------------------
# Evaluation (pure)
# ---------------------------------------------------------------------------

def evaluate_pma(row: dict, quote: dict, now_et: datetime,
                 is_final_cycle: bool, is_first_cycle: bool) -> list[dict]:
    """Every trigger on `row` that is true right now, in the engine's own
    trigger shape plus PMA's own extra fields. Pure — no clock reads, no
    file access, no network; `now_et`/`is_final_cycle`/`is_first_cycle` are
    all explicit inputs so this is exhaustively testable."""
    triggers = row.get("triggers") or []
    if not triggers or row.get("class") == "WATCH":
        return []

    price = _n(quote.get("price"))
    if price is None or price <= 0:
        return []
    day_hi = _n(quote.get("day_high"))
    day_lo = _n(quote.get("day_low"))
    prev_close = _n(quote.get("prev_close"))
    chg_pct = ((price / prev_close - 1) * 100
              if prev_close and prev_close > 0 else None)

    session_key = now_et.date().isoformat()
    out: list[dict] = []
    atr_band_hit = False

    # Card context, computed once and stamped on EVERY trigger this row
    # produces (not only the synthesized proximity ones) so the emailer
    # never has to go back to the raw PMA row to build a card's number
    # line — held cards always carry Your stop/Committee stop, shortlist
    # cards always carry Entry/Target, per the handoff's own rule that
    # the two never swap.
    is_held_row = row.get("class") == "HELD"
    ctx: dict = {}
    if is_held_row:
        broker = row.get("broker_stop") or {}
        ctx["broker_stop"] = _n(broker.get("stop"))
        ctx["committee_exit"] = _n(row.get("committee_exit"))
    else:
        levels = row.get("levels") or {}
        tp = [_n(p) for p in (levels.get("tp") or []) if _n(p) is not None]
        ctx["computed_stop"] = _n(levels.get("stop"))
        ctx["targets"] = tp
        entry_trig = next(
            (t for t in triggers if t.get("priority") == "ACTION"
             and t.get("kind") in ("trade_above", "close_above")), None)
        if entry_trig:
            entry_level = _n(entry_trig.get("level"))
            ctx["entry_price"] = entry_level
            if entry_level is not None:
                ctx["target_price"] = next((p for p in tp if p > entry_level), None)

    for trig in triggers:
        kind = trig.get("kind")
        level = _n(trig.get("level"))
        priority = trig.get("priority")
        trig_id = trig.get("id")
        action_text = trig.get("action") or ""
        if not trig_id:
            continue

        fired = False
        dedup_suffix = None
        note_suffix = ""

        if kind == "trade_above":
            fired = level is not None and day_hi is not None and day_hi >= level
        elif kind == "trade_below":
            fired = level is not None and day_lo is not None and day_lo <= level
        elif kind == "close_above":
            if level is not None:
                fired = price >= level
                if is_final_cycle:
                    dedup_suffix = "close"
                else:
                    dedup_suffix = "warn"
                    priority = "WARN"
                    note_suffix = " — beyond the line intraday, confirms only on the close"
        elif kind == "close_below":
            if level is not None:
                fired = price <= level
                if is_final_cycle:
                    dedup_suffix = "close"
                else:
                    dedup_suffix = "warn"
                    priority = "WARN"
                    note_suffix = " — beyond the line intraday, confirms only on the close"
        elif kind == "within_atr_of":
            # Folded into the synthesized "Near your stops" alert below (the
            # handoff's own wording: "within HELD_NEAR_PCT... OR inside the
            # ATR band" describes ONE alert with two OR'd conditions, not
            # two separate cards saying the same thing about the same stop)
            # rather than appended here as its own trigger.
            atr = _n(trig.get("atr"))
            atr_mult = _n(trig.get("atr_mult"))
            if level is not None and atr is not None and atr_mult is not None:
                if level < price <= level + atr_mult * atr:
                    atr_band_hit = True
            continue
        elif kind in ("no_stop_order", "order_config"):
            fired = is_first_cycle
            dedup_suffix = session_key
        else:
            fired = False

        if not fired:
            continue

        vol_min_x = _n(trig.get("volume_min_x"))
        if vol_min_x is not None:
            try:
                from src.alerts import intraday as _I
                pace = _I.measures(quote, _n(row.get("atr_14d")), now_et).get("vol_pace")
            except Exception:  # noqa: BLE001
                pace = None
            if pace is None:
                note_suffix += " (volume unconfirmed)"
            elif pace < vol_min_x:
                continue  # a genuine shortfall gives no ACTION
            else:
                note_suffix += f" (volume {pace:.2f}x pace vs {vol_min_x:.2f}x needed)"

        dedup_key = trig_id if dedup_suffix is None else f"{trig_id}|{dedup_suffix}"

        entry = {
            "ticker": row.get("ticker"), "source": "pma",
            "is_held": is_held_row,
            "level": dedup_key,
            "label": action_text or kind,
            "level_price": round(level, 2) if level is not None else None,
            "live_px": round(price, 2),
            "chg_pct": round(chg_pct, 2) if chg_pct is not None else None,
            "prev_close": round(prev_close, 2) if prev_close else None,
            "intraday": {},
            "note": (action_text + note_suffix).strip(),
            "pma_class": row.get("class"),
            "priority": priority,
            "action": action_text,
            "origin_run": row.get("origin_run") or doc_run_date(row),
            "age_sessions": row.get("age_sessions", 0),
            "carried": bool(row.get("carried")),
            "trigger_id": trig_id,
            "headline_phrase": _HEADLINE_PHRASE.get(kind, "level triggered"),
            "kind": kind,
        }
        entry.update(ctx)
        out.append(entry)

    out.extend(_synthesized_proximity_alerts(row, price, chg_pct, prev_close,
                                             session_key, ctx, atr_band_hit))
    return out


_SYNTH_SENTENCE = {
    "Near your stops": "Price is close to one of your two stops. Your broker "
                      "stop is the order in force unless the committee's own "
                      "exit is nearer.",
    "Approaching entry": "Getting close to the committee's buy line — no "
                        "condition has triggered yet.",
    "Approaching target": "Getting close to the first target above the entry.",
}


def _base(row: dict, price: float, chg_pct, prev_close, key: str, label: str,
          ctx: dict) -> dict:
    sentence = _SYNTH_SENTENCE.get(label, label)
    e = {
        "ticker": row.get("ticker"), "source": "pma",
        "is_held": row.get("class") == "HELD",
        "level": key, "label": label, "level_price": None,
        "live_px": round(price, 2),
        "chg_pct": round(chg_pct, 2) if chg_pct is not None else None,
        "prev_close": round(prev_close, 2) if prev_close else None,
        "intraday": {}, "note": sentence, "pma_class": row.get("class"), "priority": "WARN",
        "action": sentence, "trigger_id": None,
        "kind": ("near_stops" if label == "Near your stops"
                else "approaching_entry" if label == "Approaching entry"
                else "approaching_target"),
        "origin_run": row.get("origin_run") or doc_run_date(row),
        "age_sessions": row.get("age_sessions", 0),
        "carried": bool(row.get("carried")),
        "headline_phrase": _SYNTH_HEADLINE_PHRASE.get(label, label.lower()),
    }
    e.update(ctx)
    return e


def _synthesized_proximity_alerts(row: dict, price: float, chg_pct, prev_close,
                                  session_key: str, ctx: dict,
                                  atr_band_hit: bool = False) -> list[dict]:
    """The two "New alert" rows from the handoff's Distance-in-% table —
    AQE's own proximity read on top of whatever the committee's literal
    triggers already cover. "Near your stops" re-arms every morning
    (daily-shaped, like the legacy engine's NEAR_STOP); the shortlist pair
    fires once in the trigger's life, like everything else here. `ctx`
    (broker_stop/committee_exit or entry_price/target_price) was already
    computed once by the caller. `atr_band_hit` folds in the row's own
    within_atr_of trigger, if any — one OR'd condition, one card, never two
    saying the same thing about the same stop."""
    out = []
    ticker = row.get("ticker")

    if row.get("class") == "HELD":
        b_stop, c_exit = ctx.get("broker_stop"), ctx.get("committee_exit")
        b_dist = round(abs(price - b_stop) / price * 100, 1) if b_stop else None
        c_dist = round(abs(price - c_exit) / price * 100, 1) if c_exit else None
        near = (atr_band_hit
               or (b_dist is not None and b_dist <= C.HELD_NEAR_PCT)
               or (c_dist is not None and c_dist <= C.HELD_NEAR_PCT))
        if near:
            e = _base(row, price, chg_pct, prev_close,
                      f"{ticker}-nearstops|{session_key}", "Near your stops", ctx)
            e["broker_stop_dist_pct"] = b_dist
            e["committee_exit_dist_pct"] = c_dist
            out.append(e)
        return out

    entry_level, target = ctx.get("entry_price"), ctx.get("target_price")
    if entry_level is None:
        return out
    trig_id_base = f"{ticker}-entry"

    if price < entry_level:
        dist = round((entry_level - price) / price * 100, 1)
        if dist <= C.SHORTLIST_NEAR_PCT:
            e = _base(row, price, chg_pct, prev_close,
                      f"{trig_id_base}|near", "Approaching entry", ctx)
            e["entry_dist_pct"] = dist
            if target is not None:
                e["target_dist_pct"] = round((target - price) / price * 100, 1)
            out.append(e)
    elif target is not None and price < target:
        dist = round((target - price) / price * 100, 1)
        if dist <= C.SHORTLIST_NEAR_PCT:
            e = _base(row, price, chg_pct, prev_close,
                      f"{trig_id_base}|target", "Approaching target", ctx)
            e["target_dist_pct"] = dist
            out.append(e)
    return out


def doc_run_date(row: dict) -> str | None:
    """A row doesn't carry its own file's run_date; callers that have the
    parent doc stamp it in before evaluate_pma sees the row (see
    engine.py). Falls back to None so a bare unit test on a row alone
    still degrades cleanly."""
    return row.get("_run_date")
