#!/usr/bin/env python3
"""pma_levels.py -- the committee's levels, as numbers AQE's live alert loop can watch (R20).

PM ruling 2026-09-30: "add step for PMA to write card to github location" so that AQE's 15-minute
alert engine monitors the levels the committee sets and emails actionable items during market hours.

Two subcommands, both deterministic, neither forms an opinion:

  stops  Normalise the broker's open orders + positions (Tiger, READ-ONLY, pulled by the conductor)
         into broker_stops.json. The PM's broker stop is the level in force on every held name.
         Before 2026-09-29 the run read AQE's held_sl, which is null on every row, and the brief told
         the PM he had no stops when he had six.

  emit   Build pma_levels.json from the run's saved files:
           consensus.json   verdict, conviction, lane
           brackets.json    computed stop / targets (render-only, R1)
           repeat_marks.json
           cards.json       the committee's CONDITIONS as structured triggers (written at WRITE)
           broker_stops.json
           candidate_set.json  atr_14d for the near-stop band
           phase4.json      the R17 WATCH list
           slate.json       (--slate, R40) the slate-wide MARKET KILL line -> top-level market_kill
         and REFUSE to write it if the contract is broken (see validate()).

Nothing here places, changes or sizes an order. The file is information for the PM's inbox.
"""
import argparse, json, os, sys
from datetime import datetime, timezone

SCHEMA = "pma_levels.v1"
KINDS = {"trade_above", "trade_below", "close_above", "close_below",
         "within_atr_of", "no_stop_order", "order_config"}
BASES = {"15m", "daily", "open"}
PRIORITIES = {"ACTION", "WARN", "INFO"}
CLASSES = {"ADVANCE", "HOLD_FOR_CONDITIONS", "HELD", "WATCH"}
NEAR_STOP_ATR = 0.5


def _load(p, default=None):
    if not p or not os.path.exists(p):
        if default is not None:
            return default
        sys.exit(f"missing input: {p}")
    with open(p) as f:
        return json.load(f)


# --------------------------------------------------------------------------------------- stops
def _journal_book(path):
    """PM 2026-11-02: the close's journal is the book of record for the stops (Tiger's working
    orders read at 05:30). -> ({ticker: row}, journal_date, orders_pulled)."""
    j = _load(path)
    pulled = (j.get("broker_sync") or {}).get("open_orders_pull_ran")
    book = {}
    for p in j.get("open_positions") or []:
        so = p.get("stop_order") or {}
        stop = p.get("stop_live_broker")
        book[p["ticker"]] = {"qty": p.get("qty"), "avg_cost": p.get("entry"), "mark": p.get("mark_price"),
                             "order": so.get("type") if stop is not None else None, "stop": stop,
                             "limit": so.get("limit") if stop is not None else None,
                             "order_qty": so.get("qty"), "tif": so.get("time_in_force")}
    return book, j.get("date"), pulled


def _compare(journal, live):
    """Every way the live broker read disagrees with the journal, in plain words."""
    out = []
    for t in sorted(set(journal) | set(live)):
        j, l = journal.get(t), live.get(t)
        if j and not l:
            out.append(f"{t}: in the journal, NOT held at the live broker read")
        elif l and not j:
            out.append(f"{t}: held at the broker, NOT in the journal (new since the close?)")
        else:
            if j.get("qty") is not None and l.get("qty") is not None and abs(float(j["qty"]) - float(l["qty"])) > 1e-6:
                out.append(f"{t}: shares journal {j['qty']} vs broker {l['qty']}")
            js, ls = j.get("stop"), l.get("stop")
            if (js is None) != (ls is None):
                out.append(f"{t}: stop journal {js} vs broker {ls}")
            elif js is not None and abs(float(js) - float(ls)) > 0.005:
                out.append(f"{t}: stop moved, journal {js} -> broker {ls}")
    return out


def cmd_stops(a):
    if a.journal and not (a.orders and a.positions):
        book, jdate, pulled = _journal_book(a.journal)
        for t, p in book.items():
            if pulled is False:
                p["note"] = "STOPS NOT READ at the close (open orders not pulled) -- not today's answer"
            elif p["stop"] is None:
                p["note"] = "NO STOP ORDER"
        out = {"source": f"journal {jdate} (Tiger working orders read at the close); "
                         "no live broker read this run; nothing placed, changed or cancelled",
               "journal_date": jdate, "journal_orders_pulled": pulled, "positions": book,
               "disagreements": []}
        with open(a.out, "w") as f:
            json.dump(out, f, indent=1)
        print(f"wrote {a.out} from journal {jdate}: {len(book)} positions, "
              f"{sum(1 for p in book.values() if p['stop'] is None)} with no stop"
              + ("" if pulled is not False else " -- WARNING: the close did not read the orders"))
        return
    if not (a.orders and a.positions):
        sys.exit("stops: give --journal, or --orders and --positions (or all three)")
    orders = _load(a.orders)
    positions = _load(a.positions)
    orders = orders.get("result", orders) if isinstance(orders, dict) else orders
    positions = positions.get("result", positions) if isinstance(positions, dict) else positions
    held = set(a.held.split(",")) if a.held else None
    pos = {}
    for p in positions:
        if p.get("sec_type") not in (None, "STK"):
            continue
        t = p["symbol"]
        if held is not None and t not in held:
            continue
        pos[t] = {"qty": p.get("quantity"), "avg_cost": p.get("avg_cost"),
                  "mark": p.get("market_price"), "order": None, "stop": None, "limit": None}
    for o in orders:
        t = o.get("symbol")
        if t not in pos or o.get("sec_type") not in (None, "STK") or o.get("action") != "SELL":
            continue
        if o.get("order_type") not in ("STP", "STP_LMT", "TRAIL", "TRAIL_LIMIT"):
            continue
        pos[t].update({"order": o["order_type"], "stop": o.get("stop_price"),
                       "limit": o.get("limit_price"), "order_qty": o.get("quantity"),
                       "tif": o.get("time_in_force"), "outside_rth": o.get("outside_rth")})
    for t, p in pos.items():
        notes = []
        if p["stop"] is None:
            notes.append("NO STOP ORDER")
        if p.get("limit") is not None and p.get("stop") is not None and p["limit"] > p["stop"]:
            notes.append(f"limit {p['limit']} sits ABOVE stop {p['stop']}: on a drop it only fills if price recovers")
        if p.get("order_qty") is not None and p.get("qty") is not None and p["order_qty"] < p["qty"]:
            notes.append(f"stop covers {p['order_qty']} of {p['qty']} shares")
        if notes:
            p["note"] = "; ".join(notes)
    out = {"source": f"broker read-only ({a.broker}), pulled {datetime.now(timezone.utc).isoformat(timespec='minutes')}; "
                     "nothing placed, changed or cancelled",
           "positions": pos}
    if a.journal:
        jbook, jdate, pulled = _journal_book(a.journal)
        if held is None:      # the Aegis book is the journal's, never the whole account
            pos = {t: p for t, p in pos.items() if t in jbook}
            out["positions"] = pos
        out["journal_date"] = jdate
        out["journal_orders_pulled"] = pulled
        out["disagreements"] = _compare(jbook, pos)
    if a.previous and os.path.exists(a.previous):
        prev = _load(a.previous).get("positions", {})
        gone = sorted(set(prev) - set(pos))
        if gone:
            out["closed_since_last_run"] = {t: {"exit": None, "how": "no longer held at the broker; confirm the fill -- "
                                                "the broker's fill query has missed stop-outs (GLD 2026-09-28)"} for t in gone}
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {a.out}: {len(pos)} positions, "
          f"{sum(1 for p in pos.values() if p['stop'] is None)} with no stop, "
          f"{sum(1 for p in pos.values() if 'ABOVE stop' in (p.get('note') or ''))} with limit above stop")


# ---------------------------------------------------------------------------------------- emit
def _levels(b):
    if not b:
        return None
    st = b.get("stop") or {}
    fl = b.get("flags") or st.get("flags") or {}
    return {"ref_close": (b.get("price") or {}).get("value"), "stop": st.get("price"),
            "stop_type": st.get("type"), "stop_pct": st.get("stop_pct"),
            "tp": [t.get("price") for t in (b.get("tp_ladder") or [])[:3]],
            "rr_to_tp2": b.get("rr_to_tp2"),
            "gates_clear": bool(fl.get("atr_ok") and fl.get("rr_ok")), "sized": False}


def _norm_trigger(t, tk, i):
    d = {"id": t.get("id") or f"{tk}-{i}", "kind": t["kind"], "level": t.get("level"),
         "basis": t.get("basis", "daily"), "priority": t.get("priority", "ACTION"),
         "action": t.get("action", "")}
    if t.get("volume_min_x") is not None:
        d["volume_min_x"] = t["volume_min_x"]
    return d


def build(a):
    cons = _load(a.consensus)
    br = _load(a.brackets, {}).get("brackets", {})
    rm = _load(a.repeat_marks, {}).get("marks", {})
    cards = _load(a.cards)
    bs = _load(a.broker_stops, {}).get("positions", {})
    cs = _load(a.candidates, {})
    uni = {r["ticker"]: r for r in (cs.get("universe") or [])}
    p4 = _load(a.phase4, {})
    rows = []
    held_set = set(bs) | set(cards.get("held", {}))

    for c in cons:
        t, v = c["ticker"], c["verdict"]
        if v not in ("ADVANCE", "HOLD-FOR-CONDITIONS"):
            continue
        cls = "ADVANCE" if v == "ADVANCE" else "HOLD_FOR_CONDITIONS"
        card = (cards.get("advance" if cls == "ADVANCE" else "hold") or {}).get(t, {})
        trig = [_norm_trigger(x, t, i) for i, x in enumerate(card.get("triggers") or [])]
        row = {"ticker": t, "class": cls, "lane": c.get("lane"), "conviction": c.get("conviction"),
               "held": t in held_set, "mark": (rm.get(t) or {}).get("mark"),
               "levels": _levels(br.get(t)), "triggers": trig,
               "confirms": card.get("confirms"), "kills": card.get("kills")}
        if card.get("not_structured_yet"):
            row["not_structured_yet"] = card["not_structured_yet"]
        rows.append(row)

    for t in sorted(held_set):
        b = bs.get(t, {})
        card = (cards.get("held") or {}).get(t, {})
        atr = (uni.get(t) or {}).get("atr_14d") or ((uni.get(t) or {}).get("held_book") or {}).get("atr_14d")
        trig = []
        if b.get("stop") is None:
            trig.append({"id": f"{t}-nostop", "kind": "no_stop_order", "level": None, "basis": "open",
                         "priority": "ACTION",
                         "action": "No stop order at the broker. Repeat every session until an order exists or the position is gone."})
        else:
            trig.append({"id": f"{t}-stopnear", "kind": "within_atr_of", "level": b["stop"], "basis": "15m",
                         "priority": "WARN", "atr": atr, "atr_mult": NEAR_STOP_ATR,
                         "action": f"Price within {NEAR_STOP_ATR} ATR of your broker stop {b['stop']}."})
            if b.get("limit") is not None and b["limit"] > b["stop"]:
                trig.append({"id": f"{t}-ordertype", "kind": "order_config", "level": b["stop"], "basis": "open",
                             "priority": "ACTION",
                             "action": f"Stop-limit with limit {b['limit']} ABOVE stop {b['stop']}: may not fill on a drop."})
        ce = card.get("committee_exit")
        if ce is not None:
            trig.append({"id": f"{t}-committee", "kind": "close_below", "level": ce, "basis": "daily",
                         "priority": "ACTION",
                         "action": f"Closed under the committee's exit line {ce}"
                                   + (f" (tighter than your broker stop {b['stop']})" if b.get("stop") is not None else "")
                                   + ". Your call whether to act."})
        for i, x in enumerate(card.get("triggers") or []):
            trig.append(_norm_trigger(x, t, f"x{i}"))
        rows.append({"ticker": t, "class": "HELD", "qty": b.get("qty"),
                     "broker_stop": {"order": b.get("order"), "stop": b.get("stop"), "limit": b.get("limit"),
                                     "note": b.get("note")},
                     "committee_exit": ce, "committee_exit_range": card.get("committee_exit_range"),
                     "atr_14d": atr, "triggers": trig,
                     "keep_case": card.get("for"), "release_case": card.get("against")})

    for i in p4.get("informational") or []:
        rows.append({"ticker": i["ticker"], "class": "WATCH", "doors": i.get("doors"), "lane": i.get("lane"),
                     "aqe_rank": i.get("aqe_rank"), "mp": i.get("mp"), "pct_from_pivot": i.get("pct_from_pivot"),
                     "triggers": [],
                     "note": "R17: information only -- no analyst nominated it, no verdict, no levels. Digest only."})

    guard = _pinned_to_close(rows, uni)
    cond_schema = None
    if getattr(a, "conditions", None):
        cd = _load(a.conditions)
        cond_schema = cd.get("schema")
        by = {r["ticker"]: r for r in cd.get("rows") or []}
        for r in rows:
            if r["class"] != "WATCH" and r["ticker"] in by:
                r["conditions"] = _compact_conditions(by[r["ticker"]])

    return {"schema": SCHEMA, "conditions_schema": cond_schema, "_guard": guard,
            "run_date": a.date, "session": a.session or a.date,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "valid_until": a.valid_until or "next PMA run, or 16:15 ET on the session date, whichever first",
            "render_only": True,
            "guardrails": ["alerts only -- never place, change, cancel or size an order",
                           "the PM's broker stop is the level in force on every held name",
                           "WATCH rows never alert intraday (R17)",
                           "nothing observed intraday feeds back into a committee vote (R1)"],
            "counts": {k: sum(1 for r in rows if r["class"] == k) for k in sorted(CLASSES)},
            "rows": rows}


PIN_TOL = 0.0001   # a trade-through line within 0.01% of yesterday's close is pinned to the close


def _pinned_to_close(rows, uni):
    """D123 guard (found 2026-10-01: HPE's ACTION entry 'traded through Wednesday's 63.89 high' was
    Wednesday's CLOSE -- AQE's high_52w is a closing high -- so it would fire on the first uptick).
    A trade-through line sitting on yesterday's close is an uptick, not a level. Refuse it; the fix is
    at WRITE: use bar_high (yesterday's intraday high) or a close_above."""
    errs = []
    for r in rows:
        ref = ((r.get("levels") or {}).get("ref_close")
               or (uni.get(r["ticker"]) or {}).get("entry")
               or ((uni.get(r["ticker"]) or {}).get("held_book") or {}).get("live_px"))
        if not isinstance(ref, (int, float)) or ref <= 0:
            continue
        for x in r.get("triggers") or []:
            lv = x.get("level")
            if x.get("kind") == "trade_above" and isinstance(lv, (int, float)) and abs(lv / ref - 1) <= PIN_TOL:
                errs.append(f"{r['ticker']}/{x['id']}: trade_above {lv} is yesterday's close ({ref}) -- an uptick, "
                            "not a level. Use bar_high (yesterday's intraday high) or close_above (D123)")
    return errs


def _compact_conditions(c):
    """What AQE needs from conditions.json, per name: the shared lines, every analyst's own words with
    numbers attached, and the exit lines. Words are from contracts/condition_vocab.json."""
    slim = lambda r: {"word": r["word"], "w": r["w"], "when": r["when"],
                      "levels": [l["value"] for l in r["levels"]], "x": r["x"], "plain": r["plain"]}
    sh = c.get("shared") or {}
    return {"shared": {"buy": [{"w": g["w"], "level": g["value"], "x": g["x"], "seats": g["seats"], "plain": g["plain"],
                                "when": g["when"]} for g in sh.get("buy") or []],
                       "confirm": [{"w": g["w"], "level": g["value"], "x": g["x"], "seats": g["seats"],
                                    "plain": g["plain"], "when": g["when"]} for g in sh.get("confirm") or []],
                       "no_shared_buy": sh.get("no_shared_buy"),
                       "wait_zone": sh.get("wait_zone"),
                       "chase": slim(sh["chase"]) if sh.get("chase") else None},
            "exits": c.get("exits") or [],
            "analysts": [{"seat": x["seat"], "vote": x["vote"], "conviction": x["conviction"], "counts": x["counts"],
                          "lane": x["lane"], "tf": x["tf"], "non_price": x["non_price"],
                          "buy": [slim(r) for r in x["buy"]], "confirm": [slim(r) for r in x["confirm"]],
                          "wrong": [slim(r) for r in x["wrong"]], "wait": x["wait"],
                          "chase": slim(x["chase"]) if x.get("chase") else None}
                         for x in c.get("analysts") or [] if x.get("filed")]}


# ------------------------------------------------------------------------------ rolling window
def _close_of(uni, t):
    r = uni.get(t) or {}
    b = r.get("bracket") or {}
    hb = r.get("held_book") or {}
    for v in (b.get("price"), hb.get("cob_price"), hb.get("live_px")):
        if isinstance(v, (int, float)):
            return v
    return None


def apply_window(doc, history, window, uni, today_verdicts, closes=None):
    """PM ruling 2026-09-30 (R20.1): a committee level often takes a few sessions to trigger, so the
    file carries the last `window` runs ADDITIVELY, not only today's.

    Rules, all mechanical:
      * every trigger id is stamped with the run that set it (`<run_date>:<id>`), so AQE's dedup can
        remember a fire for the trigger's whole life instead of resetting it each day;
      * TODAY WINS: a ticker the committee voted today carries only today's row -- an older level for
        the same name is superseded, never shown beside it;
      * RETIRED, not carried: a name the committee PASSED today; any HELD or WATCH row from an earlier
        run (the broker and the admission rules are re-read every morning, so only today's are current);
        a row whose own kill / invalidation close has already been breached by today's served close;
        a row older than the window.
      * CARRIED: an ADVANCE or HOLD-FOR-CONDITIONS row from a run inside the window whose ticker the
        committee did not vote today (typically LEFT_THE_ROOM, or a name AQE no longer served). It is
        marked carried, with its origin run, its age in sessions and its expiry.
    """
    run = doc["run_date"]
    for r in doc["rows"]:
        r["origin_run"] = run
        r["age_sessions"] = 0
        for x in r["triggers"]:
            if ":" not in x["id"]:
                x["id"] = f"{run}:{x['id']}"
    today = {r["ticker"] for r in doc["rows"]}
    retired, carried, unchecked = [], [], []
    # Works from dated archives OR from yesterday's published file alone (which already holds its own
    # carried rows): the window is cut on each row's ORIGIN run, not on which file it arrived in.
    known = set()
    for h in history:
        if h.get("run_date") and h["run_date"] < run:
            known.add(h["run_date"])
            known.update(x for x in ((h.get("window") or {}).get("runs") or []) if x < run)
    prior = sorted(known, reverse=True)[: max(window - 1, 0)]
    runs_in_window = [run] + prior
    cand = []
    for h in history:
        for r in h.get("rows") or []:
            cand.append((r.get("origin_run") or h.get("run_date") or "", r))
    cand.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    for origin, r in cand:
        if True:
            t, cls = r["ticker"], r.get("class")
            # newest origin first, so the first row seen for a ticker is its latest view
            if cls not in ("ADVANCE", "HOLD_FOR_CONDITIONS") or t in seen:
                continue
            seen.add(t)
            if origin not in prior:
                if origin and origin < run:
                    retired.append({"ticker": t, "class": cls, "origin_run": origin,
                                    "why": f"older than the {window}-session window"})
                continue
            age = prior.index(origin) + 1
            if t in today_verdicts or t in today:
                why = ("committee PASSED it today" if today_verdicts.get(t) == "PASS"
                       else "superseded by today's verdict")
                retired.append({"ticker": t, "class": cls, "origin_run": origin, "why": why})
                continue
            px = _close_of(uni, t)
            px_src = "served close"
            if px is None and isinstance((closes or {}).get(t), (int, float)):
                # 2026-10-01: a carried name that left today's room is usually not in today's served
                # universe either, so its own kill line could never be checked -- BE broke its 288.00
                # kill (close 276.98) and was still carried. --closes supplies the last close for those.
                px, px_src = closes[t], "supplied close"
            if px is None:
                unchecked.append(t)
            breached = None
            if px is not None:
                for x in r.get("triggers") or []:
                    if x.get("kind") == "close_below" and isinstance(x.get("level"), (int, float)) \
                            and x.get("basis") == "daily" and px < x["level"] and \
                            any(w in x["id"] for w in ("kill", "dead")):
                        breached = x
                        break
            if breached:
                retired.append({"ticker": t, "class": cls, "origin_run": origin,
                                "why": f"its own line {breached['level']} is already broken ({px_src} {px})"})
                continue
            c = json.loads(json.dumps(r))
            c.update({"carried": True, "origin_run": origin, "age_sessions": age,
                      "last_session_live": (age == window - 1)})
            for x in c.get("triggers") or []:
                if ":" not in x["id"]:
                    x["id"] = f"{origin}:{x['id']}"
            carried.append(c)
    doc["rows"].extend(carried)
    doc["window"] = {"sessions": window, "runs": runs_in_window, "kill_unchecked": unchecked,
                     "carried": [f"{c['ticker']} ({c['class']}, from {c['origin_run']})" for c in carried],
                     "retired": retired,
                     "rule": "today wins; PASS today, a broken kill line, HELD/WATCH from earlier runs and anything "
                             "older than the window are retired; other ADVANCE/HOLD rows carry, marked, "
                             "with their trigger ids stamped by origin run so a fire is remembered for the row's life"}
    doc["counts"] = {k: sum(1 for r in doc["rows"] if r["class"] == k) for k in sorted(CLASSES)}
    doc["counts"]["carried"] = len(carried)
    return doc


MARKET_KILL_KEYS = ("symbol", "word", "level", "plain", "seats")


def market_kill_from_slate(path, run_date):
    """R40 (PM 2026-11-02): the slate's ONE market condition that voids every new trigger, carried into the
    levels file as top-level `market_kill` so the alert loop can say "market condition broken -- take no new
    triggers" instead of firing buys into a broken tape. Returns (market_kill, note). Copied, never composed:
    the line is decide-timing's modal market_void, which the Chair copies onto the slate. Null is declared
    with its reason -- never an invented line, never a silent absence."""
    if not path or not os.path.exists(path):
        return None, f"slate file not found ({path}) -- no market condition is watched; declared gap"
    sl = _load(path)
    if "market_kill" not in sl:
        return None, "the slate carries no market_kill field (pre-R40 slate) -- no market condition is watched"
    mk = sl.get("market_kill")
    if mk is None:
        return None, "no seat named a market condition"
    if not isinstance(mk, dict):
        return {"_bad": mk}, None
    out = {k: mk.get(k) for k in MARKET_KILL_KEYS}
    out["seats"] = list(out.get("seats") or [])
    out["origin_run"] = run_date
    return out, None


def validate(doc):
    """The contract AQE is promised. Any breach and the file is NOT written."""
    errs = list(doc.pop("_guard", None) or [])
    if "market_kill" in doc and doc["market_kill"] is not None:
        mk = doc["market_kill"]
        if "_bad" in mk:
            errs.append(f"market_kill must be an object or null, got {mk['_bad']!r}")
        else:
            if not isinstance(mk.get("plain"), str) or not mk["plain"].strip():
                errs.append("market_kill has no plain words -- the alert loop could not say what broke")
            if mk.get("level") is not None and not isinstance(mk["level"], (int, float)):
                errs.append(f"market_kill level must be a number or null, got {mk['level']!r}")
    if doc.get("schema") != SCHEMA:
        errs.append("schema")
    seen = set()
    for r in doc["rows"]:
        t, cls = r["ticker"], r["class"]
        if cls not in CLASSES:
            errs.append(f"{t}: class {cls}")
        if cls in ("ADVANCE", "HOLD_FOR_CONDITIONS") and not r["triggers"] and not r.get("not_structured_yet"):
            errs.append(f"{t}: {cls} with no trigger and no not_structured_yet reason -- a condition the "
                        "committee set would silently never be watched")
        if cls == "WATCH" and r["triggers"]:
            errs.append(f"{t}: WATCH row carries triggers (R17: information only)")
        if cls == "HELD":
            s = (r.get("broker_stop") or {}).get("stop")
            if r.get("committee_exit") is not None and s is not None and r["committee_exit"] < s:
                errs.append(f"{t}: committee exit {r['committee_exit']} is BELOW the PM's broker stop {s} -- "
                            "a committee line may never loosen a stop he has")
        for x in r["triggers"]:
            if x["id"] in seen:
                errs.append(f"{t}: duplicate trigger id {x['id']}")
            seen.add(x["id"])
            if x["kind"] not in KINDS:
                errs.append(f"{t}/{x['id']}: kind {x['kind']}")
            if x["basis"] not in BASES:
                errs.append(f"{t}/{x['id']}: basis {x['basis']}")
            if x["priority"] not in PRIORITIES:
                errs.append(f"{t}/{x['id']}: priority {x['priority']}")
            if x["kind"] not in ("no_stop_order", "order_config") and not isinstance(x.get("level"), (int, float)):
                errs.append(f"{t}/{x['id']}: level must be a number, got {x.get('level')!r}")
            if not x.get("action"):
                errs.append(f"{t}/{x['id']}: empty action text")
    return errs


def cmd_emit(a):
    doc = build(a)
    history = []
    for p in (a.history or []):
        try:
            history.append(_load(p))
        except SystemExit:
            print(f"history file missing, skipped: {p}")
    cons = _load(a.consensus)
    uni = {r["ticker"]: r for r in (_load(a.candidates, {}).get("universe") or [])}
    closes = _load(a.closes) if getattr(a, "closes", None) else {}
    doc = apply_window(doc, history, a.window, uni, {c["ticker"]: c["verdict"] for c in cons}, closes)
    if getattr(a, "slate", None):
        # R40: TODAY's market kill always wins -- set after the history merge, never carried from an older file.
        mk, note = market_kill_from_slate(a.slate, a.date)
        doc["market_kill"] = mk
        doc.pop("market_kill_note", None)
        if note:
            doc["market_kill_note"] = note
            print(f"market_kill: null -- {note}")
    errs = validate(doc)
    if errs:
        print("REFUSED: pma_levels.json not written\n  - " + "\n  - ".join(errs))
        sys.exit(2)
    with open(a.out, "w") as f:
        json.dump(doc, f, indent=1)
    n = sum(len(r["triggers"]) for r in doc["rows"])
    skipped = [r["ticker"] for r in doc["rows"] if r.get("not_structured_yet")]
    w = doc.get("window") or {}
    print(f"wrote {a.out}: {len(doc['rows'])} rows {doc['counts']}, {n} triggers; window {w.get('runs')}, "
          f"carried {len(w.get('carried') or [])}, retired {len(w.get('retired') or [])}"
          + (f"; not yet structured (AQE skips): {' '.join(skipped)}" if skipped else ""))


# ------------------------------------------------------------------------------ supplemental pass (PM 2026-11-05)
# A supplemental committee pass (run 2026-11-05-r3) happens AFTER the live run, on the SAME date. emit cannot take it: apply_window is
# "today wins, one row per ticker", so a second same-date emit would supersede or retire the live rows. merge-supplement adds the
# pass ADDITIVELY and changes nothing that is already published.
import re

SUPP_LABEL = "supplemental committee pass"


def parse_conditions_md(text):
    """{ticker: {verdict, lane, buy:{word,level,seats}, confirm:[x...], wait:(lo,hi,members), chase_level, exits:[(value,[seats])]}} read from a run's
    conditions.md. Copied, never composed: a number that is not in the text is not invented (None)."""
    out = {}
    for blk in re.split(r"(?m)^### ", text)[1:]:
        m = re.match(r"([A-Z0-9.\-]+) · (ADVANCE|HOLD-FOR-CONDITIONS) · (\w+)", blk)
        if not m:
            continue
        t, v, lane = m.groups()
        d = {"verdict": v, "lane": lane, "buy": None, "confirm": [], "wait": None, "chase_level": None, "exits": []}
        sb = re.search(r"\*\*Shared by the supporters:\*\* an hourly candle closes above (\w+) ([0-9.]+) \((\d+): ([^)]*)\)", blk)
        if sb:
            d["buy"] = {"ref": sb.group(1), "level": float(sb.group(2)), "n": int(sb.group(3)), "seats": [x.strip() for x in sb.group(4).split(",")]}
        cf = re.search(r"\*\*Confirmed by:\*\* ([^\n]*)", blk)
        if cf:
            d["confirm"] = [float(x) for x in re.findall(r"volume at least ([0-9.]+)x normal", cf.group(1))]
        wz = re.search(r"\*\*Wait-for area:\*\* ([0-9.]+)–([0-9.]+) \(([^)]*)\)", blk)
        if wz:
            d["wait"] = (float(wz.group(1)), float(wz.group(2)), [x.strip() for x in wz.group(3).split(",")])
        ch = re.search(r"\*\*Too late past:\*\* closes above (\S+) ([0-9.]+)", blk)
        if ch:
            d["chase_level"] = (ch.group(1), float(ch.group(2)))
        ex = re.search(r"\*\*Exit lines, highest first:\*\* ([^\n]*)", blk)
        if ex:
            d["exits"] = [(float(a), [x.strip() for x in b.split(",")]) for a, b in re.findall(r"([0-9.]+) \(([^)]*)\)", ex.group(1))]
        out[t] = d
    return out


def _cut_reasons(summary_text):
    """{ticker: reason} for names cut before the slate, from the supplement summary's 'Cut by ...' lines."""
    out = {}
    for m in re.finditer(r"Cut by ([a-z ]+?)(?: \(\d+\))?: ([^\n]*?)(?:\.\s|\.$|$)", summary_text or "", re.M):
        for t in re.findall(r"[A-Z][A-Z0-9.\-]*", m.group(2)):
            out[t] = m.group(1).strip()
    return out


def _supp_conditions(cd):
    sh = {"buy": [], "confirm": [], "no_shared_buy": cd["buy"] is None, "wait_zone": None, "chase": None}
    if cd["buy"]:
        b = cd["buy"]
        sh["buy"] = [{"w": "h1_close_above", "level": b["level"], "x": None, "seats": b["seats"],
                      "plain": f"an hourly candle closes above {b['ref']} {b['level']:g}", "when": "1H"}]
    for x in cd["confirm"]:
        sh["confirm"].append({"w": "vol_x_ge", "level": None, "x": x, "seats": [],
                              "plain": f"volume at least {x:g}x normal for the time of day", "when": "LIVE"})
    if cd["wait"]:
        sh["wait_zone"] = {"lo": cd["wait"][0], "hi": cd["wait"][1], "members": cd["wait"][2]}
    if cd["chase_level"]:
        ref, lv = cd["chase_level"]
        sh["chase"] = {"word": f"close_above:{ref}", "w": "close_above", "when": "EOD", "levels": [lv], "x": None,
                       "plain": f"closes above {ref} {lv:g}"}
    return {"shared": sh,
            "exits": [{"w": "close_below", "value": v, "seats": s, "plain": f"closes below {v:g}"} for v, s in cd["exits"]],
            "analysts": []}                      # per-seat detail is in conditions.md; an empty list is never counted as lit


def supplement_rows(cons, brackets, cond_md, export_rows, origin_run, cut_reasons=None):
    """-> (advance_rows, watch_rows, notes). ADVANCE/HOLD rows need a parsed shared line; a verdict without one is refused, not guessed."""
    adv, watch, notes = [], [], []
    by = {c["ticker"]: c for c in cons}
    for t, c in by.items():
        v = c["verdict"]
        cd = cond_md.get(t)
        if v in ("ADVANCE", "HOLD-FOR-CONDITIONS") and cd:
            cls = "ADVANCE" if v == "ADVANCE" else "HOLD_FOR_CONDITIONS"
            conds = _supp_conditions(cd)
            trig, i = [], 0
            if cd["buy"]:
                x = {"id": f"{t}-buy0", "kind": "close_above", "level": cd["buy"]["level"], "basis": "15m", "priority": "ACTION",
                     "action": (f"{t}: an hourly candle closes above {cd['buy']['level']:g} ({cd['buy']['n']} analysts' shared buy line)"
                                + (f" on volume at least {max(cd['confirm']):g}x normal" if cd["confirm"] else "") + ". Your decision.")}
                if cd["confirm"]:
                    x["volume_min_x"] = max(cd["confirm"])
                trig += [x, {"id": f"{t}-touch", "kind": "trade_above", "level": cd["buy"]["level"], "basis": "15m", "priority": "WARN",
                             "action": f"{t} traded through {cd['buy']['level']:g}: the buy line is in play, not met until an hourly close confirms."}]
            if cd["exits"]:
                top = cd["exits"][0][0]
                trig.append({"id": f"{t}-dead", "kind": "close_below", "level": top, "basis": "daily", "priority": "WARN",
                             "action": f"{t} closed under {top:g}, the highest exit line the supporters filed: the case is weakened."})
            row = {"ticker": t, "class": cls, "lane": c.get("lane"), "conviction": c.get("ordering_score"), "held": bool(c.get("held")),
                   "mark": None, "levels": _levels((brackets or {}).get(t)), "triggers": trig,
                   "confirms": c.get("entry_trigger"), "kills": c.get("wrong_if"), "conditions": conds,
                   "committee_status": c.get("status"),
                   "committee_objections": [{"voice": o.get("voice"), "objection": o.get("objection"), "would_clear": o.get("would_clear")}
                                            for o in c.get("objections") or []]}
            adv.append(row)
        elif v in ("ADVANCE", "HOLD-FOR-CONDITIONS"):
            notes.append(f"{t}: {v} but conditions.md has no parseable shared line -- not loaded")
        else:
            st = c.get("status")
            why = (f"dropped by the committee ({len(c.get('objections') or [])} objections)" if st == "DROPPED"
                   else f"not slated: cut by {(cut_reasons or {}).get(t) or 'the earlier steps'}")
            watch.append({"ticker": t, "class": "WATCH", "triggers": [], "brief_watch": True, "lane": c.get("lane"),
                          "committee_status": st, "committee_result": why,
                          "committee_objections": [{"voice": o.get("voice"), "objection": o.get("objection"), "would_clear": o.get("would_clear")}
                                                   for o in c.get("objections") or []],
                          "note": f"Supplemental pass {origin_run}: {why}. On the swing-pivot list; watched under AQE default criteria. Not a committee pick."})
    return adv, watch, notes


def merge_supplement(base, adv, watch, origin_run, label=SUPP_LABEL):
    """Additive merge into the published doc. A ticker already published KEEPS its row untouched (its supplemental twin is recorded, not
    applied, unless it adds a different shared buy line); every added row and trigger id is stamped with the supplemental origin."""
    doc = json.loads(json.dumps(base))
    have = {r["ticker"]: r for r in doc["rows"]}
    added, kept = [], []
    for r in adv + watch:
        t = r["ticker"]
        r = json.loads(json.dumps(r))
        if t in have:
            old = have[t]
            ob = [g.get("level") for g in ((old.get("conditions") or {}).get("shared") or {}).get("buy") or []]
            nb = [g.get("level") for g in ((r.get("conditions") or {}).get("shared") or {}).get("buy") or []]
            kept.append({"ticker": t, "published_class": old.get("class"), "supplemental_class": r["class"],
                         "same_shared_buy_line": sorted(ob) == sorted(nb) if nb else None})
            continue
        r.update(origin_run=origin_run, age_sessions=0, supplemental=True, supplemental_label=label)
        for x in r["triggers"]:
            if ":" not in x["id"]:
                x["id"] = f"{origin_run}:{x['id']}"
        doc["rows"].append(r)
        added.append(t)
    doc["counts"] = {**{k: sum(1 for r in doc["rows"] if r["class"] == k) for k in sorted(CLASSES)},
                     "carried": (doc.get("counts") or {}).get("carried", 0)}
    doc["supplement"] = {"origin_run": origin_run, "label": label, "added": added, "already_published_kept_as_is": kept,
                         "rule": "additive: published rows, stops, trigger ids and market_kill are untouched; added rows are stamped "
                                 "origin_run + supplemental and their trigger ids carry the origin"}
    return doc


def cmd_merge_supplement(a):
    base = _load(a.base)
    cons = _load(a.consensus)
    br = _load(a.brackets, {}).get("brackets", {})
    cond_md = parse_conditions_md(open(a.conditions_md).read())
    summ = open(a.summary).read() if a.summary and os.path.exists(a.summary) else ""
    adv, watch, notes = supplement_rows(cons, br, cond_md, None, a.origin_run, _cut_reasons(summ))
    doc = merge_supplement(base, adv, watch, a.origin_run)
    errs = validate(json.loads(json.dumps(doc)))
    for n in notes:
        print("NOTE:", n)
    if errs:
        print("REFUSED: pma_levels.json not written\n  - " + "\n  - ".join(errs))
        sys.exit(2)
    with open(a.out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {a.out}: +{len(doc['supplement']['added'])} supplemental rows {doc['supplement']['added']}; "
          f"kept as published: {[k['ticker'] for k in doc['supplement']['already_published_kept_as_is']]}; counts {doc['counts']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stops", help="broker orders+positions (read-only) -> broker_stops.json")
    s.add_argument("--orders", default=None); s.add_argument("--positions", default=None)
    s.add_argument("--journal", default=None,
                   help="the close's journal (book of record for stops); alone = build from it, "
                        "with --orders/--positions = live read cross-checked against it")
    s.add_argument("--held", default=None, help="comma list: restrict to the committee's held book")
    s.add_argument("--previous", default=None, help="yesterday's broker_stops.json, to catch vanished positions")
    s.add_argument("--broker", default="Tiger"); s.add_argument("--out", default="broker_stops.json")
    s.set_defaults(fn=cmd_stops)
    e = sub.add_parser("emit", help="run files -> pma_levels.json (refuses on a broken contract)")
    e.add_argument("--consensus", default="consensus.json"); e.add_argument("--brackets", default="brackets.json")
    e.add_argument("--repeat-marks", default="repeat_marks.json"); e.add_argument("--cards", default="cards.json")
    e.add_argument("--broker-stops", default="broker_stops.json"); e.add_argument("--candidates", default="candidate_set.json")
    e.add_argument("--phase4", default="phase4.json"); e.add_argument("--date", required=True)
    e.add_argument("--session", default=None); e.add_argument("--valid-until", default=None)
    e.add_argument("--history", nargs="*", default=[],
                   help="earlier runs' dated pma_levels files (aegis/output/pma/levels/<date>.json)")
    e.add_argument("--window", type=int, default=3, help="sessions a level stays live, today included (R20.1)")
    e.add_argument("--closes", default=None,
                   help="JSON {ticker: last close} for carried names today's served universe lacks, so their own "
                        "kill line can still be checked (2026-10-01: BE carried through a broken kill)")
    e.add_argument("--conditions", default=None,
                   help="conditions.json from pma_conditions.py compile (D123): each row gains the analysts' conditions")
    e.add_argument("--slate", default=None,
                   help="slate.json (R40): its market_kill line is published as top-level market_kill "
                        "{symbol, word, level, plain, seats, origin_run}; null is declared with market_kill_note")
    e.add_argument("--out", default="pma_levels.json")
    e.set_defaults(fn=cmd_emit)
    m = sub.add_parser("merge-supplement", help="add a SAME-DATE supplemental committee pass to the published file, additively (refuses on a broken contract)")
    m.add_argument("--base", default="pma_levels.json"); m.add_argument("--consensus", required=True); m.add_argument("--brackets", required=True)
    m.add_argument("--conditions-md", required=True); m.add_argument("--summary", default=None); m.add_argument("--origin-run", required=True)
    m.add_argument("--out", default="pma_levels.json")
    m.set_defaults(fn=cmd_merge_supplement)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
