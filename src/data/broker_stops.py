"""The held book's stops — one checked answer to "where is each stop right now".

PM 2026-11-02: "Stop from Tiger is correct. That's the dependency ... ask for the stops then,
both from the trade report and also during the AQE run."

Two Tiger reads, both read-only, both saved verbatim to git by a Claude scheduled task (the AQE
run itself happens on a GitHub runner with no broker access, so it cannot ask Tiger directly):

  1. THE CLOSE (05:30 SGT, the trade report). `get_open_orders` is saved with the rest of the
     broker pull; `aegis/tools/journal_build.py` writes each held name's working stop into the
     dated journal (`stop_live_broker` + `stop_order`) and stamps
     `broker_sync.open_orders_pull_ran`. This is the book of record, and `ptj.py` already reads it.
  2. THE PRE-AQE READ (06:20 SGT). The same two Tiger calls (`get_open_orders`,
     `get_stock_positions`) saved verbatim to `aegis/output/broker/tiger_read_latest.json`
     right before AQE runs. It is the cross-check: the PM can move a stop between the close and
     the run, and a second independent read is how "the export says X" becomes "the broker
     says X".

`resolve()` merges the two into the export's held-stop fields and says, per name, whether the
two reads AGREE, which one the export used, and what is missing. Nothing here decides anything:
a name with no working stop is reported as unprotected, never given a stop.

Loud, never silent: a missing read is a named status (NOT_PULLED / NO_SECOND_READ), never a
blank that reads like "no stop".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

SECOND_READ_PATH = "aegis/output/broker/tiger_read_latest.json"
STOP_TYPES = ("STP", "STP_LMT", "STOP", "STOP_LIMIT", "TRAIL", "TRAIL_LIMIT")
PRICE_TOL = 0.005


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _rows(payload):
    """Tiger MCP results arrive as {"result": [...]}, a bare list, or MCP text content."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("result"), list):
            return payload["result"]
        content = payload.get("content")
        if isinstance(content, list):
            out = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    try:
                        out.extend(_rows(json.loads(c.get("text") or "null")))
                    except ValueError:
                        pass
            return out
    return []


def stops_from_orders(open_orders) -> dict:
    """{ticker: stop_order} from Tiger's working SELL stop orders on stock. When a name has
    several, the one covering the most shares is kept and `n_orders` says there were more."""
    by: dict[str, list] = {}
    for o in _rows(open_orders):
        if str(o.get("action") or "").upper() != "SELL":
            continue
        if str(o.get("sec_type") or "STK").upper() not in ("STK", "STOCK", "EQUITY"):
            continue
        otype = str(o.get("order_type") or "").upper()
        if otype not in STOP_TYPES:
            continue
        stop = _num(o.get("stop_price"))
        if stop is None:
            stop = _num(o.get("trail_stop_price"))
        t = str(o.get("symbol") or "").strip().upper()
        if not t or stop is None:
            continue
        by.setdefault(t, []).append({
            "type": otype, "stop": stop, "limit": _num(o.get("limit_price")),
            "qty": _num(o.get("quantity")), "time_in_force": o.get("time_in_force"),
            "status": o.get("status"), "order_id": o.get("id"),
        })
    out = {}
    for t, rows in by.items():
        best = max(rows, key=lambda r: (r["qty"] or 0))
        best = dict(best, n_orders=len(rows))
        out[t] = best
    return out


def qty_from_positions(stock_positions) -> dict:
    out = {}
    for p in _rows(stock_positions):
        if str(p.get("sec_type") or "STK").upper() not in ("STK", "STOCK", "EQUITY"):
            continue
        t = str(p.get("symbol") or "").strip().upper()
        q = _num(p.get("quantity"))
        if t and q:
            out[t] = q
    return out


def parse_second_read(doc) -> dict:
    """The 06:20 pre-AQE read file -> {ok, pulled_at_utc, stops, qty, reason}."""
    if not isinstance(doc, dict):
        return {"ok": False, "reason": "unreadable"}
    if "open_orders" not in doc or "stock_positions" not in doc:
        return {"ok": False, "reason": "file lacks open_orders / stock_positions",
                "pulled_at_utc": doc.get("pulled_at_utc")}
    return {"ok": True, "pulled_at_utc": doc.get("pulled_at_utc"),
            "date_sgt": doc.get("date_sgt"),
            "stops": stops_from_orders(doc.get("open_orders")),
            "qty": qty_from_positions(doc.get("stock_positions"))}


def fetch_second_read() -> dict:
    """Read the pre-AQE Tiger read from git. Never raises; a failure is a named reason."""
    try:
        from src.data import github_sync
        if not github_sync.is_configured():
            return {"ok": False, "reason": "github not configured"}
        res = github_sync.get_file(SECOND_READ_PATH)
        if not res.get("ok"):
            return {"ok": False, "reason": f"not found at {SECOND_READ_PATH}"}
        return parse_second_read(json.loads(res["text"]))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"fetch failed ({e.__class__.__name__})"}


def _age_hours(pulled_at_utc, now=None):
    try:
        t = datetime.fromisoformat(str(pulled_at_utc).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return ((now or datetime.now(timezone.utc)) - t).total_seconds() / 3600.0
    except Exception:  # noqa: BLE001
        return None


def resolve(position: dict, journal_date, orders_pulled, second: dict | None,
            max_second_age_h: float = 20.0, now=None) -> dict:
    """The export's held-stop fields for one held row.

    position: the journal's open_positions row (stop_live_broker, stop_order, qty).
    journal_date: the journal's date (the close it records).
    orders_pulled: the journal's broker_sync.open_orders_pull_ran (None = an old journal).
    second: parse_second_read() output, or None.

    held_sl prefers the pre-AQE read when it is fresh (it is the later broker answer), else the
    journal's. Both are Tiger; neither is AQE's opinion.
    """
    t = str(position.get("ticker") or "").upper()
    j_stop = _num(position.get("stop_live_broker"))
    j_order = position.get("stop_order") if j_stop is not None else None
    if orders_pulled is False or (orders_pulled is None and j_stop is None):
        j_status = "NOT_PULLED"
    elif j_stop is None:
        j_status = "NO_STOP_ORDER"
    else:
        j_status = "LIVE"

    fresh = False
    if second and second.get("ok"):
        age = _age_hours(second.get("pulled_at_utc"), now)
        fresh = age is not None and -1.0 <= age <= max_second_age_h
    s_order = (second or {}).get("stops", {}).get(t) if fresh else None
    s_qty = (second or {}).get("qty", {}).get(t) if fresh else None

    out = {"held_stop_journal": j_stop, "held_stop_journal_status": j_status,
           "held_stop_as_of": journal_date}
    if fresh:
        out["held_stop_second_read"] = s_order["stop"] if s_order else None
        out["held_stop_second_read_at"] = second.get("pulled_at_utc")
        notes = []
        if s_qty is None:
            notes.append(f"{t} not held at Tiger at the pre-AQE read")
        if j_status == "LIVE" and s_order is None:
            notes.append(f"journal stop {j_stop} but NO working stop at the pre-AQE read")
        elif j_status != "LIVE" and s_order is not None:
            notes.append(f"journal had no stop ({j_status}) but Tiger shows {s_order['stop']}")
        elif s_order is not None and j_stop is not None and abs(s_order["stop"] - j_stop) > PRICE_TOL:
            notes.append(f"stop moved: journal {j_stop} -> Tiger {s_order['stop']}")
        if s_order and s_order.get("qty") is not None and position.get("qty") is not None \
                and s_order["qty"] + 1e-6 < float(position["qty"]):
            notes.append(f"stop covers {s_order['qty']:g} of {float(position['qty']):g} shares")
        out["held_stop_check"] = "AGREES" if not notes else "DIFFERS: " + "; ".join(notes)
        # The later broker answer is the stop in force.
        out["held_sl"] = s_order["stop"] if s_order else None
        out["held_stop_order"] = s_order
        out["held_stop_source"] = "tiger_pre_aqe_read"
        out["held_stop_status"] = "LIVE" if s_order else "NO_STOP_ORDER"
    else:
        out["held_stop_second_read"] = None
        out["held_stop_second_read_at"] = None
        out["held_stop_check"] = ("NO_SECOND_READ: " + ((second or {}).get("reason")
                                  or "stale or absent pre-AQE read"))
        out["held_sl"] = j_stop
        out["held_stop_order"] = j_order
        out["held_stop_source"] = f"journal {journal_date}" if j_status != "NOT_PULLED" else None
        out["held_stop_status"] = j_status
    return out


def summarise(rows: list[dict], journal_date, orders_pulled, second: dict | None) -> dict:
    """Top-level `held_stops` block: the whole book's stop status in one place."""
    unprotected = [r["ticker"] for r in rows if r.get("held_stop_status") == "NO_STOP_ORDER"]
    not_pulled = [r["ticker"] for r in rows if r.get("held_stop_status") == "NOT_PULLED"]
    differs = {r["ticker"]: r["held_stop_check"] for r in rows
               if str(r.get("held_stop_check", "")).startswith("DIFFERS")}
    if not rows:
        status = "EMPTY_BOOK"
    elif not_pulled:
        status = "NOT_PULLED"
    elif differs:
        status = "DIFFERS"
    elif unprotected:
        status = "UNPROTECTED"
    else:
        status = "OK"
    return {
        "status": status,
        "journal_date": journal_date,
        "journal_orders_pulled": orders_pulled,
        "second_read_at": (second or {}).get("pulled_at_utc") if (second or {}).get("ok") else None,
        "second_read_reason": None if (second or {}).get("ok") else (second or {}).get("reason"),
        "unprotected": unprotected,
        "not_pulled": not_pulled,
        "differs": differs,
        "note": ("Stops are Tiger's working orders: read at the close (the journal) and again "
                 "right before the AQE run (the pre-AQE read). held_sl is the later read. "
                 "Nothing here is AQE's opinion of where a stop should be — that is bracket.stop."),
    }
