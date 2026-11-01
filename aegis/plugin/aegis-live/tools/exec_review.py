#!/usr/bin/env python3
"""Executive 30-minute review of the PMA book.  READ-ONLY: places nothing, sizes nothing.

Reads the day's published action plan (pma_levels.json) and live prices, and prints a short
plain-English review that shows only what matters and what CHANGED since the previous review.

Inputs
  --levels   pma_levels.json of the current PMA run (ticker action plans)
  --export   aqe_daily_export.json of the same run (20-day average volume)
  --prices   JSON {TICKER: {"last":..,"prior_close":..,"high":..,"low":..}} from IBKR snapshots (SPY included)
  --bars     optional JSON {TICKER: [FMP 1-hour bars, newest first]} - only needed for names the first pass
             lists under NEEDS BARS (price is above the buy price and a confirmed candle close must be checked)
  --watch    pm_watch.json (PM discretion names, labelled 'your watch')
  --state    previous-review state file (written back after each review)
Market gates (from the market action plan, Part 1): --floor 760 (put wall), --flip 777.85 (gamma flip).
Wording rule: never prints 'line', 'hourly close' or 'AQE default' (PM-approved format).
"""
import argparse, json, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET, SGT = ZoneInfo("America/New_York"), ZoneInfo("Asia/Singapore")
# share of a normal day's volume done by each ET clock time (same curve as check.py)
CURVE = [(9.5, 0.0), (10.5, 0.24), (11.5, 0.36), (12.5, 0.46), (13.5, 0.55), (14.5, 0.65), (15.5, 0.77), (16.0, 1.0)]
NEAR_PCT = 0.5  # a name is 'near' when within this % below its buy price


def curve(now_et):
    h = now_et.hour + now_et.minute / 60
    if h <= CURVE[0][0]:
        return 0.0
    for (h0, v0), (h1, v1) in zip(CURVE, CURVE[1:]):
        if h <= h1:
            return v0 + (v1 - v0) * (h - h0) / (h1 - h0)
    return 1.0


def pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def day_chg(p, ref=None):
    """Day change %: IBKR's own change_pct if given, else last vs prior close (or the plan's last close)."""
    if p.get("change_pct") is not None:
        return float(p["change_pct"])
    return pct(p.get("last"), p.get("prior_close") or ref)


def fmt(x, nd=2):
    return "-" if x is None else f"{x:,.{nd}f}"


def plan(r, run_date):
    """Pull the ticker action plan out of one pma_levels row."""
    trig = r.get("triggers") or []
    buy = next((t for t in trig if t["kind"] == "close_above" and t.get("basis") == "15m"), None)
    kill = next((t for t in trig if t["kind"] == "close_below" and t.get("basis") == "daily"), None)
    sh = (r.get("conditions") or {}).get("shared") or {} if isinstance(r.get("conditions"), dict) else {}
    ch = (sh.get("chase") or {}).get("levels") or []
    lvl = r.get("levels") or {}
    buy_l = buy["level"] if buy else None
    late = ch[0] if ch else None
    late_ok = late is not None and (buy_l is None or late > buy_l)  # a too-late price at/under the buy price is a stale value
    return {
        "buy": buy_l, "vol_x": (buy or {}).get("volume_min_x"), "kill": kill["level"] if kill else None,
        "late": late if late_ok else None, "late_stale": late is not None and not late_ok,
        "stop": lvl.get("stop"), "tp": lvl.get("tp") or [], "ref": lvl.get("ref_close"),
        "lane": r.get("lane"), "carried": r.get("origin_run") not in (None, run_date),
        "origin": r.get("origin_run"),
    }


def classify(t, p, pl, spy_chg, bars, now_et, avgv):
    """Return (state, detail). States ordered by urgency."""
    last = p.get("last")
    chg = day_chg(p, pl["ref"])
    if pl["kill"] and last is not None and last <= pl["kill"]:
        return "UNDER KILL", f"trading under the kill price {fmt(pl['kill'])} - the case is dead if it closes there"
    if pl["late"] and last is not None and last > pl["late"]:
        return "TOO LATE", f"above {fmt(pl['late'])}: the move has run, do not chase"
    if pl["buy"] is None:
        return "NO BUY PRICE", "the committee set no buy price - wait for a reset"
    gap = pct(last, pl["buy"])
    if last is not None and last > pl["buy"]:
        if not bars:
            return "ABOVE BUY", "above the buy price, candle close not yet checked"
        done = sorted([b for b in bars if b["date"][:10] == now_et.strftime("%Y-%m-%d")
                       and datetime.strptime(b["date"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=1) <= now_et.replace(tzinfo=None)],
                      key=lambda b: b["date"])
        if not done or done[-1]["close"] <= pl["buy"]:
            return "ABOVE BUY", "above the buy price, waiting for a candle to close above it"
        vol = p.get("volume") or sum(b["volume"] for b in bars if b["date"][:10] == now_et.strftime("%Y-%m-%d"))
        pace = vol / (avgv * max(curve(now_et), 0.05)) if avgv else None
        beats = chg is not None and spy_chg is not None and chg > spy_chg
        vol_ok = pl["vol_x"] is None or (pace is not None and pace >= pl["vol_x"])
        miss = [m for m, ok in (("volume", vol_ok), ("beating SPY", beats)) if not ok]
        extra = f"volume {fmt(pace, 1)}x normal (needs {pl['vol_x']}x)" if pl["vol_x"] else "volume not required"
        if miss:
            return "CLOSED ABOVE, NOT CLEAN", f"candle closed above {fmt(pl['buy'])} but missing {' and '.join(miss)}; {extra}"
        return "BUY CONFIRMED", f"candle closed above {fmt(pl['buy'])}; {extra}; beating SPY"
    if gap is not None and -gap <= NEAR_PCT:
        return "NEAR", f"{abs(gap):.2f}% under the buy price {fmt(pl['buy'])}"
    return "WAITING", f"{abs(gap):.1f}% under the buy price {fmt(pl['buy'])}" if gap is not None else "no price"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="/home/claude/pma/d23/pma_levels.json")
    ap.add_argument("--export", default="/home/claude/pma/d23/aqe_daily_export.json")
    ap.add_argument("--prices", required=True)
    ap.add_argument("--bars")
    ap.add_argument("--watch", default="/home/claude/pma/live/pm_watch.json")
    ap.add_argument("--state", default="/home/claude/pma/live/review_state.json")
    ap.add_argument("--floor", type=float, default=760.0)
    ap.add_argument("--flip", type=float, default=777.85)
    ap.add_argument("--spy-close", type=float, help="close of SPY's latest COMPLETED hourly candle today (FMP intraday-1-hour); below the floor = stand down until a candle closes back above it")
    ap.add_argument("--now", help="override ET time 'YYYY-MM-DD HH:MM' (testing)")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()

    now_et = datetime.strptime(a.now, "%Y-%m-%d %H:%M").replace(tzinfo=ET) if a.now else datetime.now(ET)
    now_sgt = now_et.astimezone(SGT)
    lv = json.load(open(a.levels)); run_date = lv["run_date"]
    ex = json.load(open(a.export)) if os.path.exists(a.export) else {"daily_list": []}
    exrows = {r["ticker"]: r for r in ex.get("daily_list", [])}
    prices = json.load(open(a.prices))
    bars_all = json.load(open(a.bars)) if a.bars else {}
    prev = {}
    if os.path.exists(a.state):
        s = json.load(open(a.state))
        if s.get("session") == now_et.strftime("%Y-%m-%d"):
            prev = s
    prev_st = prev.get("states", {})

    spy = prices.get("SPY") or {}
    spy_last = spy.get("last")
    spy_ref = (exrows.get("SPY") or {}).get("entry")
    spy_chg = day_chg(spy, spy_ref)
    out, states, needs_bars = [], {}, []
    hdr = f"Review {now_sgt:%H:%M} SGT ({now_et:%H:%M} ET)" + (f" · vs {prev['label']}" if prev else " · first review of the session")
    out.append(hdr)

    # ---- market
    if spy_last is None:
        mkt = "SPY price unavailable - no new buys until it is back"; mstate = "NO DATA"
    else:
        d_floor = pct(spy_last, a.floor)
        if a.spy_close is not None and a.spy_close < a.floor:
            mstate, mkt = "FLOOR BROKEN", f"SPY's last completed hourly candle closed {a.spy_close:.2f}, under {a.floor:g}: stand down on new buys until a candle closes back above it"
        elif spy_last < a.floor:
            mstate, mkt = "FLOOR BROKEN", f"SPY is {abs(d_floor):.2f}% UNDER {a.floor:g}: stand down on new buys"
        elif d_floor < 0.3:
            mstate, mkt = "FLOOR AT RISK", f"SPY is only {d_floor:.2f}% above {a.floor:g}: new buys only on a confirmed close, small"
        elif spy_last >= a.flip:
            mstate, mkt = "CALM", f"SPY is above the {a.flip:g} swing-calming level: normal conditions"
        else:
            mstate, mkt = "HOLDING", f"SPY {d_floor:.2f}% above the {a.floor:g} floor, still under {a.flip:g}: swings stay amplified, confirmed closes only"
    spy_low = spy.get("low")
    if spy_low and spy_low > 0 and spy_low < a.floor and spy_last is not None and spy_last >= a.floor:
        mkt += f" · traded as low as {fmt(spy_low)} today, under {a.floor:g}, and recovered"
    out.append(f"**Market** SPY {fmt(spy_last)} ({fmt(spy_chg)}% on day) · {mkt}")
    states["_MKT"] = mstate

    rows, notes = {}, []
    for r in lv["rows"]:
        if r["class"] == "ADVANCE":
            rows[r["ticker"]] = r
    held = [r for r in lv["rows"] if r["class"] == "HELD"]
    hs = {r["ticker"] for r in held}

    # ---- committee picks
    act, near, late_, dead, wait = [], [], [], [], []
    for t, r in rows.items():
        p = prices.get(t)
        pl = plan(r, run_date)
        if not p or p.get("last") is None:
            notes.append(f"{t}: no live price"); continue
        avgv = (((exrows.get(t) or {}).get("elder_context") or {}).get("volume") or {}).get("avg_vol_20d")
        st, detail = classify(t, p, pl, spy_chg, bars_all.get(t), now_et, avgv)
        if st == "ABOVE BUY" and t not in bars_all:
            needs_bars.append(t)
        chg = day_chg(p, pl["ref"])
        stop_txt = f"{fmt(pl['stop'])} ({fmt(pct(pl['stop'], p['last']), 1)}%)" if pl["stop"] else "-"
        tp = " / ".join(fmt(x) for x in pl["tp"][:2]) if pl["tp"] else "-"
        row = (t, p["last"], chg, st, detail, pl, stop_txt, tp)
        states[t] = st
        (act if st in ("BUY CONFIRMED", "CLOSED ABOVE, NOT CLEAN", "ABOVE BUY") else near if st == "NEAR"
         else late_ if st == "TOO LATE" else dead if st == "UNDER KILL" else wait).append(row)
        if pl["late_stale"]:
            notes.append(f"{t}: carried row's too-late price is at/under its buy price - ignored (stale)")

    def table(title, items, cols):
        if not items:
            return
        out.append(f"\n**{title}**")
        out.append("| " + " | ".join(cols) + " |")
        out.append("|" + "|".join("---" for _ in cols) + "|")
        for it in items:
            out.append("| " + " | ".join(str(x) for x in it) + " |")

    def nm(t, pl, st):
        return f"{t}{'*' if pl['carried'] else ''}{' (you hold)' if t in hs else ''}{tag(t, st)}"

    def tag(t, st):
        old = prev_st.get(t)
        return " ▲NEW" if prev and old is not None and old != st else (" ▲NEW" if prev and old is None else "")

    table("Act on (Your decision)", [(nm(t, pl, st), fmt(px), f"{fmt(chg)}%", st.title(),
                                       fmt(pl["buy"]), stop_txt, tp, d) for t, px, chg, st, d, pl, stop_txt, tp in act],
          ["Name", "Price", "Day", "State", "Buy above", "Stop (−%)", "Targets 1/2", "Detail"])
    table("Near the buy price (within 0.5%)", [(nm(t, pl, st), fmt(px), f"{fmt(chg)}%",
                                              fmt(pl["buy"]), stop_txt, d) for t, px, chg, st, d, pl, stop_txt, tp in near],
          ["Name", "Price", "Day", "Buy above", "Stop (−%)", "Gap"])
    table("Too late - do not chase", [(f"{t}{tag(t, st)}", fmt(px), fmt(pl["late"]), d) for t, px, chg, st, d, pl, stop_txt, tp in late_],
          ["Name", "Price", "Too late above", "Note"])
    table("Case broken", [(f"{t}{tag(t, st)}", fmt(px), fmt(pl["kill"]), d) for t, px, chg, st, d, pl, stop_txt, tp in dead],
          ["Name", "Price", "Kill price", "Note"])
    if wait:
        out.append("\n**Waiting (more than 0.5% under the buy price):** " + ", ".join(
            f"{t} {fmt(px)}/{fmt(pl['buy'])} ({abs(pct(px, pl['buy'])):.1f}%)" for t, px, chg, st, d, pl, stop_txt, tp in wait))

    # ---- your book
    book = []
    for r in held:
        t = r["ticker"]; p = prices.get(t) or {}; bs = (r.get("broker_stop") or {}).get("stop")
        if p.get("last") is None or not bs:
            notes.append(f"{t}: held, no live price or no broker stop"); continue
        atr = r.get("atr_14d") or 0
        dist = pct(p["last"], bs)
        low = p.get("low")
        if low and low > 0 and low <= bs:
            st = "STOP TOUCHED TODAY"
        elif p["last"] - bs <= 0.5 * atr:
            st = "NEAR STOP"
        else:
            st = "ok"
        states[f"HELD:{t}"] = st
        book.append((f"{t}{tag('HELD:' + t, st)}", r.get("qty"), fmt(p["last"]), f"{fmt(day_chg(p, r.get('live_px')))}%", fmt(bs), f"{dist:.1f}% above", st))
    table("Your book", book, ["Name", "Shares", "Price", "Day", "Broker stop", "Cushion", "State"])

    # ---- your watch
    if os.path.exists(a.watch):
        w = (json.load(open(a.watch)).get("names") or {})
        wr = []
        for t, d in w.items():
            p = prices.get(t) or {}
            if p.get("last") is None:
                continue
            px = p["last"]
            st = "ABOVE BREAKOUT" if px > d["breakout_line"] else ("IN EARLY ZONE" if px > d["early_line"] else "BELOW")
            states[f"WATCH:{t}"] = st
            wr.append((f"{t}{tag('WATCH:' + t, st)}", fmt(px), fmt(d["early_line"]), fmt(d["breakout_line"]),
                       fmt((d.get("stop_ref") or {}).get("range_low")), st.title()))
        table("Your watch (not committee)", wr, ["Name", "Price", "Early above", "Breakout above", "Exit / key low", "State"])

    # ---- delta and bottom line
    changed = [k for k, v in states.items() if prev and prev_st.get(k) != v and not (k not in prev_st and v in ("WAITING", "ok"))]
    out.append("")
    if prev:
        lab = lambda k: "Market" if k == "_MKT" else k.replace("HELD:", "book ").replace("WATCH:", "watch ")
        chg_line = "**Changed since last:** " + ("; ".join(f"{lab(k)} {prev_st.get(k, 'new').title()} → {states[k].title()}" for k in changed) if changed else "nothing")
    if needs_bars:
        print(f"NEEDS BARS: {','.join(needs_bars)}", file=sys.stderr)
    n_act = sum(1 for x in act if x[3] in ("BUY CONFIRMED",))
    if mstate in ("FLOOR BROKEN", "NO DATA"):
        bl = "Hold off on every new buy."
    elif n_act:
        bl = f"Your call on {n_act} confirmed buy{'s' if n_act > 1 else ''}; stops are in the table. Everything else: wait."
    elif near or [x for x in act if x[3] != 'BUY CONFIRMED']:
        bl = "Nothing confirmed yet. Watch the names near or above their buy price."
    else:
        bl = "No action. Nothing is near a buy price."
    if any(b[-1] != "ok" for b in book):
        bl = "Check your book first: " + ", ".join(b[0].replace(' ▲NEW', '') for b in book if b[-1] != "ok") + ". " + bl
    out.insert(2, f"**Bottom line:** {bl}")
    if prev:
        out.insert(3, chg_line)
    for n in notes:
        out.append(f"_note: {n}_")
    text = "\n".join(out)
    import re
    probe = text.replace("Bottom line", "")
    for bad in (r"\bline\b", r"hourly close", r"AQE default"):
        if re.search(bad, probe, re.I):  # warn, never crash a live review
            print(f"[wording check] banned phrase {bad!r} present", file=sys.stderr)
    print(text)
    if not a.no_save:
        json.dump({"session": now_et.strftime("%Y-%m-%d"), "label": f"{now_sgt:%H:%M}", "states": states}, open(a.state, "w"))
        with open(os.path.join(os.path.dirname(a.state), "review_log.jsonl"), "a") as f:
            f.write(json.dumps({"t": now_sgt.isoformat(), "spy": spy_last, "mkt": mstate, "states": states}) + "\n")


if __name__ == "__main__":
    main()
