# AQE Slim-Emit Spec — for the external AQE engine

**Audience:** the AQE engineer (repo `TongIncomeWheel/AQE`).
**Status:** requested change, handoff/08 Lane 4 (PM sign-off 2026-07-22).
**Scope:** the daily `aqe_daily_export.json` payload ONLY. No scoring/logic change — this is a
payload-diet + one real consumption-gap fix. The kernel side (trim + tightened contracts) is
already shipped; this document is the matching request to the emitter so the two meet.

Today's export: **142 daily_list records × 97 fields**, plus **~42 KB/day of self-describing
blocks with zero code readers**, plus `subcomponents: {}` (empty) though the voice cards point at
it. The kernel now persists only the **45-field consumed set** (see
`contracts/universe.schema.json` → `x_consumed_fields` and `tools/universe_build.py::CONSUMED`).

---

## 1. STOP emitting these 5 top-level blocks (bloat, ~42 KB/day, zero readers)

| Block | Why it can go |
|---|---|
| `field_schema` | duplicates repo docs (`AQE_FIELD_GLOSSARY.md`) |
| `field_schema_enums` | duplicates repo docs |
| `field_glossary` | duplicates repo docs |
| `thematic_baskets` (TOP-LEVEL) | duplicates `srm` / `srm_signals`; nothing reads the top-level copy |
| `data_quality` | diagnostic; not consumed downstream |

These are now **optional** in `contracts/aqe_export.schema.json` (v1.2.0) — removing them will NOT
break validation. `daily_list` + `lens_ranking` remain the required payload.

---

## 2. PRUNE these never-consumed `daily_list` fields (~30)

Neither code nor any voice card reads these; they are duplicates of other fields/blocks, or pure
diagnostics. Drop them from each record:

- **Per-row thematic/sector duplicates** (already in `srm`/`srm_signals`): `thematic_basket`,
  `thematic_baskets`, `thematic_grade`, `thematic_parent_gics`, `thematic_parent_grade`,
  `thematic_rrg_direction`, `thematic_rrg_quadrant`, `sector_rrg_direction`, `sector_rrg_quadrant`
  *(keep `sector_trend_state` — it is consumed).*
- **Provenance/diagnostic flags:** `floor`, `gics_gate`, `in_ledger`, `on_elder`, `on_longlist`,
  `pipe_rank`, `ptrs`, `fip_spike_excluded`, `fip_window_effective`, `malformed_bracket`,
  `lens_warnings`, `structure_shift_ref`, `knn_neighbors_used`.
- **Redundant raw/secondary values:** `beta_252d` *(keep `beta_30d`)*, `vol_30d_ann`,
  `mp_accel` *(keep `mp_accel_state`)*, `sc_p_gates` *(momentum, not position, is consumed)*.
- **Single-bar geometry not consumed:** `inside_bar`, `pib_pattern`, `pin_bar_date`,
  `pin_bar_level` *(keep `pin_bar_state`)*.
- **Divergence detail:** `div_bull_count`, `div_date`, `div_oscs`, `choch_date`
  *(keep `div_bear_count`, `div_state`, `choch_state`).*
- **Conviction labels:** `premove_conviction`, `premove_conviction_label`, `premove_setup`,
  `runner_conviction`, `runner_conviction_label` *(keep `runner_setup`).*

---

## 3. MOVE these into `subcomponents` (voice-card primaries, not on the code path)

These ARE read by voice methodology cards (`field_lens_taxonomy.md`) but not by kernel code, so
they belong inside `subcomponents` rather than as top-level record noise:

- `elder_context`, `exhaustion_check` (Steenbarger)
- `knn_tp1`, `knn_tp2`, `knn_tp3` (Thorp reads `rr_tp2`)
- the fib ladder: `fib_236`, `fib_382`, `fib_500`, `fib_618`, `fib_786`, `fib_swing_high`,
  `fib_swing_low` *(the operative levels already ride inside `bracket.targets`; move the raw ladder
  under `subcomponents` for the voices that want it, or drop if `bracket` suffices).*

---

## 4. POPULATE `subcomponents` (the one real consumption GAP)

`subcomponents` currently ships as `{}` / `null` on every row, but the voice taxonomy cards key off
sub-scores that appear **nowhere** in the export. This is the only change that ADDS information.
Emit, per `daily_list` record, the voice sub-scores the cards require:

```
subcomponents: {
  ext_score, accum_score, base_score, squeeze_score,   // Lynch/O'Neil/Wyckoff/Raschke/Minervini
  k39, trend_score, setup_state,                        // Collin Seow, Raschke
  atr_score, rs_accel,                                  // Raschke, Minervini
  pr_rsi_score, rel_mom_score, roc_zscore, rr_tp2,      // Thorp
  earn_score, en_pos50, excess_return, exhaustion_score, sector_entry_gate
}
```

(Card→field ownership is enumerated in `field_lens_taxonomy.md` → "Cross-field index".)

---

## 5. Field-NAME reconciliations (card name → live schema name)

The voice cards were written against names that drifted from the live export. Emit under the
**live** name (or add an alias) so the cards resolve:

| Card name | Live export name |
|---|---|
| `rs_vs_spy` | `rs_spy_20d` |
| `ext_score` / `accum_score` / `base_score` / `squeeze_score` | *(not emitted at all — supply via `subcomponents`, §4)* |
| `rr_tp2` | inside `bracket.rr_tp2` today — surface into `subcomponents` for Thorp |
| `sector_entry_gate` | lives in `srm[].entry_gate` — mirror into `subcomponents` per row |

---

## Net effect

Per-record ~97 → ~45 top-level fields + a populated `subcomponents`; ~42 KB/day of dead
self-describing blocks gone; the empty-`subcomponents` consumption gap closed. The kernel already
consumes exactly the 45-field set and validates the trimmed shape, so a slimmer export is a strict
improvement with no kernel change required.
