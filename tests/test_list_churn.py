"""List size and churn (conductor/PM 2026-11-05): who left `daily_list`, and the gate that removed them."""
import json

from src.data import list_churn as LC


def _row(tk, sc=70.0, elder=8.0, **kw):
    return {"ticker": tk, "sc_momentum": sc, "elder": elder, "on_longlist": True, "on_elder": elder >= 8, **kw}


def test_a_leaver_is_explained_by_the_gate_it_failed():
    # BRZE on 4 Nov: SC_MOM 68.4, Elder 7.0 (Longlist yes, Elder list no). Next day the score fades under 65.
    r = LC.explain_drop("BRZE", {"sc_momentum_raw": 63.2, "elder_score": 7.0}, _row("BRZE", 68.4, 7.0))
    assert r["status"] == "BELOW_GATES" and r["sc_momentum_raw"] == 63.2
    assert any("63.2" in x and "Longlist" in x for x in r["reasons"]) and any("Elder-list floor of 8" in x for x in r["reasons"])
    assert r["was"] == ["on_longlist"] and r["prev_sc_momentum"] == 68.4


def test_elder_alone_failing_says_so_and_a_missing_score_row_is_not_scored():
    r = LC.explain_drop("X", {"sc_momentum_raw": 80.0, "elder_score": 6.0}, _row("X", 80.0, 8.0))
    assert r["status"] == "BELOW_GATES" and all("momentum score" not in x for x in r["reasons"])
    n = LC.explain_drop("GONE", None, _row("GONE"))
    assert n["status"] == "NOT_SCORED" and "not in today's scores" in n["reasons"][0]


def test_a_name_that_clears_a_gate_but_is_absent_is_called_a_fault_never_given_a_made_up_reason():
    r = LC.explain_drop("Y", {"sc_momentum_raw": 80.0, "elder_score": 9.0}, _row("Y"))
    assert r["status"] == "CLEARS_GATES_BUT_ABSENT" and "not a rule" in r["reasons"][0]


def test_compute_counts_added_and_removed_and_prints_one_marker_line():
    prev = {"date": "2026-11-04", "daily_list": [_row("AAA"), _row("BRZE", 68.4, 7.0), _row("TMO", 66.0, 7.0)]}
    now = [_row("AAA"), _row("NEW1"), _row("NEW2")]
    scores = {"BRZE": {"sc_momentum_raw": 60.0, "elder_score": 7.0}}          # TMO has no score row today
    ch = LC.compute(prev, now, scores, "2026-11-05")
    assert (ch["n_prev"], ch["n_now"], ch["n_added"], ch["n_removed"]) == (3, 3, 2, 2)
    assert ch["added"] == ["NEW1", "NEW2"] and [r["ticker"] for r in ch["removed"]] == ["BRZE", "TMO"]
    assert {r["ticker"]: r["status"] for r in ch["removed"]} == {"BRZE": "BELOW_GATES", "TMO": "NOT_SCORED"}
    ln = LC.line(ch)
    assert ln.startswith("List churn: 3 -> 3 names vs 2026-11-04 (+2 / -2)") and "left: BRZE, TMO" in ln
    assert len(LC.detail_lines(ch)) == 2 and "BRZE" in LC.detail_lines(ch)[0]


def test_no_previous_export_is_loud_not_an_empty_churn():
    ch = LC.compute(None, [_row("A")], {}, "2026-11-05")
    assert ch["status"] == "no_previous" and ch["n_prev"] is None
    assert LC.line(ch).startswith("List churn: NOT COMPUTED")
    assert LC.detail_lines(ch) == []


def test_load_previous_takes_the_newest_earlier_dated_file_and_never_compares_a_rerun_with_itself(tmp_path):
    a = tmp_path / "a.json"; b = tmp_path / "b.json"; c = tmp_path / "c.json"; bad = tmp_path / "bad.json"
    a.write_text(json.dumps({"date": "2026-11-03", "daily_list": [_row("A")]}))
    b.write_text(json.dumps({"date": "2026-11-04", "daily_list": [_row("B")]}))
    c.write_text(json.dumps({"date": "2026-11-05", "daily_list": [_row("C")]}))      # today's own earlier write
    bad.write_text("{not json")
    got = LC.load_previous("2026-11-05", [a, b, c, bad, tmp_path / "missing.json"])
    assert got["date"] == "2026-11-04"
    assert LC.load_previous("2026-11-03", [a]) is None                                  # nothing earlier than the first day


def test_attach_never_raises_and_records_the_error(capsys):
    exp = {"date": "2026-11-05", "daily_list": [_row("A")]}
    ch = LC.attach(exp, {}, ["/nonexistent/x.json"])
    assert exp["list_churn"]["status"] == "no_previous" and ch is exp["list_churn"]
    assert "List churn: NOT COMPUTED" in capsys.readouterr().out
    bad = {"date": "2026-11-05", "daily_list": [_row("A")]}
    class Boom(dict):
        def get(self, *a, **k): raise RuntimeError("x")
    ch2 = LC.attach(bad, Boom(), ["/nonexistent/x.json"])
    assert ch2["status"] in ("no_previous", "error")


def test_the_gates_quoted_are_the_real_ones():
    from src import longlist_screen as L
    assert LC.LL_MIN_SC == L.MIN_SC and LC.LL_MIN_ELDER == L.MIN_ELDER and LC.ELDER_LIST_MIN == 8
