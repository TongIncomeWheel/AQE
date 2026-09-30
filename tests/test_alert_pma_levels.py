"""Tests for the PMA committee-levels alert path (AQE Handoff: PMA Live
Alerts, docs/handoff/aqe_handoff_pma_live_alerts_2026-09-30.md).

Covers every trigger kind, freshness/stale handling, WATCH/not_structured_
yet exclusion, NEAR_STOP suppression, the life-of-a-trigger dedup + pruning,
the volume_min_x gate, the golden "heartbeat unchanged" byte-identical
test, the % distance card rules, card-UX plain-word constraints, and the
full acceptance replay over a FROZEN copy of the real run-2026-09-29
pma_levels.json (tests/fixtures/pma_levels_2026-09-29.json, taken verbatim
from git commit 549474e2's version of aegis/output/pma/pma_levels.json)
with the synthetic quotes the handoff itself specifies.

Deliberately NOT the live aegis/output/pma/pma_levels.json: that path is a
real production file the PMA committee overwrites every trading morning,
so an acceptance test pinned to "A"/"PK"/"MRVL"-shaped assertions would
break the day the committee's own picks changed — which already happened
once, the day after this suite was first written.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.alerts import config as C
from src.alerts import emailer as E
from src.alerts import engine as ENG
from src.alerts import pma_levels as P
from src.alerts import state as S

ET = ZoneInfo("America/New_York")
FIXTURE_FILE = (Path(__file__).resolve().parent
                / "fixtures" / "pma_levels_2026-09-29.json")


def _dt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def _q(price, hi=None, lo=None, prev=None, vol=None, avg_vol=None, op=None):
    return {"price": price, "day_high": hi if hi is not None else price,
           "day_low": lo if lo is not None else price, "prev_close": prev,
           "volume": vol, "avg_volume": avg_vol, "open": op if op is not None else prev}


@pytest.fixture(scope="module")
def real_doc():
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def real_rows(real_doc):
    return {(r["ticker"], r["class"]): r for r in real_doc["rows"]}


MID = _dt(2026, 9, 30, 12, 0)
FIRST = _dt(2026, 9, 30, 9, 45)
FINAL = _dt(2026, 9, 30, 16, 0)


# --------------------------------------------------------------- trigger kinds


def test_trade_above_fires_on_day_high_touch():
    row = {"ticker": "X", "class": "ADVANCE",
          "triggers": [{"id": "X-e", "kind": "trade_above", "level": 100.0,
                       "basis": "15m", "priority": "ACTION", "action": "new high"}]}
    hit = P.evaluate_pma(row, _q(99, hi=100.0), MID, False, False)
    assert any(t["trigger_id"] == "X-e" for t in hit)
    # day_high just short of the level: the literal trade_above must NOT
    # fire (a synthesized "Approaching entry" WARN may still fire
    # separately since this same trigger also reads as the row's entry
    # condition -- that's a different, correct check, not this one).
    miss = P.evaluate_pma(row, _q(99, hi=99.9), MID, False, False)
    assert not any(t["trigger_id"] == "X-e" for t in miss)


def test_trade_below_fires_on_day_low_touch():
    row = {"ticker": "X", "class": "HOLD_FOR_CONDITIONS",
          "triggers": [{"id": "X-b", "kind": "trade_below", "level": 50.0,
                       "basis": "15m", "priority": "WARN", "action": "breakdown watch"}]}
    assert P.evaluate_pma(row, _q(51, lo=50.0), MID, False, False)
    assert not P.evaluate_pma(row, _q(51, lo=50.1), MID, False, False)


def test_close_above_warns_intraday_and_actions_on_final_cycle():
    row = {"ticker": "X", "class": "HOLD_FOR_CONDITIONS",
          "triggers": [{"id": "X-cond", "kind": "close_above", "level": 100.0,
                       "basis": "daily", "priority": "ACTION", "action": "condition met"}]}
    mid = P.evaluate_pma(row, _q(101.0), MID, False, False)
    assert mid and mid[0]["priority"] == "WARN" and mid[0]["level"] == "X-cond|warn"
    final = P.evaluate_pma(row, _q(101.0), FINAL, True, False)
    assert final and final[0]["priority"] == "ACTION" and final[0]["level"] == "X-cond|close"


def test_close_below_warns_intraday_and_actions_on_final_cycle():
    row = {"ticker": "X", "class": "ADVANCE",
          "triggers": [{"id": "X-kill", "kind": "close_below", "level": 100.0,
                       "basis": "daily", "priority": "ACTION", "action": "idea dead"}]}
    mid = P.evaluate_pma(row, _q(99.0), MID, False, False)
    assert mid[0]["priority"] == "WARN" and mid[0]["level"] == "X-kill|warn"
    final = P.evaluate_pma(row, _q(99.0), FINAL, True, False)
    assert final[0]["priority"] == "ACTION" and final[0]["level"] == "X-kill|close"


def test_within_atr_of_folds_into_near_your_stops_not_its_own_card():
    row = {"ticker": "X", "class": "HELD", "broker_stop": {"stop": 100.0},
          "committee_exit": 110.0, "atr_14d": 10.0,
          "triggers": [{"id": "X-stopnear", "kind": "within_atr_of", "level": 100.0,
                       "atr": 10.0, "atr_mult": 0.5, "basis": "15m", "priority": "WARN",
                       "action": "near stop"}]}
    # price 104 is inside the ATR band (100 < 104 <= 105) but > HELD_NEAR_PCT
    # away from either stop numerically -- only the ATR fold-in should fire.
    out = P.evaluate_pma(row, _q(104.0), MID, False, False)
    assert len(out) == 1
    assert out[0]["label"] == "Near your stops"


def test_no_stop_order_fires_only_on_first_cycle_and_repeats_daily():
    row = {"ticker": "X", "class": "HELD", "broker_stop": {"note": "NO STOP ORDER"},
          "triggers": [{"id": "X-nostop", "kind": "no_stop_order", "level": None,
                       "basis": "open", "priority": "ACTION", "action": "no stop"}]}
    first = P.evaluate_pma(row, _q(50.0), FIRST, False, True)
    assert first and first[0]["level"] == "X-nostop|2026-09-30"
    assert not P.evaluate_pma(row, _q(50.0), MID, False, False)


def test_order_config_fires_only_on_first_cycle():
    row = {"ticker": "X", "class": "HELD", "broker_stop": {"stop": 100, "limit": 100.5},
          "triggers": [{"id": "X-ordertype", "kind": "order_config", "level": 100.0,
                       "basis": "open", "priority": "ACTION", "action": "limit above stop"}]}
    assert P.evaluate_pma(row, _q(120.0), FIRST, False, True)
    assert not P.evaluate_pma(row, _q(120.0), MID, False, False)


def test_unknown_kind_never_fires():
    row = {"ticker": "X", "class": "ADVANCE",
          "triggers": [{"id": "X-mystery", "kind": "something_new", "level": 1.0,
                       "priority": "ACTION", "action": "?"}]}
    assert P.evaluate_pma(row, _q(1.0), MID, False, False) == []


# ------------------------------------------------------------------- freshness


def test_is_fresh_true_for_todays_session():
    assert P.is_fresh({"session": "2026-09-30"}, _dt(2026, 9, 30, 10, 0))


def test_is_fresh_false_for_another_session():
    assert not P.is_fresh({"session": "2026-09-29"}, _dt(2026, 9, 30, 10, 0))


def test_is_fresh_false_for_none_doc():
    assert not P.is_fresh(None, _dt(2026, 9, 30, 10, 0))


def test_load_pma_levels_falls_back_to_github_when_local_is_stale(monkeypatch, tmp_path):
    from src.data import github_sync

    stale = tmp_path / "pma_levels.json"
    stale.write_text(json.dumps({"session": "2020-01-01", "rows": []}))
    monkeypatch.setattr(P, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "get_file",
                        lambda path: {"ok": True,
                                     "text": json.dumps({"session": "2099-01-01", "rows": []})})
    doc, reason = P.load_pma_levels("pma_levels.json")
    assert reason is None
    assert doc["session"] == "2099-01-01"


def test_load_pma_levels_no_local_no_credential_gives_a_reason(monkeypatch, tmp_path):
    from src.data import github_sync

    monkeypatch.setattr(P, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(github_sync, "is_configured", lambda: False)
    doc, reason = P.load_pma_levels("pma_levels.json")
    assert doc is None
    assert reason


# ------------------------------------------------------- WATCH / not_structured


def test_watch_rows_never_trigger(real_doc):
    watch = [r for r in real_doc["rows"] if r["class"] == "WATCH"]
    assert watch
    for row in watch:
        assert P.evaluate_pma(row, _q(9999.0, hi=9999.0), MID, True, True) == []


def test_not_structured_yet_rows_never_trigger(real_rows):
    row = real_rows[("NTRA", "HOLD_FOR_CONDITIONS")]
    assert row.get("not_structured_yet")
    assert row["triggers"] == []
    assert P.evaluate_pma(row, _q(360.0, hi=400.0), MID, True, True) == []


def test_alertable_rows_excludes_watch_and_not_structured(real_doc):
    rows = P.alertable_rows(real_doc)
    assert all(r["class"] != "WATCH" for r in rows)
    assert all(r.get("triggers") for r in rows)


# --------------------------------------------------------- NEAR_STOP suppression


def test_legacy_near_stop_suppressed_when_pma_broker_stop_present():
    rec = {"held_sl": 100.0}
    quote = _q(103.0)
    fired_normally = ENG.evaluate("X", "held", True, rec, quote)
    assert any(t["level"] == "NEAR_STOP" for t in fired_normally)
    fired_suppressed = ENG.evaluate("X", "held", True, rec, quote, suppress_near_stop=True)
    assert not any(t["level"] == "NEAR_STOP" for t in fired_suppressed)


def test_held_broker_stop_tickers_extracts_the_right_set(real_doc):
    tickers = P.held_broker_stop_tickers(real_doc)
    assert "MRVL" in tickers and "ANET" in tickers
    # WEAT has no stop order at all -- broker_stop is present but stop is None;
    # it still counts (the row DOES carry a broker_stop block).
    assert "WEAT" in tickers


# --------------------------------------------------------------- dedup/pruning


def test_pma_fired_state_life_of_trigger_not_daily():
    state = {"fired": []}
    assert not S.is_pma_fired(state, "A-entry|close")
    S.mark_pma_fired(state, "A-entry|close")
    assert S.is_pma_fired(state, "A-entry|close")
    # No date field, no reset -- unlike the legacy `fired` set.
    assert "date" not in state


def test_prune_pma_fired_drops_keys_whose_base_id_left_the_file():
    state = {"fired": ["A-entry|close", "PK-cond|close", "WEAT-nostop|2026-09-29"]}
    pruned = S.prune_pma_fired(state, live_base_ids={"A-entry"})
    assert pruned == 2
    assert state["fired"] == ["A-entry|close"]


def test_a_fired_trigger_does_not_resend_the_next_day_then_prunes_when_retired():
    """Mirrors the acceptance replay's second-day scenario: a trigger fired
    on day 1 stays quiet on day 2 (same file, same id); once its row is
    gone from a later file, its key is pruned."""
    row = {"ticker": "A", "class": "ADVANCE",
          "triggers": [{"id": "A-entry", "kind": "trade_above", "level": 176.02,
                       "basis": "15m", "priority": "ACTION", "action": "new high"}]}
    state = {"fired": []}
    day1 = P.evaluate_pma(row, _q(175, hi=176.10), MID, False, False)
    for t in day1:
        assert not S.is_pma_fired(state, t["level"])
        S.mark_pma_fired(state, t["level"])
    day2 = P.evaluate_pma(row, _q(175, hi=176.20), _dt(2026, 10, 1, 12, 0), False, False)
    assert all(S.is_pma_fired(state, t["level"]) for t in day2), (
        "the same id must stay deduped across days -- life of the trigger, not daily")
    # Now the row is gone from the next file entirely.
    pruned = S.prune_pma_fired(state, live_base_ids=set())
    assert pruned == len(state["fired"]) or state["fired"] == []
    assert not S.is_pma_fired(state, "A-entry")


# ------------------------------------------------------------------- volume gate


def test_volume_min_x_shortfall_gives_no_action():
    row = {"ticker": "X", "class": "HOLD_FOR_CONDITIONS", "atr_14d": 1.0,
          "triggers": [{"id": "X-cond", "kind": "close_above", "level": 100.0,
                       "basis": "daily", "priority": "ACTION", "action": "cond met",
                       "volume_min_x": 1.4}]}
    # elapsed enough for vol_pace to compute, volume clearly short of 1.4x pace.
    q = _q(101.0, vol=1000, avg_vol=10000, op=100)
    out = P.evaluate_pma(row, q, _dt(2026, 9, 30, 12, 0), True, False)
    assert out == []


def test_volume_min_x_unconfirmed_still_fires_and_says_so():
    row = {"ticker": "X", "class": "HOLD_FOR_CONDITIONS", "atr_14d": 1.0,
          "triggers": [{"id": "X-cond", "kind": "close_above", "level": 100.0,
                       "basis": "daily", "priority": "ACTION", "action": "cond met",
                       "volume_min_x": 1.4}]}
    # No volume data at all -> vol_pace can't compute -> unconfirmed, not dropped.
    q = _q(101.0)
    out = P.evaluate_pma(row, q, FINAL, True, False)
    assert out and "volume unconfirmed" in out[0]["note"]


def test_volume_min_x_met_annotates_pace():
    row = {"ticker": "X", "class": "HOLD_FOR_CONDITIONS", "atr_14d": 1.0,
          "triggers": [{"id": "X-cond", "kind": "close_above", "level": 100.0,
                       "basis": "daily", "priority": "ACTION", "action": "cond met",
                       "volume_min_x": 1.0}]}
    q = _q(101.0, vol=100000, avg_vol=10000, op=100)
    out = P.evaluate_pma(row, q, FINAL, True, False)
    assert out and "pace" in out[0]["note"]


# ------------------------------------------------------------- golden heartbeat


def test_heartbeat_unchanged_when_no_pma_triggers(monkeypatch):
    """A cycle with no PMA triggers must render subject/plain/html BYTE-
    IDENTICAL to send_digest's pre-PMA behaviour -- captured directly from
    _build_bodies() as the reference, per the handoff's own requirement."""
    triggers = [{"ticker": "TEST1", "source": "longlist", "is_held": False,
                "level": "BUY_ZONE", "label": "Hit buy price", "level_price": 101.5,
                "live_px": 101.6, "chg_pct": 1.2, "prev_close": 100.0,
                "intraday": {}, "note": "x"}]
    export = {"date": "2026-09-30", "regime": {"level": "RISK_ON"},
             "daily_list": [{"ticker": "TEST1", "sc_momentum": 70, "sc_momentum_raw": 70,
                            "bracket": {"valid": False}}],
             "held_positions": []}
    ref_subject, ref_plain, ref_html = E._build_bodies(triggers, export)

    captured = {}

    def fake_send(cfg, subject, plain, html):
        captured.update(subject=subject, plain=plain, html=html)
        return {"ok": True}

    monkeypatch.setattr(E, "_send_resend", fake_send)
    monkeypatch.setattr(E, "_cfg", lambda: {"resend_key": "fake", "from": "x", "to": "y",
                                            "smtp_user": "", "smtp_pw": None,
                                            "smtp_host": "", "smtp_port": 0})
    E.send_digest(triggers, export)  # no pma_triggers arg at all
    assert captured["subject"] == ref_subject
    assert captured["plain"] == ref_plain
    assert captured["html"] == ref_html


def test_heartbeat_unchanged_with_explicit_empty_pma_list(monkeypatch):
    triggers = [{"ticker": "TEST1", "source": "longlist", "is_held": False,
                "level": "BUY_ZONE", "label": "Hit buy price", "level_price": 101.5,
                "live_px": 101.6, "chg_pct": 1.2, "prev_close": 100.0,
                "intraday": {}, "note": "x"}]
    export = {"date": "2026-09-30", "regime": {"level": "RISK_ON"},
             "daily_list": [], "held_positions": []}
    ref_subject, ref_plain, ref_html = E._build_bodies(triggers, export)
    captured = {}
    monkeypatch.setattr(E, "_send_resend",
                        lambda cfg, s, p, h: captured.update(subject=s, plain=p, html=h)
                        or {"ok": True})
    monkeypatch.setattr(E, "_cfg", lambda: {"resend_key": "fake", "from": "x", "to": "y",
                                            "smtp_user": "", "smtp_pw": None,
                                            "smtp_host": "", "smtp_port": 0})
    E.send_digest(triggers, export, pma_triggers=[])
    assert (captured["subject"], captured["plain"], captured["html"]) == (
        ref_subject, ref_plain, ref_html)


def test_pma_section_absent_leaves_no_empty_heading(monkeypatch):
    subj, plain, html = E._build_pma_section([])
    assert (subj, plain, html) == ("", "", "")


def test_info_only_pma_triggers_defer_to_after_close_not_intraday(monkeypatch):
    info_trigger = [{"ticker": "X", "is_held": False, "priority": "INFO",
                     "headline_phrase": "x", "live_px": 1, "kind": "trade_above"}]
    monkeypatch.setattr(E, "_cfg", lambda: {"resend_key": "fake", "from": "x", "to": "y",
                                            "smtp_user": "", "smtp_pw": None,
                                            "smtp_host": "", "smtp_port": 0})
    res = E.send_digest([], {"date": "x", "daily_list": [], "held_positions": []},
                        pma_triggers=info_trigger)
    assert res["ok"] is False


# --------------------------------------------------------------- % distances


def test_held_card_shows_your_stop_and_committee_stop_never_entry_target():
    t = {"ticker": "MRVL", "is_held": True, "live_px": 238.0,
        "broker_stop": 233.85, "committee_exit": 234.65,
        "entry_price": 999, "target_price": 999}  # must never be read for held
    line = E._pma_number_line(t)
    assert "Your stop 233.85" in line
    assert "Committee stop 234.65" in line
    assert "Entry" not in line and "Target" not in line


def test_shortlist_card_shows_entry_and_target_never_stops():
    t = {"ticker": "A", "is_held": False, "live_px": 175.40,
        "entry_price": 176.02, "target_price": 185.48,
        "broker_stop": 999, "committee_exit": 999}  # must never be read for shortlist
    line = E._pma_number_line(t)
    assert "Entry 176.02" in line
    assert "Target 185.48" in line
    assert "stop" not in line.lower()


def test_no_broker_stop_reads_your_stop_none():
    t = {"ticker": "WEAT", "is_held": True, "live_px": 10.0,
        "broker_stop": None, "committee_exit": None}
    line = E._pma_number_line(t)
    assert "Your stop — none" in line


def test_exact_held_example_matches_the_handoffs_own_numbers():
    line = E._pma_number_line({"ticker": "MRVL", "is_held": True, "live_px": 238.00,
                              "broker_stop": 233.85, "committee_exit": 234.65})
    assert line == "Now 238.0 · Your stop 233.85 (1.7% away) · Committee stop 234.65 (1.4% away)"


def test_exact_shortlist_example_matches_the_handoffs_own_numbers():
    line = E._pma_number_line({"ticker": "A", "is_held": False, "live_px": 175.40,
                              "entry_price": 176.02, "target_price": 185.48})
    assert line == "Now 175.4 · Entry 176.02 (0.4% to go) · Target 185.48 (5.7% away)"


def test_through_by_phrasing_once_price_has_cleared_entry():
    line = E._pma_number_line({"ticker": "PK", "is_held": False, "live_px": 16.30,
                              "entry_price": 16.20, "target_price": 16.72})
    assert "through by 0.6%" in line


def test_near_alert_fires_at_threshold_not_one_tick_outside():
    row = {"ticker": "X", "class": "HELD", "broker_stop": {"stop": 100.0},
          "committee_exit": None, "atr_14d": None, "triggers": []}
    # No literal triggers on the row -- purely exercising the synthesized check.
    row["triggers"] = [{"id": "X-stub", "kind": "no_stop_order", "level": None,
                        "basis": "open", "priority": "INFO", "action": "stub"}]
    at_threshold_price = 100.0 / (1 - C.HELD_NEAR_PCT / 100)   # exactly HELD_NEAR_PCT away
    just_outside = at_threshold_price * 1.001
    hit = P._synthesized_proximity_alerts(row, at_threshold_price, None, None, "2026-09-30",
                                          {"broker_stop": 100.0, "committee_exit": None})
    miss = P._synthesized_proximity_alerts(row, just_outside, None, None, "2026-09-30",
                                           {"broker_stop": 100.0, "committee_exit": None})
    assert hit and not miss


# ------------------------------------------------------------------- card UX


_BANNED_JARGON = ("trade_above", "trade_below", "close_above", "close_below",
                  "within_atr_of", "no_stop_order", "order_config", " SC ",
                  "R:R", "AIC", "β")  # β = beta


def test_pma_section_never_leaks_jargon_or_trigger_ids():
    t = {"ticker": "A", "source": "pma", "is_held": False, "level": "A-entry|near",
        "label": "trade_above", "live_px": 175.4, "priority": "WARN",
        "action": "New high above the prior high", "note": "New high above the prior high",
        "kind": "approaching_entry", "headline_phrase": "approaching its buy line",
        "entry_price": 176.02, "target_price": 185.48, "trigger_id": "A-entry",
        "carried": False}
    subj, plain, html = E._build_pma_section([t])
    combined = subj + plain + html
    for banned in _BANNED_JARGON:
        assert banned not in combined, f"leaked {banned!r} into the committee section"
    assert "A-entry" not in plain and "A-entry" not in html


def test_number_line_has_at_most_three_labelled_items():
    t = {"ticker": "MRVL", "is_held": True, "live_px": 238.0,
        "broker_stop": 233.85, "committee_exit": 234.65}
    line = E._pma_number_line(t)
    assert line.count(" · ") <= 2   # 3 items -> 2 separators


def test_action_card_carries_a_levels_line_warn_card_does_not():
    action = {"ticker": "PK", "is_held": False, "priority": "ACTION",
             "computed_stop": 15.23, "targets": [16.2, 16.72, 17.39]}
    warn = {"ticker": "A", "is_held": False, "priority": "WARN",
           "entry_price": 176.02, "target_price": 185.48}
    assert "information only" in E._pma_levels_line(action)
    assert E._pma_levels_line(warn) == ""


def test_carried_tag_format():
    t = {"carried": True, "origin_run": "2026-09-29", "age_sessions": 1}
    tag = E._carried_tag(t)
    assert "day 2 of 3" in tag
    assert "29 Sep" in tag


def test_carried_tag_absent_for_a_fresh_row():
    assert E._carried_tag({"carried": False}) == ""


# ------------------------------------------------------------- acceptance replay


def test_acceptance_first_cycle_weat_and_ntra_both_action(real_rows):
    weat = P.evaluate_pma(real_rows[("WEAT", "HELD")], _q(9.0), FIRST, False, True)
    ntra = P.evaluate_pma(real_rows[("NTRA", "HELD")], _q(238.0), FIRST, False, True)
    assert any(t["trigger_id"] == "WEAT-nostop" and t["priority"] == "ACTION" for t in weat)
    assert any(t["trigger_id"] == "NTRA-ordertype" and t["priority"] == "ACTION" for t in ntra)


def test_acceptance_a_day_high_176_10_gives_entry_action(real_rows):
    row_a = real_rows[("A", "ADVANCE")]
    out = P.evaluate_pma(row_a, _q(175.5, hi=176.10), MID, False, False)
    assert any(t["trigger_id"] == "A-entry" and t["priority"] == "ACTION" for t in out)


def test_acceptance_a_day_high_178_90_gives_entry_and_chase(real_rows):
    row_a = real_rows[("A", "ADVANCE")]
    out = P.evaluate_pma(row_a, _q(175.5, hi=178.90), MID, False, False)
    ids = {t["trigger_id"] for t in out}
    assert "A-entry" in ids and "A-chase" in ids


def test_acceptance_pk_day_high_16_25_gives_info_only(real_rows):
    row_pk = real_rows[("PK", "HOLD_FOR_CONDITIONS")]
    out = P.evaluate_pma(row_pk, _q(15.8, hi=16.25), MID, False, False)
    assert out and all(t["priority"] == "INFO" for t in out)


def test_acceptance_pk_final_cycle_price_16_30_gives_cond_action(real_rows):
    row_pk = real_rows[("PK", "HOLD_FOR_CONDITIONS")]
    out = P.evaluate_pma(row_pk, _q(16.30, hi=16.30), FINAL, True, False)
    assert any(t["trigger_id"] == "PK-cond" and t["priority"] == "ACTION" for t in out)


def test_acceptance_mrvl_near_stops_warn_exact_numbers(real_rows):
    row_mrvl = real_rows[("MRVL", "HELD")]
    out = P.evaluate_pma(row_mrvl, _q(238.0), MID, False, False)
    near = next(t for t in out if t["label"] == "Near your stops")
    assert E._pma_number_line(near) == (
        "Now 238.0 · Your stop 233.85 (1.7% away) · Committee stop 234.65 (1.4% away)")


def test_acceptance_a_approaching_entry_warn_exact_numbers(real_rows):
    row_a = real_rows[("A", "ADVANCE")]
    out = P.evaluate_pma(row_a, _q(175.40), MID, False, False)
    appr = next(t for t in out if t["label"] == "Approaching entry")
    assert E._pma_number_line(appr) == (
        "Now 175.4 · Entry 176.02 (0.4% to go) · Target 185.48 (5.7% away)")


def test_acceptance_watch_and_named_conditions_produce_nothing(real_rows, real_doc):
    for ticker in ("TMO", "DT", "ASX", "VEEV", "NTAP", "CNK", "TEAM"):
        matches = [r for r in real_doc["rows"] if r["ticker"] == ticker]
        for row in matches:
            out = P.evaluate_pma(row, _q(1_000_000.0, hi=1_000_000.0, lo=0.01), FINAL, True, True)
            assert out == [], f"{ticker} ({row['class']}) should never trigger"


def test_acceptance_second_day_replay_dedup_and_pruning(real_doc):
    """Simulates day 2: the SAME file (nothing retired yet, this is still
    the first real run) -- a trigger fired on day 1 must stay quiet, and
    once a row is later absent, its key prunes."""
    state = {"fired": []}
    row_a = next(r for r in real_doc["rows"] if r["ticker"] == "A")
    day1 = P.evaluate_pma(row_a, _q(175.5, hi=176.10), MID, False, False)
    for t in day1:
        S.mark_pma_fired(state, t["level"])
    day2 = P.evaluate_pma(row_a, _q(175.5, hi=176.10), _dt(2026, 10, 1, 12, 0), False, False)
    for t in day2:
        assert S.is_pma_fired(state, t["level"]), "must not re-fire on day 2"
    # A later file with "A" retired entirely.
    pruned = S.prune_pma_fired(state, live_base_ids=set())
    assert pruned == len(day1)
    for t in day1:
        assert not S.is_pma_fired(state, t["level"])


def test_acceptance_render_replay_email_to_html_and_plain(real_doc, real_rows, monkeypatch):
    """Renders a full replay digest from the real file + the handoff's own
    synthetic quotes, confirming both bodies come out non-empty and
    carry the expected content."""
    quotes = {
        "WEAT": _q(9.0), "NTRA": _q(238.0),
        "A": _q(175.40, hi=178.90),
        "PK": _q(16.30, hi=16.30),
        "MRVL": _q(238.0),
    }
    pma_triggers = []
    for (ticker, cls), row in real_rows.items():
        q = quotes.get(ticker)
        if not q:
            continue
        pma_triggers += P.evaluate_pma(row, q, MID, False, True)

    assert pma_triggers, "the replay must produce at least one trigger"

    captured = {}
    monkeypatch.setattr(E, "_send_resend",
                        lambda cfg, s, p, h: captured.update(subject=s, plain=p, html=h)
                        or {"ok": True})
    monkeypatch.setattr(E, "_cfg", lambda: {"resend_key": "fake", "from": "x", "to": "y",
                                            "smtp_user": "", "smtp_pw": None,
                                            "smtp_host": "", "smtp_port": 0})
    export = {"date": "2026-09-30", "regime": {"level": "RISK_ON"},
             "daily_list": [], "held_positions": []}
    res = E.send_digest([], export, pma_triggers=pma_triggers)
    assert res["ok"] is True
    assert "COMMITTEE LEVELS" in captured["plain"]
    assert "COMMITTEE LEVELS" in captured["html"]
    assert "DRAFT" in captured["plain"]
    assert "MRVL" in captured["plain"]


def test_acceptance_after_close_digest_renders_two_tables_and_watch(real_doc):
    quotes = {r["ticker"]: _q(100.0 + i) for i, r in enumerate(real_doc["rows"])}
    subject, plain, html = E.build_after_close_digest(real_doc, quotes)
    assert "HELD BOOK" in plain
    assert "SHORTLIST" in plain
    assert "WATCH" in plain
    assert "<table" in html


# ------------------------------------------------------- card redesign (PM
# feedback on the first production email, 2026-09-30): a breached stop must
# never read "away", the same position must never produce two cards, and
# the digest must group by what it's asking of the reader, not colour alone.


def test_pma_stop_word_away_when_price_is_safely_above():
    assert E._pma_stop_word(146.59, 141.10) == "3.7% away"


def test_pma_stop_word_breached_when_price_is_at_or_below():
    """The exact real production case (2026-09-30): USO live 146.59,
    committee exit 149.28 -- price is ALREADY below the stop, so this must
    never read "away"."""
    word = E._pma_stop_word(146.59, 149.28)
    assert "BREACHED" in word
    assert "1.8%" in word
    assert "away" not in word.lower()


def test_pma_stop_word_at_the_line_when_exactly_equal():
    assert E._pma_stop_word(100.0, 100.0) == "AT THE LINE"


def test_pma_target_word_away_before_reached():
    assert E._pma_target_word(175.40, 185.48) == "5.7% away"


def test_pma_target_word_reached_once_price_clears_it():
    word = E._pma_target_word(190.0, 185.48)
    assert "reached" in word.lower()
    assert "away" not in word.lower()


def test_number_line_uses_breach_phrasing_for_held_stops():
    line = E._pma_number_line({"ticker": "USO", "is_held": True, "live_px": 146.59,
                              "broker_stop": 141.10, "committee_exit": 149.28})
    assert "BREACHED by 1.8%" in line
    assert "149.28 (1.8% away)" not in line


def test_same_ticker_triggers_consolidate_into_one_card():
    """The exact shape of the real duplication bug: two triggers on the
    same HELD row (a literal committee trigger + the synthesized near-
    stops check) must produce ONE card, not two."""
    t1 = {"ticker": "USO", "source": "pma", "is_held": True, "level": "USO-committee|warn",
         "label": "closed below its line", "live_px": 146.59, "priority": "WARN",
         "action": "Closed under the committee's exit line 149.28.",
         "note": "Closed under the committee's exit line 149.28.",
         "kind": "close_below", "headline_phrase": "closed below its line",
         "broker_stop": 141.10, "committee_exit": 149.28, "carried": False,
         "trigger_id": "USO-committee", "intraday": {}}
    t2 = {"ticker": "USO", "source": "pma", "is_held": True, "level": "USO-nearstops|2026-09-30",
         "label": "Near your stops", "live_px": 146.59, "priority": "WARN",
         "action": "Price is close to one of your two stops.",
         "note": "Price is close to one of your two stops.",
         "kind": "near_stops", "headline_phrase": "near your stops",
         "broker_stop": 141.10, "committee_exit": 149.28, "carried": False,
         "trigger_id": None, "intraday": {}}
    _, plain, html = E._build_pma_section([t1, t2])
    assert plain.count("USO —") == 1, "must render exactly one USO card, not two"
    assert html.count("USO —") == 1
    # Both committee sentences must still be present, just inside one card.
    assert "Closed under the committee's exit line" in plain
    assert "Price is close to one of your two stops" in plain


def test_different_is_held_same_ticker_stay_separate_cards():
    """A ticker can carry both a HELD position and a separate
    HOLD_FOR_CONDITIONS add-idea (e.g. NTRA in the real file) -- these are
    genuinely different things and must NOT be merged."""
    held = {"ticker": "NTRA", "is_held": True, "priority": "WARN",
           "headline_phrase": "near your stops", "live_px": 350.0,
           "action": "held note", "note": "held note", "kind": "near_stops",
           "level": "NTRA-nearstops|2026-09-30", "carried": False, "intraday": {}}
    add_idea = {"ticker": "NTRA", "is_held": False, "priority": "WARN",
               "headline_phrase": "approaching its buy line", "live_px": 355.0,
               "action": "add idea note", "note": "add idea note",
               "kind": "approaching_entry", "level": "NTRA-entry|near",
               "carried": False, "intraday": {}}
    _, plain, _ = E._build_pma_section([held, add_idea])
    assert plain.count("NTRA —") == 2


def test_section_headers_group_held_buy_and_watch_separately():
    held = {"ticker": "A", "is_held": True, "priority": "ACTION",
           "headline_phrase": "has no stop order", "live_px": 10.0,
           "action": "x", "note": "x", "kind": "no_stop_order",
           "level": "A-nostop|2026-09-30", "carried": False, "intraday": {}}
    buy = {"ticker": "B", "is_held": False, "priority": "ACTION",
          "headline_phrase": "trading through a line", "live_px": 20.0,
          "action": "y", "note": "y", "kind": "close_above",
          "level": "B-cond|close", "carried": False, "intraday": {}}
    watch = {"ticker": "C", "is_held": False, "priority": "WARN",
            "headline_phrase": "approaching its buy line", "live_px": 30.0,
            "action": "z", "note": "z", "kind": "approaching_entry",
            "level": "C-entry|near", "carried": False, "intraday": {}}
    _, plain, _ = E._build_pma_section([held, buy, watch])
    held_idx = plain.index("HELD — needs your attention")
    buy_idx = plain.index("BUY CONDITIONS MET")
    watch_idx = plain.index("WATCHING")
    assert held_idx < buy_idx < watch_idx, "sections must render in act-first order"


def test_held_section_leads_even_when_action_priority_is_elsewhere():
    """HELD is its own section regardless of priority -- the PM's money
    outranks whatever triggered it, per the badge rule."""
    held_warn = {"ticker": "A", "is_held": True, "priority": "WARN",
                "headline_phrase": "near your stops", "live_px": 10.0,
                "action": "x", "note": "x", "kind": "near_stops",
                "level": "A-nearstops|2026-09-30", "carried": False, "intraday": {}}
    buy_action = {"ticker": "B", "is_held": False, "priority": "ACTION",
                 "headline_phrase": "trading through a line", "live_px": 20.0,
                 "action": "y", "note": "y", "kind": "close_above",
                 "level": "B-cond|close", "carried": False, "intraday": {}}
    _, plain, _ = E._build_pma_section([held_warn, buy_action])
    assert plain.index("HELD — needs your attention") < plain.index("BUY CONDITIONS MET")


def test_pma_group_bucket_classification():
    held_group = [{"is_held": True, "priority": "WARN", "kind": "near_stops"}]
    buy_group = [{"is_held": False, "priority": "ACTION", "kind": "close_above"}]
    watch_group = [{"is_held": False, "priority": "WARN", "kind": "approaching_entry"}]
    assert E._pma_group_bucket(held_group) == "held"
    assert E._pma_group_bucket(buy_group) == "buy"
    assert E._pma_group_bucket(watch_group) == "watch"


def test_pma_badge_never_shows_the_bare_word_warn():
    """A PM question (2026-09-30): does 'WARN' mean risk to my money or an
    entry setup to watch? The bare internal priority word answers neither,
    so the rendered badge must never show it -- a HELD warning reads
    CAUTION (risk, it's the PM's own book) and a shortlist warning reads
    WATCHING (entry-side, nothing to lose)."""
    held_warn = [{"is_held": True, "priority": "WARN", "kind": "near_stops"}]
    watch_warn = [{"is_held": False, "priority": "WARN", "kind": "approaching_entry"}]
    _, held_badge = E._pma_group_badge(held_warn)
    _, watch_badge = E._pma_group_badge(watch_warn)
    assert held_badge == "HELD · CAUTION"
    assert watch_badge == "WATCHING"
    for badge in (held_badge, watch_badge):
        assert "WARN" not in badge


def test_pma_rendered_cards_never_show_the_bare_word_warn():
    """End-to-end: the same guarantee, through the actual card renderers
    the emailer sends, for both a HELD risk card and a shortlist watch
    card."""
    held = {"ticker": "A", "is_held": True, "priority": "WARN",
            "headline_phrase": "near your stops", "live_px": 10.0,
            "action": "Price is close to one of your two stops.",
            "note": "Price is close to one of your two stops.",
            "kind": "near_stops", "level": "A-nearstops|2026-09-30",
            "carried": False, "intraday": {}}
    watch = {"ticker": "C", "is_held": False, "priority": "WARN",
             "headline_phrase": "approaching its buy line", "live_px": 30.0,
             "action": "Getting close to the committee's buy line.",
             "note": "Getting close to the committee's buy line.",
             "kind": "approaching_entry", "level": "C-entry|near",
             "carried": False, "intraday": {}}
    for group in ([held], [watch]):
        assert "WARN" not in E._pma_card_plain(group)
        assert "WARN" not in E._pma_card_html(group)


def test_pma_primary_prefers_action_and_specific_over_generic():
    generic_action = {"priority": "ACTION", "kind": "near_stops"}
    specific_action = {"priority": "ACTION", "kind": "close_below"}
    warn = {"priority": "WARN", "kind": "close_below"}
    assert E._pma_primary([generic_action, specific_action]) is specific_action
    assert E._pma_primary([warn, specific_action]) is specific_action


def test_pma_group_sentences_deduplicates_identical_text():
    t1 = {"priority": "ACTION", "kind": "close_below", "action": "same text", "note": "same text"}
    t2 = {"priority": "WARN", "kind": "near_stops", "action": "same text", "note": "same text"}
    t3 = {"priority": "WARN", "kind": "near_stops", "action": "different text", "note": "different text"}
    sentences = E._pma_group_sentences([t1, t2, t3])
    assert sentences.count("same text") == 1
    assert "different text" in sentences


# ---------------------------------------------------- intraday context (volume)


def test_evaluate_pma_attaches_real_intraday_context_not_a_stub():
    """Answers the PM's own question: is this only watching price? No --
    the same COIL/THRUST/FAILED_PUSH + volume-pace read the legacy
    heartbeat already uses is now attached here too (annotation only, per
    that module's own discipline -- it never fires its own alert)."""
    row = {"ticker": "BE", "class": "ADVANCE", "atr_14d": 5.0,
          "levels": {"stop": 280.0, "tp": [302.99]},
          "triggers": [{"id": "BE-cond", "kind": "close_above", "level": 288.0,
                       "basis": "daily", "priority": "ACTION", "action": "x"}]}
    # A tight, held-near-highs read with the elapsed fraction high enough
    # to classify -- late-session so MIN_ELAPSED_FRACTION is cleared.
    quote = {"price": 289.96, "day_high": 290.0, "day_low": 289.8, "prev_close": 288.0}
    out = P.evaluate_pma(row, quote, FINAL, True, False)
    assert out
    assert out[0]["intraday"] != {}
    assert "signature" in out[0]["intraday"]


def test_pma_group_signature_surfaces_on_the_card():
    t = {"ticker": "BE", "is_held": False, "priority": "ACTION",
        "headline_phrase": "trading through a line", "live_px": 289.96,
        "action": "x", "note": "x", "kind": "close_above", "level": "BE-cond|close",
        "carried": False, "intraday": {"signature": "COIL"}}
    _, plain, html = E._build_pma_section([t])
    assert "COIL" in plain
    assert "COIL" in html


def test_pma_group_signature_absent_when_no_intraday_reads():
    t = {"ticker": "BE", "is_held": False, "priority": "ACTION",
        "headline_phrase": "trading through a line", "live_px": 289.96,
        "action": "x", "note": "x", "kind": "close_above", "level": "BE-cond|close",
        "carried": False, "intraday": {}}
    _, plain, _ = E._build_pma_section([t])
    assert "⟨" not in plain
