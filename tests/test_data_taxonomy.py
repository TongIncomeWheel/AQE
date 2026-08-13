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
           "source", "formula", "weight"]


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
