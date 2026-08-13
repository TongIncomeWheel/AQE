"""The taxonomy is a claim about the engines. These tests check the claim.

A field list that drifts from the code is worse than none, because it is
believed. The weights and divisors in the CSV are transcribed by hand from
src/engines/*.py; these read the engines back and assert the transcription
still holds.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "docs" / "AQE_DATA_TAXONOMY.csv"

COLUMNS = ["field", "parent", "level", "output", "state", "represents",
           "source", "formula", "weight", "used_by", "ships_in_export"]


def rows():
    with CSV_PATH.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def by_field():
    return {r["field"]: r for r in rows()}


# ── shape ────────────────────────────────────────────────────────────────

def test_the_csv_exists_and_has_the_agreed_columns():
    assert CSV_PATH.exists(), "run python -m scripts.build_data_taxonomy"
    with CSV_PATH.open(encoding="utf-8") as fh:
        assert next(csv.reader(fh)) == COLUMNS


def test_every_row_carries_the_five_things_the_pm_asked_for():
    """field name, output, state, what it represents, source, formula."""
    schema_vocab = {"role", "side", "unit"}
    for r in rows():
        assert r["field"], r
        assert r["source"], f"{r['field']} has no source"
        if r["field"] in schema_vocab:
            continue                       # the enum vocabulary itself
        assert r["represents"], f"{r['field']} has no represents"


def test_every_scored_row_carries_real_arithmetic():
    for r in rows():
        if r["level"] in ("composite", "engine", "component"):
            assert r["formula"], f"{r['field']} is a score with no formula"
            assert r["output"], f"{r['field']} has no output range"


def test_every_parent_named_by_a_child_is_resolvable():
    known = {r["field"] for r in rows()}
    # Parents that name a module rather than a scored field.
    modules = {"divergence", "smart_money_knn", "pin_bar", "signal_radar",
               "fibonacci", "moving_averages", "qs", "bracket_engine",
               "patterns", "srm", "srm_thematic", "health", "lens_consensus",
               "fip", "market_stats"}
    for r in rows():
        p = r["parent"]
        if p:
            assert p in known or p in modules, f"{r['field']} -> unknown parent {p}"


def test_no_prose_paragraphs_leaked_into_a_cell():
    """A data taxonomy is a table, not an essay."""
    for r in rows():
        for col, val in r.items():
            assert "\n" not in val, f"{r['field']}.{col} contains a newline"
            assert len(val) <= 320, f"{r['field']}.{col} is {len(val)} chars"


def test_every_field_name_is_unique():
    """The field column is the row's identity. A repeat silently shadows
    one row's data with another's wherever anything keys off the name."""
    names = [r["field"] for r in rows()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"repeated field names: {dupes}"


def test_formula_cells_hold_calculation_not_narration():
    """represents is the prose column. formula is not — it must read as an
    expression a reader could evaluate, not a description of one."""
    import re
    banned = [r"\bno squeeze\b", r"\bin squeeze\b", r"\bsame as\b",
              r"\bsame mechanism\b", r"\balready 0-100\b",
              r"\bunconditionally\b", r"\bbanded on\b", r"\bsee \w",
              r"\bdocstring\b", r"\.\.\.", r"\bonly when\b",
              r"\bnot above\b", r"\band rising->\b"]
    pattern = re.compile("|".join(banned), re.IGNORECASE)
    for r in rows():
        if not r["formula"]:
            continue
        m = pattern.search(r["formula"])
        assert not m, f"{r['field']}.formula narrates instead of computing: {m.group()!r}"


# ── the transcription matches the engines ────────────────────────────────

def test_composite_weights_match_scoring_py():
    from src.engines.scoring import SC_M_WEIGHTS, SC_P_WEIGHTS
    assert sum(SC_M_WEIGHTS.values()) == 1.0
    assert sum(SC_P_WEIGHTS.values()) == 1.0
    f = by_field()["sc_momentum"]["formula"]
    for engine, w in SC_M_WEIGHTS.items():
        assert f"{w:.2f}*{engine}" in f, f"sc_momentum formula lost {engine}"
    fp = by_field()["sc_position"]["formula"]
    for engine, w in SC_P_WEIGHTS.items():
        assert f"{w:.2f}*{engine}" in fp, f"sc_position formula lost {engine}"


def _component_max(field: str) -> float:
    """The '17 of 38' half of a weight cell."""
    w = by_field()[field]["weight"]
    head = w.split(" of ")[0]
    return float(head.replace("+", "").split("..")[-1])


def _children(parent: str) -> list[str]:
    return [r["field"] for r in rows()
            if r["parent"] == parent and r["level"] == "component"]


def test_component_maxima_sum_to_each_engine_divisor():
    """Flow 38, Energy 59.5, Structure 95, MP 100, BQ 100, Elder 10. If a
    component's cap changes in the engine and not here, the CSV is lying about
    how much that component can move the score."""
    expected = {"energy": 59.5, "structure": 95.0, "mp": 100.0, "bq": 100.0,
                "elder": 10.0}
    for engine, divisor in expected.items():
        total = sum(_component_max(c) for c in _children(engine))
        assert total == divisor, f"{engine}: components sum to {total}, not {divisor}"

    # Flow's positive components reach 40.5 and the sum is CLIPPED at 38, so it
    # is the one engine whose parts can exceed its own divisor.
    flow_positive = sum(_component_max(c) for c in _children("flow")
                        if c != "ext_score")
    assert flow_positive == 35.5
    assert "clip(" in by_field()["flow"]["formula"] and "38" in by_field()["flow"]["formula"]


def test_the_divisors_in_the_formulas_are_the_ones_in_the_engines():
    for engine, divisor in (("flow", "38"), ("energy", "59.5"),
                            ("structure", "95")):
        src = (ROOT / "src" / "engines" / f"{engine}.py").read_text(encoding="utf-8")
        assert f"/ {divisor}" in src, f"{engine}.py no longer divides by {divisor}"
        assert divisor in by_field()[engine]["formula"]


def test_the_gate_floors_match_scoring_py():
    from src.engines.scoring import SC_M_GATES, SC_P_GATES
    f = by_field()["sc_m_gates"]["formula"]
    for k, v in SC_M_GATES.items():
        assert f"{k}>={v:g}" in f, f"sc_m_gates lost {k}"
    fp = by_field()["sc_p_gates"]["formula"]
    for k, v in SC_P_GATES.items():
        if isinstance(v, (int, float)):
            assert f"{k}>={v:g}" in fp, f"sc_p_gates lost {k}"


def test_disposition_is_gone_from_the_taxonomy():
    """PTRS, then the disposition ceiling built to replace it, were both a
    re-read of SC_MOMENTUM through a threshold table with no consumer.
    Retired 2026-08-13 rather than kept as documented, unused apparatus."""
    f = by_field()
    assert "disposition" not in f
    assert "max_size" not in f
    from src.analyzer import ptrs as P
    assert not hasattr(P, "compute_disposition")
    assert not hasattr(P, "DISPOSITION_CUTS")


def test_the_shortlist_floor_matches_the_orchestrator():
    from src.pipeline.daily_orchestrator import SHORTLIST_MIN_SC
    assert SHORTLIST_MIN_SC == 45.0


def test_the_longlist_rule_matches_the_screen():
    from src.longlist_screen import MIN_ELDER, MIN_SC
    f = by_field()["on_longlist"]["formula"]
    assert f"sc_momentum_raw >= {MIN_SC}" in f
    assert f"elder >= {MIN_ELDER}" in f


# ── state fields carry the calculation that produces the label ──────────

def test_every_enum_field_also_carries_a_real_formula():
    """A label with no derivation is a value with no source. Every field
    that names states in its enum column must show how it lands on one."""
    schema_vocab = {"role", "side", "unit"}
    for r in rows():
        if r["state"] and r["field"] not in schema_vocab:
            assert r["formula"], f"{r['field']} lists states but no formula"


def test_the_srm_grade_ladder_matches_the_engine():
    from src.engines.srm import ACCEL_MIN_DIVERGENCE, ACCEL_MIN_ROC5, TREND_MIN_ROC20
    f = by_field()["grade"]["formula"]
    assert f"roc20>{TREND_MIN_ROC20}" in f
    assert f"roc5>={ACCEL_MIN_ROC5}" in f
    assert f"divergence>={ACCEL_MIN_DIVERGENCE}" in f


def test_the_bos_extension_cap_matches_the_export():
    from src.data.drive_sync import BOS_MAX_EXTENSION_PCT
    f = by_field()["structure_shift"]["formula"]
    assert f"ext_pct<={BOS_MAX_EXTENSION_PCT}" in f


def test_the_hl_state_bands_match_health_py():
    f = by_field()["hl_state"]["formula"]
    assert ">=30->TIGHTEN" in f and ">=50->HOLD" in f and ">=75->HOLD_ADD" in f


def test_previously_incomplete_enums_are_fixed_at_the_source():
    """hl_state was missing HOLD_ADD, the two RRG-direction fields were
    missing STABLE, thematic_grade was missing NO_DATA — all real values the
    engines emit that the export's own self-description didn't list. Fixed
    in agentic_dictionary.py, not just papered over in the taxonomy."""
    from src.engines.agentic_dictionary import FIELD_ENUMS
    assert "HOLD_ADD" in FIELD_ENUMS["hl_state"]
    assert "STABLE" in FIELD_ENUMS["sector_rrg_direction"]
    assert "STABLE" in FIELD_ENUMS["thematic_rrg_direction"]
    assert "NO_DATA" in FIELD_ENUMS["thematic_grade"]


# ── source integrity: never the glossary, never a malformed key ─────────

def test_nothing_cites_the_glossary_as_its_source():
    """field_glossary describes fields; it does not compute them. Citing it
    as 'source' was citing documentation as evidence. Zero tolerance: the
    one row allowed to name it is 'field_glossary' itself — the export
    BLOCK whose entire content literally IS that dict, where citing it is
    not laziness but the true and only answer. role/side/unit are not data
    fields — they're the schema's own controlled vocabulary — and are
    sourced to _FIELD_SCHEMA_ENUMS, not the glossary, since that's where
    their actual content (the enum lists) lives; the glossary carries no
    text for any of the three."""
    still_glossary = [r["field"] for r in rows()
                      if "_FIELD_GLOSSARY" in r["source"]]
    assert still_glossary == ["field_glossary"], \
        f"unexpected glossary-only sources: {still_glossary}"


def test_malformed_glossary_keys_never_become_rows():
    """field_glossary carries 3 keys that join several real field names
    with a slash — one entry documenting five fields at once. Iterating
    that dict naively turns each into a fake row."""
    from scripts.build_data_taxonomy import MALFORMED_GLOSSARY_KEYS
    field_names = {r["field"] for r in rows()}
    assert not (field_names & MALFORMED_GLOSSARY_KEYS)


def test_the_dropped_malformed_keys_real_fields_still_have_their_own_rows():
    """The fix must not lose coverage — each individual field the combined
    key was describing needs its own row with its own real formula."""
    f = by_field()
    for field in ("fib_236", "fib_382", "fib_500", "fib_618", "fib_786",
                 "fib_swing_low", "fib_swing_high",
                 "ma_20", "ma_50", "ma_100", "ma_200"):
        assert f[field]["formula"], f"{field} lost its formula in the fix"


# ── two naming corrections found while sourcing every field ─────────────

def test_structure_field_names_match_the_engines_own_columns():
    """structure.py's DataFrame column is ms_pos_score, not 'ms_pos' — this
    taxonomy used the shorter name until the mismatch was found while
    tracing what QS actually reads (QS's LENSES dict uses ms_pos_score)."""
    f = by_field()
    assert "ms_pos_score" in f
    assert "ms_pos" not in f


def test_pipeline_rank_field_names_match_the_engines_own_columns():
    """pipeline_rank.py's local variable is ret_score but its DataFrame
    column — and score_runner.py's merged name — is ret_12m_score."""
    f = by_field()
    assert "ret_12m_score" in f
    assert "ret_score" not in f


# ── used_by: consumers confirmed by direct read, not guessed ────────────

def test_qs_lens_inputs_are_marked_as_used_by_qs():
    """Every field QS's own LENSES dict reads (qs_spec.py:31-37) should say
    so, so a reader can tell this isn't just an AQE-internal number."""
    f = by_field()
    for field in ("en_pos50", "ms_pos_score", "roc_zscore", "abs_mom_score",
                 "rel_mom_score", "accum_score", "mfi", "cmf", "rs_vs_spy",
                 "bq_range_tight", "bq_ema_conv", "squeeze_score"):
        assert "QS" in f[field]["used_by"], f"{field} used_by not marked"


def test_lens_consensus_inputs_are_marked():
    f = by_field()
    assert "lens_consensus" in f["gics_gate"]["used_by"]


def test_longlist_and_elder_gates_declare_their_own_consumer():
    f = by_field()
    assert "alert" in f["on_longlist"]["used_by"].lower()
    assert "alert" in f["on_elder"]["used_by"].lower()


def test_the_integrity_findings_doc_exists_and_names_its_key_findings():
    """The completeness/duplicate audit that produced most of the fixes
    above lives in a companion doc, not just in commit messages."""
    text = (ROOT / "docs" / "AQE_DATA_INTEGRITY_FINDINGS.md").read_text(encoding="utf-8")
    for phrase in ("ms_pos_score", "ret_12m_score", "on_elder",
                  "MALFORMED_GLOSSARY_KEYS", "stair_hl_count", "rt_ratio"):
        assert phrase in text, f"findings doc lost its note on {phrase}"


# ── ships_in_export: labelling what's actually in the JSON ──────────────

def test_the_fundamental_composites_are_correctly_marked_as_exported():
    """The classifier's first version relied on _FIELD_SCHEMA/_FIELD_GLOSSARY
    as ground truth for 'is this on daily_list' and got it badly wrong: flow,
    energy, structure, mp, sc_momentum, on_longlist and gics_gate — the
    export's most fundamental fields — are in neither dict, so they all
    misclassified as unexported. Fixed by reading a live export's own keys
    as the real ground truth."""
    f = by_field()
    for field in ("flow", "energy", "structure", "mp", "sc_momentum",
                 "on_longlist", "gics_gate", "elder"):
        assert f[field]["ships_in_export"] == "daily_list", \
            f"{field} misclassified as {f[field]['ships_in_export']!r}"


def test_sc_position_and_its_engines_are_marked_as_never_exported():
    """A real finding, not a modelling choice: sc_position, bq, k39_gate,
    fip_quality, pipe_tier and momentum_composite are fully computed but
    absent from every one of 162 records in a live export. Different in
    kind from an ordinary calculation intermediate."""
    f = by_field()
    for field in ("sc_position", "bq", "k39_gate"):
        assert "NOT EXPORTED" in f[field]["ships_in_export"]


def test_a_reasonable_share_of_fields_are_pure_calculation_intermediates():
    """Roughly a fifth of everything this taxonomy documents never reaches
    the JSON at all — that's not a bug in the taxonomy, it's the honest
    shape of the calculation: an engine computes intermediates on the way
    to a score that DOES ship. Sanity bound so a classifier regression
    (e.g. everything reading as unexported) gets caught."""
    n = len(rows())
    not_exported = sum(1 for r in rows()
                       if "NOT EXPORTED" in r["ships_in_export"])
    assert 0.10 * n < not_exported < 0.35 * n, \
        f"{not_exported}/{n} marked unexported — outside the expected band"


def test_every_block_cites_its_real_calculator_not_build_export():
    """build_export only ASSEMBLES blocks other functions computed — citing
    it for regime/srm/macro_weather/etc. was the same defect as citing the
    glossary. Only fields build_export genuinely computes inline (simple
    literals/timestamps/aggregates) may still cite it."""
    f = by_field()
    delegated = {"regime": "ptrs.py", "srm": "srm.py",
                "macro_weather": "srm.py", "intermarket": "srm.py",
                "thematic_baskets": "srm.py", "held_book": "held_book.py",
                "data_quality": "_compute_data_quality",
                "lens_ranking": "lens_consensus.py"}
    for field, must_contain in delegated.items():
        assert must_contain in f[field]["source"], \
            f"{field} still points at the assembler, not its real calculator"


# ── the retirement ───────────────────────────────────────────────────────

def test_ptrs_is_absent_from_the_taxonomy():
    """It was SC_MOMENTUM under a second name. Retired 2026-08-13."""
    assert "ptrs" not in by_field()


def test_regenerating_is_deterministic():
    """The doc is generated, not maintained. Running it twice must not churn."""
    before = CSV_PATH.read_bytes()
    subprocess.run([sys.executable, "-m", "scripts.build_data_taxonomy"],
                   cwd=ROOT, check=True, capture_output=True)
    assert CSV_PATH.read_bytes() == before
