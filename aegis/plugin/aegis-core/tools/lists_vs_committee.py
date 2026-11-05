#!/usr/bin/env python3
"""The three AQE lists against the committee: a diagnostic, built by code from one finished run dir. No model calls.

    build(run_dir) -> dict   every figure, tag and quote the page section prints, each with the stored field it came from.

Reads (read only): aqe_daily_export.json, consensus.json, cards_text.json, phase4.json, aqe_valen_dashboard.json.
Definitions reused from the real page's code (pma_cards.py), not invented here:
  * in the room      = the ticker has an entry in consensus.json (the 44 names the committee carried and voted or passed);
  * not in the room  = no consensus entry (no voice nominated it and no reserved seat took it);
  * AQE top 20       = daily_list sorted by the export `rank` (AQE pipeline rank), first 20 (_top20_panel);
  * Detect-lens list = lens_ranking.ranked in its stored order (strong-lens count desc, warnings asc, momentum desc) (_detect_lens_panel);
  * sector state     = AQE's SRM grade for the row's GICS sector (_sector_state);
  * plain words      = pma_cards.PLAIN_WORDS / plain_words / plain_prose, imported from the real page's module.
Usage as a script: python3 lists_vs_committee.py [run_dir]  -> prints a JSON summary and the runtime.
"""
import collections, importlib.util, json, re, sys, time
from pathlib import Path

PMA_CARDS = Path(__file__).resolve().parent / "pma_cards.py"

# ------------------------------------------------------------------ list sizes (the PM's ask)
N_ELDER, N_AQE, N_LENS = 15, 20, 15
N_SWING = 20      # PM 2026-11-05: the 4th brief list, momentum AT the pivot (export swing_pivot true), by AQE rank

# ------------------------------------------------------------------ tag thresholds
# Committee lines: each one is quoted from a filed objection or a pass reason in this run (see COMMITTEE_LINES for the cite).
CHASE_PIVOT_PCT = 5.0      # "fires as a late buy past pivot_high +5pct" (consensus.json SN objection); export glossary: 0-5% is the buy zone
CHASE_200D_PCT = 70.0      # "more than 70% above the 200-day; ... it never buys it" (consensus.json HNGE objection; cards_text passes BRZE)
VOLUME_LINE_X = 1.4        # "on volume at least 1.4x normal" (consensus.json: the would-clear line on most volume objections)
# AQE tag rules, NOT committee rules (chosen here, labelled so on the page):
STRETCH_MAX_RANGES = 4.0   # more than 4 daily ranges above the 20-day average = EXTENDED
COIL_NEAR_HIGH_PCT = 3.0   # COILING needs the close within 3% of the 20-bar high

COMMITTEE_LINES = {
    "pivot": ("SN", "late buy past pivot_high +5pct"),
    "200d": ("HNGE", "more than 70% above the 200-day"),
    "volume": ("BRK-B", "on volume at least 1.4x normal"),
}

TAGS = ["BREAKING OUT", "COILING", "PULLBACK", "EXTENDED", "OTHER"]
TAG_WORD = {"BREAKING OUT": "Breaking out", "COILING": "Coiling", "PULLBACK": "Pullback / support bounce", "EXTENDED": "Extended", "OTHER": "Other"}
OUTCOMES = ["ADVANCE", "HOLD", "PASS", "OUT"]
OUTCOME_WORD = {"ADVANCE": "Advance", "HOLD": "Hold for conditions", "PASS": "Passed in the room", "OUT": "Never in the room"}
VOICES = ("livermore", "minervini", "oneil", "o'neil", "raschke", "seow", "wyckoff", "elder-lens", "detect-lens", "chair")

# ------------------------------------------------------------------ objection themes: keyword rules on the filed objection text (case-insensitive)
THEMES = [
    ("volume", "No volume test, or volume too light", r"volume|day_vol|nobody bought"),
    ("dip_ticket", "Objects to a dip-and-reclaim ticket: wants the new-high break", r"reclaim:ma_20|reclaim of ma_20"),
    ("no_wait", "Objects to waiting for a pull-in: buy the strength now", r"pull-in step|pull-in precondition|no pull-in|skip (a|my) signal|skips my signal"),
    ("chasing", "Chasing: too far past the line", r"late buy|past pivot_high|chasing|climax|70% above|not on extension"),
    ("wants_pullback", "Objects to buying the break: wants a pullback or pull-in first", r"pullback into|into value|at value|value reclaim|first pullback|pullback in progress|adds on the test|away from the creek|in front of price|under the rising average|not above the prior high"),
    ("base", "No countable base or tight pause", r"no base|countable base|tight base|base uncounted|base unconfirmed|gives no base|out of a base|tightest contraction|tight, quiet pause"),
    ("trend", "Strength or trend not confirmed", r"trend template|not a leader|in-line|stage 2|only barely|lh/ll"),
    ("profit_taking", "Last bar reads as profit-taking or selling", r"green going away|profit-taking|single-bar drop|last-bar drop|distribution"),
    ("sector", "Sector or group blocked", r"\bsector\b|blocked|headwind"),
]
# sentences that still carry these after the plain-words pass are not used as the shown quote (they would print jargon)
QUOTE_JARGON = re.compile(r"\b(H1|W|D|EMA\d*|HH/HL|LH/LL|ACT_NOW|act now|Creek|cmf|sma_dist|cci|coil|Template|criterion|ticket|why_agreed|quoted|hold round|ratif)\b|\b[CR]\d+\b|\d+, \d+", re.I)
RULE_CODES = re.compile(r"\s*\((?:\s*(?:[CR]\d+(?:/[CR]\d+)?|by proxy|incl\.[^)]*)\s*,?\s*)+\)")
TRIGGER_SWAPS = [("reclaim:ma_20", "a reclaim of the 20-day average"), ("h1_close_above:bar_high", "an hourly close above yesterday's high"),
                 ("h1_close_above:pivot_high", "an hourly close above the last pivot high"), ("close_above:bar_high", "a daily close above yesterday's high")]


def _load_plain():
    spec = importlib.util.spec_from_file_location("pma_cards_plain", PMA_CARDS)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_PC = None


def plain(s):
    """The real page's plain-words pass (+ the four trigger words, + the v2 page's term swaps). Term swaps only, never a fact."""
    global _PC
    if _PC is None:
        _PC = _load_plain()
    for a, b in TRIGGER_SWAPS:
        s = s.replace(a, b)
    s = _PC.plain_prose(_PC.plain_words(s))
    for a, b in (("rs rank", "strength rank"), ("ATRs", "daily ranges"), ("Elder impulse", "momentum score"), ("RSI", "momentum")):
        s = s.replace(a, b)
    return s


def sentences(s):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", s.strip()) if x.strip()]


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ------------------------------------------------------------------ setup tag
def setup_tag(r):
    """Deterministic, first rule that applies wins. Returns (tag, [what fired, in plain words], also_reclaim_day)."""
    e, piv, ma200, hi20 = r.get("entry"), r.get("pct_from_pivot"), r.get("ma_200"), r.get("hi_20d")
    ext = r.get("extension_atr_20")
    a200 = (e / ma200 - 1) * 100 if num(e) and num(ma200) and ma200 else None
    under = (hi20 - e) / hi20 * 100 if num(e) and num(hi20) and hi20 else None
    reclaim = r.get("unr_status") in ("MET", "SETUP")
    grades = r.get("setups"); grades = grades.get("grades") if isinstance(grades, dict) else grades
    unr_grade = any(isinstance(g, dict) and "undercut" in str(g.get("setup", "")).lower() and g.get("status") in ("TRIGGERED", "READY", "WATCH")
                    for g in grades or [])
    reclaim = reclaim or unr_grade
    fired = []
    if num(piv) and piv > CHASE_PIVOT_PCT:
        fired.append(f"{piv:.1f}% past its pivot (committee line {CHASE_PIVOT_PCT:g}%)")
    if num(a200) and a200 > CHASE_200D_PCT:
        fired.append(f"{a200:.0f}% above its 200-day (committee line {CHASE_200D_PCT:g}%)")
    if num(ext) and ext > STRETCH_MAX_RANGES:
        fired.append(f"{ext:.1f} daily ranges over its 20-day (AQE tag rule {STRETCH_MAX_RANGES:g})")
    setup_tag.last_key = "pivot" if num(piv) and piv > CHASE_PIVOT_PCT else ("200d" if num(a200) and a200 > CHASE_200D_PCT else ("stretch" if fired else None))
    if fired:
        return "EXTENDED", fired, reclaim
    if num(piv) and 0 <= piv <= CHASE_PIVOT_PCT:
        return "BREAKING OUT", [f"{piv:.1f}% past its pivot, inside the {CHASE_PIVOT_PCT:g}% line"], reclaim
    tight = [w for w, ok in (("in a squeeze", r.get("was_squeezed")), ("narrowest range in 4 days", r.get("nr4_flag")),
                             ("narrowest range in 7 days", r.get("nr7_flag")), ("AQE coil reading strong", (r.get("lens") or {}).get("coil") == "strong")) if ok]
    below_pivot = num(piv) and piv < 0
    if below_pivot and num(under) and under <= COIL_NEAR_HIGH_PCT and tight:
        return "COILING", [f"{under:.1f}% under its 20-bar high", tight[0]], reclaim
    m20, slope, m50 = r.get("ma_20"), r.get("ma_20_slope_5d_pct"), r.get("ma_50")
    holds = []
    if reclaim:
        holds.append("reclaim-day flag (undercut and rally)")
    if num(e) and num(m20) and e > m20 and num(slope) and slope > 0:
        holds.append("holding a rising 20-day average")
    elif num(e) and num(m50) and e > m50:
        holds.append("holding its 50-day average")
    if below_pivot and holds:
        return "PULLBACK", [f"{abs(piv):.1f}% under its pivot"] + holds[:1], reclaim
    return "OTHER", ["none of the four rules applies"], reclaim


# ------------------------------------------------------------------ build
def build(run_dir):
    t0 = time.perf_counter()
    run = Path(run_dir)
    J = lambda n: json.load(open(run / n))
    D, CONS, T, P4, V = J("aqe_daily_export.json"), J("consensus.json"), J("cards_text.json"), J("phase4.json"), J("aqe_valen_dashboard.json")
    rows = {r["ticker"]: r for r in D["daily_list"]}
    srm = {s["sector"]: s for s in D["srm"]}
    room = {c["ticker"]: c for c in CONS}
    themes_v = {t["name"]: t for t in V.get("theme_leaders") or []}
    flagged = {re.match(r"([A-Z.\-]+)\(", x).group(1) for x in P4.get("dropped") or []} | {x["ticker"] for x in P4.get("informational") or []}
    seated_strength = [x["ticker"] for x in P4.get("strong_seats") or []]
    seated_reclaim = [x["ticker"] for x in P4.get("unr_seats") or []]

    def outcome(t):
        c = room.get(t)
        if not c:
            return "OUT"
        return {"ADVANCE": "ADVANCE", "HOLD-FOR-CONDITIONS": "HOLD", "PASS": "PASS"}[c["verdict"]]

    def sector_cell(r):
        x = srm.get(r.get("gics_sector_name")) or {}
        g, gate, q = x.get("grade"), x.get("entry_gate"), x.get("rrg_quadrant")
        bucket = "DEPLOY" if g == "DEPLOY" else ("TURNING_BLOCKED" if g == "TURNING" or gate == "BLOCKED" else "OTHER")
        return dict(sector=r.get("gics_sector_name"), grade=g, gate=gate, quadrant=q, roc20=x.get("roc20"), bucket=bucket)

    def theme_cell(r):
        bs = r.get("thematic_baskets") or []
        if not bs:
            return None
        b = bs[0]
        v = themes_v.get(b["basket"]) or {}
        return dict(basket=b["basket"], name=b["basket"].replace("_", " "), grade=b.get("grade"), quadrant=b.get("rrg_quadrant"),
                    week=v.get("ret_1w_pct"), month=v.get("ret_1m_pct"), more=len(bs) - 1)

    def reason(t, r, oc, tag_fired):
        """Voted names: the filed plain line (cards_text). Not in the room: 'No voice nominated it' + the first stored fact that applies."""
        if oc == "ADVANCE":
            src = ("cards_text.json", f"cards.{t}.case (first sentence)")
            txt = sentences(T["cards"][t]["case"])[0]
        elif oc == "HOLD":
            src = ("cards_text.json", f"holds.{t}")
            txt = T["holds"][t]
        elif oc == "PASS" and (room.get(t) or {}).get("status") == "DEAL_PINNED":
            dp = (room[t].get("deal_pinned") or {})
            src = ("consensus.json", f"{t}.deal_pinned (R44)")
            txt = "Deal-pinned: " + str(dp.get("ma_note") or r.get("ma_note") or "pending acquisition")
        elif oc == "PASS":
            src = ("cards_text.json", f"passes.{t}")
            txt = T["passes"].get(t) or "Passed in the room."
        else:
            sc = sector_cell(r)
            piv, e, ma200, ext, vol = r.get("pct_from_pivot"), r.get("entry"), r.get("ma_200"), r.get("extension_atr_20"), r.get("day_vol")
            a200 = (e / ma200 - 1) * 100 if num(e) and num(ma200) else None
            if num(piv) and piv > CHASE_PIVOT_PCT:
                fact, f, rk = f"{piv:.1f}% past its pivot, over the committee's {CHASE_PIVOT_PCT:g}% line.", "pct_from_pivot", "pivot"
            elif num(a200) and a200 > CHASE_200D_PCT:
                fact, f, rk = f"{a200:.0f}% above its 200-day, over the committee's {CHASE_200D_PCT:g}% line.", "entry, ma_200", "200d"
            elif sc["bucket"] == "TURNING_BLOCKED":
                fact, f, rk = f"its sector, {sc['sector']}, is gated {sc['gate']} by AQE.", "srm.entry_gate", "sector"
            elif num(vol) and vol < VOLUME_LINE_X:
                fact, f, rk = f"volume {vol:.2f}x its average, under the committee's {VOLUME_LINE_X:g}x line.", "day_vol", "volume"
            elif num(ext) and ext > STRETCH_MAX_RANGES:
                fact, f, rk = f"{ext:.1f} daily ranges over its 20-day average.", "extension_atr_20", "stretch"
            else:
                fact, f, rk = "no single stored AQE fact stands out.", "-", "none"
            src = ("aqe_daily_export.json", f"daily_list[{t}].{f}")
            txt = "No voice nominated it; " + fact
            return plain(txt), src, rk
        return plain(txt), src, None

    def row_out(i, r, extra):
        t = r["ticker"]
        oc = outcome(t)
        tag, fired, rec = setup_tag(r)
        e, hi20 = r.get("entry"), r.get("hi_20d")
        tag_key = getattr(setup_tag, "last_key", None) if tag == "EXTENDED" else None
        txt, src, rkey = reason(t, r, oc, fired)
        c = room.get(t) or {}
        return dict(n=i, ticker=t, elder=r.get("elder"), aqe_rank=r.get("rank"), lens_positive=r.get("lens_positive"),
                    lens_warnings=r.get("lens_warnings"), sector=sector_cell(r), theme=theme_cell(r), tag=tag, tag_fired=fired, reclaim_flag=rec,
                    stretch=r.get("extension_atr_20"), under_hi20=(hi20 - e) / hi20 * 100 if num(e) and num(hi20) and hi20 else None,
                    pct_from_pivot=r.get("pct_from_pivot"), above_200d=(e / r["ma_200"] - 1) * 100 if num(e) and num(r.get("ma_200")) else None,
                    volume=r.get("day_vol"), outcome=oc, status=c.get("status"), lane=c.get("lane"), n_objections=len(c.get("objections") or []),
                    flagged_by_doors=t in flagged, reason=txt, reason_src=src, reason_key=rkey,
                    tag_note_repeats_reason=(rkey is not None and rkey == tag_key), **extra)

    elder = sorted([r for r in D["daily_list"] if r.get("on_elder")], key=lambda r: (-(r.get("elder") or 0), r.get("rank") if isinstance(r.get("rank"), int) else 10**6))
    aqe = sorted([r for r in D["daily_list"] if isinstance(r.get("rank"), int)], key=lambda r: r["rank"])
    lens = [rows[x["ticker"]] for x in (D.get("lens_ranking") or {}).get("ranked") or [] if x["ticker"] in rows]
    lists = {
        "elder": dict(title=f"Elder top {N_ELDER}", sort="Elder score high to low, then AQE rank", n_on_list=len(elder),
                      rows=[row_out(i, r, {}) for i, r in enumerate(elder[:N_ELDER], 1)]),
        "aqe": dict(title=f"AQE top {N_AQE}", sort="AQE rank, 1 first", n_on_list=len(aqe),
                    rows=[row_out(r["rank"], r, {}) for r in aqe[:N_AQE]]),
        "lens": dict(title=f"Detect lens top {N_LENS}", sort="strong-lens count high to low, then fewer warnings, then momentum (AQE's stored order)",
                     n_on_list=len(lens), rows=[row_out(i, r, {}) for i, r in enumerate(lens[:N_LENS], 1)]),
    }
    if any("swing_pivot" in r for r in D["daily_list"]):            # absent on an export built before the column existed: no list, no claim
        swing = [r for r in aqe if r.get("swing_pivot") is True]
        lists["swing"] = dict(title=f"Swing pivot top {N_SWING}", sort="AQE rank, 1 first: weekly and daily higher highs and higher lows, daily close within one daily range of the latest daily swing high",
                              n_on_list=len(swing), rows=[row_out(i, r, {}) for i, r in enumerate(swing[:N_SWING], 1)])
    for k, L in lists.items():
        L["outcomes"] = {o: sum(1 for x in L["rows"] if x["outcome"] == o) for o in OUTCOMES}
        L["tags"] = {g: sum(1 for x in L["rows"] if x["tag"] == g) for g in TAGS}
        L["sector_buckets"] = {b: sum(1 for x in L["rows"] if x["sector"]["bucket"] == b) for b in ("DEPLOY", "TURNING_BLOCKED", "OTHER")}
        L["in_room"] = sum(1 for x in L["rows"] if x["outcome"] != "OUT")
        L["out_flagged"] = sum(1 for x in L["rows"] if x["outcome"] == "OUT" and x["flagged_by_doors"])
        L["reclaim_flag"] = sum(1 for x in L["rows"] if x["reclaim_flag"])

    union = {}
    for k in ("elder", "aqe", "lens"):
        for x in lists[k]["rows"]:
            union.setdefault(x["ticker"], x)
    union_out = {o: sum(1 for x in union.values() if x["outcome"] == o) for o in OUTCOMES}

    # ---- the committee's own picks, tagged by the same rules
    def group(verdict):
        out = []
        for c in CONS:
            if c["verdict"] != verdict or c["ticker"] not in rows:
                continue
            tag, fired, rec = setup_tag(rows[c["ticker"]])
            out.append(dict(ticker=c["ticker"], tag=tag, tag_fired=fired, reclaim_flag=rec, lane=c.get("lane"), status=c.get("status"),
                            trigger_word=(c.get("trigger") or {}).get("word"), trigger_plain=(c.get("trigger") or {}).get("plain"),
                            sector=sector_cell(rows[c["ticker"]])))
        return out
    adv, hold = group("ADVANCE"), group("HOLD-FOR-CONDITIONS")
    def mix(g):
        return {t: sum(1 for x in g if x["tag"] == t) for t in TAGS}
    trig = collections.Counter(x["trigger_word"] for x in adv)
    committee = dict(advance=adv, hold=hold, advance_tags=mix(adv), hold_tags=mix(hold),
                     advance_lanes=dict(collections.Counter(x["lane"] for x in adv)), hold_lanes=dict(collections.Counter(x["lane"] for x in hold)),
                     advance_triggers=dict(trig), advance_reclaim_flag=sum(1 for x in adv if x["reclaim_flag"]),
                     advance_sector=dict(collections.Counter(x["sector"]["bucket"] for x in adv)),
                     all_hourly_close_above=all(str(w).startswith("h1_close_above:") for w in trig))

    # ---- what the rules reward: objection themes across every slated name (AGREED / CONTESTED / DROPPED)
    slated = [c for c in CONS if c.get("status") in ("AGREED", "CONTESTED", "DROPPED")]
    objs = [(c["ticker"], c["verdict"], c["status"], o["objection"]) for c in slated for o in c.get("objections") or []]
    th_out, used = [], set()
    for key, label, rx in THEMES:
        hit = [(t, v, s, txt) for t, v, s, txt in objs if re.search(rx, txt, re.I)]
        cands = []
        for t, v, s, txt in hit:
            for sen in sentences(txt):
                if not re.search(rx, sen, re.I) or any(n in sen.lower() for n in VOICES) or "elder" in sen.lower():
                    continue
                p = plain(RULE_CODES.sub("", sen)).strip()
                if QUOTE_JARGON.search(p) or "_" in p or ":" in p or "--" in p or len(p) > 150:
                    continue
                cands.append((-len(p), p, t))           # the fullest clean whole sentence under 150 characters
        cands = sorted(c for c in cands if c[1] not in used)       # a sentence is shown under one theme only
        if cands:
            used.add(cands[0][1])
        th_out.append(dict(key=key, label=label, rule=rx, n_objections=len(hit), names=sorted({h[0] for h in hit}),
                           dropped_names=sorted({h[0] for h in hit if h[2] == "DROPPED"}),
                           quote=cands[0][1] if cands else None, quote_ticker=cands[0][2] if cands else None))
    th_out.sort(key=lambda x: -x["n_objections"])
    dropped = [c for c in CONS if c.get("status") == "DROPPED"]
    drop_dip = [c["ticker"] for c in dropped if str((c.get("trigger") or {}).get("word", "")).startswith("reclaim:")]
    objections = dict(n_slated=len(slated), n_objections=len(objs), n_names_with_objections=len({o[0] for o in objs}), themes=th_out,
                      n_dropped=len(dropped), dropped_dip_tickets=drop_dip,
                      n_reservations=sum(len(c.get("reservations") or []) for c in slated))

    cross = {g: {o: sum(1 for x in union.values() if x["tag"] == g and x["outcome"] == o) for o in OUTCOMES} for g in TAGS}
    out_rows = [x for x in union.values() if x["outcome"] == "OUT"]
    out = dict(run_dir=str(run), session_close=D.get("date"), lists=lists, union=dict(n=len(union), outcomes=union_out, tag_by_outcome=cross,
               out_flagged=sum(1 for x in out_rows if x["flagged_by_doors"]), out_n=len(out_rows),
               tags=dict(collections.Counter(x["tag"] for x in union.values())),
               lane_rule=(P4.get("lanes_rule") or {})), committee=committee,
               objections=objections, room=dict(n=len(CONS), strength_seats=seated_strength, reclaim_seats=seated_reclaim),
               rules=dict(CHASE_PIVOT_PCT=CHASE_PIVOT_PCT, CHASE_200D_PCT=CHASE_200D_PCT, VOLUME_LINE_X=VOLUME_LINE_X,
                          STRETCH_MAX_RANGES=STRETCH_MAX_RANGES, COIL_NEAR_HIGH_PCT=COIL_NEAR_HIGH_PCT, COMMITTEE_LINES=COMMITTEE_LINES,
                          THEMES=[(k, l, rx) for k, l, rx in THEMES]))
    out["runtime_s"] = round(time.perf_counter() - t0, 3)
    return out


if __name__ == "__main__":
    t = time.perf_counter()
    F = build(sys.argv[1] if len(sys.argv) > 1 else ".")
    wall = time.perf_counter() - t
    print(json.dumps({k: F["lists"][k]["outcomes"] for k in F["lists"]}), json.dumps(F["union"]))
    print(json.dumps({k: F["lists"][k]["tags"] for k in F["lists"]}))
    print(json.dumps({k: F["lists"][k]["sector_buckets"] for k in F["lists"]}))
    print(json.dumps({k: v for k, v in F["committee"].items() if k not in ("advance", "hold")}))
    for x in F["committee"]["advance"] + F["committee"]["hold"]:
        print(" ", x["ticker"], x["tag"], x["tag_fired"], x["lane"], x["trigger_word"], x["reclaim_flag"])
    for x in F["objections"]["themes"]:
        print(f"  {x['n_objections']:3} {x['label']} | {x['names']} | {x['quote']}")
    print({k: v for k, v in F["objections"].items() if k != "themes"})
    print(f"build() {F['runtime_s']}s, wall incl. import {wall:.3f}s")
