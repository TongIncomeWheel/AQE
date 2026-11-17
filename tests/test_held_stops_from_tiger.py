"""PM 2026-11-02: "Stop from Tiger is correct. That's the dependency ... ask for the stops then,
both from the trade report and also during the AQE run."

held_sl was null on every export row because the close never read Tiger's working orders. These
tests pin the two-read design: the close's journal (book of record) and the pre-AQE Tiger read,
merged by src/data/broker_stops.py, every disagreement named, every gap loud.
"""
from datetime import datetime, timezone

from src.data import broker_stops as bs

# The live shape, read-only, 2026-11-02 (Tiger_MCPv7 get_open_orders / get_stock_positions).
ORDERS = {"result": [
    {"id": 45103865188585470, "status": "HELD", "action": "SELL", "order_type": "STP_LMT",
     "sec_type": "STK", "symbol": "V", "quantity": 38, "limit_price": 390.8, "stop_price": 391.8,
     "time_in_force": "GTC"},
    {"id": 45055449810862080, "status": "HELD", "action": "SELL", "order_type": "STP_LMT",
     "sec_type": "STK", "symbol": "MP", "quantity": 300, "limit_price": 36.66, "stop_price": 36.66,
     "time_in_force": "GTC"},
    {"id": 1, "status": "HELD", "action": "SELL", "order_type": "LMT", "sec_type": "STK",
     "symbol": "CRCL", "quantity": 300, "limit_price": 95.0, "stop_price": None},
]}
POSITIONS = {"result": [
    {"symbol": "MARA", "sec_type": "STK", "quantity": 17000},
    {"symbol": "MP", "sec_type": "STK", "quantity": 300},
    {"symbol": "V", "sec_type": "STK", "quantity": 38},
]}
NOW = datetime(2026, 11, 2, 22, 40, tzinfo=timezone.utc)          # 06:40 SGT Tuesday
READ = {"pulled_at_utc": "2026-11-02T22:20:00Z", "date_sgt": "2026-11-03",
        "open_orders": ORDERS, "stock_positions": POSITIONS}
MP = {"ticker": "MP", "qty": 300, "stop_live_broker": 36.66,
      "stop_order": {"type": "STP_LMT", "stop": 36.66, "limit": 36.66, "qty": 300}}
V = {"ticker": "V", "qty": 38, "stop_live_broker": 391.8,
     "stop_order": {"type": "STP_LMT", "stop": 391.8, "limit": 390.8, "qty": 38}}


def test_stops_are_read_from_working_sell_stop_orders_only():
    s = bs.stops_from_orders(ORDERS)
    assert set(s) == {"V", "MP"}                     # a plain sell limit is not a stop
    assert s["V"]["stop"] == 391.8 and s["V"]["limit"] == 390.8 and s["V"]["qty"] == 38
    assert s["V"]["time_in_force"] == "GTC"


def test_both_reads_agree_and_held_sl_is_the_broker_stop():
    second = bs.parse_second_read(READ)
    r = bs.resolve(MP, "2026-11-02", True, second, now=NOW)
    assert r["held_sl"] == 36.66 and r["held_stop_status"] == "LIVE"
    assert r["held_stop_check"] == "AGREES" and r["held_stop_source"] == "tiger_pre_aqe_read"


def test_a_stop_moved_after_the_close_uses_the_later_read_and_says_so():
    moved = {"result": [dict(ORDERS["result"][1], stop_price=38.0, limit_price=38.0)]}
    second = bs.parse_second_read(dict(READ, open_orders=moved))
    r = bs.resolve(MP, "2026-11-02", True, second, now=NOW)
    assert r["held_sl"] == 38.0
    assert r["held_stop_check"].startswith("DIFFERS") and "36.66 -> Tiger 38.0" in r["held_stop_check"]


def test_a_stop_cancelled_after_the_close_is_unprotected_not_yesterdays_number():
    second = bs.parse_second_read(dict(READ, open_orders={"result": [ORDERS["result"][0]]}))
    r = bs.resolve(MP, "2026-11-02", True, second, now=NOW)
    assert r["held_sl"] is None and r["held_stop_status"] == "NO_STOP_ORDER"
    assert "NO working stop" in r["held_stop_check"]


def test_without_a_second_read_the_journal_stop_is_used_and_the_gap_is_named():
    r = bs.resolve(V, "2026-11-02", True, {"ok": False, "reason": "not found"}, now=NOW)
    assert r["held_sl"] == 391.8 and r["held_stop_source"] == "journal 2026-11-02"
    assert r["held_stop_check"].startswith("NO_SECOND_READ: not found")


def test_a_stale_second_read_is_not_trusted():
    old = bs.parse_second_read(dict(READ, pulled_at_utc="2026-10-30T22:20:00Z"))
    r = bs.resolve(V, "2026-11-02", True, old, now=NOW)
    assert r["held_stop_source"].startswith("journal")


def test_a_close_that_did_not_read_the_orders_is_not_pulled_never_no_stop():
    r = bs.resolve({"ticker": "V", "qty": 38, "stop_live_broker": None}, "2026-10-30", None, None, now=NOW)
    assert r["held_stop_status"] == "NOT_PULLED" and r["held_sl"] is None
    summary = bs.summarise([dict(r, ticker="V")], "2026-10-30", None, None)
    assert summary["status"] == "NOT_PULLED" and summary["not_pulled"] == ["V"]


def test_partial_cover_and_a_name_gone_from_the_broker_are_named():
    half = {"result": [dict(ORDERS["result"][1], quantity=100)]}
    r = bs.resolve(MP, "2026-11-02", True, bs.parse_second_read(dict(READ, open_orders=half)), now=NOW)
    assert "covers 100 of 300 shares" in r["held_stop_check"]
    gone = bs.parse_second_read(dict(READ, stock_positions={"result": []}))
    r = bs.resolve(V, "2026-11-02", True, gone, now=NOW)
    assert "not held at Tiger" in r["held_stop_check"]


def test_summary_rolls_up_the_book():
    second = bs.parse_second_read(READ)
    rows = [dict(bs.resolve(p, "2026-11-02", True, second, now=NOW), ticker=p["ticker"]) for p in (MP, V)]
    s = bs.summarise(rows, "2026-11-02", True, second)
    assert s["status"] == "OK" and s["second_read_at"] == "2026-11-02T22:20:00Z" and not s["differs"]


def test_the_export_attaches_the_stops_from_the_ptj_cache(monkeypatch):
    from src.data import drive_sync, ptj
    monkeypatch.setattr(ptj, "load_ptj_cache", lambda: {
        "modified": "2026-11-02", "open_orders_pull_ran": True, "stop_flags": [],
        "second_read": bs.parse_second_read(dict(READ, pulled_at_utc=datetime.now(timezone.utc).isoformat()))})
    rows = [{"ticker": "MP", "held_sl": None}, {"ticker": "V", "held_sl": None}]
    out = drive_sync._attach_held_stops([MP, V], rows)
    assert [r["held_sl"] for r in rows] == [36.66, 391.8]
    assert out["status"] == "OK" and out["journal_date"] == "2026-11-02"


def test_the_ptj_cache_carries_the_orders_flag_from_the_journal(monkeypatch, tmp_path):
    from src.data import ptj
    monkeypatch.setattr(ptj, "PTJ_CACHE", tmp_path / "held_positions.json")
    monkeypatch.setattr(ptj, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(ptj, "_published_floor", lambda: None)
    monkeypatch.setattr(ptj, "fetch_latest_ptj", lambda: {
        "_ptj_file": "aegis_journal_2026-11-02.json", "_ptj_modified": "2026-11-02",
        "open_positions": [MP, V], "options": [],
        "broker_sync": {"open_orders_pull_ran": True},
        "review_flags": [{"ticker": "COIN", "type": "auto_included_unrecognized"},
                         {"ticker": "V", "type": "stop_partial_cover"}]})
    monkeypatch.setattr(bs, "fetch_second_read", lambda: {"ok": False, "reason": "not found"})
    held = ptj.refresh_held_positions()
    c = ptj.load_ptj_cache()
    assert [h["ticker"] for h in held] == ["MP", "V"]
    assert c["open_orders_pull_ran"] is True and c["second_read"]["reason"] == "not found"
    assert [f["type"] for f in c["stop_flags"]] == ["stop_partial_cover"]


# ---- conductor 2026-11-17: SPCX, a 68-share SHORT with a live BUY stop at 145.05, printed "NO stop order (unprotected)" ----
SHORT_ORDERS = {"result": [
    {"id": 7, "status": "HELD", "action": "BUY", "order_type": "STP", "sec_type": "STK", "symbol": "SPCX", "quantity": 68, "stop_price": 145.05, "time_in_force": "GTC"},
    {"id": 8, "status": "HELD", "action": "SELL", "order_type": "STP", "sec_type": "STK", "symbol": "RBRK", "quantity": 80, "stop_price": 99.45},
]}
SHORT_POS = {"result": [{"symbol": "SPCX", "sec_type": "STK", "quantity": -68}, {"symbol": "RBRK", "sec_type": "STK", "quantity": 80}]}
SHORT_READ = {"pulled_at_utc": "2026-11-02T22:20:00Z", "date_sgt": "2026-11-03", "open_orders": SHORT_ORDERS, "stock_positions": SHORT_POS}
SPCX = {"ticker": "SPCX", "qty": -68, "stop_live_broker": None, "stop_order": None}


def test_a_short_is_protected_by_a_buy_stop_and_a_long_by_a_sell_stop():
    s = bs.parse_second_read(SHORT_READ)["stops"]
    assert s["SPCX"]["stop"] == 145.05 and s["SPCX"]["qty"] == 68 and s["RBRK"]["stop"] == 99.45
    r = bs.resolve(SPCX, "2026-11-16", True, bs.parse_second_read(SHORT_READ), now=NOW)
    assert r["held_sl"] == 145.05 and r["held_stop_status"] == "LIVE" and r["held_stop_order"]["stop"] == 145.05
    assert "NO working stop" not in r["held_stop_check"] and "covers" not in r["held_stop_check"]          # 68 of 68: fully covered


def test_the_wrong_side_stop_does_not_protect_a_short():
    only_sell = dict(SHORT_READ, open_orders={"result": [dict(SHORT_ORDERS["result"][0], action="SELL")]})
    r = bs.resolve(SPCX, "2026-11-16", True, bs.parse_second_read(only_sell), now=NOW)
    assert r["held_sl"] is None and r["held_stop_status"] == "NO_STOP_ORDER"                  # UNPROTECTED only when there is truly no working stop on the right side
    assert bs.stops_from_orders(SHORT_ORDERS) .get("SPCX") is None                              # position unknown: the long-side default, as before


def test_the_journal_builder_writes_a_buy_stop_for_a_short_and_flags_no_stop_on_the_right_side_only():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("jb_short", pathlib.Path(__file__).resolve().parents[1] / "aegis" / "tools" / "journal_build.py")
    jb = importlib.util.module_from_spec(spec); spec.loader.exec_module(jb)
    eq = [{"ticker": "SPCX", "qty": -68.0}, {"ticker": "RBRK", "qty": 80.0}]
    flags = []
    jb._apply_live_stops(eq, SHORT_ORDERS, flags)
    assert eq[0]["stop_live_broker"] == 145.05 and eq[0]["stop_order"]["stop"] == 145.05 and eq[1]["stop_live_broker"] == 99.45
    assert not [f for f in flags if f["type"] in ("no_live_stop", "stop_partial_cover")]
    eq2, flags2 = [{"ticker": "SPCX", "qty": -68.0}], []
    jb._apply_live_stops(eq2, {"result": [dict(SHORT_ORDERS["result"][0], action="SELL")]}, flags2)       # a SELL stop is the wrong side for a short
    assert eq2[0]["stop_live_broker"] is None and any(f["type"] == "no_live_stop" for f in flags2)


def test_the_cards_headline_never_says_unprotected_while_the_runs_broker_read_shows_a_stop():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards_v3.py").read_text()
    i = src.index("a short's BUY stop is a working stop")
    assert "broker_stops.json" in src[i - 200:i + 700] and '_h.get("held_sl") is None' in src[i:i + 700]
