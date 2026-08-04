"""QS card renderer tests.

The first test is the important one. `qs_card` must stay BLIND — able to draw
a card from the export and nothing else. That is what guarantees the daily
file is self-sufficient: if a number can reach a card without being in the
file, the file has stopped being the source of truth and prose can make
claims nobody can audit. Enforcing it by inspection means the guarantee
survives future edits, rather than being a comment someone breaks in a year.
"""

from __future__ import annotations

import inspect

import pytest

from src.engines import qs_card


def _row(**over):
    row = {
        "ticker": "CAH", "on_qs": True,
        "bracket": {"valid": True, "stop": 219.40, "stop_type": "swing_low",
                    "risk_pct": 3.8,
                    "targets": [{"tp": "TP1", "price": 236.10, "r": 1.9,
                                 "type": "swing_high"}]},
        "qs": {
            "rank": 1, "signal": "STRONG", "conviction": 5,
            "conviction_word": "very high",
            "state": {"code": "READY+", "plain": "still qualifying today",
                      "test_hit_rate": 0.731},
            "odds": {"p": 0.71, "market_avg": 0.446, "n_analogues": 733,
                     "bucket": "8+|6-7|4-5", "bucket_kind": "3-D"},
            "objective": {"now": 228.03, "target_2atr": 238.65,
                          "target_pct": 4.7, "give_up_2atr": 217.41},
            "path": {"usual_days": 8.0, "typical_dip_pct": 3.9},
            "engine": {"recipe_hits": 17, "qs_persist": 4, "lens_total": 6.1,
                       "lens": {"structure": 6.7, "coil": 6.2, "momentum": 8.0,
                                "flow": 4.8, "leadership": 5.0},
                       "components": {"en_pos50": 76, "rs_consist": 0.47}},
            "vetoes": [],
        },
    }
    row.update(over)
    return row


MARKET = {"description": "Hot, fast, wild bull run",
          "avg_stock_hits_target": 0.446, "action": "Expect swings.",
          "regime_code": "T3V3 / PRESS_EXPECT_WHIPSAW",
          "stance": "PRESS_EXPECT_WHIPSAW"}


# --------------------------------------------------------- the blindness test

def test_renderer_cannot_reach_outside_the_export():
    """No data libraries, no file access, no engine imports.

    If this fails, the card can show a number the daily file does not
    contain — and the file has stopped being reconstructible.
    """
    src = inspect.getsource(qs_card)
    for banned in ("import pandas", "import numpy", "open(", "read_parquet",
                   "read_csv", "requests", "sqlite3", "json.load",
                   "from src.data", "from src.scanner", "Path("):
        assert banned not in src, (
            f"qs_card must render from its arguments alone — found {banned!r}")


def test_render_card_needs_only_a_row_and_market():
    out = qs_card.render_card(_row(), MARKET)
    assert "CAH" in out and "71%" in out and "READY+" in out


# ------------------------------------------------------- honest failure modes

def test_missing_path_stats_states_the_reason_rather_than_inventing():
    r = _row()
    r["qs"]["path"] = {}
    r["qs"]["odds"]["bucket_kind"] = "2-D fallback"
    out = qs_card.render_card(r, MARKET)
    assert "no path stats" in out
    assert "usually takes" not in out
    assert "typically dips" not in out


def test_invalid_bracket_says_so_and_prints_no_levels():
    r = _row(bracket={"valid": False, "invalid_reason": "no qualifying level"})
    out = qs_card.render_card(r, MARKET)
    assert "no valid structural bracket" in out
    assert "no qualifying level" in out
    assert "TP1" not in out


def test_unevaluable_veto_is_a_flagged_gap_not_a_silent_pass():
    """A veto that could not be evaluated must never look like one that passed."""
    r = _row()
    r["qs"]["unevaluable_vetoes"] = ["jumpy path + volume noise"]
    out = qs_card.render_card(r, MARKET)
    assert "DATA GAP" in out
    assert "NOT a pass" in out


def test_vetoed_name_is_shown_with_the_veto_named():
    r = _row()
    r["qs"]["vetoes"] = ["fading laggard"]
    r["qs"]["conviction"] = 0
    r["qs"]["conviction_word"] = "vetoed"
    out = qs_card.render_card(r, MARKET)
    assert "VETOED" in out and "fading laggard" in out


def test_row_without_qs_block_degrades_gracefully():
    out = qs_card.render_card({"ticker": "ZZZ"}, MARKET)
    assert "not scored by QS" in out


def test_missing_components_render_as_dashes_not_crashes():
    r = _row()
    r["qs"]["engine"]["components"] = {}
    out = qs_card.render_card(r, MARKET)
    assert "--" in out


# ------------------------------------------------ the two level sets stay apart

def test_objective_is_labelled_as_what_the_probability_refers_to():
    """The 2ATR objective and the structural bracket must not read as one set."""
    out = qs_card.render_card(_row(), MARKET)
    assert "OBJECTIVE" in out and "LEVELS" in out
    assert "refers to" in out
    # the structural ladder is explicitly marked as the tradeable one
    assert "tradeable" in out


# ------------------------------------------------------------------ the sheet

def test_sheet_only_renders_qs_flagged_rows():
    rows = [_row(), _row(ticker="NOPE", on_qs=False)]
    out = qs_card.render_sheet(rows, MARKET)
    assert "CAH" in out and "NOPE" not in out


def test_sheet_orders_by_qs_rank():
    a, b = _row(ticker="AAA"), _row(ticker="BBB")
    a["qs"]["rank"], b["qs"]["rank"] = 2, 1
    out = qs_card.render_sheet([a, b], MARKET)
    assert out.index("BBB") < out.index("AAA")


def test_empty_sheet_says_so_rather_than_rendering_nothing():
    out = qs_card.render_sheet([], MARKET)
    assert "No QS names cleared the noise rule" in out


def test_stand_down_market_is_called_out():
    m = dict(MARKET, stance="STAND_DOWN")
    assert "STAND DOWN" in qs_card.render_market(m)


def test_market_block_survives_a_missing_regime():
    assert "no regime block" in qs_card.render_market({})
