"""Tests for src/engines/lens_consensus.py — the lens-agreement reading aid
(2026-07-16 build order). Sort only: never cut, cap, filter, or eliminate.
No weighting, no invented thresholds — every verdict is either a label AQE
already computes or a top/bottom-third position in TODAY's list."""

from __future__ import annotations

from src.engines.lens_consensus import (
    LENSES, NONE, OK, STRONG, WARN,
    build_lens_ranking, compute_lens_consensus,
)


def _rec(ticker, ptrs=50.0, pipe_tier=None, pr_ret_12m=None, squeeze_score=None,
         accum_score=None, resist_score=None, premove_setup=False,
         structure_shift=None, div_state=None, gics_gate=None):
    return {
        "ticker": ticker, "ptrs": ptrs,
        "subcomponents": {
            "pipe": {"pipe_tier": pipe_tier, "pr_ret_12m": pr_ret_12m},
            "energy": {"squeeze_score": squeeze_score},
            "flow": {"accum_score": accum_score},
            "structure": {"resist_score": resist_score},
        },
        "premove_setup": premove_setup,
        "structure_shift": structure_shift,
        "div_state": div_state,
        "gics_gate": gics_gate,
    }


def _many(n, **kw):
    """n records with strictly increasing tercile-driving values, for terciles
    that need >=3 points to activate."""
    return [
        _rec(f"T{i}", pr_ret_12m=float(i), squeeze_score=float(i),
             accum_score=float(i), resist_score=float(i), **kw)
        for i in range(n)
    ]


def test_never_drops_or_adds_records():
    records = _many(10)
    before = len(records)
    compute_lens_consensus(records)
    assert len(records) == before


def test_mutation_only_adds_keys_existing_fields_untouched():
    rec = _rec("AAPL", ptrs=77.7, pipe_tier="A-TIER")
    original_keys = set(rec.keys())
    compute_lens_consensus([rec])
    assert original_keys <= set(rec.keys())
    assert rec["ptrs"] == 77.7  # untouched


def test_every_record_gets_lens_fields():
    records = _many(5)
    compute_lens_consensus(records)
    for r in records:
        assert "lens" in r and "lens_positive" in r and "lens_warnings" in r
        assert set(LENSES) <= set(r["lens"].keys()) | {"extension"}


def test_extension_is_always_null_and_never_counted():
    records = _many(5, structure_shift="BULLISH_BOS")
    compute_lens_consensus(records)
    for r in records:
        assert r["lens"]["extension"] is None
    assert "extension" not in LENSES


def test_missing_data_reads_dashes_never_strong():
    # Fewer than 3 records -> terciles can't form -> "--" everywhere data-driven.
    records = [_rec("A"), _rec("B")]
    compute_lens_consensus(records)
    for r in records:
        assert r["lens"]["leadership"] == NONE
        assert r["lens"]["coil"] == NONE
        assert r["lens"]["insti_money"] == NONE
        assert r["lens"]["resistance"] == NONE
        assert NONE in r["lens"].values()
        assert STRONG not in r["lens"].values()


def test_pipe_tier_a_tier_wins_leadership_outright():
    records = _many(10, pipe_tier="A-TIER")
    compute_lens_consensus(records)
    for r in records:
        assert r["lens"]["leadership"] == STRONG


def test_pipe_tier_d_skip_forces_warn_leadership():
    records = _many(10, pipe_tier="D-SKIP")
    compute_lens_consensus(records)
    for r in records:
        assert r["lens"]["leadership"] == WARN


def test_premove_setup_forces_strong_coil():
    records = _many(10, premove_setup=True)
    compute_lens_consensus(records)
    for r in records:
        assert r["lens"]["coil"] == STRONG


def test_structure_bullish_bos_with_bearish_divergence_is_ok_not_strong():
    rec = _rec("X", structure_shift="BULLISH_BOS", div_state="BEARISH")
    compute_lens_consensus([rec])
    assert rec["lens"]["structure"] == OK


def test_structure_bullish_bos_clean_is_strong():
    rec = _rec("X", structure_shift="BULLISH_BOS", div_state="BULLISH")
    compute_lens_consensus([rec])
    assert rec["lens"]["structure"] == STRONG


def test_structure_bearish_choch_is_always_warn():
    rec = _rec("X", structure_shift="BEARISH_CHOCH", div_state="BULLISH")
    compute_lens_consensus([rec])
    assert rec["lens"]["structure"] == WARN


def test_structure_no_shift_is_dashes():
    rec = _rec("X", structure_shift=None)
    compute_lens_consensus([rec])
    assert rec["lens"]["structure"] == NONE


def test_sector_gate_mapping():
    cases = {"PASS": STRONG, "BLOCKED": WARN, "CAUTION": WARN,
             "WATCH": OK, "CHECK": OK, "SOMETHING_ELSE": NONE, None: NONE}
    for gate, expected in cases.items():
        rec = _rec("X", gics_gate=gate)
        compute_lens_consensus([rec])
        assert rec["lens"]["sector"] == expected, gate


def test_lens_positive_and_warnings_counts():
    rec = _rec("X", pipe_tier="A-TIER", premove_setup=True,
                structure_shift="BULLISH_BOS", div_state="BULLISH", gics_gate="PASS")
    compute_lens_consensus([rec])
    # leadership, coil, structure, sector all STRONG by direct label; insti_money
    # and resistance fall to "--" (only 1 record, no terciles).
    assert rec["lens_positive"] == 4
    assert rec["lens_warnings"] == 0


def test_build_lens_ranking_sort_order_and_completeness():
    records = _many(6)
    compute_lens_consensus(records)
    ranking = build_lens_ranking(records)
    assert ranking["count"] == len(records)
    assert len(ranking["ranked"]) == len(records)
    # sorted by positive desc, warnings asc, ptrs desc
    positives = [r["positive"] for r in ranking["ranked"]]
    assert positives == sorted(positives, reverse=True)
    assert ranking["full_data_in"] == "daily_list"
    assert ranking["lens_set"] == list(LENSES)


def test_build_lens_ranking_never_filters():
    records = _many(20)
    compute_lens_consensus(records)
    ranking = build_lens_ranking(records)
    assert {r["ticker"] for r in ranking["ranked"]} == {r["ticker"] for r in records}


def test_empty_input_does_not_crash():
    assert compute_lens_consensus([]) == []
    ranking = build_lens_ranking([])
    assert ranking["count"] == 0
    assert ranking["ranked"] == []


def test_lens_glossary_merged_into_field_glossary():
    from src.data.drive_sync import _FIELD_GLOSSARY
    for key in ("lens_ranking", "lens", "lens_positive", "lens_warnings"):
        assert key in _FIELD_GLOSSARY
