# Committee Standard Scan and Committee AQE Quant Scan (PM 2026-11-16)

Purpose: prove whether the committee WITHOUT the AQE gate has more edge than AQE. Display names only; internal ids never change
(`AEGIS_REPORT=A/C`, run dir suffix `-C`, ledger `report` column, manifest ids). Report B was removed 2026-11-17 (its run dirs and ledger rows stay as history only)..

| Report | Display name | Candidate pool | Live |
|---|---|---|---|
| A | Committee Standard Scan | the whole screened universe (mcap >= $2B, 10-day vol >= 500K, NYSE/NASDAQ) via seven per-seat code screens, top 25 per seat; no AQE gate, no AQE door; nominations cap 6 | yes |
| C | Committee AQE Quant Scan | AQE's OWN scored list (`daily_list`); only aqe-quant nominates (cap 6); all 8 seats vote with the AQE indicators; takes NOTHING from A | no |

The seats KEEP every AQE field in both scans (the committee is free to use AQE filters, scores and data); the only change to the committee is the candidate pool.
AQE is tested, not hidden: every name is tagged "AQE-listed: Longlist / Elder / QS / none" plus its AQE scores (or "AQE score not available"), logged in the ledger, and
the scorecard splits the Standard Scan's picks into AQE-listed and not.

`method` lives in `run_manifest.json`: `whole_universe` (A, from 2026-11-16), `aqe_doors` (the old chain), `fallback_aqe_doors` (LOUD fallback when
`aqe_universe_rows.json` is missing or refused), `quant_scan` (C). method_change_date = 2026-11-16.

Code: `pma_pipeline.py screens | coverage | augment-export`, `aqe_listing.py`, `scan_funnel.py`, `registrar.py init --method`.
`augment-export` writes `aqe_daily_export_wu.json` (a copy of the export plus the screened names the AQE daily list lacks, tagged `universe_only`); every later command takes it as `--export`.
`packets --clean` (strip AQE membership and scores) exists but is cancelled and unused.

Funnel strip (`scan_funnel.py`, code only): the count at every stage and, from "in the room" on, each name that fell out with the tool file's own reason and its AQE tag.
Ledger rows carry `method`, `aqe_listed`, `aqe_lists`, `aqe_scores` (frozen at the pick date). `report_compare` / `pma_scorecard` grade A1 (old method), A2 (Standard Scan),
A2L (AQE-listed picks) and A2N (not AQE-listed picks) as separate series against SPY and the AQE equal-weight list; they are never pooled.
