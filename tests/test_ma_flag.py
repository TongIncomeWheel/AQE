"""M&A flag (PM 2026-11-04): classification, loud failure, cards pill, alert label."""
import sys
from datetime import date
from pathlib import Path

import pytest

from src.data import ma_flag as M

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"))

ROKU_OWN = {"publishedDate": "2026-11-02 16:05:00", "title": "Roku Releases Third Quarter 2026 Financial Results", "url": "u1",
            "text": "On June 15, 2026, Fox Corporation (Nasdaq: FOXA, FOX) and Roku announced a definitive agreement under which FOX will acquire Roku. "
                    "In light of the pending transaction, Roku will not host an earnings call."}
NOISE = {"publishedDate": "2026-10-21", "title": "Kapitalo Investimentos Ltda Acquires 29,656 Shares of Roku, Inc.", "url": "u2",
         "text": "Kapitalo acquired a new position in shares of Roku."}


def test_the_roku_case_is_a_pending_target_with_its_sentence_and_date():
    f = M.classify("ROKU", "Roku, Inc.", [NOISE, ROKU_OWN])
    assert f["ma_status"] == "PENDING_TARGET" and "FOX will acquire Roku" in f["ma_note"] and "2026-11-02" in f["ma_note"]
    assert f["ma_evidence"]["url"] == "u1" and f["ma_evidence"]["n_deal_items"] == 1


def test_the_buyer_reads_as_acquirer_and_investor_filing_noise_is_never_a_flag():
    fox = {"publishedDate": "2026-10-16", "title": "Fox upgraded to Buy as Roku deal boosts growth", "url": "u3",
           "text": "The bank expects Fox's pending acquisition of Roku Inc to improve growth. Fox will acquire Roku in a cash and stock deal."}
    assert M.classify("FOXA", "Fox Corporation", [fox])["ma_status"] == "PENDING_ACQUIRER"
    assert M.classify("ROKU", "Roku, Inc.", [NOISE])["ma_status"] == "NONE"
    assert M.classify("AAPL", "Apple Inc.", [])["ma_status"] == "NONE"


def test_a_closed_deal_newer_than_the_pending_news_is_not_pending():
    done = {"publishedDate": "2026-11-03", "title": "Fox completes acquisition of Roku", "text": "The merger closed today.", "url": "u4"}
    assert M.classify("ROKU", "Roku, Inc.", [ROKU_OWN, done])["ma_status"] == "NONE"


def test_a_failed_scan_is_unknown_never_none_and_the_scan_says_so(tmp_path):
    class Boom:
        class config:
            api_key = "x"

        def _get_json(self, *a, **k):
            raise RuntimeError("http 500")
    art = M.refresh(["AAA", "BBB"], Boom(), today=date(2026, 11, 4), cache_path=tmp_path / "c.json")
    assert art["scan_status"] == "failed" and art["n_failed"] == 2
    assert all(v["ma_status"] == "UNKNOWN" for v in art["tickers"].values())          # never NONE


def test_the_cards_pill_the_line_and_the_banner():
    import pma_cards as PC
    row = {"ticker": "ROKU", "ma_status": "PENDING_TARGET", "ma_note": "FOX will acquire Roku. (2026-11-02)"}
    assert "M&amp;A PENDING" in PC._ma_pill(row) and "p-ma" in PC._ma_pill(row)
    assert "deal spread" in PC._ma_line(row) and PC._ma_line({"ma_status": "NONE"}) == "" and PC._ma_pill({"ma_status": "NONE"}) == ""
    assert "not checked" in PC._ma_pill({"ma_status": "UNKNOWN"})
    assert PC._ma_banner({"ma_scan": {"scan_status": "ok"}}) == ""
    assert "scan failed" in PC._ma_banner({"ma_scan": {"scan_status": "failed", "n_failed": 5, "n_scanned": 5}})
    assert "not in this export" in PC._ma_banner({})


def test_the_alert_card_carries_the_flag():
    from src.alerts import emailer as E
    card = {"headline": "ROKU $160 · BUY", "lines": ["x"], "color": "#000", "summary": None}
    out = E._with_ma_flag(dict(card), {"ma_status": "PENDING_TARGET", "ma_note": "Fox will acquire Roku"})
    assert "M&A PENDING (being acquired)" in out["headline"] and out["lines"][0].startswith("M&A PENDING:")
    clean = E._with_ma_flag(dict(card), {"ma_status": "NONE"})
    assert clean["headline"] == card["headline"]
    unk = E._with_ma_flag(dict(card), {"ma_status": "UNKNOWN"})
    assert "not checked" in unk["lines"][-1]


def test_a_pending_target_never_arms_a_buy_trigger(monkeypatch):
    """R44 (PM 2026-11-04): ma_status PENDING_TARGET -> label-only row for committee and AQE-list names alike; HELD is left alone."""
    from src.alerts import condition_defaults as D
    export = {"daily_list": [{"ticker": "ROKU", "entry": 160.0, "atr_14d": 3.0, "last_pivot_high": {"price": 158.0}, "ma_status": "PENDING_TARGET",
                              "ma_note": "Fox will acquire Roku (2026-06-15)"},
                             {"ticker": "OK", "entry": 50.0, "ma_status": "NONE"}]}
    buy = {"shared": {"buy": [{"w": "h1_close_above", "level": 161.0}], "confirm": []}, "exits": [], "analysts": []}
    rows = [{"ticker": "ROKU", "class": "ADVANCE", "conditions": buy}, {"ticker": "OK", "class": "ADVANCE", "conditions": buy},
            {"ticker": "ROKU", "class": "HELD", "conditions": buy}]
    out = D.apply_deal_pinned(rows, export)
    assert out[0]["deal_pinned"] is True and out[0]["conditions"]["shared"]["buy"] == [] and out[0]["conditions"]["shared"]["no_shared_buy"] is True
    assert out[1] is rows[1]                                   # a clean name is untouched
    assert out[2] is rows[2]                                   # a held position keeps its own cards
    assert D.apply_deal_pinned(rows, {"daily_list": [{"ticker": "ROKU", "entry": 160.0}]})[0] is rows[0]   # no ma_status in the export: no claim


def test_the_export_stamp_flags_roku_and_keeps_a_failed_scan_loud(tmp_path, monkeypatch):
    """The success path of drive_sync._attach_ma_flags with a fake FMP client (news for ROKU says pending), and the failure path."""
    from src.data import drive_sync as DS, ma_flag as M2
    monkeypatch.setattr(M2, "CACHE_PATH", tmp_path / "ma.json")
    news = {"ROKU": [ROKU_OWN, NOISE], "AAPL": []}

    class Fake:
        class config:
            api_key = "k"

        def _get_json(self, url, params):
            if url.endswith("/profile"):
                return [{"companyName": "Roku, Inc."}]
            return news[params["symbols"]]
    exp = {"date": "2026-11-04", "daily_list": [{"ticker": "ROKU"}, {"ticker": "AAPL"}], "held_positions": []}
    DS._attach_ma_flags(exp, client=Fake())
    by = {r["ticker"]: r for r in exp["daily_list"]}
    assert by["ROKU"]["ma_status"] == "PENDING_TARGET" and "FOX will acquire Roku" in by["ROKU"]["ma_note"] and by["AAPL"]["ma_status"] == "NONE"
    assert exp["ma_pending"] == ["ROKU"] and exp["ma_scan"]["scan_status"] == "ok" and exp["ma_scan"]["n_flagged"] == 1

    class Down:
        class config:
            api_key = "k"

        def _get_json(self, url, params):
            raise RuntimeError("http 500")
    monkeypatch.setattr(M2, "CACHE_PATH", tmp_path / "ma2.json")
    exp2 = {"date": "2026-11-04", "daily_list": [{"ticker": "ROKU"}, {"ticker": "AAPL"}], "held_positions": []}
    DS._attach_ma_flags(exp2, client=Down())
    assert all(r["ma_status"] == "UNKNOWN" for r in exp2["daily_list"]) and exp2["ma_scan"]["scan_status"] == "failed" and exp2["ma_pending"] == []
    exp3 = {"date": "2026-11-04", "daily_list": [{"ticker": "ROKU"}], "held_positions": []}
    DS._attach_ma_flags(exp3, client=object())            # a client that cannot scan at all: still UNKNOWN, never NONE
    assert exp3["daily_list"][0]["ma_status"] == "UNKNOWN" and exp3["ma_scan"]["scan_status"] == "failed"
