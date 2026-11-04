#!/usr/bin/env python3
"""AEGIS PMA -- cards, levels and the multi-timeframe grid (R38-R41, PM 2026-11-02).

Run: `python3 tests/test_cards_levels_mtf.py`. House style of tests/test_pipeline.py: zero external
dependencies, exits 0 on pass, 1 on any failure, prints "N passed, M failed".

  * the held-HOLD card (real incident 29 Oct and 2 Nov: V needed a conductor patch before LEVELS would write)
  * R41: Valen's no-buy / parabolic flags leave the cards and the vote packet; weather and setup facts stay
  * R40: the slate's market kill line reaches pma_levels.json and the cards
  * R39: mtf.py's W / D / H1 grid -- known EMA and weekly values, declared NOT SERVED rows
Fixtures under fixtures/held_hold_2026-11-02/ are the REAL 2 Nov run files, trimmed to V, MP, HOG and FLYW.
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
PIPE = os.path.join(TOOLS, "pma_pipeline.py")
CARDS = os.path.join(TOOLS, "pma_cards.py")
LV = os.path.join(TOOLS, "pma_levels.py")
MTF = os.path.join(TOOLS, "mtf.py")
NOV2 = os.path.join(FIX, "held_hold_2026-11-02")

FAILS, PASSES = [], []


def check(name, cond, detail=""):
    (PASSES if cond else FAILS).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("\n          " + detail) if detail and not cond else ""))


def fx(n): return os.path.join(FIX, n)
def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _emit(d, cards, extra=()):
    P = lambda n: os.path.join(d, n)
    return run([LV, "emit", "--consensus", os.path.join(NOV2, "consensus.json"), "--brackets", P("none.json"),
                "--repeat-marks", P("none.json"), "--cards", cards, "--broker-stops", os.path.join(NOV2, "broker_stops.json"),
                "--candidates", P("none.json"), "--phase4", P("none.json"), "--conditions", os.path.join(NOV2, "conditions.json"),
                "--date", "2026-11-02", "--out", P("lv.json")] + list(extra))


# ------------------------------------------------------------------------------------ 1. held HOLD card
def test_a_held_name_on_hold_gets_its_add_card(td):
    """29 Oct and 2 Nov: V was HELD and voted HOLD-FOR-CONDITIONS. `triggers` built cards["held"]["V"] only,
    so LEVELS refused the file ("HOLD_FOR_CONDITIONS with no trigger") until the conductor patched a hold card
    in by hand. The hold is the ADD question on the shared buy line; the broker stop is the exit."""
    d = os.path.join(td, "heldhold"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "cards.json")
    rc, log = run([CARDS, "triggers", "--conditions", os.path.join(NOV2, "conditions.json"), "--export", os.path.join(NOV2, "export.json"),
                   "--broker-stops", os.path.join(NOV2, "broker_stops.json"), "--out", out])
    check("triggers exits clean on the real 2 Nov files", rc == 0, log[-300:])
    if rc != 0: return
    c = json.load(open(out))
    v = (c.get("hold") or {}).get("V")
    check("V (held, HOLD-FOR-CONDITIONS) now has a hold card", v is not None, str(list(c.get("hold") or {})))
    if not v: return
    act = [x for x in v["triggers"] if x["priority"] == "ACTION"]
    check("its ACTION trigger is the shared add line 414.6", any(x["kind"] == "close_above" and x["level"] == 414.6 for x in act), str(act))
    check("the trigger is worded as the ADD question", act and all("ADD question" in x["action"] and "(held)" in x["action"] for x in act), str(act))
    check("no close_below exit on a held name's hold card (the broker stop is the exit)",
          not any(x["kind"] == "close_below" for x in v["triggers"]), str(v["triggers"]))
    check("kills names the broker stop", v.get("kills") == "The broker stop 391.8 is the exit.", v.get("kills"))
    check("confirms says it is the ADD question", str(v.get("confirms", "")).startswith("ADD question: "))
    check("no not_structured_yet when a shared add line exists", "not_structured_yet" not in v)
    check("the held row stays in cards['held']", "V" in c["held"] and "MP" in c["held"])
    orig = json.load(open(os.path.join(NOV2, "cards.tool_original.json")))
    same = all(c[k].get(t) == orig[k][t] for k in orig for t in orig[k])
    check("every other card is unchanged from the 2 Nov tool output", same)
    # LEVELS: the original tool output is refused, the fixed one writes with no conductor patch
    rc0, log0 = _emit(d, os.path.join(NOV2, "cards.tool_original.json"))
    check("the 2 Nov tool output (no V hold card) is still refused by LEVELS", rc0 == 2 and "V: HOLD_FOR_CONDITIONS" in log0, log0[-300:])
    rc, log = _emit(d, out)
    check("pma_levels.py emit succeeds on the fixed cards, no conductor patch", rc == 0, log[-300:])
    if rc != 0: return
    doc = json.load(open(os.path.join(d, "lv.json")))
    R = {(r["ticker"], r["class"]): r for r in doc["rows"]}
    hv = R.get(("V", "HOLD_FOR_CONDITIONS")) or {}
    check("the levels file carries V's HOLD row with the 414.6 add trigger",
          any(x["level"] == 414.6 and x["priority"] == "ACTION" for x in hv.get("triggers") or []), str(hv)[:300])
    check("and V's HELD row beside it (broker stop 391.8)", (R.get(("V", "HELD")) or {}).get("broker_stop", {}).get("stop") == 391.8)


def test_a_held_hold_with_no_shared_buy_is_declared_not_structured(td):
    """No shared add line: no trigger is invented from one analyst's level; the reason is stated, LEVELS writes."""
    pc = _mod("pc_hh", CARDS)
    cond = json.load(open(os.path.join(NOV2, "conditions.json")))
    for r in cond["rows"]:
        if r["ticker"] == "V":
            r["shared"]["buy"] = []
            r["shared"]["no_shared_buy"] = True
    c = pc.build_triggers(cond, json.load(open(os.path.join(NOV2, "export.json"))), json.load(open(os.path.join(NOV2, "broker_stops.json"))))
    v = c["hold"].get("V") or {}
    check("a held hold with no shared buy has no trigger", v.get("triggers") == [], str(v.get("triggers")))
    check("and a stated not_structured_yet reason", "no shared add line" in str(v.get("not_structured_yet")), str(v))
    check("the broker stop is still the stated exit", v.get("kills") == "The broker stop 391.8 is the exit.")
    d = os.path.join(td, "heldhold2"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "cards.json"); json.dump(c, open(p, "w"))
    rc, log = _emit(d, p)
    check("LEVELS writes it (a stated reason is the contract)", rc == 0 and "not yet structured" in log and "V" in log, log[-300:])


# --------------------------------------------------------------------------------- 2. R41 Valen off tickets
def _render_dir(td, name, valen=None, slate=None, held=False):
    d = os.path.join(td, name); os.makedirs(d, exist_ok=True)
    cons = [{"ticker": "AAA", "verdict": "ADVANCE", "conviction": 3, "lane": "MOMENTUM", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}},
            {"ticker": "BBB", "verdict": "HOLD-FOR-CONDITIONS", "conviction": 2, "lane": "PULLBACK", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}},
            {"ticker": "CCC", "verdict": "PASS", "conviction": 2, "lane": "PULLBACK", "split": {"support": [], "oppose": [], "abstain": []}, "advisory": {}}]
    setups = [{"setup": "Parabolic", "status": "WATCH", "checks": [{"result": "PASS"}]},
              {"setup": "Failed leader", "status": "WATCH", "checks": []},
              {"setup": "VCP", "status": "READY", "checks": [{"result": "PASS"}]}]
    exp = {"daily_list": [{"ticker": t, "entry": 10.0, "rank": i, "gics_sector_name": "Tech", "setups": setups,
                           "unr_status": "MET", "unr_note": "back above the 21-day"} for i, t in enumerate(["AAA", "BBB", "CCC"], 1)],
           "held_positions": []}
    cards = {"advance": {"AAA": {"triggers": [{"id": "AAA-buy0", "kind": "close_above", "level": 10.5}, {"id": "AAA-dead", "kind": "close_below", "level": 9.5}], "confirms": "x", "kills": "y"}},
             "hold": {"BBB": {"triggers": [], "confirms": "", "kills": "", "not_structured_yet": "none"}}, "held": {}}
    p4 = {"ranked": [{"ticker": t, "lane": c["lane"]} for t, c in zip(["AAA", "BBB", "CCC"], cons)], "deliberation_set": ["AAA", "BBB", "CCC"]}
    for n, x in (("consensus.json", cons), ("export.json", exp), ("cards.json", cards), ("phase4.json", p4)):
        json.dump(x, open(os.path.join(d, n), "w"))
    words = {"session_label": "s", "stance_pill": "NEUTRAL", "bottom_line": {"headline": "h", "paragraph": "p", "stats": [{"value": "1", "label": "l"}] * 4},
             "market": {"what_happened": [{"lead": "a", "text": "b"}], "weather": [{"lead": "c", "text": "d"}]},
             "money": [{"group": "g", "read": "r", "meaning": "m"}], "book": [], "changed": ["c"],
             "cards": {"AAA": {"case": "c", "why": "w", "reason": {"agree": "A leader in a strong group breaking out on heavy buying.", "wrong_if": "It closes back under the breakout.", "wait_for": "An hourly close above the buy line."}, "readiness": "Ready now", "readiness_tone": "ok"}},
             "holds": {"BBB": "waits"}, "passes": {"CCC": "no"}, "plan": ["p"], "caveats": ["c"]}
    vpath = os.path.join(d, "nov.json")
    if valen is not None:
        vpath = os.path.join(d, "valen.json"); json.dump(valen, open(vpath, "w"))
        words["weather"] = {k: f"Read: {k}." for k in ("stance", "gex", "heartbeat", "positioning", "volatility", "divergence",
                                                        "call", "cot", "checklist", "turning", "themes", "groups")}
    tw = os.path.join(d, "words.json"); json.dump(words, open(tw, "w"))
    spath = os.path.join(d, "noslate.json")
    if slate is not None:
        spath = os.path.join(d, "slate.json"); json.dump(slate, open(spath, "w"))
    out = os.path.join(d, "r.html")
    rc, log = run([CARDS, "render", "--text", tw, "--consensus", os.path.join(d, "consensus.json"), "--export", os.path.join(d, "export.json"),
                   "--cards", os.path.join(d, "cards.json"), "--phase4", os.path.join(d, "phase4.json"), "--brackets", os.path.join(d, "nob.json"),
                   "--broker-stops", os.path.join(d, "nobs.json"), "--valen", vpath, "--crown", os.path.join(d, "nocr.json"),
                   "--scorecard", os.path.join(d, "nosc.md"), "--slate", spath, "--out", out])
    return rc, log, (open(out).read() if rc == 0 else "")


VALEN = {"read_me_first": {"as_of": "2026-11-02", "headline": "h", "so_what": "half size", "because": [], "watch_for": []},
         "stance": {"word": "NEUTRAL", "status": "OK"}, "regime": "CHOP",
         "trend": [{"symbol": "SPY", "last_price": 680.1, "daily_buy_signal": True, "weekly_buy_signal": False, "above_rising_5d": True}],
         "extension": [{"label": "VIX/VIX3M", "value": 0.86}], "breadth": [], "gex": {}, "history": [], "neighbourhood": [],
         "theme_leaders": [], "rotation": [],
         "selection": {"no_buy_list": [{"ticker": "AAA", "flags": [{"label": "4.2 ATR extended"}]},
                                       {"ticker": "BBB", "flags": [{"label": "parabolic run"}]},
                                       {"ticker": "CCC", "flags": [{"label": "under the 50-day"}]}]},
         "house": {"setups": []}, "management": {}}


def test_valen_risk_flags_are_off_the_cards(td):
    """R41 (PM 2026-11-02): "Valen risk do not need to appear at ticket selection level". A no-buy flag on every
    room name and a parabolic / failed-leader grade on every row print NOWHERE on the Cards page; the weather,
    the house setups and U&R (facts) still do."""
    rc, log, h = _render_dir(td, "r41cards", valen=VALEN)
    check("cards render with a Valen file carrying a no-buy list", rc == 0, log[-300:])
    if rc != 0: return
    for bad in ("no-buy", "NO-BUY", "No-buy", "arabolic", "Failed leader", "4.2 ATR extended", "under the 50-day"):
        check(f"no '{bad}' anywhere on the Cards page", bad not in h)
    check("Valen stays as Part 1 weather (stance pill and trend table)", "Part 1 · Daily weather" in h and "NEUTRAL" in h and "SPY" in h)
    check("the house setup FACT stays on the ADVANCE card", "VCP READY" in h)
    check("the U&R fact stays on the card and the hold row", h.count("Valen undercut-and-rally: reclaim day") >= 2)


def test_the_vote_packet_has_no_valen_risk_block(td):
    """R41: the R37 RISK block (no-buy flags, parabolic warnings) is gone from the vote packet; the stance /
    trend / extension / breadth / gamma weather lines and the per-name setup + U&R rows stay."""
    ex = json.load(open(fx("export.json"))); p4 = json.load(open(fx("phase4.json")))
    t0 = p4["deliberation_set"][0]
    for row in ex["daily_list"]:
        if row["ticker"] == t0:
            row["setups"] = [{"setup": "Parabolic", "status": "WATCH", "checks": [{"result": "PASS"}]},
                             {"setup": "VCP", "status": "READY", "checks": [{"result": "PASS"}, {"result": "FAIL"}]}]
    exp = os.path.join(td, "r41_export.json"); json.dump(ex, open(exp, "w"))
    val = dict(VALEN, selection={"no_buy_list": [{"ticker": t0, "flags": [{"label": "4.2 ATR extended"}]}]},
               breadth=[{"label": "T2108", "value": 41.0}], gex={"ticker": "SPY", "regime": "POSITIVE", "flip": 670})
    vp = os.path.join(td, "r41_valen.json"); json.dump(val, open(vp, "w"))
    out = os.path.join(td, "r41_packet.txt")
    rc, log = run([PIPE, "r2digest", "--export", exp, "--phase4", fx("phase4.json"), "--tally", fx("tally.json"),
                   "--fundamentals", fx("fundamentals.json"), "--steenbarger", fx("challenge_steenbarger.json"),
                   "--valen", vp, "--run-id", "t", "--out", out])
    check("r2digest runs with a Valen no-buy list", rc == 0, log[-300:])
    if rc != 0: return
    txt = open(out).read()
    check("no '==== RISK (Valen' block in the vote packet", "==== RISK (Valen" not in txt)
    check("no no-buy flag text anywhere in the packet", "4.2 ATR extended" not in txt and "no-buy" not in txt.lower())
    check("no parabolic warning anywhere in the packet", "arabolic WATCH" not in txt)
    check("the weather lines stay (stance, trend, extension, breadth, gamma)",
          "stance NEUTRAL" in txt and "trend SPY" in txt and "extension VIX/VIX3M" in txt and "breadth T2108" in txt and "gamma SPY" in txt)
    row = next((l for l in txt.splitlines() if l.strip().startswith(f"{t0}: setups")), "")
    check("the per-name setup + U&R row stays", "VCP READY (1/2)" in row and "U&R" in row, row)


# ------------------------------------------------------------------------------------- 3. R40 market kill
MK = {"plain": "SPY closes under the 750 put wall", "word": "close_below:put_wall", "symbol": "SPY", "level": 750.0,
      "seats": ["raschke", "elder-lens", "wyckoff"]}


def test_the_market_kill_line_reaches_the_levels_file(td):
    """R40: the slate's ONE market condition rides into pma_levels.json as top-level market_kill, so the alert
    loop can say "market condition broken -- take no new triggers". Today's wins over history; null is declared."""
    d = os.path.join(td, "mk"); os.makedirs(d, exist_ok=True)
    P = lambda n: os.path.join(d, n)
    cards = P("cards.json")
    run([CARDS, "triggers", "--conditions", os.path.join(NOV2, "conditions.json"), "--export", os.path.join(NOV2, "export.json"),
         "--broker-stops", os.path.join(NOV2, "broker_stops.json"), "--out", cards])
    json.dump({"date": "2026-11-02", "chair": "chair", "tickets": [], "market_kill": MK}, open(P("slate.json"), "w"))
    json.dump({"run_date": "2026-10-30", "rows": [], "market_kill": {"plain": "OLD LINE", "symbol": "QQQ", "level": 1.0,
                                                                     "word": None, "seats": [], "origin_run": "2026-10-30"}},
              open(P("hist.json"), "w"))
    rc, log = _emit(d, cards, ["--slate", P("slate.json"), "--history", P("hist.json")])
    check("emit with --slate exits clean", rc == 0, log[-300:])
    if rc != 0: return
    doc = json.load(open(P("lv.json")))
    mk = doc.get("market_kill") or {}
    check("market_kill is top level with symbol, word, level, plain, seats, origin_run",
          set(mk) == {"symbol", "word", "level", "plain", "seats", "origin_run"}, str(mk))
    check("the values are copied from the slate", mk.get("symbol") == "SPY" and mk.get("level") == 750.0
          and mk.get("plain") == MK["plain"] and mk.get("seats") == MK["seats"] and mk.get("word") == MK["word"])
    check("origin_run is today's run", mk.get("origin_run") == "2026-11-02")
    check("today's market kill wins over the history file's", "OLD LINE" not in json.dumps(doc))
    check("no note when a line is present", "market_kill_note" not in doc)
    json.dump({"date": "2026-11-02", "chair": "chair", "tickets": [], "market_kill": None}, open(P("slate.json"), "w"))
    rc, log = _emit(d, cards, ["--slate", P("slate.json"), "--history", P("hist.json")])
    doc = json.load(open(P("lv.json"))) if rc == 0 else {}
    check("a null market kill is published as null, never carried from history",
          rc == 0 and "market_kill" in doc and doc["market_kill"] is None, log[-300:])
    check("and declared with the note", doc.get("market_kill_note") == "no seat named a market condition", str(doc.get("market_kill_note")))
    rc, log = _emit(d, cards)
    doc = json.load(open(P("lv.json"))) if rc == 0 else {}
    check("without --slate the file is unchanged (no market_kill key)", rc == 0 and "market_kill" not in doc)
    json.dump({"date": "2026-11-02", "chair": "chair", "tickets": [], "market_kill": dict(MK, plain="")}, open(P("slate.json"), "w"))
    rc, log = _emit(d, cards, ["--slate", P("slate.json")])
    check("a market kill with no plain words is REFUSED", rc == 2 and "market_kill" in log, log[-300:])
    json.dump({"date": "2026-11-02", "chair": "chair", "tickets": []}, open(P("slate.json"), "w"))
    rc, log = _emit(d, cards, ["--slate", P("slate.json")])
    doc = json.load(open(P("lv.json"))) if rc == 0 else {}
    check("a pre-R40 slate (no field) is declared, never silent",
          rc == 0 and doc.get("market_kill") is None and "pre-R40" in str(doc.get("market_kill_note")), log[-300:])
    check("no Valen flag reaches the levels file (R41)", "no_buy" not in open(P("lv.json")).read().lower())


def test_the_market_kill_line_prints_on_the_cards(td):
    """R40 on the PM's read: the bottom line card and every ADVANCE card say what voids the trade."""
    rc, log, h = _render_dir(td, "mkcards", slate={"date": "2026-11-02", "chair": "chair", "tickets": [], "market_kill": MK})
    check("cards render with a slate market kill", rc == 0, log[-300:])
    if rc != 0: return
    b, p1 = h.find("Bottom line"), h.find("Part 1 · Daily weather")
    mk = h.find("Market kill (R40)")
    check("the market kill line is on the Bottom line card", b >= 0 and b < mk < p1, f"{b} {mk} {p1}")
    check("the ADVANCE card says 'Void if' with the line", "<dt>Void if</dt><dd>SPY closes under the 750 put wall (raschke, elder-lens, wyckoff)</dd>" in h)
    rc, log, h2 = _render_dir(td, "mkcards2")
    check("without a slate there is no market kill text", rc == 0 and "Void if" not in h2 and "Market kill" not in h2, log[-300:])
    rc, log, h3 = _render_dir(td, "mkcards3", slate={"date": "2026-11-02", "chair": "chair", "tickets": [], "market_kill": None})
    check("a null market kill is declared on the bottom line, never invented",
          rc == 0 and "no seat named a market condition" in h3 and "Void if" not in h3, log[-300:])


# ----------------------------------------------------------------------------------------- 4. R39 mtf.py
def _sessions(n, end="2026-10-30"):
    """n weekday dates ending on `end`, oldest first."""
    d, out = dt.date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def _bars(dates, closes, spread=0.5, green=True):
    return [{"date": t, "open": c - 0.2 if green else c + 0.2, "high": c + spread, "low": c - spread, "close": c, "volume": 1000}
            for t, c in zip(dates, closes)]


def _h1(day_list, per_day=7, base=100.0):
    out, i = [], 0
    for day in day_list:
        for h in range(per_day):
            c = base + i
            out.append({"date": f"{day} {10 + h:02d}:30:00", "open": c - 0.1, "high": c + 0.3, "low": c - 0.3, "close": c, "volume": 10})
            i += 1
    return out


def test_mtf_maths_known_values(td):
    """EMA and weekly bars against values worked by hand. A linear series 1..30 with an SMA seed sits exactly
    (n-1)/2 behind the price: EMA9 = 30 - 4 = 26, EMA21 = 30 - 10 = 20. A constant series has EMA = the price."""
    m = _mod("mtf_t", MTF)
    lin = [float(i) for i in range(1, 31)]
    check("EMA9 of 1..30 is 26 (SMA seed, linear steady state)", abs(m.ema(lin, 9) - 26.0) < 1e-9, str(m.ema(lin, 9)))
    check("EMA21 of 1..30 is 20", abs(m.ema(lin, 21) - 20.0) < 1e-9, str(m.ema(lin, 21)))
    check("EMA of a constant series is the constant", abs(m.ema([7.5] * 40, 21) - 7.5) < 1e-12)
    check("EMA with fewer bars than its length is None", m.ema([1.0] * 20, 21) is None)
    # two ISO weeks, Mon 2026-10-19 .. Fri 2026-10-30, given out of order
    days = _sessions(10)
    d = [{"date": t, "open": 10 + i, "high": 20 + i, "low": 5 + i, "close": 11 + i, "volume": 100 + i} for i, t in enumerate(days)]
    wk = m.weekly(m._clean(list(reversed(d))))
    check("daily bars in any order become 2 ISO weeks", len(wk) == 2, str(wk))
    if len(wk) == 2:
        w1, w2 = wk
        check("week 1: open = first, high = max, low = min, close = last, volume = sum",
              (w1["open"], w1["high"], w1["low"], w1["close"], w1["volume"]) == (10, 24, 5, 15, sum(100 + i for i in range(5))), str(w1))
        check("week 2 is dated by its last session (Fri 30 Oct) and labelled 2026-W44",
              w2["date"] == "2026-10-30" and w2["week"] == "2026-W44" and w2["open"] == 15 and w2["close"] == 20, str(w2))


def test_mtf_build_grid_and_declared_gaps(td):
    """mtf.py build: every room name gets a row. A rising name reads above EMA9, 9>21, HH/HL at its 20-bar high on
    every frame; a name with no bars file and a courier-declared unserved name are NOT SERVED with their reason;
    a name with fewer than 21 hourly bars has H1 NOT SERVED while W and D are served."""
    d = os.path.join(td, "mtf"); bars = os.path.join(d, "mtf_bars"); os.makedirs(bars, exist_ok=True)
    days = _sessions(160)
    up = [100.0 + i for i in range(160)]
    json.dump({"daily": list(reversed(_bars(days, up))), "h1": _h1(days[-5:])}, open(os.path.join(bars, "UPP.json"), "w"))
    json.dump({"daily": _bars(days, up), "h1": _h1(days[-2:], per_day=7)}, open(os.path.join(bars, "SHH.json"), "w"))
    json.dump({"unserved": True}, open(os.path.join(bars, "UNS.json"), "w"))
    # a future bar (after --date) must be dropped, never read
    fut = _bars(days, up) + [{"date": "2026-11-03", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    json.dump({"daily": fut, "h1": _h1(days[-5:])}, open(os.path.join(bars, "FUT.json"), "w"))
    room = ["UPP", "SHH", "MIS", "UNS", "FUT"]
    json.dump({"deliberation_set": room}, open(os.path.join(d, "phase4.json"), "w"))
    json.dump({"daily_list": [{"ticker": "UPP", "entry": 259.0}, {"ticker": "SHH", "entry": 200.0}]}, open(os.path.join(d, "export.json"), "w"))
    out = os.path.join(d, "mtf.json")
    rc, log = run([MTF, "build", "--bars", bars, "--phase4", os.path.join(d, "phase4.json"), "--export", os.path.join(d, "export.json"),
                   "--date", "2026-11-02", "--out", out])
    check("mtf.py build exits clean", rc == 0, log[-300:])
    if rc != 0: return
    g = json.load(open(out))
    check("schema mtf.v1, date and the three frames", g["schema"] == "mtf.v1" and g["date"] == "2026-11-02" and g["frames"] == ["W", "D", "H1"])
    check("every room name has a row", set(g["names"]) == set(room), str(list(g["names"])))
    u = g["names"]["UPP"]
    check("a rising name is served on all three frames", u["served"] and all(u[f]["served"] for f in ("W", "D", "H1")), str(u.get("reason")))
    D = u["D"]
    check("D: close 259, EMA9 255, EMA21 249 (linear steady state)",
          (D["close"], D["ema9"], D["ema21"]) == (259.0, 255.0, 249.0), str((D["close"], D["ema9"], D["ema21"])))
    check("D: above EMA9, 9>21, green, HH/HL", (D["close_vs_ema9"], D["ema_order"], D["last_bar"], D["hh_hl_3"]) == ("above", "9>21", "green", "HH/HL"), str(D))
    check("D: distance to the 20-day high is the half-spread (259.5 high vs 259 close)", D["dist_to_20bar_high_pct"] == round(0.5 / 259.5 * 100, 2), str(D["dist_to_20bar_high_pct"]))
    W = u["W"]
    check("W: weekly bars built from 160 sessions (32 weeks), last week complete on a Monday run",
          W["bars"] == 32 and W["close"] == 259.0 and not W.get("partial_last_bar"), str((W.get("bars"), W.get("close"))))
    H = u["H1"]
    check("H1: 35 hourly bars, close at the top of the day's range", H["bars"] == 35 and H["pos_in_day_range_pct"] == round((134 - 127.7) / (134.3 - 127.7) * 100, 1), str(H))
    check("D close matches the export's close", D.get("close_matches_export") is True)
    check("the name summary joins the three frames in plain words",
          u["summary"].startswith("W: above EMA9, 9>21, HH/HL") and " | D: " in u["summary"] and " | H1: " in u["summary"], u["summary"])
    check("a frame summary names its distance to the 20-bar high", "% under 20-day high" in u["summary"], u["summary"])
    s = g["names"]["SHH"]
    check("< 21 hourly bars: H1 NOT SERVED while W and D are served",
          s["W"]["served"] and s["D"]["served"] and not s["H1"]["served"] and "14 hr bars" in s["H1"]["reason"], str(s["H1"]))
    check("a partial grid is not a served name, and says why", s["served"] is False and "H1 not served" in (s["reason"] or "") and "H1: NOT SERVED" in s["summary"])
    check("a close that disagrees with the export is declared", s["D"].get("close_matches_export") is False and "SHH" in g["measurement"]["close_mismatch_vs_export"])
    mi = g["names"]["MIS"]
    check("a name with no bars file is NOT SERVED with the reason, row still present",
          mi["served"] is False and "no bars file" in mi["reason"] and mi["summary"].startswith("MTF NOT SERVED") and not mi["W"]["served"])
    check("a courier-declared unserved name is NOT SERVED", g["names"]["UNS"]["served"] is False and "unserved" in g["names"]["UNS"]["reason"])
    f = g["names"]["FUT"]
    check("a bar dated after the run is dropped, never read", f.get("dropped_future_bars") == 1 and f["D"]["close"] == 259.0, str(f.get("D", {}).get("close")))
    m = g["measurement"]
    check("measurement counts served and not served", (m["served"], m["not_served"]) == (2, 3) and m["not_served_names"] == ["MIS", "SHH", "UNS"], str(m))


def test_mtf_stale_and_partial_week_are_declared(td):
    """Stale-but-present is a failure, not a reading; a week still open on the run date is flagged, and the
    HH/HL test reads completed weeks only."""
    m = _mod("mtf_t2", MTF)
    days = _sessions(160, end="2026-10-30")
    up = [100.0 + i for i in range(160)]
    r = m.build_name("OLD", {"daily": _bars(days, up), "h1": _h1(days[-5:])}, "2026-11-20")
    check("a last daily bar 21 days old is NOT SERVED as stale", r["served"] is False and "stale" in r["D"]["reason"] and "stale" in r["W"]["reason"], str(r.get("reason")))
    r = m.build_name("MID", {"daily": _bars(days, up), "h1": _h1(days[-5:])}, "2026-10-30")
    check("a run inside an open week flags the weekly bar as partial", r["W"].get("partial_last_bar") is True and "this week still open" in r["summary"], r["summary"])
    src = open(MTF).read()
    check("mtf.py is pure python (no pandas / numpy)", "import pandas" not in src and "import numpy" not in src)


# ------------------------------------------------------------------------------------------ 5. seat docs
def test_the_seat_docs_carry_the_two_tier_funnel(td):
    """R38-R40 reach the seats and the Chair in their own cards."""
    core = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    vd = open(os.path.join(os.path.dirname(core), "aegis-voices", "skills", "voice-deliberate", "SKILL.md")).read()
    for k in ("THE CLAIMS BOARD", "TIER 1", "TIER 2", "RATIFY", "THE RECORD", "CONFIRM", "REFUTE", "CANNOT_SEE",
              "stance_after", "ACT_NOW", "WAIT", "wrong_if", "market_void", "OBJECT"):
        check(f"voice-deliberate carries {k}", k in vd)
    ch = open(os.path.join(core, "agents", "chair.md")).read()
    check("the Chair runs board / claims / claims-score / pair / decide-timing",
          all(k in ch for k in ("board", "claims-score", "pair", "decide-timing")) and "never votes" in ch.lower())
    check("the Chair copies market_kill and keeps the hold round on floor messages", "market_kill" in ch and "floor2" in ch)
    sk = open(os.path.join(core, "skills", "pma", "SKILL.md")).read()
    check("SKILL.md has THE FUNNEL (R38–R41) and the 39-spawn chain",
          "THE FUNNEL (R38–R41)" in sk and "39 spawns" in sk and "TIER2 7" in sk and "MTF courier" in sk)


def main():
    print("AEGIS PMA -- cards, levels and the multi-timeframe grid (R38-R41)\n")
    with tempfile.TemporaryDirectory() as td:
        for fn in [test_a_held_name_on_hold_gets_its_add_card,
                   test_a_held_hold_with_no_shared_buy_is_declared_not_structured,
                   test_valen_risk_flags_are_off_the_cards,
                   test_the_vote_packet_has_no_valen_risk_block,
                   test_the_market_kill_line_reaches_the_levels_file,
                   test_the_market_kill_line_prints_on_the_cards,
                   test_mtf_maths_known_values,
                   test_mtf_build_grid_and_declared_gaps,
                   test_mtf_stale_and_partial_week_are_declared,
                   test_the_seat_docs_carry_the_two_tier_funnel]:
            print(fn.__name__.replace("test_", "").replace("_", " ") + ":")
            try:
                fn(td)
            except Exception as e:
                check(fn.__name__ + " raised", False, repr(e))
            print()
    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        print("FAILED:"); [print("  - " + f) for f in FAILS]
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
