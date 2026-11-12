"""Conductor 2026-11-12, three findings from the 12 Nov run:
1 held_view / broker stops must handle SHORTS (SPCX -68 with a live BUY stop above entry),
2 repeat-watch refuses when the phase-4 ledger has no row for the run date,
3 the repeat-watch text names the PRIOR sessions it compares with, not today."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
sys.path.insert(0, str(TOOLS))
import held_view as HV  # noqa: E402

PIPE = TOOLS / "pma_pipeline.py"
LEVELS = TOOLS / "pma_levels.py"


def short_row(t="SPCX", entry=142.35, live=145.0, qty=-68):
    return {"ticker": t, "entry": entry, "live_px": live, "qty": qty, "unreal_usd": round((live - entry) * qty, 2),
            "bracket": {"valid": False, "stop": None, "atr_fallback_stop": 135.0},        # a long-side fallback BELOW entry: not a short's stop
            "extension_bracket": {"available": False, "stop": None}}


def test_a_short_with_a_buy_stop_above_entry_has_positive_risk_open_r_and_no_set_stop():
    v = HV.held_view({"held_positions": [short_row()]}, {"positions": {"SPCX": {"stop": 148.15}}}, one_r=620)[0]
    assert v["side"] == "short" and v["action"] is None and v["broker_stop_status"] == "broker buy stop 148.15"
    assert v["r_per_share"] == round(148.15 - 142.35, 4)
    assert v["risk_usd"] == round(68 * (148.15 - 142.35), 2) and v["risk_usd"] > 0
    assert v["open_r"] == round((142.35 - 145.0) / (148.15 - 142.35), 2)        # price rose against the short: negative R
    assert v["pnl_usd"] == round((145.0 - 142.35) * -68, 2)


def test_a_short_with_no_buy_stop_says_so_and_never_borrows_a_long_side_stop_below_entry():
    v = HV.held_view({"held_positions": [short_row()]}, {"positions": {}}, one_r=620)[0]
    assert v["action"] == "SET-STOP" and v["broker_stop_status"] == "NO STOP AT BROKER"
    assert v["reference_stop"] is None and v["risk_usd"] is None and v["open_r"] is None


def test_longs_are_unchanged():
    long_ = {"ticker": "EBAY", "entry": 100.0, "live_px": 103.0, "qty": 10, "unreal_usd": 30.0, "bracket": {"valid": False, "atr_fallback_stop": 97.0},
             "extension_bracket": {"available": False}}
    v = HV.held_view({"held_positions": [long_]}, {"positions": {}}, one_r=620)[0]
    assert v["side"] == "long" and v["r_per_share"] == 3.0 and v["open_r"] == 1.0 and v["risk_usd"] == 30.0


def test_broker_stops_maps_a_buy_stop_to_a_short_and_a_sell_stop_to_a_long(tmp_path):
    orders = [{"symbol": "SPCX", "action": "BUY", "order_type": "STP", "stop_price": 148.15, "quantity": 68, "sec_type": "STK"},
              {"symbol": "SPCX", "action": "SELL", "order_type": "STP", "stop_price": 120.0, "quantity": 68, "sec_type": "STK"},   # wrong side for a short: ignored
              {"symbol": "EBAY", "action": "SELL", "order_type": "STP", "stop_price": 119.0, "quantity": 150, "sec_type": "STK"},
              {"symbol": "EBAY", "action": "BUY", "order_type": "STP", "stop_price": 130.0, "quantity": 150, "sec_type": "STK"}]   # wrong side for a long: ignored
    positions = [{"symbol": "SPCX", "quantity": -68, "avg_cost": 142.35, "market_price": 145.0, "sec_type": "STK"},
                 {"symbol": "EBAY", "quantity": 150, "avg_cost": 122.9, "market_price": 123.5, "sec_type": "STK"}]
    (tmp_path / "o.json").write_text(json.dumps(orders)); (tmp_path / "p.json").write_text(json.dumps(positions))
    r = subprocess.run([sys.executable, str(LEVELS), "stops", "--orders", str(tmp_path / "o.json"), "--positions", str(tmp_path / "p.json"),
                        "--out", str(tmp_path / "bs.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    pos = json.loads((tmp_path / "bs.json").read_text())["positions"]
    assert pos["SPCX"]["stop"] == 148.15 and pos["EBAY"]["stop"] == 119.0
    assert not pos["SPCX"].get("note") and not pos["EBAY"].get("note")           # 68 of 68 shares covered: no 'covers n of m' note for a negative quantity


def _ledger(path, dates):
    path.write_text(json.dumps({"window_sessions": 5, "retention_sessions": 20, "repeat_threshold": 2,
                                "entries": [{"date": d, "tickers": ["AAA", "BBB"]} for d in dates],
                                "repeat_flags": [{"ticker": "AAA", "appearances": len(dates), "window": len(dates)}]}))


def _rw(tmp_path, date):
    return subprocess.run([sys.executable, str(PIPE), "repeat-watch", "--ledger", str(tmp_path / "led.json"), "--verdicts", str(tmp_path / "none.json"),
                           "--date", date, "--out", str(tmp_path / "rw.json")], capture_output=True, text=True)


def test_repeat_watch_refuses_when_the_ledger_has_no_row_for_the_run_date(tmp_path):
    _ledger(tmp_path / "led.json", ["2026-11-09", "2026-11-10", "2026-11-11"])
    r = _rw(tmp_path, "2026-11-12")
    assert r.returncode != 0 and "REFUSED" in (r.stderr + r.stdout) and "2026-11-12" in (r.stderr + r.stdout) and "ledger" in (r.stderr + r.stdout)
    assert not (tmp_path / "rw.json").exists()


def test_repeat_watch_names_the_prior_sessions_it_compares_with_not_today(tmp_path):
    _ledger(tmp_path / "led.json", ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"])
    r = _rw(tmp_path, "2026-11-12")
    assert r.returncode == 0, r.stderr
    md = json.loads((tmp_path / "rw.json").read_text())["markdown"]
    assert "The list compared is the 2026-11-12 session" not in md
    assert "compared with the 3 sessions before it (2026-11-09 to 2026-11-11)" in md
    assert "NEW" in md and "REMAIN" in md and "LEFT" in md                    # the count line the gate reads is intact


def test_the_first_ever_session_says_there_is_nothing_to_compare_with(tmp_path):
    _ledger(tmp_path / "led.json", ["2026-11-12"])
    r = _rw(tmp_path, "2026-11-12")
    assert r.returncode == 0, r.stderr
    assert "no earlier session on the ledger" in json.loads((tmp_path / "rw.json").read_text())["markdown"]
