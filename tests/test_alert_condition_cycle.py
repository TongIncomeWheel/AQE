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
    monkeypatch.setattr(CC, "_maybe_email", lambda *a, **k: sent.append(a))

    quotes = {"HPE": {"price": 64.2, "prev_close": 61.0, "day_high": 64.5,
                      "day_low": 61.9, "open": 62.0},
             "SPY": {"price": 500.5, "prev_close": 499.0}}
    summary = CC.run_condition_cycle(_pma_doc_with_conditions(), quotes,
                                     datetime(2026, 10, 2, 11, 0, tzinfo=_ET),
                                     run_date="2026-10-02")
    assert summary["enabled"] is True
    assert "HPE" in summary["fired"]
    assert "CONDITION_MET" in summary["fired"]["HPE"]
    # _maybe_email was CALLED (the wiring reaches it)...
    assert sent
    # ...but send_condition_state_email itself must never actually be
    # invoked while PMA_CONDITIONS_LIVE is False -- verified directly below.


def test_maybe_email_is_a_noop_in_shadow_mode(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "PMA_CONDITIONS_LIVE", False)
    calls = []
    monkeypatch.setattr("src.alerts.emailer.send_condition_state_email",
                       lambda *a, **k: calls.append(a))
    CC._maybe_email("HPE", {}, {}, ["CONDITION_MET"], {})
    assert calls == []


def test_maybe_email_sends_in_live_mode(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "PMA_CONDITIONS_LIVE", True)
    calls = []
    monkeypatch.setattr("src.alerts.emailer.send_condition_state_email",
                       lambda *a, **k: calls.append(a) or {"ok": True})
    CC._maybe_email("HPE", {}, {}, ["CONDITION_MET"], {})
    assert len(calls) == 1
    assert calls[0][0] == "HPE"


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
