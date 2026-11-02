"""Final-cycle rule: close_* triggers must confirm in EVERY session.

Regression for 2026-11-02: with 30-min cycles the poller (stopped at 16:15 ET,
final slot 16:00) landed a cycle in the final slot only ~50% of sessions.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import config as C
from src.alerts import condition_spec as S
from src.alerts import engine as E
from src.alerts import pma_levels as P

ET = ZoneInfo("America/New_York")


def _et(h, m, day=2):                       # 2026-11-02 is a Monday
    return datetime(2026, 11, day, h, m, tzinfo=ET)


def test_one_definition_of_final_cycle():
    assert S.FINAL_CYCLE_HOUR_MIN == C.FINAL_CYCLE_FROM_MIN == 15 * 60 + 45
    assert P.is_final_cycle_of_session(_et(15, 45)) and not P.is_final_cycle_of_session(_et(15, 44))


@pytest.mark.parametrize("drift", [0, 3, 6, 10])
def test_every_phase_has_a_cycle_in_the_final_span(drift):
    """Any cycle phase, 30-min cadence plus drift, yields >=1 in-window cycle at
    or after the final-cycle start."""
    step = C.ALERT_MINUTES + drift
    for phase in range(0, step):
        t = 9 * 60 + 45 + phase
        hits = 0
        while t < C.ALERT_WINDOW_END[0] * 60 + C.ALERT_WINDOW_END[1]:
            if t >= C.FINAL_CYCLE_FROM_MIN:
                hits += 1
            t += step
        assert hits >= 1, f"phase {phase} drift {drift}: no final cycle"


def test_alert_window_extends_past_market_close_but_in_market_window_does_not():
    assert E.in_alert_window(_et(16, 30)) and not E.in_alert_window(_et(16, 45))
    assert not E.in_alert_window(_et(9, 44)) and E.in_alert_window(_et(9, 45))
    assert not E.in_alert_window(_et(10, 0, day=7))          # Saturday
    assert (C.MARKET_CLOSE[0] * 60 + C.MARKET_CLOSE[1]) < (C.ALERT_WINDOW_END[0] * 60 + C.ALERT_WINDOW_END[1])


def test_close_trigger_confirms_in_final_cycle_not_before():
    row = {"ticker": "X", "class": "ADVANCE", "triggers": [
        {"id": "X-1", "kind": "close_above", "level": 100, "priority": "ACTION", "action": "a"}]}
    q = {"price": 101, "day_high": 101, "day_low": 99, "prev_close": 99}
    early = P.evaluate_pma(row, q, _et(15, 30), P.is_final_cycle_of_session(_et(15, 30)), False)
    late = P.evaluate_pma(row, q, _et(16, 20), P.is_final_cycle_of_session(_et(16, 20)), False)
    assert early[0]["priority"] == "WARN" and late[0]["priority"] == "ACTION"
