"""The REPORT step's safety net (PM 2026-11-04, choice B): v3 is the Cards; if it errors or the plain-words gate fails, v2 publishes and the
fallback is LOUD (stdout, run_notes.md, cards_renderer.json). Never silent, never a blank page."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "cards_v3"
PUB = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "pma_cards_publish.py"
STUB_V2 = "echo '<html>v2 page</html>' > {out}"


@pytest.fixture()
def run(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(FIX, d)
    return d


def publish(run, *extra):
    r = subprocess.run([sys.executable, str(PUB), "--date", "2026-11-04", "--run-dir", str(run), "--refresh-dir", str(run / "ref"), "--renderer", "v3",
                        "--v2-command", STUB_V2, *extra], capture_output=True, text=True, timeout=300)
    meta = json.loads((run / "cards_renderer.json").read_text()) if (run / "cards_renderer.json").exists() else None
    return r, meta


def test_the_run_map_promotes_v3_and_names_the_publish_command():
    ry = (ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "RUN.yaml").read_text()
    assert "cards_renderer: v3" in ry and "pma_cards_publish.py --date <date>" in ry and "CARDS FALLBACK" in ry


def test_a_good_run_publishes_the_v3_page(run):
    r, meta = publish(run)
    assert r.returncode == 0, r.stderr[-600:]
    assert meta["renderer_published"] == "v3" and meta["fallback"] is False
    assert "Aegis committee cards" in (run / "pma_cards_2026-11-04.html").read_text()


def test_a_missing_input_falls_back_to_v2_loudly(run):
    (run / "phase4.json").unlink()
    r, meta = publish(run)
    assert r.returncode == 0
    assert meta["renderer_published"] == "v2" and meta["fallback"] is True and "phase4.json" in meta["reason"]
    assert "CARDS FALLBACK" in r.stdout and "CARDS FALLBACK" in (run / "run_notes.md").read_text()
    assert (run / "pma_cards_2026-11-04.html").read_text() .strip() == "<html>v2 page</html>"


def test_a_failed_plain_words_gate_falls_back_and_the_bad_page_is_never_published(run):
    p = run / "aqe_daily_export.json"
    o = json.loads(p.read_text())
    for row in o["daily_list"]:
        row["ma_status"], row["ma_note"] = ("PENDING_TARGET", "see bar_high and day_vol") if row["ticker"] == "HNGE" else ("NONE", "none")
    p.write_text(json.dumps(o))
    r, meta = publish(run)
    assert r.returncode == 0 and meta["fallback"] is True and "gate FAILED" in meta["reason"]
    assert "CARDS FALLBACK" in r.stdout
    assert (run / "pma_cards_2026-11-04.html").read_text() .strip() == "<html>v2 page</html>"            # the v2 page, not the rejected v3 one
    assert (run / "pma_cards_2026-11-04.html.v3.rejected.html").exists()                       # kept for the post-mortem


def test_if_v2_also_fails_the_command_fails_loudly(run):
    (run / "phase4.json").unlink()
    r = subprocess.run([sys.executable, str(PUB), "--date", "2026-11-04", "--run-dir", str(run), "--renderer", "v3", "--v2-command", "false"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 2 and "CARDS FAILED" in r.stdout


def test_a_writer_line_that_breaks_the_gate_is_named_in_run_notes_and_the_page_still_publishes(run):
    cons = json.loads((run / "consensus.json").read_text())
    t = next(c["ticker"] for c in cons if c["verdict"] == "ADVANCE")
    (run / "cards_lines.json").write_text(json.dumps({t: {"why": "Livermore likes this leader (C9).", "contested": "No objection filed: the room agreed on the break."}}))
    r, meta = publish(run)
    assert r.returncode == 0 and meta["renderer_published"] == "v3" and meta["fallback"] is False
    notes = (run / "run_notes.md").read_text()
    assert f"CARDS LINES FALLBACK: {t} (why)" in notes and "names a seat" in notes


def test_a_missing_lines_file_is_declared_in_run_notes(run):
    r, meta = publish(run)
    assert meta["renderer_published"] == "v3"
    assert "CARDS LINES: " in (run / "run_notes.md").read_text() and "file absent" in (run / "run_notes.md").read_text()
