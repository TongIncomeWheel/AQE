"""Report C input guard: value-level check on the export's `subcomponents` block (PM 2026-11-05)."""
from src.data.drive_sync import _subcomponents_status

GOOD = {"flow": {"flow_score": 17.0, "mfi": None}, "mp": {"adx_val": 31.0}}
NULLS = {"flow": {"flow_score": None}, "mp": {"adx_val": None}}


def test_live_when_every_row_has_values():
    r = _subcomponents_status([{"ticker": "A", "subcomponents": GOOD}, {"ticker": "B", "subcomponents": GOOD}])
    assert r["status"] == "live" and r["rows"] == 2


def test_degraded_names_the_rows_that_are_empty_or_missing():
    r = _subcomponents_status([{"ticker": "A", "subcomponents": GOOD}, {"ticker": "B", "subcomponents": NULLS},
                               {"ticker": "C", "subcomponents": None}])
    assert r["status"] == "degraded" and r["missing"] == 1 and r["all_null"] == 1
    assert r["tickers"] == ["B", "C"] and "2 of 3" in r["reason"]


def test_error_when_nothing_is_usable_and_never_raises():
    assert _subcomponents_status([{"ticker": "A", "subcomponents": NULLS}])["status"] == "error"
    assert _subcomponents_status([])["status"] == "error"
    assert _subcomponents_status([None])["status"] == "error"


def test_a_key_check_alone_would_have_passed_the_all_null_block():
    assert _subcomponents_status([{"ticker": "A", "subcomponents": NULLS}])["status"] != "live"


def test_rows_built_on_the_recipe_path_are_filled_from_the_scores_row_and_the_rest_stay_loud():
    from src.data import drive_sync as ds
    wr = {"ticker": "NDAQ", "flow_100": 90.0, "energy_100": 70.0, "structure_100": 80.0, "mp_100": 85.0, "elder_score": 8.0,
          "bq_100": 70.0, "k39_gate": True, "mfi": 60.0}
    rows = [{"ticker": "NDAQ", "subcomponents": None, "sc_m_gate_detail": None, "sc_p_gate_detail": None, "sc_m_gates": None, "sc_p_gates": None},
            {"ticker": "OK", "subcomponents": GOOD, "sc_m_gate_detail": {"flow": True}, "sc_p_gate_detail": {"flow": True}},
            {"ticker": "GONE", "subcomponents": None, "sc_m_gate_detail": None, "sc_p_gate_detail": None}]
    out = ds._fill_aqe_blocks(rows, {"NDAQ": wr})
    assert out["filled"] == 1 and out["absent"] == ["GONE"]
    assert isinstance(rows[0]["subcomponents"], dict) and set(rows[0]["subcomponents"]) >= {"flow", "energy", "structure", "mp", "bq", "pipe"}
    assert rows[0]["sc_m_gate_detail"] is not None and rows[0]["sc_m_gates"] in (True, False)
    assert rows[1]["subcomponents"] is GOOD, "a row that already has the block is never touched"
    st = ds._subcomponents_status(rows)
    assert st["status"] in ("degraded", "error") and "GONE" in st.get("tickers", [])


def test_the_filler_never_raises():
    from src.data import drive_sync as ds
    assert "filled" in ds._fill_aqe_blocks([None, {"ticker": None}], {})
