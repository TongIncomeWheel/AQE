# AQE Data Integrity Findings — 2026-08-13

What this is: the completeness and integrity audit requested alongside the
data taxonomy. Every claim below traces to a `file:line` citation, gathered by
direct code read (not inference) across two passes — one by hand, one by an
independent research agent working from the same brief, so the two could
disagree and be checked against each other.

Companion to `docs/AQE_DATA_TAXONOMY.csv`. Regenerate the CSV with
`python -m scripts.build_data_taxonomy`; this document is a snapshot of what
that pass found and fixed, plus what it found and could not fix in the same
sitting.

---

## 1 · Sourcing — the headline fix

Before this pass, **101 of 254 taxonomy rows** cited their source as
`src/data/drive_sync.py:_FIELD_GLOSSARY` — the export's own self-description
dict, which describes fields in prose. Citing it as a field's *source* was
citing documentation as evidence: the glossary doesn't compute anything, it
describes what something else computed.

After this pass, **3 rows** remain sourced that way — `role`, `side`, `unit`,
which are not data fields at all but the schema's own controlled vocabulary,
and are exempted deliberately. Every other field now cites the real
calculator (a `src/engines/*.py` or `src/data/*.py` line that computes it) or
an explicit external source: **EXTERNAL: FMP quote endpoint**, **EXTERNAL: PTJ
trade journal**. `test_almost_nothing_still_cites_the_glossary_as_its_source`
pins this so it can't quietly regress.

The generator (`scripts/build_data_taxonomy.py`) now prints any field it still
can't source to stderr on every run, rather than letting a newly-added export
field silently fall back to the glossary and look sourced when it isn't.

## 2 · Two naming corrections, found while tracing real sources

Tracing what QS's own `LENSES` dict (`qs_spec.py:31-37`) actually reads turned
up two fields this taxonomy had under the wrong name — not a QS bug, a
taxonomy bug:

- **`ms_pos`** → **`ms_pos_score`**. `structure.py`'s own DataFrame column
  (`structure.py:235`) is `ms_pos_score`; the shorter name was invented for
  this taxonomy and never checked against the export.
- **`ret_score`** → **`ret_12m_score`**. `pipeline_rank.py`'s local Python
  variable is named `ret_score`, but the column it's stored under —
  `pipeline_rank.py:246`, and the name `score_runner.py:291` merges it under
  (`pr_ret_12m`) — is `ret_12m_score`. The taxonomy had copied the local
  variable name rather than the actual column.

`test_structure_field_names_match_the_engines_own_columns` and
`test_pipeline_rank_field_names_match_the_engines_own_columns` pin both.

## 3 · One wrong claim, corrected

The taxonomy previously stated that MP's ADX/DMI (`mp.py:139-158`) and
Pipeline Rank's own ADX/DMI (`pipeline_rank.py:254-273`) were "a separate
implementation... not the same series." Direct side-by-side comparison shows
they reduce to the **same Wilder ADX/DMI construction** at the same `n=14`
window — different code (a boolean-mask multiply vs `np.where`, and a
different point in the pipeline where `fillna(0.0)` is applied, which can only
matter in the NaN warmup window), same formula. This is corrected in both
`adx_val`'s and `pr_adx_score`'s rows. It is now filed under §5 as a
duplicate, not a distinct calculation.

## 4 · One citation error, corrected

`on_elder` was cited to `longlist_screen.py`. That file contains no
`on_elder` logic — `passes()` is the only function in it, and it implements
the longlist rule, not the standalone Elder list. The real check is
`(elder or 0) >= 8`, inline at `src/data/drive_sync.py:1964`. Fixed, and
`test_the_longlist_rule_matches_the_screen` / the `on_elder` row now cite the
real location.

## 5 · Duplicate computations — the same formula, independently maintained

Confirmed by direct read, not inferred from similar-sounding names. Each pair
computes the *identical* arithmetic; only the downstream step-score bands
differ, so the numbers a reader sees look different even though the
underlying quantity is the same value computed twice (or four times).

| Quantity | Where #1 | Where #2 (and #3, #4) |
|---|---|---|
| Close position in the 50-bar high/low range | `en_pos50`, `energy.py:39-46` | `ms_p50` (feeds `ms_pos_score`), `structure.py:181-186` |
| ADX/DMI, Wilder construction, n=14 | `adx_val`, `mp.py:139-158` | `pr_adx_score`'s input, `pipeline_rank.py:254-273` |
| 5-bar "higher-low staircase" count | `stair_hl_count`, `structure.py:74-79` (feeds `mode2_staircase`) | `bq.py:67-68` (feeds `mode2_staircase`, plus an extra AND-gate) |
| ATR(5)/ATR(20) tightness ratio | `rt_ratio`, `bq.py:36` (feeds `bq_range_tight`) | `readiness.py:48` (feeds `rd_compression`) |
| SMA(5)/SMA(20) volume ratio | `vtr`, `flow.py:126-127` | `bq.py:46-48`, `pipeline_rank.py:126-128`, `readiness.py:81-83` — **four** places |
| EMA(8/13/21) spread / ATR(20) | `norm_spread`, `bq.py:128-138` (feeds `bq_ema_conv`) | `readiness.py:92-98` (feeds `rd_compression`) |
| Bollinger-inside-Keltner squeeze + bandwidth percentile | `bwp`/`sq`, `energy.py:103-115` (feeds `squeeze_score`) | `readiness.py:58-70` |
| Inside-bar test (`high<high[1] AND low>low[1]`) | `inside_bar`, `pin_bar.py:119-121` (single flag) | `readiness.py:107` (same test, rolled over 5 bars) |
| 20-day RS vs SPY | `excess_return`, `mp.py:64-68` | `health.py:136-142` (`hl_rs` sub-score C1) — Health never reads MP's output; independently derived |
| RS acceleration (20d RS − 60d RS) | `rs_accel`, `structure.py:52-55` | `health.py:144-150` (`hl_rs` sub-score C2) — same shape, independently derived |

`readiness.py` (the Readiness engine — `rd_*` fields, excluded from the daily
export by PM ruling but still computed for every ticker and still read by
QS) accounts for five of these on its own. Its own docstring
(`readiness.py:5-8`) frames this as deliberate reuse of "the ONLY
subcomponents with positive TP1 spread" from BQ — a design choice, not an
accident — but it is still five formulas independently maintained in a second
file, with real drift risk: nothing forces the two copies to change together
if one is edited.

**Not flagged as duplicates** — confirmed genuinely distinct despite similar
names: `qs_fields.py`'s `trend_200`/`vol_60` are benchmarked against QS's own
equal-weight eligible-universe index, explicitly not SPY
(`qs_fields.py:18-23`) — no overlap with any SPY-relative calc elsewhere. The
higher-lows-count family (`energy.py` 4-bar, `structure.py` 5-bar
`stair_hl_count`, `structure.py`'s variable-lookback `hl_in_base`,
`health.py`'s proper 10-bar rolling sum) share an idea but use different
windows and, in `hl_in_base`'s case, a different loop structure — a family
worth a consolidation conversation, not four copies of one bug.

## 6 · QS reads fields with zero visibility in the export

QS's recipes and vetoes (`data/qs/recipe_book.json`, read by
`qs_engine.count_recipe_hits` / `evaluate_vetoes`) depend on three families of
fields that **never reach `daily_list` for a non-held ticker**:

- `hl_score`, `hl_flow`, `hl_higher_lows`, `hl_trend_bars`, `hl_vol_updn` —
  computed for every scored ticker (`score_runner.py:137,308-316`) but
  exported only on `held_positions`.
- `rd_compression`, `rd_pos_mod` — the Readiness engine's own sub-scores
  (`score_runner.py:136,299-301`). Readiness is explicitly excluded from the
  feed by PM ruling (`drive_sync.py:88-90`: *"Readiness ... is intentionally
  NOT in this feed"*).
- `k39_value` — computed (`score_runner.py:228`) but not exported to
  `daily_list`.

None of this is a bug in QS — QS reads `scores_daily.parquet` directly, not
the export. But it means **an auditor working from the export JSON alone
cannot see three of QS's own input families**, for any name QS scored that
isn't also in the held book. Worth knowing before trusting an export-only
audit of what QS is actually reading.

## 7 · Malformed keys in the export's own glossary

`_FIELD_GLOSSARY` carries three keys that document several real fields under
one slash-joined pseudo-name instead of one entry per field:

- `"fib_236/382/500/618/786"` — five real fields, one glossary entry
- `"ma_20/50/100/200"` — four real fields, one glossary entry
- `"fib_swing_low/high"` — two real fields, one glossary entry

Iterating that dict's keys naively (as the taxonomy generator used to)
promotes each combined string into its own fake taxonomy row — three garbage
fields whose "name" is not a name. `MALFORMED_GLOSSARY_KEYS` in the generator
now excludes them explicitly, and each real field they were describing has
its own row with its own real formula (`test_malformed_glossary_keys_never_
become_rows`, `test_the_dropped_malformed_keys_real_fields_still_have_
their_own_rows`).

The `_FIELD_GLOSSARY` dict itself still carries these malformed keys — this
document flags it as a source-side defect worth fixing when that dict is
retired in favour of the taxonomy, per the standing plan for it.

## 8 · True gaps — export fields with no taxonomy row at all

Different in kind from a mis-sourced field: these have **zero documentation
anywhere**, not just a blank formula. Cross-referencing a live export's
`daily_list[0]`, `held_positions[0]`, `srm[0]`, one `thematic_baskets[]`
entry, and `lens_ranking`'s own keys against every taxonomy field name found
44 with no row. This pass closed the ones with the clearest, cheapest real
source (`grade` and its direct inputs — `above_sma20`, `roc20`, `roc5`,
`divergence`, `grade_path`, `sh_value`, `grade_trend`, `etf`, `sector`,
`entry_gate_reason` — plus `ticker`). **Still open:**

- **`srm[]`'s own remaining raw fields**: `macro_headwind_flag`,
  `macro_headwind_score`, `rrg_grade_override`, `sh_trend` — the per-ticker
  *projections* of related values are documented (`sector_trend_state`,
  `sector_rrg_*`), the sector-list's own raw copies mostly are not yet.
- **`thematic_baskets[]`'s own raw fields**: `constituents_used`, `coverage`,
  `raw_grade` — same pattern as `srm[]`, the per-ticker projection
  (`thematic_grade` etc.) is documented, the basket object's own field
  isn't yet.
- **`lens_ranking`'s 7 meta keys**: `count`, `extension_note`, `full_data_in`,
  `lens_set`, `method`, `ranked`, `reading_aid_not_a_prediction` — all
  defined inline at `lens_consensus.py:134-154`; cheap to add, not yet done.
- **`held_positions`-only journal fields**: `cob_price`, `exposure`, `notes`,
  `position_type`, `ptj_sector`, `ptj_srm_grade`, `qty`, `trade_date` — pass
  straight through from the PTJ broker journal (external), arguably out of
  scope for a *calculation* taxonomy, but currently undocumented either way.
- **`rvol`, `ptrs`** — both keys appear in the specific 2026-07-28 sample
  export used for this audit, and neither has a row. `rvol` was renamed to
  `day_vol` on 2026-08-05 (which **does** have a row); `ptrs` was retired
  2026-08-13. Both are consistent with the glossary's own stated timeline —
  a same-day export rebuilt today would very plausibly show neither key at
  all, so this reads as a stale-sample artifact, not a fresh gap.

Only **3 fields are formally marked undocumented by AQE's own code** —
`floor`, `fip_spike_excluded`, `fip_window_effective` carry the literal string
`"UNDOCUMENTED — AQE owner to define"` in
`agentic_dictionary.GLOSSARY_FILL`/`UNDOCUMENTED` (`agentic_dictionary.py:100-
102,115`). This pass gave `floor` and `fip_spike_excluded`/
`fip_window_effective` real, verified formulas anyway (`min(flow, energy,
structure, mp)`; the DSG-20 prior-spike-exclusion mechanism in
`pipeline_rank.py:187-207`) — the code was never actually undefined, only the
glossary *text* was never written.

## 9 · What this pass did not attempt

- Full geometric derivation of all 13 candlestick patterns
  (`engines/candles.py`) or all 6 chart-pattern detectors
  (`engines/patterns.py`) — each field has a real enum, a real source
  citation and a proportionate formula (the classifier's mechanism and its
  named constants), not a line-by-line transcription of every shape test.
  Matches the depth already given to `elder_pattern`'s 5-branch rule and
  `pipe_tier`'s ladder.
- Full modelling of QS's calibration-table lookup
  (`data/qs/calibration.json`) — it is a frozen historical look-alike table,
  not a closed-form formula, and is documented as exactly that rather than
  invented as one.
- Closing all 44 true gaps from §8 — the highest-value ones (sector grade and
  its inputs) are closed; the rest are named above rather than left silent.
- Consolidating any of the §5 duplicates — that is an engineering decision
  for the PM, not something a documentation pass should do unasked.
