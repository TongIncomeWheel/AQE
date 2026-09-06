"""Tests for the 2026-09-06 PM ruling: Layer 0 -- the committee (PMA) only
ever sees tickers on BOTH the Longlist and the Elder list, the same
intersection already surfaced to the AIC as the export's own
elder_and_longlist_tickers view.

Motivation (verbatim from the PM): observed runners were disproportionately
names on both lists; the wider single-list candidate pool was diluting the
committee's attention rather than sharpening it.

Two things are tested end to end against real subprocess invocations (not
imports) -- this is the actual CLI contract both pma_pipeline.py and
emit_packets.py are invoked through in production:

1. pma_pipeline.py's cmd_trim() applies the actual filter, and fixes a real
   bug caught in the same pass: `on_longlist` used to be derived from
   `source == "longlist"` (which list first produced the row), not the
   row's own real on_longlist flag -- silently misreporting on_longlist=false
   for any name whose primary source was elder_list/qs but which also
   independently cleared the longlist screen.
2. emit_packets.py's Layer 0 assurance check: candidate_set.json's own
   universe, and every seat packet's actual served ticker set, must match
   elder_and_longlist_tickers exactly, or it refuses to stamp -- the daily
   proof the two never drift apart."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

ROOT = "/home/user/AQE"
PMA_PIPELINE = f"{ROOT}/aegis/skills/premarket-analysis/tools/pma_pipeline.py"
EMIT_PACKETS = f"{ROOT}/aegis/skills/premarket-analysis/tools/emit_packets.py"


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def _row(ticker, on_longlist, on_elder, source="longlist", **extra):
    row = {
        "ticker": ticker, "rank": 1, "sc_momentum": 80.0, "source": source,
        "on_longlist": on_longlist, "on_elder": on_elder, "in_ledger": False,
        "held": False, "entry": 100.0, "elder": 8.0, "elder_5d": [8, 8, 8, 8, 8],
        "flow": 70.0, "energy": 70.0, "structure": 70.0, "mp": 70.0,
        "mp_state": "STRONG", "bracket": {"valid": True, "stop": 90.0},
    }
    row.update(extra)
    return row


@pytest.fixture
def export_file(tmp_path):
    daily_list = [
        _row("BOTH1", True, True),
        _row("BOTH2", True, True, source="elder_list"),  # the bug-fix case:
        # primary source is elder_list, but on_longlist is independently True
        _row("LONGLIST_ONLY", True, False),
        _row("ELDER_ONLY", False, True, source="elder_list"),
        _row("NEITHER", False, False, source="qs"),
    ]
    export = {
        "date": "2026-09-06",
        "exported_at": "2026-09-06 08:00:00 SGT",
        "daily_list": daily_list,
        "held_positions": [],
        "srm": [],
        "elder_and_longlist_tickers": ["BOTH1", "BOTH2"],
    }
    p = tmp_path / "aqe_daily_export.json"
    p.write_text(json.dumps(export), encoding="utf-8")
    return p


@pytest.fixture
def menus_file(tmp_path):
    menus = {
        "elder-lens": ["ticker", "elder", "elder_5d", "mp_state", "mp"],
        "livermore": ["ticker", "rank", "held", "entry", "bracket.valid", "bracket.stop"],
    }
    p = tmp_path / "voice_menus.json"
    p.write_text(json.dumps(menus), encoding="utf-8")
    return p


# ── cmd_trim: the actual filter ─────────────────────────────────────────────

def test_cmd_trim_keeps_only_names_on_both_lists(export_file, tmp_path):
    out = tmp_path / "candidate_set.json"
    r = _run([sys.executable, PMA_PIPELINE, "trim", "--export", str(export_file),
              "--date", "2026-09-06", "--out", str(out)])
    assert r.returncode == 0, r.stderr

    cs = json.loads(out.read_text())
    tickers = {row["ticker"] for row in cs["universe"]}
    assert tickers == {"BOTH1", "BOTH2"}, (
        "only names with on_longlist AND on_elder both true may survive Layer 0")
    assert "LAYER 0" in r.stdout
    assert "3 of 5 excluded" in r.stdout


def test_cmd_trim_on_longlist_reflects_the_real_flag_not_the_source(export_file, tmp_path):
    """The 2026-09-06 bug fix: BOTH2's primary source is elder_list, but it
    independently clears on_longlist=True -- the old `source == "longlist"`
    derivation would have misreported on_longlist=false for it and, before
    Layer 0 even existed, silently misclassified this exact class of runner
    everywhere on_longlist was read downstream."""
    out = tmp_path / "candidate_set.json"
    _run([sys.executable, PMA_PIPELINE, "trim", "--export", str(export_file),
          "--date", "2026-09-06", "--out", str(out)])
    cs = json.loads(out.read_text())
    both2 = next(row for row in cs["universe"] if row["ticker"] == "BOTH2")
    assert both2["on_longlist"] is True
    assert both2["on_elder"] is True


def test_cmd_trim_matches_elder_and_longlist_tickers_exactly(export_file, tmp_path):
    """Layer 0's own output must agree with the export's independently-
    computed elder_and_longlist_tickers view -- the same invariant
    emit_packets.py enforces at stamp time, checked here at the source."""
    out = tmp_path / "candidate_set.json"
    _run([sys.executable, PMA_PIPELINE, "trim", "--export", str(export_file),
          "--date", "2026-09-06", "--out", str(out)])
    cs = json.loads(out.read_text())
    export = json.loads(export_file.read_text())
    assert {row["ticker"] for row in cs["universe"]} == set(export["elder_and_longlist_tickers"])


# ── emit_packets.py: the daily assurance check ──────────────────────────────

def test_emit_packets_layer0_scan_is_clean_on_a_correct_export(export_file, menus_file, tmp_path):
    outdir = tmp_path / "voice_packets"
    r = _run([sys.executable, EMIT_PACKETS,
              "--export", str(export_file), "--menus", str(menus_file),
              "--pipeline", PMA_PIPELINE, "--outdir", str(outdir), "--date", "2026-09-06"])
    assert r.returncode == 0, r.stderr

    stamp = json.loads((outdir / "packet_stamp.json").read_text())
    assert stamp["layer0_scan"] == "clean"
    assert stamp["layer0_count"] == 2

    cs = json.loads((outdir / "candidate_set.json").read_text())
    assert {row["ticker"] for row in cs["universe"]} == {"BOTH1", "BOTH2"}

    livermore = (outdir / "livermore.tsv").read_text().splitlines()
    served = {ln.split("\t")[0] for ln in livermore[1:] if ln}
    assert served == {"BOTH1", "BOTH2"}


def test_emit_packets_refuses_to_stamp_on_a_layer0_drift(export_file, menus_file, tmp_path):
    """Corrupt elder_and_longlist_tickers so it disagrees with what
    cmd_trim's own on_longlist/on_elder flags would produce -- this is
    exactly the class of drift the assurance check exists to catch."""
    export = json.loads(export_file.read_text())
    export["elder_and_longlist_tickers"] = ["BOTH1"]  # drops BOTH2 -- a lie
    export_file.write_text(json.dumps(export), encoding="utf-8")

    outdir = tmp_path / "voice_packets"
    r = _run([sys.executable, EMIT_PACKETS,
              "--export", str(export_file), "--menus", str(menus_file),
              "--pipeline", PMA_PIPELINE, "--outdir", str(outdir), "--date", "2026-09-06"])

    assert r.returncode == 1
    assert "FATAL LAYER 0 BREACH" in r.stderr
    assert "BOTH2" in r.stderr
    assert not outdir.exists() or not (outdir / "packet_stamp.json").exists(), (
        "a Layer 0 breach must never publish a stamped (falsely trustworthy) packet set")
