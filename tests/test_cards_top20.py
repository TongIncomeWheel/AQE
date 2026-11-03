"""PM 2026-11-03: the Cards end with the 20 best-ranked AQE names, built by code (no model).

Real data: tests/fixtures/top20_real/export_top20.json is the 3 Nov 2026 export's daily_list ranks 1..22 and its
sector grades. The conductor's sample of that day: RYAN, HAYW, CUBE, DLTR, UPS, CCL, KIM, EXC, VLTO, HOG, STGW, CNP,
FTV, AJG, SIRI, AMGN, KDP, SNY, PPG, CWK - 14 strong, 6 turning.
"""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pma_cards_t", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards.py")
PC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PC)

D = json.loads((ROOT / "tests" / "fixtures" / "top20_real" / "export_top20.json").read_text())
SAMPLE = "RYAN HAYW CUBE DLTR UPS CCL KIM EXC VLTO HOG STGW CNP FTV AJG SIRI AMGN KDP SNY PPG CWK".split()
VOICES = ["elder-lens", "livermore", "minervini", "oneil", "raschke", "seow", "wyckoff"]


def cons_for(**per):
    return [{"ticker": t, "verdict": v, "status": st, "split": {"support": sup, "oppose": [], "abstain": []}}
            for t, (v, st, sup) in per.items()]


def rows_of(html):
    return re.findall(r"<tr><td class=\"num\">(\d+)</td><td><b>([A-Z.]+)</b></td><td>(.*?)</td><td><span class=\"pill (p-\w+)\" title=\"(.*?)\">(.*?)</span></td><td>(.*?)</td><td>(.*?)</td></tr>", html)


def test_exactly_the_twenty_best_ranked_names_in_rank_order_from_the_real_export():
    html = PC._top20_panel(D, [])
    rows = rows_of(html)
    assert [r[1] for r in rows] == SAMPLE and [int(r[0]) for r in rows] == list(range(1, 21))
    assert "RANK" not in html and "CWK" in html and "AIZ" not in html          # rank 21-22 are not shown


def test_sector_state_matches_the_group_turn_sections_rule_14_strong_6_turning():
    rows = rows_of(PC._top20_panel(D, []))
    state = {r[1]: r[5] for r in rows}
    assert sum(1 for s in state.values() if s == "STRONG") == 14 and sum(1 for s in state.values() if s == "TURNING") == 6
    assert state["RYAN"] == "STRONG" and state["HAYW"] == "TURNING" and state["STGW"] == "TURNING"      # TURNING grade, LAGGING quadrant
    # the SAME function the group-turn section uses
    srm = {x["sector"]: x for x in D["srm"]}
    for r in D["daily_list"][:20]:
        x = srm[r["gics_sector_name"]]
        k = PC._group_kind(x["grade"], x["rrg_quadrant"])
        assert state[r["ticker"]] == {"lead": "STRONG", "turn": "TURNING"}[k]


def test_a_sector_that_is_neither_shows_its_plain_aqe_state_and_a_missing_grade_is_declared():
    d = json.loads(json.dumps(D))
    d["srm"] = [dict(x, grade="WATCH", rrg_quadrant="LAGGING") if x["sector"] == "Financials" else x for x in d["srm"]]
    d["srm"] = [x for x in d["srm"] if x["sector"] != "Utilities"]
    rows = {r[1]: r for r in rows_of(PC._top20_panel(d, []))}
    assert rows["RYAN"][5] == "WATCH · lagging" and rows["RYAN"][3] == "p-n"            # plain AQE words, never blank
    assert rows["EXC"][5] == "no sector grade" and "declared gap" in rows["EXC"][4]       # Utilities removed: declared, not invented


def test_verdict_and_voters_come_from_the_record_and_names_the_room_did_not_carry_say_so():
    cons = cons_for(RYAN=("ADVANCE", "AGREED", VOICES), HAYW=("HOLD-FOR-CONDITIONS", "CONTESTED", ["oneil", "seow"]),
                    CUBE=("PASS", "DROPPED", []))
    rows = {r[1]: r for r in rows_of(PC._top20_panel(D, cons))}
    assert "ADVANCE" in rows["RYAN"][6] and "AGREED" in rows["RYAN"][6] and rows["RYAN"][7] == ", ".join(VOICES)
    assert "WATCH" in rows["HAYW"][6] and "HOLD" not in rows["HAYW"][6] and rows["HAYW"][7] == "oneil, seow"       # HOLD-FOR-CONDITIONS reads WATCH
    assert "PASS" in rows["CUBE"][6] and rows["CUBE"][7] == "no voice supported it"
    assert "not in the room" in rows["DLTR"][6] and rows["DLTR"][7] == "&mdash;"
    assert sum(1 for r in rows.values() if "not in the room" in r[6]) == 17


def test_fewer_than_twenty_ranked_or_none_is_declared_not_padded():
    small = {"daily_list": D["daily_list"][:5], "srm": D["srm"]}
    html = PC._top20_panel(small, [])
    assert len(rows_of(html)) == 5 and "Only 5 ranked names are in today" in html
    assert "declared gap, nothing invented" in PC._top20_panel({"daily_list": []}, [])
    unranked = {"daily_list": [{"ticker": "AAA", "gics_sector_name": "Utilities"}], "srm": []}
    assert "declared gap" in PC._top20_panel(unranked, [])


def test_the_table_is_the_very_last_section_of_the_rendered_cards():
    src = (ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards.py").read_text()
    i_top, i_caveats, i_foot = src.index("o.append(_top20_panel(D, cons))"), src.index('Read with care</div>'), src.index('<div class="foot">DRAFT')
    assert i_caveats < i_top < i_foot
