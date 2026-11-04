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


def test_a_real_cash_offer_and_stock_merger_on_lci_reads_as_a_target():
    """Real FMP news (4 Nov): LCI Industries agreed an all-stock merger with Patrick and received a cash proposal from Monomoy; the release calls
    the company 'LCI', not 'LCI Industries' - the role is read around the short alias too."""
    items = [{"publishedDate": "2026-10-30 07:30:00", "url": "u1",
              "title": "LCI Board Determines That the Unsolicited, Non-Binding Proposal From Monomoy Capital Partners Does Not Constitute a Superior Proposal",
              "text": "LCI Industries (NYSE: LCII) (“LCI”), today announced that its Board of Directors has unanimously determined that the unsolicited, non-binding proposal "
                      "received from Monomoy Capital Partners to acquire LCI for $101 per share in cash does not constitute a superior proposal"},
             {"publishedDate": "2026-10-28 06:03:00", "url": "u2", "title": "Patrick Industries, Inc. Reaffirms Merger Agreement with LCI Industries",
              "text": "Patrick reaffirmed its agreement to combine with LCI Industries (NYSE: LCII) in an all-stock merger"}]
    # After the 4 Nov precision fix: a non-binding proposal and "X's merger agreement with Y" do not say who buys whom, so LCI is flagged (the pill and
    # the sentence show) but as PENDING_UNCLEAR, which excludes nothing. R44 deal-pins only a clearly-read target.
    assert M.classify("LCII", "LCI Industries, Inc.", items)["ma_status"] == "PENDING_UNCLEAR"
    assert M.classify("PATK", "Patrick Industries, Inc.", items[1:])["ma_status"].startswith("PENDING")       # flagged; role unclear is fine (flag-only)


def test_dry_run_noise_of_4_nov_never_flags_and_loose_language_never_deal_pins():
    """The 4 Nov dry-run flagged 202 of 261 names (62 PENDING_TARGET): fund-holding filings and 'stocks to buy' advice. None of these is a deal."""
    from datetime import date
    noise = [("WM", "Waste Management", "Is It Too Late to Buy Waste Management Inc (WM) After 4.2% Rally?"),
             ("SF", "Stifel Financial", "199,915 Shares in Stifel Financial Corporation $SF Acquired by Argent Capital Management LLC."),
             ("TFC", "Truist Financial", "13,413 Shares in Truist Financial Corporation $TFC Acquired by Archer Investment Corp."),
             ("WEC", "WEC Energy", "$WEC Shares Acquired by International Assets Investment Management LLC."),
             ("TMO", "Thermo Fisher", "All You Need to Know About Thermo Fisher (TMO) Rating Upgrade to Buy."),
             ("TEL", "TE Connectivity", "3 Electronics Components Stocks to Buy as Industry Prospects Brighten."),
             ("VRT", "Vertiv", "Is It Time to Buy the Dip?")]
    for tk, nm, title in noise:
        r = M.classify(tk, nm, [{"publishedDate": "2026-10-20", "title": title, "text": "", "url": "u"}], today=date(2026, 11, 4))
        assert r["ma_status"] == "NONE", (tk, r["ma_status"])
    # loose language alone ("Merger with" in a results headline of a third party) is at most UNCLEAR, never a target
    loose = {"publishedDate": "2026-10-20", "title": "Wendy's Surges 14% on Trian-Led $1.4B Take-Private Offer; McDonald's Edges Higher, Yum Brands Stays Put.", "text": "", "url": "u"}
    assert M.classify("YUM", "Yum Brands", [loose], today=date(2026, 11, 4))["ma_status"] != "PENDING_TARGET"
    # "X's merger with Y" says X is a party, not which side: it is not a role on its own
    only = {"publishedDate": "2026-11-02", "title": "As Roku's Merger With Fox Clears More Hurdles, Streaming Provider Delivers Strong Q3 Results.", "text": "", "url": "u"}
    assert M.classify("ROKU", "Roku, Inc.", [only], today=date(2026, 11, 4))["ma_status"] == "PENDING_UNCLEAR"
    deal = {"publishedDate": "2026-10-16", "title": "Fox to buy Roku", "text": "Fox will acquire Roku in a cash and stock deal under a definitive merger agreement.", "url": "u"}
    assert M.classify("ROKU", "Roku, Inc.", [only, deal], today=date(2026, 11, 4))["ma_status"] == "PENDING_TARGET"
    cases = [("AWK", "American Water Works", "American Water announced Brad Nielsen will become President upon the closing of American Water's proposed merger with Essential Utilities."),
             ("FITB", "Fifth Third Bancorp", "Fifth Third Bancorp is seeing early results of its merger with Comerica and is making progress on the integration."),
             ("CZR", "Caesars Entertainment", "Caesars received a non-binding proposal from the Icahn Group to acquire Caesars for $34.00 per share in cash.")]
    for tk, nm, txt in cases:   # the three wrong PENDING_TARGET reads of the first corrected dry-run
        r = M.classify(tk, nm, [{"publishedDate": "2026-10-20", "title": txt, "text": "", "url": "u"}], today=date(2026, 11, 4))
        assert r["ma_status"] != "PENDING_TARGET", (tk, r["ma_status"])
    for tk, nm, txt in [("BRZE", "Braze", "Braze entered into a definitive agreement to be acquired by Salesforce."),
                        ("PAYO", "Payoneer", "Payoneer announced an agreement to be acquired by Nuvei on June 15, 2026.")]:
        assert M.classify(tk, nm, [{"publishedDate": "2026-10-20", "title": txt, "text": "", "url": "u"}], today=date(2026, 11, 4))["ma_status"] == "PENDING_TARGET"


def test_the_circuit_breaker_fails_the_scan_instead_of_mass_deal_pinning(tmp_path):
    from datetime import date
    class Many:
        """Every ticker's news reads as a pending takeover of that ticker: a broken classifier."""
    def fake_fetch(client, tk, today):
        return [{"publishedDate": "2026-11-01", "title": f"Fox will acquire {tk}", "text": f"Definitive agreement under which Fox will acquire {tk}. In light of the pending transaction, {tk} will not host a call.", "url": "u"}]
    orig = M.fetch_items
    M.fetch_items = fake_fetch
    try:
        tks = [f"T{i}" for i in range(20)]
        names = {t: f"T{i} Corp" for i, t in enumerate(tks)}
        art = M.refresh(tks, Many(), today=date(2026, 11, 4), cache_path=tmp_path / "c.json", names=names)
        assert art["scan_status"] == "failed" and "circuit breaker" in art["reason"] and art["n_flagged"] == 0
        assert all(v["ma_status"] == "UNKNOWN" for v in art["tickers"].values())
        raw = M.refresh(tks, Many(), today=date(2026, 11, 5), cache_path=tmp_path / "d.json", names=names, breaker=False)
        assert sum(v["ma_status"] == "PENDING_TARGET" for v in raw["tickers"].values()) == 20
        few = M.refresh(tks[:3], Many(), today=date(2026, 11, 6), cache_path=tmp_path / "e.json", names=names)
        assert few["scan_status"] == "ok" and few["n_flagged"] == 3          # a handful of real targets is within the limit
    finally:
        M.fetch_items = orig


def test_the_5_nov_misreads_are_not_targets_and_real_ones_still_are():
    """5 Nov export (395 names): APO, RY, F, COMP were read as pending takeover targets and were not. The target verb must sit next to the company's name,
    and a rumour, a discussion or a class-action notice is not an agreed deal."""
    from datetime import date
    wrong = [("APO", "Apollo Global Management", "Universal Music Group discussed going private with buyout firms including Apollo, Bloomberg News reports."),
             ("RY", "Royal Bank of Canada", "Francisco Partners Agrees to Buy Moneris From BMO and Royal Bank of Canada for $1.4 Billion."),
             ("F", "Ford Motor Company", "Crescent Energy to Acquire Eagle Ford Assets from Devon Energy under a definitive agreement."),
             ("COMP", "Compass, Inc.", "Compass allegedly misled investors in connection with its merger with Anywhere Real Estate Inc. Robbins reminds investors of the class action.")]
    for tk, nm, txt in wrong:
        r = M.classify(tk, nm, [{"publishedDate": "2026-10-20", "title": txt, "text": "", "url": "u"}], today=date(2026, 11, 5))
        assert r["ma_status"] != "PENDING_TARGET", (tk, r["ma_status"], r["ma_note"])
    right = [("ROKU", "Roku, Inc.", "Fox will acquire Roku under a definitive merger agreement."),
             ("CART", "Maplebear", "DoorDash agreed to acquire Maplebear Inc. for $17 billion under a definitive agreement."),
             ("D", "Dominion Energy", "NextEra Energy announced the proposed acquisition of Dominion Energy in an all-stock deal under a merger agreement."),
             ("CZR", "Caesars Entertainment", "Caesars Entertainment agreed to be acquired in a definitive agreement; Robbins LLP is investigating the proposed acquisition of Caesars.")]
    for tk, nm, txt in right:
        r = M.classify(tk, nm, [{"publishedDate": "2026-10-20", "title": txt, "text": "", "url": "u"}], today=date(2026, 11, 5))
        assert r["ma_status"] == "PENDING_TARGET", (tk, r["ma_status"], r["ma_note"])
