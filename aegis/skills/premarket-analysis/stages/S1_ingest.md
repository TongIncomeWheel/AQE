# S1 — INGEST (deterministic) · GitHub is the source of record

**PM ruling 2026-08-12: nothing sits in Drive.** Drive is where AQE happens to write; it is
not where Aegis reads from. S1 is the boundary that moves the day's data into the repo and
never lets a downstream stage touch Drive again.

## Canonical location (the consistent path)

**PM ruling 2026-08-13 supersedes the dated-folder layout below it.** One
destination, fixed filenames, overwritten every day. No date folders, no
`latest.json` pointer, no gzip, no retention job — the PM does not want an
archive, and the timestamp that identifies a run lives *inside* each file
(`date` and `exported_at` in the export, `generated_at` in the Crown file).

```
aegis/output/
├── aqe_daily_export.json     the full AQE scan
├── aqe_crown_macro.json      the Nick Crown macro layer
├── manifest.json             provenance: sha256, bytes, generated_at, fetched_at, schema_version, staleness_days
└── … the rest of the day's artifacts (see docs/AQE_DATA_TAXONOMY.md §1)
```

**Rules.**
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
- The AQE pipeline writes this folder directly at 08:30 SGT
  (`src/data/github_sync.py`), so on a normal day S1 has nothing to fetch and
  only has to validate. The Drive fetch is the fallback for a day the pipeline
  could not publish.

## The fetch (code, not agent)

On a normal day there is **no fetch**. The AQE pipeline publishes `aegis/output/`
itself at 08:30 SGT, so S1 reads what is already in the working tree and goes
straight to Validation.

The Drive fetch survives only as the fallback for a day the pipeline could not
publish. `tools/pma_ingest.py` runs in-process and streams Drive → disk →
commit. **It must not run inside an agent's context**: the 2.6 MB payload
base64-encodes to ~3.5 MB and would blow any context window it passed through
(this was gap G1, found the hard way). The ingest tool is the only component
that holds the raw file, and it holds it as bytes on disk, never as tokens.

If that fetch also fails, S1 uses the `aegis/output/` files already in the repo
and marks `staleness_days` from the `date` inside them — the repo is the source
of record, so a Drive outage degrades the run, it does not stop it. **A fixed
path always reads, so staleness is the only thing standing between a degraded
run and a wrong one.** Validation item 3 is not optional.

## Validation

1. Export → `contracts/aqe_export.schema.json`, then `tools/tripwires.py` (blocks on anomaly).
2. Crown → `contracts/pma/crown_macro.schema.json`. `status: DEGRADED` is **not** a failure; it
   propagates with its `limits[]` verbatim.
3. Freshness — export `date` must equal run date; Crown `generated_at` must equal run date AND
   `how_current.oldest_source_days_behind` is carried forward (a run stamped today built on
   three-week-old legs is a three-week-old read, whatever the timestamp says — Crown C28).
4. Stale beyond tolerance → `proceed: false` unless an explicit `--ack "<reason>"` is supplied,
   and the ack text is recorded verbatim in the receipt and reprinted in the final plan.

## Output

`data/pma/<date>/ingest_receipt.json` (`contracts/pma/ingest_receipt.schema.json`) — per file:
found / fetched_at / generated_at / staleness_days / schema_valid / tripwire_result /
degraded_flags[]; plus `proceed`, `blocking_reason`, `pm_ack`.

**Failure ladder.** Export missing/invalid/tripwired → STOP, no plan. Crown missing →
`proceed: true`, `crown_absent: true`, and the plan's first line says the regime read is
AQE-only. A missing input is refused, never zeroed.
