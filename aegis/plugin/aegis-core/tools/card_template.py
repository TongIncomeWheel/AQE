#!/usr/bin/env python3
"""card_template.py -- ONE fixed, code-built card template for every name on the Cards (PM 2026-11-05).

Every card, whatever its class (ADVANCE, HOLD, supplemental, rejected, never slated, an AQE-list name), carries the SAME ten fields in
this order. A field that cannot be filled prints `not available: <reason>` -- never blank, never omitted:

   1 Lane (small tag: new / returned / held, streak)
   2 Why it made the list      (tagged: committee consensus / supplemental committee pass, contested / AQE list, not a committee pick)
   3 Contested or rejected     (one plain committee line + what would clear it; rejected names: why; never slated: why)
   4 Sector and theme          (grade, entry gate, 20-day move, theme basket)
   5 Triggers                  (what must print, with volume)
   6 Bracket                   (entry reference, stop, reward-to-risk to TP2 and the ladder, risk in ATR, U&R line)
   7 Verdict and timing        (act now / wait, horizon in sessions)
   8 Wrong if / exit line
   9 Event risk                (M&A status, earnings inside the horizon, market-kill line)
  10 Trend frames              (weekly / daily / hourly swing class and the ATR distance from the daily swing high)

ATTRIBUTION (PM 2026-11-05): the card shows the COMMITTEE, never a seat by name, and no vote tallies. Lines 2 and 3 are each ONE
committee-voice line built by code: a whole sentence taken VERBATIM from the adopted R42 text (committee_position.json `why`) or from the
filed objections' `would_clear`, passed only through the plain-words table (term swaps, never a fact). A sentence that does not read clean is
skipped; if none does the field says so. The seats' own words sit only in the folded audit trail, unattributed.

Pure functions: no file or network access. The renderer (pma_cards_v3.py) supplies the run's data. R1: information only -- nothing here is a
gate, a vote input or a verdict change.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = ("Lane", "Why it made the list", "Contested or rejected", "Sector and theme", "Triggers", "Bracket",
          "Verdict and timing", "Wrong if / exit line", "Event risk", "Trend frames")
FIELD_IDS = ("lane", "why", "contested", "sector", "triggers", "bracket", "verdict", "wrong_if", "event", "frames")
MIN_TARGET_R = 1.0
MAX_LINE = 190          # a committee line longer than this is not "one line"


def _mod(name):
    p = HERE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"card_template_{name}", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_LVC = None


def _lvc():
    global _LVC
    if _LVC is None:
        _LVC = _mod("lists_vs_committee")
    return _LVC


def na(reason: str) -> str:
    return f"not available: {reason}"


def is_na(text: str) -> bool:
    return str(text).startswith("not available:")


# ----------------------------------------------------------------------------------------------- the committee-voice sentence
_TALLY = re.compile(r"\b\d+\s+(?:of|/)\s*\d+\b|\b\d+\s+(?:analysts|seats|voices|supporters|objections)\b|\b(?:analysts|seats) (?:agree|filed|share)", re.I)


_SEAT_VOICE = re.compile(r"\b(?:my|mine|I|I'm|I'd|I've|me|we|our)\b", re.I)                         # a seat speaking in the first person
_SEAT_NAME = re.compile(r"\bElder\b(?!\s+(?:score|impulse|reading|pattern|run))|\bChair\b")           # 'Elder adds on the pullback' names the seat; 'the Elder score' does not


def _sentence_ok(s, max_len):
    L = _lvc()
    low = s.lower()
    if not s or len(s) > max_len or len(s) < 30 or len(s.split()) < 6:
        return False
    if L.QUOTE_JARGON.search(s) or "_" in s or any(v in low for v in L.VOICES) or "elder-lens" in low or _TALLY.search(s) or _SEAT_VOICE.search(s) or _SEAT_NAME.search(s):
        return False
    return not re.search(r"[:;]|--|\[|\]|\{|\}|\(\s*\)", s)


def clean_sentences(text, max_len=MAX_LINE):
    """Every whole sentence of `text` that reads clean to a trader after the plain-words pass: no seat name or first-person seat voice, no rule
    code, no tally, no leftover field name or list literal, 6+ words, within MAX_LINE. Verbatim words (term swaps only)."""
    L = _lvc()
    out = []
    for sen in L.sentences(str(text or "")):
        s = L.plain(L.RULE_CODES.sub("", sen)).strip()
        if _sentence_ok(s, max_len):
            out.append(s if s[-1] in ".!?" else s + ".")
    return out


def clean_sentence(text, max_len=MAX_LINE):
    c = clean_sentences(text, max_len)
    return max(c, key=len) if c else None


def first_clean(texts, max_len=MAX_LINE):
    """The most informative clean sentence across the texts (the longest within one line); None when none reads clean."""
    best = []
    for t in texts or []:
        best += clean_sentences(t, max_len)
    return max(best, key=len) if best else None


def audit_quotes(items):
    """Folded audit trail only: the seats' words, plain-words pass applied, with no seat name ('an analyst') and no tally."""
    L = _lvc()
    out = []
    for t in items or []:
        s = L.plain(L.RULE_CODES.sub("", str(t or ""))).strip()
        if s:
            out.append(s)
    return out


BRIEF_N = {"Elder": 15, "AQE": 20, "Detect lens": 15, "Swing pivot": 20}


def brief_lists(daily_list, lens_ranked=None):
    """{ticker: ['Elder top 15', ...]} for the brief's lists, from the export alone (same definitions as the alert universe)."""
    rank = lambda r: r.get("rank") if isinstance(r.get("rank"), int) else 10 ** 6
    elder = sorted([r for r in daily_list if r.get("on_elder")], key=lambda r: (-(r.get("elder") or 0), rank(r)))
    aqe = sorted([r for r in daily_list if isinstance(r.get("rank"), int)], key=lambda r: r["rank"])
    known = {r.get("ticker") for r in daily_list}
    lens = [x["ticker"] for x in lens_ranked or [] if x.get("ticker") in known]
    swing = [r["ticker"] for r in aqe if r.get("swing_pivot") is True]
    out = {}
    for name, tks in (("Elder", [r["ticker"] for r in elder]), ("AQE", [r["ticker"] for r in aqe]), ("Detect lens", lens), ("Swing pivot", swing)):
        for tk in tks[:BRIEF_N[name]]:
            out.setdefault(tk, []).append(f"{name} top {BRIEF_N[name]}")
    return out


# ----------------------------------------------------------------------------------------------- fields
def _lane(c):
    lane = str(c.get("lane") or "").title()
    tags = []
    mark = c.get("mark")
    if c.get("held"):
        tags.append("held")
    if mark and str(mark).strip().lower() not in ("none", "-", "n/a", "null"):
        tags.append(str(mark).lower())
        mp = c.get("mark_plain")
        if mp and str(mp).strip().lower() not in ("none", "-"):
            tags.append(mp)
    if not lane:
        return na("no lane (the committee did not vote this name)") + (f" [{'; '.join(tags)}]" if tags else "")
    return lane + (f" · {'; '.join(tags)}" if tags else "")


def _why(c):
    cons, pos = c.get("cons"), c.get("pos")
    if c.get("supplemental") and cons:
        tag = "supplemental committee pass" + (", contested" if str(cons.get("status")) == "CONTESTED" else "")
    elif cons and str(cons.get("status")) in ("AGREED", "CONTESTED"):
        tag = "committee consensus" + (", with reservations" if str(cons.get("status")) == "AGREED" and (cons.get("reservations")) else "")
    elif cons and str(cons.get("status")) in ("DROPPED", "NOT_SLATED", "DEAL_PINNED"):
        tag = "committee did not advance it"
    else:
        tag = "AQE list, not a committee pick"
    if not pos and not cons:
        ol = c.get("on_lists")
        if ol:
            return tag, "On the " + " and ".join(ol[:3]) + (" lists." if len(ol) > 1 else " list.")
        return tag, na("the committee did not vote this name and it is on no AQE list")
    texts = [w.get("text") for w in (pos or {}).get("why") or []]
    line = first_clean(texts)
    if line:
        return tag, line
    if cons and str(cons.get("status")) in ("DROPPED", "NOT_SLATED", "DEAL_PINNED") and c.get("on_lists"):
        return tag, "On the " + " and ".join(c["on_lists"][:3]) + (" lists." if len(c["on_lists"]) > 1 else " list.")
    if not texts:
        return tag, na("no filed rationale for this name")
    return tag, na("no sentence in the committee's filed rationale reads clean in plain words (the full words are in the audit trail)")


def _contested(c):
    cons = c.get("cons")
    if not cons:
        if c.get("committee_result"):
            return str(c["committee_result"]).capitalize() + "."
        return na("not voted by the committee")
    st = str(cons.get("status"))
    objs = cons.get("objections") or []
    if st == "NOT_SLATED":
        return "Not slated: " + (c.get("cut_reason") or "it was cut before the slate") + "."
    if st == "DEAL_PINNED":
        return "Excluded by rule: a pending takeover target trades on the deal spread, not on momentum."
    if st == "AGREED" and not objs:
        return "No objection filed: the room agreed."
    lead = "Rejected" if st == "DROPPED" else "Contested"
    obj = first_clean([o.get("objection") for o in objs])
    clr = first_clean([o.get("would_clear") for o in objs])
    if not objs:
        return na(f"{lead.lower()} but no objection is on file")
    if not obj and not clr:
        return na(f"{lead.lower()}: no filed objection reads clean in plain words (see the audit trail)")
    return (f"{lead}: {obj}" if obj else f"{lead}: the filed objection does not read clean in plain words (the full words are in the audit trail).") + \
        (f" What would clear it: {clr}" if clr else " What would clear it: not available (no clean line filed).")


def _sector(c):
    s, row = c.get("srm"), c.get("row") or {}
    if not s:
        return na("no sector grade served for this name")
    q = str(s.get("rrg_quadrant") or "").lower()
    bits = [f"{s.get('sector')}: graded {s.get('grade')}", f"{q} on the strength map" if q else None,
            (f"20-day move {s['roc20']:+.1f}%" if isinstance(s.get("roc20"), (int, float)) else None),
            f"entry gate {s.get('entry_gate')}"]
    th = row.get("thematic_baskets") or ([row["thematic_basket"]] if row.get("thematic_basket") else [])
    th = [(t if isinstance(t, str) else str(t.get("name") or t.get("basket") or t)).replace("_", " ") for t in th]
    return ", ".join(b for b in bits if b) + "; " + (f"theme basket: {', '.join(th)}" if th else "no theme basket")


def _triggers(c):
    lv, row = c.get("lv"), c.get("row") or {}
    trig = (lv or {}).get("triggers") or []
    buy = next((x for x in trig if x.get("kind") == "close_above"), None)
    if buy:
        vol = f" on at least {buy['volume_min_x']:g}x normal volume" if buy.get("volume_min_x") else ""
        what = "An hourly close" if buy.get("basis") == "15m" else "A daily close"
        chase = ((lv.get("conditions") or {}).get("shared") or {}).get("chase") or {}
        late = f"; too late past {chase['levels'][0]:g}" if chase.get("levels") else ""
        return f"{what} above {buy['level']:g}{vol}{late}."
    lph = (row.get("last_pivot_high") or {}).get("price")
    e = row.get("entry")
    if isinstance(lph, (int, float)) and isinstance(e, (int, float)) and lph > e:
        return f"AQE default, not a committee trigger: an hourly close above {lph:g}."
    return na("no committee trigger and no pivot above the last close")


def _ladder(entry, stop, tps):
    risk = entry - stop
    if risk <= 0:
        return None
    rr = [((tp - entry) / risk, tp) for tp in tps if isinstance(tp, (int, float))]
    return [(round(r, 1), tp) for r, tp in rr if r >= MIN_TARGET_R], [(round(r, 1), tp) for r, tp in rr if r < MIN_TARGET_R]


def _bracket(c):
    br, lv, row, cx = c.get("br"), c.get("lv"), c.get("row") or {}, c.get("cx")
    levels = None
    src = None
    if br and (br.get("stop") or {}).get("price") is not None:
        levels = {"stop": br["stop"]["price"], "tp": [t.get("price") for t in br.get("tp_ladder") or []], "risk_atr": br.get("risk_atr"),
                  "rr2": br.get("rr_to_tp2"), "ref": (br.get("price") or {}).get("value")}
        src = br.get("source")
    elif lv and (lv.get("levels") or {}).get("stop") is not None:
        l = lv["levels"]
        levels = {"stop": l["stop"], "tp": l.get("tp") or [], "risk_atr": l.get("risk_atr"), "rr2": l.get("rr_to_tp2"), "ref": l.get("ref_close")}
        src = lv.get("levels_source")
    unr = cx.unr_tag(row) if cx else na("U&R reader not loaded")
    if not levels:
        why = (br or {}).get("invalid_reason") or (lv or {}).get("levels_invalid_reason") or "no bracket was built for this name"
        return na(why) + ". " + unr
    trig = next((x["level"] for x in (lv or {}).get("triggers") or [] if x.get("kind") == "close_above"), None)
    entry = trig if isinstance(trig, (int, float)) else levels["ref"]
    ent_word = "buy line" if isinstance(trig, (int, float)) else "last close"
    parts = [f"Entry reference {entry:g} ({ent_word})", f"stop {levels['stop']:g}"]
    lad = _ladder(entry, levels["stop"], levels["tp"]) if isinstance(entry, (int, float)) else None
    if lad:
        good, near = lad
        parts.append("targets " + (", ".join(f"{tp:g} ({r:g}R)" for r, tp in good) if good else "none reaches 1R"))
        if near:
            parts.append("nearby resistance, not targets: " + ", ".join(f"{tp:g}" for _, tp in near))
    if isinstance(levels.get("rr2"), (int, float)):
        parts.append(f"reward to the second target {levels['rr2']:g}R")
    parts.append(f"risk {levels['risk_atr']:g} daily ranges" if isinstance(levels.get("risk_atr"), (int, float)) else "risk in daily ranges not available (no average daily range served)")
    return ", ".join(parts) + "." + (f" Levels source: {src}." if src else "") + " " + unr


def _verdict(c):
    cons, tk = c.get("cons"), c.get("slate_ticket")
    if not cons:
        return na("the committee did not vote this name")
    v = {"ADVANCE": "Advance", "HOLD-FOR-CONDITIONS": "Hold for conditions", "PASS": "Pass"}.get(cons.get("verdict"), str(cons.get("verdict")))
    if not tk:
        return v + ". Timing: " + na("not on the slate, so no timing read")
    if cons.get("verdict") == "PASS":
        return v + ". Timing: not applicable, the committee passed on it."
    tc = tk.get("timing_count") or {}
    now, wait = tc.get("act_now"), tc.get("wait")
    if isinstance(now, int) and isinstance(wait, int) and now + wait:
        timing = "act now, on the trigger" if now >= wait else "wait"
    else:
        timing = "not available: no timing read filed"
    hz = tk.get("horizon_sessions")
    return f"{v}. Timing: {timing}" + (f"; horizon {hz} sessions." if hz else ".")


def _wrong_if(c):
    lv, br = c.get("lv"), c.get("br")
    dead = next((x for x in (lv or {}).get("triggers") or [] if x.get("kind") == "close_below"), None)
    if dead and isinstance(dead.get("level"), (int, float)):
        return f"Wrong if a daily close prints under {dead['level']:g}."
    k = (lv or {}).get("kills")
    if k:
        k = re.sub(r"\s*\(\d+ analysts?'? exit line\)", "", str(k)).strip()
        if k:
            return clean_sentence(k) or na("the filed exit line does not read clean in plain words")
    stp = ((br or {}).get("stop") or {}).get("price")
    if isinstance(stp, (int, float)):
        return f"No committee exit line; the AQE stop is {stp:g}."
    return na("no exit line and no stop on file")


def _event(c):
    row, hz, mk = c.get("row") or {}, (c.get("slate_ticket") or {}).get("horizon_sessions"), c.get("market_kill")
    st = str(row.get("ma_status") or "")
    ma = ("M&A: no pending deal flagged" if st == "NONE" else
          "M&A: a pending deal is flagged" + (f" ({row.get('ma_status').replace('PENDING_', '').replace('_', ' ').lower()})" if st.startswith("PENDING") else "") if st else
          "M&A: " + na("the scan did not report this name"))
    if st == "UNKNOWN":
        ma = "M&A: not checked (the scan did not run for this name)"
    d = row.get("days_to_earnings")
    if isinstance(d, (int, float)):
        er = f"earnings in {int(d)} trading days" + (", inside the horizon" if isinstance(hz, int) and d <= hz else (", outside the horizon" if isinstance(hz, int) else ""))
    else:
        er = "earnings: " + na("no earnings date served")
    kill = f"market-kill line: {mk}" if mk else "market-kill line: none active"
    return f"{ma}; {er}; {kill}."


def _frames(c):
    mtf, row, cx = c.get("mtf"), c.get("row") or {}, c.get("cx")
    if not cx:
        return na("trend reader not loaded")
    if not isinstance(mtf, dict):
        return na("no trend-frame grid row for this name")
    if not mtf.get("served"):
        return na(str(mtf.get("reason") or "frames not served"))
    txt = " ".join(cx.frame_plain(tf, mtf.get(tf)) for tf in ("W", "D", "H1"))
    ad = cx.atr_distance(mtf, row)
    return txt + (" Daily close vs the latest daily swing high: " + ad["text"] + "." if ad else " Distance from the daily swing high: " + na("no swing high or no average daily range"))


def build_fields(c: dict) -> list[dict]:
    """c = the context dict (see pma_cards_v3 `tmpl_ctx`). Returns the ten fields in order: id, label, text, tag (field 2 only), ok."""
    tag, why = _why(c)
    vals = [_lane(c), why, _contested(c), _sector(c), _triggers(c), _bracket(c), _verdict(c), _wrong_if(c), _event(c), _frames(c)]
    out = []
    for i, (fid, lab, v) in enumerate(zip(FIELD_IDS, LABELS, vals)):
        out.append({"id": fid, "label": lab, "text": v, "tag": tag if i == 1 else None, "ok": not is_na(v)})
    return out


# ----------------------------------------------------------------------------------------------- html
TEMPLATE_CSS = """
.tmpl .tf{display:grid;grid-template-columns:minmax(120px,170px) minmax(0,1fr);gap:4px 14px;padding:7px 0;border-top:1px solid var(--line)}
.tmpl .tf .lab{font-size:13px;color:var(--text-3)}
.tmpl .tf .val{font-size:15px;line-height:1.4}
.tmpl .tf.na .val{color:var(--text-2);font-style:italic}
.tmpl .src{font-size:12px;color:var(--text-3);margin-left:8px;font-weight:400}
@media (max-width:560px){.tmpl .tf{grid-template-columns:1fr}}
"""


def render_card(c: dict, esc, head_html: str = "") -> str:
    """The card as html. `esc` is html.escape. `head_html` is the ticker + pills row built by the caller."""
    fields = build_fields(c)
    rows = []
    for f in fields:
        tag = f' <span class="src">[{esc(f["tag"])}]</span>' if f.get("tag") else ""
        rows.append(f'<div class="tf{"" if f["ok"] else " na"}" data-f="{f["id"]}"><span class="lab">{esc(f["label"])}{tag}</span>'
                    f'<div class="val">{esc(f["text"])}</div></div>')
    cons, pos = c.get("cons") or {}, c.get("pos") or {}
    quotes = audit_quotes([w.get("text") for w in (pos.get("why") or [])])
    quotes += audit_quotes([o.get("objection") for o in cons.get("objections") or []])
    clears = audit_quotes([o.get("would_clear") for o in cons.get("objections") or []])
    audit = ""
    if quotes or clears:
        items = "".join(f"<li>{esc(q)}</li>" for q in quotes) + "".join(f"<li>What would clear it: {esc(q)}</li>" for q in clears)
        audit = f'<details><summary>Audit trail: the analysts&rsquo; own words</summary><ul class="plainlist">{items}</ul></details>'
    return f'<div class="card tmpl" data-t="{esc(str(c.get("ticker")))}">{head_html}{"".join(rows)}{audit}</div>'


def validate_card(card_html: str) -> list[str]:
    """Problems with one rendered card: a missing field, a field out of order, an empty value. [] = the template is whole."""
    errs = []
    ids = re.findall(r'data-f="([a-z_]+)"', card_html)
    if ids != list(FIELD_IDS):
        missing = [f for f in FIELD_IDS if f not in ids]
        errs.append(f"fields {'missing: ' + ', '.join(missing) if missing else 'out of order'} (got {ids})")
    for fid in FIELD_IDS:
        m = re.search(rf'data-f="{fid}".*?<div class="val">(.*?)</div>', card_html, re.S)
        if m is not None and not re.sub(r"<[^>]+>|\s", "", m.group(1)):
            errs.append(f"field {fid} is blank")
    return errs
