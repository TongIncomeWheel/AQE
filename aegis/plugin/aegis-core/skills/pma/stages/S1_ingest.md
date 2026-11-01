# S1 — INGEST (deterministic) · GitHub is the source of record

**PM ruling 2026-08-12: nothing sits in Drive.** Drive is where AQE happens to write; it is
not where Aegis reads from. S1 is the boundary that moves the day's data into the repo and
never lets a downstream stage touch Drive again.

## Canonical location — LOCKED. Do not deviate.

**PM ruling 2026-08-13, restated and locked 2026-08-14.** One destination, fixed
filenames, overwritten every day. No date folders, no `latest.json` pointer, no
gzip, no retention job — the PM does not want an archive, and the timestamp that
identifies a run lives *inside* each file (`date` and `exported_at` in the
export, `generated_at` in the Crown files).

**Repo `TongIncomeWheel/AQE`, branch `main`, folder `aegis/output/`.**

```
aegis/output/
├── aqe_daily_export.json     the main daily pipeline export — the full AQE scan
├── aqe_crown_macro.json      Nick Crown committee read (plain English first, ~14KB)
├── aqe_macro_pack.json       the fifth door — Crown + scenarios + SRM + Thematic,
│                             sector/theme agreement check (AGREES/DISAGREES/UNTESTED)
├── manifest.json             provenance: sha256, bytes, generated_at, fetched_at,
│                             schema_version, staleness_days
└── … the rest of the day's artifacts (`src/data/github_sync.py` DAILY_ARTIFACTS, 11 files)
```

**Rules.**
- **This pointer is fixed.** Any stage, tool, agent or skill that reads AQE data
  reads `aegis/output/` on `main`. Not Drive, not a dated folder, not a local
  path, not a session download. If a file is absent from this folder, that is a
  reported failure — it is never a reason to go looking somewhere else.
- Every stage after S1 reads `aegis/output/`. **No stage other than S1 may call
  a Drive tool.** Enforceable by review: grep for Drive tool names outside S1.
- **Nothing hardcodes a date, because no path contains one.** The indirection
  that `latest.json` used to provide is gone along with the need for it.
- **Freshness is a check, not a lookup.** With a fixed path, reading the file
  always succeeds — so the `date` inside it must be compared against the run
  date on every read. A stale file at a fixed path is the one failure this
  layout can produce that the dated layout could not, and it is silent unless
  S1 checks. That check is mandatory, and it belongs in Validation below.
- No retention job. Git history holds prior versions if anyone ever needs one;
  nothing in the working tree accumulates.
- The AQE pipeline writes this folder directly (`src/data/github_sync.py`,
  `OUTPUT_DIR_IN_REPO = "aegis/output"`, published at
  `daily_orchestrator.py` step 8a-2), so on a normal day S1 has nothing to
  fetch and only has to validate.

## Publish-leg health (checked, not assumed)

`github_sync.publish_daily_outputs()` requires `GITHUB_TOKEN` or
`AQE_GITHUB_TOKEN` in AQE's environment. Without it every call returns
`{"ok": false, "reason": "GITHUB_TOKEN not set — GitHub sync disabled"}` — an
import-safe soft failure that leaves the day looking successful while nothing
was written.

**S1 must not paper over this.** If a required artifact is missing from
`aegis/output/`, or its internal date is behind the run date, S1 records the
publish leg as FAILED in the receipt and says so in the report's first section.
A silent decline is the failure mode this stage exists to catch.

## The fetch (code, not agent)

On a normal day there is **no fetch**. S1 reads what is already in the working
tree and goes straight to Validation.

The Drive fetch survives only as the emergency fallback for a day the publish
leg is down. `tools/pma_ingest.py` runs in-process and streams Drive → disk →
commit. **It must not run inside an agent's context**: the payload
base64-encodes to several MB and would blow any context window it passed
through (this was gap G1, found the hard way). The ingest tool is the only
component that holds the raw file, and it holds it as bytes on disk, never as
tokens. Using the fallback is itself a reported degradation, never a silent
substitution.

## Validation

1. Export → `contracts/aqe_export.schema.json`, then `tools/tripwires.py` (blocks on anomaly).
2. Crown → `contracts/pma/crown_macro.schema.json`. `status: DEGRADED` is **not** a failure; it
   propagates with its `limits[]` verbatim. Macro pack → `pack_status: PARTIAL` likewise
   propagates, with the coherence sections absent rather than empty.
3. Freshness — export `date` must equal run date; Crown `generated_at` must equal run date AND
   `how_current.oldest_source_days_behind` is carried forward (a run stamped today built on
   three-week-old legs is a three-week-old read, whatever the timestamp says — Crown C28).
4. Stale beyond tolerance → `proceed: false` unless an explicit `--ack "<reason>"` is supplied,
   and the ack text is recorded verbatim in the receipt and reprinted in the final plan.

## Output

`data/pma/<date>/ingest_receipt.json` (`contracts/pma/ingest_receipt.schema.json`) — per file:
found / fetched_at / generated_at / staleness_days / schema_valid / tripwire_result /
degraded_flags[]; plus `proceed`, `blocking_reason`, `pm_ack`, `publish_leg`.

**Failure ladder.** Export missing/invalid/tripwired → STOP, no plan. Crown missing →
`proceed: true`, `crown_absent: true`, and the plan's first line says the regime read is
AQE-only. Macro pack missing → `proceed: true`, coherence check absent and named as absent.
A missing input is refused, never zeroed.
