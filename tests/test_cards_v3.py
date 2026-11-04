"""The v3 Cards renderer (PM 2026-11-04, 'great upgrade'): a finished run dir in, one page out; every fact built from the files.
Fixture = the real 4 Nov r2 run (trimmed). The mutation tests change the facts and assert the page follows them."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "cards_v3"
TOOL = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards_v3.py"


def render(run: Path):
    out = run / "out.html"
    r = subprocess.run([sys.executable, str(TOOL), "--run-dir", str(run), "--out", str(out), "--refresh-dir", str(run / "ref")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-1500:]
    return out.read_text(encoding="utf-8")


@pytest.fixture()
def run(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(FIX, d)
    return d


def edit(run, name, fn):
    p = run / name
    o = json.loads(p.read_text())
    fn(o)
    p.write_text(json.dumps(o))


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_the_page_renders_from_the_fixture_with_every_section(run):
    h = render(run)
    for sid in ("macro", "sectors", "happened", "book", "tickers", "lists", "plan", "scorecard", "care"):
        assert f'id="{sid}"' in h, sid
    t = text(h)
    assert "Wed 4 Nov 2026" in t and "rerun r2, not live" in t              # the fixture's own date and run kind
    assert "theme baskets grade Deploy" in t                                # PM 2026-11-04: theme baskets in the sector-strength section
    assert "Equal-weight S&amp;P" in h and 'class="legend"' in h            # the line chart names each line


def test_a_direction_word_is_derived_from_the_sign_never_typed(run):
    """PM 2026-11-04 (the 3.37% above/below error): flip the sign of a level's distance and the word flips with it."""
    def flip(o):
        for k in o["key_levels"]:
            if k["what"] in ("SPY put wall", "SPY call wall", "RSP/SPY 20-day average"):
                k["distance_pct"] = -k["distance_pct"]
    base = text(render(run))
    edit(run, "aqe_crown_macro.json", flip)
    flipped = text(render(run))
    # put wall: below SPY (negative distance) vs above SPY once the sign flips; call wall the other way round
    assert re.search(r"put wall \([\d.]+% below SPY\)", base) and re.search(r"put wall \([\d.]+% above SPY\)", flipped)
    assert re.search(r"call wall \([\d.]+% above\)", base) and re.search(r"call wall \([\d.]+% below\)", flipped)
    assert re.search(r"The line is [\d.]+% above its 20-day average", base) and re.search(r"The line is [\d.]+% below its 20-day average", flipped)


def test_nothing_from_the_fixture_day_is_typed_into_the_page(run):
    def d(o):
        o["date"] = "2026-11-06"
        o["held_positions"] = [h for h in o["held_positions"] if h["ticker"] != "MP"]
        o["held_book"]["positions"] = [p for p in o["held_book"]["positions"] if p["ticker"] != "MP"]
    edit(run, "aqe_daily_export.json", d)
    def crown(o):
        dd = o["readings"]["positioning"]["option_dealers"]
        dd["regime"] = "POSITIVE"
        for k in ("SPY", "QQQ"):
            dd["detail"][k]["flip_distance_pct"] = -1.1
    edit(run, "aqe_crown_macro.json", crown)
    def valen(o):
        o["regime"] = "UPTREND"
        for t in o["trend"]:
            t["above_rising_5d"] = t["daily_buy_signal"] = True
        o["management"]["trim_trail"] = [x for x in o["management"]["trim_trail"] if x["ticker"] != "MP"]
    edit(run, "aqe_valen_dashboard.json", valen)
    edit(run, "cards_text.json", lambda o: (o.__setitem__("book", [b for b in o["book"] if b["ticker"] != "MP"]), o.__setitem__("plan", [x for x in o["plan"] if "MP" not in x])))
    edit(run, "ref/valen_dashboard.json", lambda o: o["data_freshness"].__setitem__("expected_session", "2026-11-05"))
    t = text(render(run))
    assert "Fri 6 Nov 2026" in t and "Wed 4 Nov" not in t
    assert "Trend is up." in t and "Trend is down" not in t and "Dealers damp moves." in t and "Dealers amplify" not in t
    assert "On Thursday SPY" in t                                           # the close was 5 Nov in this mutation
    assert "reclaims about 769" not in t
    assert "decide on MP" not in t and "MP: an exit case" not in t


def test_a_pending_takeover_is_flagged_and_deal_pinned_not_a_buy_card(run):
    def exp(o):
        for r in o["daily_list"]:
            r["ma_status"], r["ma_note"], r["ma_evidence"] = "NONE", None, None
            if r["ticker"] == "ROKU":
                r["ma_status"], r["ma_note"] = "PENDING_TARGET", "FOX will acquire Roku (2026-06-15)"
            if r["ticker"] == "GMAB":
                r["ma_status"] = "UNKNOWN"
        o["ma_scan"] = {"scan_status": "partial", "n_failed": 30, "n_scanned": 260, "reason": None}
    edit(run, "aqe_daily_export.json", exp)
    def cons(o):
        for c in o:
            if c["ticker"] == "ROKU":
                c.update(status="DEAL_PINNED", verdict="PASS", slate_verdict="ADVANCE", deal_pinned={"ma_note": "FOX will acquire Roku (2026-06-15)"})
    edit(run, "consensus.json", cons)
    h = render(run)
    t = text(h)
    assert "Deal-pinned, not a momentum pick" in t and "FOX will acquire Roku" in t
    assert 'class="pill ma"' in h and "M&amp;A scan partial" in t
    tcards = re.findall(r'<div class="card tcard">.*?<span class="tk">([A-Z\-]+)</span>', h, flags=re.S)
    li_thin = re.findall(r'<li><div class="row"><span class="tk">([A-Z\-]+)</span>', h)
    assert "ROKU" not in tcards and "ROKU" not in li_thin                   # no buy card for it


def test_the_extension_bracket_line_shows_on_the_ticker_card(run):
    def exp(o):
        for r in o["daily_list"]:
            if r["ticker"] == "BRK-B":
                r["extension_bracket"] = {"available": True, "passed": True, "stop": 480.0, "targets": [{"tp": "TP1", "price": 530.0, "r": 2.0}, {"tp": "TP2", "price": 560.5, "r": 3.4}]}
    edit(run, "aqe_daily_export.json", exp)
    t = text(render(run))
    assert "If it runs into open air: targets 530.00 (1.272 of its last leg) and 560.50 (1.618), stop 480.00, 3.4R to the second" in t
    assert "ignores nearby resistance" in t


def test_the_rendered_page_passes_the_plain_words_gate_with_the_new_sections(run):
    """daily-check's cards HTML gate: no raw field name in any text node, including the M&A banner, the deal-pinned section and the lists notes."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("chk_v3", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py")
    ck = importlib.util.module_from_spec(spec); spec.loader.exec_module(ck)
    def exp(o):
        for r in o["daily_list"]:
            r["ma_status"], r["ma_note"] = ("PENDING_TARGET", "FOX will acquire Roku (2026-06-15)") if r["ticker"] == "ROKU" else ("NONE", None)
        o["ma_scan"] = {"scan_status": "failed", "n_failed": 5, "n_scanned": 5, "reason": "http 500"}
    edit(run, "aqe_daily_export.json", exp)
    def cons(o):
        for c in o:
            if c["ticker"] == "ROKU":
                c.update(status="DEAL_PINNED", verdict="PASS", slate_verdict="ADVANCE", deal_pinned={"ma_note": "FOX will acquire Roku (2026-06-15)"})
    edit(run, "consensus.json", cons)
    render(run)
    fails, notes = ck.check_cards_html(str(run / "out.html"))
    assert fails == [], fails


def _churn(removed):
    return {"status": "ok", "date": "2026-11-04", "prev_date": "2026-11-03", "n_prev": 260, "n_now": 395, "n_added": 158, "n_removed": len(removed), "added": [], "removed": removed}


def test_a_committee_book_name_that_left_the_aqe_list_is_flagged_with_the_gate_that_removed_it(run):
    """Conductor/PM 2026-11-05: TMO is on the committee book (pma_levels) and fails both list gates today -> the page says so, in plain words."""
    def exp(o):
        o["list_churn"] = _churn([{"ticker": "TMO", "status": "BELOW_GATES", "was": ["on_longlist"], "reasons": ["momentum score 63.2 is under the Longlist floor of 65", "Elder impulse 7.0 is under the Elder-list floor of 8"]},
                                  {"ticker": "ZZZ", "status": "NOT_SCORED", "was": [], "reasons": ["not in today's scores"]}])    # ZZZ is not on the book: not mentioned
    edit(run, "aqe_daily_export.json", exp)
    h = render(run)
    t = text(h)
    assert "Left the AQE list today, still on your book or the committee book:" in t
    assert "TMO (momentum score 63.2 is under the Longlist floor of 65; Elder impulse 7.0 is under the Elder-list floor of 8)" in t
    assert "ZZZ" not in t
    import importlib.util
    spec = importlib.util.spec_from_file_location("chk_v3b", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py")
    ck = importlib.util.module_from_spec(spec); spec.loader.exec_module(ck)
    fails, _ = ck.check_cards_html(str(run / "out.html"))
    assert fails == [], fails


def test_no_churn_block_or_nobody_on_the_book_leaving_adds_nothing_and_a_failed_churn_says_so(run):
    base = text(render(run))
    assert "Left the AQE list today" not in base and "List changes were not worked out" not in base
    edit(run, "aqe_daily_export.json", lambda o: o.update(list_churn=_churn([{"ticker": "ZZZ", "status": "NOT_SCORED", "was": [], "reasons": ["x"]}])))
    assert "Left the AQE list today" not in text(render(run))
    edit(run, "aqe_daily_export.json", lambda o: o.update(list_churn={"status": "no_previous", "reason": "no earlier export to compare with"}))
    assert "List changes were not worked out today. no earlier export to compare with" in text(render(run))


def test_the_v2_page_has_the_same_left_the_list_banner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pc_v2", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards.py")
    pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
    D = {"list_churn": _churn([{"ticker": "TMO", "reasons": ["momentum score 63.2 is under the Longlist floor of 65"]}, {"ticker": "ZZZ", "reasons": ["x"]}])}
    h = pc._left_banner(D, {"TMO", "HELD1"})
    assert "Left the AQE list today" in h and "<b>TMO</b>" in h and "63.2" in h and "ZZZ" not in h
    assert pc._left_banner({}, {"TMO"}) == "" and pc._left_banner(D, {"OTHER"}) == ""
    assert "not worked out" in pc._left_banner({"list_churn": {"status": "no_previous", "reason": "r"}}, set())
