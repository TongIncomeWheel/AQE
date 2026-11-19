# AQE component-score backtest, 2026-11-19 (handoff to the Backtest and Scoring Review session)

Result: no stable edge in any of the 77 allowed component/sub-component columns (5/10/20d vs SPY and equal-weight universe).
Tables: tables/. Scripts: scripts/ (prep.py builds the panel from the extract; lib.py loads it; ic_screen.py, buckets.py, recipe.py, bull_check.py, exposures.py, null_only.py).
Large intermediates (_panel.parquet etc.) are NOT here; rebuild them with prep.py from the extract.

DATA: aqe_research_extract_2026-11-19.parquet (2,138,382 rows, 1,618 tickers, 2021-03-15 to 2026-11-18). Drive file id 1uzQ_MEhAFBmkO8KBvxzXVswxS1EC4ZAd in the pinned AQE Drive folder; also GitHub Actions artifact 14487921610 (run 44434357359), download with `gh api repos/TongIncomeWheel/AQE/actions/artifacts/14487921610/zip > ext.zip`. extract_meta.json lists column groups, forward-return definitions and every not-point-in-time label (survivorship: today's 1,618 names applied backwards; sector = current map; market cap not provided).

GLOSSARY (all in the repo): docs/AQE_DATA_TAXONOMY.csv (392 rows: field, parent, level, represents, source file:line, formula, weight, used_by); docs/AQE_TECHNICAL_REFERENCE.md (every formula cited to source); aegis/plugin/aegis-core/skills/pma/contracts/aqe_glossary.md; the `field_glossary` block inside aqe_daily_export.json.

METHOD USED: per-date cross-sectional rank-IC vs forward excess return, raw and neutralised for volatility, dollar volume and sector, Newey-West errors, by year; top-quintile hit-rate lift for singles, pairs and triples drawn from 18 columns (10 aggregates plus the 8 strongest sub-scores); a frozen-recipe search (up to 3 gate conditions plus 1 rank, top 20/day) frozen on 2021-23, checked on 2024, run once on 2025-26, with a 200-shuffle permutation null.
KNOWN LIMITS: combinations came from the strongest singles, not from AQE's own absolute-threshold gates; measured fixed-horizon returns, not trade outcomes with structural stops/targets; survivorship-biased universe.
