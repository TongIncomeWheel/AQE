# Committee Standard Scan and Committee AQE Quant Scan (PM 2026-11-16)

Purpose: prove whether the committee WITHOUT the AQE gate has more edge than AQE. Display names only; internal ids never change
(`AEGIS_REPORT=A/B/C`, run dir suffixes `-B/-C`, ledger `report` column, manifest ids).

| Report | Display name | Candidates | Live |
|---|---|---|---|
| A | Committee Standard Scan | whole screened universe (mcap >= $2B, 10-day vol >= 1.5M, NYSE/NASDAQ): 25 names per seat from code screens, no AQE gate, no AQE door; nominations cap 6 | yes |
| C | Committee AQE Quant Scan | whole AQE universe, code quant screen (top 30 by AQE rank + top 6 on Flow, Energy, Structure, MP, Elder); only aqe-quant nominates (cap 6); all 8 seats vote with the AQE indicators; takes NOTHING from A | no |
| B | Report B | frozen 2026-11-16 (ledger rows stay as their own series) | no |

`method` lives in `run_manifest.json`: `whole_universe` (A, from 2026-11-16), `aqe_doors` (the old chain), `fallback_aqe_doors` (LOUD fallback when
`aqe_universe_rows.json` is missing or refused), `quant_scan` (C), `report_b`. method_change_date = 2026-11-16.

Code: `pma_pipeline.py screens | coverage | augment-export | packets --clean | quant-screen`, `aqe_listing.py`, `registrar.py init --method`.
`augment-export` writes `aqe_daily_export_wu.json` (a copy of the export plus the screened names the AQE daily list lacks, tagged `universe_only`);
every later command takes it as `--export`.

Clean test: seat packets carry no AQE list membership and no AQE composite or engine score (`CLEAN_STRIP` in `pma_pipeline.py`); declared in a
`# CLEAN TEST` line and `packets/clean_test.json`; `check.py` fails a packet that carries a stripped column. Stage 2 (re-expressing the four screen fields
structure_shift, structure score, mp_state, rs_leadership on raw price) is a later PM call; until then every brief, Cards page and scorecard carries:
*Seat screens use AQE structure and momentum-phase fields, not AQE list membership or scores.*

Write-up: every name shows "AQE-listed: Longlist / Elder / QS / none" plus its AQE scores, or "AQE score not available" (never blank). PTRS is not an export field and is never claimed.
Ledger rows carry `method`, `aqe_listed`, `aqe_lists`, `aqe_scores` (frozen at the pick date). `report_compare` / `pma_scorecard` grade A1 (old method), A2 (Standard Scan),
A2L (AQE-listed picks) and A2N (not AQE-listed picks) as separate series against SPY and the AQE equal-weight list; they are never pooled.
