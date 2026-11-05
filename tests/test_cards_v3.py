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


def test_a_market_kill_line_with_a_gate_note_in_brackets_passes_the_plain_words_gate(run):
    """5 Nov: '(C2, gate DELEGATED)' on the market-kill line failed the plain-words gate and the page fell back to v2."""
    def dec(o):
        o["market_kill"]["plain"] = "Void every new trigger if SPY closes under 500 (C2, gate DELEGATED)."
    edit(run, "decision.json", dec)
    h = render(run)
    assert "gate DELEGATED" not in h and "(C2" not in h
    import importlib.util
    spec = importlib.util.spec_from_file_location("chk_mk", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py")
    ck = importlib.util.module_from_spec(spec); spec.loader.exec_module(ck)
    fails, _ = ck.check_cards_html(str(run / "out.html"))
    assert fails == [], fails


def _frame(cls, d_pct=None, order="9>21", close=None, sh=None):
    f = {"served": True, "swing_class": cls, "ema_order": order, "swing": {"close_vs_swing_high_pct": d_pct}}
    if close is not None:
        f["close"] = close
        f["swing"]["last_swing_high"] = {"price": sh, "date": "2026-10-20"}
    return f


def _mtf_doc(flag_names):
    names = {}
    for t in ("ROKU", "SN", "V", "BRK-B", "DIS", "TMO", "EW", "HNGE", "AJG", "GEN", "SWK", "FA"):
        hit = t in flag_names
        names[t] = {"served": True, "W": _frame("HH/HL", 1.0), "D": (_frame("HH/HL", 3.9, "9>21", close=557.07, sh=535.93) if hit else _frame("LH but HL", -6.2, "9<21")),   # BRK-B: atr_14d 7.29 -> 2.9 daily ranges above
                    "H1": _frame("LH/LL", -1.1, "9<21"), "momentum": {"flag": hit, "reasons": ["ok" if hit else "daily swing is LH but HL, not HH/HL"]}}
    names["DIS"] = {"served": False, "reason": "only 14 hr bars; EMA21 needs 21"}
    return {"schema": "mtf.v1", "date": "2026-11-04", "names": names}


def test_every_card_shows_the_weekly_daily_hourly_strip_the_momentum_flag_and_a_one_line_unr_tag(run):
    (run / "mtf.json").write_text(json.dumps(_mtf_doc({"BRK-B"})))
    def exp(o):
        for r in o["daily_list"]:
            if r["ticker"] == "BRK-B":
                r.update(unr_status="MET", unr_level=round(r["entry"] / 1.08, 2))     # 8% under the last close: no useful reference
            if r["ticker"] == "TMO":
                r.update(unr_status="MET", unr_level=round(r["entry"] / 1.02, 2))     # 2% under: a usable reference
            if r["ticker"] == "EW":
                r.update(unr_status="NO", unr_level=None)
    edit(run, "aqe_daily_export.json", exp)
    h = render(run)
    t = text(h)
    assert "Weekly: higher highs and higher lows; fast average above slow; 1.0% above the last swing high." in t
    assert "Daily: lower highs but higher lows; fast average below slow; 6.2% under the last swing high." in t
    assert "Hourly: lower highs and lower lows" in t
    assert "Trend frames: not served (only 14 hr bars; EMA21 needs 21)" in t                      # DIS: declared, not neutral
    assert 'class="unr"' in h
    assert t.count("Uptrend") >= 2                                                     # the banner title and BRK-B's pill
    assert "Uptrend, extended (+2.9 ATR)" in t and "2.9 daily ranges (ATR) above the last swing high (+3.9%), extended" in h
    assert "1 of 11 slate names have weekly and daily higher highs and higher lows" in t        # DIS has no readable flag (not served), so it is not counted either way
    assert "extended: BRK-B +2.9" in t and "Information only: not a gate, not a vote." in t
    assert "Momentum setup" not in t and "within 2%" not in t
    assert re.search(r"Risk \d+\.\d\d \(\d+\.\d%, \d+\.\d ATR\)", t) or re.search(r"Risk \d+\.\d\d/share \(\d+\.\d%, \d+\.\d ATR\)", t), "the stop's risk is also shown in ATR"
    assert "no useful U&amp;R reference" in t and "U&amp;R: reclaim day. Support line" in t and "U&amp;R: none." in t
    import importlib.util
    spec = importlib.util.spec_from_file_location("chk_x", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py")
    ck = importlib.util.module_from_spec(spec); spec.loader.exec_module(ck)
    fails, _ = ck.check_cards_html(str(run / "out.html"))
    assert fails == [], fails


def test_no_mtf_file_means_no_strip_claim_and_no_momentum_line(run):
    t = text(render(run))
    assert "Trend frames" not in t.replace("Trend frames and U&R", "") and "have weekly and daily higher highs" not in t


def test_the_same_percent_distance_lands_in_different_atr_bands_and_the_edges_live_in_one_place():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cx2", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "card_extras.py")
    cx = importlib.util.module_from_spec(spec); spec.loader.exec_module(cx)
    mt = {"D": {"close": 104.0, "swing": {"last_swing_high": {"price": 100.0}}}}                 # +4.0% above the swing high in all three
    calm, normal, wild = ({"atr_14d": a} for a in (5.0, 1.5, 0.9))
    assert cx.atr_distance(mt, calm)["band"] == "at the pivot" and cx.atr_distance(mt, calm)["atr_dist"] == 0.8
    assert cx.atr_distance(mt, normal)["band"] == "extended" and cx.atr_distance(mt, normal)["atr_dist"] == 2.67
    assert cx.atr_distance(mt, wild)["band"] == "far extended" and cx.atr_distance(mt, wild)["atr_dist"] == 4.44
    assert {cx.atr_distance(mt, r)["pct"] for r in (calm, normal, wild)} == {4.0}
    below = {"D": {"close": 90.0, "swing": {"last_swing_high": {"price": 100.0}}}}
    assert cx.atr_distance(below, normal)["band"] == "below the pivot" and cx.atr_distance(below, {"atr_14d": 20.0})["band"] == "at the pivot"
    assert cx.atr_distance(mt, {"ticker": "X"}) is None and cx.atr_distance(mt, {"atr_14d": 0}) is None      # missing/zero ATR: no claim
    # the edges are the module constants: change them and the bands move, nothing else is hard-wired
    cx.ATR_NEAR, cx.ATR_FAR = 0.5, 1.0
    assert cx.atr_distance(mt, calm)["band"] == "extended" and cx.atr_distance(mt, normal)["band"] == "far extended"


def test_card_extras_unr_rules_and_brief_table():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cx", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "card_extras.py")
    cx = importlib.util.module_from_spec(spec); spec.loader.exec_module(cx)
    row = lambda st, lvl, close: {"unr_status": st, "unr_level": lvl, "entry": close}
    assert "no useful U&R reference" in cx.unr_tag(row("MET", 41.77, 44.93))                    # GLBE +7.6%
    assert "no useful U&R reference" in cx.unr_tag(row("MET", 131.24, 141.64))                  # DG +7.9%
    assert "+2.5% from it" in cx.unr_tag(row("MET", 287.53, 294.83)) and "no useful" not in cx.unr_tag(row("MET", 287.53, 294.83))  # ABBV
    assert cx.unr_tag(row("NO", None, 95.8)).startswith("U&R: none.") and cx.unr_tag(row("NA", None, 1)).startswith("U&R: not checked")
    assert cx.unr_tag({"ticker": "X"}) == "U&R: not in this export." and cx.unr_tag(row("SETUP", 10, 9.5)).startswith("U&R: setup forming")
    md = cx.unr_table_md({"KO": row("NO", None, 95.8), "GLBE": row("MET", 41.77, 44.93), "ABBV": row("MET", 287.53, 294.83)},
                         [("KO", "ADVANCE (AGREED)"), ("GLBE", "ADVANCE (CONTESTED)"), ("ABBV", "ADVANCE (CONTESTED)"), ("ZZ", "HELD")], "4 Nov")
    assert "| GLBE | ADVANCE (CONTESTED) | MET | 41.77 | 44.93 | +7.6% | no useful U&R reference |" in md
    assert "| ABBV | ADVANCE (CONTESTED) | MET | 287.53 | 294.83 | +2.5% | line is near enough to use |" in md
    assert "| ZZ | HELD | not in export |" in md and "No useful U&R reference (close more than 5% above the line): GLBE." in md
    assert "Read: 2 of 4 names are on a U&R reclaim day." in md


def test_the_v2_fallback_page_has_the_same_strip_flag_and_unr_line():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pc_v2b", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards.py")
    pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
    pc._MTF = _mtf_doc({"BRK-B"})["names"]
    h = pc._extras("BRK-B", {"unr_status": "NO", "unr_level": None, "entry": 100.0})
    assert "Weekly: higher highs and higher lows; fast average above slow; 1.0% above the last swing high." in h and 'class="unr"' in h and "U&amp;R: none." in h
    brk = {"ticker": "BRK-B", "atr_14d": 7.29}
    assert "Uptrend, extended (+2.9 ATR)" in pc._mom_pill("BRK-B", brk) and pc._mom_pill("TMO", {"ticker": "TMO", "atr_14d": 5.0}) == ""
    assert "1 of 11 slate names have weekly and daily higher highs and higher lows" in pc._mom_banner([{"ticker": t, "status": "CONTESTED"} for t in pc._MTF] + [{"ticker": "PASSY", "status": "NOT_SLATED"}], {"BRK-B": brk})
    pc._MTF = {}
    assert pc._extras("KO", {"ticker": "KO"}).startswith('<p class="unr">U&amp;R: not in this export.') and pc._mom_banner([{"ticker": "KO"}]) == ""


def test_the_unr_table_command_builds_the_brief_table_from_the_export_and_is_wired_into_the_run_map(run):
    tool = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "card_extras.py"
    def exp(o):
        for r in o["daily_list"]:
            if r["ticker"] == "TMO":
                r.update(unr_status="MET", unr_level=round(r["entry"] / 1.02, 2))
            if r["ticker"] == "BRK-B":
                r.update(unr_status="MET", unr_level=round(r["entry"] / 1.08, 2))
    edit(run, "aqe_daily_export.json", exp)
    out = run / "unr_table.md"
    r = subprocess.run([sys.executable, str(tool), "unr-table", "--export", str(run / "aqe_daily_export.json"), "--consensus", str(run / "consensus.json"),
                        "--date", "4 Nov", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    md = out.read_text()
    assert md.startswith("U&R = a daily support level") and "| TMO | ADVANCE (CONTESTED) | MET |" in md and "no useful U&R reference" in md
    assert "| ROKU | ADVANCE (AGREED) |" in md
    runmap = (ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "RUN.yaml").read_text()
    assert "card_extras.py unr-table" in runmap and "produces: [brackets.json, repeat_marks.json, unr_table.md]" in runmap
    assert "unr_table.md" in (ROOT / "aegis" / "plugin" / "aegis-core" / "agents" / "brief-writer.md").read_text()


def test_an_older_mtf_grid_without_swing_fields_says_so_instead_of_claiming_no_structure(run):
    old = _mtf_doc(set())
    for r in old["names"].values():
        for tf in ("W", "D", "H1"):
            if r.get("served") and isinstance(r.get(tf), dict):
                r[tf].pop("swing_class", None); r[tf].pop("swing", None)
        r.pop("momentum", None)
    (run / "mtf.json").write_text(json.dumps(old))
    t = text(render(run))
    assert "swing structure not computed in this grid (older mtf.json)" in t
    assert "have weekly and daily higher highs" not in t            # no flag in an older grid = no count
    assert "no clear swing structure" not in t


def test_the_unr_table_covers_the_slate_and_the_book_not_every_name_the_room_looked_at(run):
    tool = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "card_extras.py"
    out = run / "unr2.md"
    r = subprocess.run([sys.executable, str(tool), "unr-table", "--export", str(run / "aqe_daily_export.json"), "--consensus", str(run / "consensus.json"), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    md = out.read_text()
    assert "| ROKU |" in md and "| OHI |" not in md and "NOT_SLATED" not in md
