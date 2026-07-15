# PTRS Formula Changelog — Math Lab / Backtest Impact

**Trigger:** AIC Charter Amendment v2.8 (2026-07-15) — `CLAUDE_CODE_HANDOFF_PTRS_
Alignment_20260715.md`, Committee 9-0, PM-ratified. Origin: AIC deliberation on
`AQE_AIC_BRIEFING_2026-07-14.md`.

**Status:** fixed 2026-07-15. Full suite green with 2 new regression tests
pinning the exact bugs below.

---

## What the ruling required

Production PTRS = `SC_MOMENTUM` verbatim (Sector-Health term dropped, PM ruling
2026-07). `src/analyzer/ptrs.py` still documented/implemented the legacy
`SC_MOMENTUM + SH` formula in `compute_ptrs_batch()`, which the ticket flagged
as consumed by Math Lab backtesting.

## What was actually found (broader than the ticket named)

`compute_ptrs_batch()` has **zero call sites anywhere in the repository**
(confirmed by a full-repo grep) — it was never actually consumed by Math Lab or
anything else. It's fixed anyway (per the ticket's acceptance criteria), but it
was not the live contamination vector.

**The real, LIVE leak was three other call sites**, all still computing real
Sector-Health after the rest of the pipeline moved to `sh=0.0`:

| # | Location | Reach | Fixed |
|---|---|---|---|
| 1 | `src/pipeline/daily_orchestrator.py::_compute_ptrs_all` | **Live production.** Feeds `shortlist.json`'s `candidates[]` → `drive_sync.py` copies this verbatim into `export["top_picks"]`. Because the export's ticker-merge (`_merged`, in `drive_sync.py`) takes the FIRST-SEEN record per ticker across `(top_picks, edge_list, longlist, watchlist)` and does not overwrite `ptrs` on a later duplicate, any ticker whose first appearance was via `top_picks` kept a `+SH`-tainted PTRS all the way into the final `daily_list` — including the `PTRS>=60` check inside `longlist_screen.passes()`. | ✅ 2026-07-15 |
| 2 | `src/ui/1_Scanner.py::_quick_ptrs` | Live UI. Used by the Scanner's ad-hoc "score any ticker" feature — the PM could see a DIFFERENT PTRS for the same ticker/score than the daily_list showed. | ✅ 2026-07-15 |
| 3 | `src/ui/1_Scanner.py::_vectorized_ptrs` | Defined, unused (dead code like `compute_ptrs_batch`) — fixed for consistency/future-safety. | ✅ 2026-07-15 |

**Net: the AIC's core concern — "PTRS means two different things in different
parts of the app" — was correct, and worse than described: it wasn't confined
to Math Lab, it was live in the daily feed itself** for any ticker sourced from
`top_picks` in the merge. All four locations (the named one + these three) now
compute `PTRS = SC_MOMENTUM` verbatim, bit-for-bit, with no code path left that
can produce a nonzero SH.

## Historical data impact — the caveat the committee needs

**The signal ledger's persisted `ptrs` column (`data/aqe.db`,
`signal_snapshots` table) cannot be trusted as pure SC_MOMENTUM for any row
recorded before 2026-07-15.**

Why this can't be cleanly separated after the fact: `record_signals()` persists
whatever `ptrs` value was on that day's `daily_list` export row. Because the
export's ticker-merge doesn't retain WHICH of the four internal tiers
(`top_picks`/`edge_list`/`longlist`/`watchlist`) actually won for a given
ticker on a given day — only the final `longlist`/`elder_list` tag survives
into the ledger's `list_source` column — there is **no retained provenance**
that lets us distinguish a clean (`sc_momentum`-only) historical row from a
`+SH`-tainted one. Both are simply "ptrs: <number>" in the DB.

**Recommendation for any backtest/analysis using signal-ledger `ptrs` values
dated before 2026-07-15:** treat PTRS-based rankings, PTRS-threshold screens,
or PTRS-driven disposition bands from that period as **potentially mixed-
formula** and not a clean reproduction of the current live strategy. Engine
scores (`sc_mom`, `flow`, `energy`, `structure`, `mp`, `elder`, etc.) in the
same historical rows are UNAFFECTED — this caveat is scoped to the `ptrs`
column only.

**Going forward (2026-07-15 onward):** every `ptrs` value recorded anywhere —
live feed, ad-hoc scorer, signal ledger, any future Math Lab batch call — is
guaranteed `SC_MOMENTUM` verbatim, pinned by regression tests (see below).

## Regression tests added

`tests/test_smoke_endtoend.py`:
- `test_compute_ptrs_batch_matches_live_feed` — asserts `compute_ptrs_batch()`
  output equals `sc_momentum` verbatim even when fed a `sector_grades` dict
  with nonzero SH values (proves the parameter is inert).
- `test_orchestrator_ptrs_matches_live_feed` — asserts
  `daily_orchestrator._compute_ptrs_all()`'s output equals `sc_momentum`
  verbatim under the same adversarial `sector_grades` input. This is the
  regression pin for the actual live-leak bug (#1 above).

`src/ui/1_Scanner.py`'s `_quick_ptrs`/`_vectorized_ptrs` fixes are **not**
covered by an automated test: the module executes `st.set_page_config()` and
other Streamlit calls at import time, so it cannot be safely unit-imported
outside a full Streamlit script-run context, and there is no existing
precedent in this suite for testing it. Both were fixed by direct inspection,
using the identical pattern (`compute_ptrs(score, 0.0)`) as the two tested
fixes. Flagging this honestly rather than skipping it silently — if the
committee wants automated coverage here, it needs either an `AppTest`-based
UI test or refactoring these two helpers into a plain importable module.

## Out of scope (unchanged, per the ruling)

- No changes to any gate, screen, sizing input, or list membership *definition*
  (`sc_m_gates`, `sc_p_gates`, longlist thresholds, bracket gates). Fix #1 above
  changes an *input value* that feeds the existing, unchanged `PTRS>=60`
  longlist check — the gate itself is untouched; a wrong number feeding it is
  a data bug, not a policy change.
- No changes to the 7 builds shipped 2026-07-14.
- Bracket-engine skill rebuild remains a separate, PM-owned track.
