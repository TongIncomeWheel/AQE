# S2 — MARKET FRAME (deterministic)

**Job.** Answer "what kind of day is this?" by distilling the GLOBAL blocks of both inputs
into one small JSON every later stage (and every voice packet) can carry. Pure mapping — no
model judgment, no thresholds invented here.

**Reads.** From the export: `regime.*` (vix, hurst, trend, level, implication),
`intermarket.*` (uup/tlt/hyg/spy_iwm), `macro_weather.*`, `srm[]` (grade, rrg_quadrant,
macro_headwind_flag, entry_gate per sector), `thematic_baskets.*`, `summary`, `data_quality`.
From the crown file: `read_me_first` (verbatim), `the_call` (expression_family,
match_quality, size_multiplier, conditions_met/not_met), `readings.*` summary values,
`key_levels[]` (nearest 8 by |distance_pct|), `status` + `limits[]`.

**Output.** `data/pma/DATE/market_frame.json` (contract: `contracts/pma/market_frame.schema.json`):

- `risk_tone`: GREEN/AMBER/RED — direct copy of `regime.level`, never recomputed
- `momentum_caveat`: the hurst/trend implication in one plain sentence (a MEAN_REVERT tape is
  a caveat on every momentum idea downstream, said once here so every stage inherits it)
- `crown`: {present, status, headline, family, size_multiplier, conditions_not_met[], key_levels_near[]}
- `sectors`: per-ETF {grade, quadrant, headwind, entry_gate} — the rotation map
- `cross_asset`: the dollar/bonds/credit/breadth one-liners with their numbers
- `declared_gaps[]`: anything absent or degraded, named

**Rule.** Every value carries its source path (`regime.vix`, `readings.volatility.gap`, …).
A number without provenance does not enter the frame.
