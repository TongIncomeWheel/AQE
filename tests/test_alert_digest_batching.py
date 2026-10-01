"""Digest batching — a hard floor on email FREQUENCY (src/alerts/state.py's
digest-batching section, src/alerts/config.py's MIN_DIGEST_GAP_MINUTES,
engine.py's run_alert_cycle send block).

PM complaint (2026-10-01): alerts arrived too often — "once every 15 mins
in one email, not by individual ticker." state.py's own docstring already
admitted the gap this closes: the two pollers (in-app 15-min thread,
GitHub Actions backstop) share dedup state, but "a collision can at worst
send one duplicate, never miss one" — last-writer-wins on a read-then-write
race when both land close together.

The fix queues every fresh trigger FIRST, unconditionally, then gates only
the SEND on a shared "when did we last actually email" timestamp — so a
cycle that's gated folds its content into the next send instead of losing
it (a trigger already marked fired above is never re-evaluated, so simply
skipping the email would drop it for good).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.alerts import config as C
from src.alerts import engine as E
from src.alerts import state as S

_UTC = ZoneInfo("UTC")
_ET = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Every digest-batching test gets its own on-disk state, and Drive is
    forced off so these never touch the network."""
    monkeypatch.setattr(S, "LOCAL_PENDING_DIGEST", tmp_path / "pending.json")
    monkeypatch.setattr(S, "LOCAL_LAST_DIGEST", tmp_path / "last_sent.json")
    import src.data.gdrive_uploader as G
    monkeypatch.setattr(G, "is_configured", lambda: False)


# --------------------------------------------------------- state.py: pending queue


def test_pending_digest_starts_empty():
    assert S.load_pending_digest() == {"legacy": [], "pma": []}


def test_append_pending_digest_merges_legacy_and_pma():
    S.append_pending_digest([{"level": "T|MOVE"}], [{"level": "A-cond|close"}])
    pending = S.load_pending_digest()
    assert pending["legacy"] == [{"level": "T|MOVE"}]
    assert pending["pma"] == [{"level": "A-cond|close"}]


def test_append_pending_digest_accumulates_across_calls():
    S.append_pending_digest([{"level": "T|MOVE"}], [])
    S.append_pending_digest([{"level": "U|MOVE"}], [{"level": "A-cond|close"}])
    pending = S.load_pending_digest()
    assert {t["level"] for t in pending["legacy"]} == {"T|MOVE", "U|MOVE"}
    assert {t["level"] for t in pending["pma"]} == {"A-cond|close"}


def test_append_pending_digest_dedups_by_level():
    """The same trigger (by its own dedup key) queued twice must not appear
    twice in the eventual email."""
    S.append_pending_digest([{"level": "T|MOVE", "note": "first"}], [])
    S.append_pending_digest([{"level": "T|MOVE", "note": "stale duplicate"}], [])
    pending = S.load_pending_digest()
    assert len(pending["legacy"]) == 1
    assert pending["legacy"][0]["note"] == "first"


def test_clear_pending_digest_empties_both_buckets():
    S.append_pending_digest([{"level": "T|MOVE"}], [{"level": "A-cond|close"}])
    S.clear_pending_digest()
    assert S.load_pending_digest() == {"legacy": [], "pma": []}


# ------------------------------------------------------ state.py: last-sent gate


def test_last_digest_sent_is_none_before_any_send():
    assert S.load_last_digest_sent() is None


def test_seconds_since_last_digest_is_infinite_before_any_send():
    assert S.seconds_since_last_digest(datetime.now(_UTC)) == float("inf")


def test_mark_and_load_last_digest_sent_round_trips():
    now = datetime(2026, 10, 1, 14, 30, tzinfo=_UTC)
    S.mark_digest_sent(now)
    assert S.load_last_digest_sent() == now


def test_seconds_since_last_digest_reflects_elapsed_time():
    now = datetime(2026, 10, 1, 14, 30, tzinfo=_UTC)
    S.mark_digest_sent(now)
    later = now + timedelta(minutes=7)
    assert S.seconds_since_last_digest(later) == pytest.approx(7 * 60, abs=1)


# --------------------------------------------------- engine.py: the send gate


def _base_export():
    return {"date": "2026-10-01", "held_positions": [],
            "daily_list": [{"ticker": "T", "on_longlist": True, "on_elder": True,
                            "entry": 100.0, "atr_14d": 3.0,
                            "bracket": {"valid": True, "stop": 92.0, "risk": 8.0,
                                       "targets": [{"tp": "TP1", "price": 112.0}]}}]}


def _wire_common(monkeypatch, export):
    monkeypatch.setattr(E, "load_export", lambda: export)
    monkeypatch.setattr(E, "in_market_window", lambda: True)
    monkeypatch.setattr(E, "_export_age_days", lambda _e: 0)
    monkeypatch.setattr(E.S, "load_alert_state", lambda: {"date": "x", "fired": []})
    monkeypatch.setattr(E.S, "save_alert_state", lambda _s: None)
    monkeypatch.setattr(E.S, "append_history", lambda _f: None)
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC.FMPClient, "__init__", lambda self: None)
    monkeypatch.setattr(FC.FMPClient, "get_quotes",
                        lambda self, tks: {"T": {"price": 105.0, "prev_close": 100.0}})


def test_cycle_sends_immediately_when_no_prior_digest(monkeypatch):
    export = _base_export()
    _wire_common(monkeypatch, export)
    sent = []
    import src.alerts.emailer as EM
    monkeypatch.setattr(EM, "send_digest",
                        lambda triggers, exp, pma_triggers=None: sent.append(triggers) or
                        {"ok": True})

    summary = E.run_alert_cycle(send_email=True)
    assert summary["new_triggers"] >= 1
    assert summary["deferred"] is False
    assert summary["emailed"] is True
    assert sent, "send_digest was never called"
    assert S.load_pending_digest() == {"legacy": [], "pma": []}
    assert S.load_last_digest_sent() is not None


def test_cycle_defers_when_a_digest_just_went_out(monkeypatch):
    """The exact PM complaint: a second poller (or an overlapping cycle)
    landing inside the gap must NOT send a second email -- but must not
    drop the trigger either."""
    export = _base_export()
    _wire_common(monkeypatch, export)
    S.mark_digest_sent(datetime.now(_UTC))  # "another digest just went out"

    sent = []
    import src.alerts.emailer as EM
    monkeypatch.setattr(EM, "send_digest",
                        lambda triggers, exp, pma_triggers=None: sent.append(triggers) or
                        {"ok": True})

    summary = E.run_alert_cycle(send_email=True)
    assert summary["new_triggers"] >= 1
    assert summary["deferred"] is True
    assert not sent, "send_digest must not be called inside the gap"
    pending = S.load_pending_digest()
    assert pending["legacy"], "the fresh trigger must be queued, not dropped"


def test_deferred_trigger_is_folded_into_the_next_successful_send(monkeypatch):
    """End-to-end: a cycle gated by the timer, followed by a cycle after
    the gap clears, must deliver the FIRST cycle's trigger in the SECOND
    cycle's one email -- never silently lost."""
    export = _base_export()
    _wire_common(monkeypatch, export)
    S.mark_digest_sent(datetime.now(_UTC) - timedelta(minutes=C.MIN_DIGEST_GAP_MINUTES + 1))

    # First cycle: gap already clear, sends immediately and clears state.
    sent = []
    import src.alerts.emailer as EM
    monkeypatch.setattr(EM, "send_digest",
                        lambda triggers, exp, pma_triggers=None: sent.append(list(triggers)) or
                        {"ok": True})
    first = E.run_alert_cycle(send_email=True)
    assert first["deferred"] is False and first["emailed"] is True
    assert len(sent) == 1 and len(sent[0]) >= 1

    # Simulate a second, near-simultaneous cycle (e.g. the GH Actions
    # backstop) landing inside the gap this same trigger would have
    # re-fired under a stale dedup read -- here we inject a DIFFERENT
    # fresh trigger directly into the pending queue to model "gated".
    S.append_pending_digest([{"level": "U|MOVE", "ticker": "U", "note": "queued"}], [])

    # Third cycle: still inside the gap -> deferred, queue keeps growing.
    second = E.run_alert_cycle(send_email=True)
    assert second["deferred"] is True
    pending = S.load_pending_digest()
    assert any(t.get("level") == "U|MOVE" for t in pending["legacy"])

    # Fourth cycle: gap cleared -> the queued item finally goes out.
    S.mark_digest_sent(datetime.now(_UTC) - timedelta(minutes=C.MIN_DIGEST_GAP_MINUTES + 1))
    third = E.run_alert_cycle(send_email=True)
    assert third["deferred"] is False and third["emailed"] is True
    assert any(t.get("level") == "U|MOVE" for t in sent[-1])
    assert S.load_pending_digest() == {"legacy": [], "pma": []}


def test_failed_send_keeps_the_pending_queue_for_retry(monkeypatch):
    export = _base_export()
    _wire_common(monkeypatch, export)
    import src.alerts.emailer as EM
    monkeypatch.setattr(EM, "send_digest",
                        lambda triggers, exp, pma_triggers=None:
                        {"ok": False, "reason": "no email backend"})

    summary = E.run_alert_cycle(send_email=True)
    assert summary["emailed"] is False
    assert summary["deferred"] is False
    assert S.load_last_digest_sent() is None, "a failed send must not arm the gate"
    pending = S.load_pending_digest()
    assert pending["legacy"], "a failed send must not drop the trigger"


def test_a_cycle_with_no_fresh_triggers_never_touches_the_gate(monkeypatch):
    """No new events this cycle -> nothing queued, nothing sent, the
    last-digest timestamp is untouched."""
    export = {"date": "2026-10-01", "held_positions": [], "daily_list": []}
    _wire_common(monkeypatch, export)
    monkeypatch.setattr(FC_mod(), "get_quotes", lambda self, tks: {})

    summary = E.run_alert_cycle(send_email=True)
    assert summary["new_triggers"] == 0
    assert not summary.get("deferred")
    assert not summary.get("emailed")
    assert S.load_pending_digest() == {"legacy": [], "pma": []}
    assert S.load_last_digest_sent() is None


def FC_mod():
    import src.data.fmp_client as FC
    return FC.FMPClient
