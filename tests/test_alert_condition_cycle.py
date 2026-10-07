"""Integration tests for src/alerts/condition_cycle.py (AQE handoff
D123/R21, 2026-10-02) -- the orchestration wiring between the pure
evaluator/state/ledger pieces and engine.py's cycle loop. §9's two most
load-bearing acceptance criteria live here: "shadow mode sends zero new
emails" and "a levels file without conditions behaves exactly as today."
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import condition_cycle as CC
from src.alerts import condition_state as CS

_ET = ZoneInfo("America/New_York")


class _FakeClient:
    """15-min bars shaped so a full session's worth of history makes a
    usable volume profile, and today's bars clear the shared buy level
    with normal-to-hot volume (unless `below_level=True`, for the "nothing
    fires" case)."""

    def __init__(self, below_level: bool = False):
        self.below_level = below_level

    def get_intraday_bars(self, ticker, interval="15min", from_date=None, to_date=None):
        if ticker == "SPY":
            return [{"date": "2026-10-02 09:30:00", "open": 500, "high": 501,
                     "low": 499, "close": 500.5, "volume": 100000}]
        if from_date != to_date:  # the 20-session history pull
            bars = []
            for d in range(1, 4):
                for slot in range(26):
                    mins = 9 * 60 + 30 + slot * 15
                    hh, mm = divmod(mins, 60)
                    bars.append({"date": f"2026-09-0{d} {hh:02d}:{mm:02d}:00",
                                "open": 60, "high": 61, "low": 59, "close": 60.5,
                                "volume": 1000})
            return bars
        if self.below_level:
            # four 15-min bars, one completed hourly candle, closing
            # BELOW the 62.15 shared buy level.
            return [{"date": "2026-10-02 09:30:00", "open": 60.0, "high": 60.5,
                    "low": 59.5, "close": 60.0, "volume": 2000},
                   {"date": "2026-10-02 09:45:00", "open": 60.0, "high": 60.5,
                    "low": 59.5, "close": 60.0, "volume": 2000},
                   {"date": "2026-10-02 10:00:00", "open": 60.0, "high": 60.5,
                    "low": 59.5, "close": 60.0, "volume": 2000},
                   {"date": "2026-10-02 10:15:00", "open": 60.0, "high": 60.5,
                    "low": 59.5, "close": 60.0, "volume": 2000}]
        # today's bars: four 15-min bars (one completed hourly candle),
        # closing well above the 62.15 shared buy level, double volume.
        return [{"date": "2026-10-02 09:30:00", "open": 62.0, "high": 63.0,
                "low": 61.9, "close": 62.2, "volume": 2000},
               {"date": "2026-10-02 09:45:00", "open": 62.2, "high": 63.5,
                "low": 62.1, "close": 63.0, "volume": 2000},
               {"date": "2026-10-02 10:00:00", "open": 63.0, "high": 64.0,
                "low": 62.9, "close": 63.8, "volume": 2000},
               {"date": "2026-10-02 10:15:00", "open": 63.8, "high": 64.5,
                "low": 63.7, "close": 64.2, "volume": 2000}]



@pytest.fixture(autouse=True)
def _long_card_layout(monkeypatch):
    """These tests pin the previous word-by-word card; the compact U&R-first
    layout (PM 2026-10-07) has its own tests in test_alert_compact_card.py."""
    from src.alerts import config as _C
    monkeypatch.setattr(_C, "CONDITION_CARD_STYLE", "full")

def _pma_doc_with_conditions() -> dict:
    return {
        "run_date": "2026-10-02",
        "rows": [{
            "ticker": "HPE", "class": "ADVANCE", "atr_14d": 2.0,
            "conditions": {
                "shared": {
                    "buy": [{"w": "h1_close_above", "level": 62.15}],
                    "confirm": [{"w": "vol_x_ge", "x": 1.0}],
                    "no_shared_buy": False,
                },
                "exits": [],
                "analysts": [{"seat": "minervini", "counts": True,
                             "buy": [{"w": "h1_close_above", "level": 62.15}],
                             "confirm": [{"w": "vol_x_ge", "x": 1.0}], "wrong": []}],
            },
        }],
    }


def _pma_doc_without_conditions() -> dict:
    return {"run_date": "2026-10-02",
           "rows": [{"ticker": "X", "class": "ADVANCE", "triggers": []}]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from src.alerts import condition_data as CD, condition_ledger as CL
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path / "vp")
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")   # never the repo tree
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    monkeypatch.setattr(CD, "_panel_history", lambda tickers, today: {})
    monkeypatch.setattr(CL, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(CS, "CONDITION_STATE_PATH", tmp_path / "state.json")
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC, "FMPClient", _FakeClient)


# -------------------------------------------------------------- back-compat


def test_no_conditions_anywhere_is_a_complete_noop():
    """§9: "a levels file without conditions behaves exactly as today."
    No FMP calls, no ledger line, no state entry."""
    quotes = {"X": {"price": 100.0, "prev_close": 99.0}}
    summary = CC.run_condition_cycle(_pma_doc_without_conditions(), quotes,
                                     datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["enabled"] is False
    assert summary["rows"] == 0


def test_rows_with_conditions_filters_correctly():
    assert CC.rows_with_conditions(_pma_doc_without_conditions()) == []
    assert len(CC.rows_with_conditions(_pma_doc_with_conditions())) == 1


def test_none_pma_doc_is_a_noop():
    summary = CC.run_condition_cycle(None, {}, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["enabled"] is False


# ----------------------------------------------------------- shadow mode


def test_shadow_mode_fires_the_state_but_sends_zero_emails(monkeypatch):
    """§9's acceptance rule still holds even though "live" is now the
    default (PM's own call, 2026-10-02): whenever PMA_CONDITIONS_MODE
    IS "shadow" (e.g. rolled back for a re-test), the state machine still
    advances and the ledger still gets a line, but NOTHING is emailed."""
    from src.alerts import config as C
    monkeypatch.setattr(C, "PMA_CONDITIONS_LIVE", False)

    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))

    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(_pma_doc_with_conditions(), quotes,
                                     datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["enabled"] is True
    assert "HPE" in summary["fired"]
    assert "CONDITION_MET" in summary["fired"]["HPE"]
    # _maybe_email_digest was CALLED once with HPE's card (the wiring reaches it)...
    assert len(sent) == 1
    assert [c[0] for c in sent[0][0]] == ["HPE"]
    # ...but send_condition_digest itself must never actually be invoked
    # while PMA_CONDITIONS_LIVE is False -- verified directly below.


def test_maybe_email_is_a_noop_in_shadow_mode(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "PMA_CONDITIONS_LIVE", False)
    calls = []
    monkeypatch.setattr("src.alerts.emailer.send_condition_digest",
                       lambda *a, **k: calls.append(a))
    CC._maybe_email_digest([("HPE", {}, {}, ["CONDITION_MET"], {})],
                           datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert calls == []


def test_maybe_email_sends_in_live_mode(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "PMA_CONDITIONS_LIVE", True)
    calls = []
    monkeypatch.setattr("src.alerts.emailer.send_condition_digest",
                       lambda *a, **k: calls.append(a) or {"ok": True})
    CC._maybe_email_digest([("HPE", {}, {}, ["CONDITION_MET"], {})],
                           datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert len(calls) == 1
    assert calls[0][0][0][0] == "HPE"


def test_two_rows_firing_in_one_cycle_make_one_digest_not_two_emails(monkeypatch):
    """PM 2026-10-03: no per-ticker alerts -- one email per 15-min cycle
    carrying every card that changed state."""
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    doc = _pma_doc_with_conditions()
    second = dict(doc["rows"][0], ticker="DELL")
    doc["rows"].append(second)
    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "DELL": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(doc, quotes, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert set(summary["fired"]) == {"HPE", "DELL"}
    assert len(sent) == 1
    assert sorted(c[0] for c in sent[0][0]) == ["DELL", "HPE"]


def test_analyst_out_alone_is_ledgered_but_never_becomes_a_card(monkeypatch):
    """PM 2026-10-03: "analyst fail is nonsense ... it wouldn't be
    published." The state still fires for the ledger (PMA's scorecard reads
    it); it just never produces an email card on its own."""
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC, "FMPClient", lambda: _FakeClient(below_level=True))
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    doc = _pma_doc_with_conditions()
    # buy stays unmet (bars close under 62.15); raschke's own "wrong" rule
    # (traded above 59) fires off day_high.
    doc["rows"][0]["conditions"]["analysts"].append(
        {"seat": "raschke", "counts": True, "buy": [], "confirm": [],
         "wrong": [{"w": "trade_above", "level": 59.0}]})
    quotes = {"HPE": {"price": 60.0, "prev_close": 61.0, "day_high": 60.5,
                      "day_low": 59.5, "open": 60.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(doc, quotes, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["fired"]["HPE"] == ["ANALYST_OUT"]
    assert sent == []
    assert "cards" not in summary


def test_an_aqe_default_row_is_evaluated_and_its_card_says_so(monkeypatch):
    """PM 2026-10-04: Longlist/Elder names outside the committee book ride
    the same cycle under AQE-default criteria, labelled as such."""
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_DEFAULTS_ENABLED", True)
    monkeypatch.setattr(C, "CONDITION_DEFAULT_SOURCES", "longlist,elder")
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    export = {"daily_list": [{"ticker": "HPE", "entry": 61.0, "atr_14d": 2.0,
                              "last_pivot_high": {"price": 62.15}, "prior_bar_high": 61.5,
                              "on_longlist": True, "on_elder": False,
                              "bracket": {"valid": True, "stop": 59.0, "targets": []}}],
              "held_positions": []}
    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(None, quotes, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02", export=export)
    assert summary["defaults"] == 1 and summary["enabled"] is True
    assert summary["fired"]["HPE"] == ["CONDITION_MET"]
    assert len(sent) == 1
    ticker, row, ev, states, live = sent[0][0][0]
    assert row["aqe_default"] is True and row["class"] == "AQE_LONGLIST"
    from src.alerts import emailer as E
    subject, plain, _ = E.build_condition_state_body(ticker, row, ev, states, live)
    assert "AQE default criteria" in subject
    assert "an hourly candle closes above 62.15 (AQE default)" in plain
    assert "Bracket: entry 62.15 · stop 59.00" not in plain      # no target -> no bracket line


def test_exit_line_on_a_name_not_held_is_ledgered_but_never_a_card(monkeypatch):
    """PM 2026-10-03: "why would I care about an exit I don't own?" Only a
    HELD position's exit line becomes a card; a watch name's crossing is
    kept in the ledger and nothing more."""
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC, "FMPClient", lambda: _FakeClient(below_level=True))
    sent = []
    monkeypatch.setattr(CC, "_maybe_email_digest", lambda *a, **k: sent.append(a))
    doc = {"run_date": "2026-10-02",
           "rows": [{"ticker": "HPE", "class": "WATCH", "atr_14d": 2.0,
                     "conditions": {"shared": {"buy": [], "confirm": []},
                                    "analysts": [],
                                    # bars close at 60.0 -> hourly close under 61
                                    "exits": [{"w": "close_below", "value": 61.0}]}}]}
    quotes = {"HPE": {"price": 60.0, "prev_close": 61.0, "day_high": 60.5,
                      "day_low": 59.5, "open": 60.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(doc, quotes, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["fired"]["HPE"] == ["EXIT_LINE_WARN"]
    assert sent == []


# -------------------------------------------------------------- ledger wiring


def test_cycle_writes_a_ledger_line_even_when_nothing_fires(monkeypatch):
    from src.alerts import condition_ledger as CL
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC, "FMPClient", lambda: _FakeClient(below_level=True))
    quotes = {"HPE": {"price": 60.0, "prev_close": 61.0, "day_high": 60.5,
                      "day_low": 59.5, "open": 60.0},  # below the buy level
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    CC.run_condition_cycle(_pma_doc_with_conditions(), quotes,
                           datetime(2026, 10, 2, 11, 0, tzinfo=_ET), run_date="2026-10-02")
    lines = CL.load_lines("2026-10-02")
    assert len(lines) == 1
    assert lines[0]["ticker"] == "HPE"
    assert lines[0]["fired_states"] == []


def test_cycle_persists_condition_state_across_calls():
    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    CC.run_condition_cycle(_pma_doc_with_conditions(), quotes,
                           datetime(2026, 10, 2, 11, 0, tzinfo=_ET), run_date="2026-10-02")
    state = CS.load_condition_state()
    assert state["2026-10-02:HPE"]["stage"] == CS.STAGE_CONDITION_MET


def test_one_names_error_never_blocks_the_rest(monkeypatch):
    """A row that blows up mid-evaluation must not stop other names in
    the same cycle from being evaluated and logged."""
    doc = _pma_doc_with_conditions()
    doc["rows"].append({"ticker": "BOOM", "class": "ADVANCE", "atr_14d": 2.0,
                        "conditions": {"shared": {"buy": [{"w": "h1_close_above",
                                                          "level": None}]},
                                      "exits": [], "analysts": []}})
    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "BOOM": {"price": 10.0, "prev_close": 10.0, "day_high": 10.0,
                     "day_low": 10.0, "open": 10.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(doc, quotes, datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert "HPE" in summary["fired"]
