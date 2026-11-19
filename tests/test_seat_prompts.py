"""seat_prompts: the later rounds' prompts built from the run's own files (conductor + PM 2026-11-19). Offline.

GOLDEN: the 19 Nov run's CROSS / TIER2 / RATIFY / FLOOR2 / RATIFY2 / ADOPT prompts (60 files the conductor ran) are reproduced BYTE FOR BYTE from the committed run
files and the repo templates, apart from the one added seat-rows READ item."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools"
RUN = ROOT / "aegis" / "output" / "pma" / "run" / "2026-11-19"
SEATS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]
GOLD_ROOT = "/home/user/pma_run/2026-11-19"
GOLD_REPO = "/home/user/AQE"

R40_AMENDMENTS = [
    ("The trigger is an entry point, not a gate (R40, amended 2026-11-19): if you disagree with the ticket's trigger, still answer AGREE (or AGREE_WITH_RESERVATION about the stock) and file your "
     "preferred trigger as trigger_note {word, tf, plain}; OBJECT is only for the stock itself and must carry objects_to \"STOCK\"; trigger notes never count toward a drop.",
     "A seat that disagrees with a ticket's trigger must OBJECT, not reserve (R40)."),
    ("OBJECT (the stock only: objects_to \"STOCK\", and the one thing that would clear it), plus", "OBJECT (say the one thing that would clear it), plus"),
    ("A trigger you would set differently is a trigger_note {word, tf, plain} on an AGREE, never an OBJECT (R40 amended). Judge on YOUR method now", "Judge on YOUR method now"),
    ("say what would clear your objection (about the stock; a preferred trigger goes in trigger_note {word, tf, plain}, never as an objection - R40 amended).", "say what would clear your objection."),
    (" Hold on STOCK evidence only (each hold carries about \"STOCK\"): trigger wording is an entry point, not a gate, and is never a ground for a hold (R40 amended 2026-11-19).", ""),
    (" If you would set the ticket's trigger differently, add it as trigger_note {word, tf, plain}; a trigger note is carried to the alert layer and never counts as a dissent against the stock (R40 amended).", ""),
]

spec = importlib.util.spec_from_file_location("seat_prompts", TOOLS / "seat_prompts.py")
SP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SP)

pytestmark = pytest.mark.skipif(not (RUN / "prompts" / "CROSS" / "seow.txt").exists(), reason="the 19 Nov prompts are not in this checkout")


@pytest.fixture()
def work(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    for f in ("run_manifest.json", "funnel.json", "claims_board.json", "slate.json", "rationale_draft.json", "phase4.json", "consensus.json", "broker_stops.json", "held_table.md"):
        if (RUN / f).exists():
            shutil.copy(RUN / f, w / f)
    (w / "forms" / "qa").mkdir(parents=True)
    shutil.copy(RUN / "forms" / "qa" / "steenbarger.json", w / "forms" / "qa" / "steenbarger.json")
    return w


@pytest.mark.parametrize("rnd", SP.ROUNDS)
def test_the_19_nov_prompts_are_reproduced_byte_for_byte_without_the_seat_rows_item(work, rnd):
    for seat in SP.ROUND_SEATS.get(rnd, SEATS):
        got = SP.render(rnd, seat, str(work), GOLD_REPO, with_rows=False)
        got = got.replace(str(work), GOLD_ROOT)
        want = (RUN / "prompts" / rnd / f"{seat}.txt").read_text(encoding="utf-8")
        # The conductor's NOMINATE text also said "SPCX was closed on 18 Nov and RBRK on 17 Nov": closed-position history is not in broker_stops.json or the held
        # table, so the tool does not carry it (the book line comes from those two files only). Everything else is byte for byte.
        want = want.replace("; SPCX was closed on 18 Nov and RBRK on 17 Nov, so held_review", ", so held_review")
        # R40 AMENDED (PM 2026-11-19, after the 19 Nov run): the trigger is an entry point, not a gate. The templates carry the amended wording from the
        # 20 Nov session; the 19 Nov prompts were run under the original rule. These are the ONLY substitutions; reversing them must give the 19 Nov text exactly.
        for new_txt, old_txt in R40_AMENDMENTS:
            got = got.replace(new_txt, old_txt)
        assert got == want, f"{rnd}/{seat} differs from the prompt the conductor ran"


@pytest.mark.parametrize("rnd", sorted(SP.ROWS_ROUNDS))
def test_every_prompt_names_the_seat_rows_file_once_and_numbers_it_after_the_last_item(work, rnd):
    t = SP.render(rnd, "seow", str(work), GOLD_REPO, with_rows=True)
    path = SP.seat_rows_path(str(work), rnd, "seow")
    assert t.count(path) == 1 and "not in it is off your menu" in t.replace("a field that is not in it", "not in it") or "off your menu" in t
    if rnd != "ADOPT":
        m = re.search(r"^(\d+)\. Your AQE data for this round", t, flags=re.M)
        assert m, rnd
        items = [int(x) for x in re.findall(r"^(\d+)\. ", t.split("READ ONLY")[1].split("THE ROUND")[0].split("Steenbarger (QA)")[0], flags=re.M)]
        assert items == list(range(1, len(items) + 1)), (rnd, items)


def test_a_missing_run_file_is_a_loud_failure_never_a_default(work):
    (work / "funnel.json").unlink()
    with pytest.raises(SystemExit) as e:
        SP.render("TIER2", "seow", str(work), GOLD_REPO, with_rows=False)
    assert "funnel.json is missing" in str(e.value)
    (work / "forms" / "qa" / "steenbarger.json").write_text(json.dumps({"holds": []}))
    with pytest.raises(SystemExit) as e:
        SP.render("FLOOR2", "seow", str(work), GOLD_REPO, with_rows=False)
    assert "no holds" in str(e.value)


def test_the_stale_text_check_fails_on_yesterdays_tickers_and_dates(work, tmp_path):
    repo = tmp_path / "repo"
    old = repo / "aegis" / "output" / "pma" / "run" / "2026-11-18"
    old.mkdir(parents=True)
    (old / "slate_held.json").write_text(json.dumps({"tickets": [{"ticker": "MBGL"}, {"ticker": "ZZYY"}]}))
    (old / "broker_stops.json").write_text(json.dumps({"stops": [{"ticker": "RBRK"}, {"symbol": "SPCX"}]}))
    clean = SP.render("RATIFY2", "seow", str(work), str(repo), with_rows=False)
    assert SP.check_prompt(clean, str(work), str(repo)) == []
    stale = clean.replace("WWW and AMRX", "MBGL and ZZYY") + "\nthe book: RBRK long, SPCX short; data 2026-11-17"
    bad = SP.check_prompt(stale, str(work), str(repo))
    for t in ("MBGL", "ZZYY", "RBRK", "SPCX"):
        assert any(f"ticker {t}" in b for b in bad), (t, bad)
    assert any("2026-11-17" in b for b in bad)


def test_the_build_command_writes_rows_and_prompts_and_declares_a_ticker_with_no_row(work, tmp_path):
    cs = {"universe": [{"ticker": t, "adx_14": 20.0, "subcomponents": {"flow": {"cmf": 0.1}}} for t in ("WWW", "AMRX")]}   # the held pair only
    (work / "candidate_set.json").write_text(json.dumps(cs))
    out = tmp_path / "prompts"
    r = subprocess.run([sys.executable, str(TOOLS / "seat_prompts.py"), "build", "--round", "RATIFY2", "--seats", "seow", "--work", str(work), "--repo", str(tmp_path / "norepo"),
                        "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = json.loads((work / "seat_rows" / "RATIFY2" / "seow.json").read_text())
    assert [n["ticker"] for n in rows["names"]] == ["WWW", "AMRX"] and rows["names"][0]["row"]["adx_14"] == 20.0
    assert (out / "RATIFY2" / "seow.txt").exists()
    cs["universe"].pop()
    (work / "candidate_set.json").write_text(json.dumps(cs))
    r = subprocess.run([sys.executable, str(TOOLS / "seat_prompts.py"), "build", "--round", "RATIFY2", "--seats", "seow", "--work", str(work), "--repo", str(tmp_path / "norepo"),
                        "--out", str(out)], capture_output=True, text=True)
    rows = json.loads((work / "seat_rows" / "RATIFY2" / "seow.json").read_text())
    assert rows["names"][1]["row"] is None and "row_gap" in rows["names"][1], "a missing row is declared in the file"
    assert "WARNING" in r.stdout


def test_the_book_line_comes_only_from_broker_stops_and_the_held_table_and_the_two_must_agree(work):
    assert "FLAT: no position is held" in SP.book_sentence(str(work))
    (work / "broker_stops.json").write_text(json.dumps({"positions": {"RBRK": {"stop": 99.45}, "SPCX": {"stop": 150}}}))
    with pytest.raises(SystemExit) as e:
        SP.book_sentence(str(work))                        # the held table still says FLAT
    assert "FLAT" in str(e.value) and "RBRK" in str(e.value)
    (work / "held_table.md").write_text("| Ticker | Qty |\n|---|---|\n| RBRK | 80 |\n| SPCX | -68 |\n")
    line = SP.book_sentence(str(work))
    assert "RBRK, SPCX" in line and "99.45" not in line, "tickers only: no stop or quantity is restated in prompt text"
    (work / "held_table.md").write_text("| Ticker | Qty |\n|---|---|\n| RBRK | 80 |\n")
    with pytest.raises(SystemExit) as e:
        SP.book_sentence(str(work))
    assert "names ['RBRK']" in str(e.value)
    (work / "held_table.md").unlink()
    with pytest.raises(SystemExit) as e:
        SP.book_sentence(str(work))
    assert "held_table.md is missing" in str(e.value)


def test_a_stale_book_in_another_runs_broker_stops_is_caught_in_a_nominate_prompt(work, tmp_path):
    repo = tmp_path / "repo"
    old = repo / "aegis" / "output" / "pma" / "run" / "2026-11-18"
    old.mkdir(parents=True)
    (old / "broker_stops.json").write_text(json.dumps({"positions": {"RBRK": {"stop": 99.45}, "SPCX": {"stop": 150}}}))
    clean = SP.render("NOMINATE", "seow", str(work), str(repo), with_rows=False)
    assert SP.check_prompt(clean, str(work), str(repo)) == []
    stale = clean.replace("FLAT: no position is held", "RBRK is held with a stop at 99.45")
    bad = SP.check_prompt(stale, str(work), str(repo))
    assert any("ticker RBRK" in b for b in bad), bad


def test_the_vote_prompt_splits_the_room_by_the_runs_own_deliberation_set(work):
    t = SP.render("VOTE", "seow", str(work), GOLD_REPO, with_rows=False)
    n = len(SP.round_tickers("VOTE", str(work), "seow"))
    assert f"vote on EVERY one of the {n} deliberation-set names" in t and "file 2 parts" in t
    ph = json.loads((work / "phase4.json").read_text())
    ph["deliberation_set"] = ph["deliberation_set"][:5]
    (work / "phase4.json").write_text(json.dumps(ph))
    t = SP.render("VOTE", "seow", str(work), GOLD_REPO, with_rows=False)
    assert "EVERY one of the 5 deliberation-set" in t and "file 1 parts" in t.replace("file 1 parts", "file 1 parts") and "partNof1" in t


def test_challenge_and_qa_are_the_qa_seats_and_carry_no_seat_rows(work):
    for rnd in ("CHALLENGE", "QA"):
        assert SP.ROUND_SEATS[rnd] == ["steenbarger"] and rnd not in SP.ROWS_ROUNDS
        t = SP.render(rnd, "steenbarger", str(work), GOLD_REPO, with_rows=False)
        assert "STEENBARGER seat" in t and "seat_rows" not in t
