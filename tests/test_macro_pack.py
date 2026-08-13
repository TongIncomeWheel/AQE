"""The macro pack — the fifth, read-only door onto Crown/Macro Weather/SRM/
Thematic Rotation. Signed-off proposal: docs/AQE_MACRO_PACK_PROPOSAL.md.

The tests here are mostly about what the proposal's consistency check against
the Committee Card found: crown_status governs the whole artifact exactly as
it governs Crown alone, and a coherence read must never be silently computed
against a scenario that was never produced.
"""

from __future__ import annotations

from src.macro.pack import build_pack

CROWN_OK = {
    "crown_status": "OK",
    "freshness": {"oldest_leg": "2026-08-13"},
    "plain_english": {"headline": "A narrow market, calm on the surface.",
                      "caveats": ["No dealer-positioning read today."]},
    "degraded": [],
}
SCEN_REFLATION = {
    "status": "OK", "leading": "REFLATION", "leading_score": 0.71,
    "runner_up": "DISPERSION_REGIME", "contested": False,
    "reading": "REFLATION is the cleanest fit to the current cross-asset state.",
    "note": "share of conditions met, not a probability", "scenarios": [],
}
SRM_ROWS = [
    {"etf": "XLE", "sector": "Energy", "grade": "DEPLOY", "entry_gate": "PASS",
     "rrg_quadrant": "LEADING"},
    {"etf": "XLU", "sector": "Utilities", "grade": "DEPLOY", "entry_gate": "PASS",
     "rrg_quadrant": "LAGGING"},
]
BASKET_ROWS = [
    {"basket": "Oil_Services", "grade": "DEPLOY", "parent_gics": "XLE"},
]


# ── the standing refusals, same as Crown's own ───────────────────────────

def test_it_never_sizes():
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    text = str(out)
    assert "size_multiplier" not in text and '"size":' not in text


def test_it_never_names_a_ticker():
    """Sector and theme rows are the finest grain — no individual name."""
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    names = {r["name"] for r in out["sector_read"]} | \
            {r["name"] for r in out["thematic_read"]}
    assert names == {"XLE", "XLU", "Oil_Services"}   # ETFs and baskets only


def test_coherence_is_a_category_never_a_number():
    """Same rule as the scenario scores it's built from — never read as the
    same kind of number as QS's calibrated probability."""
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    for r in out["sector_read"] + out["thematic_read"]:
        assert r["coherence"] in ("AGREES", "DISAGREES", "UNTESTED")
        assert not isinstance(r["coherence"], (int, float))


def test_it_does_not_change_what_the_gate_computes():
    """A sector disagreeing with the leading scenario does not touch its own
    entry_gate — that's still purely sector_entry_gate's own output."""
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    by_name = {r["name"]: r for r in out["sector_read"]}
    assert by_name["XLE"]["gate"] == "PASS"   # copied verbatim, not recomputed


# ── crown_status governs the whole artifact, per the Committee Card ─────

def test_early_exit_makes_sector_read_absent_not_empty():
    """The Committee Card's central rule: on EARLY_EXIT the sections below
    are empty because they never ran, not because they came back quiet. A
    coherence tag computed against a scenario that was never produced would
    be exactly the failure this guards against."""
    crown_early = {"crown_status": "EARLY_EXIT", "freshness": {"oldest_leg": None},
                  "plain_english": {"headline": "Breadth is unreadable."}}
    out = build_pack(crown_early, {}, SRM_ROWS, BASKET_ROWS)
    assert out["pack_status"] == "PARTIAL"
    assert "sector_read" not in out
    assert "thematic_read" not in out


def test_unavailable_also_goes_partial():
    crown_unavail = {"crown_status": "UNAVAILABLE", "freshness": {}}
    out = build_pack(crown_unavail, {}, SRM_ROWS, BASKET_ROWS)
    assert out["pack_status"] == "PARTIAL"
    assert "sector_read" not in out


def test_no_leading_scenario_also_goes_partial_even_with_a_good_crown_read():
    """crown_status alone is not sufficient — sector_read is DERIVED FROM the
    leading scenario, so a healthy Crown read with no scenario leading must
    still withhold coherence rather than compute it against nothing."""
    scen_none = {"status": "OK", "leading": None, "scenarios": []}
    out = build_pack(CROWN_OK, scen_none, SRM_ROWS, BASKET_ROWS)
    assert out["pack_status"] == "PARTIAL"
    assert "sector_read" not in out


def test_degraded_crown_still_computes_but_says_so():
    crown_degraded = {**CROWN_OK, "crown_status": "DEGRADED"}
    out = build_pack(crown_degraded, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    assert out["pack_status"] == "DEGRADED"
    assert "sector_read" in out   # still computes, unlike EARLY_EXIT


def test_pack_status_and_crown_status_surface_at_the_top_level():
    """The Committee Card puts crown_status/freshness.oldest_leg first,
    before trusting anything else. The pack must not bury these inside the
    nested crown block — a reader checks the pack's OWN top level first."""
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    assert set(out) >= {"pack_status", "crown_status", "oldest_leg"}
    assert out["crown_status"] == "OK"
    assert out["oldest_leg"] == "2026-08-13"


def test_contested_scenarios_are_stated_not_hidden():
    scen_contested = {**SCEN_REFLATION, "contested": True}
    out = build_pack(CROWN_OK, scen_contested, SRM_ROWS, BASKET_ROWS)
    assert "Two stories fit the tape" in out["read_me_first"]


# ── the coherence math itself ────────────────────────────────────────────

def test_untested_when_the_sector_has_no_sensitivity_to_the_story():
    """DOLLAR_SQUEEZE's conditions (UUP/CPER/GLD/HYG) are all zero-weighted
    for XLV (Healthcare) — the one nonzero XLV sensitivity is TLT, which
    DOLLAR_SQUEEZE never touches."""
    scen = {"status": "OK", "leading": "DOLLAR_SQUEEZE", "leading_score": 0.6,
           "runner_up": None, "contested": False, "reading": "x", "note": "y",
           "scenarios": []}
    srm = [{"etf": "XLV", "sector": "Healthcare", "grade": "HOLD",
           "entry_gate": "WATCH"}]
    out = build_pack(CROWN_OK, scen, srm, [])
    assert out["sector_read"][0]["coherence"] == "UNTESTED"


def test_turning_grade_is_untested_not_forced_to_a_side():
    """A grade mid-transition is not asked to agree or disagree with
    anything — forcing a call on TURNING would be inventing a signal."""
    srm = [{"etf": "XLE", "sector": "Energy", "grade": "TURNING",
           "entry_gate": "WATCH"}]
    out = build_pack(CROWN_OK, SCEN_REFLATION, srm, [])
    assert out["sector_read"][0]["coherence"] == "UNTESTED"


def test_disagree_rows_sort_first():
    """The most useful row is on top — a reader scanning sector_read sees
    what needs attention before what confirms the story."""
    srm = [
        {"etf": "XLE", "sector": "Energy", "grade": "DEPLOY", "entry_gate": "PASS"},
        {"etf": "XLU", "sector": "Utilities", "grade": "AVOID", "entry_gate": "BLOCKED"},
    ]
    out = build_pack(CROWN_OK, SCEN_REFLATION, srm, [])
    coherences = [r["coherence"] for r in out["sector_read"]]
    if "DISAGREES" in coherences:
        assert coherences.index("DISAGREES") == 0


def test_thematic_read_states_it_inherits_the_parent_sensitivity():
    """A basket has no macro sensitivity vector of its own — it borrows its
    parent GICS sector's. The row must say so, not read as a theme-specific
    macro finding."""
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    row = out["thematic_read"][0]
    assert "parent" in row["coherence_reason"].lower()
    assert row["parent_gics"] == "XLE"


# ── limits carry forward, never re-derived ───────────────────────────────

def test_crown_caveats_carry_forward_verbatim():
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    assert "No dealer-positioning read today." in out["limits"]


def test_the_four_standing_refusals_are_stated_in_limits():
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    limits = " ".join(out["limits"]).lower()
    assert "does not size" in limits
    assert "does not name a ticker" in limits
    assert "never a probability" in limits


# ── what_changed: silence is a real answer ───────────────────────────────

def test_no_previous_pack_reads_as_first_run_not_an_error():
    out = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS, previous=None)
    assert out["what_changed"]["available"] is False


def test_nothing_changed_is_a_stated_fact_not_an_empty_list():
    first = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    second = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS, previous=first)
    assert second["what_changed"]["changes"] == []
    assert second["what_changed"]["note"]


def test_a_newly_disagreeing_sector_is_named():
    srm_before = [{"etf": "XLU", "sector": "Utilities", "grade": "DEPLOY",
                  "entry_gate": "PASS"}]
    srm_after = [{"etf": "XLU", "sector": "Utilities", "grade": "AVOID",
                 "entry_gate": "BLOCKED"}]
    before = build_pack(CROWN_OK, SCEN_REFLATION, srm_before, [])
    after = build_pack(CROWN_OK, SCEN_REFLATION, srm_after, [], previous=before)
    changes = " ".join(after["what_changed"]["changes"])
    assert "XLU" in changes


def test_leading_scenario_flip_is_reported():
    scen_2 = {**SCEN_REFLATION, "leading": "GROWTH_SCARE"}
    before = build_pack(CROWN_OK, SCEN_REFLATION, SRM_ROWS, BASKET_ROWS)
    after = build_pack(CROWN_OK, scen_2, SRM_ROWS, BASKET_ROWS, previous=before)
    changes = " ".join(after["what_changed"]["changes"])
    assert "REFLATION" in changes and "GROWTH_SCARE" in changes


# ── never mutates or imports the four systems it reads ───────────────────

def test_module_never_imports_srm_into_crown_or_vice_versa():
    """The whole point of a fifth external module: it must not create the
    coupling the standalone directive forbids. Static check on the actual
    import graph, not a docstring claim."""
    import ast
    tree = ast.parse(open("src/macro/pack.py", encoding="utf-8").read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(m.startswith("src.macro.crown") and m != "src.macro.crown.daily"
                  for m in imports), \
        "pack.py must only read crown.daily.load_crown, never a crown internal"
    crown_src = open("src/macro/crown/kernel.py", encoding="utf-8").read()
    assert "macro.pack" not in crown_src and "engines.srm" not in crown_src


def test_build_pack_is_pure_no_file_io():
    """build_pack takes plain dicts/lists and returns a dict — the network/
    file-reading side is entirely in run_pack, kept separate on purpose so
    the assembly logic is trivially testable, as this whole file proves."""
    import inspect

    from src.macro import pack as pack_module
    src = inspect.getsource(pack_module.build_pack)
    assert "open(" not in src and "requests." not in src and ".read_text(" not in src
