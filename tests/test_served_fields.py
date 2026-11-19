"""NOT_SERVED audit (PM 2026-11-19: "if a seat's required data is not served, that is an engineering fix"). Offline.

Causes found on the 18 and 19 Nov runs, each locked here:
  * later rounds re-served no AQE row, or only a short shared field list, so seats read cmf/adx in Round 1 and were told "not served" after;
  * round2packets skipped the momentum floor Round 1 gets;
  * the `trim` whitelist (CONSUMED) dropped export fields that a menu named;
  * seat cards declared fields NOT_SERVED that the export carries.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "aegis" / "plugin" / "aegis-core"
TOOLS = CORE / "skills" / "pma" / "tools"
MENUS = CORE / "skills" / "pma" / "contracts" / "voice_menus.json"
CHECK = CORE / "skills" / "daily-check" / "check.py"
CARDS = ROOT / "aegis" / "plugin" / "aegis-voices" / "agents"
DECIDERS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def pp():
    os.environ["AEGIS_REPORT"] = "A"
    sys.path.insert(0, str(TOOLS))
    return _load(TOOLS / "pma_pipeline.py", "pma_pipeline_sf")


@pytest.fixture(scope="module")
def ck():
    return _load(CHECK, "check_sf")


def test_every_menu_field_survives_the_trim_whitelist(pp):
    """A menu column whose root is missing from CONSUMED is nulled by `trim`: the seat is served a blank (19 Nov: raschke's hi_20d/lo_20d/nr7/stoch)."""
    menus = json.loads(MENUS.read_text())
    ok = set(pp.CONSUMED) | set(pp.HELD_FLOOR) | set(pp.MOMENTUM_SERVED) | {f.split(".")[0] for f in pp.HELD_FLOOR}
    for v in DECIDERS:
        gone = [f for f in menus[v] if f not in ok and f.split(".")[0] not in ok]
        assert not gone, f"{v}: menu fields that `trim` drops before any packet is built: {gone}"


def _universe_row(t):
    return {"ticker": t, "adx_14": 31.2, "atr_14d": 2.5, "stoch_k_14": 40.0, "stoch_d_3": 38.0, "hi_20d": 12.0, "lo_20d": 9.0, "nr4_flag": True,
            "nr7_flag": False, "bar_range_5d": [1, 2, 3, 4, 5], "hv_ratio_6_100": 0.8, "rs_rank_pct": 80.0, "ret_12m": 20.0,
            "subcomponents": {"flow": {"cmf": 0.12, "mfi": 55.0}, "energy": {"squeeze_score": 3.1}, "bq": {"bq_base_dur": 22.0, "bq_range_tight": 4.2}},
            "rvol_20d": 1.4, "elder_context": {"volume": {"avg_vol_20d": 1000000}}, "bar_low": 9.9, "ma_40": 10.1, "cci_20": 50.0}


def test_seat_rows_serve_each_seats_own_menu_and_the_floors_and_declare_a_missing_row(pp):
    menus = json.loads(MENUS.read_text())
    rows = pp._seat_rows_for(menus, [_universe_row("AAA")], "raschke", ["AAA", "ZZZ"])
    r = rows[0]["row"]
    for f in ("adx_14", "stoch_k_14", "stoch_d_3", "hi_20d", "lo_20d", "nr4_flag", "nr7_flag", "bar_range_5d", "hv_ratio_6_100", "subcomponents.energy.squeeze_score"):
        assert r.get(f) is not None, f"raschke is not served {f}"
    assert rows[1]["row"] is None and "not in candidate_set" in rows[1]["row_gap"], "a missing row is DECLARED, never dropped"
    seow = pp._seat_rows_for(menus, [_universe_row("AAA")], "seow", ["AAA"])[0]["row"]
    assert seow.get("subcomponents.flow.cmf") == 0.12 and seow.get("atr_14d") == 2.5 and seow.get("bar_low") == 9.9


def test_the_seat_rows_command_exits_nonzero_on_a_missing_ticker_and_still_writes_the_declaration(tmp_path):
    cs = tmp_path / "candidate_set.json"
    cs.write_text(json.dumps({"universe": [_universe_row("AAA")]}))
    env = dict(os.environ, AEGIS_REPORT="A")
    r = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "seat-rows", "--candidates", str(cs), "--menus", str(MENUS), "--tickers", "AAA", "ZZZ",
                        "--date", "2026-11-19", "--outdir", str(tmp_path / "sr")], capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "ZZZ" in (r.stdout + r.stderr)
    f = json.loads((tmp_path / "sr" / "seow.json").read_text())
    assert f["names"][0]["row"]["adx_14"] == 31.2 and f["names"][1]["row_gap"]
    ok = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "seat-rows", "--candidates", str(cs), "--menus", str(MENUS), "--tickers", "AAA",
                         "--date", "2026-11-19", "--outdir", str(tmp_path / "sr2")], capture_output=True, text=True, env=env)
    assert ok.returncode == 0, ok.stderr


def test_round2_packets_carry_the_momentum_floor_and_the_seats_own_menu(tmp_path):
    cs = tmp_path / "candidate_set.json"
    cs.write_text(json.dumps({"universe": [_universe_row("AAA")]}))
    (tmp_path / "phase4.json").write_text(json.dumps({"deliberation_set": ["AAA"]}))
    (tmp_path / "tally.json").write_text(json.dumps([{"ticker": "AAA", "reasons": []}]))
    for v in ("rogers", "steenbarger", "lynch", "detectlens"):
        (tmp_path / f"{v}.json").write_text(json.dumps({"voice": v, "document_text": "x"}))
    env = dict(os.environ, AEGIS_REPORT="A")
    r = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "round2packets", "--candidates", str(cs), "--menus", str(MENUS),
                        "--phase4", str(tmp_path / "phase4.json"), "--tally", str(tmp_path / "tally.json"), "--rogers", str(tmp_path / "rogers.json"),
                        "--steenbarger", str(tmp_path / "steenbarger.json"), "--lynch", str(tmp_path / "lynch.json"), "--detectlens", str(tmp_path / "detectlens.json"),
                        "--date", "2026-11-19", "--outdir", str(tmp_path / "r2")], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    rasc = json.loads((tmp_path / "r2" / "raschke.json").read_text())["names"][0]["row"]
    assert rasc["adx_14"] == 31.2 and rasc["stoch_k_14"] == 40.0 and rasc["rs_rank_pct"] == 80.0, "Round 2 must serve the same floors and menu Round 1 does"
    seow = json.loads((tmp_path / "r2" / "seow.json").read_text())["names"][0]["row"]
    assert seow["subcomponents.flow.cmf"] == 0.12 and seow["adx_14"] == 31.2


def test_a_claims_packet_row_is_sliced_to_the_reviewing_seats_own_menu(pp, tmp_path):
    menus = json.loads(MENUS.read_text())
    board = {"date": "2026-11-19", "deciders_present": ["seow"], "routing": {"seow": ["AAA-oneil-for"]},
             "names": {"AAA": {"claims": [{"claim_id": "AAA-oneil-for", "kind": "for", "author": "oneil", "text": "t"}], "mtf": None,
                               "support": [], "oppose": [], "abstain": [], "no_vote": [], "convictions": {}}}}
    pp._write_claim_packets(board, {"AAA": _universe_row("AAA")}, str(tmp_path / "cp"), menus=menus)
    row = json.loads((tmp_path / "cp" / "seow.json").read_text())["claims"][0]["row"]
    assert row["subcomponents.flow.cmf"] == 0.12 and row["bar_low"] == 9.9 and row["ma_40"] == 10.1 and row["cci_20"] == 50.0
    pp._write_claim_packets(board, {"AAA": _universe_row("AAA")}, str(tmp_path / "cp0"))
    old = json.loads((tmp_path / "cp0" / "seow.json").read_text())["claims"][0]["row"]
    assert "subcomponents.flow.cmf" not in old and "bar_low" not in old, "the old short shared list is what left cmf/bar_low unserved"


def test_the_claims_and_pair_steps_pass_the_menus_so_no_round_is_served_without_the_seats_data():
    y = (CORE / "skills" / "pma" / "RUN.yaml").read_text()
    assert "--packets-dir claims_packets --export aqe_daily_export.json --menus voice_menus.json" in y
    assert "--packets-dir tier2_packets --candidates candidate_set.json --menus voice_menus.json" in y
    assert "seat-rows" in y


def test_a_card_that_declares_a_field_not_served_while_the_export_carries_it_fails_before_the_vote(ck, tmp_path):
    export = {"daily_list": [{"ticker": "AAA", "adx_14": 20, "stoch_k_14": 50, "stoch_d_3": 50, "hi_20d": 1, "lo_20d": 1, "nr4_flag": False,
                              "nr7_flag": False, "bar_range_5d": [1, 2, 3, 4, 5], "hv_ratio_6_100": 1.0}]}
    cards = tmp_path / "agents"
    cards.mkdir()
    for v in DECIDERS:
        (cards / f"voice-{v}.md").write_text("`market_breadth: OUT_OF_SERVED_SCOPE` and `hl_trend` NOT_SERVED (the export has none)\n")
    f, n = ck.check_card_declarations(export, DECIDERS, str(cards))
    assert f == [], f
    (cards / "voice-raschke.md").write_text("`adx: NOT_SERVED (C7, C8)` · `stochastic_kd: NOT_SERVED (C6)` · `bar_range_history: NOT_SERVED (C12, C13)` · "
                                            "I declare exact_20day_extreme: NOT_SERVED\n")
    f, n = ck.check_card_declarations(export, DECIDERS, str(cards))
    assert len(f) == 4 and all(x.startswith("raschke:") for x in f), f
    assert any("adx_14" in x for x in f) and any("stoch_k_14" in x for x in f) and any("hi_20d" in x for x in f)


def test_the_real_seat_cards_declare_nothing_not_served_that_the_export_carries(ck):
    """Against the committed export: after this fix no decider card names a NOT_SERVED field that AQE exports."""
    exp = json.loads((ROOT / "aegis" / "output" / "aqe_daily_export.json").read_text())
    f, n = ck.check_card_declarations(exp, DECIDERS, str(CARDS))
    assert f == [], f


def test_a_missing_cards_dir_is_a_loud_warn_never_a_silent_pass(ck, tmp_path):
    f, n = ck.check_card_declarations({"daily_list": []}, DECIDERS, str(tmp_path / "nope"))
    assert f == [] and n and n[0].startswith("WARN card declaration check SKIPPED")
