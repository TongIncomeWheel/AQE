# DATA SHELVES (four, matching the daily rhythm) — Drive-synced; janitor keeps growth flat
- sod/YYYY-MM-DD/        start of day: universe, AQE working read, 10 nomination files, committee file, plan
- intraday/YYYY-MM-DD/   alert fires, wake logs, staging previews/refusals, trade entries
- eod/YYYY-MM-DD/        journal, portfolio metrics, audit, design-review output
- persistent/            ledger.jsonl · pipeline tracking · week posture memory · voice memories · cs_weekly/ · journal_seed · rollups/
- archive/               monthly zips written by tools/janitor.py after RB:retention.raw_days + legacy_* from the one-time migration
Rules: dated folders are immutable once the day closes · janitor rolls up then archives raw days > retention.raw_days · nothing is ever deleted, only archived with a manifest.
