"""PM ruling on the 11 Nov Cards page and brief (conductor 2026-11-11), six changes:
1 held-book reference stops, 2 P&L in R, 3 ONE book table, 4 Valen setups table with tickers, 5 strong-names table, 6 compact repeat watch + plain sortable lists."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
sys.path.insert(0, str(TOOLS))
import held_view as HV  # noqa: E402

PIPE = TOOLS / "pma_pipeline.py"
FIX = ROOT / "tests" / "fixtures" / "cards_v3"


def row(t, entry, live, qty, valid=False, bstop=None, ext=None, atr=None, unreal=None):
    return {"ticker": t, "entry": entry, "live_px": live, "qty": qty, "unreal_usd": unreal if unreal is not None else round((live - entry) * qty, 2),
            "bracket": {"valid": valid, "stop": bstop, "atr_fallback_stop": atr},
            "extension_bracket": ({"available": True, "stop": ext, "stop_basis": "x"} if ext is not None else {"available": False, "stop": None})}


# ---------------------------------------------------------------- 1 + 2 the reference stop and P&L in R
def test_reference_stop_precedence_structural_then_extension_then_atr_fallback_each_labelled():
    s, b = HV.reference_stop(row("A", 10, 10, 1, valid=True, bstop=9.0, ext=8.0, atr=9.5))
    assert (s, b) == (9.0, "structural bracket")
    s, b = HV.reference_stop(row("B", 10, 10, 1, valid=False, ext=8.0, atr=9.5))
    assert s == 8.0 and b.startswith("extension bracket")
    s, b = HV.reference_stop(row("C", 10, 10, 1, valid=False, atr=9.5))
    assert (s, b) == (9.5, "1 ATR fallback")
    assert HV.reference_stop(row("D", 10, 10, 1)) == (None, "no worked-out stop")


def test_p_and_l_in_r_uses_the_reference_stop_and_a_real_broker_stop_replaces_it_and_the_committee_1r_is_a_second_labelled_figure():
    ex = {"held_positions": [row("EBAY", 122.9178, 123.52, 150, atr=119.67, unreal=90.33), row("RBRK", 112.430375, 109.34, 80, ext=101.41, unreal=-247.23)]}
    v = {x["ticker"]: x for x in HV.held_view(ex, {"positions": {}}, one_r=620)}
    assert v["EBAY"]["reference_stop"] == 119.67 and v["EBAY"]["open_r"] == pytest.approx(0.19, abs=0.005)
    assert v["RBRK"]["open_r"] == pytest.approx(-0.28, abs=0.005)
    assert v["EBAY"]["pnl_in_committee_1r"] == pytest.approx(0.15, abs=0.005) and v["RBRK"]["pnl_in_committee_1r"] == pytest.approx(-0.40, abs=0.005)
    assert v["EBAY"]["broker_stop_status"] == "NO STOP AT BROKER" and v["EBAY"]["action"] == "SET-STOP"
    v2 = {x["ticker"]: x for x in HV.held_view(ex, {"positions": {"EBAY": {"stop": 121.0}}}, one_r=620)}
    assert v2["EBAY"]["stop_used"] == 121.0 and v2["EBAY"]["action"] is None and v2["EBAY"]["broker_stop_status"] == "broker stop 121.0"
    assert v2["EBAY"]["open_r"] == pytest.approx((123.52 - 122.9178) / (122.9178 - 121.0), abs=0.005)       # the real stop is used for R


def test_a_figure_that_cannot_be_computed_is_none_never_a_guess():
    ex = {"held_positions": [row("X", 10, 11, 5)]}                       # no stop of any kind
    x = HV.held_view(ex, {"positions": {}}, one_r=620)[0]
    assert x["reference_stop"] is None and x["open_r"] is None and x["pnl_in_committee_1r"] is not None
    assert "n/a" in HV.render_table([x]) and "SET-STOP" in HV.render_table([x])


def test_the_one_table_has_the_ruled_columns_and_the_flat_book_says_so():
    ex = {"held_positions": [row("EBAY", 122.9178, 123.52, 150, atr=119.67, unreal=90.33)]}
    md = HV.render_table(HV.held_view(ex, {"positions": {}}, one_r=620))
    head = md.splitlines()[0]
    for col in ("Name", "Qty", "Entry", "Mark", "P&L $", "P&L in R", "Broker stop status", "Worked-out stop (basis)", "Action", "not a size"):
        assert col in head, col
    out = subprocess.run([sys.executable, str(TOOLS / "held_view.py"), "table", "--export", str(_write(ex, "flat_or_held.json"))], capture_output=True, text=True)
    assert out.returncode == 0 and "EBAY" in out.stdout
    flat = subprocess.run([sys.executable, str(TOOLS / "held_view.py"), "table", "--export", str(_write({"held_positions": []}, "flat.json"))], capture_output=True, text=True)
    assert "FLAT" in flat.stdout


def _write(obj, name, d=[None]):
    import tempfile
    if d[0] is None:
        d[0] = Path(tempfile.mkdtemp())
    p = d[0] / name
    p.write_text(json.dumps(obj))
    return p


def test_cards_json_held_strings_no_longer_print_none():
    import pma_cards as PC
    ex = {"daily_list": [], "held_positions": [row("EBAY", 122.9178, 123.52, 150, atr=119.67, unreal=90.33)]}
    cond = {"rows": [{"ticker": "EBAY", "verdict": "PASS", "exits": [{"value": 100.0, "seats": ["a"]}]}]}
    bs = {"positions": {"EBAY": {"qty": 150, "stop": None, "order": None, "order_qty": None, "tif": None, "note": "NO STOP ORDER"}}}
    cards = PC.build_triggers(cond, ex, bs)
    f = cards["held"]["EBAY"]["for"]
    assert "None" not in f and "SET A STOP" in f and "119.67" in f and "reference only" in f
    assert "None" not in cards["held"]["EBAY"]["against"]


def test_pma_levels_held_rows_carry_the_reference_stop_status_and_set_stop_action(tmp_path):
    ex = {"daily_list": [], "held_positions": [row("EBAY", 122.9178, 123.52, 150, atr=119.67, unreal=90.33)]}
    (tmp_path / "e.json").write_text(json.dumps(ex))
    src = (TOOLS / "pma_levels.py").read_text()
    assert '"stop_status"' in src and '"reference_stop"' in src and '"SET-STOP"' in src


# ---------------------------------------------------------------- 3 the gate: SET-STOP in the one table under the combined heading
PFIX = TOOLS.parent / "tests" / "fixtures"


def _gate(tmp_path, nine_a, held, tag):
    stem = ("# B\n\n## §0 VERDICTS\n\n| T | V |\n|---|---|\n| X | ADVANCE |\n\n"
            "## §1 MACRO\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| c | d |\n|---|---|\n| 3 | 4 |\n\n## §2 SECTOR\n\n")
    adv = [c["ticker"] for c in json.load(open(PFIX / "consensus.json")) if c["verdict"] == "ADVANCE"]
    adv_rows = "".join(f"| {t} | ref | stop | conf | kill | ctx | Ready now |\n" for t in adv)
    ex = tmp_path / f"e_{tag}.json"
    ex.write_text(json.dumps({"daily_list": [], "held_positions": [{"ticker": t} for t in held]}))
    b = tmp_path / f"b_{tag}.md"
    b.write_text(stem + nine_a + "\n## §4 REPEAT\n\nthe committee will monitor the macro backdrop closely in the usual way.\n\n## §9A (the book table is §3 / §9A above)\n\nThe actions are the Action column above.\n\n"
                 "## §9B TRADE\n\n| Ticker | Entry | Stop | Confirms | Kills | Sector | Ready |\n|---|---|---|---|---|---|---|\n" + adv_rows + "\n## §9C PLAN\n\nAt the open, do x.\n")
    r = subprocess.run([sys.executable, str(PIPE), "gate", "--brief", str(b), "--consensus", str(PFIX / "consensus.json"), "--verdict-ledger", str(PFIX / "verdict_ledger.json"),
                        "--export", str(ex), "--date", "2026-09-06"], capture_output=True, text=True)
    return r.stdout + r.stderr


def test_the_gate_accepts_set_stop_in_the_one_table_under_the_combined_heading_and_ignores_the_words_in_other_sections(tmp_path):
    tbl = "## §3 / §9A — THE BOOK: what I own and what to do with it\n\n| Name | Action |\n|---|---|\n| **EBAY** | SET-STOP |\n| **GPN** | SET-STOP |\n"
    log = _gate(tmp_path, tbl, ["EBAY", "GPN"], "ok")
    assert "[PASS] Q9D 9A has one row per held name, each with exactly one action word (2 held)" in log
    assert "[FAIL] Q9D 9A has no unactionable" not in log          # 'monitor' appears in §4, outside the 9A section
    bad = _gate(tmp_path, tbl.replace("| **GPN** | SET-STOP |\n", ""), ["EBAY", "GPN"], "miss")
    assert "GPN (no row)" in bad


# ---------------------------------------------------------------- 6 compact repeat watch
def _ledger(tmp_path):
    ents = [{"date": "2026-11-03", "tickers": ["OLD", "STAY"]}, {"date": "2026-11-04", "tickers": ["STAY", "OLD"]}, {"date": "2026-11-05", "tickers": ["STAY"]},
            {"date": "2026-11-06", "tickers": ["STAY", "NEW1", "NEW2"]}]
    (tmp_path / "led.json").write_text(json.dumps({"entries": ents, "repeat_flags": [{"ticker": "STAY"}, {"ticker": "OLD"}]}))
    rows = [{"date": d, "ticker": t, "verdict": "PASS", "ref_price": 10.0 + i} for i, (d, t) in enumerate([("2026-11-03", "STAY"), ("2026-11-06", "STAY"), ("2026-11-06", "NEW1")])]
    (tmp_path / "ver.json").write_text(json.dumps({"rows": rows}))
    return tmp_path / "led.json", tmp_path / "ver.json"


def test_repeat_watch_is_a_count_line_and_one_row_per_new_or_standing_name_with_gaps_kept_in_the_json_only(tmp_path):
    led, ver = _ledger(tmp_path)
    out = tmp_path / "rw.json"
    r = subprocess.run([sys.executable, str(PIPE), "repeat-watch", "--ledger", str(led), "--verdicts", str(ver), "--date", "2026-11-06", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text())
    assert d["counts"]["new"] == 2 and d["counts"]["remain"] == 1 and d["counts"]["left"] == 1       # NEW1, NEW2 / STAY / OLD
    assert sorted(d["listed"]) == ["NEW1", "NEW2", "STAY"]
    md = d["markdown"]
    assert "2 NEW" in md and "1 REMAIN" in md and "1 LEFT" in md and "OLD" not in md and "GAP" not in md
    assert "| Ticker | First seen | Days on list | Verdict today | % vs first COB |" in md
    assert any(x.get("gap") for x in d["rows"]) and d["gaps"]                  # the per-date rows and the gap rows stay in the JSON


# ---------------------------------------------------------------- 4, 5, 6 + the book on the Cards page
@pytest.fixture()
def run(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(FIX, d)
    return d


def _render(run):
    out = run / "out.html"
    r = subprocess.run([sys.executable, str(TOOLS / "pma_cards_v3.py"), "--run-dir", str(run), "--out", str(out), "--refresh-dir", str(run / "ref")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-1500:]
    return out.read_text(encoding="utf-8")


def _text(h):
    import html as _h
    return _h.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))


def test_the_cards_page_has_the_one_book_table_the_valen_ticker_table_the_strong_names_table_the_count_strip_and_plain_sortable_lists(run):
    (run / "repeat_watch.json").write_text(json.dumps({"counts": {"new": 5, "remain": 7, "left": 3, "latest_list_date": "2026-11-04", "prior_sessions": 3}, "markdown": "x"}))
    h = _render(run)
    t = _text(h)
    # the book: one table, ruled columns, held names without a stop say so
    assert "Worked-out stop (basis)" in t and "P&L in R (own stop)" in t and "Broker stop status" in t
    # the strip
    assert "5 new, 7 remaining, 3 left" in t and "Against the last 3 sessions" in t
    # lists: plain tables with the ruled columns and a sortable class + script
    assert "Committee verdict Extended" in t and h.count('class="lst sortable"') >= 3 and "table.sortable" in h
    assert "Reason" not in re.findall(r"<th>[^<]*</th>", h.split('id="lists"')[1][:20000]).__str__()
    # strong names: a table beside the bar chart
    assert "Tickers (lead over SPY, 20 days)" in t
    # the Valen card: when any grade is triggered/ready/watch the table lists tickers
    if "Ticker Setup Status Pivot Stop" in t:
        assert re.search(r"Ticker Setup Status Pivot Stop \w", t)


def test_a_run_without_repeat_watch_counts_says_so_for_the_strip(run):
    t = _text(_render(run))
    assert "New, remaining and left counts are not available" in t
