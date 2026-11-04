#!/usr/bin/env python3
"""pma_cards.py -- the PM's committee card report, ONE fixed format (PM 2026-10-23).

WHY THIS EXISTS. The PM: "why is the PMA report format always changing, the cards form always
works the best". It changed because nothing fixed it: each run a model hand-wrote the HTML (an old
build_report.py carried 25-Sep prose hard-coded inside it and was rewritten by hand every morning).
This tool fixes the LAYOUT in code. The writer supplies only words, in cards_text.json, against a
fixed schema; every number on a card comes from the run's own files. Same page every day.

Two subcommands:

  triggers  conditions.json + export + broker_stops.json -> cards.json (the structured triggers
            LEVELS needs). Deterministic; replaces the hand-built cards step.
  render    run files + cards_text.json -> pma_cards_<date>.html (the report the PM reads).
            REFUSES (exit 2) if the words file misses an ADVANCE card, a HOLD line or a PASS line,
            or carries a ticker the committee did not vote on -- a gap is never silently blank.

Render-only. Nothing here places, changes, cancels or sizes an order. Verdicts are read, never set.
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import os
import re
import sys

E = html.escape


def load(p, default=None):
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit(f"pma_cards: required file missing: {p}")
    return json.load(open(p))


# ------------------------------------------------------------------------------------------ triggers
def _n(k):
    return f"{k} analysts'" if k != 1 else "1 analyst's"


def build_triggers(conditions, export, broker_stops):
    xr = {r["ticker"]: r for r in export.get("daily_list") or []}
    for h in export.get("held_positions") or []:
        xr.setdefault(h["ticker"], h)
    bs = (broker_stops or {}).get("positions") or {}

    def own_buys(r):
        g = collections.OrderedDict()
        for a in r.get("analysts") or []:
            if a.get("vote") != "SUPPORT" or not a.get("counts"):
                continue
            for b in a.get("buy") or []:
                if not b.get("levels"):
                    continue
                key = (b["w"], b["levels"][0]["value"])
                g.setdefault(key, {"w": b["w"], "value": key[1], "seats": []})["seats"].append(a["seat"])
        return list(g.values())

    UP = ("h1_close_above", "close_above")

    def trig(t, r):
        sh = r["shared"]; buys = list(sh.get("buy") or []); label = "shared"
        if not buys:
            label = "not shared (no majority)"
            buys = own_buys(r)
        # 2026-10-23 (XOM 164.91 vs close 178.23, RXO 23.90 vs 28.92): a "close above" buy line at or
        # under the last close is an old breakout point the stock already left behind -- an alert on it
        # fires at once and means nothing. Never use it; fall back to the supporters' own lines above
        # the close, labelled as such.
        # A line just under the close is a breakout that just happened ("ready now", ROKU 158.85 vs 160.06);
        # a line more than one average daily range under it is an old breakout point left behind.
        close = r.get("ref_close") or (xr.get(t) or {}).get("entry")
        atr = r.get("atr_14d") or 0
        live_up = lambda b: (close is None or b.get("value") is None or b["value"] >= close - atr)
        stale = [b for b in buys if b["w"] in UP and not live_up(b)]
        if stale and not [b for b in buys if b["w"] in UP and live_up(b)]:
            label = f"not shared (the shared line {stale[0]['value']} is an old level well below the price)"
            buys = [b for b in buys if b["w"] not in UP] + [b for b in own_buys(r) if b["w"] in UP and live_up(b)]
        vx = [b.get("x") for b in sh.get("confirm") or [] if b.get("w") == "vol_x_ge" and b.get("x")]
        up = sorted([b for b in buys if b["w"] in UP and live_up(b)], key=lambda b: -len(b["seats"]))
        dn = [b for b in buys if b["w"] in ("in_zone", "reclaim")]
        tr = []
        if up:
            b = up[0]
            d = {"id": f"{t}-buy0", "kind": "close_above", "level": b["value"], "basis": "15m", "priority": "ACTION",
                 "action": f"{t}: an hourly candle closes above {b['value']} ({_n(len(b['seats']))} {label} buy line). Your decision."}
            if vx:
                d["volume_min_x"] = max(vx)
            tr.append(d)
            bh = (xr.get(t) or {}).get("bar_high")
            if bh:
                tr.append({"id": f"{t}-touch", "kind": "trade_above", "level": bh, "basis": "15m", "priority": "WARN",
                           "action": f"{t} traded through yesterday's intraday high {bh}: the buy line is in play, not met until an hourly close confirms."})
        for i, b in enumerate(dn[:2]):
            tr.append({"id": f"{t}-dip{i + 1}", "kind": "trade_below", "level": b["value"], "basis": "15m", "priority": "WARN",
                       "action": f"{t} traded down to {b['value']} ({_n(len(b['seats']))} pullback line). The buy is an hourly close back above it, not the touch."})
        wz = sh.get("wait_zone")
        if wz and up and wz["hi"] < up[0]["value"] and not any(x["level"] == wz["hi"] for x in tr):
            tr.append({"id": f"{t}-wait", "kind": "trade_below", "level": wz["hi"], "basis": "15m", "priority": "WARN",
                       "action": f"{t} is back in the wait area {wz['lo']}-{wz['hi']}."})
        ex_ = sorted(r.get("exits") or [], key=lambda e: (-len(e["seats"]), -e["value"]))
        if ex_:
            e = ex_[0]
            tr.append({"id": f"{t}-dead", "kind": "close_below", "level": e["value"], "basis": "daily", "priority": "WARN",
                       "action": f"{t} closed under {e['value']}, the exit line most analysts share: the case is invalidated."})
        conf = "; ".join(b["plain"] for b in [x for x in (sh.get("buy") or []) if not (x["w"] in UP and not live_up(x))]
                         + (sh.get("confirm") or [])) or \
            "no shared buy: " + "; ".join(f"{b['w']} {b['value']} ({len(b['seats'])})" for b in buys)
        kills = f"A daily close under {ex_[0]['value']} ({_n(len(ex_[0]['seats']))} exit line)." if ex_ else "no exit line filed"
        return tr, conf, kills, ex_

    cards = {"advance": {}, "hold": {}, "held": {}}
    for r in conditions["rows"]:
        t, v = r["ticker"], r["verdict"]
        live = v in ("ADVANCE", "HOLD-FOR-CONDITIONS")
        tr, conf, kills, ex_ = trig(t, r) if live else ([], "", "", r.get("exits") or [])
        if t in bs:
            stop = bs[t].get("stop")
            ok = [e for e in ex_ if stop is not None and e["value"] >= stop]
            held = {"committee_exit": (max(ok, key=lambda e: e["value"])["value"] if ok else None),
                    "committee_exit_range": None,
                    "for": f"Keep under the broker stop {stop} ({bs[t].get('order')} {bs[t].get('order_qty')}, {bs[t].get('tif')}).",
                    "against": ("Every analyst exit line sits below the broker stop, so the broker stop is the tighter exit."
                                if ex_ and not ok else "")}
            cards["held"][t] = held
            if v == "ADVANCE":
                # A held name advanced on the ADD question: watch the add triggers, never an exit
                # below the PM's stop (LEVELS refuses a committee line that loosens his stop).
                cards["advance"][t] = {"triggers": [x for x in tr if x["kind"] != "close_below"],
                                       "confirms": "ADD question: " + conf,
                                       "kills": f"The broker stop {stop} is the exit."}
            elif v == "HOLD-FOR-CONDITIONS":
                # 2026-11-02 (29 Oct and 2 Nov, V): a HELD name on HOLD-FOR-CONDITIONS got no hold card, so
                # LEVELS refused the file until the conductor patched one in by hand. The hold is the ADD
                # question: the same trigger construction as any hold, worded as an add, never an exit line
                # (the PM's broker stop is the exit; the committee's tighter line rides on the held row).
                cards["hold"][t] = _held_hold_card(t, r, tr, conf, stop)
            continue
        if not live:
            continue
        card = {"triggers": tr, "confirms": conf, "kills": kills}
        if not any(x["priority"] == "ACTION" or x["kind"] == "trade_below" for x in tr):
            card["not_structured_yet"] = "no analyst buy level resolved"
        cards["advance" if v == "ADVANCE" else "hold"][t] = card
    return cards


def _held_hold_card(t, r, tr, conf, stop):
    """The hold card for a HELD name on HOLD-FOR-CONDITIONS: the ADD question on the shared buy line."""
    kills = f"The broker stop {stop} is the exit."
    if not ((r.get("shared") or {}).get("buy")):
        return {"triggers": [], "confirms": "ADD question: no shared add line", "kills": kills,
                "not_structured_yet": "held name: no shared add line (no buy level shared by a majority of "
                                      "supporters) -- the ADD question is not structured; the broker stop is the exit"}
    add = []
    for x in tr:
        if x["kind"] == "close_below":
            continue
        x = dict(x)
        if x["priority"] == "ACTION":
            x["action"] = x["action"].replace(f"{t}: ", f"{t} (held): ", 1).replace(
                "Your decision.", "ADD question only; your decision.").replace("buy line)", "add line)")
        add.append(x)
    card = {"triggers": add, "confirms": "ADD question: " + conf, "kills": kills}
    if not any(x["priority"] == "ACTION" or x["kind"] == "trade_below" for x in add):
        card["not_structured_yet"] = "held name: the shared add line did not resolve to a live level"
    return card


def cmd_triggers(a):
    cards = build_triggers(load(a.conditions), load(a.export), load(a.broker_stops, {}))
    json.dump(cards, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}: advance {len(cards['advance'])}, hold {len(cards['hold'])}, held {len(cards['held'])}")


# ------------------------------------------------------------------------------------------ render
CSS = """
:root{--bg:#eef1f4;--card:#ffffff;--fg:#17202b;--mute:#5b6878;--line:#d6dde5;--soft:#f5f7f9;--accent:#1f5f8b;--accent-soft:#e2edf5;
--up:#1d7a4c;--down:#b3402e;--warn:#a86a00;--warn-soft:#fbf1dc;--down-soft:#f8e4e0;--up-soft:#e0f1e8;
--f-disp:"Archivo",system-ui,sans-serif;--f-body:"Source Sans 3",system-ui,sans-serif;--f-mono:"JetBrains Mono",ui-monospace,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f151c;--card:#17202a;--fg:#e4eaf0;--mute:#93a1b0;--line:#2a3644;--soft:#1b2631;--accent:#6fb0de;--accent-soft:#1c3346;--up:#5cc58f;--down:#ec8a77;--warn:#e3ad4f;--warn-soft:#3a2e17;--down-soft:#3d221d;--up-soft:#173327;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f151c;--card:#17202a;--fg:#e4eaf0;--mute:#93a1b0;--line:#2a3644;--soft:#1b2631;--accent:#6fb0de;--accent-soft:#1c3346;--up:#5cc58f;--down:#ec8a77;--warn:#e3ad4f;--warn-soft:#3a2e17;--down-soft:#3d221d;--up-soft:#173327;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--f-body);font-size:15.5px;line-height:1.55}
.wrap{max-width:1100px;margin:0 auto;padding-block:22px 40px;padding-inline:16px;display:flex;flex-direction:column;gap:16px}
h1,h2,h3{font-family:var(--f-disp);margin:0;text-wrap:balance}h1{font-size:1.8rem;font-weight:800}h2{font-size:1.2rem;font-weight:800}h3{font-size:1rem;font-weight:600}
p{margin:0}
.eyebrow{font-family:var(--f-mono);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:12px}
.chip{display:inline-block;white-space:nowrap;margin:0 8px 4px 0;font-size:.85rem}.chip .pill{margin-left:4px}
.gauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px 18px;margin-top:8px}.gauge{font-size:.85rem}.gh{display:flex;justify-content:space-between}.gh b{font-family:var(--f-mono)}.bar{height:7px;border-radius:4px;background:var(--line);overflow:hidden;margin:4px 0}.bar span{display:block;height:100%;background:var(--accent)}.gl{display:flex;justify-content:space-between;color:var(--mute);font-size:.78rem}.gn{color:var(--mute);font-size:.72rem}
.light{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px;vertical-align:-1px}.why{margin:6px 0 10px}
.pill{display:inline-block;font-family:var(--f-mono);font-size:.68rem;font-weight:600;padding:2px 8px;border-radius:999px;letter-spacing:.03em;white-space:nowrap;margin-left:6px;max-width:100%;overflow-wrap:anywhere}@media (max-width:640px){.pill{white-space:normal;border-radius:10px}}
.p-up,.p-ok{background:var(--up-soft);color:var(--up)}.p-down,.p-bad{background:var(--down-soft);color:var(--down)}.p-warn{background:var(--warn-soft);color:var(--warn)}.p-n{background:var(--accent-soft);color:var(--accent)}.p-ma{background:#b3261e;color:#fff}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;display:flex;flex-direction:column;gap:12px;min-width:0}
.bottom{border:2px solid var(--accent)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}@media (max-width:700px){.grid4{grid-template-columns:repeat(2,1fr)}}
.grid2>*,.grid4>*,.names>*,.holds>*{min-width:0}
.stat{border:1px solid var(--line);border-radius:8px;padding:10px 12px}.stat .v{font-family:var(--f-disp);font-weight:800;font-size:1.35rem}.stat .l{font-size:.82rem;color:var(--mute)}
ul,ol{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px}
.tbl{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th{font-family:var(--f-mono);font-size:.66rem;letter-spacing:.05em;text-transform:uppercase;color:var(--mute);text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line);background:var(--soft);white-space:nowrap}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-variant-numeric:tabular-nums;overflow-wrap:break-word}
.neg{color:var(--down)}.pos{color:var(--up)}.wrn{color:var(--warn)}
.section-title{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-top:8px}
.names{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:820px){.names{grid-template-columns:1fr}}
.name header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.tk{font-family:var(--f-disp);font-weight:800;font-size:1.35rem}.why{font-size:.9rem;color:var(--mute)}
.kv2{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;margin:0;border-top:1px solid var(--line);padding-top:10px}
.kv2>div{min-width:0}.kv2 .full{grid-column:1/-1}@media (max-width:480px){.kv2{grid-template-columns:1fr}}
dt{font-family:var(--f-mono);font-size:.64rem;letter-spacing:.05em;text-transform:uppercase;color:var(--mute)}dd{margin:0;font-size:.88rem}
.holds{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}@media (max-width:900px){.holds{grid-template-columns:repeat(2,1fr)}}@media (max-width:560px){.holds{grid-template-columns:1fr}}
.hold{border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:5px;font-size:.86rem}
.hh{display:flex;align-items:center;gap:4px}.hh .num{margin-left:auto;font-family:var(--f-mono);font-size:.75rem;color:var(--mute)}
.tk2{font-family:var(--f-disp);font-weight:800;font-size:1.05rem}.cond{color:var(--mute)}
.flag{border-left:3px solid var(--warn);background:var(--warn-soft);padding:8px 12px;border-radius:0 6px 6px 0;font-size:.88rem}
.reason p{margin:.25rem 0;font-size:.95rem}\n.audit{margin-top:4px;font-size:.82rem;color:var(--mute)}.audit summary{cursor:pointer}.bracket dd{font-family:var(--f-mono);font-size:.86rem}
.committee{border-left:3px solid var(--up);background:var(--up-soft,var(--warn-soft));padding:8px 12px;margin:8px 0;border-radius:0 6px 6px 0;font-size:.9rem}
.committee .minority{margin-top:4px;color:var(--ink-2,inherit)}
.read{display:flex;flex-direction:column;gap:10px;max-width:72ch}
.foot{font-family:var(--f-mono);font-size:.8rem;text-align:center;color:var(--mute);padding-top:8px}
"""
TONE = {"ok": "p-ok", "warn": "p-warn", "bad": "p-bad", "pos": "pos", "neg": "neg", "wrn": "wrn", "up": "p-up", "down": "p-down", "n": "p-n"}
REQUIRED_TOP = ["session_label", "stance_pill", "bottom_line", "market", "money", "book", "changed",
                "cards", "holds", "passes", "plan", "caveats"]




# ---------------------------------------------------------------------------------------------------------------
# PLAIN WORDS (PM 2026-11-04: "random words that don't explain"): ONE table turns every raw field / state name that reaches the
# page into words a trader reads. Applied to every text node of the rendered HTML, so no block (Confirms, Valen, Sector, committee
# quotes, ...) can leak a field name. A token not in the table falls back to lower-case words and is reported at render so the
# table gets extended; check.py cards --html then FAILs any underscore token that still appears.
PLAIN_WORDS = {
    "bar_high": "yesterday's high", "bar_low": "yesterday's low", "prior_bar_high": "yesterday's high", "prior_bar_low": "yesterday's low",
    "high_52w_close": "the 52-week closing high", "high_52w": "the 52-week high", "low_52w": "the 52-week low",
    "from_52w_hi": "distance from the 52-week high", "pct_from_52w_high": "distance from the 52-week high",
    "ma_20": "the 20-day average", "ma_40": "the 40-day average", "ma_50": "the 50-day average", "ma_100": "the 100-day average",
    "ma_150": "the 150-day average", "ma_200": "the 200-day average",
    "hi_20d": "the 20-day high", "lo_20d": "the 20-day low", "hi_50d": "the 50-day high", "lo_50d": "the 50-day low",
    "base_low_20d": "the 20-day base low", "pivot_high": "the last pivot high", "pct_from_pivot": "distance from the pivot",
    "structure_shift_ref": "the structure break level", "structure_shift": "market structure",
    "day_vol": "today's volume against its average", "rvol_20d": "volume against its 20-day average",
    "rs_rank_pct": "relative-strength rank", "rs_leadership": "relative-strength leadership", "rs_spy_20d": "20-day strength against the index",
    "elder_5d": "the 5-day Elder score run", "elder_pattern": "the Elder pattern", "mp_state": "momentum state", "ret_63d": "3-month return",
    "dist_to_20bar_high_pct": "distance from the 20-bar high", "pos_in_day_range_pct": "position in today's range",
    "hh_hl_3": "higher highs and higher lows", "sma_dist": "distance from the average", "close_vs_ema9": "close against the 9-day average",
    "ema_order": "the order of the averages", "last_bar": "the last bar", "held_tp1": "the held first target",
    "horizon_sessions": "horizon in sessions", "why_agreed": "why agreed", "atr_14d": "the average daily range",
    "ext_atr20": "stretch from the 20-day average", "vol_x_ge": "volume at least", "run_10d": "10-day run", "elder_le": "Elder score at most",
    "pvp_vah": "the top of the value area", "pvp_val": "the bottom of the value area", "pvp_poc": "the highest-volume price",
    "vwap_14d": "the 14-day volume-weighted price", "avwap_structure": "the structure-anchored volume-weighted price",
    "avwap_swing": "the swing-anchored volume-weighted price",
    "h1_close_above": "an hourly close above", "close_above": "a daily close above", "close_below": "a daily close below",
    "trade_above": "trading above", "trade_below": "trading below", "in_zone": "in the zone",
    "aqe_atr_fallback": "one daily range below the price", "stop_type": "stop type",
    "STP_LMT": "stop-limit order", "ACT_NOW": "act now", "NOT_SLATED": "not slated", "ABOVE_STRUCTURE": "above structure",
    "BULLISH_BOS": "a bullish break of structure", "BEARISH_CHOCH": "a bearish change of character", "BULLISH_CHOCH": "a bullish change of character",
    "BROADENING_CARRY": "broadening", "CORRECTION_REENTRY": "correction re-entry", "PAST_PIVOT": "past the pivot", "RISK_OFF": "risk-off",
    "RISK_ON": "risk-on", "DOLLAR_SQUEEZE": "dollar squeeze", "GROWTH_SCARE": "growth scare",
    "crown_oldest_leg": "the oldest macro input", "positioning_cot": "positioning (COT report)", "breadth_whole_market": "whole-market breadth",
    "heartbeat_rsp_spy": "market breadth heartbeat", "vix_level": "VIX level", "dispersion_vixeq": "stock-volatility spread",
    "implied_correlation_cor1m": "implied correlation", "PUBLISHER_CADENCE": "latest published release", "PUBLISHER_LAG": "publisher not yet posted",
    "OUR_BUDGET": "we ran out of time", "SOURCE_DOWN": "source unavailable",
}
_PLAIN_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
_PLAIN_FALLBACK: set = set()


def plain_words(text):
    def sub(m):
        t = m.group(0)
        if t in PLAIN_WORDS:
            return PLAIN_WORDS[t]
        if t.lower() in PLAIN_WORDS:
            return PLAIN_WORDS[t.lower()]
        _PLAIN_FALLBACK.add(t)
        return t.lower().replace("_", " ")
    return _PLAIN_TOKEN.sub(sub, text)


_JARGON_PROSE = [
    (re.compile(r"\s*\(RSI\)"), ""), (re.compile(r"(?<=[a-z] )RSI\b"), "momentum gauge"),
    (re.compile(r"(?<=[a-z0-9\-] )VWAP\b"), "volume-weighted price"), (re.compile(r"(?<=[a-z] )MACD\b"), "momentum trend gauge"),
    (re.compile(r"(?<=[a-z] )ATR(?= multiple| extended| of| from)"), "daily range"), (re.compile(r"(?<=[0-9] )ATR\b"), "daily ranges"),
]


def plain_prose(text):
    """Indicator names in PROSE (a lower-case word before them), never a bare ticker cell: RSI / VWAP / MACD / ATR -> plain words."""
    for rx, rep in _JARGON_PROSE:
        text = rx.sub(rep, text)
    return text


def plainify_html(page):
    """Translate raw tokens in the TEXT of the page only (never <style>, <script> or tag attributes)."""
    parts = re.split(r"(<style.*?</style>|<script.*?</script>)", page, flags=re.S | re.I)
    out = []
    for seg in parts:
        if seg[:6].lower() in ("<style", "<scrip"):
            out.append(seg)
        else:
            out.append(re.sub(r">([^<>]+)<", lambda m: ">" + plain_prose(plain_words(m.group(1))) + "<", seg))
    return "".join(out)

# ---------------------------------------------------------------------------------------------------------------
# B1/B2 (PM 2026-11-04): every ADVANCE card carries a code-rendered BRACKET - entry, stop, risk, each target in R, RR to TP2, 1R in
# dollars - and a level under 1.0R is never presented as a target. "The first target is ultra stupid once you consider RR"
# (ROKU: stop 157.90, buy line 161.26, first level 161.26 = 0R). bracket_engine.py stays the source of the LEVELS; this is the
# selection and presentation rule at the cards layer: >= 1R = TP1/TP2/TP3; closer levels = "nearby resistance (x.xR)".
MIN_TARGET_R = 1.0


def _one_r_usd():
    """The fixed 1R in dollars (config/aegis_fund.md one_r_usd, PM 2026-10-27), or None if unset."""
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("../../../config/aegis_fund.md", "../config/aegis_fund.md", "../../config/aegis_fund.md"):
        p = os.path.join(here, rel)
        if os.path.exists(p):
            try:
                m = re.search(r"^one_r_usd:\s*(\d+(?:\.\d+)?)", open(p, encoding="utf-8").read(), re.M)
                if m:
                    return float(m.group(1))
            except OSError:
                pass
    return None


def bracket_view(entry, entry_src, stop, stop_type, levels, one_r=None):
    """Pure. -> the card's bracket: entry | stop | risk | targets in R | nearby | RR to TP2 | 1R shares. Never raises."""
    out = {"entry": entry, "entry_src": entry_src, "stop": stop, "stop_type": stop_type, "risk": None, "risk_pct": None,
           "targets": [], "nearby": [], "rr_tp2": None, "one_r_usd": one_r, "shares": None, "note": None}
    try:
        if not (isinstance(entry, (int, float)) and isinstance(stop, (int, float))) or stop >= entry:
            out["note"] = "no valid stop under the entry - no bracket, no R multiples"
            return out
        risk = entry - stop
        out["risk"], out["risk_pct"] = round(risk, 2), round(100 * risk / entry, 2)
        rows = sorted({round(float(p), 2) for p in levels if isinstance(p, (int, float))})
        for p in rows:
            r = (p - entry) / risk
            if r >= MIN_TARGET_R:
                out["targets"].append({"n": len(out["targets"]) + 1, "price": p, "r": round(r, 2)})
            else:
                out["nearby"].append({"price": p, "r": round(r, 2)})
        out["targets"] = out["targets"][:3]
        if len(out["targets"]) >= 2:
            out["rr_tp2"] = out["targets"][1]["r"]
        if len(out["targets"]) < 2:
            out["note"] = (("No level reaches 1R above the entry" if not out["targets"] else "Only one level reaches 1R above the entry")
                           + " - no usable target ladder; treat the nearby levels as resistance to trade through, not as targets")
        if one_r:
            out["shares"] = int(one_r // risk)
    except Exception as e:  # noqa: BLE001
        out["note"] = f"bracket could not be built: {e.__class__.__name__}"
    return out


def _bracket_html(b):
    if b.get("risk") is None:
        return f'<div class="full bracket"><dt>Bracket</dt><dd class="neg">{E(b.get("note") or "n/a")}</dd></div>'
    tp = " &nbsp;·&nbsp; ".join(f'TP{x["n"]} <b>{x["price"]:.2f}</b> ({x["r"]:.1f}R)' for x in b["targets"]) or "no target reaches 1R"
    near = (" · ".join(f'{x["price"]:.2f} ({x["r"]:.1f}R)' for x in b["nearby"]) or "")
    one = (f'1R ${b["one_r_usd"]:,.0f} = {b["shares"]} shares' if b.get("shares") is not None else "1R $ not set")
    rr = f'{b["rr_tp2"]:.1f}R' if b.get("rr_tp2") is not None else "n/a"
    first = (f'Reward/risk to the first real target: <b>{b["targets"][0]["r"]:.1f}R</b>' if b["targets"] else
             '<b class="neg">Reward does not justify the risk at this entry: no target reaches 1R</b>')
    st = str(b.get("stop_type") or "").replace("_", " ")
    return (f'<div class="full bracket"><dt>Bracket</dt><dd>{first}<br>'
            f'Entry <b>{b["entry"]:.2f}</b> ({E(b["entry_src"])}) &nbsp;·&nbsp; Stop <b>{b["stop"]:.2f}</b> ({E(st)}) &nbsp;·&nbsp; '
            f'Risk <b>{b["risk"]:.2f}</b>/share ({b["risk_pct"]:.1f}%) &nbsp;·&nbsp; {tp} &nbsp;·&nbsp; RR to TP2 <b>{rr}</b> &nbsp;·&nbsp; {E(one)}'
            + (f'<br><span class="cond">Nearby resistance, not targets: {E(near)}</span>' if near else "")
            + (f'<br><span class="neg">{E(b["note"])}</span>' if b.get("note") else "") + '</dd></div>')


# B3 (PM 2026-11-04): ONE voice, plain English. The reason block is three sentences for a trader - why the room agrees it is a buy,
# the one thing that would make it wrong, what to wait for. The audit trail (verbatim quotes) stays in the slate; this text is plain.
REASON_KEYS = ("agree", "wrong_if", "wait_for")
REASON_MAX_CHARS = 240
REASON_MAX_NUMBERS = 4
JARGON = ("ema", "sma", "atr", "macd", "rsi", "cci", "adx", "vwap", "obv", "pvp", "poc", "vah", "val", "bos", "choch", "dsl", "mfi", "cmf",
          "support seats", "oppose", "abstain", "voted", "votes", "vote", "unanimous", "analysts agree", "quorum", "conviction")
_RAW_FIELD = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\b[a-z_]+\.[a-z_]+\b")
_TALLY = re.compile(r"\b\d+\s*(?:of|/|out of)\s*\d+\b", re.I)
_NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:[.,]\d+)?%?")


def validate_reason(reason):
    """-> list of problems (empty = plain). FAIL, not WARN: raw field names, vote tallies, jargon, more than 4 numbers, or not three
    one-sentence parts."""
    errs = []
    if not isinstance(reason, dict) or any(not isinstance(reason.get(k), str) or not reason[k].strip() for k in REASON_KEYS):
        return [f"reason must be {{agree, wrong_if, wait_for}}, one plain sentence each"]
    nums = 0
    for k in REASON_KEYS:
        t = reason[k].strip()
        if len(t) > REASON_MAX_CHARS:
            errs.append(f"reason.{k}: {len(t)} chars > {REASON_MAX_CHARS} - one sentence")
        if len(re.findall(r"[.!?](?=\s+[A-Z])", t)) > 0:
            errs.append(f"reason.{k}: more than one sentence")
        m = _RAW_FIELD.findall(t)
        if m:
            errs.append(f"reason.{k}: raw field name(s) {sorted(set(m))[:3]} - say it in plain words")
        if _TALLY.search(t):
            errs.append(f"reason.{k}: a vote tally ({_TALLY.search(t).group(0)!r}) - the card never counts votes")
        low = " " + re.sub(r"[^a-z ]", " ", t.lower()) + " "
        bad = [j for j in JARGON if f" {j} " in low]
        if bad:
            errs.append(f"reason.{k}: jargon {bad[:3]}")
        nums += len(_NUMBER.findall(t))
    if nums > REASON_MAX_NUMBERS:
        errs.append(f"reason: {nums} numbers > {REASON_MAX_NUMBERS} - keep only the ones that matter")
    return errs


_ONE_R = None
_MARKER = None
_REFRESHED = None


def _reason_html(w):
    r = w.get("reason")
    if isinstance(r, dict) and all(r.get(k) for k in REASON_KEYS):
        return ('<div class="reason"><p><b>Why it is a buy:</b> ' + E(r["agree"]) + '</p><p><b>What would make it wrong:</b> ' + E(r["wrong_if"]) +
                '</p><p><b>What to wait for:</b> ' + E(r["wait_for"]) + '</p></div>')
    return f'<p class="why">{E(w.get("why", ""))}</p>'          # legacy text only (--allow-legacy-text)


def _validate_text(T, cons, legacy=False):
    gaps = [k for k in REQUIRED_TOP if k not in T]
    adv = [c["ticker"] for c in cons if c["verdict"] == "ADVANCE"]
    hol = [c["ticker"] for c in cons if c["verdict"] == "HOLD-FOR-CONDITIONS"]
    pas = [c["ticker"] for c in cons if c["verdict"] == "PASS"]
    voted = set(adv + hol + pas)
    for t in adv:
        c = (T.get("cards") or {}).get(t) or {}
        miss = [k for k in ("case", "readiness", "readiness_tone") if not c.get(k)]
        if not c.get("reason") and not (legacy and c.get("why")):
            miss.append("reason")
        if miss:
            gaps.append(f"cards.{t} missing {miss}")
        if c.get("reason"):
            gaps += [f"cards.{t}.{e}" for e in validate_reason(c["reason"])]
    gaps += [f"holds.{t}" for t in hol if not (T.get("holds") or {}).get(t)]
    gaps += [f"passes.{t}" for t in pas if not (T.get("passes") or {}).get(t)]
    for sec in ("cards", "holds", "passes"):
        gaps += [f"{sec}.{t} is not a voted name" for t in (T.get(sec) or {}) if t not in voted]
    bl = T.get("bottom_line") or {}
    if not bl.get("headline") or len(bl.get("stats") or []) != 4:
        gaps.append("bottom_line needs a headline and exactly 4 stats")
    return gaps


def _trig_text(card, kind_order=("close_above", "trade_below")):
    tr = card.get("triggers") or []
    buy = next((x for x in tr if x["kind"] == "close_above"), None)
    dip = next((x for x in tr if x["kind"] == "trade_below" and x["id"].split("-")[-1].startswith("dip")), None)
    if buy and dip:
        return f"Hourly close above {buy['level']} · or a dip to {dip['level']} and reclaim"
    if buy:
        return f"Hourly close above {buy['level']}" + (f" on {buy['volume_min_x']}x volume" if buy.get("volume_min_x") else "")
    if dip:
        return f"Dip to {dip['level']} and an hourly close back above it"
    return card.get("not_structured_yet") or "no buy level"


def _dead_text(card):
    d = next((x for x in card.get("triggers") or [] if x["kind"] == "close_below"), None)
    return f"Daily close under {d['level']}" if d else card.get("kills") or "—"



# ---------------------------------------------------------------------- PART 1: DAILY WEATHER (PM 2026-10-23)
# PM: "Part 1 = Daily Weather ... situational awareness and stance, GEX traffic light, Macro cockpit, a short
# write up on COT crowded positions long and short, market checklist and instruments, weather turning, theme
# leaders and rotation. these numbers are all available, you just have to explain them."
# Every number below is read from AQE's own files by code. The words come from cards_text.json `weather`
# (one explanation per block) -- never a number typed by the writer.
WEATHER_KEYS = ["stance", "gex", "heartbeat", "positioning", "volatility", "divergence", "call", "cot", "checklist", "turning", "themes", "groups"]
COT_NAMES = {"ES": "S&P 500 futures", "NQ": "Nasdaq-100 futures", "RTY": "Russell 2000 futures", "YM": "Dow futures",
             "ZT": "2-year Treasury note", "ZF": "5-year Treasury note", "ZN": "10-year Treasury note",
             "ZB": "30-year Treasury bond", "UB": "Ultra bond", "ZC": "corn", "ZS": "soybeans", "ZW": "wheat",
             "KE": "KC wheat", "CL": "crude oil", "NG": "natural gas", "RB": "gasoline", "HO": "heating oil",
             "GC": "gold", "SI": "silver", "HG": "copper", "PL": "platinum", "6E": "euro", "6J": "yen",
             "6B": "pound", "6A": "Aussie dollar", "6C": "Canadian dollar", "DX": "US dollar index",
             "VX": "VIX futures", "BTC": "bitcoin futures"}
LIGHT = {"RED": "var(--down)", "AMBER": "var(--warn)", "YELLOW": "var(--warn)", "GREEN": "var(--up)"}


def _num(v, fmt="{:g}"):
    return fmt.format(v) if isinstance(v, (int, float)) else ("—" if v is None else str(v))


def _already_met(line):
    """Valen's watch_for can list a threshold that is already met ('clears 1.0 (now 4.38)')."""
    import re
    m = re.search(r"(clears|falls under)\s+(-?[\d.]+)\s*\(now\s+(-?[\d.]+)\)", line)
    if not m:
        return False
    thr, now = float(m.group(2)), float(m.group(3))
    return now >= thr if m.group(1) == "clears" else now < thr




def _unr_words(r):
    """U&R is ONE of Valen's five setups, not his entry rule (PM 2026-10-23: "the NO valen UNR sounds kind of
    weird"). Show it only when it happened, in words; say nothing on NO / NA."""
    st = str(r.get("unr_status") or "")
    if st == "MET":
        return "Valen undercut-and-rally: reclaim day" + (f' ({r.get("unr_note")})' if r.get("unr_note") else "")
    if st == "SETUP":
        return "Valen undercut-and-rally forming: undercut, not yet reclaimed" + (f' ({r.get("unr_note")})' if r.get("unr_note") else "")
    return ""

def _is_valen_warning(x):
    """R41 (PM 2026-11-02): Valen's long-only risk warnings (parabolic, failed leader) are not printed on the
    cards -- selection is the seats' judgment on their own methods. The house setups themselves are facts and stay."""
    nm = str((x or {}).get("setup", "")).lower()
    return "parabolic" in nm or "failed leader" in nm


def _house_setups(r):
    gr = r.get("setups")
    if isinstance(gr, dict):
        gr = gr.get("grades")
    return [x for x in (gr or []) if isinstance(x, dict) and not _is_valen_warning(x)]


def _market_kill_text(mk):
    """R40: the slate's ONE market kill line, in plain words (copied from the slate, never composed here)."""
    if not isinstance(mk, dict) or not mk.get("plain"):
        return ""
    import re
    who = ", ".join(mk.get("seats") or [])
    plain = re.sub(r"^\s*void\s+(every\s+new\s+trigger\s+)?if\s+", "", str(mk["plain"]), flags=re.I)
    return plain + (f" ({who})" if who else "")


_VOICES = ("oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff")


def _plain_void(mk):
    """The VISIBLE market-kill line (PM 2026-11-04): the slate's words without canon codes '(C1, C2)' and without seat names
    '(oneil)'; the verbatim line (codes, seats) stays in the audit trail. Never composed here, only stripped."""
    if not isinstance(mk, dict) or not mk.get("plain"):
        return ""
    t = re.sub(r"^\s*void\s+(every\s+new\s+trigger\s+)?if\s+", "", str(mk["plain"]), flags=re.I)
    t = re.sub(r"\s*\(\s*C\d+(?:\s*[,/]\s*C\d+)*\s*\)", "", t)
    t = re.sub(r"\s*\(\s*(?:" + "|".join(_VOICES) + r")(?:\s*,\s*(?:" + "|".join(_VOICES) + r"))*\s*\)", "", t)
    t = re.sub(r"\bC\d{1,2}\b", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;:")
    return t.rstrip(".") + "."


def _void_cell(mk):
    plain = _plain_void(mk)
    if not plain:
        return ""
    verb = _market_kill_text(mk)
    return (f'<div class="full"><dt>Void if</dt><dd>{E(plain)}<details class="audit"><summary>Audit trail: the verbatim line</summary>'
            f'{E(verb)}</details></dd></div>')


def _ma_pill(row):
    """PM 2026-11-04: a name with a pending merger / acquisition / buyout carries a red pill wherever it is picked. UNKNOWN (the scan
    failed for this ticker) is NOT shown as a clean name: it gets a grey 'M&A not checked' pill."""
    st = str((row or {}).get("ma_status") or "")
    if st == "PENDING_TARGET":
        txt = "M&A PENDING · being acquired"
    elif st == "PENDING_ACQUIRER":
        txt = "M&A PENDING · the buyer"
    elif st == "PENDING_UNCLEAR":
        txt = "M&A PENDING"
    elif st == "UNKNOWN":
        return '<span class="pill p-n" title="The M&amp;A scan did not run for this name">M&amp;A not checked</span>'
    else:
        return ""
    return f'<span class="pill p-ma" title="{E(str(row.get("ma_note") or ""))}">{E(txt)}</span>'


def _ma_line(row):
    """The sentence under a pending-deal name: what was found, and why it matters. Empty for a clean name."""
    st = str((row or {}).get("ma_status") or "")
    if not st.startswith("PENDING"):
        return ""
    why = {"PENDING_TARGET": " A stock with a pending takeover trades on the deal spread, not on momentum, so flow, energy and structure mean little here.",
           "PENDING_ACQUIRER": " This company is the buyer; the deal can move its stock, but it is not pinned to a price.",
           "PENDING_UNCLEAR": " The role in the deal could not be read from the news; check the headline."}.get(st, "")
    return f'<p class="flag"><b>M&amp;A PENDING.</b> {E(str(row.get("ma_note") or ""))}{E(why)}</p>'


def _ma_banner(D):
    """A failed or partial M&A scan is loud on the page: a clean-looking name might simply be unchecked."""
    sc = (D or {}).get("ma_scan")
    if not isinstance(sc, dict):
        return ('<p class="flag"><b>M&amp;A flags are not in this export.</b> The export carries no ma_scan block, so no name can be called '
                'free of a pending deal.</p>')
    if sc.get("scan_status") != "ok":
        return (f'<p class="flag"><b>M&amp;A scan {E(str(sc.get("scan_status")))}.</b> {E(str(sc.get("n_failed")))} of {E(str(sc.get("n_scanned")))} '
                f'names could not be checked for a pending merger or buyout{(": " + E(str(sc.get("reason")))) if sc.get("reason") else ""}. '
                'Names marked &ldquo;M&amp;A not checked&rdquo; are unchecked, not clean.</p>')
    return ""


def _wind_gauges(v):
    """PM 2026-10-23 (Valen's 'Market as of now' panel): simple bars for the direction of the wind. Built ONLY
    from the breadth numbers AQE computes on its full curated panel (aqe_valen_dashboard.json breadth[]). The
    scored daily_list is NOT used: it is pre-filtered to strong names and read 100% above the 20-day on
    2026-10-23 -- a biased sample, not the wind. Whole-market counts (new highs/lows, up/down from open, up/down
    volume, % above 20/50/200, stage counts) need AQE to export them; until then they are declared, not faked."""
    b = {x.get("label"): x for x in (v or {}).get("breadth") or []}
    def bar(lbl, pct, left, right, note=""):
        pct = max(0, min(100, round(pct)))
        return (f'<div class="gauge"><div class="gh"><span>{E(lbl)}</span><b>{pct}%</b></div>'
                f'<div class="bar"><span style="width:{pct}%"></span></div>'
                f'<div class="gl"><span>{E(left)}</span><span>{E(right)}</span></div>'
                + (f'<div class="gn">{E(note)}</div>' if note else "") + "</div>")
    g = []
    t = next((x for k, x in b.items() if k and k.startswith("T2108")), None)
    if t and isinstance(t.get("value"), (int, float)):
        g.append(bar("Stocks above their 40-day average", t["value"], f'{t["value"]:g}% above', "50% = risk-on line",
                     "under 20 washed out · over 80 overheated"))
    for lbl, key in (("Big up days vs big down days · 5 days", "5-day up/down 4% count"),
                     ("Big up days vs big down days · 10 days", "10-day up/down 4% count")):
        x = b.get(key)
        if x and isinstance(x.get("value"), (int, float)) and x["value"] >= 0:
            r = x["value"]
            g.append(bar(lbl, 100 * r / (1 + r), f"{r:g} up for every 1 down", "1.0 = even",
                         "a big day = a stock up or down 4% or more"))
    nh = b.get("Net High/Net Low (8d vs 20d)")
    if nh and (nh.get("status") not in (None, "OK") or not isinstance(nh.get("value"), bool)):
        # A missing or stale read is NOT a direction (null was rendering as 'Worsening'): say so, with the reason.
        why = str(nh.get("reason") or nh.get("status") or "no value served")
        g.append('<div class="gauge"><div class="gh"><span>Net new highs, 8-day vs 20-day average</span><b>Not read</b></div>'
                 f'<div class="gl"><span>{E(why)}</span></div></div>')
    elif nh:
        g.append(f'<div class="gauge"><div class="gh"><span>Net new highs, 8-day vs 20-day average</span><b class="{"pos" if nh.get("value") else "neg"}">'
                 f'{"Improving" if nh.get("value") else "Worsening"}</b></div><div class="gl"><span>{E(str(nh.get("display") or ""))}</span></div>'
                 + ('<div class="gn">still negative means more new lows than highs, but fewer than before</div>'
                    if str(nh.get("display") or "").strip().startswith("-") else "") + '</div>')
    if not g:
        return '<p class="flag">Breadth numbers not served this run: declared gap.</p>'
    return ('<h3>Direction of the wind</h3><p class="cond">Measured on AQE\'s full curated panel (about 800 stocks), not the whole market. '
            'A bar past halfway means more stocks on the bullish side. Whole-market counts (new highs vs lows, up vs down from the open, '
            'up vs down volume, stage counts) are not exported by AQE yet.</p><div class="gauges">' + "".join(g) + "</div>")


def _thrust_state(t):
    if t.get("rotation_state") == "LEADING":
        return "Leading near its highs"
    if t.get("rotation_state") == "OFF_THE_FLOOR":
        return "Bouncing off the floor"
    w, m, th = t.get("ret_1w_pct"), t.get("ret_1m_pct"), t.get("thrust")
    if not isinstance(w, (int, float)) or not isinstance(m, (int, float)):
        return "—"
    if w > 0 and m > 0:
        return "Rising"
    if w > 0:
        return "Turning up"
    if isinstance(th, (int, float)) and th > 0:
        return "Still falling, but slower"
    return "Falling faster"


def _group_kind(grade, quadrant):
    """The ONE rule for a group's state, shared by the group-turn section (8) and the top-20 table so the two
    views cannot disagree: 'turn' = the grade is TURNING or the rotation quadrant is IMPROVING; 'lead' = the quadrant
    is LEADING and the grade is DEPLOY or HOLD; anything else is None and is shown in its plain AQE words."""
    if grade == "TURNING" or quadrant == "IMPROVING":
        return "turn"
    if quadrant == "LEADING" and grade in ("DEPLOY", "HOLD"):
        return "lead"
    return None


def _sector_state(srm_by_sector, row):
    """-> (label, pill class, plain AQE words). STRONG = the sector is leading the market; TURNING = improving or
    recovering from weakness; anything else shows its plain AQE grade and quadrant - never blank, never invented."""
    x = (srm_by_sector or {}).get((row or {}).get("gics_sector_name"))
    if not x:
        return "no sector grade", "p-n", "AQE has no sector grade for this name (declared gap)"
    g, q = x.get("grade"), x.get("rrg_quadrant")
    words = f"{g or 'no grade'} · {str(q).lower() if q else 'no quadrant'}"
    k = _group_kind(g, q)
    return ({"lead": "STRONG", "turn": "TURNING"}.get(k) or words, {"lead": "p-up", "turn": "p-warn"}.get(k, "p-n"), words)


TOP_N = 20
SHOWN_VERDICT = {"ADVANCE": "ADVANCE", "HOLD-FOR-CONDITIONS": "WATCH", "PASS": "PASS"}   # the Cards' own head pill reads "HOLD · WATCH"


def _top20_panel(D, cons):
    """PM 2026-11-03: the 20 best-ranked AQE names (export `rank` 1..20) at the very bottom of the Cards, built by code,
    no model. For each: rank, ticker, sector, sector state (same grades as the group-turn section), the committee's
    verdict (ADVANCE / WATCH / PASS, or 'not in the room'), and WHO VOTED FOR IT = the voices that SUPPORTED it at the
    blind vote (consensus `split.support`), by name. Nothing invented: a name the room did not carry says so."""
    rows = sorted([r for r in (D or {}).get("daily_list") or [] if isinstance(r, dict) and isinstance(r.get("rank"), int)],
                  key=lambda r: r["rank"])[:TOP_N]
    head = '<section class="card"><div class="eyebrow">Top 20 AQE names &middot; by AQE rank &middot; built by code, information only</div>'
    if not rows:
        return head + '<p class="cond">The export carries no ranked daily_list &mdash; declared gap, nothing invented.</p></section>'
    srm = {x.get("sector"): x for x in (D or {}).get("srm") or [] if isinstance(x, dict)}
    room = {c["ticker"]: c for c in cons}
    body, n_strong, n_turn = [], 0, 0
    for r in rows:
        label, pill, words = _sector_state(srm, r)
        n_strong += label == "STRONG"; n_turn += label == "TURNING"
        c = room.get(r["ticker"])
        if c:
            v = SHOWN_VERDICT.get(c.get("verdict"), E(str(c.get("verdict"))))
            vc = {"ADVANCE": "p-up", "WATCH": "p-warn", "PASS": "p-n"}.get(v, "p-n")
            sup = (c.get("split") or {}).get("support") or []
            who = ", ".join(E(x) for x in sup) if sup else "no voice supported it"
            verdict_cell = f'<span class="pill {vc}">{E(v)}</span>' + (f' <span class="cond">{E(c["status"])}</span>' if c.get("status") else "")
        else:
            verdict_cell, who = '<span class="cond">not in the room</span>', "&mdash;"
        body.append(f'<tr><td class="num">{E(str(r["rank"]))}</td><td><b>{E(r["ticker"])}</b>{_ma_pill(r)}</td><td>{E(str(r.get("gics_sector_name") or "—"))}</td>'
                    f'<td><span class="pill {pill}" title="{E(words)}">{E(label)}</span></td><td>{verdict_cell}</td><td>{who}</td></tr>')
    note = "" if len(rows) == TOP_N else f' Only {len(rows)} ranked names are in today\'s export.'
    return (head + '<div class="tbl"><table><thead><tr><th>Rank</th><th>Ticker</th><th>Sector</th><th>Sector state</th><th>Committee verdict</th><th>Voted for it (blind vote)</th></tr></thead><tbody>'
            + "".join(body) + f'</tbody></table></div><p class="cond">{n_strong} in a leading sector (STRONG), {n_turn} in a turning one (TURNING); the rest show their plain AQE state. '
            'Verdict and voters are the committee\'s, copied from the record; &ldquo;not in the room&rdquo; means the committee did not carry the name. A voter is a voice that supported the name at the blind vote.' + note + '</p></section>')


def _group_turns(D, verdicts, say):
    """PM 2026-10-23: "an easy section to see the strong stocks in supportive and/or turning sectors. This is info
    only ... a signal of where stocks are early in riding their sector turn and strengthen." Code-rendered from the
    export alone: AQE's sector grades (srm) and theme grades (thematic_baskets on each row) with their rotation
    quadrant. Strong = on the Longlist or Elder list, beating SPY over 20 days, above its 50-day average."""
    rows = [r for r in (D or {}).get("daily_list") or [] if isinstance(r, dict)]
    sec = {x.get("sector"): x for x in (D or {}).get("srm") or []}
    def strong(r):
        rs, e, m = r.get("rs_spy_20d"), r.get("entry"), r.get("ma_50")
        return bool((r.get("on_longlist") or r.get("on_elder")) and isinstance(rs, (int, float)) and rs > 0
                    and isinstance(e, (int, float)) and isinstance(m, (int, float)) and e > m)
    def word(g, q):
        if g == "TURNING":
            return {"IMPROVING": "Turning up, now gaining on the market", "WEAKENING": "Turning back up after a pullback",
                    "LAGGING": "Turning up from the bottom, still lagging"}.get(q, "Turning up")
        if q == "IMPROVING":
            return "Improving: starting to beat the market"
        if q == "LEADING":
            return "Leading the market"
        return None
    kind = _group_kind
    groups = collections.defaultdict(list); meta = {}
    for r in rows:
        if not strong(r):
            continue
        for b in r.get("thematic_baskets") or []:
            k = kind(b.get("grade"), b.get("rrg_quadrant"))
            if k:
                key = ("Theme", b.get("basket")); groups[key].append(r); meta[key] = (k, word(b.get("grade"), b.get("rrg_quadrant")), b.get("grade"))
        x = sec.get(r.get("gics_sector_name"))
        if x:
            k = kind(x.get("grade"), x.get("rrg_quadrant"))
            if k:
                key = ("Sector", x.get("sector")); groups[key].append(r); meta[key] = (k, word(x.get("grade"), x.get("rrg_quadrant")), x.get("grade"))
    if not groups:
        return ""
    tag = {"ADVANCE": "p-up", "HOLD-FOR-CONDITIONS": "p-warn", "PASS": "p-n"}
    short = {"ADVANCE": "ADV", "HOLD-FOR-CONDITIONS": "HOLD", "PASS": "PASS"}
    def table(which):
        uniq = lambda k: len({r["ticker"] for r in groups[k]})
        ks = [k for k in groups if meta[k][0] == which and (k[0] == "Sector" or uniq(k) >= 2)]
        ks.sort(key=lambda k: (k[0] != "Sector", meta[k][2] != "TURNING", -uniq(k)))
        out = []
        for k in ks:
            names = sorted({r["ticker"]: r for r in groups[k]}.values(), key=lambda r: -r["rs_spy_20d"])
            shown = names[:6]
            cell = " ".join(f'<span class="chip"><b>{E(r["ticker"])}</b> {r["rs_spy_20d"]:+.0f}%'
                            + (f'<span class="pill {tag[verdicts[r["ticker"]]]}">{short[verdicts[r["ticker"]]]}</span>' if r["ticker"] in verdicts else "")
                            + "</span>" for r in shown) + (f' <span class="cond">+{len(names) - len(shown)} more</span>' if len(names) > len(shown) else "")
            out.append(f'<tr><td><b>{E(str(k[1]).replace("_", " "))}</b><div class="cond">{E(k[0])} · grade {E(str(meta[k][2]))}</div></td>'
                       f'<td>{E(meta[k][1] or "")}</td><td class="num">{len(names)}</td><td>{cell}</td></tr>')
        return ('<div class="tbl"><table><thead><tr><th>Group</th><th>What the group is doing</th><th>Strong names</th><th>Strongest, beat vs SPY over 20 days · committee verdict</th></tr></thead><tbody>'
                + "".join(out) + "</tbody></table></div>") if out else '<p class="cond">None today.</p>'
    return ('<section class="card"><div class="eyebrow">8 · Strong stocks riding a group turn · information only, not a vote</div>' + say("groups")
            + '<h3>Turning groups · where names are early in the turn</h3>' + table("turn")
            + '<h3 style="margin-top:12px">Already-leading groups · for context</h3>' + table("lead")
            + '<p class="cond"><b>How this is built.</b> AQE grades every sector and theme on its own trend (DEPLOY, HOLD, TURNING, WATCH, AVOID) '
              'and on whether it is gaining on the market (leading, improving, weakening, lagging). TURNING means the group is back above its 20-day average '
              'with this week beating this month. A strong name here is on the Longlist or Elder list, beating SPY over 20 days and above its 50-day average. '
              'Names with no verdict were not voted today. A name can appear under both its sector and its theme. Themes with only one strong name are left out.</p></section>')

def _weather_part1(v, crown, W, rows, dl=None, D_=None, verdicts=None):
    W = W or {}
    say = lambda k: f'<p class="why">{E(W[k])}</p>' if W.get(k) else ""
    if not v:
        return ('<div class="section-title"><h2>Part 1 · Daily weather</h2></div><section class="card"><p class="flag">'
                'Valen dashboard not served this run — declared gap, not a neutral reading.</p></section>')
    rm = v.get("read_me_first") or {}; st = _stance_word(v)
    hist = {h["label"]: h for h in v.get("history") or []}
    tone = {"RISK_ON": "p-up", "NEUTRAL": "p-warn", "RISK_OFF": "p-down"}.get(st, "p-n")
    o = [_freshness_html(v, _MARKER, _REFRESHED), '<div class="section-title"><h2>Part 1 · Daily weather</h2><span class="eyebrow">AQE numbers · plain-English read · as of '
         + E(str(v.get("exported_at") or v.get("date"))) + '</span></div>']
    # 1. Situational awareness and stance
    o.append(f'<section class="card"><div class="eyebrow">1 · Situational awareness and stance</div>'
             f'<h3>Stance <span class="pill {tone}">{E(st)}</span> <span class="pill p-n">Trend {E(str(v.get("regime")))}</span></h3>'
             + say("stance") +
             '<div class="tbl"><table><thead><tr><th>Index</th><th>Price</th><th>Daily buy signal</th><th>Weekly buy signal</th><th>Above a rising 5-day</th></tr></thead><tbody>'
             + "".join(f'<tr><td><b>{E(t["symbol"])}</b></td><td class="num">{_num(t.get("last_price"))}</td>'
                       + "".join(f'<td class="{"pos" if t.get(k) else "neg"}">{"Yes" if t.get(k) else "No"}</td>' for k in ("daily_buy_signal", "weekly_buy_signal", "above_rising_5d"))
                       + "</tr>" for t in v.get("trend") or [])
             + '</tbody></table></div><div class="tbl"><table><thead><tr><th>Stretch</th><th>Now</th><th>Flag</th></tr></thead><tbody>'
             + "".join(f'<tr><td>{E(e["label"])}</td><td class="num">{_num(e.get("value"))}</td><td>{"stretched" if e.get("flag") else "—"}</td></tr>' for e in v.get("extension") or [])
             + '</tbody></table></div><p class="cond"><b>What these mean.</b> <b>VIX</b> is the market\'s expected S&amp;P 500 swing over the next 30 days, read from option prices; <b>VIX3M</b> is the same over 3 months. '
             'Normally near-term fear is lower than longer-term fear, so the <b>VIX curve</b> slopes upward and VIX/VIX3M sits below 1. '
             'Under 0.82 is calm, 0.82 to 1.00 is normal, above 1.00 means near-term fear has overtaken the longer view (the curve has inverted): a stress signal. '
             '<b>Stretch</b> is how far the index sits from its 50-day average, in average daily ranges.</p>'
             + f'<p class="cond">Handbook doctrine for this stance (quoted, not an Aegis rule): {E(rm.get("so_what") or "")} AQE makes no sizing decision.</p></section>')
    # 2. GEX traffic light
    g = v.get("gex") or {}
    det = ((((crown or {}).get("readings") or {}).get("positioning") or {}).get("option_dealers") or {}).get("detail") or {}
    if g.get("status") == "OK" or det:
        lights = []
        for sym, d in (("SPY", det.get("SPY")), ("QQQ", det.get("QQQ"))):
            if not d:
                continue
            below = d.get("spot") is not None and d.get("gamma_flip") is not None and d["spot"] < d["gamma_flip"]
            lt = (g.get("light") if sym == "SPY" and g.get("light") else ("RED" if below else "GREEN"))
            cw = (d.get("call_wall") or {}).get("strike"); pw = (d.get("put_wall") or {}).get("strike")
            lights.append(f'<tr><td><span class="light" style="background:{LIGHT.get(str(lt).upper(), "var(--mute)")}"></span><b>{sym}</b> {E(str(lt))}</td>'
                          f'<td class="num">{_num(d.get("spot"))}</td><td class="num">{_num(d.get("gamma_flip"), "{:.2f}")}</td>'
                          f'<td class="num">{_num(d.get("flip_distance_pct"), "{:.2f}%")} {"below" if below else "above"}</td><td class="num">{_num(pw)}</td><td class="num">{_num(cw)}</td></tr>')
        o.append('<section class="card"><div class="eyebrow">2 · GEX traffic light · dealer gamma</div>'
                 + f'<h3>Dealer gamma <span class="pill {"p-down" if str(g.get("regime")).upper() == "NEGATIVE" else "p-up"}">{E(str(g.get("regime") or "—"))}</span></h3>'
                 + say("gex")
                 + '<div class="tbl"><table><thead><tr><th>Light</th><th>Price</th><th>Flip</th><th>Gap to flip</th><th>Put wall</th><th>Call wall</th></tr></thead><tbody>'
                 + "".join(lights) + '</tbody></table></div><p class="cond">Below the flip, dealers sell into falls and buy into rallies, so moves get bigger. '
                 'Which side dealers are on is a standard assumption, not observed data.</p></section>')
    # 3. Crown macro layer -- heartbeat, positioning, volatility, divergence, the call (PM 2026-10-23:
    # "make sure these are presenting and explained in easy to read form"). Numbers from aqe_crown_macro.json.
    ck = v.get("crown_cockpit") or {}; dv = ck.get("divergence") or {}
    CRr = (crown or {}).get("readings") or {}
    hb, vo, dvg = CRr.get("breadth") or {}, CRr.get("volatility") or {}, CRr.get("divergence") or {}
    tf = (CRr.get("positioning") or {}).get("trend_funds") or {}
    call = (crown or {}).get("the_call") or {}; scen = (crown or {}).get("scenario") or {}
    crm = (crown or {}).get("read_me_first") or {}; hc = (crown or {}).get("how_current") or {}
    kl = (crown or {}).get("key_levels") or []
    lv = lambda kind: [k for k in kl if k.get("kind") == kind]
    def kv(rows_):
        return '<div class="tbl"><table><tbody>' + "".join(f'<tr><td>{a}</td><td class="num"><b>{b}</b></td><td class="cond">{c}</td></tr>' for a, b, c in rows_) + "</tbody></table></div>"
    pct = lambda x: _num(x * 100 if isinstance(x, (int, float)) and abs(x) <= 1 else x, "{:.0f}")
    o.append('<section class="card"><div class="eyebrow">3 · Crown macro layer · heartbeat, positioning, volatility, divergence · oldest source '
             + E(str(hc.get("oldest_source") or "—")) + '</div>'
             + (f'<h3>{E(crm.get("headline") or "")}</h3>' if crm.get("headline") else "") + "</section>")
    # 3a heartbeat
    bl_ = {k["what"]: k for k in lv("breadth")}
    r20, hi12, lo12 = bl_.get("RSP/SPY 20-day average") or {}, bl_.get("RSP/SPY 12-month high") or {}, bl_.get("RSP/SPY 12-month low") or {}
    o.append('<section class="card"><div class="eyebrow">3a · Market heartbeat · equal-weight vs cap-weight S&amp;P</div>'
             + f'<h3>Breadth <span class="pill {"p-up" if hb.get("regime") == "broadening" else "p-warn"}">{E(str(hb.get("regime") or "—"))}</span>'
             + f' <span class="pill p-n">{"gate passed" if hb.get("passed_the_gate") else "gate FAILED"}</span></h3>' + say("heartbeat")
             + kv([("Days in this regime", _num(hb.get("days_in_this_regime")), ""),
                   ("Position in its 12-month range", E(str(hb.get("position_in_12_month_range") or "—")), f'low {_num(lo12.get("level"), "{:.4f}")} · now {_num(r20.get("now"), "{:.4f}")} · high {_num(hi12.get("level"), "{:.4f}")}'),
                   ("Change 5 / 20 / 60 days", f'{_num(hb.get("change_5d_pct"), "{:+.1f}%")} / {_num(hb.get("change_20d_pct"), "{:+.1f}%")} / {_num(hb.get("change_60d_pct"), "{:+.1f}%")}', ""),
                   ("Its own 20-day average", _num(r20.get("level"), "{:.4f}"), "falling back under it is the first sign breadth is narrowing again"),
                   ("Confidence in the read", _num(hb.get("confidence")), "under 0.40 Crown stops: a market it cannot read gets no call")])
             + '<p class="cond"><b>What this is.</b> RSP holds every S&amp;P 500 stock in equal size; SPY weights them by size, so a few giants dominate it. '
               'RSP/SPY rising means the average stock is keeping up with the giants: a broad market, good for stock pickers. Falling means a narrow market carried by a handful of names. '
               'Crown reads this first; if it cannot read it, nothing else is used.</p></section>')
    # 3b positioning
    flips = sorted([k for k in lv("trend followers") if isinstance(k.get("distance_pct"), (int, float))], key=lambda k: abs(k["distance_pct"]))[:6]
    sect = tf.get("by_sector") or {}
    o.append('<section class="card"><div class="eyebrow">3b · Positioning · trend-following funds</div>'
             + f'<h3>Trend funds <span class="pill p-n">{E(str(tf.get("bias") or "—"))}</span> <span class="pill p-n">size dial {_num(tf.get("size_dial"))}×</span></h3>' + say("positioning")
             + kv([("Markets read", _num(tf.get("markets_read")), ""),
                   ("Share at an extreme", f'{pct(tf.get("share_at_an_extreme"))}%', "high = crowded, fragile"),
                   ("Lean by sector", " · ".join(f'{E(k)} <span class="{"pos" if x >= 0 else "neg"}">{x:+.2f}</span>' for k, x in sorted(sect.items(), key=lambda kv_: -kv_[1])) or "—", "+ long, − short, −1 to +1")])
             + ('<h3 style="margin-top:10px">Nearest lines where they turn</h3><div class="tbl"><table><thead><tr><th>Market</th><th>Now</th><th>Flip</th><th>Distance</th><th>What happens</th></tr></thead><tbody>'
                + "".join(f'<tr><td>{E(k["what"].replace(" flip", ""))}</td><td class="num">{_num(k.get("now"), "{:,.2f}")}</td><td class="num">{_num(k.get("level"), "{:,.2f}")}</td>'
                          f'<td class="num">{_num(k.get("distance_pct"), "{:+.1f}%")}</td><td>{"turn buyer above" if k.get("direction") == "buy_above" or "seller to buyer" in (k.get("if_it_breaks") or "") else "turn seller below"}</td></tr>' for k in flips)
                + "</tbody></table></div>" if flips else "")
             + '<p class="cond"><b>What this is.</b> Trend-following funds (CTAs) buy what is rising and sell what is falling by formula, and they all use similar rules. '
               'We replicate that formula across 18 futures markets to estimate their position and, more usefully, the price where each market would flip them from buyer to seller. '
               'Those flip lines are where moves can speed up. The size dial is Crown\'s multiplier on your own normal risk: 1.00 means no change. Dealer positioning is block 2; speculator crowding is block 4.</p></section>')
    # 3c volatility
    vl = {k["what"]: k for k in lv("volatility")}
    calm, elev = vl.get("Single-stock vs index gap — calm band") or {}, vl.get("Single-stock vs index gap — elevated band") or {}
    ic = next((k for k in kl if k.get("kind") == "correlation"), {})
    o.append('<section class="card"><div class="eyebrow">3c · Volatility · VIX, single-stock volatility (VIXEQ) and the gap · as of '
             + E(str(hc.get("volatility_as_of") or "—")) + '</div>'
             + f'<h3>Gap <span class="pill {"p-warn" if "ELEVATED" in str(vo.get("state")) else "p-n"}">{E(str(vo.get("state") or "—").replace("_", " ").lower())}</span>'
             + f' <span class="pill p-n">VIX curve {E(str(vo.get("term_structure") or "—").lower())}</span></h3>' + say("volatility")
             + kv([("VIX · index volatility", _num(vo.get("vix")), "15 or less with calm dealers favours selling premium · 25+ means protection is already expensive"),
                   ("VIXEQ · average single-stock volatility", _num(vo.get("single_stock_vol")), ""),
                   ("Gap (VIXEQ − VIX)", _num(vo.get("gap")), f'calm under {_num(calm.get("level"))} · elevated over {_num(elev.get("level"))}'),
                   ("Gap vs last 2 years", f'{pct(vo.get("gap_vs_history"))}th percentile', f'change over 20 days {_num(vo.get("gap_change_20d"), "{:+.2f}")}'),
                   ("Implied correlation", _num(vo.get("implied_correlation")), f'{_num(ic.get("now"))}th percentile · low = stocks move on their own news, so stock picking pays')])
             + '<p class="cond"><b>What this is.</b> VIX measures how much traders expect the S&amp;P 500 index to swing. VIXEQ (Cboe) measures the same for the average large stock. '
               'The gap between them shows how much single stocks are moving that the index hides. A wide gap means opportunity and risk sit in individual names, not the index; '
               'a gap that is narrowing means stress is leaving, so buying index protection now is late. Implied correlation is how much stocks are expected to move together. '
               'A VIX curve in contango (near-term cheaper than longer-term) is the normal, calm shape; inverted is stress.</p></section>')
    # 3d divergence
    o.append('<section class="card"><div class="eyebrow">3d · Divergence · is anything not confirming the move?</div>'
             + f'<h3>Market-level warnings <span class="pill {"p-warn" if (dv.get("count") or 0) else "p-up"}">{_num(dv.get("count"))} of {_num(dv.get("total"))}</span>'
             + f' <span class="pill p-n">{_num(dvg.get("warnings_lit"))} on individual markets</span></h3>' + say("divergence")
             + kv([("Firing", E(", ".join({"rsi": "momentum (RSI) not confirming price"}.get(x, x.replace("_", " ")) for x in dv.get("types_fired") or []) or "none"), "")])
             + '<p class="cond"><b>What this is.</b> A divergence is when one reading fails to confirm another: price making highs while momentum fades, '
               'or stocks rising while copper, credit, the dollar or volatility say otherwise. Crown checks eight types at the market level and the same tests on each futures market. '
               'One warning is not a reason to sell; several pointing the same way as weakening breadth is.</p></section>')
    # 3e the call, scenario, what would change it, calendar
    COND = {"broadening": "breadth broadening", "narrowing": "breadth narrowing", "range_not_extreme": "breadth not at an extreme of its range",
            "range_extreme": "breadth at an extreme of its range", "cta_low_flip": "trend funds not crowded", "cta_high_flip": "trend funds crowded",
            "gamma_positive": "dealers damping moves (gamma positive)", "gamma_negative": "dealers amplifying moves (gamma negative)",
            "dispersion_normal": "single-stock vs index volatility gap normal", "dispersion_elevated": "volatility gap elevated", "rsi": "momentum (RSI) not confirming price"}
    plain = lambda xs: ", ".join(COND.get(x, str(x).replace("_", " ")) for x in xs or []) or "none"
    wc = crm.get("what_would_change_it") or []
    cal = [x for x in ((crown or {}).get("what_is_coming") or []) if x.get("kind") == "macro"][:5]
    o.append('<section class="card"><div class="eyebrow">3e · Crown\'s call and the macro story</div>'
             + (f'<h3>Call <span class="pill p-n">{E(str(call.get("expression_family")))}</span> <span class="pill p-warn">{E(str(call.get("match_quality")))} fit</span>'
                f' <span class="pill p-n">size {_num(call.get("size_multiplier"))}×</span></h3>' if call else "") + say("call")
             + kv([("Conditions met", E(plain(call.get("conditions_met"))), ""),
                   ("Conditions not met", E(plain(call.get("conditions_not_met"))), ""),
                   ("Leading macro story", E(str(scen.get("leading") or "—")).replace("_", " ").title(),
                    f'{pct(scen.get("score_share_of_conditions"))}% of its conditions met' + (f' · contested with {E(str(scen.get("runner_up")).replace("_", " ").title())}' if scen.get("contested") else ""))])
             + (f'<p class="cond">{E(scen.get("story") or "")}</p>' if scen.get("story") else "")
             + ('<p class="eyebrow" style="margin-top:8px">What would change the call</p><ul>' + "".join(f"<li>{E(x)}</li>" for x in wc) + "</ul>" if wc else "")
             + ('<p class="eyebrow" style="margin-top:8px">Coming up · what each event tests</p><div class="tbl"><table><tbody>'
                + "".join(f'<tr><td>{E(x.get("day") or "")} {E(str(x.get("date") or ""))}</td><td><b>{E(x.get("event") or "")}</b></td><td class="cond">{E(x.get("what_it_tests") or "")}</td></tr>' for x in cal)
                + "</tbody></table></div>" if cal else "")
             + '<p class="cond">Crown names a family of trades and a multiplier on your own risk, never a ticker or a size. A scenario score is the share of its conditions met, not a probability.</p></section>')
    # 4. COT crowded positions
    cot = ck.get("cot") or (((crown or {}).get("readings") or {}).get("positioning") or {}).get("large_speculators") or {}
    nm = lambda c: f'<b>{E(c)}</b> {E(COT_NAMES.get(c, ""))}'.strip()
    o.append('<section class="card"><div class="eyebrow">4 · COT · where large speculators are crowded · CFTC report as of '
             + E(str(cot.get("as_of"))) + '</div><div class="grid2">'
             + '<div><h3 class="pos">Crowded long</h3><p>' + (" · ".join(nm(c) for c in cot.get("crowded_long") or []) or "none") + "</p></div>"
             + '<div><h3 class="neg">Crowded short</h3><p>' + (" · ".join(nm(c) for c in cot.get("crowded_short") or []) or "none") + "</p></div></div>"
             + say("cot") + '<p class="cond"><b>What this is.</b> The CFTC publishes every week how traders are positioned in US futures (the Commitments of Traders report). '
             '<b>Large speculators</b> are the hedge funds and trend-following funds. We take their net position as a share of all open contracts and rank it against the last three years: '
             'at the 85th percentile or higher it is <b>crowded long</b>, at the 15th or lower <b>crowded short</b>. Crowded is a warning, not a signal: when everyone is already in, '
             'the next surprise forces them out together, so crowded longs fall hardest on bad news and crowded shorts squeeze on good news. '
             'The report covers Tuesday and is published Friday, so it is at least three days old and cannot time a trade.</p></section>')
    # 5. Market checklist and instruments
    bl = v.get("breadth") or []
    def brow(b):
        val = b.get("display") or b.get("value")
        ok = b.get("value") if b.get("kind") == "bool" else b.get("flag")
        cls = "pos" if ok is True else ("neg" if ok is False else "")
        return f'<tr><td>{E(b["label"])}</td><td class="num {cls}">{E(_num(val) if not isinstance(val, bool) else ("Pass" if val else "Fail"))}</td></tr>'
    o.append('<section class="card"><div class="eyebrow">5 · Direction of the wind · checklist and instruments</div>' + say("checklist") + _wind_gauges(v) + '<div class="grid2" style="margin-top:12px">'
             + '<div><h3>Checklist</h3><div class="tbl"><table><tbody>' + "".join(brow(b) for b in bl if b.get("section") == "checklist") + "</tbody></table></div></div>"
             + '<div><h3>Instruments</h3><div class="tbl"><table><tbody>' + "".join(brow(b) for b in bl if b.get("section") == "instrument") + "</tbody></table></div></div></div>"
             + '<p class="cond"><b>T2108</b> is the share of stocks trading above their own 40-day average: a quick read of how many stocks are in short-term uptrends. '
             'Under 20% is washed out (often near a low), over 80% is overheated; Valen wants it above 50% before calling the market risk-on. '
             'The <b>4% count</b> compares stocks up 4% or more in a day with stocks down 4% or more, summed over 5 or 10 days: above 1 means buyers are winning the big days. '
             'All of these are measured on AQE\'s own list, not the whole market.</p></section>')
    # 6. Weather turning
    wf = [x for x in rm.get("watch_for") or [] if not _already_met(x)]
    o.append('<section class="card"><div class="eyebrow">6 · Weather turning · now vs 5 days vs 1 month</div>' + say("turning")
             + '<div class="tbl"><table><thead><tr><th>Reading</th><th>Now</th><th>5 days ago</th><th>1 month ago</th></tr></thead><tbody>'
             + "".join(f'<tr><td>{E(h["label"])}</td><td><b>{E(_num(h.get("now")))}</b></td><td>{E(_num(h.get("5d_ago")))}</td><td>{E(_num(h.get("1mo_ago")))}</td></tr>' for h in v.get("history") or [])
             + "</tbody></table></div>"
             + ('<p class="eyebrow" style="margin-top:8px">What would change the stance</p><ul>' + "".join(f"<li>{E(x)}</li>" for x in wf) + "</ul>" if wf else "")
             + "</section>")
    # 7. Theme leaders and rotation
    tl = v.get("theme_leaders") or []
    lead = [t for t in tl if t.get("rotation_state") in ("LEADING", "OFF_THE_FLOOR")]
    lead.sort(key=lambda t: (t.get("rotation_state") != "LEADING", -(t.get("ret_1m_pct") or -99)))
    rot = sorted(v.get("rotation") or [], key=lambda t: -(t.get("thrust") or -99))[:6]
    trow = lambda t, extra: (f'<tr><td>{E(t.get("display_name") or t["name"])}</td><td class="num {"pos" if (t.get("ret_1w_pct") or 0) >= 0 else "neg"}">{_num(t.get("ret_1w_pct"), "{:+.1f}%")}</td>'
                             f'<td class="num {"pos" if (t.get("ret_1m_pct") or 0) >= 0 else "neg"}">{_num(t.get("ret_1m_pct"), "{:+.1f}%")}</td><td class="num">{_num(t.get("pct_off_52w_high"), "{:.1f}%")}</td>{extra}</tr>')
    o.append('<section class="card"><div class="eyebrow">7 · Theme leaders and rotation</div>' + say("themes")
             + ("<ul>" + "".join(f"<li>{E(x)}</li>" for x in v.get("neighbourhood") or []) + "</ul>" if v.get("neighbourhood") else "")
             + '<h3>Leaders</h3><div class="tbl"><table><thead><tr><th>Theme</th><th>1 week</th><th>1 month</th><th>Off 52w high</th><th>State</th></tr></thead><tbody>'
             + "".join(trow(t, f'<td>{E(str(t.get("rotation_state")).replace("_", " ").title())}</td>') for t in lead)
             + '</tbody></table></div><h3 style="margin-top:10px">Rotation · where the turn is sharpest</h3><div class="tbl"><table><thead><tr><th>Theme</th><th>1 week</th><th>1 month</th><th>Off 52w high</th><th>State</th></tr></thead><tbody>'
             + "".join(trow(t, f'<td>{E(_thrust_state(t))}</td>') for t in rot)
             + '</tbody></table></div><p class="cond"><b>How the order is set.</b> Each theme is ranked by its <b>thrust</b>: this week\'s return minus this month\'s return. '
               'A theme down 8% this week but 32% over the month has a big thrust, because it is falling much less sharply than before, not because it is rising. '
               '<b>State</b> says it plainly: Rising (up on both), Turning up (up this week, still down on the month), Still falling but slower, or Falling faster.</p></section>')
    o.append(_group_turns(D_, verdicts or {}, say))
    hs = collections.Counter()
    for r in rows.values():
        for x in _house_setups(r):
            hs[(x.get("setup"), x.get("status"))] += 1
    ready = [k for k in hs if k[1] in ("TRIGGERED", "READY")]
    o.append('<section class="card"><div class="eyebrow">Valen house setups across the list</div><p>'
             + (", ".join(f"{E(a)} {E(b)} ×{n}" for (a, b), n in sorted(hs.items())) or "none graded")
             + (". <b>None is TRIGGERED or READY.</b>" if not ready else "") + "</p></section>")
    return "\n".join(o)

def _now_summary(refreshed):
    """The NOW half, from the refreshed Valen file's legs table: 'all current' or 'all current except <leg date reason>'."""
    df = (refreshed or {}).get("data_freshness") or {}
    rows = df.get("legs_table") or []
    if not rows:
        return None
    off = [r for r in rows if r.get("reason") != "CURRENT"]
    when = str((refreshed or {}).get("exported_at") or (refreshed or {}).get("date") or "")
    if not off:
        body = f"all current for the {df.get('expected_session')} close"
    else:
        def one(r):
            extra = ""
            if r.get("reason") == "PUBLISHER_CADENCE" and "next release" in (r.get("detail") or ""):
                extra = " (latest published; next release " + r["detail"].split("next release ")[-1] + ")"
            return f"{r['leg']} {r.get('as_of')} [{r.get('reason')}]{extra}"
        body = f"all current except " + "; ".join(one(r) for r in off)
    return f"NOW (refreshed {when}, after the committee): {body}"


def _freshness_html(v, marker=None, refreshed=None):
    """One line on every card page: expected session and each macro leg's date with its reason code (PM 2026-11-04). It carries BOTH
    halves when main has refreshed weather: 'AT RUN TIME: <what the committee saw>' and 'NOW (refreshed ..., after the committee):
    all current except ...'. At-run-time comes from the run's Valen legs table, else the run marker's 'Macro legs:' line; only if
    neither exists is it a declared gap."""
    line = ((v or {}).get("data_freshness") or {}).get("line")
    at_run = None
    if line:
        at_run = line.replace("FRESHNESS | ", "", 1)
    elif marker:
        ml = str(marker.get("macro_legs") or "")
        if ml and not ml.startswith("unknown"):
            at_run = ml.replace("Macro legs:", "").strip() + " (from the run marker)"
    now = _now_summary(refreshed) if refreshed is not None else None
    if at_run and now:
        return f'<div class="flag freshness"><b>FRESHNESS</b> | <b>AT RUN TIME:</b> {E(at_run)} | <b>{E(now)}</b></div>'
    if at_run:
        return f'<div class="flag freshness"><b>FRESHNESS</b> | {E(at_run)}</div>'
    if now:
        return f'<div class="flag freshness"><b>FRESHNESS</b> | at run time: not recorded in this run | <b>{E(now)}</b></div>'
    if not v and not marker:
        return '<div class="flag freshness"><b>FRESHNESS</b> | no Valen file and no run marker - no macro leg can be dated (declared gap)</div>'
    return '<div class="flag freshness"><b>FRESHNESS</b> | this Valen file carries no legs table and the run marker has none - the macro legs cannot be dated (declared gap)</div>'


def _stance_word(v):
    """The stance, or WITHHELD with the reason - never blank, never a guess."""
    st = (v or {}).get("stance") or {}
    w = st.get("word") or st.get("stance")
    if w:
        return str(w)
    why = st.get("reason") or ((v or {}).get("data_freshness") or {}).get("banner") or (v or {}).get("reason") or "inputs not current"
    return "WITHHELD - " + str(why)[:160]


def _valen_card(v, rows, room):
    if not v:
        return '<section class="card"><div class="eyebrow">Valen · market weather</div><p class="flag">Valen dashboard not served this run — declared gap, not a neutral reading.</p></section>'
    rm = v.get("read_me_first") or {}; st = _stance_word(v)
    hist = {h["label"]: h for h in v.get("history") or []}
    tone = {"RISK_ON": "p-up", "NEUTRAL": "p-warn", "RISK_OFF": "p-down"}.get(st, "p-n")
    o = ['<section class="card"><div class="eyebrow">Valen · the VIV System market weather (AQE)</div>',
         f'<h3>Stance <span class="pill {tone}">{E(st)}</span>'
         + (f' <span class="eyebrow">5 days ago {E(str(hist.get("Stance", {}).get("5d_ago")))} · 1 month ago {E(str(hist.get("Stance", {}).get("1mo_ago")))}</span>' if "Stance" in hist else "")
         + '</h3>', f'<p>{E(rm.get("headline") or "")}</p>',
         f'<p class="flag">Handbook doctrine (quoted, not an Aegis rule): <b>{E(rm.get("so_what") or "")}</b> AQE makes no sizing decision.</p>',
         '<div class="tbl"><table><thead><tr><th>Block</th><th>Reading</th><th>Now</th><th>5 days ago</th><th>1 month ago</th></tr></thead><tbody>']
    for t in v.get("trend") or []:
        for k, lab in (("daily_buy_signal", "daily buy signal"), ("weekly_buy_signal", "weekly buy signal"), ("above_rising_5d", "above a rising 5-day")):
            val = t.get(k)
            o.append(f'<tr><td>Trend</td><td>{E(t["symbol"])} {lab}</td><td class="{"pos" if val else "neg"}">{"Yes" if val else "No"}</td><td></td><td></td></tr>')
    for e in v.get("extension") or []:
        h = next((x for x in hist.values() if x["label"].lower().startswith(e["label"].lower()[:12])), {})
        o.append(f'<tr><td>Extension</td><td>{E(e["label"])}</td><td>{E(str(e["value"]))}</td><td>{E(str(h.get("5d_ago", "")))}</td><td>{E(str(h.get("1mo_ago", "")))}</td></tr>')
    for b in v.get("breadth") or []:
        val = b.get("display") or b.get("value"); h = hist.get("T2108", {}) if "T2108" in b["label"] else {}
        o.append(f'<tr><td>Breadth</td><td>{E(b["label"])}</td><td>{E(str(val))}</td><td>{E(str(h.get("5d_ago", "")))}</td><td>{E(str(h.get("1mo_ago", "")))}</td></tr>')
    o.append('</tbody></table></div>')
    g = v.get("gex") or {}
    if g.get("status") == "OK":
        o.append(f'<p><b>Dealer gamma {E(str(g.get("regime")))} ({E(str(g.get("light")))}):</b> SPY {g.get("price")} · flip {g.get("flip")} · call wall {g.get("call_wall")} · put wall {g.get("put_wall")}. {E(g.get("commentary") or "")} <span class="eyebrow">Dealer side is an assumed convention, not observed data.</span></p>')
    if v.get("neighbourhood"):
        o.append("<ul>" + "".join(f"<li>{E(x)}</li>" for x in v["neighbourhood"]) + "</ul>")
    tl = sorted(v.get("theme_leaders") or [], key=lambda t: -(t.get("ret_1w_pct") or -99))
    if tl:
        o.append('<div class="tbl"><table><thead><tr><th>Theme</th><th>1 week</th><th>1 month</th><th>Off 52w high</th><th>Quadrant</th></tr></thead><tbody>')
        for t in tl[:6] + tl[-3:]:
            o.append(f'<tr><td>{E(t.get("display_name") or t["name"])}</td><td class="{"pos" if (t.get("ret_1w_pct") or 0) >= 0 else "neg"}">{t.get("ret_1w_pct"):+.2f}%</td><td>{t.get("ret_1m_pct"):+.2f}%</td><td>{t.get("pct_off_52w_high")}%</td><td>{E(str(t.get("rrg_quadrant")).title())}</td></tr>')
        o.append('</tbody></table></div>')
    wf = rm.get("watch_for") or []
    if wf:
        o.append('<p class="eyebrow">What would change the stance</p><ul>' + "".join(f"<li>{E(x)}</li>" for x in wf) + "</ul>")
    hs = collections.Counter()
    for r in rows.values():
        for x in _house_setups(r):
            hs[(x.get("setup"), x.get("status"))] += 1
    ready = [k for k in hs if k[1] in ("TRIGGERED", "READY")]
    o.append(f'<p><b>House setups across the list:</b> ' + (", ".join(f"{E(a)} {E(b)} ×{n}" for (a, b), n in sorted(hs.items())) or "none graded")
             + (". <b>None is TRIGGERED or READY.</b>" if not ready else "") + "</p>")
    o.append("</section>")
    return "\n".join(o)



# ---- R34 / R31 (PM 2026-10-30): the slate's status, its objections, and the Detect-lens list. -------
# Rendered from consensus.json / the export only -- never from the words file. Rows without `status`
# (pre-redesign runs) render exactly as before: every helper returns "" when the field is absent.
def _committee_block(pos, on):
    """R42: the committee's position. VISIBLE on the card: 'Conviction 4 of 5' (plain, PM-signed scale) and a dissent count. The
    committee's verbatim rationale (Why / Also / What would change it / minority notes) is the AUDIT TRAIL: kept whole, folded in a
    <details> closed by default (PM 2026-11-04: the wall of C-codes, scores and indicator names was unreadable on the card).
    `on` False = the run predates R42 or no position file was passed: print nothing. On and missing = a declared gap."""
    if not on:
        return ""
    if not pos:
        return '<div class="committee"><b>Committee position:</b> not filed for this ticket &mdash; declared gap, nothing invented.</div>'
    n = pos.get("committee_conviction")
    head = f"Conviction {n} of 5" if isinstance(n, int) else "Conviction not counted (fewer than 4 scores filed)"
    mn = pos.get("minority_notes") or []
    ndis = sum(1 for m in mn if "DISSENT" in str(m.get("kind", "")))
    vis = E(head) + (f" &middot; {ndis} reviewer{'s' if ndis != 1 else ''} dissent{'s' if ndis == 1 else ''} (see the audit trail)" if ndis else "")
    why = " ".join(E(c["text"]) for c in pos.get("why") or []) or "no rationale filed"
    also = "".join(f' <span class="also"><b>Also ({E(a["voice"])}):</b> {E(a["text"])}</span>' for a in pos.get("also") or [])
    wc = " ".join(E(c["text"]) for c in pos.get("what_would_change_it") or []) or "none filed"
    stage = ' <b>[DRAFT, not adopted]</b>' if pos.get("rationale_stage") == "draft" else ""
    mino = ('<div class="minority"><b>Minority note:</b> ' + " &middot; ".join(f'{E(m["voice"])} ({E(m["kind"])}): {E(m["text"])}' for m in mn) + "</div>") if mn else ""
    gaps = f'<div class="cond">{E("; ".join(pos.get("gaps") or []))}</div>' if pos.get("gaps") else ""
    return (f'<div class="committee"><b>{vis}</b>{" " + stage if stage else ""}'
            f'<details class="audit"><summary>Audit trail: what each reviewer filed (verbatim)</summary>'
            f'<div>Why: {why}{also} What would change it: {wc}{mino}{gaps}</div></details></div>')


def _rationale_banner(pos_doc, on):
    """R42: a rationale that is not the adopted final is declared at the top of the page, never a silent fallback."""
    if not on:
        return ""
    ts = list((pos_doc or {}).get("tickets", {}).values())
    stages = {t.get("rationale_stage") for t in ts}
    if not ts or stages == {"final"}:
        return ""
    if stages <= {"draft"}:
        msg = "Committee rationale: DRAFT, not adopted - the final rationale was not filed (Chair draft shown, labelled)."
    elif "draft" in stages:
        msg = "Committee rationale: some tickets show a DRAFT, not adopted - the final rationale is incomplete."
    else:
        msg = "Committee rationale: NOT FILED this run - declared gap, nothing invented."
    return f'<p class="flag"><b>{E(msg)}</b></p>'


def _status_pills(cons):
    by = collections.Counter(c.get("status") for c in cons if c.get("status"))
    if not by:
        return ""
    return '<span class="pill p-n">' + " · ".join(f"{by[k]} {k}" for k in ("AGREED", "CONTESTED", "DROPPED") if by.get(k)) + "</span>"


def _contest_html(c):
    st = c.get("status")
    if not st:
        return ""
    n = c.get("n_deciders") or 7
    if st == "CONTESTED":
        objs = c.get("objections") or []
        items = "".join(f"<li><b>{E(str(o.get('voice', '')))}</b>: {E(str(o.get('objection') or ''))}"
                        + (f" &mdash; <i>would clear:</i> {E(str(o.get('would_clear')))}" if o.get("would_clear") else "") + "</li>"
                        for o in objs)
        return (f'<div class="flag">Contested &middot; {len(objs)} of {n} object &middot; stays listed'
                f'<details class="audit"><summary>Audit trail: the objections (verbatim)</summary><ul>{items}</ul></details></div>')
    res = c.get("reservations") or []
    if st == "AGREED" and res:
        return ('<div class="cond">Agreed, with ' + f"{len(res)} reservation{'s' if len(res) != 1 else ''}" +
                '<details class="audit"><summary>Audit trail: the reservations (verbatim)</summary>' + "; ".join(
            f"<b>{E(str(r.get('voice', '')))}</b> &mdash; {E(str(r.get('reservation') or ''))}" for r in res) + "</details></div>")
    if st == "AGREED":
        return '<p class="cond">Agreed &middot; no objections</p>'
    return ""


def _dropped_prefix(c):
    st = c.get("status")
    if st == "DROPPED":
        return f"<b>DROPPED</b> by {len(c.get('objections') or [])} of {c.get('n_deciders') or 7} objections (R34) &middot; "
    if st == "NOT_SLATED":
        return "Not slated by the Chair &middot; "
    return ""


def _detect_lens_panel(D, cons):
    """R31: Detect-lens is an independent top-10 LIST, not a voice. AQE already ranks it
    (lens_ranking.ranked, sorted lens_positive desc, warnings asc, sc_momentum desc); the row field
    `rank` is NOT the lens rank. A name here that the room passed on is visible by design."""
    ranked = ((D.get("lens_ranking") or {}).get("ranked") or [])[:10]
    head = '<section class="card"><div class="eyebrow">Detect-lens top 10 &middot; AQE\'s own lens count &middot; an independent list, not a vote</div>'
    if not ranked:
        return head + '<p class="cond">lens_ranking is not served in today\'s export &mdash; declared gap, nothing invented.</p></section>'
    room = {c["ticker"]: c for c in cons}
    def marker(t):
        c = room.get(t)
        if not c:
            return "&mdash;"
        return E(c.get("verdict", "")) + (f" &middot; {E(c['status'])}" if c.get("status") else "") + " (in the room)"
    _byt = {r.get("ticker"): r for r in (D.get("daily_list") or []) if isinstance(r, dict)}
    rows = "".join(f'<tr><td class="num">{E(str(x.get("rank", i)))}</td><td><b>{E(str(x.get("ticker")))}</b>{_ma_pill(_byt.get(x.get("ticker")))}</td>'
                   f'<td class="num">{E(str(x.get("positive", "")))}</td><td class="num">{E(str(x.get("warnings", "")))}</td><td>{marker(x.get("ticker"))}</td></tr>'
                   for i, x in enumerate(ranked, 1))
    return (head + '<div class="tbl"><table><thead><tr><th>#</th><th>Ticker</th><th>Strong lenses</th><th>Warnings</th><th>Committee</th></tr></thead><tbody>'
            + rows + '</tbody></table></div><p class="cond">Where the lens and the committee disagree, both are shown; neither overrides the other.</p></section>')



def _valen_management_html(V, held):
    """PM 2026-11-01 (weather-spec item 6): Valen's management switch and per-position trim/trail FACTS under
    the book table. Readings + the handbook quoted as doctrine -- the trim/trail/add call is the PM's. Rendered
    from aqe_valen_dashboard.json's management block only; absent = one declared line, never blank."""
    mg = (V or {}).get("management") or {}
    mn = mg.get("manage_note") or {}
    out = []
    if mn.get("status") == "OK":
        out.append(f'<p class="cond"><b>Valen management switch:</b> {E(mn.get("note", ""))} <i>{E(mn.get("doctrine", ""))}</i></p>')
    else:
        out.append(f'<p class="cond">Valen management switch not served ({E(str(mn.get("reason") or "no Valen management block"))}) &mdash; declared gap.</p>')
    tt = [r for r in (mg.get("trim_trail") or []) if r.get("ticker") in held] if held else (mg.get("trim_trail") or [])
    if tt:
        def _f(v, fmt="{:g}"):
            return fmt.format(v) if isinstance(v, (int, float)) else "&mdash;"
        def _b(v):
            return "yes" if v is True else ("no" if v is False else "&mdash;")
        out.append('<div class="tbl"><table><thead><tr><th>Name</th><th>R (approx.)</th><th>2R+</th><th>First target printed</th><th>vs 20-day line</th><th>Stop distance</th><th>Days held</th><th>Gaps</th></tr></thead><tbody>'
                   + "".join(f'<tr><td><b>{E(str(r.get("ticker")))}</b></td><td class="num">{_f(r.get("r_multiple"), "{:+.2f}")}</td><td>{_b(r.get("r_multiple_2r_or_more"))}</td>'
                             f'<td>{_b(r.get("tp1_printed"))}</td><td class="num">{_f(r.get("pct_vs_ma_20"), "{:+.1f}%")}</td><td class="num">{_f(r.get("dist_from_stop_pct"), "{:.1f}%")}</td>'
                             f'<td class="num">{_f(r.get("days_held"), "{:d}")}</td><td>{E(", ".join(r.get("gaps") or []) or "&mdash;")}</td></tr>' for r in tt)
                   + '</tbody></table></div><p class="cond">Facts beside the handbook: <i>trim into strength; trail the rest on one moving average, daily closes; add only when a winner proves itself again</i> (pieces 17&ndash;19, quoted). R is approximate (current stop as the risk). The call is yours.</p>')
    return "".join(out)

def cmd_render(a):
    global _ONE_R, _MARKER, _REFRESHED
    _ONE_R = _one_r_usd()
    _MARKER = load(a.last_run, None) if getattr(a, "last_run", None) and os.path.exists(a.last_run) else None
    _REFRESHED = load(a.refreshed_valen, None) if getattr(a, "refreshed_valen", None) and os.path.exists(a.refreshed_valen) else None
    T = load(a.text); cons = load(a.consensus)
    gaps = _validate_text(T, cons, legacy=bool(getattr(a, "allow_legacy_text", False)))
    if a.valen and os.path.exists(a.valen):
        gaps += [f"weather.{k}" for k in WEATHER_KEYS if not (T.get("weather") or {}).get(k)]
    if gaps:
        print("REFUSED: cards_text.json is incomplete -- the report is never published with blanks:")
        for g in gaps:
            print("  -", g)
        sys.exit(2)
    D = load(a.export); rows = {r["ticker"]: r for r in D["daily_list"]}
    for h in D.get("held_positions") or []:
        rows.setdefault(h["ticker"], h)
    held = {h["ticker"]: h for h in D.get("held_positions") or []}
    CD = load(a.cards); BR = (load(a.brackets, {}) or {}).get("brackets") or {}
    BS = (load(a.broker_stops, {}) or {}).get("positions") or {}
    P4 = load(a.phase4); lane = {r["ticker"]: r["lane"] for r in P4["ranked"]}
    V = load(a.valen, {}) if a.valen else {}
    CR = load(a.crown, {}) if getattr(a, "crown", None) else {}
    SC = open(a.scorecard).read() if a.scorecard and os.path.exists(a.scorecard) else ""
    # R41 (PM 2026-11-02): Valen's no-buy list is NOT read here -- no card, hold row or pass row carries it.
    SL = load(a.slate, {}) if getattr(a, "slate", None) else {}
    PS = load(a.position, {}) if getattr(a, "position", None) and os.path.exists(a.position) else None
    POS_ON = PS is not None                                    # R42: a position file was passed => every slated ticket shows one
    POS = (PS or {}).get("tickets") or {}
    MK = _market_kill_text(SL.get("market_kill")) if isinstance(SL, dict) else ""
    if MK:
        mk_line = (f'<div class="flag"><b>Void every new trigger if:</b> {E(_plain_void(SL.get("market_kill")))}'
                   f'<details class="audit"><summary>Audit trail: the verbatim line</summary>{E(MK)}</details></div>')
    elif isinstance(SL, dict) and "market_kill" in SL:
        mk_line = '<p class="cond">Market kill (R40): none -- no seat named a market condition.</p>'
    else:
        mk_line = ""
    mk_line += _rationale_banner(PS, POS_ON)
    by = collections.defaultdict(list)
    for c in cons:
        by[c["verdict"]].append(c)
    order = {"ok": 0, "warn": 1, "bad": 2}
    adv = sorted(by["ADVANCE"], key=lambda c: (order.get(T["cards"][c["ticker"]]["readiness_tone"], 3), c["ticker"]))
    def _no_ladder(t):
        _b = BR.get(t) or {}
        _c = (CD["advance"].get(t) or {})
        _tr = next((x for x in (_c.get("triggers") or []) if x.get("kind") == "close_above" and isinstance(x.get("level"), (int, float))), None)
        _p = (_b.get("price") or {}).get("value") if isinstance(_b.get("price"), dict) else None
        _e = _tr["level"] if _tr else (_p if isinstance(_p, (int, float)) else (rows.get(t) or {}).get("entry"))
        _s = (_b.get("stop") or {}).get("price") if isinstance(_b.get("stop"), dict) else (BS.get(t) or {}).get("stop")
        return not bracket_view(_e, "", _s, "", [x.get("price") for x in (_b.get("tp_ladder") or [])], None)["targets"]
    n_no_ladder = sum(1 for c in adv if _no_ladder(c["ticker"]))
    o = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>Aegis Committee Cards</title>',
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">',
         f"<style>{CSS}</style></head><body><div class=\"wrap\">"]
    o.append(f'<div class="head"><div><div class="eyebrow">{E(T["session_label"])}</div><h1>Committee Cards</h1></div><div>'
             f'<span class="pill p-up">{len(by["ADVANCE"])} ADVANCE</span><span class="pill p-warn">{len(by["HOLD-FOR-CONDITIONS"])} HOLD &middot; WATCH</span>'
             f'<span class="pill p-n">{len(by["PASS"])} PASS</span>{_status_pills(cons)}<span class="pill p-down">{E(T["stance_pill"])}</span>'
             + (f'<span class="pill p-warn">{n_no_ladder} of {len(adv)} ADVANCE: reward does not justify the risk at this entry</span>' if n_no_ladder else "") + '</div></div>')
    o.append(_freshness_html(V, _MARKER, _REFRESHED))
    bl = T["bottom_line"]
    o.append(f'<section class="card bottom"><div class="eyebrow">Bottom line</div><h2>{E(bl["headline"])}</h2><p>{E(bl.get("paragraph", ""))}</p><div class="grid4">'
             + "".join(f'<div class="stat"><div class="v {TONE.get(s.get("tone"), "")}">{E(str(s["value"]))}</div><div class="l">{E(s["label"])}</div></div>' for s in bl["stats"])
             + "</div>" + mk_line + "</section>")
    m = T["market"]
    o.append(_weather_part1(V, CR, T.get("weather"), rows, D.get("daily_list"), D, {c["ticker"]: c["verdict"] for c in cons}))
    o.append('<div class="section-title"><h2>Cross-asset · what happened</h2></div><div class="grid2">')
    for key, lab in (("what_happened", "What happened"), ("weather", "What the weather systems say")):
        o.append(f'<section class="card read"><div class="eyebrow">{lab}</div>'
                 + "".join(f'<p><b>{E(x["lead"])}</b> {E(x["text"])}</p>' for x in m.get(key) or []) + "</section>")
    o.append("</div>")
    o.append('<section class="card"><div class="eyebrow">Where money is moving</div><div class="tbl"><table><thead><tr><th>Group</th><th>Read</th><th>What it means</th></tr></thead><tbody>'
             + "".join(f'<tr><td><b>{E(x["group"])}</b></td><td>{E(x["read"])}</td><td>{E(x["meaning"])}</td></tr>' for x in T["money"]) + "</tbody></table></div></section>")
    o.append('<div class="section-title"><h2>Part 2 · Your book and the committee</h2></div>' + _ma_banner(D))
    o.append('<section class="card"><div class="eyebrow">What it means for your book</div><div class="tbl"><table><thead><tr><th>Name</th><th>Position</th><th>Broker stop</th><th>Committee read</th><th>Why</th></tr></thead><tbody>')
    for b in T["book"]:
        t = b["ticker"]; h = held.get(t) or {}; s = BS.get(t) or {}
        pnl = h.get("unreal_usd")
        pos = (f'{int(h["qty"])} @ {h["entry"]:.2f} · last {h.get("live_px")} · <span class="{"pos" if (pnl or 0) >= 0 else "neg"}">{pnl:+,.0f}</span>'
               if h.get("qty") else "—")
        o.append(f'<tr><td><b>{E(t)}</b></td><td>{pos}</td><td>{E(str(s.get("stop") if s else "NONE"))}{(" " + E(str(s.get("order")))) if s else ""}</td>'
                 f'<td><span class="pill {TONE.get(b.get("tone"), "p-n")}">{E(b["read_pill"])}</span></td><td>{E(b["why"])}</td></tr>')
    o.append("</tbody></table></div>" + (f'<div class="flag">{E(T["book_flag"])}</div>' if T.get("book_flag") else "") + _valen_management_html(V, held) + "</section>")
    o.append('<section class="card"><div class="eyebrow">What changed since yesterday</div><ul>' + "".join(f"<li>{E(x)}</li>" for x in T["changed"]) + "</ul></section>")
    o.append('<div class="section-title"><h2>Committee recommendations</h2><span class="eyebrow">Ordered by readiness · act on the trigger · nothing at market</span></div><div class="names">')
    for c in adv:
        t = c["ticker"]; w = T["cards"][t]; card = CD["advance"].get(t) or {}; r = rows.get(t) or {}
        br = (BR.get(t) or {}).get("stop") or {}
        stop = (f'{br.get("price")} ({str(br.get("type", "")).replace("_", " ")}, {br.get("stop_pct")}%)' if br.get("price") else
                (f'{BS[t]["stop"]} broker stop' if t in BS else "—"))
        _b = BR.get(t) or {}
        _trig = next((x for x in (card.get("triggers") or []) if x.get("kind") == "close_above" and isinstance(x.get("level"), (int, float))), None)
        _ref = (_b.get("price") or {}).get("value") if isinstance(_b.get("price"), dict) else None
        _ref = _ref if isinstance(_ref, (int, float)) else (r.get("entry") if t not in held else held[t].get("live_px"))
        _entry, _esrc = ((_trig["level"], "buy line") if _trig else (_ref, "last close"))
        _stop = (_b.get("stop") or {}).get("price") if isinstance(_b.get("stop"), dict) else None
        if _stop is None and t in BS:
            _stop = BS[t].get("stop")
        bracket = bracket_view(_entry, _esrc, _stop, ((_b.get("stop") or {}).get("type") if _b.get("stop") else "broker stop"),
                               [x.get("price") for x in (_b.get("tp_ladder") or [])], _ONE_R)
        tp = None
        setups = [f'{x.get("setup")} {x.get("status")}' for x in _house_setups(r)]
        valen = E("; ".join(setups) or "no Valen house setup graded") + (f' · {E(_unr_words(r))}' if _unr_words(r) else "")
        void = _void_cell(SL.get("market_kill")) if MK else ""
        o.append(f'<article class="card name"><header><div><span class="tk">{t}</span><span class="pill p-up">ADVANCE</span>'
                 f'<span class="pill p-n">{E(lane.get(t, c["lane"]).title())}</span>{"<span class=\"pill p-warn\">HELD · ADD</span>" if t in held else ""}{_ma_pill(r)}</div>'
                 f'<span class="pill {("p-warn" if not bracket["targets"] else TONE.get(w["readiness_tone"], "p-n"))}">{E("Reward does not justify the risk at this entry" if not bracket["targets"] else w["readiness"])}</span></header>'
                 f'{_ma_line(r)}<p class="case"><b>{E(w["case"])}</b></p>{_reason_html(w)}{_committee_block(POS.get(t), POS_ON)}{_contest_html(c)}'
                 f'<dl class="kv2"><div><dt>Buy trigger</dt><dd>{E(_trig_text(card))}</dd></div><div><dt>Confirms</dt><dd>{E(card.get("confirms", "—"))}</dd></div>'
                 f'<div><dt>Dead if</dt><dd>{E(_dead_text(card))}</dd></div><div><dt>Last close</dt><dd>{E(str(r.get("entry") if t not in held else held[t].get("live_px")))}</dd></div>'
                 f'{void}{_bracket_html(bracket)}'
                 f'<div class="full"><dt>Valen</dt><dd>{valen}</dd></div>'
                 f'<div class="full"><dt>Sector</dt><dd>{E(w.get("sector_note") or str(r.get("gics_sector_name") or ""))}</dd></div></dl></article>')
    o.append("</div>")
    if T.get("common_risk"):
        o.append(f'<div class="flag">{E(T["common_risk"])}</div>')
    o.append('<section class="card"><div class="eyebrow">HOLD for conditions · nothing to do until the condition prints · AQE rank shown</div><div class="holds">')
    for c in sorted(by["HOLD-FOR-CONDITIONS"], key=lambda c: c["ticker"]):
        t = c["ticker"]; card = CD["hold"].get(t) or {}; r = rows.get(t) or {}
        o.append(f'<div class="hold"><div class="hh"><span class="tk2">{t}</span><span class="pill p-n">{E(lane.get(t, c["lane"]).title())}</span>{_ma_pill(r)}<span class="num">#{r.get("rank", "—")}</span></div>'
                 f'{_ma_line(r)}<p>{E(T["holds"][t])}</p>{_committee_block(POS.get(t), POS_ON)}{_contest_html(c)}<p class="cond">Condition: {E(_trig_text(card))} · dead: {E(_dead_text(card))}{(" · " + E(_unr_words(r))) if _unr_words(r) else ""}</p></div>')
    o.append("</div></section>")
    o.append('<section class="card"><div class="eyebrow">PASS · off the list</div><div class="tbl"><table><thead><tr><th>Ticker</th><th>Why not</th></tr></thead><tbody>'
             + "".join(f'<tr><td><b>{c["ticker"]}</b>{_ma_pill(rows.get(c["ticker"]))}</td><td>{_dropped_prefix(c)}{E(T["passes"][c["ticker"]])}</td></tr>' for c in sorted(by["PASS"], key=lambda c: c["ticker"]))
             + "</tbody></table></div></section>")
    # R26 (PM 2026-10-23): "our objective is to NOT miss strong momentum picks". Code-rendered from
    # phase4.json, never from words: the strongest Longlist/Elder names no voice nominated, and the R25
    # reserved reclaim seats. Flagged, not voted -- nothing here is a committee call.
    info = P4.get("informational") or []
    unr = P4.get("unr_seats") or []
    strong = P4.get("strong_seats") or []
    if info or unr or strong:
        def _f(v, fmt):
            return fmt.format(v) if isinstance(v, (int, float)) else "—"
        lists = lambda x: " + ".join(n for n, k in (("Longlist", "on_longlist"), ("Elder", "on_elder")) if x.get(k)) or "—"
        o.append('<section class="card"><div class="eyebrow">Strongest names no voice picked · seated by rule, then the next ones flagged · strongest vs SPY first</div>')
        if strong:
            o.append('<p class="cond">Seated for strength today (voted, momentum lane, no voice nominated them): '
                     + ", ".join(f'<b>{E(x["ticker"])}</b>' for x in strong) + ". Their verdicts are in the cards above.</p>")
        if unr:
            o.append('<p class="cond">Reserved reclaim seats today (voted, no voice nominated them): '
                     + ", ".join(f'<b>{E(u["ticker"])}</b> ({E(u.get("unr_note") or "")})' for u in unr) + "</p>")
        if info:
            o.append('<div class="tbl"><table><thead><tr><th>Ticker</th><th>vs SPY 20d</th><th>Momentum</th><th>Lists</th>'
                     '<th>U&amp;R</th><th>Stretch</th><th>Past breakout</th><th>AQE #</th></tr></thead><tbody>'
                     + "".join(f'<tr><td><b>{E(x["ticker"])}</b></td><td class="num">{_f(x.get("rs_spy_20d"), "{:+.1f}")}</td>'
                               f'<td class="num">{_f(x.get("sc_momentum"), "{:.0f}")}</td><td>{E(lists(x))}</td>'
                               f'<td>{E({"MET": "reclaim day", "SETUP": "forming"}.get(str(x.get("unr_status")), "—"))}</td><td class="num">{_f(x.get("extension_atr_20"), "{:.1f}×")}</td>'
                               f'<td class="num">{_f(x.get("pct_from_pivot"), "{:+.1f}%")}</td><td class="num">{E(str(x.get("aqe_rank") or "—"))}</td></tr>'
                               for x in info)
                     + '</tbody></table></div><p class="cond">Stretch = distance above the 20-day average in average daily ranges. '
                       'Add any of these by hand as a PM pick if you want the committee to vote it.</p>')
        o.append("</section>")
    o.append(_detect_lens_panel(D, cons))      # R31: independent top-10 list, before the plan
    o.append('<section class="card"><div class="eyebrow">The plan (SGT)</div><ol>' + "".join(f"<li>{E(x)}</li>" for x in T["plan"]) + "</ol></section>")
    if SC:
        lines = [l for l in SC.splitlines() if l.startswith("|")]
        o.append('<section class="card"><div class="eyebrow">Scorecard · graded calls (information, changes no verdict)</div><div class="tbl"><table>')
        for i, l in enumerate(lines[:16]):
            cells = [x.strip() for x in l.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tag = "th" if i in (0,) or (i > 0 and cells and cells[0] in ("Run", "Verdict", "Group")) else "td"
            o.append("<tr>" + "".join(f"<{tag}>{E(x)}</{tag}>" for x in cells) + "</tr>")
        o.append("</table></div>" + (f'<p class="flag">{E(T["scorecard_note"])}</p>' if T.get("scorecard_note") else "") + "</section>")
    o.append('<section class="card"><div class="eyebrow">Read with care</div><ul>' + "".join(f"<li>{E(x)}</li>" for x in T["caveats"]) + "</ul></section>")
    o.append(_top20_panel(D, cons))            # PM 2026-11-03: the very bottom of the Cards, built by code
    o.append('<div class="foot">DRAFT — PM approval required. Nothing is staged, nothing is armed.</div></div></body></html>')
    page = plainify_html("\n".join(o))
    if _PLAIN_FALLBACK:
        print("  [plain words] no table entry for: " + ", ".join(sorted(_PLAIN_FALLBACK)) + " (rendered as lower-case words; add them to PLAIN_WORDS)")
    open(a.out, "w").write(page)
    print(f"wrote {a.out}: {os.path.getsize(a.out)} bytes; {len(adv)} ADVANCE cards, {len(by['HOLD-FOR-CONDITIONS'])} holds, {len(by['PASS'])} passes")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("triggers"); s.add_argument("--conditions", default="conditions.json"); s.add_argument("--export", default="aqe_daily_export.json")
    s.add_argument("--broker-stops", default="broker_stops.json"); s.add_argument("--out", default="cards.json"); s.set_defaults(fn=cmd_triggers)
    s = sub.add_parser("render"); s.add_argument("--text", default="cards_text.json"); s.add_argument("--consensus", default="consensus.json")
    s.add_argument("--export", default="aqe_daily_export.json"); s.add_argument("--cards", default="cards.json"); s.add_argument("--brackets", default="brackets.json")
    s.add_argument("--broker-stops", default="broker_stops.json"); s.add_argument("--phase4", default="phase4.json")
    s.add_argument("--valen", default="aqe_valen_dashboard.json"); s.add_argument("--crown", default="aqe_crown_macro.json"); s.add_argument("--scorecard", default="scorecard.md")
    s.add_argument("--slate", default="slate.json", help="R40: the slate's market_kill line prints on the bottom line and on every ADVANCE card")
    s.add_argument("--position", default=None, help="R42: committee_position.json - each slated ticket shows 'Committee: Conviction n/5. Why ... What would change it ... Minority note ...'. Absent = no committee block (runs before 2026-11-04)")
    s.add_argument("--last-run", dest="last_run", default="aqe_last_run.json", help="the run marker: its 'Macro legs:' line dates the FRESHNESS header when the Valen file has no legs table")
    s.add_argument("--refreshed-valen", dest="refreshed_valen", default=None, help="main's refreshed aqe_valen_dashboard.json: if newer than the committee copy the page says so")
    s.add_argument("--allow-legacy-text", dest="allow_legacy_text", action="store_true", help="accept the old `why` wall instead of the plain 3-part `reason` (re-rendering an old run only)")
    s.add_argument("--out", required=True); s.set_defaults(fn=cmd_render)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
