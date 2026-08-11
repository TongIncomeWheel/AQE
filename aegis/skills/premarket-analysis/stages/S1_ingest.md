# S1 — INGEST (deterministic)

**Job.** Fetch the day's two inputs from the AQE Drive folder, prove they are today's and
well-formed, land them locally, stamp a receipt. Nothing else.

**Inputs (Google Drive, folder `1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger`):**
1. `aqe_daily_export.json` — the full AQE scan (validate against `contracts/aqe_export.schema.json`; run `tools/tripwires.py`)
2. `aqe_crown_macro.json` — the Nick Crown macro layer (no schema exists yet — validate structurally: required top-level keys `status`, `read_me_first`, `the_call`, `readings`, `key_levels`, `limits`; authoring `contracts/pma/crown_macro.schema.json` is an open backlog item)

**Freshness rules.**
- Export `date` must equal the run date (T-1 tolerated only with an explicit PM acknowledgement, per RB:data_sources.staleness).
- Crown `generated_at` must be the run date; additionally read `how_current.oldest_source_days_behind` — the read is only as current as its oldest leg, whatever the timestamp says.
- `status: DEGRADED` in the crown file is NOT a failure — it propagates as a flag with its `limits[]` verbatim.

**Output.** `data/pma/DATE/ingest_receipt.json` (contract: `contracts/pma/ingest_receipt.schema.json`):
per-file {found, fetched_at, generated_at, staleness_days, schema_valid, tripwire_result,
degraded_flags[]}, plus overall `proceed: true|false` and `blocking_reason`.

**Failure.** Export missing/invalid/tripwired → `proceed: false`, kernel stops, no plan.
Crown missing → `proceed: true` with `crown_absent: true` — the plan runs AQE-only and says so.
