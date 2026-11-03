"""Per-voice data coverage (PM 2026-11-03): each decider's charter-required fields against its packet.

Real packets: tests/fixtures/voice_coverage_real/ holds 30 rows of each decider's packet from the 3 Nov nightly run
(the held name MP and the names the committee flagged, RHI and PK, are in them) and 3 real export rows. Seeded
failures prove each bucket: NOT SERVED, AQE GAP, OFF MY MENU, CONDITIONAL, a waived known gap, and a new one.
"""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "voice_coverage_real"
CORE = ROOT / "aegis" / "plugin" / "aegis-core"
CHECK_PY = CORE / "skills" / "daily-check" / "check.py"
CONTRACT = CORE / "contracts" / "voice_coverage.json"
DECIDERS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


C = _load(CHECK_PY, "check_cov")
BUILD = _load(CORE / "tools" / "build_voice_coverage.py", "build_cov")


@pytest.fixture()
def work(tmp_path):
    pk = tmp_path / "packets"
    shutil.copytree(FIX / "packets", pk)
    exp = json.loads((FIX / "export_columns.json").read_text())
    return tmp_path, pk, exp


def cov(pk, exp, contract=CONTRACT, room=None, voices=DECIDERS):
    return C.check_voice_coverage(str(pk), exp, voices, str(contract), room=room)


def edit_packet(pk, voice, fn):
    """fn(header: list[str], rows: list[list[str]]) -> (header, rows); comment lines are kept."""
    p = pk / f"{voice}.tsv"
    lines = p.read_text(encoding="utf-8").split("\n")
    com = [l for l in lines if l.startswith("#")]
    body = [l.split("\t") for l in lines if l.strip() and not l.startswith("#")]
    hdr, rows = fn(body[0], body[1:])
    p.write_text("\n".join(com + ["\t".join(hdr)] + ["\t".join(r) for r in rows]) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------- the contract
def test_the_required_fields_in_the_contract_match_the_canon_locks():
    """A changed canon can never leave the check reading a stale requirement list."""
    contract = json.loads(CONTRACT.read_text())
    for v in DECIDERS:
        assert contract["required_fields"][v] == BUILD.required_fields(v), v


def test_every_standing_item_is_real_and_carries_a_written_reason():
    """No placeholder waivers: each standing gap, alias and capability names something a recogniser reads and says WHY."""
    contract = json.loads(CONTRACT.read_text())
    assert "known_gaps" not in contract
    for v, gaps in contract["standing"].items():
        assert set(gaps) <= set(contract["required_fields"][v]), f"{v}: a standing item no recogniser reads"
        for f, why in gaps.items():
            assert len(why) > 40 and "snapshot" not in why.lower() and "PM to confirm" not in why, f"{v}.{f}: not a real reason"
    for v, al in contract["served_as"].items():
        assert set(al) <= set(contract["required_fields"][v])
        assert all(a["as"] and len(a["why"]) > 30 for a in al.values())
    assert contract["conditional_blank"] and all(r for r in contract["conditional_blank"].values())
    for v, items in contract["declared_unavailable"].items():
        for it in items:
            assert len(contract["capabilities"][v][it["id"]]) > 60, f"{v} {it['id']}: NOT_AVAILABLE recogniser with no written reason"


def test_the_not_available_recognisers_are_extracted_from_the_canon_locks():
    """The 3 Nov blind spot: elder-lens R1-R6 carry an empty `fields:` and an `if:` that says NOT_AVAILABLE."""
    got = {i["id"] for i in BUILD.declared_unavailable("elder-lens")}
    assert got == {"R1", "R2", "R3", "R4", "R5", "R6"}
    assert any("fitted moving-average channel" in i["needs"] for i in BUILD.declared_unavailable("elder-lens"))
    assert all(BUILD.declared_unavailable(v) == [] for v in DECIDERS if v != "elder-lens")


# --------------------------------------------------------------------------- the real packets pass
def test_real_packets_pass_with_the_standing_gaps_named_and_waived(work):
    _, pk, exp = work
    fails, notes, rep = cov(pk, exp)
    assert fails == [], fails
    assert set(rep) == set(DECIDERS)
    # the 3 Nov evidence: seow's index_pct_change_63d is a DATA gap, listed on every run, waived not hidden
    # R8 is now SERVED: the index return rides every row beside ret_63d
    assert "index_pct_change_63d" not in rep["seow"]["not_served_known"]
    assert "index_pct_change_63d" not in rep["seow"]["not_served_new"]
    # the canon's names for columns the packet carries under another name
    assert "rvol=day_vol" in rep["oneil"]["served_as"] and "stop=bracket.stop" in rep["seow"]["served_as"]
    assert "macro_brief" in rep["oneil"]["not_served_known"]
    seow = next(n for n in notes if n.startswith("WARN voice coverage seow:") and "standing" in n)
    assert "portfolio_value" in seow and "industry_group_pct_change_63d" in seow
    # and the six Elder recognisers the canon itself declares NOT_AVAILABLE are named on every run
    assert rep["elder-lens"]["capabilities_not_served"] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    el = next(n for n in notes if n.startswith("WARN voice coverage elder-lens:"))
    assert "CAPABILITY NOT SERVED (canon says NOT_AVAILABLE): R1, R2, R3, R4, R5, R6" in el


def test_off_my_menu_is_a_menu_choice_and_never_a_gap(work):
    _, pk, exp = work
    fails, notes, rep = cov(pk, exp)
    assert "hl_score" in rep["oneil"]["off_my_menu"] and "hl_score" in rep["wyckoff"]["off_my_menu"]
    assert "held" in rep["elder-lens"]["off_my_menu"] and "bracket" in rep["elder-lens"]["conditional"]
    assert not any("hl_score" in f for f in fails)
    line = next(n for n in notes if "voice coverage minervini:" in n and "off my menu" in n)
    assert "a menu choice, not a gap" in line


def test_the_same_field_is_a_menu_choice_if_aqe_exports_it_and_a_gap_if_it_does_not(work):
    """hl_score is off every menu. AQE exports it, so it is a menu choice. Take it out of the export and it
    becomes an AQE gap that blocks: the bucket depends on the data, not on the label."""
    _, pk, exp = work
    assert cov(pk, exp)[0] == []
    gone = copy.deepcopy(exp)
    for r in gone["daily_list"] + gone["held_positions"]:
        r.pop("hl_score", None)
    fails, _, _ = cov(pk, gone)
    assert any(f.startswith("oneil: hl_score -- AQE GAP") for f in fails), fails
    assert any(f.startswith("wyckoff: hl_score -- AQE GAP") for f in fails)


# -------------------------------------------------------------------------- seeded blocking gaps
def test_a_column_on_the_menu_that_vanishes_from_the_packet_blocks(work):
    _, pk, exp = work
    edit_packet(pk, "wyckoff", lambda h, rows: (
        [c for i, c in enumerate(h) if c != "base_low_20d"],
        [[x for i, x in enumerate(r) if h[i] != "base_low_20d"] for r in rows]))
    fails, _, _ = cov(pk, exp)
    assert any(f.startswith("wyckoff: base_low_20d -- NOT SERVED: on the menu but no such column") for f in fails), fails
    assert "put it in contracts/voice_coverage.json `standing` with a written reason" in fails[0]


def test_a_menu_column_blank_for_every_name_blocks_but_only_some_blank_does_not(work):
    _, pk, exp = work
    def blank_all(h, rows):
        i = h.index("pos_in_50d_range_pct")
        for r in rows:
            r[i] = ""
        return h, rows
    edit_packet(pk, "wyckoff", blank_all)
    fails, _, _ = cov(pk, exp)
    assert any(f.startswith("wyckoff: pos_in_50d_range_pct -- NOT SERVED: blank for all 30 names in the packet") for f in fails), fails
    # blank for just PK and RHI (the 3 Nov evidence): served, listed by name, no block
    fresh = work[0] / "fresh"
    shutil.copytree(FIX / "packets", fresh)
    def blank_two(h, rows):
        i = h.index("base_low_20d")
        for r in rows:
            if r[0] in ("PK", "RHI"):
                r[i] = ""
        return h, rows
    edit_packet(fresh, "wyckoff", blank_two)
    fails, notes, rep = cov(fresh, exp)
    assert fails == [], fails
    assert set(rep["wyckoff"]["name_blanks"]["base_low_20d"]) >= {"PK", "RHI"}
    assert any("voice coverage wyckoff: name-level blanks" in n and "base_low_20d" in n for n in notes)


def test_a_conditionally_blank_field_never_blocks(work):
    """AQE glossary: bracket.* is null when no valid structural bracket exists; blanking it everywhere is not a gap."""
    _, pk, exp = work
    def blank_bracket(h, rows):
        for i, c in enumerate(h):
            if c.startswith("bracket."):
                for r in rows:
                    r[i] = ""
        return h, rows
    for v in ("raschke", "wyckoff", "minervini"):
        edit_packet(pk, v, blank_bracket)
    fails, _, rep = cov(pk, exp)
    assert fails == [], fails
    assert any(f.startswith("bracket.") for f in rep["raschke"]["conditional"])


def test_a_standing_item_without_a_reason_on_file_blocks_and_the_rest_stay_standing(work, tmp_path):
    _, pk, exp = work
    c = json.loads(CONTRACT.read_text())
    del c["standing"]["seow"]["portfolio_value"]
    cp = tmp_path / "contract.json"
    cp.write_text(json.dumps(c))
    fails, _, _ = cov(pk, exp, contract=cp)
    assert [f for f in fails if "portfolio_value" in f and f.startswith("seow:")], fails
    assert len(fails) == 1, "only the field with no written reason blocks; the rest stay standing"


def test_a_not_available_recogniser_with_no_reason_on_file_blocks_and_a_new_one_would_too(work, tmp_path):
    """The blind spot itself: a recogniser the canon declares NOT_AVAILABLE is a gap even though it names no field."""
    _, pk, exp = work
    c = json.loads(CONTRACT.read_text())
    del c["capabilities"]["elder-lens"]["R5"]
    cp = tmp_path / "c.json"
    cp.write_text(json.dumps(c))
    fails, _, _ = cov(pk, exp, contract=cp)
    assert len(fails) == 1 and fails[0].startswith("elder-lens: R5 (NOT_AVAILABLE) -- CAPABILITY NOT SERVED") and "fitted moving-average channel" in fails[0], fails
    c = json.loads(CONTRACT.read_text())
    c["declared_unavailable"]["wyckoff"] = [{"id": "R99", "needs": "price > some_new_channel -- needs a build"}]
    cp.write_text(json.dumps(c))
    fails, _, _ = cov(pk, exp, contract=cp)
    assert any(f.startswith("wyckoff: R99 (NOT_AVAILABLE)") for f in fails), fails


def test_an_alias_is_served_only_while_its_source_column_is(work):
    """rvol is served as day_vol. Blank day_vol everywhere and the alias is a gap, with the source named."""
    _, pk, exp = work
    def blank_dayvol(h, rows):
        i = h.index("day_vol")
        for r in rows:
            r[i] = ""
        return h, rows
    edit_packet(pk, "oneil", blank_dayvol)
    fails, _, _ = cov(pk, exp)
    assert any(f.startswith("oneil: rvol -- SERVED AS day_vol, but day_vol is not served") for f in fails), fails


# --------------------------------------------------------------------------------- room scoping
def test_scoped_to_the_room_the_blanks_are_the_rooms_not_the_packets(work):
    _, pk, exp = work
    _, _, all_rep = cov(pk, exp)
    fails, notes, rep = cov(pk, exp, room={"MP", "RHI", "PK"})
    assert fails == [], "a 3-name room must not fake a feed gap (elder_pattern is legitimately blank for some names)"
    assert rep["wyckoff"]["scope"] == "room" and rep["wyckoff"]["names_in_scope"] == 3
    assert all_rep["wyckoff"]["names_in_scope"] == 30
    fails, _, _ = cov(pk, exp, room={"NOT_A_NAME"})
    assert any("none of the room" in f for f in fails)


# ------------------------------------------------------------------------------------------- CLI
def _cli(*args):
    r = subprocess.run([sys.executable, str(CHECK_PY), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_the_coverage_command_exits_0_on_real_packets_and_1_on_a_new_gap(work, tmp_path):
    t, pk, exp = work
    ex = t / "export.json"
    ex.write_text(json.dumps(exp))
    p4 = t / "phase4.json"
    p4.write_text(json.dumps({"deliberation_set": ["MP", "RHI", "PK"]}))
    out = t / "cov.json"
    rc, log = _cli("coverage", "--packets-dir", str(pk), "--export", str(ex), "--phase4", str(p4), "--out", str(out))
    assert rc == 0 and "VOICE COVERAGE: Healthy" in log, log
    rep = json.loads(out.read_text())
    assert rep["seow"]["scope"] == "room" and "portfolio_value" in rep["seow"]["not_served_known"]
    edit_packet(pk, "seow", lambda h, rows: (h[:1] + h[2:], [r[:1] + r[2:] for r in rows]))   # drop a menu column
    rc, log = _cli("coverage", "--packets-dir", str(pk), "--export", str(ex))
    assert rc == 1 and "PROBLEM(S)" in log and "seow:" in log, log


def test_the_handoff_gate_runs_the_coverage_check_and_the_off_switch_is_loud(work):
    t, pk, exp = work
    out = t / "aegis" / "output"
    (out / "packets").mkdir(parents=True)
    for f in pk.iterdir():
        shutil.copy(f, out / "packets" / f.name)
    (out / "aqe_daily_export.json").write_text(json.dumps(exp))
    f, n = C.check_data(str(out), voice_contract=str(CONTRACT))[:2]
    assert any("voice coverage seow" in x for x in n), "check_data must run the per-voice coverage check"
    f, n = C.check_data(str(out), voice_contract=None)[:2]
    assert any("voice coverage check DISABLED" in x for x in n)


# ------------------------------------------------------------ held rows: why MP was blank, and the fix
def test_a_held_row_is_completed_from_the_full_record_without_overwriting_anything():
    """MP (held, not on any list) had 197 fields where a normal row has ~299: no bar_*, base_low_20d, elder_5d, lens...
    so ~10 Wyckoff and ~17 Seow fields read blank on the one name the PM owns. The fix fills only what is missing."""
    import copy
    from src.data.drive_sync import HELD_FILL_SKIP, _fill_held_rows
    exp = json.loads((FIX / "export_columns.json").read_text())
    held = exp["held_positions"][0]
    assert held["ticker"] == "MP"
    full_row = exp["daily_list"][0]                       # a real normal row = the full record shape
    before = copy.deepcopy(held)
    missing_before = {k for k in full_row if k not in held}
    assert {"bar_close", "base_low_20d", "bar_range_5d", "elder_5d", "pos_in_50d_range_pct"} <= missing_before
    res = _fill_held_rows([held], lambda tk: dict(full_row, ticker=tk))
    assert res["no_full_record"] == [] and res["keys_added"]["MP"] == len(missing_before - HELD_FILL_SKIP)
    for k, v in before.items():                           # nothing the row already had is replaced
        assert held[k] == v, k
    assert held["bar_close"] == full_row["bar_close"] and held["base_low_20d"] == full_row["base_low_20d"]
    for k in HELD_FILL_SKIP:                              # list-membership keys are never claimed
        if k not in before:
            assert k not in held, k
    again = _fill_held_rows([held], lambda tk: dict(full_row, ticker=tk))
    assert again["keys_added"]["MP"] == 0                  # idempotent


def test_a_held_name_with_no_full_record_is_declared_not_guessed():
    from src.data.drive_sync import _fill_held_rows
    rows = [{"ticker": "ZZZ", "qty": 1}, {"ticker": "YYY", "qty": 2}]

    def build(tk):
        if tk == "ZZZ":
            return None
        raise RuntimeError("no bars")
    res = _fill_held_rows(rows, build)
    assert res["no_full_record"] == ["ZZZ", "YYY"] and res["keys_added"] == {} and rows == [{"ticker": "ZZZ", "qty": 1}, {"ticker": "YYY", "qty": 2}]


def test_the_index_return_rides_every_row_beside_the_stock_return():
    """Seow R8: stock_pct_change_63d <= index_pct_change_63d. Both exist on a row, in the same unit."""
    from src.data import drive_sync
    fields = drive_sync._v21_record_fields("AAA", {}, {"spy_ret_63d": 6.2, "enrichment": {}}, {}, {})
    assert fields["index_pct_change_63d"] == 6.2
    none = drive_sync._v21_record_fields("AAA", {}, {"enrichment": {}}, {}, {})
    assert none["index_pct_change_63d"] is None
    menu = json.loads((CORE / "skills" / "pma" / "contracts" / "voice_menus.json").read_text())["seow"]
    assert "index_pct_change_63d" in menu and "ret_63d" in menu
    assert "index_pct_change_63d" in drive_sync._FIELD_GLOSSARY
