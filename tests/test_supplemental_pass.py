"""A SAME-DATE supplemental committee pass (run 2026-11-05-r3, PM 2026-11-05) is loaded into the live alert levels ADDITIVELY and labelled.
Real r3 files (committed under aegis/output/pma/run/2026-11-05-r3/); the base file is built in the test so it cannot drift."""
import importlib.util
import json
from pathlib import Path

import pytest

from src.alerts import condition_defaults as D
from src.alerts import condition_evaluator as CE
from src.alerts import emailer as EM
from src.alerts import pma_levels as PL

ROOT = Path(__file__).resolve().parents[1]
R3 = ROOT / "aegis/output/pma/run/2026-11-05-r3"
spec = importlib.util.spec_from_file_location("pma_levels_tool", ROOT / "aegis/plugin/aegis-core/skills/pma/tools/pma_levels.py")
LV = importlib.util.module_from_spec(spec); spec.loader.exec_module(LV)

ORIGIN = "2026-11-05-r3"


def _base():
    """A published 5 Nov file in miniature: one live ADVANCE row, the HELD V row carrying the same shared line as r3's V, a market kill."""
    adv = {"ticker": "KO", "class": "ADVANCE", "lane": "MOMENTUM", "triggers": [{"id": "2026-11-05:KO-buy0", "kind": "close_above", "level": 96.56,
           "basis": "15m", "priority": "ACTION", "action": "KO buy"}], "origin_run": "2026-11-05", "age_sessions": 0}
    v = {"ticker": "V", "class": "HELD", "triggers": [{"id": "2026-11-05:V-stopnear", "kind": "within_atr_of", "level": 400.0, "basis": "15m",
         "priority": "WARN", "action": "near stop"}], "origin_run": "2026-11-05", "age_sessions": 0,
         "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 436.76, "seats": [], "plain": "x", "when": "1H", "x": None}]}}}
    return {"schema": "pma_levels.v1", "run_date": "2026-11-05", "session": "2026-11-05", "rows": [adv, v],
            "counts": {"ADVANCE": 1, "HELD": 1, "carried": 0}, "market_kill": {"plain": "x", "level": None, "origin_run": "2026-11-05"}}


def _merge(base=None):
    cons = json.loads((R3 / "consensus.json").read_text())
    br = json.loads((R3 / "brackets.json").read_text())["brackets"]
    md = LV.parse_conditions_md((R3 / "conditions.md").read_text())
    cut = LV._cut_reasons((R3 / "supplement_summary.md").read_text())
    adv, watch, notes = LV.supplement_rows(cons, br, md, None, ORIGIN, cut)
    return LV.merge_supplement(base or _base(), adv, watch, ORIGIN), adv, watch, notes


def test_conditions_md_is_read_for_the_shared_line_volume_and_exits():
    md = LV.parse_conditions_md((R3 / "conditions.md").read_text())
    adp = md["ADP"]
    assert adp["buy"]["level"] == 309.4 and adp["buy"]["ref"] == "pivot_high" and adp["buy"]["n"] == 4 and "livermore" in adp["buy"]["seats"]
    assert adp["confirm"] == [1.4] and adp["exits"][0][0] == 296.16 and adp["chase_level"] == ("pivot_high+1atr", 316.78)
    assert md["V"]["verdict"] == "HOLD-FOR-CONDITIONS" and md["V"]["buy"]["level"] == 436.76 and md["V"]["confirm"] == [1.2, 1.4]


def test_the_merge_is_additive_and_leaves_every_published_row_byte_identical():
    base = _base()
    doc, adv, watch, notes = _merge(base)
    assert doc["rows"][:2] == base["rows"]                              # published rows, ids and stops untouched
    assert doc["market_kill"] == base["market_kill"]
    assert [r["ticker"] for r in adv] == ["ADP", "PK", "SONY", "V"] and len(watch) == 17
    added = {r["ticker"]: r for r in doc["rows"][2:]}
    assert set(added) == {"ADP", "PK", "SONY"} | {w["ticker"] for w in watch}
    assert all(r["supplemental"] and r["origin_run"] == ORIGIN and r["supplemental_label"] == "supplemental committee pass" for r in added.values())
    assert doc["supplement"]["already_published_kept_as_is"] == [{"ticker": "V", "published_class": "HELD", "supplemental_class": "HOLD_FOR_CONDITIONS", "same_shared_buy_line": True}]
    ids = [x["id"] for r in doc["rows"] for x in r["triggers"]]
    assert len(ids) == len(set(ids)) and all(i.startswith(f"{ORIGIN}:") for r in added.values() for i in [x["id"] for x in r["triggers"]])
    assert LV.validate(json.loads(json.dumps(doc))) == []               # the real contract passes
    assert doc["counts"]["ADVANCE"] == 4 and doc["counts"]["WATCH"] == 17


def test_the_advance_rows_carry_the_committee_line_volume_and_the_bracket():
    doc, *_ = _merge()
    adp = next(r for r in doc["rows"] if r["ticker"] == "ADP")
    buy = next(x for x in adp["triggers"] if x["id"].endswith("ADP-buy0"))
    assert buy["kind"] == "close_above" and buy["level"] == 309.4 and buy["volume_min_x"] == 1.4
    assert adp["levels"]["stop"] == 296.16 and adp["levels"]["tp"][0] == 309.4 and adp["levels"]["rr_to_tp2"] == 2.76
    assert adp["committee_status"] == "CONTESTED" and len(adp["committee_objections"]) == 2
    assert {"voice", "objection", "would_clear"} <= set(adp["committee_objections"][0])


def test_rejected_and_unslated_names_say_why():
    doc, _a, watch, _n = _merge()
    by = {w["ticker"]: w for w in watch}
    assert by["NCNO"]["committee_result"].startswith("dropped by the committee (5 objections)") and len(by["NCNO"]["committee_objections"]) == 5
    assert by["LTH"]["committee_result"] == "not slated: cut by claims" and by["EL"]["committee_result"] == "not slated: cut by timing"
    assert all(w["triggers"] == [] and w["brief_watch"] for w in watch)


def test_a_verdict_without_a_parseable_shared_line_is_not_loaded_and_says_so():
    cons = json.loads((R3 / "consensus.json").read_text())
    adv, _w, notes = LV.supplement_rows(cons, {}, {}, None, ORIGIN, {})
    assert adv == [] and any("ADP" in n and "not loaded" in n for n in notes)


def test_a_broken_contract_is_refused_not_written(tmp_path):
    doc, *_ = _merge()
    bad = next(r for r in doc["rows"] if r["ticker"] == "ADP")
    bad["triggers"] = []                                                 # an ADVANCE that would silently never be watched
    assert any("ADP" in e for e in LV.validate(json.loads(json.dumps(doc))))


def test_supplemental_rows_count_as_the_latest_run_but_carried_rows_do_not():
    doc, *_ = _merge()
    adp = next(r for r in doc["rows"] if r["ticker"] == "ADP")
    assert PL.is_latest_run_row(doc, adp) is True
    assert PL.is_latest_run_row(doc, dict(adp, supplemental=False)) is False        # an unlabelled other-run row is still dropped
    assert PL.is_latest_run_row(doc, dict(adp, carried=True)) is False


def test_the_committee_line_evaluates_on_a_supplemental_row():
    doc, *_ = _merge()
    adp = next(r for r in doc["rows"] if r["ticker"] == "ADP")
    live = {"price": 310.0, "last_hourly_close": 309.8, "vol_x": {"so_far": 1.6}}
    import datetime as dt
    now = dt.datetime(2026, 11, 5, 11, 0)
    r = CE.evaluate_conditions(adp, live, now)
    assert r["buy_met"] is True and r["n_counting"] == 0
    r2 = CE.evaluate_conditions(adp, dict(live, vol_x={"so_far": 0.9}), now)
    assert r2["buy_met"] is False                                        # the volume confirmation is enforced


def test_the_alert_labels_say_supplemental_committee_pass_and_why():
    adv = {"supplemental": True, "supplemental_label": "supplemental committee pass", "class": "ADVANCE"}
    assert EM._who(adv) == "Committee (ADVANCE) · supplemental committee pass"
    lst = {"aqe_list": True, "aqe_default": True, "supplemental": True, "supplemental_label": "supplemental committee pass",
           "committee_result": "dropped by the committee (5 objections)"}
    assert EM._who(lst) == "AQE list, not a committee pick · supplemental committee pass: dropped by the committee (5 objections)"
    assert EM._supp_tag({"class": "ADVANCE"}) == ""


def test_dropped_and_unslated_names_are_watched_under_aqe_defaults_and_labelled(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_ENABLED", True)
    monkeypatch.setattr(C, "CONDITION_DEFAULT_SOURCES", "brief_lists")
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_INCLUDE_WATCH", False)
    monkeypatch.setattr(C, "CONDITION_MAX_WATCHED", 120)
    doc, *_ = _merge()
    rec = lambda tk: {"ticker": tk, "entry": 100.0, "atr_14d": 2.0, "last_pivot_high": {"price": 102.0}, "prior_bar_high": 101.0,
                      "on_longlist": False, "on_elder": False, "held": False,
                      "bracket": {"valid": True, "stop": 97.0, "targets": [{"price": 105.0}]}}
    export = {"daily_list": [rec("NCNO"), rec("LTH"), rec("ZZZ")], "held_positions": []}
    rows = {r["ticker"]: r for r in D.synthesize_rows(export, doc)}
    assert set(rows) == {"NCNO", "LTH"}                                  # ZZZ is on no list: not watched
    n = rows["NCNO"]
    assert n["aqe_list"] and n["aqe_default"] and n["supplemental"] and n["origin_run"] == ORIGIN
    assert n["committee_result"].startswith("dropped by the committee (5 objections)") and n["levels"]["stop"] == 97.0
    assert rows["LTH"]["committee_result"] == "not slated: cut by claims"
    assert "Swing pivot" in n["on_lists"]


def test_swing_pivot_is_the_fourth_brief_list_bounded_and_absent_on_an_older_export(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "BRIEF_LIST_ELDER_N", 0); monkeypatch.setattr(C, "BRIEF_LIST_AQE_N", 0); monkeypatch.setattr(C, "BRIEF_LIST_LENS_N", 0)
    monkeypatch.setattr(C, "BRIEF_LIST_SWING_N", 2)
    dl = [{"ticker": f"T{i}", "rank": i, "swing_pivot": i != 2} for i in range(1, 6)]
    on = D.brief_list_names({"daily_list": dl})
    assert on == {"T1": ["Swing pivot"], "T3": ["Swing pivot"]}          # by AQE rank, bounded, T2 (swing_pivot false) out
    older = D.brief_list_names({"daily_list": [{"ticker": "A", "rank": 1}]})
    assert all("Swing pivot" not in v for v in older.values())
