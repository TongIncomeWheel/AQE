"""The cockpit notice (PM 2026-11-02): one record per cycle, from the email's own cards."""
import json
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import notice as N

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 2, 10, 16, tzinfo=ET)

ROW = {"ticker": "HPE", "class": "ADVANCE", "atr_14d": 2.0,
       "levels": {"stop": 60.1, "stop_type": "swing_low", "tp": [66.0, 68.0]},
       "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 62.15}],
                                 "confirm": [{"w": "vol_x_ge", "x": 1.0}], "no_shared_buy": False},
                      "exits": [], "analysts": []}}
EV = {"buy_met": True, "lit": [], "n_counting": 0,
      "shared_buy_detail": [({"w": "h1_close_above", "level": 62.15}, "TRUE")],
      "shared_confirm_detail": [({"w": "vol_x_ge", "x": 1.0}, "TRUE")]}
LIVE = {"price": 64.2, "prev_close": 61.0, "day_high": 64.5, "day_low": 61.9,
        "unr": {"status": "NONE", "armed": [], "stop": None, "volume": {}},
        "vwap_trigger": {"state": "NOT_READY"}, "vol_x": {"so_far": 1.4}, "ema": {}, "elder": {}}
CARD = ("HPE", ROW, EV, ["CONDITION_MET"], LIVE)
SETUP = ("DELL", dict(ROW, ticker="DELL"), dict(EV, buy_met=False),
         ["UNR_ARMED"], dict(LIVE, unr={"status": "ARMED", "stop": 60.0, "volume": {},
                                        "armed": [{"name": "ema21", "level": 63.0, "reclaimed": True, "when": "today", "depth_atr": 0.4}]}))
HELD_EV = {"ticker": "MP", "kind": "near_stops", "level": "MP-nearstops|2026-11-02", "live_px": 37.4,
           "chg_pct": -2.1, "broker_stop": 36.66, "committee_exit": None, "is_held": True,
           "broker_stop_dist_pct": 2.0}
META = {"pma_run": "2026-11-02", "pma_session": "2026-11-02", "aqe_date": "2026-10-31",
        "aqe_covers": "2026-10-30", "aqe_current": True,
        "market_kill": {"status": "ACTIVE", "state": "INTACT", "broken": False, "just_broke": False,
                        "plain": "void if SPY closes under 750", "kill": {}}}


def _build(**kw):
    args = dict(cards=[CARD], setup_rows=[SETUP], held_events=[HELD_EV], meta=META,
                email={"ok": True, "subject": "[AQE] 10:16 ET conditions · 2 cards"},
                engine={"checked": 40, "new_triggers": 1, "pma_fresh": True, "suppressed": 0},
                now_et=NOW, seq=3, source="hf")
    args.update(kw)
    return N.build(**args)


def test_actionable_notice_matches_the_email_cards():
    n = _build()
    assert n["schema"] == "aqe_alert_notice.v1" and n["seq"] == 3 and n["session_date"] == "2026-11-02"
    assert n["cycle_at_sgt"] == "2026-11-02 23:16 SGT" and n["cycle_at_et"] == "10:16 ET"
    assert n["actionable"] and n["quiet_line"] is None
    acts = [i for i in n["items"] if i["severity"] == "ACT"]
    assert acts[0]["ticker"] == "HPE" and acts[0]["entry"] == 62.15 and acts[0]["stop"] == 60.1
    assert acts[0]["target"] == 66.0 and acts[0]["risk_per_share"] == pytest.approx(2.05)
    assert acts[0]["conditions"] == {"met": 2, "of": 2, "who": "Committee (ADVANCE)"}
    assert "HPE" in acts[0]["headline"] and acts[0]["lines"]
    assert acts[0]["action"].startswith("Buy trigger hit")
    held = [i for i in n["items"] if i["held"]][0]
    assert held["severity"] == "RISK" and held["stop"] == 36.66 and held["stop_type"] == "broker"
    assert [i["severity"] for i in n["items"]] == ["ACT", "RISK"]           # ACT first
    assert n["setups_forming"][0]["ticker"] == "DELL" and "DELL" in n["setups_forming"][0]["text"]
    assert n["email"] == {"sent": True, "subject": "[AQE] 10:16 ET conditions · 2 cards"}
    assert n["data"]["pma_run"] == "2026-11-02" and n["market"]["state"] == "INTACT"
    json.dumps(n)  # serialisable


def test_quiet_cycle_is_a_real_answer():
    n = _build(cards=[], setup_rows=[], held_events=[], email=None)
    assert not n["actionable"] and n["items"] == []
    assert n["quiet_line"] == "23:16 SGT · AQE: no trigger, no action."
    assert n["email"] == {"sent": None, "subject": None}


def test_market_just_broke_is_actionable_without_cards():
    meta = dict(META, market_kill=dict(META["market_kill"], state="BROKEN", broken=True, just_broke=True,
                                       detail="SPY at 749"))
    n = _build(cards=[], setup_rows=[], held_events=[], meta=meta)
    assert n["actionable"] and n["market"]["broken"] and "take no new triggers" in n["market"]["line"]


def test_unr_trigger_uses_low_of_day_stop_and_spot_entry():
    live = dict(LIVE, unr={"status": "ARMED", "stop": 63.1, "volume": {},
                           "armed": [{"name": "ema21", "level": 63.5, "reclaimed": True, "when": "today", "depth_atr": 0.4}]},
                vwap_trigger={"state": "TRIGGERED", "vwap": 63.9, "at": "10:15", "close": 64.2, "entry": 64.2})
    n = _build(cards=[("HPE", ROW, dict(EV, buy_met=False), ["UNR_TRIGGER"], live)], held_events=[], setup_rows=[])
    it = n["items"][0]
    assert it["severity"] == "ACT" and it["entry"] == 64.2 and it["stop"] == 63.1 and it["stop_type"] == "unr_low_of_day"


def test_broken_market_marks_entries_suppressed():
    meta = dict(META, market_kill=dict(META["market_kill"], state="BROKEN", broken=True))
    n = _build(meta=meta)
    assert [i for i in n["items"] if i["ticker"] == "HPE"][0]["suppressed_by_market_kill"] is True
    assert [i for i in n["items"] if i["held"]][0]["suppressed_by_market_kill"] is False


def test_a_bad_card_never_drops_the_notice():
    n = _build(cards=[CARD, ("BAD", None, None, ["CONDITION_MET"], None)], held_events=[], setup_rows=[])
    assert {i["ticker"] for i in n["items"]} == {"HPE", "BAD"}
    assert "unreadable" in [i for i in n["items"] if i["ticker"] == "BAD"][0]["headline"]


def test_seq_continues_within_a_session_and_resets_on_a_new_date(monkeypatch, tmp_path):
    monkeypatch.setattr(N, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(N, "_drive", lambda: None)
    (tmp_path / "latest.json").write_text(json.dumps({"session_date": "2026-11-02", "seq": 7}))
    assert N._next_seq("2026-11-02") == 8 and N._next_seq("2026-11-03") == 1


def test_publish_names_every_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(N, "LOCAL_DIR", tmp_path)
    class Drive:
        def upload_or_replace(self, *a, **k): raise OSError("drive down")
    monkeypatch.setattr(N, "_drive", lambda: Drive())
    import src.data.github_sync as GS
    monkeypatch.setattr(GS, "is_configured", lambda: True)
    monkeypatch.setattr(GS, "put_file", lambda p, c, m: {"ok": False, "reason": "403"})
    monkeypatch.setattr(GS, "get_file", lambda p: {"ok": False})
    res = N.publish(_build())
    assert res["local"] == "ok" and "drive down" in res["drive"] and res["github_latest"] == "failed: 403"


def test_publish_prepends_to_the_days_list_and_dedups_seq(monkeypatch, tmp_path):
    monkeypatch.setattr(N, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(N, "_drive", lambda: None)
    import src.data.github_sync as GS
    store = {f"{N.REPO_DIR}/2026-11-02.json": json.dumps([{"seq": 2}, {"seq": 3, "old": True}])}
    monkeypatch.setattr(GS, "is_configured", lambda: True)
    monkeypatch.setattr(GS, "get_file", lambda p: {"ok": p in store, "text": store.get(p)})
    monkeypatch.setattr(GS, "put_file", lambda p, c, m: store.__setitem__(p, c) or {"ok": True})
    N.publish(_build(seq=3))
    day = json.loads(store[f"{N.REPO_DIR}/2026-11-02.json"])
    assert [d["seq"] for d in day] == [3, 2] and "old" not in day[0]


def test_engine_wrapper_publishes_from_the_stashed_inputs(monkeypatch):
    from src.alerts import engine as E
    import src.alerts.heartbeat as H
    monkeypatch.setattr(H, "beat", lambda *a, **k: {})
    got = []
    monkeypatch.setattr(N, "publish", lambda n: got.append(n) or {"local": "ok"})
    monkeypatch.setattr(N, "_next_seq", lambda d: 1)
    monkeypatch.setattr(E, "_run_alert_cycle", lambda **k: {
        "ok": True, "in_window": True, "checked": 5, "new_triggers": 1, "pma": {"fresh": True},
        "pma_conditions": {"enabled": True},
        "_notice": {"cards": [CARD], "setup_rows": [], "held_events": [], "meta": META,
                    "email": {"ok": True, "subject": "s"}}})
    s = E.run_alert_cycle()
    assert got and got[0]["items"][0]["ticker"] == "HPE" and s["notice"]["actionable"]
    assert "_notice" not in s


def test_end_to_end_writer_to_cockpit_reader(tmp_path):
    """The engine's notice renders in the cockpit reader without a single
    hand-edit: the contract holds across the two sides."""
    n = _build()
    f = tmp_path / "latest.json"
    f.write_text(json.dumps(n, default=str))
    tool = "aegis/plugin/aegis-live/tools/aqe_notice.py"
    r = subprocess.run([sys.executable, tool, "render", "--file", str(f),
                        "--state", str(tmp_path / "st.json"), "--one-r", "620",
                        "--now", "2026-11-02T15:20:00+00:00"],      # 4 min after the cycle
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "HPE" in out and "MP" in out and "DELL" in out
    assert "~302 sh" in out            # floor(620 / 2.05)
    assert "AQE default" not in out and "hourly close" not in out


def test_alarm_record_is_a_distinct_actionable_notice_with_no_items(monkeypatch, tmp_path):
    monkeypatch.setattr(N, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(N, "_drive", lambda: None)
    monkeypatch.setattr(N, "publish", lambda d: {"local": "ok", "drive": "ok"})
    res = N.publish_alarm("no completed cycle for 52 min", last_primary_utc="2026-11-02T14:10:00+00:00",
                          now_et=NOW, source="gha")
    d = res["notice"]
    assert d["schema"] == N.SCHEMA and d["actionable"] and d["items"] == [] and d["alarm"]["kind"] == "engine_silent"
    assert "NOT being watched" in d["alarm"]["text"] and d["seq"] == 1
    # and the reader shows it as the silent headline, exit 4
    f = tmp_path / "alarm.json"
    f.write_text(json.dumps(d, default=str))
    r = subprocess.run([sys.executable, "aegis/plugin/aegis-live/tools/aqe_notice.py", "render", "--file", str(f),
                        "--state", str(tmp_path / "st.json")], capture_output=True, text=True)
    assert r.returncode == 4 and r.stdout.startswith("AQE ALERT ENGINE SILENT")
