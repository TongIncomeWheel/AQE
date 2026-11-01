"""Tests for VALEN's Parts 2-6 (pieces 04-20): src/valen/selection.py,
house.py, execution.py, management.py, and daily.py's run_playbook()
integration. All pure functions of plain dicts (no pandas, no file
access) -- same blindness discipline as card.py, verified the same way.
"""

from __future__ import annotations

import inspect

from src.valen import execution, house, management, selection


def _row(**kw):
    """A minimal daily_list-shaped row; every field defaults to an
    absent/None-safe value so a test only needs to set what it's testing."""
    base = {
        "ticker": "TEST", "rs_rank_pct": None, "rs_leadership": None,
        "pipe_rank": None, "thematic_grade": None, "on_longlist": False,
        "on_elder": False, "on_qs": False, "held": False, "bracket": None,
        "ma_200": None, "extension_atr_20": None, "days_to_earnings": None,
        "sector_trend_state": None, "elder_context": None,
        "mover_subtype": None, "squeeze_breakout_state": None,
        "pin_bar_state": None, "div_state": None, "structure_shift": None,
        "premove_setup": False, "subcomponents": None, "pattern_stage": None,
        "pattern": None, "squeeze_breakout_volume_confirmed": None,
    }
    base.update(kw)
    return base


# ------------------------------------------------------------------ blindness


def test_modules_render_from_their_arguments_alone():
    for mod in (selection, house, execution, management):
        src = inspect.getsource(mod)
        for banned in ("import pandas", "import numpy", "open(", "read_parquet",
                      "read_csv", "requests", "sqlite3", "from src.data",
                      "Path("):
            assert banned not in src, f"{mod.__name__} found {banned!r}"


# --------------------------------------------------------------- piece 04 RS


def test_relative_strength_leaders_ranks_by_rs_rank_pct_desc():
    rows = [_row(ticker="A", rs_rank_pct=50.0), _row(ticker="B", rs_rank_pct=99.0),
           _row(ticker="C", rs_rank_pct=None)]
    out = selection.relative_strength_leaders(rows)
    assert [r["ticker"] for r in out] == ["B", "A"]


def test_relative_strength_leaders_respects_top_n():
    rows = [_row(ticker=str(i), rs_rank_pct=float(i)) for i in range(20)]
    out = selection.relative_strength_leaders(rows, top_n=5)
    assert len(out) == 5
    assert out[0]["ticker"] == "19"


# ------------------------------------------------------------- piece 05 funnel


def test_funnel_counts_narrows_in_order():
    rows = [
        _row(ticker="A", on_longlist=True, on_elder=True, on_qs=True, held=True),
        _row(ticker="B", on_longlist=True, on_elder=False),
        _row(ticker="C"),
    ]
    stages = selection.funnel_counts(rows)
    counts = {s["stage"]: s["count"] for s in stages}
    assert counts["Scored universe"] == 3
    assert counts["On longlist"] == 2
    assert counts["On longlist AND Elder"] == 1
    assert counts["QS-scored (third lens)"] == 1
    assert counts["Held"] == 1


def test_funnel_precision_edge_not_tracked_reads_honestly():
    stages = selection.funnel_counts([_row()])
    edge = next(s for s in stages if s["stage"] == "Precision Edge")
    assert edge["count"] is None
    assert "not tracked" in edge["reason"]


def test_funnel_precision_edge_counted_when_tickers_given():
    rows = [_row(ticker="A"), _row(ticker="B")]
    stages = selection.funnel_counts(rows, edge_tickers={"A"})
    edge = next(s for s in stages if s["stage"] == "Precision Edge")
    assert edge["count"] == 1


# ------------------------------------------------------------ piece 07 no-buy


def test_no_buy_flags_below_200d():
    row = _row(bracket={"price": 90.0}, ma_200=100.0)
    flags = selection.no_buy_flags(row)
    assert any(f["flag"] == "below_200d" for f in flags)


def test_no_buy_flags_stretched_uses_frozen_threshold():
    from src.valen import spec as S
    row = _row(extension_atr_20=S.PER_STOCK_ATR_MULT_LAUNCHPAD_BELOW)
    flags = selection.no_buy_flags(row)
    assert any(f["flag"] == "stretched" for f in flags)


def test_no_buy_flags_earnings_soon():
    row = _row(days_to_earnings=2)
    flags = selection.no_buy_flags(row)
    assert any(f["flag"] == "earnings_soon" for f in flags)


def test_no_buy_flags_market_red_only_when_risk_off():
    row = _row()
    assert not selection.no_buy_flags(row, market_stance_word="RISK_ON")
    assert selection.no_buy_flags(row, market_stance_word="RISK_OFF")


def test_no_buy_flags_clean_row_is_empty():
    row = _row(bracket={"price": 100.0}, ma_200=90.0)
    assert selection.no_buy_flags(row, market_stance_word="RISK_ON") == []


def test_no_buy_list_only_flags_candidates_by_default():
    rows = [_row(ticker="A", on_longlist=True, ma_200=100.0, bracket={"price": 50.0}),
           _row(ticker="B", ma_200=100.0, bracket={"price": 50.0})]  # not a candidate
    out = selection.no_buy_list(rows)
    assert [r["ticker"] for r in out] == ["A"]


def test_no_buy_list_sorted_worst_first():
    rows = [
        _row(ticker="ONE_FLAG", on_longlist=True, ma_200=100.0, bracket={"price": 50.0}),
        _row(ticker="TWO_FLAGS", on_longlist=True, ma_200=100.0, bracket={"price": 50.0},
             days_to_earnings=1),
    ]
    out = selection.no_buy_list(rows)
    assert out[0]["ticker"] == "TWO_FLAGS"


# ---------------------------------------------------------------- Part 3 House


def _g(status, setup="VCP", piece="08"):
    return {"piece": piece, "setup": setup, "status": status, "checks": [], "fails": []}


def test_house_retired_the_detect_field_proxies():
    # PM 2026-10-05: DETECT fields are context, never called setups again.
    assert not hasattr(house, "classify_setups")
    row = _row(ticker="X", mover_subtype="tight_base", pin_bar_state="BULLISH_PIN",
               squeeze_breakout_state="BREAKOUT_UP", on_longlist=True)
    assert house.house_setups([row]) == []


def test_house_setups_reads_graded_rows_best_status_first():
    rows = [_row(ticker="F", setups=[_g("FAILED")]),
            _row(ticker="R", setups=[_g("READY")]),
            _row(ticker="T", setups=[_g("TRIGGERED", "Undercut and rally", "10")]),
            _row(ticker="N", setups=[])]
    out = house.house_setups(rows)
    assert [r["ticker"] for r in out] == ["T", "R", "F"]


def test_house_setups_includes_held_positions_for_piece_12_warnings():
    held = [{"ticker": "H", "setups": [_g("WARNING", "Failed leader — risk warning on a long", "12")]}]
    out = house.house_setups([], held)
    assert out[0]["ticker"] == "H" and out[0]["held"] is True


# ------------------------------------------------------------- Part 4 Execution


def test_entry_sequence_reads_trigger_volume_stop_in_order():
    row = _row(structure_shift="BULLISH_BOS", squeeze_breakout_volume_confirmed=True,
              bracket={"stop": 90.0, "stop_type": "structural", "risk_pct": 2.0,
                      "valid": True})
    seq = execution.entry_sequence(row)
    assert seq["trigger"] == "Break of structure (BULLISH_BOS)"
    assert seq["volume_confirmed"] is True
    assert seq["stop"] == 90.0
    assert seq["bracket_valid"] is True


def test_entry_candidates_excludes_rows_with_no_trigger():
    rows = [_row(ticker="A", on_longlist=True, bracket={"stop": 1}),
           _row(ticker="B", on_longlist=True, structure_shift="BULLISH_BOS",
                bracket={"stop": 1})]
    out = execution.entry_candidates(rows)
    assert [e["ticker"] for e in out] == ["B"]


def test_stop_breach_unknown_without_data():
    assert execution.stop_breach({"ticker": "X"})["status"] == "UNKNOWN"


def test_stop_breach_true_when_live_at_or_below_stop():
    row = {"ticker": "X", "held_sl": 100.0, "live_px": 99.0}
    out = execution.stop_breach(row)
    assert out["status"] == "OK"
    assert out["breached"] is True


def test_stop_breach_false_when_live_above_stop():
    row = {"ticker": "X", "held_sl": 100.0, "live_px": 105.0}
    assert execution.stop_breach(row)["breached"] is False


# ------------------------------------------------------------ Part 5/6 Mgmt


def test_held_position_facts_r_multiple_and_distance():
    import datetime
    row = {"ticker": "X", "entry": 100.0, "live_px": 110.0, "held_sl": 95.0,
          "qty": 10, "unreal_usd": 100.0, "trade_date": "2026-09-01"}
    facts = management.held_position_facts(row, today=datetime.date(2026, 9, 11))
    assert facts["r_multiple"] == 2.0          # (110-100)/(100-95)
    assert facts["r_multiple_is_approx"] is True
    assert facts["dist_from_stop_pct"] == round((110 - 95) / 110 * 100, 2)
    assert facts["days_held"] == 10


def test_held_position_facts_missing_stop_gives_no_r_multiple():
    facts = management.held_position_facts({"ticker": "X", "entry": 100.0, "live_px": 110.0})
    assert facts["r_multiple"] is None
    assert facts["r_multiple_is_approx"] is False


def test_held_position_facts_bad_trade_date_degrades_to_none():
    facts = management.held_position_facts({"ticker": "X", "trade_date": "not-a-date"})
    assert facts["days_held"] is None


def test_held_book_facts_maps_every_row():
    rows = [{"ticker": "A"}, {"ticker": "B"}]
    out = management.held_book_facts(rows)
    assert [f["ticker"] for f in out] == ["A", "B"]



# ---- PM 2026-11-01, weather-spec item 6 (items 1-2): readings + quoted doctrine, never a call ----
def _art(green, status="OK"):
    return {"breadth": {"net_high_low": {"status": status, "avg8": 12.5 if green else 3.0, "avg20": 8.0, "green": green,
                                          "latest_net": 15, "population": "aqe_panel", "reason": None if status == "OK" else "fewer than 40 sessions"}}}


def test_manage_note_reads_the_net_new_highs_switch_both_ways():
    g = management.manage_note(_art(True)); r = management.manage_note(_art(False))
    assert g["status"] == "OK" and g["state"] == "ABOVE" and "rewarded" in g["note"] and g["avg8"] == 12.5
    assert r["status"] == "OK" and r["state"] == "BELOW" and "tighten side" in r["note"]
    for x in (g, r):
        assert x["is_decision"] is False and "quoted doctrine" in x["doctrine"] and "panel" in x["note"]


def test_manage_note_is_loud_when_the_row_is_missing():
    assert management.manage_note(None)["status"] == "UNAVAILABLE"
    u = management.manage_note(_art(True, status="UNAVAILABLE"))
    assert u["status"] == "UNAVAILABLE" and "40 sessions" in u["reason"]


def test_trim_trail_facts_are_facts_plus_doctrine():
    row = {"ticker": "MP", "entry": 53.0, "live_px": 61.0, "held_sl": 49.0, "held_tp1": 60.0, "ma_20": 58.0, "qty": 300, "trade_date": "2026-10-01"}
    f = management.trim_trail_facts(row)
    assert f["r_multiple"] == 2.0 and f["r_multiple_2r_or_more"] is True
    assert f["tp1_printed"] is True and f["above_ma_20"] is True and abs(f["pct_vs_ma_20"] - 5.17) < 0.01
    assert f["is_decision"] is False and set(f["doctrine"]) == {"trim", "trail", "add"} and f["gaps"] == []
    bare = management.trim_trail_facts({"ticker": "X", "entry": 10.0, "live_px": 11.0})
    assert bare["tp1_printed"] is None and bare["above_ma_20"] is None and sorted(bare["gaps"]) == ["held_sl", "held_tp1", "ma_20"]


def test_management_text_never_recommends():
    import inspect
    src = inspect.getsource(management)
    # the module docstring explains that it never recommends (and so uses the word); the doctrine quotes are the
    # handbook's words -- check the computing code between them
    body = src.split("def _days_held")[1].split("TRIM_TRAIL_DOCTRINE")[0]
    for word in ("should trim", "should trail", "recommend", "we advise", "cut the position"):
        assert word not in body.lower()


def test_run_playbook_carries_manage_note_and_trim_trail():
    from src.valen import daily
    export = {"daily_list": [], "held_positions": [{"ticker": "MP", "entry": 53.0, "live_px": 61.0, "held_sl": 49.0, "held_tp1": 60.0, "ma_20": 58.0}]}
    out = daily.run_playbook(export, valen_artifact=_art(True))
    mg = out["management"]
    assert mg["manage_note"]["status"] == "OK" and mg["trim_trail"][0]["ticker"] == "MP"
    from src.valen import card
    blk = card.management_block({"management": mg})
    assert blk["manage_note"]["state"] == "ABOVE" and len(blk["trim_trail"]) == 1
