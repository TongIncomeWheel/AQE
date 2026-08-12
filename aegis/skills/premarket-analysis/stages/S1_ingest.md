# S1 — INGEST (deterministic) · GitHub is the source of record

**PM ruling 2026-08-12: nothing sits in Drive.** Drive is where AQE happens to write; it is
not where Aegis reads from. S1 is the boundary that moves the day's data into the repo and
never lets a downstream stage touch Drive again.

## Canonical location (the consistent path)

```
data/aqe/<YYYY-MM-DD>/
├── aqe_daily_export.json.gz      the full AQE scan   (gzip: ~2.6 MB → ~250 KB)
├── aqe_crown_macro.json          the Nick Crown macro layer (~25 KB, uncompressed — read daily by humans)
└── manifest.json                 provenance: sha256, bytes, generated_at, fetched_at, source_file_id, schema_version, staleness_days
data/aqe/latest.json              {"date": "YYYY-MM-DD", "manifest_sha": "..."} — the only pointer anything follows
```

**Rules.**
- Every stage after S1 reads `data/aqe/<date>/`. **No stage other than S1 may call a Drive tool.** This is enforceable by review: grep for Drive tool names outside S1.
- `latest.json` is the single indirection. Nothing hardcodes a date.
- Gzip the export, not the Crown file: the export is machine-only and huge; the Crown file is small and gets read by people.
- **Retention:** last 90 days live in-tree; older dates are pruned by `tools/pma_retention.py` to `data/aqe/archive/<YYYY-MM>.tar.gz`. At ~250 KB/day gzipped this is ~90 MB/yr — acceptable in git. Uncompressed it would be ~650 MB/yr, which is not. The gzip decision is what makes the PM's "GitHub not Drive" ruling affordable.
- Commit message convention: `DATA: AQE export + Crown macro for <date>` — one commit per day, so `git log data/aqe/` is the feed's own audit trail.

## The fetch (code, not agent)

`tools/pma_ingest.py` runs in-process and streams Drive → disk → gzip → commit. **It must not
run inside an agent's context**: the 2.6 MB payload base64-encodes to ~3.5 MB and would blow
any context window it passed through (this was gap G1, found the hard way). The ingest tool is
the only component that holds the raw file, and it holds it as bytes on disk, never as tokens.

If the Drive fetch fails, S1 falls back to the newest `data/aqe/<date>/` already in the repo
and marks `staleness_days` accordingly — the repo is the source of record, so a Drive outage
degrades the run, it does not stop it.

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
