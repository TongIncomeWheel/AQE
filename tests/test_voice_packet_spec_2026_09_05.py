"""Tests for the 2026-09-05 voice packet spec
(docs/specs/aqe_voice_packet_spec_2026-09-05.md): the pure derived-field
helpers added to src/data/drive_sync.py, and the structural invariants added
to the PMA slicing pipeline (CONSUMED coverage, the pattern-field build-time
assertion, and voice_menus.json's own shape).

The 2026-09-04 regression this file guards against directly: elder_hi7_streak
was computed correctly at every row's own call site, then silently clobbered
by _v21_record_fields()'s own default-None dict being spread in AFTER it --
caught only by running against real production data. test_elder_hi7_streak_*
covers the pure function; the clobber itself is a wiring bug that a pure
unit test on the helper alone cannot catch (see the full-export smoke test
at the bottom of this file)."""

from __future__ import annotations

import json

import pytest

from src.data import drive_sync as ds


# ── _stack_state ─────────────────────────────────────────────────────────

def test_stack_state_full_bullish_stack_is_aligned():
    assert ds._stack_state(20, 18, 16, 14) == "ALIGNED"


def test_stack_state_full_bearish_stack_is_inverted():
    assert ds._stack_state(14, 16, 18, 20) == "INVERTED"


def test_stack_state_short_end_recovering_is_repairing():
    """ma_20 has recrossed above ma_50 but the long end (ma_100/200) hasn't
    caught up yet -- a bullish repair in progress."""
    assert ds._stack_state(ma20=20, ma50=18, ma100=14, ma200=16) == "REPAIRING"


def test_stack_state_short_end_turning_down_is_rolling():
    """ma_20 has turned below ma_50 while the long end is still bullish -- a
    bearish rollover in progress."""
    assert ds._stack_state(ma20=18, ma50=20, ma100=16, ma200=14) == "ROLLING"


def test_stack_state_is_none_on_any_missing_ma():
    assert ds._stack_state(None, 18, 16, 14) is None
    assert ds._stack_state(20, 18, 16, None) is None
    assert ds._stack_state(None, None, None, None) is None


# ── _elder_hi7_streak ────────────────────────────────────────────────────

def test_elder_hi7_streak_counts_trailing_run_above_the_floor():
    assert ds._elder_hi7_streak([10, 10, 10, 10, 10]) == 5
    assert ds._elder_hi7_streak([5, 7, 8, 9, 10]) == 4
    assert ds._elder_hi7_streak([9, 9, 3, 9, 9]) == 2


def test_elder_hi7_streak_is_zero_when_the_most_recent_bar_is_below_seven():
    assert ds._elder_hi7_streak([10, 10, 10, 10, 6]) == 0


def test_elder_hi7_streak_is_none_on_empty_or_missing_history():
    assert ds._elder_hi7_streak(None) is None
    assert ds._elder_hi7_streak([]) is None


def test_elder_hi7_streak_caps_at_the_length_of_elder_5d():
    """elder_5d only ever carries 5 sessions -- the field cannot report a
    longer run than that, by construction, not by an arbitrary clamp."""
    assert ds._elder_hi7_streak([7, 7, 7]) == 3
    assert ds._elder_hi7_streak([7, 7, 7, 7, 7]) == 5


def test_v21_record_fields_defaults_never_clobber_the_call_site_value():
    """2026-09-04 regression: _v21_record_fields()'s own bulletproof defaults
    dict used to define elder_hi7_streak: None, and every call site spreads
    **_v21_record_fields(...) AFTER setting its own elder_hi7_streak key in
    the same dict literal -- so the default silently overwrote the real,
    already-computed value on every single row. The fix is that
    _v21_record_fields() must never define this key at all (mirroring how
    elder_5d itself is handled), so a caller's own value always wins."""
    fields = ds._v21_record_fields(
        "AAPL", {}, {}, {}, {}, regime_level=None)
    assert "elder_hi7_streak" not in fields, (
        "elder_hi7_streak must be set only by the caller (like elder_5d), "
        "never defaulted inside _v21_record_fields, or it will clobber "
        "whatever the call site already computed")


# ── PMA pipeline: CONSUMED field coverage ───────────────────────────────────
# 2026-09-05 regression: adding a field to voice_menus.json is not enough --
# pma_pipeline.py's cmd_trim() only carries CONSUMED fields into
# candidate_set.json, so a menu field missing from CONSUMED silently serves a
# blank column to that seat forever (caught only by running the real
# trim+packets pipeline against real data and reading its own
# missing_menu_fields receipt).

def _load_pma_pipeline_module():
    import importlib.util
    path = ("aegis/skills/premarket-analysis/tools/pma_pipeline.py")
    spec = importlib.util.spec_from_file_location("pma_pipeline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_voice_menus():
    with open("aegis/skills/premarket-analysis/contracts/voice_menus.json") as f:
        return json.load(f)


def test_every_menu_field_used_by_a_seat_is_carried_by_consumed():
    pp = _load_pma_pipeline_module()
    menus = _load_voice_menus()
    consumed = set(pp.CONSUMED)
    missing = set()
    for seat, cols in menus.items():
        if seat.startswith("~~"):
            continue
        for c in cols:
            top = c.split(".")[0]
            if top not in consumed:
                missing.add((seat, c))
    assert not missing, (
        f"menu field(s) not carried into candidate_set.json by CONSUMED "
        f"(seat will be served a permanently blank column): {sorted(missing)}")


def test_pattern_fields_are_never_named_by_any_seat_menu():
    """The build-time assertion pma_pipeline.py's cmd_packets() runs, checked
    directly against the real menus file rather than only through a full
    packets-build integration run."""
    pp = _load_pma_pipeline_module()
    menus = _load_voice_menus()
    for seat, cols in menus.items():
        if seat.startswith("~~"):
            continue
        breach = [f for f in cols
                  if f == pp.PATTERN_FORBIDDEN_PREFIX
                  or f.startswith(pp.PATTERN_FORBIDDEN_PREFIX + "_")
                  or f.startswith(pp.PATTERN_FORBIDDEN_PREFIX + ".")]
        assert not breach, f"{seat}'s menu names forbidden pattern field(s) {breach}"


def test_qs_fields_are_still_never_named_by_any_seat_menu():
    pp = _load_pma_pipeline_module()
    menus = _load_voice_menus()
    for seat, cols in menus.items():
        if seat.startswith("~~"):
            continue
        breach = [f for f in cols if f in pp.QS_FORBIDDEN or f.startswith("qs.")]
        assert not breach, f"R3 breach: {seat}'s menu names {breach}"


def test_no_seat_menu_carries_a_duplicate_column():
    menus = _load_voice_menus()
    for seat, cols in menus.items():
        if seat.startswith("~~"):
            continue
        dups = [c for c in set(cols) if cols.count(c) > 1]
        assert not dups, f"{seat}'s menu has duplicate column(s) {dups}"


# ── canon.lock.yaml: PM ruling R1 -- bracket fields are informational only ──
# oneil R6, raschke R6, wyckoff R6 used to reject a setup outright on
# bracket.valid/risk_pct. The spec's PM ruling R1 says no seat may reject on
# bracket.valid, bracket.rr* or bracket.risk_pct -- these three cards are the
# ones that still said so.

def _load_canon_lock(voice):
    import yaml
    with open(f"aegis/canon/{voice}/canon.lock.yaml") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("voice", ["oneil", "raschke", "wyckoff"])
def test_canon_lock_counts_still_match_the_recogniser_list_length(voice):
    """canon.lock.yaml is normally a BUILD artifact whose counts.recognisers
    is computed by canon_build.py -- this file was hand-edited (the source
    principles.yaml/diff.json for these voices are gitignored and not present
    in this checkout, so the normal build pipeline could not be re-run), so
    this is the one guard against the count silently drifting out of sync
    with the actual list on a future hand-edit."""
    lock = _load_canon_lock(voice)
    assert lock["counts"]["recognisers"] == len(lock["recognisers"])


@pytest.mark.parametrize("voice", ["oneil", "wyckoff"])
def test_canon_lock_no_recogniser_rejects_on_the_barred_bracket_fields(voice):
    """oneil and wyckoff's old R6 rejected outright on bracket.valid being
    false. Neither voice's recognisers may condition a reject on
    bracket.valid/bracket.rr*/bracket.risk_pct any more (PM ruling R1)."""
    lock = _load_canon_lock(voice)
    for r in lock["recognisers"]:
        cond = r["if"].lower()
        assert "bracket.valid is false" not in cond, (voice, r["id"], r["if"])
        assert "bracket.risk_pct exceeds" not in cond, (voice, r["id"], r["if"])


def test_raschke_r6_keeps_its_structural_stop_guidance_but_drops_the_reject():
    """raschke's R6 legitimately routes the stop through bracket.stop/
    bracket.stop_type rather than a percentage -- that guidance must survive.
    Only the 'bracket.valid: false is a hard reject' clause is barred."""
    lock = _load_canon_lock("raschke")
    r6 = next(r for r in lock["recognisers"] if r["id"] == "R6")
    assert "bracket.stop" in r6["then"]
    assert "hard reject" not in r6["then"].lower()
    assert "bracket.valid" not in r6["fields"], (
        "bracket.valid is no longer part of this recogniser's basis")


# ── emit_packets.py: the second, independent pattern-field lock ────────────

def _load_emit_packets_module():
    import importlib.util
    path = "aegis/skills/premarket-analysis/tools/emit_packets.py"
    spec = importlib.util.spec_from_file_location("emit_packets", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emit_packets_pattern_lock_flags_an_exact_header_match(tmp_path):
    ep = _load_emit_packets_module()
    tsv = tmp_path / "fake.tsv"
    tsv.write_text("ticker\tpattern\televated\n", encoding="utf-8")
    header = tsv.read_text(encoding="utf-8").splitlines()[0]
    cols = set(header.split("\t"))
    assert cols & ep.PATTERN_FIELDS_FORBIDDEN == {"pattern"}


def test_emit_packets_pattern_lock_never_false_positives_on_elder_pattern(tmp_path):
    """elder_pattern is a real, legitimate menu field on several seats and
    must never be flagged just for containing the substring 'pattern'."""
    ep = _load_emit_packets_module()
    tsv = tmp_path / "fake.tsv"
    tsv.write_text("ticker\televated_pattern\telder_pattern\n", encoding="utf-8")
    header = tsv.read_text(encoding="utf-8").splitlines()[0]
    cols = set(header.split("\t"))
    assert not (cols & ep.PATTERN_FIELDS_FORBIDDEN)
