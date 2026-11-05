"""Report C glossary: every composite and every export sub-component has a plain entry; footnotes resolve; no formulas in the body."""
import importlib.util, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "aegis/plugin/aegis-core/skills/pma/tools/aqe_glossary.py")
spec = importlib.util.spec_from_file_location("aqe_glossary", TOOL)
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def test_every_export_subcomponent_has_an_entry():
    from src.data.drive_sync import _SUBCOMPONENT_SPEC
    _comp, subs = G.all_fields()
    for eng, cols in _SUBCOMPONENT_SPEC.items():
        assert eng in subs, f"engine {eng} has no glossary section"
        assert set(cols) == set(subs[eng]), (eng, set(cols) ^ set(subs[eng]))


def test_every_composite_the_seat_is_served_has_an_entry():
    comp, _subs = G.all_fields()
    d = json.load(open(os.path.join(ROOT, "tests/fixtures/cards_v3/aqe_daily_export.json")))
    row = d["daily_list"][0]
    for f in ("sc_momentum", "sc_m_gates", "sc_m_gate_detail", "sc_p_gates", "sc_p_gate_detail", "pipe_rank",
              "flow", "energy", "structure", "mp", "elder", "mp_state"):
        assert f in comp, f"{f} missing from the glossary"
        assert f in row or f in ("mp_state",), f"{f} is not an export field any more"


def test_footnotes_point_at_real_headings_in_the_reference_doc():
    doc = open(os.path.join(ROOT, "docs/AQE_TECHNICAL_REFERENCE.md")).read()
    heads = [ln.lstrip("#").strip() for ln in doc.splitlines() if ln.startswith("#")]
    for key, h in G.REF_HEADINGS.items():
        assert any(x.startswith(h) for x in heads), f"{key}: no heading starting {h!r} in the reference doc"
    for _f, *_rest, ref in G.COMPOSITES:
        assert ref in G.REF_HEADINGS


def test_body_is_words_not_formulas():
    body = G.render().split("\n---\n")[0]
    for bad in ("=", "×", "Σ", "≥", "≤", "sqrt", "linreg", "ewm"):
        assert bad not in body, f"formula character {bad!r} in the glossary body"
    for line in body.splitlines():
        if line.startswith("- `"):
            assert re.search(r"Measures .+ Range: .+ High: .+ Low: ", line), line


def test_it_is_one_page_and_the_file_on_disk_is_current():
    text = G.render()
    assert len(text.splitlines()) <= 130
    assert open(G.OUT).read() == text, "stale: run python3 aegis/plugin/aegis-core/skills/pma/tools/aqe_glossary.py"
