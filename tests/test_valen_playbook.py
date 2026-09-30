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


def test_house_vcp_setup_detected():
    row = _row(elder_context={"vcp": {"vcp_label": "VCP_SETUP"}})
    tags = house.classify_setups(row)
    assert any(t["piece"] == "08" for t in tags)


def test_house_momentum_breakout_from_mover_subtype():
    row = _row(mover_subtype="tight_base")
    tags = house.classify_setups(row)
    assert any(t["piece"] == "09" for t in tags)


def test_house_momentum_breakout_from_squeeze_state():
    row = _row(squeeze_breakout_state="BREAKOUT_UP")
    tags = house.classify_setups(row)
    assert any(t["piece"] == "09" for t in tags)


def test_house_undercut_and_rally_from_pin_bar():
    row = _row(pin_bar_state="BULLISH_PIN")
    tags = house.classify_setups(row)
    assert any(t["piece"] == "10" for t in tags)


def test_house_undercut_and_rally_from_div_and_bos():
    row = _row(div_state="BULLISH", structure_shift="BULLISH_BOS")
    tags = house.classify_setups(row)
    assert any(t["piece"] == "10" for t in tags)


def test_house_episodic_pivot_is_labelled_technical_fingerprint_only():
    row = _row(premove_setup=True, mover_subtype="explosive")
    tags = house.classify_setups(row)
    ep = next(t for t in tags if t["piece"] == "11")
    assert "technical fingerprint" in ep["name"].lower()
    assert "no catalyst" in ep["detail"].lower() or "no catalyst" in ep["detail"]


def test_house_exhaustion_risk_below_threshold():
    from src.valen import spec as S
    row = _row(subcomponents={"energy": {"exhaustion_score": S.EXHAUSTION_SCORE_WATCH_BELOW - 1}})
    tags = house.classify_setups(row)
    assert any(t["piece"] == "12" for t in tags)
    detail = next(t for t in tags if t["piece"] == "12")["detail"]
    assert "not a short signal" in detail


def test_house_exhaustion_at_baseline_is_not_flagged():
    from src.valen import spec as S
    row = _row(subcomponents={"energy": {"exhaustion_score": S.EXHAUSTION_SCORE_MAX}})
    tags = house.classify_setups(row)
    assert not any(t["piece"] == "12" for t in tags)


def test_house_clean_row_has_no_tags():
    assert house.classify_setups(_row()) == []


def test_house_setups_filters_to_candidates_by_default():
    rows = [_row(ticker="A", on_qs=True, pin_bar_state="BULLISH_PIN"),
           _row(ticker="B", pin_bar_state="BULLISH_PIN")]
    out = house.house_setups(rows)
    assert [r["ticker"] for r in out] == ["A"]


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
