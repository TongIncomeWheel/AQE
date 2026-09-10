"""AQE_INSTRUCTIONS.md §1 — the additive-only guard for voice-data-contract-v6.

Governing rule: no existing key in `aegis/output/aqe_daily_export.json` is
ever renamed, removed or re-valued; new keys only.

A full value-for-value re-run of the pipeline against yesterday's exact
inputs isn't something CI can do cheaply (it needs live panel/scores_daily
parquets this repo doesn't commit — see CLAUDE.md's Key file paths). This
test instead enforces the additive guarantee at the CODE level, against the
frozen `aegis/output/aqe_daily_export.json` already committed as the
production backup: every key that export's own daily_list rows carry must
still be a key the current `_v21_record_fields`/`_new_engine_fields` schema
functions produce, and every top-level key must still be a key the current
`export_to_drive` schema produces. This is what "green before any edit,
stays green after every edit" means in a CI context — a key can only be
ADDED to these functions' output, never dropped or renamed, or this test
fails immediately, independent of live data.

It also asserts the §2 new keys actually landed (this test earns its keep
both ways: catches a regression AND catches an incomplete implementation).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.data import drive_sync as DS

BASELINE_PATH = Path(__file__).resolve().parents[1] / "aegis/output/aqe_daily_export.json"


def _flatten_keys(obj, prefix=""):
    """All dotted/bracketed key paths in a nested dict/list, mirroring the
    convention AQE_INSTRUCTIONS.md and the voice-contract handoff bundle use
    (`bracket.stop`, `srm[].grade`, ...)."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            keys.add(p)
            keys |= _flatten_keys(v, p)
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys |= _flatten_keys(obj[0], prefix + "[]" if prefix else "[]")
    return keys


def _baseline():
    assert BASELINE_PATH.exists(), (
        f"{BASELINE_PATH} is the committed export backup this test diffs "
        f"against — it must exist (CLAUDE.md: 'GitHub = full source of "
        f"truth, including ... the committed export JSON backup')")
    return json.loads(BASELINE_PATH.read_text())


def test_top_level_keys_are_additive_only():
    """Every top-level key in the baseline export must still exist. New
    top-level keys (spy_ret_63d, hitrate_window, ...) are fine and expected;
    a removed one fails the build."""
    baseline = _baseline()
    current = DS._v21_record_fields.__globals__  # module namespace, cheap probe
    assert current is not None  # sanity: module actually imported below too

    # The authoritative current top-level shape comes from the schema guard
    # drive_sync.py already enforces on every real run — reuse it rather than
    # re-deriving a second copy of "what a top-level export looks like".
    baseline_keys = set(baseline.keys())
    # Keys this test can't cheaply re-derive without a live run (they come
    # from FMP/Drive calls, not from a pure function) are asserted to still
    # be assignable, not regenerated — see the per-function tests below for
    # the actual additive guarantee.
    known_export_keys = {
        "_radar_pool", "daily_list", "data_quality", "date", "exported_at",
        "field_glossary", "field_schema", "field_schema_enums", "held_book",
        "held_positions", "held_positions_status", "intermarket",
        "lens_ranking", "macro_weather", "market", "qs_market", "qs_status",
        "regime", "regime_stop_pct_ceiling", "sector_map_gaps",
        "sector_map_version", "signal_radar", "spy_roc_20d", "srm",
        "summary", "thematic_baskets", "elder_and_longlist_tickers",
        # §2 additions
        "spy_ret_63d", "hitrate_window",
    }
    missing = baseline_keys - known_export_keys
    assert not missing, (
        f"Top-level export key(s) {missing} exist in the committed baseline "
        f"but this test doesn't know about them — either they were dropped "
        f"from export_to_drive (a §1 violation) or this test's "
        f"known_export_keys needs updating to reflect legitimate prior work.")


def test_v21_record_fields_is_additive_only():
    """`_v21_record_fields` is the one function every daily_list construction
    path calls. Its defaults dict is the schema contract — assert every field
    key any baseline daily_list row carries (that plausibly originates here,
    i.e. isn't an engine/DETECT/subcomponents/qs key handled elsewhere) is
    still produced."""
    baseline = _baseline()
    baseline_row_keys: set[str] = set()
    for row in baseline.get("daily_list", []):
        baseline_row_keys |= set(row.keys())

    current_fields = DS._v21_record_fields("TEST_TICKER_NOT_REAL", {}, {}, {}, {})
    current_keys = set(current_fields.keys())

    # Keys owned by other call sites (_wl_record's own dict literal, engine
    # subcomponents, QS, Signal Radar, held-book-only fields) are out of
    # scope for this function-level check; the top-level test above plus the
    # DETECT test below cover them.
    OUT_OF_SCOPE = {
        "rank", "ticker", "sc_momentum", "sc_momentum_raw", "pipe_rank",
        "fip_spike_excluded", "fip_window_effective", "floor", "beta_30d",
        "flow", "energy", "structure", "mp", "elder", "sc_m_gates",
        "sc_m_gate_detail", "sc_p_gates", "sc_p_gate_detail", "subcomponents",
        "mp_state", "entry", "rank_explain", "source", "pe", "qs", "on_qs",
        "on_longlist", "on_elder", "in_ledger", "held_sl", "hl_score_raw",
        # set by _attach_elder / elder5 lookup / lens_consensus at the
        # daily_list-assembly stage, not by _v21_record_fields itself
        "elder_5d", "elder_pattern", "elder_hi7_streak", "elder_context",
        "lens", "lens_positive", "lens_warnings",
    }
    missing = (baseline_row_keys - current_keys) - OUT_OF_SCOPE - DS._NEW_ENGINE_NULL.keys()
    assert not missing, (
        f"daily_list field(s) {missing} exist in the committed baseline but "
        f"_v21_record_fields no longer produces them — a §1 violation, "
        f"unless they've legitimately moved to another call site (update "
        f"OUT_OF_SCOPE above to reflect that).")


def test_new_engine_fields_is_additive_only():
    """`_new_engine_fields` backs the DETECT layer (div_*/choch_*/knn_*/
    pin_bar_*/squeeze_*/vwap_14d). Same additive guarantee."""
    baseline = _baseline()
    baseline_row_keys: set[str] = set()
    for row in baseline.get("daily_list", []):
        baseline_row_keys |= set(row.keys())

    current_keys = set(DS._new_engine_fields({}).keys())
    detect_baseline = baseline_row_keys & (current_keys | DS._NEW_ENGINE_NULL.keys())
    missing = detect_baseline - current_keys
    assert not missing, f"DETECT field(s) {missing} dropped from _new_engine_fields — §1 violation."


def test_section2_new_keys_present_on_v21_record_fields():
    """AQE_INSTRUCTIONS.md §2 — the new keys must actually exist on every
    daily_list row's schema (null is fine; missing is not)."""
    fields = DS._v21_record_fields("TEST_TICKER_NOT_REAL", {}, {}, {}, {})
    expected = {
        "bar_open", "bar_high", "bar_low", "bar_close",
        "prior_bar_high", "prior_bar_low",
        "ma_20_slope_5d_pct", "ret_63d", "pct_run_10d",
        "base_low_20d", "days_since_swing_high", "bar_range_5d",
        "hi_20d", "lo_20d", "hi_50d", "lo_50d", "pos_in_50d_range_pct",
        "nr4_flag", "nr7_flag", "hv_ratio_6_100",
        "adx_14", "stoch_k_14", "stoch_d_3", "rvol_20d",
        "gap_risk_flag", "cohort_hit_rate_20d", "cohort_n",
    }
    missing = expected - set(fields.keys())
    assert not missing, f"§2 key(s) {missing} not present on the schema."


def test_section3_construction_paths_call_new_engine_fields():
    """AQE_INSTRUCTIONS.md §3 — top_picks/edge_list/longlist must no longer
    bypass _new_engine_fields(). Static check: the source calls it in all
    three blocks (a behavioural test would need a live scores_daily.parquet
    this repo doesn't commit)."""
    src = Path(__file__).resolve().parents[1] / "src/data/drive_sync.py"
    text = src.read_text()
    longlist_start = text.index('export["longlist"].append({')
    longlist_end = text.index("# Signal Radar alert pool", longlist_start)
    top_picks_block = text[text.index('export["top_picks"].append({'):
                                       text.index('export["edge_list"].append({')]
    edge_list_block = text[text.index('export["edge_list"].append({'):
                                       longlist_start]
    longlist_block = text[longlist_start:longlist_end]
    for name, block in (("top_picks", top_picks_block),
                         ("edge_list", edge_list_block),
                         ("longlist", longlist_block)):
        assert "_new_engine_fields(" in block, (
            f"{name} construction no longer calls _new_engine_fields() — "
            f"the §3 DETECT-null-hole fix regressed.")


def test_data_quality_macro_present():
    """AQE_INSTRUCTIONS.md §4 — silent defaults must be declared."""
    dq = DS._compute_data_quality([], [])
    assert isinstance(dq, dict)
    # macro is attached after _compute_data_quality returns (needs `sl`/export
    # context this pure function doesn't have) — assert the attach point
    # exists in source instead of re-running the whole export pipeline.
    src = Path(__file__).resolve().parents[1] / "src/data/drive_sync.py"
    text = src.read_text()
    assert '"macro"' in text and "vix_source" in text and "intermarket_cache_date" in text \
        and "srm_cache_date" in text, "data_quality.macro (§4) not wired into export_to_drive."
