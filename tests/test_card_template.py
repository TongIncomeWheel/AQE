"""PM card spec 2026-11-05: EVERY card, whatever its class, carries the SAME ten fields in the same order, built by code; a field that cannot be
filled prints 'not available: <reason>' (never blank, never omitted); the card shows the COMMITTEE, never a seat by name, no tallies."""
import html
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis/plugin/aegis-core/skills/pma/tools"
spec = importlib.util.spec_from_file_location("card_template_t", TOOLS / "card_template.py")
CT = importlib.util.module_from_spec(spec); spec.loader.exec_module(CT)
cxs = importlib.util.spec_from_file_location("card_extras_t", TOOLS / "card_extras.py")
CX = importlib.util.module_from_spec(cxs); cxs.loader.exec_module(CX)

LABELS = ["Lane", "Why it made the list", "Contested or rejected", "Sector and theme", "Triggers", "Bracket",
          "Verdict and timing", "Wrong if / exit line", "Event risk", "Trend frames"]
SEATS = ("livermore", "minervini", "oneil", "o'neil", "raschke", "seow", "wyckoff", "elder-lens", "chair")


def _mtf():
    fr = lambda cls, ema="9>21": {"served": True, "swing_class": cls, "ema_order": ema, "close": 104.0,
                                  "swing": {"close_vs_swing_high_pct": 4.0, "last_swing_high": {"price": 100.0, "date": "2026-10-20"}}}
    return {"served": True, "W": fr("HH/HL"), "D": fr("HH/HL"), "H1": fr("HH but LL", "9<21")}


def _ctx(kind):
    row = {"ticker": "ZZ", "entry": 104.0, "atr_14d": 2.0, "gics_sector_name": "Technology", "ma_status": "NONE", "days_to_earnings": 12,
           "thematic_baskets": ["AI power"], "unr_status": "NO", "last_pivot_high": {"price": 106.0}}
    srm = {"sector": "Technology", "grade": "DEPLOY", "rrg_quadrant": "LEADING", "roc20": 6.2, "entry_gate": "PASS"}
    pos = {"why": [{"text": "A fresh break to a new high on heavy volume, led by the strongest name in its group (C9).", "voice": "oneil"},
                   {"text": "Template pass, rs_rank_pct 91 and dist_to_20bar_high_pct 0.4.", "voice": "minervini"}]}
    cons = {"ticker": "ZZ", "verdict": "ADVANCE", "status": "CONTESTED", "lane": "MOMENTUM",
            "objections": [{"voice": "seow", "objection": "The signal is read on the hourly chart, not on the daily candle, so it buys in front of price.",
                            "would_clear": "A daily close above the pivot high, then a buy stop over the next high."},
                           {"voice": "elder-lens", "objection": "Elder buys the pullback into value.", "would_clear": "A dip to the 20-day average."}]}
    lv = {"ticker": "ZZ", "class": "ADVANCE", "levels": {"ref_close": 104.0, "stop": 100.0, "tp": [106.0, 112.0, 118.0], "rr_to_tp2": 2.0, "risk_atr": 2.0},
          "triggers": [{"id": "x:ZZ-buy0", "kind": "close_above", "level": 106.0, "basis": "15m", "volume_min_x": 1.4},
                       {"id": "x:ZZ-dead", "kind": "close_below", "level": 100.0, "basis": "daily"}]}
    slate = {"ticker": "ZZ", "timing_count": {"act_now": 5, "wait": 2}, "horizon_sessions": 20}
    c = {"ticker": "ZZ", "cons": cons, "pos": pos, "lv": lv, "br": None, "row": row, "srm": srm, "mtf": _mtf(), "cx": CX, "held": False,
         "mark": "RETURNED", "mark_plain": "advanced before and again today", "lane": "MOMENTUM", "slate_ticket": slate,
         "market_kill": "the index is under distribution", "on_lists": ["AQE top 20"], "supplemental": False}
    if kind == "advance":
        cons["status"] = "AGREED"; cons["objections"] = []
    elif kind == "hold":
        cons["verdict"] = "HOLD-FOR-CONDITIONS"; c["held"] = True; c["mark"] = None; c["mark_plain"] = None
    elif kind == "supplemental":
        c["supplemental"] = True; lv["supplemental"] = True
    elif kind == "dropped":
        cons.update(verdict="PASS", status="DROPPED"); c["lv"] = None
    elif kind == "not_slated":
        cons.update(verdict="PASS", status="NOT_SLATED", objections=[]); c["lv"] = None; c["pos"] = None; c["cut_reason"] = "claims ruled against it"
    elif kind == "aqe_list":
        c["cons"] = None; c["pos"] = None; c["lv"] = None; c["lane"] = None; c["slate_ticket"] = None; c["mtf"] = None; c["srm"] = None
    return c


KINDS = ["contested", "advance", "hold", "supplemental", "dropped", "not_slated", "aqe_list"]


def _body(h):
    """The card as a trader sees it: everything outside the folded audit trail."""
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<details.*?</details>", "", h, flags=re.S)))


@pytest.mark.parametrize("kind", KINDS)
def test_every_class_of_card_renders_the_same_ten_fields_in_order(kind):
    h = CT.render_card(_ctx(kind), html.escape)
    assert CT.validate_card(h) == []
    assert re.findall(r'data-f="([a-z_]+)"', h) == list(CT.FIELD_IDS)
    labels = re.findall(r'<span class="lab">(.*?)(?: <span|</span>)', h)
    assert [html.unescape(x) for x in labels] == LABELS


@pytest.mark.parametrize("kind", KINDS)
def test_a_field_that_cannot_be_filled_says_why_and_none_is_blank(kind):
    h = CT.render_card(_ctx(kind), html.escape)
    for fid in CT.FIELD_IDS:
        val = re.search(rf'data-f="{fid}".*?<div class="val">(.*?)</div>', h, re.S).group(1).strip()
        assert val, (kind, fid)
        if "not available" in val:
            assert re.search(r"not available[:\s(]+\S", val), (kind, fid, val)          # a reason follows
    ctx = _ctx("aqe_list")
    fields = {f["id"]: f for f in CT.build_fields(ctx)}
    assert fields["lane"]["text"].startswith("not available:") and fields["verdict"]["text"].startswith("not available:")
    assert fields["frames"]["text"].startswith("not available:") and fields["sector"]["text"].startswith("not available:")
    assert fields["why"]["text"] == "On the AQE top 20 list."


def test_mutation_dropping_or_blanking_any_field_is_caught():
    h = CT.render_card(_ctx("contested"), html.escape)
    assert CT.validate_card(h) == []
    for fid in CT.FIELD_IDS:
        dropped = re.sub(rf'<div class="tf[^"]*" data-f="{fid}">.*?</div></div>', "", h, count=1, flags=re.S)
        assert dropped != h and CT.validate_card(dropped), fid                          # removing the field fails the check
        blanked = re.sub(rf'(data-f="{fid}".*?<div class="val">).*?(</div>)', r"\1\2", h, count=1, flags=re.S)
        assert any("blank" in e for e in CT.validate_card(blanked)), fid
    swapped = h.replace('data-f="lane"', 'data-f="XX"', 1)
    assert CT.validate_card(swapped)


def test_the_card_shows_the_committee_never_a_seat_and_no_tally():
    for kind in KINDS:
        body = _body(CT.render_card(_ctx(kind), html.escape)).lower()
        assert not any(s in body for s in SEATS), (kind, body)
        assert not re.search(r"\b\d+ (of|/) \d+\b|\b\d+ (analysts|seats|objections)\b|\bC\d{1,2}\b|_", body), (kind, body)
        assert " my " not in body and " i " not in body


def test_lines_two_and_three_are_one_verbatim_committee_sentence_each():
    c = _ctx("contested")
    f = {x["id"]: x for x in CT.build_fields(c)}
    assert f["why"]["tag"] == "committee consensus"
    assert f["why"]["text"] == "A fresh break to a new high on heavy volume, led by the strongest name in its group."          # the code removed '(C9)', nothing else
    assert f["contested"]["text"] == ("Contested: The signal is read on the hourly chart, not on the daily candle, so it buys in front of price. "
                                      "What would clear it: A daily close above the pivot high, then a buy stop over the next high.")
    # the line follows the filed words (mutation): change the rationale and the card changes with it
    c["pos"]["why"][0]["text"] = "Volume dried up under the line and the group is rolling over."
    assert CT.build_fields(c)[1]["text"] == "Volume dried up under the line and the group is rolling over."


def test_attribution_tag_changes_with_the_class_of_the_card():
    tags = {k: CT.build_fields(_ctx(k))[1]["tag"] for k in KINDS}
    assert tags["advance"] == "committee consensus" and tags["contested"] == "committee consensus"
    assert tags["supplemental"] == "supplemental committee pass, contested"
    assert tags["dropped"] == "committee did not advance it" and tags["aqe_list"] == "AQE list, not a committee pick"


def test_rejected_and_unslated_names_say_why_in_the_committee_slot():
    f = {k: {x["id"]: x["text"] for x in CT.build_fields(_ctx(k))} for k in ("dropped", "not_slated")}
    assert f["dropped"]["contested"].startswith("Rejected: ") and "What would clear it:" in f["dropped"]["contested"]
    assert f["not_slated"]["contested"] == "Not slated: claims ruled against it."


def test_bracket_trigger_exit_timing_event_and_frames_come_from_the_files():
    f = {x["id"]: x["text"] for x in CT.build_fields(_ctx("contested"))}
    assert f["triggers"].startswith("An hourly close above 106 on at least 1.4x normal volume")
    assert "stop 100" in f["bracket"] and "risk 2 daily ranges" in f["bracket"] and "U&R: none" in f["bracket"] and "reward to the second target 2R" in f["bracket"]
    assert f["verdict"] == "Advance. Timing: act now, on the trigger; horizon 20 sessions."
    assert f["wrong_if"] == "Wrong if a daily close prints under 100."
    assert "earnings in 12 trading days, inside the horizon" in f["event"] and "the index is under distribution" in f["event"] and f["event"].startswith("M&A: no pending deal flagged")
    assert "Weekly: higher highs and higher lows" in f["frames"] and "1.0 daily ranges (ATR) above the last swing high" not in f["frames"]
    assert "2.0 daily ranges (ATR) above the last swing high (+4.0%), extended" in f["frames"]
    assert f["sector"] == "Technology: graded DEPLOY, leading on the strength map, 20-day move +6.2%, entry gate PASS; theme basket: AI power"
    assert f["lane"] == "Momentum · returned; advanced before and again today"


def test_a_bracket_with_no_valid_stop_says_why_never_blank():
    c = _ctx("contested")
    c["lv"] = {"levels": None, "levels_invalid_reason": "NO STOP DEFINABLE", "triggers": []}
    f = {x["id"]: x["text"] for x in CT.build_fields(c)}
    assert f["bracket"].startswith("not available: NO STOP DEFINABLE")
    assert f["wrong_if"].startswith("not available:")
    assert f["triggers"].startswith("AQE default, not a committee trigger: an hourly close above 106")


def test_a_mark_of_none_is_not_a_tag_a_passed_name_has_no_timing_and_an_unclean_objection_is_said_plainly():
    c = _ctx("contested")
    c["mark"], c["mark_plain"] = "none", "none"
    assert CT.build_fields(c)[0]["text"] == "Momentum"                              # 'none' is not a returned/new tag
    d = _ctx("dropped")
    d["slate_ticket"] = {"timing_count": {"act_now": 5, "wait": 0}, "horizon_sessions": 20}
    assert CT.build_fields(d)[6]["text"] == "Pass. Timing: not applicable, the committee passed on it."
    d["cons"]["objections"] = [{"voice": "oneil", "objection": "ticket reclaim:ma_20 vs H1 (C4)", "would_clear": "A daily close above the pivot high, then a buy stop."}]
    t = CT.build_fields(d)[2]["text"]
    assert t == "not available: no committee line in plain words is on file for this rejected name"


# ------------------------------------------------------------------ WRITER lines (cards_lines.json), PM 2026-11-05
GOOD_WHY = "A market leader breaking to a new high on heavy buying, the strongest of its group."
GOOD_CONTESTED = "Contested: the buy trigger is read on the hourly chart, not the daily close; it clears on a daily close above the pivot high."


def test_the_writers_lines_are_preferred_over_the_extraction_route():
    c = _ctx("contested")
    c["lines"] = {"why": GOOD_WHY, "contested": GOOD_CONTESTED.replace("; it", ", and it")}
    f = {x["id"]: x["text"] for x in CT.build_fields(c)}
    assert f["why"] == GOOD_WHY and f["contested"].startswith("Contested: the buy trigger is read on the hourly chart")
    assert c["_src"] == {"why": "writer", "contested": "writer"} and "_fallback" not in c


@pytest.mark.parametrize("bad,problem", [
    ("Livermore thinks it is a leader breaking out.", "names a seat"),
    ("I would buy the leader on the break.", "first-person seat voice"),
    ("Five of seven analysts back the leader on the break.", "vote tally"),
    ("The leader breaks above bar_high on heavy buying.", "field name or code"),
    ("A leader breaking out (C9) on heavy buying.", "field name or code"),
    ("A leader up 12%, 5.4 daily ranges above 96.56 and 94.1 under the line.", "numbers"),
    ("A market leader breaking out. It is the strongest of its group.", "more than one sentence"),
    ("x" * 210 + ".", "over the 200 cap"),
])
def test_a_writer_line_that_breaks_the_gate_is_never_printed_the_extraction_line_stands(bad, problem):
    assert any(problem in e for e in CT.gate_line(bad, "why")), CT.gate_line(bad, "why")
    c = _ctx("contested")
    c["lines"] = {"why": bad, "contested": GOOD_CONTESTED}
    f = {x["id"]: x["text"] for x in CT.build_fields(c)}
    assert f["why"] == "A fresh break to a new high on heavy volume, led by the strongest name in its group."          # the verbatim extraction line
    assert c["_fallback"][0][0] == "why" and c["_fallback"][0][1]
    assert f["contested"] == GOOD_CONTESTED                                                                           # the good line still prints


def test_the_good_lines_pass_the_gate_and_an_empty_line_does_not():
    assert CT.gate_line(GOOD_WHY, "why") == [] and CT.gate_line(GOOD_CONTESTED, "contested") == []
    assert CT.gate_line("", "why") == ["empty"]


def test_no_placeholder_sentence_is_ever_card_content():
    for kind in KINDS:
        for f in CT.build_fields(_ctx(kind)):
            assert "does not read clean" not in f["text"] and "reads clean" not in f["text"], (kind, f["id"], f["text"])
    c = _ctx("dropped")
    c["pos"] = None
    c["cons"]["objections"] = [{"voice": "oneil", "objection": "ticket reclaim:ma_20 vs H1 (C4)", "would_clear": "A daily close above the pivot high, then a buy stop."}]
    t = CT.build_fields(c)[2]["text"]
    assert t == "not available: no committee line in plain words is on file for this rejected name"


def test_grammar_one_daily_range_is_singular():
    c = _ctx("contested")
    c["lv"]["levels"]["risk_atr"] = 1.0
    assert "risk 1 daily range," in CT.build_fields(c)[5]["text"] or "risk 1 daily range." in CT.build_fields(c)[5]["text"]
    c["lv"]["levels"]["risk_atr"] = 1.5
    assert "risk 1.5 daily ranges" in CT.build_fields(c)[5]["text"]


def test_a_name_with_no_levels_row_takes_the_export_bracket_and_says_where_it_came_from():
    c = _ctx("aqe_list")
    c["row"]["bracket"] = {"valid": True, "stop": 98.0, "targets": [{"price": 106.0}, {"price": 112.0}, {"price": 120.0}]}
    t = CT.build_fields(c)[5]["text"]
    assert "stop 98" in t and "targets 112 (2.3R)" not in t and "Levels source: AQE export bracket." in t
    c["row"]["bracket"] = {"valid": False, "atr_fallback_stop": 101.0, "targets": [{"price": 108.0}], "invalid_reason": "no structural support passes the gates"}
    t2 = CT.build_fields(c)[5]["text"]
    assert "stop 101" in t2 and "no structural stop passed the gates" in t2
    c["row"]["bracket"] = {"valid": False, "invalid_reason": "no structural support passes the gates"}
    assert CT.build_fields(c)[5]["text"].startswith("not available: no structural support passes the gates")


def test_check_py_gates_the_lines_file(tmp_path):
    import json
    cs = importlib.util.spec_from_file_location("chk_lines", ROOT / "aegis/plugin/aegis-core/skills/daily-check/check.py")
    ck = importlib.util.module_from_spec(cs); cs.loader.exec_module(ck)
    good = {"KO": {"why": GOOD_WHY, "contested": GOOD_CONTESTED}}
    p = tmp_path / "cards_lines.json"
    p.write_text(json.dumps(good))
    assert ck.check_cards_lines(str(p))[0] == []
    p.write_text(json.dumps({"KO": {"why": "Livermore likes it (C9).", "contested": GOOD_CONTESTED}, "DG": {"why": GOOD_WHY}}))
    fails = ck.check_cards_lines(str(p))[0]
    assert any("KO.why" in f and "names a seat" in f for f in fails) and any("DG.contested: missing" in f for f in fails)
    f, notes = ck.check_cards_lines(str(tmp_path / "absent.json"))
    assert f == [] and "not found" in notes[0]                                           # absent = declared, not a silent pass


def test_a_supplemental_advance_row_uses_its_own_committee_levels_and_every_exit_line_falls_back_to_a_stop():
    c = _ctx("supplemental")
    c["br"] = {"stop": {"price": 90.0}, "tp_ladder": [{"price": 105.0}, {"price": 110.0}], "risk_atr": 3.0, "rr_to_tp2": 1.0, "price": {"value": 104.0}, "source": "AQE list (AQE)"}
    t = CT.build_fields(c)[5]["text"]
    assert "stop 100" in t and "stop 90" not in t                       # the supplemental pass's own levels, not the brief-list bracket
    d = _ctx("dropped")
    d["lv"] = None; d["br"] = None
    d["row"]["bracket"] = {"valid": True, "stop": 98.5, "targets": [{"price": 108.0}]}
    assert CT.build_fields(d)[7]["text"] == "No committee exit line; the AQE stop is 98.5."
