"""R40 market_kill: loader tolerance, evaluation, sticky break, suppression, header."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.alerts import config as C
from src.alerts import emailer as EM
from src.alerts import engine as E
from src.alerts import pma_levels as P

ET = ZoneInfo("America/New_York")
MK = {"symbol": "SPY", "word": "close_below", "level": 750, "plain": "void if SPY closes under the 750 put wall",
      "seats": ["a", "b"], "origin_run": "2026-11-02"}


def doc(**kw):
    d = {"run_date": "2026-11-02", "session": "2026-11-02", "rows": []}
    d.update(kw)
    return d


# ---------------------------------------------------------------- loader tolerance
def test_absent_key_is_declared_not_silent():
    r = P.read_market_kill(doc())
    assert r["status"] == "ABSENT" and "pre-R40" in r["note"] and r["kill"] is None


def test_null_carries_the_files_own_reason():
    r = P.read_market_kill(doc(market_kill=None, market_kill_note="no seat named a market condition"))
    assert r["status"] == "NULL" and r["note"] == "no seat named a market condition"


def test_populated_is_active_and_normalised():
    r = P.read_market_kill(doc(market_kill=dict(MK, symbol="spy")))
    assert r["status"] == "ACTIVE" and r["kill"]["symbol"] == "SPY" and r["kill"]["level"] == 750.0


@pytest.mark.parametrize("bad", ["a string", 7, ["x"], {"_bad": "oops"}, dict(MK, plain=""), dict(MK, plain=None),
                                 dict(MK, level="750"), dict(MK, level=True), dict(MK, level=float("nan"))])
def test_malformed_is_flagged_never_raises(bad):
    assert P.read_market_kill(doc(market_kill=bad))["status"] == "MALFORMED"


def test_stale_origin_run_is_not_trusted():
    assert P.read_market_kill(doc(market_kill=dict(MK, origin_run="2026-10-29")))["status"] == "STALE"


@pytest.mark.parametrize("patch", [{"word": "h1_close_below"}, {"word": None}, {"symbol": None}, {"level": None}])
def test_unwatchable_says_so_and_keeps_the_committees_words(patch):
    r = P.read_market_kill(doc(market_kill=dict(MK, **patch)))
    assert r["status"] == "UNWATCHABLE" and MK["plain"] in r["note"]


def test_no_file_is_absent():
    assert P.read_market_kill(None)["status"] == "ABSENT"


def test_other_helpers_unchanged_by_the_new_key():
    for mk in (None, MK):
        d = doc(market_kill=mk, rows=[{"ticker": "A", "class": "ADVANCE", "triggers": [
            {"id": "A-1", "kind": "close_above", "level": 10, "priority": "ACTION"}]}])
        assert len(P.alertable_rows(d)) == 1 and P.pma_tickers(d) == {"A"} and P.is_fresh(d, datetime(2026, 11, 2, 10, tzinfo=ET))


# ---------------------------------------------------------------- evaluation
K = P.read_market_kill(doc(market_kill=MK))["kill"]


def test_close_below_warns_intraday_breaks_on_final():
    q = {"price": 749.0}
    assert P.evaluate_market_kill(K, q, False)["state"] == "WARN"
    assert P.evaluate_market_kill(K, q, True)["state"] == "BROKEN"
    assert P.evaluate_market_kill(K, {"price": 751.0}, True)["state"] == "INTACT"


def test_trade_below_breaks_on_the_touch():
    k = dict(K, word="trade_below")
    assert P.evaluate_market_kill(k, {"price": 760, "day_low": 749.5}, False)["state"] == "BROKEN"
    assert P.evaluate_market_kill(k, {"price": 760, "day_low": 755}, False)["state"] == "INTACT"


def test_missing_quote_is_loud_not_a_pass():
    assert P.evaluate_market_kill(K, None, True)["state"] == "NO_QUOTE"
    assert P.evaluate_market_kill(K, {"price": None}, True)["state"] == "NO_QUOTE"


# ---------------------------------------------------------------- header
def _hdr(mk, **meta):
    return EM._market_line({"market_kill": mk, **meta})


def test_header_lines():
    base = {"status": "ACTIVE", "plain": MK["plain"], "kill": K}
    assert _hdr(dict(base, broken=True, detail="SPY at 749, under the 750 line at the close")).startswith("⛔ MARKET CONDITION BROKEN — take no new triggers")
    assert "confirms only on the close" in _hdr(dict(base, state="WARN", detail="x"))
    assert "NOT checked" in _hdr(dict(base, state="NO_QUOTE", detail="no SPY quote"))
    assert _hdr(dict(base, state="INTACT")).startswith("Market condition (holding)")
    assert "No market condition is being watched: pre-R40" in _hdr({"status": "ABSENT", "note": "pre-R40"})
    assert _hdr({"status": "ABSENT", "note": "x"}, pma_missing="2026-10-29") is None


def test_broken_digest_subject_and_body_even_with_no_cards():
    meta = {"pma_run": "2026-11-02", "pma_session": "2026-11-02", "aqe_date": "2026-10-30",
            "market_kill": {"status": "ACTIVE", "plain": MK["plain"], "kill": K, "broken": True,
                            "just_broke": True, "detail": "SPY at 749"}}
    now = datetime(2026, 11, 2, 16, 20, tzinfo=ET)
    subject, plain, html = EM.build_condition_digest([], now, [], meta)
    assert "MARKET BROKEN" in subject and "take no new triggers" in plain and "take no new triggers" in html


# ---------------------------------------------------------------- engine: sticky + suppression
def _wire(monkeypatch, pma, quotes, captured):
    export = {"date": "2026-11-02", "held_positions": [],
              "daily_list": [{"ticker": "T", "on_longlist": True, "on_elder": True,
                              "entry": 100.0, "atr_14d": 3.0,
                              "bracket": {"valid": True, "stop": 92.0, "risk": 8.0,
                                          "targets": [{"tp": "TP1", "price": 112.0}]}}]}
    monkeypatch.setattr(C, "LEGACY_DIGEST_EMAIL", False)
    monkeypatch.setattr(E, "load_export", lambda: export)
    monkeypatch.setattr(E, "in_market_window", lambda: True)
    monkeypatch.setattr(E, "_export_age_days", lambda _e: 0)
    st = {"date": "x", "fired": []}
    monkeypatch.setattr(E.S, "load_alert_state", lambda: st)
    monkeypatch.setattr(E.S, "save_alert_state", lambda _s: None)
    monkeypatch.setattr(E.S, "append_history", lambda _f: None)
    pf = {"fired": []}
    monkeypatch.setattr(E.S, "load_pma_fired_state", lambda: pf)
    monkeypatch.setattr(E.S, "save_pma_fired_state", lambda _s: None)
    monkeypatch.setattr(P, "load_pma_levels", lambda path=None: (pma, None))
    monkeypatch.setattr(P, "is_fresh", lambda d, n: True)
    import src.alerts.condition_cycle as CC
    monkeypatch.setattr(CC, "run_condition_cycle", lambda *a, **k: captured.append(k["meta"]) or {"enabled": False})
    import src.alerts.ledger as L
    ledgered = []
    monkeypatch.setattr(L, "append", lambda rows: ledgered.extend(rows) or {"appended": len(rows)})
    import src.data.fmp_client as FC
    monkeypatch.setattr(FC.FMPClient, "__init__", lambda self: None)
    monkeypatch.setattr(FC.FMPClient, "get_quotes", lambda self, tks: {t: quotes[t] for t in tks if t in quotes})
    import src.alerts.heartbeat as H
    monkeypatch.setattr(H, "beat", lambda *a, **k: {})
    return st, ledgered


ROWS = [
    {"ticker": "BUY", "class": "ADVANCE", "triggers": [
        {"id": "BUY-1", "kind": "trade_above", "level": 100, "priority": "ACTION", "action": "buy line"}]},
    {"ticker": "OWN", "class": "HELD", "broker_stop": {"stop": 90}, "triggers": [
        {"id": "OWN-1", "kind": "trade_below", "level": 95, "priority": "ACTION", "action": "stop line"}]},
]
QUOTES = {"T": {"price": 100.0, "prev_close": 100.0}, "BUY": {"price": 101, "day_high": 101, "day_low": 99, "prev_close": 99},
          "OWN": {"price": 94, "day_high": 96, "day_low": 94, "prev_close": 96},
          "SPY": {"price": 749, "day_high": 760, "day_low": 748, "prev_close": 760}}


def test_broken_market_suppresses_entries_keeps_held_stops_and_is_sticky(monkeypatch):
    mk = dict(MK, word="trade_below")
    pma = doc(rows=ROWS, market_kill=mk)
    meta = []
    st, ledgered = _wire(monkeypatch, pma, QUOTES, meta)
    s1 = E.run_alert_cycle(send_email=False)
    kinds = {(t["ticker"], t["kind"]) for t in s1["triggers"]}
    assert ("OWN", "trade_below") in kinds and ("BUY", "trade_above") not in kinds
    assert any(r.get("suppressed_by") == "market_kill" for r in ledgered)
    assert s1["market_kill"]["broken"] and s1["market_kill"]["just_broke"] and s1["market_kill"]["suppressed"] == 1
    assert meta[0]["market_kill"]["just_broke"] is True
    # next cycle: SPY recovered -- still broken for the session, announced only once
    recovered = dict(QUOTES, SPY={"price": 780, "day_high": 780, "day_low": 748, "prev_close": 760})
    monkeypatch.setattr(__import__("src.data.fmp_client", fromlist=["x"]).FMPClient, "get_quotes",
                        lambda self, tks: {t: recovered[t] for t in tks if t in recovered})
    s2 = E.run_alert_cycle(send_email=False)
    assert s2["market_kill"]["broken"] and not s2["market_kill"]["just_broke"]
    assert meta[1]["market_kill"]["broken"] is True


def test_intact_market_lets_entries_through(monkeypatch):
    pma = doc(rows=ROWS, market_kill=dict(MK, word="trade_below"))
    q = dict(QUOTES, SPY={"price": 770, "day_high": 771, "day_low": 765, "prev_close": 760})
    meta = []
    _wire(monkeypatch, pma, q, meta)
    s = E.run_alert_cycle(send_email=False)
    assert ("BUY", "trade_above") in {(t["ticker"], t["kind"]) for t in s["triggers"]}
    assert not s["market_kill"]["broken"]


@pytest.mark.parametrize("pmakw", [{}, {"market_kill": None}, {"market_kill": "junk"}, {"market_kill": dict(MK, level="x")}])
def test_engine_runs_normally_on_absent_null_or_malformed(monkeypatch, pmakw):
    meta = []
    _wire(monkeypatch, doc(rows=ROWS, **pmakw), QUOTES, meta)
    s = E.run_alert_cycle(send_email=False)
    assert s["ok"] and ("BUY", "trade_above") in {(t["ticker"], t["kind"]) for t in s["triggers"]}
    assert meta[0]["market_kill"]["status"] in ("ABSENT", "NULL", "MALFORMED") and not meta[0]["market_kill"]["broken"]


def test_missing_symbol_quote_is_no_quote_not_intact(monkeypatch):
    meta = []
    q = {k: v for k, v in QUOTES.items() if k != "SPY"}
    _wire(monkeypatch, doc(rows=ROWS, market_kill=MK), q, meta)
    E.run_alert_cycle(send_email=False)
    assert meta[0]["market_kill"]["state"] == "NO_QUOTE" and not meta[0]["market_kill"]["broken"]


def test_empty_export_still_watches_committee_and_held_rows(monkeypatch):
    """PM/conductor 2026-11-02 (7): an export with no Longlist/Elder/held names
    used to end the cycle at 'no monitored tickers' BEFORE the levels file was
    loaded, so held-name stops went unwatched."""
    meta = []
    st, ledgered = _wire(monkeypatch, doc(rows=ROWS), QUOTES, meta)
    monkeypatch.setattr(E, "load_export", lambda: {"date": "2026-11-02", "held_positions": [], "daily_list": []})
    s = E.run_alert_cycle(send_email=False)
    kinds = {(t["ticker"], t["kind"]) for t in s["triggers"]}
    assert s["ok"] and ("OWN", "trade_below") in kinds and ("BUY", "trade_above") in kinds
    assert "no AQE-monitored names" in s["note"] and meta  # condition cycle still ran
