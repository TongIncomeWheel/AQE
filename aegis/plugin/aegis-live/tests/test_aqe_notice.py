"""aqe_notice.py -- the cockpit reader for the AQE alert notice (aqe_alert_notice.v1)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "aqe_notice.py"
spec = importlib.util.spec_from_file_location("aqe_notice", TOOL)
N = importlib.util.module_from_spec(spec)
spec.loader.exec_module(N)

IN_WINDOW_NOW = "2026-11-02T15:20:00+00:00"      # 10:20 ET Mon = 23:20 SGT
OUT_WINDOW_NOW = "2026-11-02T08:00:00+00:00"     # 03:00 ET


def base(**kw):
    d = {
        "schema": "aqe_alert_notice.v1", "seq": 3, "session_date": "2026-11-02",
        "cycle_at_utc": "2026-11-02T15:16:00+00:00", "cycle_at_sgt": "2026-11-02 23:16 SGT",
        "cycle_at_et": "10:16 ET", "source": "hf",
        "data": {"pma_run": "2026-11-02", "pma_session": "2026-11-02", "pma_missing": None,
                 "aqe_date": "2026-10-30", "aqe_covers": "2026-10-30", "aqe_current": True},
        "market": {"status": "ACTIVE", "state": "INTACT", "broken": False, "just_broke": False,
                   "plain": "void if SPY closes under the 750 put wall", "line": "Market condition (holding): void if SPY closes under the 750 put wall"},
        "actionable": False, "items": [], "setups_forming": [], "suppressed": 0,
        "quiet_line": "23:16 SGT · AQE: no trigger, no action.",
        "email": {"sent": False, "subject": None},
    }
    d.update(kw)
    return d


ITEMS = [
    {"ticker": "DBX", "class": "HOLD_FOR_CONDITIONS", "held": False, "states": ["FAILED_PUSH"], "severity": "INFO",
     "headline": "DBX $30.10 · BACK UNDER", "action": "Back under its buy price: wait", "price": 30.1, "day_pct": -0.4,
     "entry": 30.5, "stop": 28.9, "stop_type": "committee", "target": 33.0, "risk_per_share": 1.6, "lines": []},
    {"ticker": "MP", "class": "HELD", "held": True, "states": ["near_stops"], "severity": "RISK",
     "headline": "MP $61.20 · NEAR YOUR STOP", "action": "Near your broker stop: check it", "price": 61.2, "day_pct": -3.1,
     "entry": None, "stop": 60.0, "stop_type": "broker", "target": None, "risk_per_share": None, "lines": []},
    {"ticker": "IOT", "class": "ADVANCE", "held": False, "states": ["CONDITION_MET"], "severity": "ACT",
     "headline": "IOT $41.30 · BUY MET", "action": "Buy trigger hit: queue the Tiger preview on your word", "price": 41.3,
     "day_pct": 2.2, "entry": 41.0, "stop": 39.45, "stop_type": "committee", "target": 44.0, "risk_per_share": 1.55,
     "conditions": {"met": 3, "of": 3, "who": "Committee"}, "lines": ["AQE default criteria: all met"]},
]


def write(tmp_path, doc, name="latest.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def run(tmp_path, doc, capsys, *extra, state="st.json", now=IN_WINDOW_NOW):
    f = write(tmp_path, doc)
    rc = N.main(["render", "--file", str(f), "--state", str(tmp_path / state), "--one-r", "620", "--now", now, *extra])
    return rc, capsys.readouterr().out


def test_actionable_renders_table_act_first_with_shares(tmp_path, capsys):
    rc, out = run(tmp_path, base(actionable=True, items=ITEMS, setups_forming=[{"ticker": "ZS", "price": 1, "text": "x"}, {"ticker": "GTLB", "text": "y"}]), capsys)
    assert rc == 0
    lines = out.splitlines()
    assert lines[0] == "23:16 SGT · AQE cycle 3 · PMA run 2026-11-02 · AQE export 2026-10-30"
    assert "Market condition" not in out                   # PM 2026-11-02: no market sentence in the cockpit
    rows = [l for l in lines if l.startswith("| ") and "Name" not in l]
    assert rows[0].startswith("| IOT") and "| MP (you hold)" in rows[1] and rows[2].startswith("| DBX")
    assert "~400 sh at stop 39.45" in rows[0]              # floor(620/1.55)
    assert "buy above 41.00 · stop 39.45" in rows[0]
    assert "Setups forming: ZS, GTLB" in out
    assert "arithmetic, not a recommendation" in out
    assert "▲NEW" not in out                                # first render: nothing to compare against


def test_quiet_notice_exits_3_silent_unless_quiet_line(tmp_path, capsys):
    rc, out = run(tmp_path, base(), capsys)
    assert rc == 3 and out == ""
    rc, out = run(tmp_path, base(seq=4), capsys, "--quiet-line")
    assert rc == 3 and out.strip() == "23:16 SGT · AQE: no trigger, no action."


def test_dedup_same_seq_prints_nothing_new_seq_marks_new_rows(tmp_path, capsys):
    doc = base(actionable=True, items=ITEMS[:1])
    rc, out = run(tmp_path, doc, capsys)
    assert rc == 0 and "DBX" in out
    rc, out = run(tmp_path, doc, capsys)
    assert rc == 3 and out == ""                             # same (session, seq) -> nothing
    doc2 = base(seq=4, actionable=True, items=ITEMS)
    rc, out = run(tmp_path, doc2, capsys)
    assert rc == 0
    assert re.search(r"\| IOT ▲NEW", out) and re.search(r"\| MP \(you hold\) ▲NEW", out)
    assert not re.search(r"\| DBX ▲NEW", out)
    assert "Market condition" not in out                     # not first of session, market intact -> silent


def test_broken_market_is_a_row_not_a_sentence(tmp_path, capsys):
    mk = {"status": "ACTIVE", "state": "BROKEN", "broken": True, "just_broke": True}
    row = {"ticker": "SPY", "class": "MARKET", "held": False, "states": ["MARKET_KILL"], "severity": "RISK",
           "headline": "SPY · MARKET CONDITION BROKEN — take no new triggers",
           "action": "Market condition broken: no new buys this session", "price": None, "lines": []}
    rc, out = run(tmp_path, base(actionable=True, market=mk, items=[row, ITEMS[1]], suppressed=2), capsys)
    assert rc == 0 and "MARKET CONDITION BROKEN" in out and "2 entry alerts suppressed by the broken market condition" in out
    assert "⛔" not in out


def test_stale_inside_window_exit_4_outside_window_not_stale(tmp_path, capsys):
    old = base(actionable=True, items=ITEMS[:1], cycle_at_utc="2026-11-02T14:10:00+00:00", cycle_at_sgt="2026-11-02 22:10 SGT")
    rc, out = run(tmp_path, old, capsys, now="2026-11-02T15:20:00+00:00")   # 70 min, in window
    assert rc == 4 and out.startswith("AQE alert engine silent: last cycle 22:10 SGT (70 min ago)")
    rc, out = run(tmp_path, old, capsys, state="st2.json", now="2026-11-03T08:00:00+00:00")  # out of window
    assert rc == 0 and "DBX" in out


def test_missing_file_exit_5(tmp_path, capsys):
    rc = N.main(["render", "--file", str(tmp_path / "nope.json"), "--state", str(tmp_path / "s.json")])
    assert rc == 5 and capsys.readouterr().out.startswith("No AQE notice published yet")


def test_malformed_items_do_not_raise(tmp_path, capsys):
    items = [{"severity": "ACT", "action": "x"}, {"ticker": "A", "severity": "ACT", "price": "n/a", "entry": None, "stop": None, "states": ["CONDITION_MET"]}]
    rc, out = run(tmp_path, base(actionable=True, items=items, seq="7", suppressed="1"), capsys)
    assert rc == 0
    assert "1 item unreadable" in out and "| A ▲NEW" not in out and "| A |" in out
    assert "no stop known, no share count" in out


def test_house_wording_no_banned_phrases(tmp_path, capsys):
    items = [dict(ITEMS[2], action="Buy trigger hit under AQE default criteria: queue the Tiger preview on your word")] + ITEMS[:2]
    rc, out = run(tmp_path, base(actionable=True, items=items, data={"pma_run": None, "pma_missing": "2026-10-29", "aqe_date": "2026-10-28", "aqe_current": False}), capsys)
    assert rc == 0
    assert N.wording_check(out) == []
    assert "AQE criteria" in out and "AQE default" not in out
    assert "No PMA file for today's session (latest is 2026-10-29)" in out
    assert "older than the last close" in out


def test_status_one_line(tmp_path, capsys):
    f = write(tmp_path, base(email={"sent": True, "subject": "x"}))
    rc = N.main(["status", "--file", str(f), "--now", IN_WINDOW_NOW])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("AQE notice: cycle 3 at 2026-11-02 23:16 SGT (4 min ago)") and "email sent true" in out


def test_one_r_read_from_fund_file(tmp_path):
    (tmp_path / "aegis/plugin/aegis-core/config").mkdir(parents=True)
    (tmp_path / N.FUND_PATH).write_text("x: 1\none_r_usd: 700\n", encoding="utf-8")
    assert N.one_r_from_fund(str(tmp_path)) == 700.0
    assert N.one_r_from_fund(str(tmp_path / "missing")) == 620.0


def test_alarm_record_prints_once_and_exits_4(tmp_path, capsys):
    doc = base(actionable=True, seq=9, alarm={"kind": "engine_silent", "reason": "no completed cycle for 52 min",
                                             "text": "AQE ALERT ENGINE SILENT: no completed cycle for 52 min. Levels are NOT being watched."})
    rc, out = run(tmp_path, doc, capsys)
    assert rc == 4 and out.startswith("AQE ALERT ENGINE SILENT")
    rc, out = run(tmp_path, doc, capsys)        # same record again: already shown
    assert rc == 3 and out == ""
