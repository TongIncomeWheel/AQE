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
