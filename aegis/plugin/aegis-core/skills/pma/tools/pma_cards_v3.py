#!/usr/bin/env python3
"""pma_cards_v3: the daily Cards page in the "no slop" form (PM 2026-11-04: "great upgrade"). Every section of the real page plus section 5b,
the three AQE lists against the committee.

Reads one finished run dir (the same files `pma_cards.py render` reads) plus the refreshed weather files (valen_dashboard.json,
crown_macro.json) read-only; invents nothing. Every sentence that states a fact is built from those files: the page for a different
day prints that day's facts or says the input is missing; a test renders a mutated run and asserts that no 4 Nov text survives.

Usage: pma_cards_v3.py --run-dir RUN [--out OUT.html] [--refresh-dir DIR]"""
import argparse, collections, html, json, math, os, re, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ap = argparse.ArgumentParser(description="Render the daily Cards (v3 form) from a finished run dir")
_ap.add_argument("--run-dir", default=".")
_ap.add_argument("--out", default=None)
_ap.add_argument("--refresh-dir", default=None, help="folder holding the refreshed valen_dashboard.json / crown_macro.json (default: <repo>/aegis/output)")
_A, _unknown = _ap.parse_known_args()
RUN = Path(_A.run_dir)
_RUN_DATE = None
OUT = Path(_A.out) if _A.out else RUN / "pma_cards_v3.html"
_REPO = Path(__file__).resolve().parents[5]
REF = Path(_A.refresh_dir) if _A.refresh_dir else _REPO / "aegis" / "output"          # refreshed weather, read only
sys.path.insert(0, str(Path(__file__).resolve().parent))
SGT, ET = ZoneInfo("Asia/Singapore"), ZoneInfo("America/New_York")
J = lambda n: json.load(open(RUN / n))
E = html.escape
import pma_cards as _PC
import card_extras as CX
import card_template as CT          # PM 2026-11-05: ONE fixed ten-field template for every card
ONE_R = int(_PC._one_r_usd() or 620)         # fund file one_r_usd (PM 2026-10-27), same figure as the real page

T = J("cards_text.json"); CONS = J("consensus.json"); POS = J("committee_position.json")["tickets"]
LV = {r["ticker"]: r for r in J("pma_levels.json")["rows"]}
CD = J("cards.json"); V = J("aqe_valen_dashboard.json"); CR = J("aqe_crown_macro.json"); MARK = J("aqe_last_run.json")
RUN_META = json.load(open(RUN / "run_manifest.json")) if (RUN / "run_manifest.json").exists() else {}
DEC = J("decision.json"); D = J("aqe_daily_export.json"); P4 = J("phase4.json")
SCMD = (RUN / "scorecard.md").read_text()
RV = json.load(open(REF / "valen_dashboard.json")); RC = json.load(open(REF / "crown_macro.json"))
ROWS = {r["ticker"]: r for r in D["daily_list"]}
MTF = (json.load(open(RUN / "mtf.json")).get("names") or {}) if (RUN / "mtf.json").exists() else {}
for h in D.get("held_positions") or []:
    ROWS.setdefault(h["ticker"], h)
if (RUN / "mtf_supplement.json").exists():          # PM 2026-11-05: the supplemental pass's own trend-frame grid (same schema as mtf.json); never overrides a room name
    for _t, _m in ((json.load(open(RUN / "mtf_supplement.json")).get("names")) or {}).items():
        MTF.setdefault(_t, _m)
HELD = {h["ticker"]: h for h in D["held_positions"]}
_opt = lambda n, dflt: json.load(open(RUN / n)) if (RUN / n).exists() else dflt          # run files the fixture / an older run may lack: the card says "not available", never invents
BRK = (_opt("brackets.json", {}) or {}).get("brackets") or {}
RMK = (_opt("repeat_marks.json", {}) or {}).get("marks") or {}
_RL = _opt("report_lines.json", None) or {}   # one plain line per report (A, B, C) from report_compare.py (PM 2026-11-05); absent until the first run of B/C
_CL = _opt("cards_lines.json", None)           # WRITER-authored lines 2 and 3 (PM 2026-11-05): {TICKER: {"why": one sentence, "contested": one sentence}}
CL = ((_CL or {}).get("cards") if isinstance(_CL, dict) and isinstance((_CL or {}).get("cards"), dict) else _CL) or {}
CARD_FIELDS = {}                                # ticker -> the ten fields as printed; written to card_fields.json for the alert side
LINE_FALLBACK = []                              # (ticker, field, problems): a writer line that broke the gate; the extraction line was printed instead
ON_LISTS = CT.brief_lists(D["daily_list"], (D.get("lens_ranking") or {}).get("ranked"))
SLATE_T = {x["ticker"]: x for x in (_opt("slate.json", {}) or {}).get("tickets") or []}
SRM = {s["sector"]: s for s in D["srm"]}
CONS_BY = {c["ticker"]: c for c in CONS}
BYV = collections.defaultdict(list)
for c in CONS:
    BYV[c["verdict"]].append(c)
RD = CR["readings"]; KL = CR["key_levels"]
kl = lambda what: next(k for k in KL if k["what"] == what)

def f2(x): return f"{x:,.2f}"
def sg(x, d=2): return f"{x:+.{d}f}".replace("-", "&minus;")
def mins(s): return str(s).replace("-", "&minus;") if str(s).startswith("-") else str(s)
from card_words import LEVEL_PLAIN, WORD_PLAIN, GENERIC_COND, cond_plain, no_raw_words   # one table; see card_words.py

def plain(s):
    """Term swaps only (never a fact): the same jargon-to-words idea the real page's plainify step uses."""
    for a, b in (("rs rank", "strength rank"), ("ATRs", "daily ranges"), ("Elder impulse", "momentum score"), ("RSI", "momentum")):
        s = s.replace(a, b)
    return s

# ------------------------------------------------------------------ small SVG kit (percent x, px y: text never scales)
CLAY, GRAY = "var(--clay)", "var(--bar)"

def xpct(v, lo, hi): return max(1.5, min(98.5, 100 * (v - lo) / (hi - lo)))
def anchor(x): return "start" if x < 14 else ("end" if x > 86 else "middle")

def strip(lo, hi, marks, bands=(), label=""):
    """A number line. marks: (value, text, colour, row) with row -2/-1 above the line, 1/2 below."""
    rows_used = {m[3] for m in marks}
    top = 18 * sum(1 for r in (-2, -1) if r in rows_used) + 6
    axis = top + 8
    hgt = axis + 8 + 18 * sum(1 for r in (1, 2) if r in rows_used) + 4
    ypos = {-2: top - 24, -1: top - 6 if -2 in rows_used else top - 6, 1: axis + 22, 2: axis + 40}
    if -2 in rows_used:
        ypos[-2], ypos[-1] = 14, 32
    else:
        ypos[-1] = 14
    s = [f'<svg class="viz" width="100%" height="{hgt}" role="img" aria-label="{E(label)}">']
    for a, b, fill in bands:
        x1, x2 = xpct(a, lo, hi), xpct(b, lo, hi)
        s.append(f'<rect x="{x1:.1f}%" y="{axis-6}" width="{x2-x1:.1f}%" height="12" fill="{fill}" rx="3"/>')
    s.append(f'<line x1="0%" x2="100%" y1="{axis}" y2="{axis}" stroke="var(--line)" stroke-width="2"/>')
    for v, txt, col, row in marks:
        x = xpct(v, lo, hi)
        y1, y2 = (ypos[row] + 4, axis) if row < 0 else (axis, ypos[row] - 12)
        s.append(f'<line x1="{x:.1f}%" x2="{x:.1f}%" y1="{y1}" y2="{y2}" stroke="{col}" stroke-width="2"/>')
        s.append(f'<circle cx="{x:.1f}%" cy="{axis}" r="5" fill="{col}"/>')
        s.append(f'<text x="{x:.1f}%" y="{ypos[row]}" text-anchor="{anchor(x)}" class="t13" fill="var(--text)">{txt}</text>')
    s.append("</svg>")
    return "".join(s)

def hbars(rows, lo, hi, label="", guides=(), rowh=40):
    """Horizontal bars, label line above each bar so nothing collides at 400px.
    rows: (left text html, right text html, value, colour)."""
    lo, hi = min(lo, 0), max(hi, 0)
    z = 100 * (0 - lo) / (hi - lo)
    s = [f'<div class="bars" role="img" aria-label="{E(label)}">']
    for lt, rt, v, col in rows:
        vx = 100 * (v - lo) / (hi - lo)
        x1, w = (min(z, vx), abs(vx - z))
        g = "".join(f'<line x1="{100*(gv-lo)/(hi-lo):.1f}%" x2="{100*(gv-lo)/(hi-lo):.1f}%" y1="0" y2="14" stroke="var(--text-3)" stroke-dasharray="2 2"/>' for gv, _ in guides)
        zl = f'<line x1="{z:.1f}%" x2="{z:.1f}%" y1="0" y2="14" stroke="var(--text-3)"/>' if lo < 0 else ""
        s.append(f'<div class="br"><div class="bl"><span>{lt}</span><b>{rt}</b></div>'
                 f'<svg class="viz" width="100%" height="14" aria-hidden="true"><rect x="0" y="2" width="100%" height="10" rx="3" fill="var(--soft)"/>'
                 f'<rect x="{x1:.2f}%" y="2" width="{max(w, 0.6):.2f}%" height="10" rx="3" fill="{col}"/>{g}{zl}</svg></div>')
    s.append("</div>")
    return "".join(s)

def pill(txt, tone=""): return f'<span class="pill {tone}">{txt}</span>'
def ma_pill(r):
    """PM 2026-11-04: a pending merger / acquisition / buyout is flagged wherever the name is picked. UNKNOWN (scan failed) is never shown as clean."""
    st = str((r or {}).get("ma_status") or "")
    txt = {"PENDING_TARGET": "M&amp;A PENDING &middot; being acquired", "PENDING_ACQUIRER": "M&amp;A PENDING &middot; the buyer", "PENDING_UNCLEAR": "M&amp;A PENDING"}.get(st)
    if txt:
        return f'<span class="pill ma" title="{E(str(r.get("ma_note") or ""))}">{txt}</span>'
    return '<span class="pill out" title="The M&amp;A scan did not run for this name">M&amp;A not checked</span>' if st == "UNKNOWN" else ""
def ma_line(r):
    st = str((r or {}).get("ma_status") or "")
    if not st.startswith("PENDING"):
        return ""
    why = {"PENDING_TARGET": " A stock with a pending takeover trades on the deal spread, not on momentum, so flow, energy and structure mean little here.",
           "PENDING_ACQUIRER": " This company is the buyer; the deal can move its stock, but it is not pinned to a price.",
           "PENDING_UNCLEAR": " The role in the deal could not be read from the news; check the headline."}.get(st, "")
    return f'<p class="flag"><b>M&amp;A PENDING.</b> {E(str(r.get("ma_note") or ""))}{E(why)}</p>'
def mom_pill(t):
    """PM 2026-11-05: weekly+daily uptrend structure from mtf.json with the daily close's distance from the latest daily swing high in ATR (bands in card_extras). Information only."""
    f, why = CX.momentum(MTF.get(t), ROWS.get(t))
    return f'<span class="pill good" title="{E(why)}">{E(CX.trend_pill_text(MTF.get(t), ROWS.get(t)))}</span>' if f else ""
def risk_atr(r):
    """', 1.3 ATR' appended to the stop's risk, same card line (PM 2026-11-05); '' when atr_14d is not in the export."""
    a = (ROWS.get(r["t"]) or {}).get("atr_14d")
    return f", {r['risk'] / a:.1f} ATR" if isinstance(a, (int, float)) and a > 0 else ""
def extras(t):
    """The weekly / daily / hourly strip and the one-line U&R tag, both from the files; nothing is claimed when mtf.json has no row."""
    return CX.strip_html(MTF.get(t), E) + f'<p class="unr">{E(CX.unr_tag(ROWS.get(t)))}</p>'
def ext_line(r):
    """The labelled extension bracket, one plain line ('targets if the stock runs into open air'); empty on an older export."""
    eb = (r or {}).get("extension_bracket")
    if not isinstance(eb, dict):
        return ""
    if not eb.get("available"):
        return f'<p><b>If it runs into open air:</b> not available ({E(str(eb.get("reason") or "no reason given"))}).</p>'
    t = {x.get("tp"): x for x in eb.get("targets") or []}
    return (f'<p><b>If it runs into open air:</b> targets {f2(t["TP1"]["price"])} (1.272 of its last leg) and {f2(t["TP2"]["price"])} (1.618), stop {f2(eb["stop"])}, '
            f'{t["TP2"]["r"]:.1f}R to the second. A second bracket that ignores nearby resistance, so a far target makes the reward easy to show; it '
            f'{"clears" if eb.get("passed") else "does not clear"} the three bracket checks.</p>')
def card(h3, visual, read="", more="", cls=""):
    return (f'<div class="card {cls}"><h3>{h3}</h3>{visual}' + (f'<p class="read">{read}</p>' if read else "")
            + (f"<details><summary>{more[0]}</summary>{more[1]}</details>" if more else "") + "</div>")
def table(head, rows, cls=""):
    return (f'<div class="tbl"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")
def tile(num, lab, tag=""):
    return f'<div class="tile"><div class="num">{num}</div><div>{lab}</div>' + (f'<span class="tag">{tag}</span>' if tag else "") + "</div>"
def section(n, h2, body, sid):
    return f'<section id="{sid}"><div class="kicker">{n}</div><h2>{h2}</h2>{body}</section>'

# ------------------------------------------------------------------ the reward ladder (v1 logic, unchanged)
ADV = [c["ticker"] for c in BYV["ADVANCE"]]
trade = {}
for t in ADV:
    lv = LV[t]["levels"]
    _tr = next((x for x in LV[t]["triggers"] if x["kind"] == "close_above"), None)
    trig = _tr["level"] if _tr else (ROWS[t].get("entry") or lv.get("entry"))              # no hourly-close buy line: the last close stands in, said on the card
    entry, stop = trig, lv["stop"]; risk = entry - stop
    rr = [((tp - entry) / risk, tp) for tp in lv["tp"]]
    ladder = [(round(r, 1), tp) for r, tp in rr if r >= 1.0]
    near = [(round(r, 1), tp) for r, tp in rr if r < 1.0]
    ctr = next((x for x in CD["advance"][t]["triggers"] if x["kind"] == "close_above"), {})
    dead = next((x["level"] for x in CD["advance"][t]["triggers"] if x["kind"] == "close_below"), None)
    trade[t] = dict(t=t, entry=entry, stop=stop, risk=risk, risk_pct=100 * risk / entry, shares=int(ONE_R // risk),
                    ladder=ladder, near=near, vol=ctr.get("volume_min_x"), dead=dead, last=ROWS[t]["entry"],
                    status=CONS_BY[t]["status"], conv=POS[t]["committee_conviction"], w=T["cards"][t],
                    sector=ROWS[t].get("gics_sector_name"))
usable = sorted([r for r in trade.values() if len(r["ladder"]) >= 2], key=lambda r: -r["ladder"][1][0])
thin = [trade[t] for t in ADV if len(trade[t]["ladder"]) < 2]
n_adv, n_slated = len(ADV), len(DEC["survivors"])
n_agreed = sum(1 for t in ADV if trade[t]["status"] == "AGREED")

# ------------------------------------------------------------------ shared facts
spy = next(x for x in V["trend"] if x["symbol"] == "SPY"); qqq = next(x for x in V["trend"] if x["symbol"] == "QQQ")
ext = {e["label"]: e["value"] for e in V["extension"]}
hist = {h["label"]: h for h in V["history"]}
dd = RD["positioning"]["option_dealers"]["detail"]; dS, dQ = dd["SPY"], dd["QQQ"]
vol = RD["volatility"]; hb = RD["breadth"]; tf = RD["positioning"]["trend_funds"]
_vm = re.search(r"(higher|lower) than (\d+)% of days", " ".join(CR["read_me_first"]["why"]))
vix_rel, vix_pct = (_vm.group(1), _vm.group(2)) if _vm else (None, None)             # Crown's own sentence; absent = the page says so
VIX_PHRASE = (f"is {vix_rel} than {vix_pct}% of the past two years" if _vm else "has no two-year ranking in Crown's reading")
pw_dist = kl("SPY put wall")["distance_pct"]
stale = re.search(r"(\d+)/(\d+) tickers \((\d+)%\) carry the (\S+) bar, need (\d+)%", (V.get("breadth") or [{}])[0].get("reason") or "")
st_have, st_tot, st_pct, st_need = ((int(stale.group(1)), int(stale.group(2)), int(stale.group(3)), int(stale.group(5))) if stale else (None, None, None, None))
lead_secs = [s["sector"] for s in D["srm"] if s["entry_gate"] == "PASS"]
blocked_lag = [s["sector"] for s in D["srm"] if s["entry_gate"] == "BLOCKED" and s["rrg_quadrant"] == "LAGGING"]
SHORT = {"Consumer Staples": "Staples", "Consumer Discretionary": "Discretionary", "Communication Services": "Communication Services"}
sc_lines = [l for l in SCMD.splitlines() if l.startswith("| 20")]
last_run_row = [c.strip() for c in sc_lines[-1].strip("|").split("|")]          # yesterday's one-session row
y_spy, y_list, y_beat = last_run_row[3], last_run_row[4], last_run_row[5]
mk = DEC["market_kill"]
mk_plain = re.sub(r"\s*\(\s*C\d+(?:\s*,\s*(?:C\d+|gate [A-Z_ ]+))*\s*\)", "", re.sub(r"^\s*void\s+(every\s+new\s+trigger\s+)?if\s+", "", mk["plain"], flags=re.I)).strip().rstrip(".")
mk_plain = no_raw_words(mk_plain)               # the 9 Nov line printed "SPY close_below ma_50" raw
now_sgt = datetime.now(SGT)
WORD = {i: w for i, w in enumerate("No One Two Three Four Five Six Seven Eight Nine Ten".split())}
nword = lambda n: WORD.get(n, str(n))
RUN_DATE = datetime.strptime(str(D["date"])[:10], "%Y-%m-%d")
OPEN_SGT = datetime(RUN_DATE.year, RUN_DATE.month, RUN_DATE.day, 9, 30, tzinfo=ET).astimezone(SGT)      # 09:30 ET on the run's calendar day
FIRST_HOUR_SGT = OPEN_SGT.replace(hour=OPEN_SGT.hour + 1) if OPEN_SGT.hour < 23 else OPEN_SGT
DEALER_REG = RD["positioning"]["option_dealers"].get("regime")           # NEGATIVE amplifies moves, POSITIVE damps them
RERUN = (RUN_META.get("rerun") or {}).get("suffix")                      # r2 ... ; absent on a live run

# ------------------------------------------------------------------ TOP BLOCK
_jn2 = lambda L: ", ".join(L[:-1]) + (" and " if len(L) > 1 else "") + L[-1] if L else ""
TREND = str(V.get("regime") or "").upper()
PLAINLEG = {"breadth_whole_market": "breadth", "positioning_cot": "futures positioning", "heartbeat_rsp_spy": "market breadth line",
            "vix_level": "the VIX", "dispersion_vixeq": "single-stock volatility", "implied_correlation_cor1m": "implied correlation"}
_both = [bool(x.get("daily_buy_signal")) for x in (spy, qqq)]
reason_trend = ("<p><b>Trend is down.</b> SPY and QQQ are under their short-term lines.</p>" if TREND == "DOWNTREND" and not any(_both) else
                "<p><b>Trend is up.</b> SPY and QQQ are above their short-term lines.</p>" if TREND == "UPTREND" and all(_both) else
                f"<p><b>Trend is {E(TREND.lower() or 'unclear')}.</b> SPY and QQQ {'both have' if all(_both) else 'both lack' if not any(_both) else 'disagree on'} a daily buy signal.</p>")
_fd = dS["flip_distance_pct"]                       # positive = the flip sits above SPY
reason_dealers = (f"<p><b>Dealers amplify moves.</b> SPY is {abs(_fd)}% {'under' if _fd > 0 else 'over'} the {f2(dS['gamma_flip'])} flip.</p>" if DEALER_REG == "NEGATIVE" else
                  f"<p><b>Dealers damp moves.</b> SPY is {abs(_fd)}% {'under' if _fd > 0 else 'over'} the {f2(dS['gamma_flip'])} flip.</p>" if DEALER_REG == "POSITIVE" else
                  "<p><b>Dealer positioning is not read.</b> No options data was served.</p>")
reason_money = (f"<p><b>Money sits in {'defence' if set(lead_secs) <= {'Consumer Staples', 'Utilities', 'Healthcare', 'Real Estate'} else 'these sectors'}.</b> "
                f"{', '.join(SHORT.get(x, x) for x in lead_secs)} lead.</p>" if lead_secs else "<p><b>No sector passes the entry gate.</b></p>")
LEGS = RV["data_freshness"]["legs_table"]
off = [r for r in LEGS if r["reason"] != "CURRENT"]
cot_leg = next((r for r in LEGS if r["leg"] == "positioning_cot"), None)
nxt = ((cot_leg or {}).get("detail", "").split("next release ")[-1] if cot_leg else "")
nxt = nxt if re.fullmatch(r"\d{4}-\d{2}-\d{2}", nxt or "") else ""
d = lambda s: datetime.strptime(s, "%Y-%m-%d").strftime("%-d %b")
ref_at = RV["exported_at"].replace(" SGT", "")
TREND = str(V.get("regime") or "").upper()
cautions = []
if TREND == "DOWNTREND": cautions.append("the index is in a downtrend")
elif TREND == "CHOP": cautions.append("the index is choppy")
if DEALER_REG == "NEGATIVE": cautions.append("dealers amplify moves")
h1 = (("No names are ready on a trigger" if n_adv == 0 else f"{nword(n_adv)} {'name is' if n_adv == 1 else 'names are'} ready on a trigger")
      + (f", but {' and '.join(cautions)}." if cautions else "."))
exit_cases = [x["ticker"] for x in T.get("book") or [] if str(x.get("tone")) == "down"]
ask = (f"Before the {OPEN_SGT:%H:%M} SGT open: " + (f"decide on {' and '.join(exit_cases)} and " if exit_cases else "")
       + f"which of the {n_adv} triggers to watch." if n_adv else f"Before the {OPEN_SGT:%H:%M} SGT open: " + (f"decide on {' and '.join(exit_cases)}." if exit_cases else "nothing is armed today."))
close_d = RV["data_freshness"].get("expected_session") or str(D["date"])[:10]
_stale_b = [x for x in V.get("breadth") or [] if x.get("status") in ("STALE", "UNAVAILABLE")]
run_note = ", breadth stale" if _stale_b else ""
off_note = ("only " + " and ".join(PLAINLEG.get(x["leg"], x["leg"]) + f" old ({d(x['as_of'])})" for x in off[:3])) if off else "every input current"
_ms = D.get("ma_scan")
ma_banner = ('<p class="flag"><b>M&amp;A flags are not in this export.</b> The export carries no M&amp;A scan result, so no name can be called free of a pending deal.</p>' if not isinstance(_ms, dict) else
             f'<p class="flag"><b>M&amp;A scan {E(str(_ms.get("scan_status")))}.</b> {E(str(_ms.get("n_failed")))} of {E(str(_ms.get("n_scanned")))} names could not be checked for a pending merger or buyout'
             f'{(": " + E(str(_ms.get("reason")))) if _ms.get("reason") else ""}. Names marked &ldquo;M&amp;A not checked&rdquo; are unchecked, not clean.</p>' if _ms.get("scan_status") != "ok" else "")
_msum = CX.momentum_summary(MTF, [c["ticker"] for c in CONS if c.get("status") not in ("DEAL_PINNED", "NOT_SLATED")], ROWS)
mom_banner = f'<p class="flag"><b>Uptrend structure.</b> {E(_msum["text"])}</p>' if _msum else ""
top = f'''<div class="meta">Aegis committee cards &middot; {RUN_DATE:%a} {RUN_DATE.day} {RUN_DATE:%b %Y} &middot; to the PM{(' &middot; rerun ' + RERUN + ', not live') if RERUN else ''} &middot; {n_adv} triggers</div>
<h1>{h1}</h1>
<p class="ask">{ask}</p>
<p class="fresh"><b>Data:</b> {d(close_d)} close &middot; run {MARK["exported_at"][11:16]} SGT{run_note} &middot; refreshed {ref_at[11:16]} SGT, {off_note} &middot; now {now_sgt:%H:%M} SGT</p>
<div class="tiles">
{tile(n_adv, "ready on a trigger", f"{n_agreed} agreed, {n_adv-n_agreed} contested")}
{tile(mins(f"{D['spy_roc_20d']:.2f}%"), "SPY, 20 days", f"closed {spy['last_price']}")}
{tile(f"{vol['vix']}", "VIX", (f"{'above' if vix_rel == 'higher' else 'below'} {vix_pct}% of 2 years" if _vm else ""))}
{tile(f"{len(usable)} of {n_adv}", "pay 1R+ at two targets", ("not " + " or ".join(r["t"] for r in thin)) if thin else "all of them")}
</div>
<div class="reasons">
{reason_trend}
{reason_dealers}
{reason_money}
</div>
{ma_banner}
{mom_banner}'''
top = f'<header id="top">{top}</header>'

# refreshed-after-committee detail (post-committee facts, labelled)
rb = RV["breadth"]
refresh_more = ("What the 13:21 SGT refresh shows, after the committee", "<ul class='plainlist'>"
    + f"<li>Valen&rsquo;s stance now reads <b>{RV['stance']['stance'].replace('_', ' ')}</b> (the committee saw it withheld).</li>"
    + f"<li>Whole-market breadth is current: {rb['pct_above_40d']['value']}% of {rb['pct_above_40d']['n']:,} stocks are above their 40-day line; the 5-day count of big up vs down days is {rb['five_day_count']['value']}.</li>"
    + f"<li>SPY&rsquo;s dealer flip moved to {f2(RV['gex']['flip'])} ({RV['gex']['flip_distance_pct']}% above SPY).</li>"
    + "".join(f"<li>{E(plain(x)).replace('NORMAL_RISING', 'normal and rising').replace('NORMAL', 'normal')}</li>" for x in RC["what_changed"]["changes"])
    + "</ul>")

# ------------------------------------------------------------------ 1 MACRO AND WEATHER
yn = lambda b: pill("Yes", "good") if b else pill("No", "bad")
_stance = V.get("stance") or {}
_withheld = _stance.get("status") in ("DEGRADED", "WITHHELD", "UNAVAILABLE") or _stance.get("word") in (None, "—", "")
_under = [x["symbol"] for x in (spy, qqq) if not x["above_rising_5d"]]
_lines = ("SPY and QQQ are under their short-term lines" if len(_under) == 2 else "SPY and QQQ are above their short-term lines" if not _under
          else f"{_under[0]} is under its short-term line and {'QQQ' if _under[0] == 'SPY' else 'SPY'} is above its own")
c_valen = card((("Valen&rsquo;s one-word stance is withheld" if _withheld else f"Valen&rsquo;s stance reads {E(str(_stance.get('word')).replace('_', ' ').title())}") + f"; {_lines}."),
    table(["Index", "Price", "Daily buy signal", "Weekly buy signal", "From 50-day avg"],
          [[f"<b>{x['symbol']}</b>", f2(x["last_price"]), yn(x["daily_buy_signal"]), yn(x["weekly_buy_signal"]),
            mins(f'{ext[x["symbol"] + " ATRs above 50-day"]:.2f}') + " daily ranges"] for x in (spy, qqq)]),
    ((f"The stance needs fresh whole-market breadth: {st_have:,} of {st_tot:,} tickers carried the {d(stale.group(4))} bar, and {st_need}% are needed. " if stale else
      (f"The stance was not given because: {E(str(_stance.get('reason') or 'no reason served'))}. " if _withheld else ""))
     + "Doctrine quoted, not an Aegis rule: if the market check is not green, do not push."),
    ("More on the trend read", "<p>Above a rising 5-day average: " + ", ".join(f"{x['symbol']} {'yes' if x['above_rising_5d'] else 'no'}" for x in (spy, qqq)) + ". Distance from the 50-day is in average daily ranges.</p>"))

def strip_dealer(dx, sym):
    lo = min(dx["put_wall"]["strike"], dx["spot"]) * 0.993; hi = max(dx["call_wall"]["strike"], dx["gamma_flip"]) * 1.007
    return strip(lo, hi, [(dx["spot"], f"<tspan class='b'>{sym} {dx['spot']}</tspan>", CLAY, -1),
                          (dx["gamma_flip"], f"Flip {f2(dx['gamma_flip'])}", "var(--text-2)", -1),
                          (dx["put_wall"]["strike"], f"Put wall {dx['put_wall']['strike']:g}", "var(--text-2)", 1),
                          (dx["call_wall"]["strike"], f"Call wall {dx['call_wall']['strike']:g}", "var(--text-2)", 1)], label=f"{sym} dealer levels")
_fdS, _fdQ = dS["flip_distance_pct"], dQ["flip_distance_pct"]
_uo = lambda v: "under" if v > 0 else "over"                  # flip_distance_pct > 0: the flip sits above the index
_gam = ("short gamma" if DEALER_REG == "NEGATIVE" else "long gamma" if DEALER_REG == "POSITIVE" else "not read")
c_gex = card(f"Dealers are {_gam}: SPY is {abs(_fdS)}% {_uo(_fdS)} the {f2(dS['gamma_flip'])} flip, so moves get {'bigger' if DEALER_REG == 'NEGATIVE' else 'damped' if DEALER_REG == 'POSITIVE' else 'unclear'}.",
    strip_dealer(dS, "SPY") + strip_dealer(dQ, "QQQ"),
    ((f"Moves get amplified in both directions until SPY reclaims about {dS['gamma_flip']:.0f}. " if (DEALER_REG == "NEGATIVE" and _fdS > 0) else
      f"Moves get amplified in both directions; SPY is already over the flip, so the risk is a fall back through {dS['gamma_flip']:.0f}. " if DEALER_REG == "NEGATIVE" else
      f"Moves get damped while SPY stays over {dS['gamma_flip']:.0f}. " if DEALER_REG == "POSITIVE" else "") + "The dealer side is a stated assumption, not observed data."),
    ("What the flip and walls are", "<p>Below the flip, dealers sell into falls and buy into rallies, so moves get bigger; above it they damp moves. "
     f"The put wall ({abs(pw_dist)}% {'below' if pw_dist < 0 else 'above'} SPY) usually acts as support; the call wall ({abs(kl('SPY call wall')['distance_pct'])}% {'below' if kl('SPY call wall')['distance_pct'] < 0 else 'above'}) as resistance. "
     f"QQQ is {abs(_fdQ)}% {_uo(_fdQ)} its own flip.</p>"))

# heartbeat line chart: committee numbers, series from the refreshed file (same 3 Nov last bar)
ser = RC["heartbeat"]["series"]; n = 252
ys, ma = ser["ratio"][-n:], ser["ma_20"][-n:]
hi12, lo12, ma_now = kl("RSP/SPY 12-month high"), kl("RSP/SPY 12-month low"), kl("RSP/SPY 20-day average")
ylo, yhi = lo12["level"] * 0.995, hi12["level"] * 1.004
PH, PT = 130, 8
py = lambda v: PT + PH * (1 - (v - ylo) / (yhi - ylo))
pts = " ".join(f"{i},{100*(1-(v-ylo)/(yhi-ylo)):.2f}" for i, v in enumerate(ys))
pma = " ".join(f"{i},{100*(1-(v-ylo)/(yhi-ylo)):.2f}" for i, v in enumerate(ma) if v)
hb_svg = (f'<svg class="viz" width="100%" height="{PH+PT+22}" role="img" aria-label="Equal-weight vs cap-weight S&amp;P, 12 months">'
    f'<svg x="0" y="{PT}" width="100%" height="{PH}" viewBox="0 0 {len(ys)-1} 100" preserveAspectRatio="none">'
    f'<polyline points="{pma}" fill="none" stroke="var(--bar)" stroke-width="2" vector-effect="non-scaling-stroke"/>'
    f'<polyline points="{pts}" fill="none" stroke="{CLAY}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'
    + "".join(f'<line x1="0" x2="100%" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="var(--line)" stroke-dasharray="3 4"/>'
              f'<text x="0" y="{py(v)-4:.1f}" class="t13" fill="var(--text-2)">{lab} {v:.4f}</text>'
              for v, lab, a in ((hi12["level"], "12-month high", "hi"), (lo12["level"], "12-month low", "lo")))
    + f'<text x="100%" y="{py(ys[-1])-6:.1f}" text-anchor="end" class="t13 b" fill="var(--text)">now {ys[-1]:.4f}</text>'
    + f'<text x="100%" y="{py(ma_now["level"])+16:.1f}" text-anchor="end" class="t13" fill="var(--text-2)">20-day avg {ma_now["level"]:.4f}</text>'
    + f'<text x="0" y="{PH+PT+18}" class="t13" fill="var(--text-2)">{datetime.strptime(ser["dates"][-n], "%Y-%m-%d"):%-d %b %Y}</text>'
    + f'<text x="100%" y="{PH+PT+18}" text-anchor="end" class="t13" fill="var(--text-2)">{d(ser["dates"][-1])}</text></svg>')
_hbr = str(hb.get("regime") or "").lower()
c_hb = card((f"The average stock is beating the index: breadth has been broadening for {hb['days_in_this_regime']} days." if _hbr == "broadening" else
             f"The average stock is lagging the index: breadth has been {E(_hbr or 'unread')} for {hb['days_in_this_regime']} days." if _hbr in ("narrowing", "deteriorating") else
             f"Breadth reads {E(_hbr or 'unread')}: {E(str(hb.get('means') or 'no reading served'))}."),
    hb_svg + f'<div class="legend"><span><i class="sw" style="background:{CLAY}"></i>Equal-weight S&amp;P &divide; size-weighted S&amp;P (RSP/SPY)</span><span><i class="sw" style="background:var(--bar)"></i>Its 20-day average</span></div>'
             + f'<div class="chips"><span>5 days {sg(hb["change_5d_pct"],1)}%</span><span>20 days {sg(hb["change_20d_pct"],1)}%</span>'
             f'<span>60 days {sg(hb["change_60d_pct"],1)}%</span><span>confidence {hb["confidence"]} (Crown stops under 0.40)</span></div>',
    (f"The line is {abs(ma_now['distance_pct'])}% above its 20-day average ({ma_now['level']:.4f}); falling back under it would be the first sign breadth is narrowing again."
     if ma_now['distance_pct'] < 0 else
     f"The line is {abs(ma_now['distance_pct'])}% below its 20-day average ({ma_now['level']:.4f}): breadth is narrowing again."),
    ("What this line is", "<p>The equal-weight S&amp;P 500 (every stock the same size) divided by the normal, size-weighted S&amp;P 500. "
     "Rising means the average stock keeps up with the giants: a broad market. Crown reads this first; if it cannot read it, nothing else is used.</p>"))

flips = sorted([k for k in KL if k["kind"] == "trend followers"], key=lambda k: abs(k["distance_pct"]))[:6]
fl_rows = [(f"{E(k['what'].replace(' flip',''))} &middot; {'buyers above' if 'seller to buyer' in k['if_it_breaks'] else 'sellers below'} {k['level']:,.2f}",
            mins(f"{k['distance_pct']:+.2f}%"), k["distance_pct"], CLAY if k["what"].startswith("S&P") else GRAY) for k in flips]
lean = sorted(tf["by_sector"].items(), key=lambda kv: -kv[1])
LEAN = {"fx": "dollar", "ags": "farm goods"}
SECN = {"fx": "the dollar", "rates": "rates", "ags": "farm goods", "metals": "metals", "energy": "energy", "equity": "equities"}
_IDX = ("Dow", "S&P 500", "Nasdaq 100", "Russell 2000")                  # the title names the first two index flips served, in this order
_idx_flips = [k for nm in _IDX for k in KL if k["kind"] == "trend followers" and k["what"] == nm + " flip"][:2]
_verb = lambda k: "sellers" if "buyer to seller" in k["if_it_breaks"] else "buyers"
_nm = lambda k: {"Dow": "the Dow", "S&P 500": "the S&amp;P"}.get(k["what"].replace(" flip", ""), "the " + k["what"].replace(" flip", ""))
_cta_t = (f"Trend funds are {E(str(tf.get('bias') or 'unread'))}; " + " and ".join(
    f"they turn {_verb(k)} {abs(k['distance_pct'])}% {'lower' if k['distance_pct'] < 0 else 'higher'} on {_nm(k)}" if i == 0 else
    f"{abs(k['distance_pct'])}% {'lower' if k['distance_pct'] < 0 else 'higher'} on {_nm(k)}" for i, k in enumerate(_idx_flips)) + ".") if _idx_flips else \
    f"Trend funds are {E(str(tf.get('bias') or 'unread'))}; no index flip line was served."
c_cta = card(_cta_t,
    hbars(fl_rows, min(k["distance_pct"] for k in flips), max(k["distance_pct"] for k in flips), "Nearest trend-fund flip lines, distance from now"),
    f"{tf['markets_read']} markets, {tf['share_at_an_extreme']*100:.0f}% at an extreme, size dial {tf['size_dial']:.2f}. "
    + (lambda bs: f"They lean {'long' if max(bs.values()) > 0 else 'short'} {SECN.get(max(bs, key=bs.get), max(bs, key=bs.get))} ({sg(max(bs.values()))}) and "
                f"{'short' if min(bs.values()) < 0 else 'long'} {SECN.get(min(bs, key=bs.get), min(bs, key=bs.get))} ({sg(min(bs.values()))}).")(tf["by_sector"]),
    ("Lean by market group, and what this is", "<p>" + " &middot; ".join(f"{LEAN.get(k, k)} {sg(v)}" for k, v in lean)
     + " (&minus;1 short to +1 long).</p><p>Trend-following funds buy what rises and sell what falls by formula. We replicate that formula across "
     f"{tf['markets_read']} futures markets to find the price where each one flips them. Those lines are where moves can speed up. "
     "The size dial is Crown&rsquo;s multiplier on your own normal risk: 1.00 means no change.</p>"))

def ordn(x):
    n = int(round(x)); suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"
vk = {k["what"]: k for k in KL if k["kind"] == "volatility"}
calm, elev = vk["Single-stock vs index gap — calm band"]["level"], vk["Single-stock vs index gap — elevated band"]["level"]
ic = next(k for k in KL if k["kind"] == "correlation")
_GAP = {"NORMAL_RISING": "normal but rising", "NORMAL_EASING": "normal and easing", "ELEVATED_RISING": "elevated and rising", "ELEVATED_EASING": "elevated but easing"}
_gap_state = _GAP.get(str(vol.get("state")), str(vol.get("state") or "not read").replace("_", " ").lower())
_disagree = any("disagree" in str(x).lower() for x in (CR.get("limits") or []))
c_vol = card(f"VIX at {vol['vix']} {VIX_PHRASE}; the single-stock gap is {_gap_state}.",
    '<p class="lab">VIX</p>' + strip(10, 30, [(vol["vix"], f"<tspan class='b'>Now {vol['vix']}</tspan>", CLAY, -1),
                                         (15, "15: sell premium", GRAY, 1), (25, "25: protection expensive", GRAY, 1)], label="VIX")
    + '<p class="lab">Single-stock volatility minus VIX</p>'
    + strip(15, 26, [(vol["gap"], f"<tspan class='b'>Now {vol['gap']}</tspan>", CLAY, -1),
                     (calm, f"Calm under {calm}", GRAY, 1), (elev, f"Elevated over {elev:.2f}", "var(--watch)", 1)],
            bands=[(calm, elev, "var(--soft)")], label="Volatility gap")
    + f'<div class="chips"><span>gap wider than {vol["gap_vs_history"]*100:.0f}% of history</span><span>{sg(vol["gap_change_20d"])} in 20 days</span>'
      f'<span>implied correlation {vol["implied_correlation"]} ({ordn(ic["now"])} percentile)</span><span>curve {vol["term_structure"].lower()}</span></div>',
    (f"The index is {'not quiet' if vol['vix'] >= 15 else 'quiet'} and the gap is {'rising' if vol['gap_change_20d'] > 0 else 'easing'}"
     + (", but two other gauges of how differently stocks move (Cboe's dispersion index and implied correlation) do not confirm the gap, so treat that read with caution. " if _disagree else ". ")
     + f"Committee-time data, dated {d(CR['how_current']['volatility_as_of'])}."),
    ("What these are", f"<p>VIX is the expected 30-day swing of the S&amp;P 500, read from options. Single-stock volatility ({vol['single_stock_vol']}) is the same for the average large stock. "
     "A wide gap means risk and opportunity sit in single names, not the index. Implied correlation is how much stocks are expected to move together; "
     "low means stock picking pays. Contango, near-term cheaper than longer-term, is the normal shape.</p>"))

dv = V["crown_cockpit"]["divergence"]
boxes = "".join(f'<rect x="{i*12.5+0.6:.1f}%" y="0" width="11%" height="26" rx="5" fill="{"var(--watch-bg)" if i < dv["count"] else "var(--soft)"}" stroke="var(--line)"/>'
                for i in range(dv["total"]))
_DIVW = {"rsi": "momentum is not keeping up with price"}
_which = [_DIVW.get(x, x) for x in (RD["divergence"].get("which") or [])]
c_div = card(f"{nword(dv['count'])} of {dv['total']} market-level warnings {'is' if dv['count'] == 1 else 'are'} lit" + (f": {' and '.join(_which)}." if dv["count"] and _which else "."),
    f'<svg class="viz" width="100%" height="30" role="img" aria-label="{dv["count"]} of {dv["total"]} warnings lit">{boxes}</svg>'
    f'<div class="chips"><span>{dv["count"]} of {dv["total"]} market-level types</span><span>{RD["divergence"]["warnings_lit"]} on individual markets</span></div>',
    ("One warning is no reason to sell; it counts when several agree with a weak breadth reading. "
     + ("Breadth is not weak, so the warnings are not yet lining up with it." if _hbr == "broadening" else
        f"Breadth reads {E(_hbr or 'unread')}, so check whether the warnings are lining up with it.")),
    ("What a divergence is", "<p>One reading failing to confirm another: price making highs while momentum fades, or stocks rising while copper, credit, the dollar or "
     "volatility say otherwise. Crown checks eight types for the market and the same tests on each futures market.</p>"))

call, scen = CR["the_call"], CR["scenario"]
_cond_name = lambda x: COND.get(x, x.replace("_", " ").capitalize())
COND = {"broadening": "Breadth broadening", "range_not_extreme": "Breadth not at an extreme of its range", "dispersion_normal": "Single-stock gap normal",
        "cta_low_flip": "Trend funds not crowded", "gamma_positive": "Dealers damping moves"}
cond_rows = [[_cond_name(x), pill("met", "good")] for x in call["conditions_met"]] + [[_cond_name(x), pill("not met", "bad")] for x in call["conditions_not_met"]]
sc_pct = round(scen["score_share_of_conditions"] * 100)
c_call = card(f"Crown&rsquo;s call is {E(str(call.get('expression_family') or 'unread').replace('_', ' ').lower())} at {call['size_multiplier']:.2f}x your normal risk, a {E(str(call.get('match_quality') or 'unrated'))} fit: {len(call['conditions_met'])} of {len(cond_rows)} conditions met.",
    table(["Condition", "Today"], cond_rows, "tight")
    + hbars([(f"Leading story: {scen['leading'].replace('_',' ').title()}" + (f", contested by {scen['runner_up'].replace('_',' ').title()}" if scen.get("contested") and scen.get("runner_up") else ""), f"{sc_pct}% of its conditions", sc_pct, CLAY)], 0, 100, "Leading macro story"),
    E(scen["story"]) + " " + E(CR["read_me_first"]["so_what"].split(" — ")[0]) + ".",
    ("What would change the call", "<ul class='plainlist'>" + "".join(f"<li>{E(x)}</li>" for x in CR["read_me_first"]["what_would_change_it"]) + "</ul>"
     "<p>Crown names a family of trades and a multiplier on your own risk, never a ticker or a size. A story&rsquo;s score is the share of its conditions met, not a probability.</p>"))

today = RUN_DATE.date()
horizon = (RUN_DATE + __import__('datetime').timedelta(days=7)).date()
evs = collections.OrderedDict()
for x in CR["what_is_coming"]:
    if x["kind"] != "macro":
        continue
    dt = datetime.strptime(f"{x['date']} {x['time_et']}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(SGT)
    if datetime.strptime(x["date"], "%Y-%m-%d").date() < today:
        continue
    evs.setdefault(dt, []).append(x)
ev_items = list(evs.items())
shown_ev = [e for e in ev_items if e[0].date() <= horizon][:5]
tl = "".join(f'<li><span class="when">{dt:%a %-d %b} &middot; {dt:%H:%M} SGT</span><span>{" and ".join(E(x["event"]) for x in xs)}</span></li>' for dt, xs in shown_ev)
c_cal = card((f"{len(shown_ev)} scheduled US data release{'s' if len(shown_ev) != 1 else ''} land{'s' if len(shown_ev) == 1 else ''} before {horizon.day} {horizon:%b}, starting with {E(' and '.join(x['event'] for x in shown_ev[0][1]))} on {shown_ev[0][0]:%a %H:%M} SGT."
              if shown_ev else f"No scheduled US data release lands before {horizon.day} {horizon:%b}."),
    f'<ul class="timeline">{tl}</ul>', "Hourly triggers around those prints are the ones to treat with care.",
    ("What each release tests", "<ul class='plainlist'>" + "".join(f"<li><b>{E(x['event'])}</b> ({x['day']} {d(x['date'])}, {x['time_et']} ET): {E(x['what_it_tests'])}</li>"
                                                              for _, xs in ev_items for x in xs) + "</ul>"))

COTN = dict(_PC.COT_NAMES, NQ="Nasdaq-100", RTY="Russell 2000", ZF="5-year Treasury", ZT="2-year Treasury", CL="Crude oil", NG="Natural gas", SI="Silver")
_ceq = {"ES", "NQ", "RTY", "YM"}
cot = V["crown_cockpit"]["cot"]; cm = RC["cot"]["markets"]
cot_rows = [(f"{COTN[c]} &middot; crowded long", f"{ordn(cm[c]['percentile']*100)} percentile", cm[c]["percentile"] * 100, CLAY if c in _ceq else GRAY) for c in cot["crowded_long"]] \
         + [(f"{COTN[c]} &middot; crowded short", f"{ordn(cm[c]['percentile']*100)} percentile", cm[c]["percentile"] * 100, GRAY) for c in cot["crowded_short"]]
_jn = lambda L: ", ".join(L[:-1]) + (" and " if len(L) > 1 else "") + L[-1] if L else ""
c_cot = card("Big speculators are " + (f"crowded long {_jn([COTN.get(c, c) for c in cot['crowded_long']])}" if cot["crowded_long"] else "not crowded long anywhere")
             + (f", and crowded short {_jn([COTN.get(c, c) for c in cot['crowded_short']])}." if cot["crowded_short"] else "; none is crowded short."),
    hbars(cot_rows, 0, 100, "Speculator positioning percentile vs 3 years", guides=((15, ""), (85, ""))),
    f"Crowding is fuel for a fast drop if a flip line breaks, never a timing signal. Report as of {d(cot['as_of'])}" + (f"; the next one is out {d(nxt)}." if nxt else ".") + "",
    ("How crowding is measured", "<p>The weekly CFTC report shows how large speculators are positioned in US futures. Their net position, as a share of all open contracts, "
     "is ranked against the last three years: 85th percentile or higher is crowded long, 15th or lower crowded short (the dashed lines). "
     "The report covers Tuesday and comes out Friday, so it is at least three days old.</p>"))

if stale:
    wind_svg = (f'<svg class="viz" width="100%" height="52" role="img" aria-label="Share of tickers with the latest bar">'
        f'<text x="0" y="15" class="t13" fill="var(--text)">Tickers with the {d(stale.group(4))} bar</text>'
        f'<text x="100%" y="15" text-anchor="end" class="t13 b" fill="var(--text)">{st_pct}% ({st_have:,} of {st_tot:,})</text>'
        f'<rect x="0" y="22" width="100%" height="12" rx="3" fill="var(--soft)"/><rect x="0" y="22" width="{st_pct}%" height="12" rx="3" fill="var(--bad)"/>'
        f'<line x1="{st_need}%" x2="{st_need}%" y1="18" y2="38" stroke="var(--text)" stroke-width="2"/>'
        f'<text x="{st_need}%" y="50" text-anchor="end" class="t13" fill="var(--text-2)">{st_need}% needed</text></svg>')
    c_wind = card(f"No breadth checklist could be read: {st_pct}% of tickers carried the {d(stale.group(4))} bar, and {st_need}% are needed.",
        wind_svg, "The net-new-highs and 4% counts that decide how open trades are managed cannot be quoted; that is a gap, not a neutral reading.",
        ("The 11 gauges that were stale", "<ul class='plainlist'>" + "".join(f"<li>{E(b['label'].replace('T2108 — ', ''))}: stale</li>" for b in V["breadth"]) + "</ul>"
         "<p>The share of stocks above their 40-day line: under 20% is washed out, over 80% overheated; Valen wants it above 50% before calling risk-on. "
         "The 4% count is stocks up 4% or more in a day against stocks down 4% or more, over 5 or 10 days.</p>"))
else:
    _brows = [[E(str(b.get("label") or "").replace("T2108 — ", "")), E(str(b.get("display") if b.get("display") not in (None, "") else b.get("value") if b.get("value") is not None else "not read")),
               pill(str(b.get("status") or "?").title(), "good" if b.get("status") == "OK" else "bad")] for b in V.get("breadth") or []]
    c_wind = card("Whole-market breadth gauges" + ("" if _brows else ": none was served") + ("; " + str(sum(1 for b in V.get("breadth") or [] if b.get("status") == "OK")) + " of " + str(len(_brows)) + " read." if _brows else "."),
        table(["Gauge", "Reading", "Status"], _brows, "tight") if _brows else "",
        "Where a gauge did not read, the page says so: that is a gap, not a neutral reading.")

tone_reg = {"DOWNTREND": "bad", "CHOP": "watch", "UPTREND": "good"}
h_reg, h_spy = hist["Trend regime"], hist["SPY ATRs above 50-day"]
_RW = {"DOWNTREND": "downtrend", "UPTREND": "uptrend", "CHOP": "choppy range"}
_rn, _r1 = h_reg["now"], h_reg["1mo_ago"]
c_turn = card((f"The weather turned from {_RW.get(_r1, str(_r1).lower())} to {_RW.get(_rn, str(_rn).lower())} in one month." if _rn != _r1
               else f"The weather has stayed a {_RW.get(_rn, str(_rn).lower())} for a month."),
    table(["Reading", "Now", "5 days ago", "1 month ago"],
          [["Trend", *[pill(h_reg[k].title(), tone_reg[h_reg[k]]) for k in ("now", "5d_ago", "1mo_ago")]],
           ["SPY from its 50-day avg, daily ranges", *[f"<b>{mins(f'{h_spy[k]:+.2f}')}</b>" if k == "now" else mins(f"{h_spy[k]:+.2f}") for k in ("now", "5d_ago", "1mo_ago")]]]),
    f"SPY went from {sg(h_spy['1mo_ago'])} to {sg(h_spy['now'])} daily ranges against its 50-day average in a month.")

s1 = section("1 &middot; Macro and weather", ({"DOWNTREND": "The index is in a downtrend", "UPTREND": "The index is in an uptrend", "CHOP": "The index is in a choppy range"}.get(TREND, "The index trend is unclear")
              + (", but the average stock is holding up." if (TREND != "UPTREND" and _hbr == "broadening") else
                 " and the average stock is keeping up." if _hbr == "broadening" else
                 ", and breadth is narrowing too." if _hbr in ("narrowing", "deteriorating") else ".")),
             f'<div class="grid">{c_valen}{c_gex}{c_hb}{c_cta}{c_vol}{c_div}{c_call}{c_cal}{c_cot}{c_wind}{c_turn}</div>', "macro")

# ------------------------------------------------------------------ 2 SECTOR AND THEME STRENGTH
GT = {"PASS": "good", "WATCH": "watch", "CAUTION": "watch", "BLOCKED": "bad"}
secs = sorted(D["srm"], key=lambda s: -s["roc20"])
sec_rows = [(f"{E(s['sector'])} &middot; gate {s['entry_gate']}", mins(f"{s['roc20']:+.2f}%"), s["roc20"], CLAY if s["sector"] == secs[0]["sector"] else GRAY) for s in secs]
c_sec = card(f"{secs[0]['sector']} leads at {sg(secs[0]['roc20'])}% in 20 days; {secs[-1]['sector']} trails at {sg(secs[-1]['roc20'])}%.",
    hbars(sec_rows, min(s["roc20"] for s in secs), max(s["roc20"] for s in secs), "Sector return over 20 days"),
    " ".join(E(m["meaning"]) for i, m in enumerate(T.get("money") or []) if i in (0, 2)),
    ("Where money is moving, group by group", table(["Group", "Read", "What it means"], [[f"<b>{E(x['group'])}</b>", E(x["read"]), E(x["meaning"])] for x in T["money"]])))

tlv = [t for t in V["theme_leaders"] if t.get("rotation_state") in ("LEADING", "OFF_THE_FLOOR")]
tlv.sort(key=lambda t: (t.get("rotation_state") != "LEADING", -(t.get("ret_1m_pct") or -99)))
_both_up = [t["display_name"] for t in sorted([t for t in tlv if (t.get("ret_1w_pct") or 0) > 0 and (t.get("ret_1m_pct") or 0) > 0], key=lambda t: -t["ret_1m_pct"])][:2]   # the two strongest over a month that are also up on the week
th_rows = [(f"{E(t['display_name'])} &middot; week {mins(f'{t['ret_1w_pct']:+.1f}')}% &middot; {abs(t['pct_off_52w_high']):.1f}% off high",
            f"month {mins(f'{t['ret_1m_pct']:+.1f}')}%", t["ret_1m_pct"], CLAY if t["display_name"] in _both_up else GRAY) for t in tlv[:5]]
STATE = lambda t: {"LEADING": "Leading near its highs", "OFF_THE_FLOOR": "Bouncing off the floor"}.get(t["rotation_state"], "")
def thrust_state(t):
    w, m, th = t.get("ret_1w_pct"), t.get("ret_1m_pct"), t.get("thrust")
    return "Rising" if w > 0 and m > 0 else ("Turning up" if w > 0 else ("Still falling, but slower" if th and th > 0 else "Falling faster"))
rot = sorted(V["rotation"], key=lambda t: -(t.get("thrust") or -99))[:6]
trow = lambda t, st: [E(t["display_name"]), mins(f"{t['ret_1w_pct']:+.1f}%"), mins(f"{t['ret_1m_pct']:+.1f}%"), f"{abs(t['pct_off_52w_high']):.1f}%", st]
c_th = card((f"{' and '.join(E(x) for x in _both_up)} lead{'s' if len(_both_up) == 1 else ''} on both the week and the month." if _both_up else "No theme leads on both the week and the month."),
    hbars(th_rows, min(0, min(r[2] for r in th_rows)), max(r[2] for r in th_rows), "Theme return over 1 month"),
    ((f"{' and '.join(E(x) for x in _both_up)} {'is' if len(_both_up) == 1 else 'are'} where leadership is; the strong names inside each group are in the next card." if _both_up
      else "Leadership is thin: no theme is up on both horizons.")),
    ("All theme leaders, and where the turn is sharpest",
     "<ul class='plainlist'>" + "".join(f"<li>{E(x)}</li>" for x in V["neighbourhood"]) + "</ul>"
     + table(["Leader", "1 week", "1 month", "Off 52-week high", "State"], [trow(t, STATE(t)) for t in tlv])
     + table(["Sharpest turn", "1 week", "1 month", "Off 52-week high", "State"], [trow(t, thrust_state(t)) for t in rot])
     + "<p>The turn is ranked by this week&rsquo;s return minus this month&rsquo;s: a theme falling much less sharply than before ranks high even while it falls.</p>"))

# strong stocks riding a group turn (same rule as the real page's code)
def gkind(g, q):
    if g == "TURNING" or q == "IMPROVING": return "turn"
    if q == "LEADING" and g in ("DEPLOY", "HOLD"): return "lead"
def gword(g, q):
    if g == "TURNING":
        return {"IMPROVING": "Turning up, now gaining on the market", "WEAKENING": "Turning back up after a pullback", "LAGGING": "Turning up from the bottom, still lagging"}.get(q, "Turning up")
    return {"IMPROVING": "Improving: starting to beat the market", "LEADING": "Leading the market"}.get(q)
grp = collections.defaultdict(dict); meta = {}
for r in D["daily_list"]:
    rs, e_, m_ = r.get("rs_spy_20d"), r.get("entry"), r.get("ma_50")
    if not ((r.get("on_longlist") or r.get("on_elder")) and isinstance(rs, (int, float)) and rs > 0 and isinstance(e_, (int, float)) and isinstance(m_, (int, float)) and e_ > m_):
        continue
    for b in r.get("thematic_baskets") or []:
        k = gkind(b.get("grade"), b.get("rrg_quadrant"))
        if k:
            key = ("Theme", b["basket"].replace("_", " ")); grp[key][r["ticker"]] = r; meta[key] = (k, gword(b.get("grade"), b.get("rrg_quadrant")), b.get("grade"))
    x = SRM.get(r.get("gics_sector_name"))
    if x:
        k = gkind(x.get("grade"), x.get("rrg_quadrant"))
        if k:
            key = ("Sector", x["sector"]); grp[key][r["ticker"]] = r; meta[key] = (k, gword(x.get("grade"), x.get("rrg_quadrant")), x.get("grade"))
VERD = {c["ticker"]: {"ADVANCE": "ADVANCE", "HOLD-FOR-CONDITIONS": "HOLD", "PASS": "PASS"}[c["verdict"]] for c in CONS}
def gkeys(which):
    ks = [k for k in grp if meta[k][0] == which and (k[0] == "Sector" or len(grp[k]) >= 2)]
    return sorted(ks, key=lambda k: (k[0] != "Sector", meta[k][2] != "TURNING", -len(grp[k])))
def top3(k, n=3):
    return sorted(grp[k].values(), key=lambda r: -r["rs_spy_20d"])[:n]
turn_k = sorted(gkeys("turn"), key=lambda k: -len(grp[k]))
_wrong_side = [t for t in ADV if any(b.get("grade") == "AVOID" or b.get("rrg_quadrant") == "LAGGING" for b in (ROWS.get(t, {}).get("thematic_baskets") or []))]
gr_rows = [(f"{E(k[1])} &middot; " + ", ".join(f"{r['ticker']} {r['rs_spy_20d']:+.0f}%" for r in top3(k)), f"{len(grp[k])} strong names", len(grp[k]), GRAY) for k in turn_k]
names_cell = lambda k: " ".join(f"<b>{r['ticker']}</b> {r['rs_spy_20d']:+.0f}%" + (f" ({VERD[r['ticker']]})" if r["ticker"] in VERD else "") for r in top3(k, 6)) + (f" +{len(grp[k])-6} more" if len(grp[k]) > 6 else "")
c_grp = card(f"Strong names are turning up with {', '.join(k[1] for k in turn_k[:-1])} and {turn_k[-1][1]}.",
    hbars(gr_rows, 0, max(r[2] for r in gr_rows), "Strong names per turning group"),
    ("That is a place to look, not a list to buy" + (f", and {', '.join(_wrong_side)} {'is' if len(_wrong_side) == 1 else 'are'} among the ADVANCE names whose group is on the wrong side." if _wrong_side else ".")),
    ("Already-leading groups, and how strong is defined",
     table(["Group", "What it is doing", "Strong names", "Strongest vs SPY over 20 days"],
           [[f"<b>{E(k[1])}</b> ({k[0].lower()})", E(meta[k][1]), len(grp[k]), names_cell(k)] for k in gkeys("lead")])
     + "<p>A strong name is on the Longlist or Elder list, beating SPY over 20 days and above its 50-day average. Percentages are the lead over SPY in 20 days. "
       "A name can sit under its sector and its theme.</p>"))

hs = collections.Counter(); hs_status = collections.Counter()
for r in ROWS.values():
    gr = r.get("setups"); gr = gr.get("grades") if isinstance(gr, dict) else gr
    for x in gr or []:
        if not isinstance(x, dict): continue
        nm = str(x.get("setup", "")).lower()
        if "parabolic" in nm or "failed leader" in nm:            # R41: Valen's risk warnings are never printed
            continue
        hs[(x.get("setup"), x.get("status"))] += 1; hs_status[x.get("status")] += 1
n_ready = hs_status.get("TRIGGERED", 0) + hs_status.get("READY", 0)
ST = [("Triggered or ready", n_ready, CLAY), ("Watch", hs_status.get("WATCH", 0), GRAY), ("Past the pivot", hs_status.get("PAST_PIVOT", 0), GRAY), ("Failed", hs_status.get("FAILED", 0), GRAY)]
c_hs = card(("No Valen house setup is triggered or ready across the list." if not n_ready else f"{n_ready} Valen house setup grade{'s are' if n_ready != 1 else ' is'} triggered or ready across the list."),
    hbars([(a, str(b), b, c) for a, b, c in ST], 0, max(b for _, b, _ in ST), "Valen house setups by status"),
    f"{sum(hs_status.values())} setup grades across the list" + ("; none is a buy today." if not n_ready else "; the triggered or ready ones are in the table below."),
    ("Every setup grade", "<p>" + ", ".join(f"{E(a)} {E(str(b).replace('PAST_PIVOT','past the pivot').lower())} &times;{n}" for (a, b), n in sorted(hs.items())) + ".</p>"))
GRADE_ORDER = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}
def basket_card():
    """PM 2026-11-04 ('essential, thin is fine, baskets are a proxy'): AQE's curated theme baskets, their grade, week, month, rotation and strongest members."""
    tb = D.get("thematic_baskets") or {}
    if not isinstance(tb, dict) or not tb:
        return card("Theme baskets are not in the export.", "", "Declared gap: nothing is invented.")
    byt = {r.get("ticker"): r for r in D["daily_list"]}
    rows_ = []
    for name, b in sorted(tb.items(), key=lambda kv: (GRADE_ORDER.get(str(kv[1].get("grade")), 9), -(kv[1].get("roc20") if isinstance(kv[1].get("roc20"), (int, float)) else -999))):
        mem = sorted([byt[t] for t in (b.get("constituents_used") or []) if t in byt and isinstance(byt[t].get("rs_spy_20d"), (int, float))], key=lambda r: -r["rs_spy_20d"])[:3]
        g = str(b.get("grade") or "")
        rows_.append([E(name.replace("_", " ")), pill(E(g.title() or "n/a"), {"DEPLOY": "good", "AVOID": "bad", "TURNING": "watch"}.get(g, "")),
                      mins(f"{b['roc5']:+.1f}%") if isinstance(b.get("roc5"), (int, float)) else "&mdash;", mins(f"{b['roc20']:+.1f}%") if isinstance(b.get("roc20"), (int, float)) else "&mdash;",
                      E(" ".join(x for x in (str(b.get("rrg_quadrant") or "").title(), "&middot;", str(b.get("rrg_direction") or "").lower()) if x != "&middot;" or b.get("rrg_direction")) or "&mdash;"),
                      ", ".join(f"<b>{E(r['ticker'])}</b> {r['rs_spy_20d']:+.0f}%" for r in mem) or "&mdash;"])
    n_deploy = sum(1 for b in tb.values() if b.get("grade") == "DEPLOY")
    return card(f"{n_deploy} of AQE&rsquo;s {len(tb)} theme baskets grade Deploy.", "",
                "Baskets are a hand-picked proxy for themes, not the whole market. A name in no basket is simply not here.",
                ("All baskets: grade, week, month, rotation, strongest members",
                 table(["Basket", "Grade", "1 week", "1 month", "Rotation", "Strongest members (20-day strength vs SPY)"], rows_)))
c_basket = basket_card()
s2 = section("2 &middot; Sector and theme strength", (f"Money sits in {_jn2([SHORT.get(x, x) for x in lead_secs])}" if lead_secs else "No sector passes the entry gate")
             + (f"; {_jn2(blocked_lag)} lag." if blocked_lag else "."),
             f'<div class="grid">{c_sec}{c_th}{c_basket}{c_grp}{c_hs}</div>', "sectors")

# ------------------------------------------------------------------ 3 WHAT HAPPENED
yv = lambda s: float(s.replace("%", ""))
CLOSE_DT = datetime.strptime(close_d, "%Y-%m-%d"); CLOSE_WD = CLOSE_DT.strftime("%A"); CLOSE_S = f"{CLOSE_DT.day} {CLOSE_DT:%b}"
_mv = lambda x: ("rose" if yv(x) >= 0 else "fell")
_pad = max(0.3, 0.2 * max(abs(yv(y_spy)), abs(yv(y_list))))
c_idx = card(f"On {CLOSE_WD} SPY {_mv(y_spy)} {y_spy.lstrip('-+')} while the equal-weight list {_mv(y_list)} {y_list.lstrip('-+')}.",
    hbars([(f"SPY, {CLOSE_S}", y_spy, yv(y_spy), GRAY), (f"AQE list, equal weight, {CLOSE_S}", mins(y_list), yv(y_list), CLAY)], min(0, min(yv(y_spy), yv(y_list))) - _pad, max(0, max(yv(y_spy), yv(y_list))) + _pad, "One-session returns")
    + f'<div class="chips"><span>only {y_beat.split("/")[0]} of {y_beat.split("/")[1]} list names beat SPY</span><span>SPY {mins(f"{D['spy_roc_20d']:.2f}")}% over 20 days</span></div>',
    f"SPY closed {spy['last_price']}, {abs(ext['SPY ATRs above 50-day'])} daily ranges {'under' if ext['SPY ATRs above 50-day'] < 0 else 'over'} its 50-day average.")
mw = D["macro_weather"]
MW = [("tlt", "Long Treasuries (TLT)"), ("uup", "US dollar (UUP)"), ("hyg", "High-yield credit (HYG)"), ("iwm", "Small caps (IWM)"),
      ("gld", "Gold (GLD)"), ("cper", "Copper (CPER)"), ("uso", "Oil (USO)")]
mw_rows = [(lab, mins(f"{mw[k+'_roc5']:+.2f}%"), mw[k + "_roc5"], GRAY) for k, lab in MW]
_up5 = [lab.split(" (")[0] for lab, _, v, _c in mw_rows if v > 0]; _dn5 = [lab.split(" (")[0] for lab, _, v, _c in mw_rows if v <= 0]
_big = [lab.split(" (")[0] for lab, _, v, _c in sorted(mw_rows, key=lambda r: r[2])[:3] if v < 0]
c_x = card((("Everything in the cross-asset set fell over five days" if not _up5 else "Everything in the cross-asset set rose over five days" if not _dn5 else
             f"Over five days {_jn2(_up5)} rose and {_jn2(_dn5)} fell") + (f"; {_jn2(_big)} fell most." if _big and _dn5 else ".")),
    hbars(mw_rows, min(0, min(r[2] for r in mw_rows)), max(0.2, max(r[2] for r in mw_rows)), "Five-day returns"),
    E(mw["regime_description"]),
    ("Twenty-day view", "<p>" + " &middot; ".join(f"{k.upper()} {mins(f'{D['intermarket'][k]['roc20']:+.2f}')}%" for k in ("tlt", "uup", "hyg"))
     + f" &middot; IWM {mins(f'{D['intermarket']['spy_iwm']['iwm_roc20']:+.2f}')}% "
     f"against SPY {mins(f'{D['spy_roc_20d']:+.2f}')}% (20 days). Five-day returns as of {d(mw['snapshot_date'])}.</p>"))
hv = hist["VIX / VIX3M"]
_vv_vals = [hv["1mo_ago"], hv["5d_ago"], hv["now"], 0.82, 1.00]
c_vv = card(f"Near-term fear {'rose' if hv['now'] > hv['1mo_ago'] else 'eased' if hv['now'] < hv['1mo_ago'] else 'held'}: VIX against the 3-month VIX went from {hv['1mo_ago']:.2f} to {hv['now']:.2f} in a month.",
    strip(min(_vv_vals) - 0.04, max(_vv_vals) + 0.04, [(hv["1mo_ago"], f"1 month ago {hv['1mo_ago']:.2f}", GRAY, -2), (hv["5d_ago"], f"5 days ago {hv['5d_ago']:.2f}", GRAY, -1),
                       (hv["now"], f"<tspan class='b'>Now {hv['now']:.2f}</tspan>", CLAY, -2),
                       (0.82, "0.82 calm", "var(--good)", 1), (1.00, "1.00 stress", "var(--bad)", 1)],
          bands=[(0.82, 1.00, "var(--soft)")], label="VIX against 3-month VIX"),
    "Under 0.82 is calm; over 1.00 means near-term fear has overtaken the 3-month view.")
s3 = section("3 &middot; What happened", f"SPY {'fell' if D['spy_roc_20d'] < 0 else 'rose'} {abs(D['spy_roc_20d'])}% in 20 days, and on {CLOSE_WD} the list {'lagged' if yv(y_list) < yv(y_spy) else 'led' if yv(y_list) > yv(y_spy) else 'matched'} a {'rising' if yv(y_spy) > 0 else 'falling'} SPY.",
             f'<div class="grid">{c_idx}{c_x}{c_vv}</div>', "happened")

# ------------------------------------------------------------------ 4 YOUR BOOK
mg = {x["ticker"]: x for x in (V.get("management") or {}).get("trim_trail") or []}
bk = {b["ticker"]: b for b in T.get("book") or []}
hbk = D.get("held_book") or {}; pos_b = {p["ticker"]: p for p in hbk.get("positions") or []}
_cap1 = lambda x: x[:1].upper() + x[1:]

def held_card(t):
    h, m, w = HELD[t], mg.get(t) or {}, bk.get(t) or {}
    why = str(w.get("why") or "")
    exit_case = str(w.get("tone")) == "down"
    pill_txt = _cap1(str(w.get("read_pill") or "Held").replace(" \u00b7 ", ", ").lower())
    add = re.search(r"daily close above ([\d.]+)", why)
    v_add = float(add.group(1)) if add else None
    up = h["unreal_usd"] >= 0
    # A HELD NAME WITH NO STOP ORDER (conductor 2026-11-11): held_sl is None. min() over a list holding None raised TypeError, v3 fell back to v2 every run while the book was
    # unprotected and card_fields.json was never written. Skip every None mark; the missing stop is stated on the card in plain words instead of drawn.
    _no_stop = h.get("held_sl") is None
    marks_vals = [x for x in [h["entry"], h["live_px"], h.get("held_sl")] + ([v_add] if v_add else []) + ([m["ma_20"]] if (exit_case and m.get("ma_20")) else []) if x is not None]
    lo, hi = min(marks_vals) * 0.98, max(marks_vals) * 1.02
    if exit_case:
        marks = [(h["live_px"], f"<tspan class='b'>Last {h['live_px']}</tspan>", CLAY, -1), (h["entry"], f"Bought {h['entry']:.2f}", GRAY, -1)]
        if m.get("ma_20"):
            marks.append((m["ma_20"], f"20-day avg {m['ma_20']}", GRAY, -2))
        if not _no_stop:
            marks.append((h["held_sl"], f"Stop {h['held_sl']}", "var(--bad)", 1))
        title = (f"{t}: an exit case, {'up' if up else 'down'} ${abs(h['unreal_usd']):,.2f} on {int(h['qty'])} shares, "
                 + ("with NO stop order at the broker." if _no_stop else f"with the stop {(m.get('dist_from_stop_pct') or 0):.2f}% below."))
        tail = "NO stop order is working: this position is unprotected" if _no_stop else "stop-limit order working at the broker"
        body = E(_cap1(why.split("; ", 1)[1])) if "; " in why else E(why)
        tone = "bad"
    else:
        marks = [(h["entry"], f"Bought {h['entry']:.2f}", GRAY, -1), (h["live_px"], f"<tspan class='b'>Last {h['live_px']}</tspan>", CLAY, -1)]
        if not _no_stop:
            marks.append((h["held_sl"], f"Stop {h['held_sl']}", "var(--bad)", 1))
        if v_add:
            marks.append((v_add, f"Add above {v_add}", "var(--good)", 1))
        title = f"{t}: keep, {'up' if up else 'down'} ${abs(h['unreal_usd']):,.2f} on {int(h['qty'])} shares, " + ("with NO stop order at the broker." if _no_stop else f"with the stop at {h['held_sl']}.")
        tail = ("reports " + why.split("reports ")[-1].rstrip(".")) if "reports " in why else ""
        if _no_stop:
            tail = ("NO stop order is working: this position is unprotected" + (f"; {tail}" if tail else ""))
        body = (E(why.split("; reports")[0]) + ".")
        tone = "good"
    return card(title,
        strip(lo, hi, marks, label=f"{t} levels") + f'<div class="chips">{pill(pill_txt, tone)}' + (f"<span>{tail}</span>" if tail else "") + "</div>", body)

HELD_ORDER = [t for t in bk if t in HELD] + [t for t in HELD if t not in bk]
held_cards = "".join(held_card(t) for t in HELD_ORDER)
_bp = sorted(pos_b.values(), key=lambda p: -p["beta_adj_exposure_usd"])
_secname = lambda t: (HELD.get(t, {}).get("gics_sector_name") or HELD.get(t, {}).get("ptj_sector") or "")
if _bp:
    _gap5 = (hbk.get("gap_scenarios") or {}).get("gap_5pct") or {}
    c_conc = card(f"{_bp[0]['ticker']} carries ${_bp[0]['beta_adj_exposure_usd']:,.0f} of the book&rsquo;s ${hbk['beta_adj_exposure_usd']:,.0f} market-adjusted exposure.",
        hbars([(f"{p['ticker']} &middot; {E(_secname(p['ticker']))} {p['sector_weight_pct']:.1f}% of the book &middot; beta {p['beta_30d']}", f"${p['beta_adj_exposure_usd']:,.0f}", p["beta_adj_exposure_usd"], CLAY if i == 0 else GRAY)
               for i, p in enumerate(_bp)], 0, hbk["beta_adj_exposure_usd"], "Market-adjusted exposure by position"),
        f"A 1% market gap costs about ${hbk['loss_per_1pct_gap_usd']:,.0f}" + (f"; a 5% gap about ${_gap5['est_book_loss_usd']:,.0f}." if _gap5.get("est_book_loss_usd") is not None else "."),
        ("Trim and trail facts beside the handbook",
         table(["Name", "R so far (approx.)", "vs 20-day avg", "Stop distance", "Days held"],
               [[f"<b>{t}</b>", mins(f"{mg[t]['r_multiple']:+.2f}"), mins(f"{mg[t]['pct_vs_ma_20']:+.1f}%"), f"{mg[t]['dist_from_stop_pct']:.1f}%", mg[t]["days_held"]] for t in HELD_ORDER if t in mg])
         + "<p>Gap scenarios: " + ", ".join(f"{k.split('_')[1]} costs ${v['est_book_loss_usd']:,.0f}" for k, v in (hbk.get("gap_scenarios") or {}).items())
         + ". Handbook, quoted: trim into strength; trail the rest on one moving average, daily closes; add only when a winner proves itself again. "
           "R is approximate (current stop as the risk). "
         + ("Valen&rsquo;s management switch: " + E(str(((V.get("management") or {}).get("manage_note") or {}).get("note") or "")) if ((V.get("management") or {}).get("manage_note") or {}).get("status") == "OK"
            else "Valen&rsquo;s management switch was not served" + (": breadth was stale" if _stale_b else "") + ".")
         + " The call is yours.</p>"))
else:
    c_conc = ""
_clauses = []
for t in HELD_ORDER:
    h = HELD[t]; w = bk.get(t) or {}
    if str(w.get("tone")) == "down":
        _clauses.append(f"{t} is an exit case, {'up' if h['unreal_usd'] >= 0 else 'down'} ${abs(h['unreal_usd']):,.0f}")
    else:
        _clauses.append(f"keep {t} with " + ("NO stop order (unprotected)" if h.get("held_sl") is None else f"its stop at {h['held_sl']}"))
s4 = section("4 &middot; Your book", (_cap1("; ".join(_clauses)) + ".") if _clauses else "No positions are held.",
             f'<div class="grid">{held_cards}{c_conc}</div>' if HELD else '<div class="card"><p>No positions are held.</p></div>', "book")

# ------------------------------------------------------------------ 5 THE TICKERS
chg = {x.split(":")[0]: x for x in T.get("changed") or []}
def tick_list(s_): return re.findall(r"\b[A-Z]{2,5}(?:-[A-Z])?\b", s_)
def named(key):
    """Tickers a 'Key: A (detail), B (detail) and C (detail).' line is about: the symbol before each opening bracket, or the symbols before the first verb."""
    txt = (chg.get(key) or "").split(":", 1)[-1]
    if not chg.get(key):
        return []
    hits = re.findall(r"\b([A-Z]{2,5}(?:-[A-Z])?) \(", txt)
    return hits or tick_list(re.split(r" (?:was|were|advanced|are|is|the first)\b", txt)[0])
new_l = named("New ADVANCE") or tick_list((chg.get("New ADVANCE") or ":").split(":", 1)[1].split(", the")[0])
still = named("Still ADVANCE")
down = tick_list((chg.get("Downgraded") or ":").split(":", 1)[1].split(" was ")[0])
left = tick_list((chg.get("Left the room") or ":").split(":", 1)[1].split(" advanced")[0])
_parts = ([f"{nword(len(new_l)).lower()} {'name is' if len(new_l) == 1 else 'names are'} new"] if new_l else []) \
       + ([f"{nword(len(still)).lower()} {'is' if len(still) == 1 else 'are'} still advancing"] if still else []) \
       + ([f"{_jn2(down)} {'was' if len(down) == 1 else 'were'} downgraded"] if down else []) \
       + ([f"{nword(len(left)).lower()} left"] if left else [])
chg_html = ('<div class="card"><h3>Since yesterday: ' + (_jn2(_parts) if _parts else "nothing changed") + '.</h3><div class="chg">'
    + f'<div><span class="lab">New</span>{"".join(pill(t, "good") for t in new_l)}</div>'
    + f'<div><span class="lab">Still</span>{"".join(pill(t) for t in still)}</div>'
    + f'<div><span class="lab">Downgraded</span>{"".join(pill(t, "watch") for t in down)}</div>'
    + f'<div><span class="lab">Left</span>{"".join(pill(t) for t in left)}</div></div>'
    + f'<details><summary>Since when, and by how much</summary><ul class="plainlist">{"".join(f"<li>{E(x)}</li>" for x in T.get("changed") or [])}</ul></details></div>')

order = usable + thin
RH, mx = 50, 5.0
rh = RH * len(order) + 26
rsv = [f'<svg class="viz" width="100%" height="{rh}" role="img" aria-label="Reward in R at each target">']
for v in range(1, 6):
    x = 100 * v / mx
    rsv.append(f'<line x1="{x:.1f}%" x2="{x:.1f}%" y1="18" y2="{rh-22}" stroke="var(--line)" stroke-dasharray="{"0" if v == 1 else "3 4"}"/>')
    rsv.append(f'<text x="{x:.1f}%" y="{rh-6}" text-anchor="{"end" if v == 5 else "middle"}" class="t13" fill="var(--text-2)">{v}R</text>')
for i, r in enumerate(order):
    y = i * RH
    lab = (" &middot; ".join(f"{rv}R at {f2(tp)}" for rv, tp in r["ladder"][:2]) if len(r["ladder"]) >= 2
           else (f"only one level reaches 1R: {r['ladder'][0][0]}R at {f2(r['ladder'][0][1])}" if r["ladder"] else "no level reaches 1R"))
    col = "var(--text-2)" if len(r["ladder"]) >= 2 else "var(--bad)"
    rsv.append(f'<text x="0" y="{y+15}" class="t16 b" fill="var(--text)">{E(r["t"])}</text><text x="100%" y="{y+15}" text-anchor="end" class="t13" fill="{col}">{lab}</text>')
    for j, (rv, tp) in enumerate(r["ladder"][:2][::-1]):
        jj = 1 - j if len(r["ladder"]) >= 2 else 0
        rsv.append(f'<rect x="0" y="{y+22}" width="{100*min(rv,mx)/mx:.1f}%" height="14" rx="3" fill="{CLAY if jj == 1 else GRAY}"/>')
rsv.append("</svg>")
reward = ('<div class="card"><h3>Reward at the first two real targets, from the buy line, in R (1R = the risk to the stop)</h3>' + "".join(rsv)
          + f'<div class="legend"><span><i style="background:var(--bar)"></i>first target at 1R or more</span><span><i style="background:var(--clay)"></i>second target</span><span>1R = ${ONE_R}</span></div></div>')

def tmpl_ctx(t):
    """Everything the ten-field template reads for one name, from the run's files (nothing invented)."""
    row = ROWS.get(t) or {}
    lvr = LV.get(t) or {}
    cut = ""
    return {"ticker": t, "cons": CONS_BY.get(t), "pos": POS.get(t), "lv": lvr or None, "br": BRK.get(t), "row": row,
            "srm": SRM.get(row.get("gics_sector_name")), "mtf": MTF.get(t), "cx": CX, "held": t in HELD,
            "mark": (RMK.get(t) or {}).get("mark"), "mark_plain": (RMK.get(t) or {}).get("mark_plain"),
            "lane": (CONS_BY.get(t) or {}).get("lane") or lvr.get("lane"), "slate_ticket": SLATE_T.get(t),
            "market_kill": (mk_plain.split(": ", 1)[1] if ": " in mk_plain else mk_plain) if mk_plain else None,
            "on_lists": ON_LISTS.get(t), "lines": CL.get(t), "supplemental": bool(lvr.get("supplemental")), "committee_result": lvr.get("committee_result"), "cut_reason": cut or None}

def tmpl_card(t):
    """The fixed template card for one name; a whole-template check runs on every card (a dropped field stops the render, so the safety net falls back loudly)."""
    return _tmpl_from(tmpl_ctx(t))

def _tmpl_from(c):
    t = c["ticker"]
    head = f'<div class="row"><span class="tk">{E(t)}</span>{ma_pill(ROWS.get(t))}{mom_pill(t)}</div>'
    h = CT.render_card(c, E, head)
    LINE_FALLBACK.extend((t, f, p) for f, p in c.get("_fallback") or [])
    CARD_FIELDS[t] = {"tag": next((f["tag"] for f in c.get("_fields") or [] if f.get("tag")), None),
                      "fields": [{"id": f["id"], "label": f["label"], "text": f["text"]} for f in c.get("_fields") or []]}
    errs = CT.validate_card(h)
    if errs:
        raise SystemExit(f"card template broken for {t}: {errs}")
    return h

def tcard(r):
    w = r["w"]; tag = pill("Agreed", "good") if r["status"] == "AGREED" else pill("Contested", "watch")
    rep = re.search(r"(Reports \d{4}-\d{2}-\d{2}[^.]*\.)", w["sector_note"])
    g = SRM.get(r["sector"], {})
    buy = f"{f2(r['entry'])}" + (f" on {r['vol']}x volume" if r["vol"] else "")
    kv = [("Buy line, hourly close", buy), ("Stop", f"{f2(r['stop'])}"), ("Risk", f"{r['risk']:.2f} ({r['risk_pct']:.1f}%{risk_atr(r)})"),
          (f"1R ${ONE_R}", f"{r['shares']} shares"), ("Target 1", f"{f2(r['ladder'][0][1])} &middot; {r['ladder'][0][0]}R"),
          ("Target 2", f"{f2(r['ladder'][1][1])} &middot; {r['ladder'][1][0]}R"), ("Dead if daily close under", f2(r["dead"]) if r["dead"] is not None else "&mdash;"), ("Last close", f"{r['last']}")]
    return (f'<div class="card tcard"><div class="row"><span class="tk">{r["t"]}</span>{tag}{ma_pill(ROWS.get(r["t"]))}{mom_pill(r["t"])}<span class="tag">conviction {r["conv"]}/5 &middot; {E(r["sector"])}, gate {g.get("entry_gate","")}'
            + (f" &middot; {E(rep.group(1)).rstrip('.')}" if rep else "") + '</span></div>'
            + '<div class="kv">' + "".join(f"<div><span class='lab'>{a}</span><b>{b}</b></div>" for a, b in kv) + "</div>"
            + extras(r["t"]) + ma_line(ROWS.get(r["t"])) + f'<p><b>Wait for:</b> {E(w["reason"]["wait_for"])}</p><p><b>Why:</b> {E(w["reason"]["agree"])}</p><p><b>Wrong if:</b> {E(w["reason"]["wrong_if"])}</p>' + ext_line(ROWS.get(r["t"])) + '</div>')

_tcard_numbers = tcard
def tcard(r):
    """Template card first; the writer's numbers (buy line, 1R shares, targets) stay folded beneath it."""
    h = tmpl_card(r["t"])
    assert h.endswith("</div>")
    return h[:-6] + f'<details class="big"><summary>Writer&rsquo;s numbers and 1R shares</summary>{_tcard_numbers(r)}</details></div>'

def supp_ctx(t):
    """A supplemental-pass name (PM 2026-11-05): the room did not vote it in THIS run, so everything comes from its live levels row
    (origin_run <date>-r3), the brackets file / its export bracket, and the writer's lines."""
    row = ROWS.get(t) or {}
    lvr = LV[t]
    cls = lvr.get("class")
    verdict = {"ADVANCE": "ADVANCE", "HOLD_FOR_CONDITIONS": "HOLD-FOR-CONDITIONS"}.get(cls, "PASS")
    res = str(lvr.get("committee_result") or "")
    cons = {"ticker": t, "verdict": verdict, "status": lvr.get("committee_status"), "lane": lvr.get("lane"),
            "objections": lvr.get("committee_objections") or []}
    return {"ticker": t, "cons": cons, "pos": None, "lv": lvr, "br": BRK.get(t), "row": row, "srm": SRM.get(row.get("gics_sector_name")),
            "mtf": MTF.get(t), "cx": CX, "held": t in HELD, "mark": None, "mark_plain": None, "lane": lvr.get("lane"), "slate_ticket": None,
            "no_timing_reason": "the supplemental pass has no timing read on file",
            "market_kill": (mk_plain.split(": ", 1)[1] if ": " in mk_plain else mk_plain) if mk_plain else None,
            "on_lists": ON_LISTS.get(t), "lines": CL.get(t), "supplemental": True, "committee_result": res or None,
            "cut_reason": res[len("not slated: "):] if res.startswith("not slated: ") else None}

SUPP = sorted([t for t, r in LV.items() if r.get("supplemental") and t not in CONS_BY],
              key=lambda t: ({"ADVANCE": 0, "HOLD_FOR_CONDITIONS": 1}.get(LV[t].get("class"), 2), t))
supp_section = ""
if SUPP:
    _sorigin = next((LV[t].get("origin_run") for t in SUPP if LV[t].get("origin_run")), "")
    _n_adv = sum(1 for t in SUPP if LV[t].get("class") == "ADVANCE")
    supp_section = (f'<div class="card"><h3>Supplemental committee pass (contested): {len(SUPP)} more names sitting at their swing high</h3>'
                    f'<p>A second committee pass, run after the live run (run {E(str(_sorigin))}), on names whose weekly and daily swings both make higher highs and higher lows '
                    f'and whose last close is within one daily range of the daily swing high. {_n_adv} came out ADVANCE, contested: the room did not agree, so none is an agreed pick. '
                    f'The levels are the live alert levels.</p></div><div class="stack">'
                    + "".join(_tmpl_from(supp_ctx(t)) for t in SUPP) + "</div>")

def thin_li(r):
    w = r["w"]; tag = pill("Agreed", "good") if r["status"] == "AGREED" else pill("Contested", "watch")
    near = ", ".join(f"{f2(tp)} ({mins(f'{rv}')}R)" for rv, tp in r["near"])
    why = (f"only target 1 reaches 1R: {f2(r['ladder'][0][1])} at {r['ladder'][0][0]}R" if r["ladder"] else "no level reaches 1R")
    return (f'<li><div class="row"><span class="tk">{r["t"]}</span>{tag}{ma_pill(ROWS.get(r["t"]))}{mom_pill(r["t"])}<span class="tag">buy line {f2(r["entry"])}' + (f" on {r['vol']}x volume" if r["vol"] else "")
            + f' &middot; stop {f2(r["stop"])} &middot; 1R ${ONE_R} = {r["shares"]} shares</span></div>'
            + f'<p><b>{why[0].upper()+why[1:]}.</b> Nearer levels are resistance to trade through, not targets: {near}.</p>' + extras(r["t"]) + '</li>')

_secs = collections.Counter(trade[t]["sector"] for t in ADV if trade[t].get("sector"))
_top2 = _secs.most_common(2)
_pwd = pw_dist if "pw_dist" in globals() else None
if len(ADV) >= 3 and _top2 and sum(c for _, c in _top2) >= 0.6 * len(ADV) and _top2[0][1] >= 2:
    common = (f'<p class="flag">{_cap1(nword(sum(c for _, c in _top2)).lower())} of the {nword(len(ADV)).lower()} sit in {nword(len(_top2)).lower()} sector{"s" if len(_top2) > 1 else ""}: '
              + " and ".join(f"{E(sec)} (" + ", ".join(t for t in ADV if trade[t]["sector"] == sec) + ")" for sec, _ in _top2) + "."
              + (f" SPY is only {abs(pw_dist)}% {'above' if pw_dist < 0 else 'under'} the {kl('SPY put wall')['level']:g} put wall, so a break there hits every trigger together.</p>" if pw_dist < 0 else "</p>"))
else:
    common = ""
void = (f'<p class="flag watch"><b>Void every new trigger if</b> the index is under distribution: {E(mk_plain.split(": ",1)[1] if ": " in mk_plain else mk_plain)}.</p>' if mk_plain else "")

holds = sorted(BYV["HOLD-FOR-CONDITIONS"], key=lambda c: c["ticker"])
def hold_row(t):
    cd = CD["hold"][t]; tr = cd["triggers"]
    buy = next(x for x in tr if x["kind"] == "close_above")
    wa = next((x for x in tr if x["kind"] == "trade_below" and "wait area" in x["action"]), None)
    zone = re.search(r"wait area ([\d.]+-[\d.]+)", wa["action"]).group(1).rstrip(".").replace("-", " to ") if wa else ("held: add question only" if t in HELD else "&mdash;")
    dead = next((f"daily close under {x['level']}" for x in tr if x["kind"] == "close_below"), cd.get("kills", "&mdash;"))
    return [f"<b>{t}</b>{ma_pill(ROWS.get(t))}{mom_pill(t)}", f"#{ROWS.get(t, {}).get('rank', '&mdash;')}", zone, f"{buy['level']}" + (f" on {buy['volume_min_x']}x volume" if buy.get("volume_min_x") else ""), E(dead), extras(t)]
hold_tmpl = (f'<details class="big"><summary>The {len(holds)} hold cards, same template</summary><div class="stack">' + "".join(tmpl_card(c["ticker"]) for c in holds) + "</div></details>") if holds else ""
hold_card = card(f"{len(holds)} names wait for a condition first; nothing to do until it prints.",
    table(["Name", "AQE rank", "Pull back into", "Then an hourly close above", "Dead if", "Trend frames and U&R"], [hold_row(c["ticker"]) for c in holds]),
    "For a held name the line is an add question only.",
    ("Why each one waits", "<ul class='plainlist'>" + "".join(f"<li><b>{c['ticker']}</b>: {E(plain(T['holds'][c['ticker']]))}</li>" for c in holds) + "</ul>"))

_dp = sorted([c for c in BYV["PASS"] if c.get("status") == "DEAL_PINNED"], key=lambda c: c["ticker"])
passes = sorted([c for c in BYV["PASS"] if c.get("status") != "DEAL_PINNED"], key=lambda c: c["ticker"])
deal_pinned_html = ("" if not _dp else '<div class="card"><h3>Deal-pinned, not a momentum pick</h3><p>Off the buy list by rule (R44). A stock with a pending takeover trades on the deal spread, '
    'not on momentum, so flow, energy and structure mean little. No buy trigger is armed for these names.</p>'
    + table(["Name", "Sector", "Last close", "The deal", "Committee"],
            [[f"<b>{c['ticker']}</b>{ma_pill(ROWS.get(c['ticker']))}", E(str(ROWS.get(c['ticker'], {}).get("gics_sector_name") or "")), f2(ROWS[c['ticker']]["entry"]) if (ROWS.get(c['ticker']) or {}).get("entry") else "&mdash;",
              E(str((c.get("deal_pinned") or {}).get("ma_note") or (ROWS.get(c['ticker']) or {}).get("ma_note") or "pending acquisition")),
              f"had it as {'ADVANCE' if c.get('slate_verdict') == 'ADVANCE' else 'WATCH' if c.get('slate_verdict') == 'WATCH' else 'a slate name'}; excluded"] for c in _dp]) + "</div>")
pass_tmpl = (f'<details class="big"><summary>The {len(passes) + len(_dp)} rejected names, same template: why each was passed</summary><div class="stack">'
             + "".join(tmpl_card(c["ticker"]) for c in passes + _dp) + "</div></details>") if (passes or _dp) else ""
pass_det = (f'<details class="big"><summary>{len(passes)} names are passed today: {sum(1 for c in passes if c["status"]=="DROPPED")} dropped on objections, the rest not slated</summary>'
            + table(["Name", "Why not"], [[f"<b>{c['ticker']}</b>", E(plain(T["passes"][c["ticker"]]))] for c in passes]) + "</details>") + pass_tmpl
info = P4.get("informational") or []
lists = lambda x: " + ".join(n for n, k in (("Longlist", "on_longlist"), ("Elder", "on_elder")) if x.get(k)) or "&mdash;"
lr = D["lens_ranking"]["ranked"][:10]
def room(t):
    c = CONS_BY.get(t)
    return "not voted" if not c else {"ADVANCE": "advance", "HOLD-FOR-CONDITIONS": "hold", "PASS": "pass"}[c["verdict"]] + {"AGREED": ", agreed", "CONTESTED": ", contested", "DROPPED": ", dropped", "NOT_SLATED": ", not slated", "DEAL_PINNED": ", deal-pinned"}.get(c.get("status"), "")
top20 = sorted([r for r in D["daily_list"] if isinstance(r.get("rank"), int)], key=lambda r: r["rank"])[:20]
def sstate(r):
    x = SRM.get(r.get("gics_sector_name")) or {}
    return {"lead": "leading", "turn": "turning"}.get(gkind(x.get("grade"), x.get("rrg_quadrant")), f"{x.get('grade','')} {str(x.get('rrg_quadrant','')).lower()}")
strong_det = ('<details class="big"><summary>Strong names no reviewer picked, the Detect-lens top 10 and the AQE top 20</summary>'
    + f"<p>Seated for strength today, no reviewer nominated them: {', '.join(x['ticker'] for x in P4['strong_seats'])}. "
      f"Seated on a reclaim day: {', '.join(x['ticker'] for x in P4['unr_seats'])}. Their verdicts are above.</p>"
    + table(["Next strongest, not voted", "Lead over SPY, 20 days", "Momentum score", "Lists", "Reclaim day", "Above 20-day avg, daily ranges", "From breakout"],
            [[f"<b>{x['ticker']}</b>", mins(f"{x['rs_spy_20d']:+.1f}"), f"{x['sc_momentum']:.0f}", lists(x), "yes" if x.get("unr_status") == "MET" else "&mdash;",
              f"{x['extension_atr_20']:.1f}", mins(f"{x['pct_from_pivot']:+.1f}%")] for x in info])
    + "<p>Add any of these by hand as a PM pick if you want the committee to vote it.</p>"
    + table(["Detect lens #", "Name", "Strong lenses", "Warnings", "Committee"], [[x["rank"], f"<b>{x['ticker']}</b>", x["positive"], x["warnings"], room(x["ticker"])] for x in lr])
    + table(["AQE #", "Name", "Sector", "Sector state", "Committee"], [[r["rank"], f"<b>{r['ticker']}</b>", E(r.get("gics_sector_name") or ""), sstate(r), room(r["ticker"])] for r in top20])
    + "<p>The lens list and the AQE rank are AQE&rsquo;s own orderings; neither overrides the committee, and the committee does not override them.</p></details>")

s5 = section("5 &middot; The tickers", (f"{len(usable)} of the {n_adv} ADVANCE names pay 1R or more at two targets; {' and '.join(r['t'] for r in thin)} do not." if thin else
                                           f"All {n_adv} ADVANCE names pay 1R or more at two targets." if n_adv else "No name is ADVANCE today."),
    chg_html + void + reward + '<div class="stack">' + "".join(tcard(r) for r in usable) + "</div>"
    + (f'<div class="card"><h3>Reward too thin at the buy line: {" and ".join(r["t"] for r in thin)}</h3><ul class="thin">{"".join(thin_li(r) for r in thin)}</ul></div>'
       + "".join(tmpl_card(r["t"]) for r in thin) if thin else "")
    + common + hold_card + hold_tmpl + deal_pinned_html + pass_det + supp_section + strong_det, "tickers")

# ------------------------------------------------------------------ 5b THE THREE AQE LISTS AGAINST THE COMMITTEE (lists_vs_committee.py, code only)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lists_vs_committee as LVC
_t5b = time.perf_counter()
F = LVC.build(RUN)
F_RUNTIME = time.perf_counter() - _t5b
FL, FU, FC, FO = F["lists"], F["union"], F["committee"], F["objections"]
OC_COL = {"ADVANCE": "var(--clay)", "HOLD": "var(--watch-solid)", "PASS": "var(--bar)", "OUT": "var(--soft)"}
OC_WORD = {"ADVANCE": "advance", "HOLD": "hold", "PASS": "passed in the room", "OUT": "never in the room"}
TG_COL = {"BREAKING OUT": "var(--t-brk)", "COILING": "var(--t-coil)", "PULLBACK": "var(--clay)", "EXTENDED": "var(--t-ext)", "OTHER": "var(--soft)"}
TG_WORD = {"BREAKING OUT": "breaking out", "COILING": "coiling", "PULLBACK": "pullback", "EXTENDED": "extended", "OTHER": "other"}
LKEYS = ("elder", "aqe", "lens")
LNAME = {"elder": "Elder top 15", "aqe": "AQE top 20", "lens": "Detect lens top 15"}

def stack(rows, label):
    """Stacked horizontal bars, label line above each bar. rows: (left html, right html, [(count, colour)])."""
    s = [f'<div class="bars stk" role="img" aria-label="{E(label)}">']
    for lt, rt, segs in rows:
        tot = sum(v for v, _ in segs) or 1
        x, rects = 0.0, []
        for v, col in segs:
            if v:
                w = 100 * v / tot
                rects.append(f'<rect x="{x:.2f}%" y="1" width="{w:.2f}%" height="14" fill="{col}" stroke="var(--card)" stroke-width="1.5"/>')
                x += w
        s.append(f'<div class="br"><div class="bl"><span>{lt}</span><b>{rt}</b></div>'
                 f'<svg class="viz" width="100%" height="16" aria-hidden="true"><rect x="0" y="1" width="100%" height="14" fill="var(--soft)" stroke="var(--line)"/>{"".join(rects)}</svg></div>')
    s.append("</div>")
    return "".join(s)

def legend(items):
    return '<div class="legend">' + "".join(f'<span><i style="background:{c};border:1px solid var(--line)"></i>{E(w)}</span>' for w, c in items) + "</div>"

def counts_line(d, order, words):
    return " &middot; ".join(f"{d[k]} {words[k]}" for k in order if d.get(k))

# A. how each list ended up
rowsA = [(f"<b>{LNAME[k]}</b>", counts_line(FL[k]["outcomes"], LVC.OUTCOMES, OC_WORD), [(FL[k]["outcomes"][o], OC_COL[o]) for o in LVC.OUTCOMES]) for k in LKEYS]
rowsA.append((f"<b>All three, {FU['n']} different names</b>", counts_line(FU["outcomes"], LVC.OUTCOMES, OC_WORD), [(FU["outcomes"][o], OC_COL[o]) for o in LVC.OUTCOMES]))
agree = {k: FL[k]["outcomes"]["ADVANCE"] + FL[k]["outcomes"]["HOLD"] for k in LKEYS}
size = {k: len(FL[k]["rows"]) for k in LKEYS}
hi_k = max(LKEYS, key=lambda k: agree[k] / size[k]); lo_k = min(LKEYS, key=lambda k: agree[k] / size[k])
mid_k = next(k for k in LKEYS if k not in (hi_k, lo_k))
sb = {k: FL[k]["sector_buckets"] for k in LKEYS}
n_adv_u = FU["outcomes"]["ADVANCE"]
cardA = card(f"{FU['outcomes']['OUT']} of the {FU['n']} names on AQE&rsquo;s three lists never reached the room; the committee advanced {n_adv_u}.",
    stack(rowsA, "How each AQE list ended up at the committee")
    + legend([("Advance", OC_COL["ADVANCE"]), ("Hold for conditions", OC_COL["HOLD"]), ("Passed in the room (not slated or dropped)", OC_COL["PASS"]), ("Never in the room", OC_COL["OUT"])]),
    f"The committee agrees most with the <b>{LNAME[hi_k]}</b> ({agree[hi_k]} of {size[hi_k]} advanced or held) and least with the <b>{LNAME[lo_k]}</b> ({agree[lo_k]} of {size[lo_k]}); "
    f"the {LNAME[mid_k]} has {agree[mid_k]} of {size[mid_k]}. <b>Sectors:</b> " + ", ".join(f"{sb[k]['DEPLOY']} of {size[k]} {LNAME[k].split(' top')[0]}" for k in LKEYS)
    + f" names sit in DEPLOY (leading) sectors; {' / '.join(str(sb[k]['TURNING_BLOCKED']) for k in LKEYS)} in TURNING sectors gated BLOCKED.",
    ("How a name reaches the room", f"<p>A name is voted only if a voice nominates it, it is held, or it takes one of the {len(F['room']['strength_seats'])} strength seats "
     f"({', '.join(F['room']['strength_seats'])}) or {len(F['room']['reclaim_seats'])} reclaim-day seats ({', '.join(F['room']['reclaim_seats'])}). "
     f"AQE&rsquo;s entry doors flagged {FU['out_flagged']} of the {FU['out_n']} names that never reached the room; by the room&rsquo;s own rule a door flags a name for you and never seats it. "
     f"&ldquo;In the room&rdquo; means the name has a committee record today ({F['room']['n']} names), the same test the real page uses.</p>"))

# C/D. the setup mix: the committee's picks against the lists
def mix_row(lab, d, n):
    return (f"<b>{lab}</b>", counts_line(d, LVC.TAGS, TG_WORD), [(d[t], TG_COL[t]) for t in LVC.TAGS])
rowsD = [mix_row(f"Committee advance, {len(FC['advance'])} names", FC["advance_tags"], len(FC["advance"])),
         mix_row(f"Committee hold, {len(FC['hold'])} names", FC["hold_tags"], len(FC["hold"]))] + [mix_row(LNAME[k], FL[k]["tags"], size[k]) for k in LKEYS]
at, ht = FC["advance_tags"], FC["hold_tags"]
lanes = FC["advance_lanes"]; trg = FC["advance_triggers"]
trg_words = {"h1_close_above:bar_high": "above yesterday&rsquo;s high", "h1_close_above:pivot_high": "above the last pivot high"}
trg_names = {w: [x["ticker"] for x in FC["advance"] if x["trigger_word"] == w] for w in trg}
trg_txt = " and ".join(f"{n} {trg_words.get(w) or E(cond_plain(w))}" + (f" ({', '.join(trg_names[w])})" if n <= 2 else "") for w, n in sorted(trg.items(), key=lambda kv: -kv[1]))
trg_txt = no_raw_words(trg_txt)
ext_l = {k: FL[k]["tags"]["EXTENDED"] for k in LKEYS}
_nA = len(FC["advance"])
_dom = max(LVC.TAGS, key=lambda t: at.get(t, 0)) if _nA else None
_ext_lists = [LNAME[k].split(" top")[0] for k in LKEYS if size[k] and FL[k]["tags"]["EXTENDED"] > size[k] / 2]
_titleD = ("No names are advanced today." if not _nA else
           (f"The {_nA} advance names are mostly {TG_WORD[_dom]} ({at[_dom]})" + (f", not pulling back ({at['PULLBACK']})" if _dom != "PULLBACK" else "") if at[_dom] > _nA / 2 else
            f"The {_nA} advance names are split: " + ", ".join(f"{at[t]} {TG_WORD[t]}" for t in LVC.TAGS if at.get(t)))
           + (f"; the {_jn2(_ext_lists)} list{'s are' if len(_ext_lists) > 1 else ' is'} mostly extended." if _ext_lists else "."))
_trg_all = (f"All {_nA} triggers are an hourly close above a prior high: {trg_txt}." if FC.get("all_hourly_close_above") else f"The triggers are: {trg_txt}.")
cardD = card(_titleD,
    stack(rowsD, "Setup type mix, committee picks against the three lists")
    + legend([(LVC.TAG_WORD[t], TG_COL[t]) for t in LVC.TAGS if t != "OTHER"]),
    f"The room&rsquo;s &ldquo;pullback&rdquo; lane holds {lanes.get('PULLBACK', 0)} of the {len(FC['advance'])} advance names, but it only means no AQE strength door opened; "
    f"{FC['advance_reclaim_flag']} carry a reclaim-day flag. {_trg_all}",
    ("How each name is tagged", "<p>The first rule that applies wins. Every input is a stored field of the daily export; nothing is fitted.</p><ul class='plainlist'>"
     f"<li><b>Extended:</b> more than {LVC.CHASE_PIVOT_PCT:g}% past its pivot (the committee&rsquo;s own line: &ldquo;a late buy past the pivot +5%&rdquo;, first filed on SN, 4 Nov 2026), or more than {LVC.CHASE_200D_PCT:g}% above its 200-day "
     f"(the committee&rsquo;s own line: &ldquo;more than 70% above the 200-day&rdquo;, first filed on HNGE, 4 Nov 2026), or more than {LVC.STRETCH_MAX_RANGES:g} daily ranges above its 20-day average (AQE tag rule, not a committee rule).</li>"
     f"<li><b>Breaking out:</b> at or up to {LVC.CHASE_PIVOT_PCT:g}% past its last pivot high.</li>"
     f"<li><b>Coiling:</b> below its pivot, within {LVC.COIL_NEAR_HIGH_PCT:g}% of its 20-bar high (AQE tag rule), and tight: in a squeeze, the narrowest bar in 4 or 7 days, or AQE&rsquo;s coil reading strong.</li>"
     "<li><b>Pullback / support bounce:</b> below its pivot and holding support: a reclaim-day (undercut and rally) flag, a rising 20-day average under price, or the 50-day average under price.</li>"
     "<li><b>Other:</b> none of the above.</li></ul>"
     f"<p>A reclaim-day flag on a name that is breaking out keeps the breakout tag; the flag is counted on its own. Volume is not a tag input; the committee&rsquo;s {LVC.VOLUME_LINE_X:g}x line shows in the tables.</p>"))

# E. what the committee's rules reward
th = FO["themes"]
rowsE = [(E(x["label"]), f"{x['n_objections']} objections &middot; {len(x['names'])} names", x["n_objections"],
          CLAY if x["key"] in ("dip_ticket", "no_wait", "wants_pullback") else GRAY) for x in th]
thk = {x["key"]: x for x in th}
to_break = thk["dip_ticket"]["n_objections"] + thk["no_wait"]["n_objections"]
to_pull = thk["wants_pullback"]["n_objections"]
quotes = "<ul class='plainlist'>" + "".join(
    f"<li><b>{E(x['label'])}</b> ({x['n_objections']}): " + (f"&ldquo;{E(x['quote'])}&rdquo; (filed on {x['quote_ticker']})" if x["quote"] else
        ("no objection filed." if not x["n_objections"] else "every filed sentence leans on indicator shorthand, so none is quoted.")) + f" Names: {', '.join(x['names']) or 'none'}.</li>" for x in th) + "</ul>"
_top2E = [x for x in th if x["n_objections"]][:2]
_THEME_SHORT = {"volume": "a volume test", "dip_ticket": "dip-and-reclaim tickets", "no_wait": "waiting for a pull-in", "chasing": "chasing past the line", "wants_pullback": "buying the break",
                "base": "a missing base", "trend": "unconfirmed trend", "profit_taking": "last-bar selling", "sector": "a blocked sector"}
_vb = lambda x: {"volume": "ask for", "dip_ticket": "reject", "no_wait": "reject", "chasing": "flag", "wants_pullback": "push back on", "base": "flag", "trend": "flag",
                 "profit_taking": "flag", "sector": "flag"}.get(x["key"], "raise")
cardE = card((f"The most filed objections {' and '.join(f'{_vb(x)} {_THEME_SHORT.get(x['key'], E(x['label'].lower()))} ({x['n_objections']})' for x in _top2E)}; {to_pull} want a pullback first." if _top2E else "No objection was filed on a slated name."),
    hbars(rowsE, 0, max(x["n_objections"] for x in th), "Objection themes across the slated names"),
    f"Across {FO['n_slated']} slated names and {FO['n_objections']} objections, {to_break} push toward buying the break and {to_pull} toward waiting for a pullback, "
    f"and {len(FO['dropped_dip_tickets'])} of the {FO['n_dropped']} dropped names ({', '.join(FO['dropped_dip_tickets'])}) were dip-and-reclaim tickets. "
    f"So the filed rules {'favour a break near the pivot' if to_break > to_pull else 'favour waiting for a pullback' if to_pull > to_break else 'are split between a break and a pullback'}.",
    ("One filed sentence per theme, and the keyword rules", quotes
     + "<p>Each objection is matched against every theme&rsquo;s keywords, so one objection can count in several themes. Clay bars are the three themes about where to buy: the break or the pullback. "
       "Quotes are whole sentences, rule codes removed and field names put in plain words with the real page&rsquo;s own table.</p>"))

# B. the three lists
def sec_cell(x):
    s_ = x["sector"]
    st = f"{(s_['grade'] or '').title()} &middot; {str(s_['quadrant'] or '').lower()}" + (", gate blocked" if s_["gate"] == "BLOCKED" else "")
    return f"{E(SHORT.get(s_['sector'], s_['sector'] or '&mdash;'))}<span class='sub'>{st}</span>"
def theme_cell(x):
    t_ = x["theme"]
    if not t_:
        return "&mdash;"
    wm = " ".join(f"{lab} {mins(f'{v:+.1f}')}%" for lab, v in (("wk", t_["week"]), ("mo", t_["month"])) if isinstance(v, (int, float)))
    return f"{E(t_['name'])}<span class='sub'>{(t_['grade'] or '').title()} &middot; {str(t_['quadrant'] or '').lower()}" + (f" &middot; {wm}" if wm else "") + "</span>"
def tag_cell(x):
    return (f"<span class='tg'><i style='background:{TG_COL[x['tag']]}'></i>{LVC.TAG_WORD[x['tag']]}</span>"
            + ("" if x.get("tag_note_repeats_reason") else f"<span class='sub'>{E(x['tag_fired'][0])}</span>") + ("<span class='sub'>+ reclaim-day flag</span>" if x["reclaim_flag"] else ""))
OC_PILL = {"ADVANCE": ("Advance", "good"), "HOLD": ("Hold", "watch"), "PASS": ("Passed", ""), "OUT": ("Not in the room", "out")}
OC_PILL_STATUS = {"DEAL_PINNED": ("Deal-pinned", "bad")}
def oc_cell(x):
    w, tone = OC_PILL[x["outcome"]]
    if x["status"] == "DEAL_PINNED":
        w, tone = OC_PILL_STATUS["DEAL_PINNED"]
    sub = {"DROPPED": "dropped", "NOT_SLATED": "not slated", "CONTESTED": "contested", "AGREED": "agreed", "DEAL_PINNED": "pending takeover"}.get(x["status"], "")
    return pill(w, tone) + (f"<span class='sub'>{sub}</span>" if sub else "")
fx = lambda v, f: f.format(v) if isinstance(v, (int, float)) else "&mdash;"
HEAD = ["#", "Name", "Sector", "Theme basket", "Setup", "Over 20-day (ranges)", "Under 20-bar high", "Volume vs avg", "Committee", "Reason"]
def list_table(k):
    body = []
    for x in FL[k]["rows"]:
        cells = [x["n"], f"<span class='ph'>#{x['n']} </span><b>{x['ticker']}</b>{ma_pill(ROWS.get(x['ticker']))}", sec_cell(x), theme_cell(x), tag_cell(x), fx(x["stretch"], "{:.1f}"), fx(x["under_hi20"], "{:.1f}%"),
                 fx(x["volume"], "{:.2f}x"), oc_cell(x), E(x["reason"])]
        body.append("<tr>" + "".join(f'<td data-l="{E(h)}">{c}</td>' for h, c in zip(HEAD, cells)) + "</tr>")
    return ('<div class="tbl"><table class="lst"><thead><tr>' + "".join(f"<th>{h}</th>" for h in HEAD) + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")
LH3 = {
    "elder": f"Elder top 15, by Elder score then AQE rank: {FL['elder']['tags']['EXTENDED']} are extended, and {FL['elder']['outcomes']['OUT']} never reached the room.",
    "aqe": f"AQE top 20, by AQE rank: {FL['aqe']['tags']['EXTENDED']} are extended, and {FL['aqe']['outcomes']['OUT']} never reached the room.",
    "lens": f"Detect lens top 15, by strong-lens count: {FL['lens']['tags']['BREAKING OUT']} are breaking out, and {FL['lens']['outcomes']['OUT']} never reached the room.",
}
cardsB = "".join(f'<div class="card"><h3>{LH3[k]}</h3>{list_table(k)}</div>' for k in LKEYS)
if "swing" in FL:      # PM 2026-11-05: the fourth brief list, shown beside the other three; the three-list comparisons above are unchanged
    _sw = FL["swing"]
    cardsB += (f'<div class="card"><h3>Swing pivot top {len(_sw["rows"])}: weekly and daily higher highs and higher lows, sitting within one daily range of the latest daily swing high: '
               f'{_sw["outcomes"]["ADVANCE"] + _sw["outcomes"]["HOLD"]} advance or hold, and {_sw["outcomes"]["OUT"]} never reached the room.</h3>{list_table("swing")}</div>')

built = ("How this is built", f"<p>Built by code, with <b>zero model calls</b> at run time: a small script reads the run folder&rsquo;s export, committee record, "
         f"card words and door log, tags each name and counts; this page only draws the result. It took {F['runtime_s']:.2f} seconds. "
         "The Elder, AQE and Detect lists and the &ldquo;in the room&rdquo; test are the real page&rsquo;s own definitions. The reason column is the committee&rsquo;s filed line for voted names; "
         "for the rest it is the first stored fact that applies, in this order: past the pivot line, past the 200-day line, a blocked sector, volume under 1.4x, more than 4 daily ranges over the 20-day. "
         "This is a diagnostic: it ranks and recommends nothing.</p>")
s5b = section("5b &middot; The three AQE lists against the committee",
    f"The room took {FU['n'] - FU['outcomes']['OUT']} of the {FU['n']} list names; {FU['tag_by_outcome']['EXTENDED']['OUT']} of the {FU['outcomes']['OUT']} it never saw are extended past its own chase lines.",
    cardA + f'<div class="grid">{cardD}{cardE}</div>' + cardsB + f'<details class="big"><summary>{built[0]}</summary>{built[1]}</details>', "lists")
# ------------------------------------------------------------------ 6 THE PLAN
steps = []
for x in T.get("plan") or []:
    head, body = x.split(": ", 1) if ": " in x else ("", x)
    steps.append(f'<li><span class="when">{E(head)}</span><span>{E(body[0].upper() + body[1:])}</span></li>')
s6 = section("6 &middot; The plan, Singapore time", f"Nothing can fire before the first hourly close at {FIRST_HOUR_SGT:%H:%M} SGT.",
             f'<div class="card"><ul class="timeline">{"".join(steps)}</ul></div>', "plan")

# ------------------------------------------------------------------ 7 SCORECARD
def md_table(title):
    blk = SCMD.split(title, 1)[1].split("\n## ", 1)[0]
    ls = [l for l in blk.splitlines() if l.startswith("|")]
    return [[c.strip() for c in l.strip("|").split("|")] for l in ls if not set(l) <= set("|-: ")]
full = md_table("## 3 · Full-horizon calls only"); runs = md_table("## 1 · The list vs the market")
sc_rows = [(f"{r[0]} &middot; {r[5].split('/')[0]} of {r[5].split('/')[1]} beat SPY", f"mean {mins(r[2])}", yv(r[2]), CLAY if r[0] == "Advance" else GRAY) for r in full[1:]]
_adv_m = next((yv(r[2]) for r in full[1:] if r[0] == "Advance"), None); _hold_m = next((yv(r[2]) for r in full[1:] if r[0].lower().startswith("hold")), None)
s7 = section("7 &middot; Scorecard", ("ADVANCE calls have not yet beaten HOLD calls over full five-session horizons." if (_adv_m is not None and _hold_m is not None and _adv_m <= _hold_m) else
                                    "ADVANCE calls have beaten HOLD calls over full five-session horizons." if (_adv_m is not None and _hold_m is not None) else
                                    "The scorecard does not yet compare ADVANCE and HOLD calls over full five-session horizons."),
    card(f"Mean return of each kind of call over full five-session horizons, as of the {CLOSE_S} close",
         hbars(sc_rows, min(r[2] for r in sc_rows), max(r[2] for r in sc_rows), "Mean return by verdict"),
         f"Yesterday&rsquo;s one-session list returned {mins(y_list)} against SPY {y_spy}. The scorecard is information and changes no verdict.",
         ("Every run, list against SPY", table(runs[0], [[mins(c) for c in r] for r in runs[1:]]))), "scorecard")

# ------------------------------------------------------------------ 8 READ WITH CARE
# engineering notes (rule codes, commit ids, QA-hold lists, step names) are left out; everything the PM needs to weigh the run stays
_ENG = re.compile(r"\bR\d{2}\b|\b[0-9a-f]{7}\b|\bRATIONALE-FINAL\b|\bQA review\b")
cav = [plain(c) for c in T.get("caveats") or [] if not _ENG.search(c)]
_n_stale = (1 if _stale_b else 0) + (1 if (CR.get("how_current") or {}).get("oldest_source_days_behind", 0) else 0)
s8 = section("8 &middot; Read with care", ("This is a rerun on frozen votes" if RERUN else "This is the live run")
             + (f", and {nword(_n_stale).lower()} data leg{' was' if _n_stale == 1 else 's were'} stale when the committee met." if _n_stale else ", and every data leg was current when the committee met."),
    f'<details class="big"><summary>{len(cav)} caveats on the run, the data, the book and the sizing</summary><ul class="plainlist">{"".join(f"<li>{E(x)}</li>" for x in cav)}</ul>'
    f'<p>{E(MARK["committee_data_status"])}. {E(MARK["ma_panel_refresh"])}.</p></details>'
    f'<details class="big"><summary>{refresh_more[0]}</summary>{refresh_more[1]}</details>'
    + (f'<details class="big"><summary>Which of the three reports is beating the market</summary><ul class="plainlist">{"".join(f"<li>{E(plain(_RL[k]))}</li>" for k in ("A", "B", "C") if _RL.get(k))}</ul></details>' if any(_RL.get(k) for k in ("A", "B", "C")) else ""), "care")

# ------------------------------------------------------------------ page
CSS = """
:root{--bg:#fff;--soft:#f3f3f1;--card:#fff;--text:rgba(0,0,0,.9);--text-2:rgba(0,0,0,.6);--text-3:rgba(0,0,0,.47);--line:rgba(0,0,0,.12);--shadow:0 4px 20px rgba(0,0,0,.075);--clay:#d97757;--clay-strong:#c6613f;--bar:#bdbdbd;--good:#006c10;--good-bg:rgba(16,161,34,.14);--bad:#a42528;--bad-bg:rgba(220,60,61,.12);--watch:#794c02;--watch-bg:rgba(251,179,21,.16);--serif:Georgia,"Times New Roman",serif;--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151515;--soft:#262626;--card:#1f1f1f;--text:rgba(255,255,255,.93);--text-2:rgba(255,255,255,.57);--text-3:rgba(255,255,255,.4);--line:rgba(255,255,255,.12);--shadow:none;--bar:#5c5c5c;--good:#53c556;--bad:#f17778;--watch:#e49c06;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#151515;--soft:#262626;--card:#1f1f1f;--text:rgba(255,255,255,.93);--text-2:rgba(255,255,255,.57);--text-3:rgba(255,255,255,.4);--line:rgba(255,255,255,.12);--shadow:none;--bar:#5c5c5c;--good:#53c556;--bad:#f17778;--watch:#e49c06;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 var(--sans)}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px 56px}
h1,h2{font-family:var(--serif);font-weight:400;margin:0;text-wrap:balance}
h1{font-size:32px;line-height:1.2;margin-top:18px}
h2{font-size:22px;line-height:1.3;margin:0 0 14px}
h3{font-size:16px;font-weight:600;margin:0;line-height:1.4}
p{margin:0}
section{margin-top:44px}
.kicker{font-size:13px;color:var(--clay-strong);font-weight:600;margin-bottom:4px}
.meta{font-size:13px;color:var(--text-2);border-bottom:1px solid var(--line);padding:12px 0}
.ask{font-size:22px;line-height:1.35;margin:16px 0 10px;border-left:4px solid var(--clay);padding-left:14px}
.fresh{font-size:13px;color:var(--text-2);margin:0 0 16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:12px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:20px;min-width:0}
.tile{display:flex;flex-direction:column;gap:6px}
.card{display:flex;flex-direction:column;gap:10px}
.num{font-size:40px;font-weight:500;line-height:1;white-space:nowrap}
.tag{font-size:13px;color:var(--text-2)}
.reasons{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px;margin-top:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:14px;align-items:start}
.stack{display:flex;flex-direction:column;gap:14px;margin-top:14px}
section>.card,section>details,section>.flag{margin-top:14px}
.read{color:var(--text)}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:500;background:var(--soft);white-space:nowrap}
.good{color:var(--good);background:var(--good-bg)}.bad{color:var(--bad);background:var(--bad-bg)}.watch{color:var(--watch);background:var(--watch-bg)}
.viz{display:block;overflow:visible}
.t13{font-size:13px;font-family:var(--sans)}.t16{font-size:16px;font-family:var(--sans)}.b{font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--text-2)}
.lab{font-size:13px;color:var(--text-2);display:block}
.tbl{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font-weight:600;color:var(--text-2);border-bottom:1px solid var(--line);padding:6px 8px 6px 0}
td{border-bottom:1px solid var(--line);padding:7px 8px 7px 0;vertical-align:top}
table.tight td{padding:4px 8px 4px 0}
details{border-top:1px solid var(--line);padding-top:10px}
details.big{border:1px solid var(--line);border-radius:12px;padding:12px 16px;background:var(--card)}
details>*:not(summary){margin-top:10px}
summary{cursor:pointer;font-weight:500;font-size:16px;color:var(--clay-strong)}
details:not(.big) summary{font-size:13px}
details p,details li{font-size:13px;color:var(--text-2)}
.plainlist{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px}
.timeline{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0}
.timeline li{display:grid;grid-template-columns:minmax(0,190px) minmax(0,1fr);gap:4px 16px;padding:10px 0 10px 16px;border-left:2px solid var(--line);position:relative}
.timeline li::before{content:"";position:absolute;left:-6px;top:16px;width:10px;height:10px;border-radius:50%;background:var(--clay)}
.timeline .when{font-weight:600}
@media (max-width:560px){.timeline li{grid-template-columns:minmax(0,1fr)}}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.tk{font-family:var(--serif);font-size:22px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:10px 14px;padding:12px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.tcard p{max-width:none}
.thin{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:14px}
.flag{border-left:4px solid var(--line);padding:8px 14px;background:var(--soft);border-radius:0 10px 10px 0}
.flag.watch{border-left-color:var(--watch);color:var(--text)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--text-2)}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.bars{display:flex;flex-direction:column;gap:8px}
.bl{display:flex;justify-content:space-between;align-items:baseline;gap:4px 12px;font-size:13px;flex-wrap:wrap}
.bl span{min-width:0}.bl b{white-space:nowrap;font-weight:600}
.chg{display:flex;flex-direction:column;gap:8px}
.chg>div{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.chg .lab{display:inline-block;width:96px}

:root{--watch-solid:#e0a106;--t-brk:#5f5f5f;--t-coil:#9c9c9c;--t-ext:#d4d4d4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--watch-solid:#c88a05;--t-brk:#d6d6d6;--t-coil:#9a9a9a;--t-ext:#555}}
:root[data-theme="dark"]{--watch-solid:#c88a05;--t-brk:#d6d6d6;--t-coil:#9a9a9a;--t-ext:#555}
.stk .bl b{white-space:normal;font-weight:500;color:var(--text-2)}
.sub{display:block;font-size:13px;color:var(--text-2);line-height:1.35}
.tg{white-space:nowrap;font-weight:600}.tg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;border:1px solid var(--line);vertical-align:0}
.ph{display:none}
.pill.ma{background:#b3261e;color:#fff}
.pill.out{background:transparent;border:1px dashed var(--line);color:var(--text-2)}
.mtf,.unr{font-size:13px;color:var(--text-2);margin:6px 0}
code{font-size:13px;background:var(--soft);padding:1px 4px;border-radius:4px}
table.lst td:last-child{min-width:220px}
table.lst td:nth-child(n+6):nth-child(-n+8){white-space:nowrap}
section#lists>.card{margin-top:14px}
@media (max-width:760px){
 table.lst thead{display:none}
 table.lst,table.lst tbody,table.lst tr,table.lst td{display:block;width:100%}
 table.lst tr{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:4px 12px;padding:12px 0;border-bottom:1px solid var(--line)}
 table.lst td{border:0;padding:0;min-width:0!important;white-space:normal!important}
 table.lst td::before{content:attr(data-l);display:block;font-size:13px;color:var(--text-3)}
 .ph{display:inline}
 table.lst td:nth-child(1){display:none}
 table.lst td:nth-child(2)::before{content:none}
 table.lst td:nth-child(2){font-size:16px;grid-column:1/-1}
 table.lst td:last-child{grid-column:1/-1}
}
"""
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Daily Cards</title><style>{CSS}{CT.TEMPLATE_CSS}</style></head><body><div class="wrap">
{top}{s1}{s2}{s3}{s4}{s5}{s5b}{s6}{s7}{s8}
<p class="fresh" style="margin-top:36px">Draft for the PM. Nothing is staged, armed or placed; sizing and the trade call are yours.</p>
</div></body></html>"""
OUT.write_text(page)
json.dump({"schema": "card_fields.v1", "date": str(D["date"])[:10], "note": "the ten card fields exactly as printed on the Cards (PM 2026-11-05); the alert emails quote these",
           "cards": CARD_FIELDS}, open(OUT.parent / "card_fields.json", "w"), indent=1)
for _t, _f, _p in LINE_FALLBACK:
    print(f"CARDS LINES FALLBACK: {_t} ({_f}): {'; '.join(_p)}")
print(f"cards lines: {sum(1 for t in CL if CL.get(t))} writer ticker(s) read from cards_lines.json" + ("" if _CL is not None else " (file absent: extraction lines used)"))
print("wrote", OUT, len(page), "bytes; usable", [r["t"] for r in usable], "thin", [r["t"] for r in thin])
